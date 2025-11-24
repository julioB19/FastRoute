import io
import math
from datetime import date, datetime

import pandas as pd
from banco_dados import BancoDados


class ServicoImportacao:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def importar_dados_csv(self, arquivo, tamanho_lote: int = 500):
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
                        id_endereco = cursor.fetchone()[0]

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
                            SET dt_nota = EXCLUDED.dt_nota;
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

            return True, "Importação concluída com sucesso!"
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

    def listar_pedidos(self, pagina: int = 1, itens_por_pagina: int = 10):
        try:
            pagina = max(int(pagina), 1)
            itens_por_pagina = max(int(itens_por_pagina), 1)
        except (TypeError, ValueError):
            pagina = 1
            itens_por_pagina = 10

        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("SELECT COUNT(*) FROM PEDIDO;")
                total_registros = cursor.fetchone()[0] or 0

                total_paginas = max(math.ceil(total_registros / itens_por_pagina), 1) if total_registros else 1
                pagina = min(pagina, total_paginas)
                offset = (pagina - 1) * itens_por_pagina

                cursor.execute(
                    """
                    SELECT
                        p.n_nota,
                        p.dt_nota,
                        p.id_cliente,
                        c.nome_cliente
                    FROM PEDIDO p
                    LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
                    ORDER BY p.dt_nota DESC NULLS LAST, p.n_nota DESC
                    LIMIT %s OFFSET %s;
                    """,
                    (itens_por_pagina, offset),
                )
                colunas = [descricao[0].lower() for descricao in cursor.description]
                pedidos = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]

            for pedido in pedidos:
                data_nota = pedido.get("dt_nota")
                if isinstance(data_nota, (datetime, date)):
                    pedido["dt_nota_formatada"] = data_nota.strftime("%d/%m/%Y")
                elif data_nota:
                    pedido["dt_nota_formatada"] = str(data_nota)
                else:
                    pedido["dt_nota_formatada"] = None

            return {
                "pedidos": pedidos,
                "pagina": pagina,
                "total_paginas": total_paginas,
                "total_registros": total_registros,
                "itens_por_pagina": itens_por_pagina,
            }
        except Exception as e:
            print(f"Erro ao listar pedidos: {e}")
            return {
                "pedidos": [],
                "pagina": 1,
                "total_paginas": 1,
                "total_registros": 0,
                "itens_por_pagina": itens_por_pagina,
            }
