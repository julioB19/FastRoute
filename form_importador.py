import io
import pandas as pd
from banco_dados import BancoDados
from typing import List, Dict, Tuple


class ServicoImportacao:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def importar_dados_csv(self, arquivo, tamanho_lote: int = 500) -> Tuple[bool, str]:
        try:
            df = pd.read_csv(io.StringIO(arquivo.stream.read().decode('utf-8')), sep=',')
            df = df[df['NfForCod'].notnull() & (df['NfForCod'] != '')]
            df['NfForCod'] = df['NfForCod'].apply(lambda x: int(float(x)))
            df['NfNumero'] = df['NfNumero'].apply(lambda x: int(float(x)))
            df['ItemProCod'] = df['ItemProCod'].apply(lambda x: int(float(x)) if not pd.isna(x) else None)

            with self.banco.obter_cursor() as (conn, cursor):
                total_processadas = 0

                for index, row in enumerate(df.itertuples(index=False), start=1):
                    # Evita perder as linhas ja persistidas em caso de erro de formato
                    try:
                        id_cliente = row.NfForCod
                        nome_cliente = f"Cliente {id_cliente}"

                        cursor.execute(
                            """
                            INSERT INTO CLIENTE (id_cliente, nome_cliente)
                            VALUES (%s, %s)
                            ON CONFLICT (id_cliente) DO UPDATE
                            SET nome_cliente = EXCLUDED.nome_cliente;
                            """,
                            (id_cliente, nome_cliente),
                        )

                        cursor.execute(
                            """
                            INSERT INTO ENDERECO_CLIENTE (id_cliente, cidade, bairro, tipo_logradouro, numero, complemento)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (
                                id_cliente,
                                row.MunNom,
                                row.TraBairro,
                                row.TraEnd,
                                str(row.TraNumEnd) if pd.notna(row.TraNumEnd) else None,
                                row.TraComplemento,
                            ),
                        )

                        cursor.execute(
                            """
                            SELECT id_endereco
                            FROM ENDERECO_CLIENTE
                            WHERE id_cliente = %s
                                AND cidade = %s
                                AND bairro = %s
                                AND tipo_logradouro = %s
                            LIMIT 1;
                            """,
                            (id_cliente, row.MunNom, row.TraBairro, row.TraEnd),
                        )
                        res = cursor.fetchone()
                        if not res:
                            conn.commit()
                            continue
                        id_endereco = res[0]

                        if row.ItemProCod:
                            fam = int(float(row.ProFamCod)) if pd.notna(row.ProFamCod) else None
                            grp = int(float(row.ProGrpCod)) if pd.notna(row.ProGrpCod) else None
                            classificacao = 2 if fam == 2 and grp == 11 else 1

                            cursor.execute(
                                """
                                INSERT INTO PRODUTO (id_produto, nome_produto, classificacao)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (id_produto) DO UPDATE
                                SET nome_produto = EXCLUDED.nome_produto,
                                    classificacao = EXCLUDED.classificacao;
                                """,
                                (
                                    row.ItemProCod,
                                    getattr(row, 'ProNom', 'Produto sem nome'),
                                    classificacao,
                                ),
                            )

                        cursor.execute(
                            """
                            INSERT INTO PEDIDO (n_nota, dt_nota, id_cliente, id_endereco)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (n_nota) DO UPDATE
                            SET dt_nota = EXCLUDED.dt_nota, id_cliente = EXCLUDED.id_cliente, id_endereco = EXCLUDED.id_endereco;
                            """,
                            (row.NfNumero, row.NfDatEmis, id_cliente, id_endereco),
                        )

                        if row.ItemProCod:
                            qtd_bruta = str(row.ItemQtdade) if pd.notna(row.ItemQtdade) else "1"
                            qtd = float(qtd_bruta.replace(',', '.')) if qtd_bruta else 1.0
                            cursor.execute(
                                """
                                INSERT INTO PRODUTO_PEDIDO (pedido_n_nota, produto_id_produto, quant_pedido)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (pedido_n_nota, produto_id_produto) DO UPDATE
                                SET quant_pedido = EXCLUDED.quant_pedido;
                                """,
                                (row.NfNumero, row.ItemProCod, qtd),
                            )

                        total_processadas += 1
                        if total_processadas % tamanho_lote == 0:
                            conn.commit()

                    except Exception as linha_erro:
                        print(f"Erro na linha {index}: {linha_erro}")
                        conn.rollback()

                conn.commit()

            return True, "Importação concluida com sucesso!"
        except Exception as e:
            return False, f"Erro ao processar arquivo: {e}"

    def buscar_clientes(self):
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT id_cliente, nome_cliente
                    FROM CLIENTE
                    ORDER BY id_cliente;
                    """
                )
                return cursor.fetchall()
        except Exception as e:
            print(f"Erro ao buscar clientes: {e}")
            return []

    # -------------------------
    # Métodos adicionados para dashboard e tela de pedidos
    # -------------------------
    def contar_pedidos(self) -> int:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("SELECT COUNT(*) FROM PEDIDO;")
                r = cursor.fetchone()
                return r[0] if r else 0
        except Exception as e:
            print(f"Erro ao contar pedidos: {e}")
            return 0

    def contar_pedidos_divergentes(self) -> int:
        """
        Conta pedidos cujo endereço não possui coordenadas válidas.
        Usa ENDERECO_CLIENTE.COORDENADAS (varchar). Considera 'NULL' ou '' ou sem vírgula como inválido.
        """
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM PEDIDO p
                    JOIN ENDERECO_CLIENTE ec ON p.id_endereco = ec.id_endereco
                    WHERE ec.coordenadas IS NULL
                       OR trim(ec.coordenadas) = ''
                       OR position(',' IN ec.coordenadas) = 0;
                """)
                r = cursor.fetchone()
                return r[0] if r else 0
        except Exception as e:
            print(f"Erro ao contar pedidos divergentes: {e}")
            return 0

    def contar_entregas_ultimo_mes(self) -> int:
        """
        Conta entregas (ENTREGA.DATA_ENTREGA) nos últimos 30 dias.
        """
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM ENTREGA
                    WHERE DATA_ENTREGA IS NOT NULL
                      AND DATA_ENTREGA BETWEEN current_date - interval '30 days' AND current_date;
                """)
                r = cursor.fetchone()
                return r[0] if r else 0
        except Exception as e:
            print(f"Erro ao contar entregas do ultimo mes: {e}")
            return 0

    def listar_datas_entregas(self) -> List:
        """
        Retorna uma lista de datas (YYYY-MM-DD) de entregas ocorridas nos últimos 30 dias.
        """
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("""
                    SELECT DISTINCT DATA_ENTREGA
                    FROM ENTREGA
                    WHERE DATA_ENTREGA IS NOT NULL
                      AND DATA_ENTREGA BETWEEN current_date - interval '30 days' AND current_date
                    ORDER BY DATA_ENTREGA;
                """)
                rows = cursor.fetchall()
                return [r[0] for r in rows if r and r[0] is not None]
        except Exception as e:
            print(f"Erro ao listar datas de entregas: {e}")
            return []

    def listar_entregas_pendentes(self) -> List[Dict]:
        """
        Retorna lista de entregas pendentes com coordenadas para o mini-mapa.
        Retorna dicts: { "n_nota": <int>, "lat": <float>, "lng": <float>, "cliente": <str> }
        Critério: entrega não concluída (ENTREGA.STATUS != 'ENTREGUE' ou não existe) e ENDERECO_CLIENTE.COORDENADAS válida.
        """
        marcadores = []
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("""
                    SELECT p.n_nota, ec.coordenadas, c.nome_cliente
                    FROM PEDIDO p
                    LEFT JOIN ENTREGA e ON e.pedido_n_nota = p.n_nota
                    JOIN ENDERECO_CLIENTE ec ON p.id_endereco = ec.id_endereco
                    LEFT JOIN CLIENTE c ON p.id_cliente = c.id_cliente
                    WHERE (e.id_entrega IS NULL OR lower(coalesce(e.status,'')) <> 'entregue')
                      AND ec.coordenadas IS NOT NULL
                      AND trim(ec.coordenadas) <> ''
                """)
                rows = cursor.fetchall()
                for r in rows:
                    n_nota = r[0]
                    coords = r[1]
                    cliente = r[2] if len(r) > 2 else None
                    try:
                        lat_str, lng_str = [s.strip() for s in coords.split(',')]
                        lat = float(lat_str)
                        lng = float(lng_str)
                        marcadores.append({"n_nota": n_nota, "lat": lat, "lng": lng, "cliente": cliente})
                    except Exception:
                        continue
        except Exception as e:
            print(f"Erro ao listar entregas pendentes: {e}")
        return marcadores

    def buscar_pedidos(self, filtro: str = "todos", data_prevista: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Busca pedidos para exibir na tela de pedidos importados.
        filtro: 'todos'|'completos'|'incompletos'
        data_prevista: string 'YYYY-MM-DD' para filtrar por DATA_ENTREGA (se existir campo de previsão)
        Retorna lista de dicts com campos: id (n_nota), cliente, cidade, endereco (concatenado), data_prevista, completo (bool)
        Observação: adapta conforme seu schema.
        """
        pedidos = []
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                sql = """
                    SELECT p.n_nota,
                           coalesce(c.nome_cliente, '—') as cliente,
                           ec.cidade,
                           concat_ws(' ', ec.tipo_logradouro, ec.ponto_referencia, coalesce(ec.numero,'')) as endereco,
                           e.data_entrega,
                           ec.coordenadas
                    FROM PEDIDO p
                    LEFT JOIN CLIENTE c ON p.id_cliente = c.id_cliente
                    LEFT JOIN ENDERECO_CLIENTE ec ON p.id_endereco = ec.id_endereco
                    LEFT JOIN ENTREGA e ON e.pedido_n_nota = p.n_nota
                """
                where_clauses = []
                params = []

                if filtro == 'completos':
                    where_clauses.append("e.status IS NOT NULL AND lower(e.status) = 'entregue'")
                elif filtro == 'incompletos':
                    where_clauses.append("(e.id_entrega IS NULL OR lower(coalesce(e.status,'')) <> 'entregue')")

                if data_prevista:
                    where_clauses.append("e.data_entrega = %s")
                    params.append(data_prevista)

                if where_clauses:
                    sql += " WHERE " + " AND ".join(where_clauses)

                sql += " ORDER BY p.n_nota DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                for r in rows:
                    n_nota = r[0]
                    cliente = r[1]
                    cidade = r[2]
                    endereco = r[3]
                    data_prev = r[4].isoformat() if r[4] is not None else None
                    coords = r[5]
                    completo = (coords is not None and coords.strip() != '')
                    pedidos.append({
                        "id": n_nota,
                        "cliente": cliente,
                        "cidade": cidade,
                        "endereco": endereco,
                        "data_prevista": data_prev,
                        "completo": completo
                    })
        except Exception as e:
            print(f"Erro ao buscar pedidos: {e}")
        return pedidos

    def buscar_pedido_por_id(self, n_nota: int) -> Dict:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("""
                    SELECT p.n_nota, c.nome_cliente, ec.cidade, ec.bairro, ec.tipo_logradouro, ec.numero, ec.coordenadas, e.status, e.data_entrega
                    FROM PEDIDO p
                    LEFT JOIN CLIENTE c ON p.id_cliente = c.id_cliente
                    LEFT JOIN ENDERECO_CLIENTE ec ON p.id_endereco = ec.id_endereco
                    LEFT JOIN ENTREGA e ON e.pedido_n_nota = p.n_nota
                    WHERE p.n_nota = %s
                """, (n_nota,))
                r = cursor.fetchone()
                if not r:
                    return {}
                return {
                    "n_nota": r[0],
                    "cliente": r[1],
                    "cidade": r[2],
                    "bairro": r[3],
                    "logradouro": r[4],
                    "numero": r[5],
                    "coordenadas": r[6],
                    "status_entrega": r[7],
                    "data_entrega": r[8].isoformat() if r[8] else None
                }
        except Exception as e:
            print(f"Erro ao buscar pedido por id: {e}")
            return {}
