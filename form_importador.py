import io
import math
from datetime import datetime, date

import pandas as pd
from banco_dados import BancoDados


class ServicoImportacao:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def _normaliza_colunas(self, cols):
        """
        Normaliza nomes de colunas: tira espaços, BOM, deixa em lowercase.
        Retorna lista normalizada.
        """
        res = []
        for c in cols:
            if not isinstance(c, str):
                res.append(c)
                continue
            c2 = c.strip().replace('\ufeff', '').lower()
            res.append(c2)
        return res

    def _parse_float_int_safe(self, valor):
        """
        Tenta converter para inteiro (via float) de forma segura, retorna None em falha.
        """
        try:
            if pd.isna(valor) or valor == '' or valor is None:
                return None
            # remove espaços e possíveis milhares
            s = str(valor).strip().replace(' ', '').replace(',', '.')
            # se for vazio depois do strip
            if s == '':
                return None
            return int(float(s))
        except Exception:
            return None

    def _parse_float_safe(self, valor):
        try:
            if pd.isna(valor) or valor is None or valor == '':
                return None
            s = str(valor).strip().replace(' ', '').replace(',', '.')
            if s == '':
                return None
            return float(s)
        except Exception:
            return None

    def _parse_date_safe(self, valor):
        """
        Tenta parsear a data em vários formatos comuns. Retorna None se falhar.
        """
        if pd.isna(valor) or valor is None:
            return None
        if isinstance(valor, (date, datetime)):
            return valor
        s = str(valor).strip()
        if s == '':
            return None
        # tenta pandas to_datetime com dayfirst True (brasileiro)
        try:
            dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
            if pd.isna(dt):
                return None
            return dt.to_pydatetime()
        except Exception:
            return None

    def importar_dados_csv(self, arquivo, tamanho_lote: int = 500):
        try:
            # -------------------------
            # LEITURA DO ARQUIVO
            # -------------------------
            conteudo = arquivo.read()
            if not conteudo or len(conteudo) == 0:
                return False, "Erro: arquivo recebido está vazio."

            try:
                texto = conteudo.decode("utf-8", errors="replace")
            except Exception:
                return False, "Erro ao decodificar arquivo CSV (UTF-8 inválido)."

            # tenta detectar separador: se tiver ';' usaremos ';' senão ','
            sep = ';' if ';' in texto.splitlines()[0] else ','
            df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)

            if df is None or df.empty:
                return False, "Erro: CSV sem dados ou sem colunas válidas."

            # normaliza nomes de colunas
            df.columns = self._normaliza_colunas(df.columns.tolist())

            # Verifica se coord existe (nome normalizado)
            if "coord" not in df.columns:
                return False, "Erro: coluna 'Coord' não encontrada no CSV."

            # renomeações úteis se usuário tiver nomes diferentes
            # (já normalizamos para lowercase sem espaços)
            # agora garantimos que colunas necessárias existam em forma normalizada
            required_like = {
                "nfforcod": ["nfforcod", "nf_for_cod", "nf_forcod", "forcod", "id_cliente"],
                "nfnumer o": ["nfnumer o", "nf_numero", "nfnumero", "nfnnumero", "nfn"],
                "nfnumero": ["nfnumero", "nf_numero", "nfn"],
                "nfdatemis": ["nfdatemis", "nf_dat_emis", "data_emissao", "dt_nota", "dt_nota"],
                # endereços
                "traend": ["traend", "endereco", "tra_end"],
                "trabairro": ["trabairro", "bairro", "tra_bairro"],
                "munnom": ["munnom", "municipio", "mun_nom"],
                "tranumend": ["tranumend", "numero", "tra_num_end", "tra_numend"],
                "tracomplemento": ["tracomplemento", "complemento", "tra_complemento"],
                # produtos/itens
                "itemprocod": ["itemprocod", "item_pro_cod", "itemprocod", "itemcod"],
                "itemqtidade": ["itemqtidade", "item_qtidade", "item_qtdade", "itemqtdade"],
                "profamcod": ["profamcod", "pro_fam_cod", "profamcod"],
                "progrpcod": ["progrpcod", "pro_grp_cod", "progrpcod"],
                "pronome": ["pronome", "pronm", "pron", "pronom", "pron"],
            }

            # helper para pegar o nome real de coluna no df a partir de lista de candidatos
            def acha_col(candidatos):
                for c in candidatos:
                    c_norm = c.strip().lower()
                    if c_norm in df.columns:
                        return c_norm
                return None

            col_nfforcod = acha_col(required_like["nfforcod"])
            col_nfnumero = acha_col(required_like["nfnumero"])
            col_nfdatemis = acha_col(required_like["nfdatemis"])
            col_traend = acha_col(required_like["traend"])
            col_trabairro = acha_col(required_like["trabairro"])
            col_munnom = acha_col(required_like["munnom"])
            col_tranumend = acha_col(required_like["tranumend"])
            col_tracomplemento = acha_col(required_like["tracomplemento"])
            col_itemprocod = acha_col(required_like["itemprocod"])
            col_itemqtidade = acha_col(required_like["itemqtidade"])
            col_profamcod = acha_col(required_like["profamcod"])
            col_progrpcod = acha_col(required_like["progrpcod"])
            col_pronom = acha_col(required_like["pronome"])
            col_coord = "coord"  # já garantido

            # valida colunas mínimas
            if not col_nfforcod or not col_nfnumero or not col_traend or not col_trabairro or not col_munnom:
                # mostra colunas para ajudar debug
                return False, f"Erro: CSV não contém colunas mínimas necessárias. Colunas encontradas: {df.columns.tolist()}"

            # remove linhas sem cliente
            df = df[df[col_nfforcod].notnull() & (df[col_nfforcod].str.strip() != '')]

            if df.empty:
                return False, "Erro: após filtro de NfForCod o CSV ficou vazio."

            # -------------------------
            # normaliza tipos em novas colunas auxiliares
            # -------------------------
            # converte algumas colunas para valores tratáveis
            df['_nfforcod_int'] = df[col_nfforcod].apply(self._parse_float_int_safe)
            df['_nfnumero_int'] = df[col_nfnumero].apply(self._parse_float_int_safe)
            df['_itemprocod_int'] = df[col_itemprocod].apply(self._parse_float_int_safe) if col_itemprocod else None
            df['_itemqt_float'] = df[col_itemqtidade].apply(self._parse_float_safe) if col_itemqtidade else None
            df['_nfdatemis_dt'] = df[col_nfdatemis].apply(self._parse_date_safe) if col_nfdatemis else None

            # começar a inserir
            with self.banco.obter_cursor() as (conn, cursor):
                total_processadas = 0

                for index, row in df.iterrows():
                    try:
                        id_cliente = row.get('_nfforcod_int')
                        if id_cliente is None:
                            # pula linha
                            print(f"DEBUG: pulando linha {index} por id_cliente inválido -> {row.get(col_nfforcod)}")
                            continue
                        nome_cliente = f"Cliente {id_cliente}"

                        # -------------------------
                        # CLIENTE: upsert via PK (id_cliente é PK)
                        # -------------------------
                        cursor.execute(
                            """
                            INSERT INTO CLIENTE (id_cliente, nome_cliente)
                            VALUES (%s, %s)
                            ON CONFLICT (id_cliente) DO UPDATE
                            SET nome_cliente = EXCLUDED.nome_cliente;
                            """,
                            (id_cliente, nome_cliente),
                        )

                        # -------------------------
                        # ENDERECO_CLIENTE: procurar endereço existente por combinação de campos
                        # se existe -> atualizar coordenadas (sevier); se não -> inserir
                        # -------------------------
                        cidade = row.get(col_munnom)
                        bairro = row.get(col_trabairro)
                        endereco = row.get(col_traend)
                        numero = str(row.get(col_tranumend)).strip() if col_tranumend and pd.notna(row.get(col_tranumend)) else None
                        complemento = row.get(col_tracomplemento) if col_tracomplemento and pd.notna(row.get(col_tracomplemento)) else None
                        coordenadas = row.get(col_coord) if pd.notna(row.get(col_coord)) else None

                        # busca por igualdade usando COALESCE para tratar None/NULL/'' consistentemente
                        cursor.execute(
                            """
                            SELECT id_endereco, coordenadas
                            FROM endereco_cliente
                            WHERE id_cliente = %s
                              AND cidade = %s
                              AND bairro = %s
                              AND endereco = %s
                              AND COALESCE(numero, '') = COALESCE(%s, '')
                              AND COALESCE(complemento, '') = COALESCE(%s, '')
                            LIMIT 1;
                            """,
                            (id_cliente, cidade, bairro, endereco, numero, complemento),
                        )
                        endereco_existente = cursor.fetchone()

                        if endereco_existente:
                            id_endereco = endereco_existente[0]
                            # atualiza coordenadas se vier algo novo (pode ser None também)
                            if coordenadas is not None:
                                cursor.execute(
                                    """
                                    UPDATE endereco_cliente
                                    SET coordenadas = %s
                                    WHERE id_endereco = %s;
                                    """,
                                    (coordenadas, id_endereco),
                                )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO endereco_cliente (
                                    id_cliente, cidade, bairro, endereco,
                                    numero, complemento, coordenadas
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING id_endereco;
                                """,
                                (id_cliente, cidade, bairro, endereco, numero, complemento, coordenadas),
                            )
                            res = cursor.fetchone()
                            id_endereco = res[0] if res else None

                        # -------------------------
                        # PRODUTO
                        # -------------------------
                        if col_itemprocod and row.get('_itemprocod_int') is not None:
                            id_produto = row.get('_itemprocod_int')
                            fam = self._parse_float_int_safe(row.get(col_profamcod)) if col_profamcod else None
                            grp = self._parse_float_int_safe(row.get(col_progrpcod)) if col_progrpcod else None
                            classificacao = 2 if (fam == 2 and grp == 11) else 1

                            cursor.execute(
                                """
                                INSERT INTO produto (id_produto, nome_produto, classificacao)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (id_produto) DO UPDATE
                                SET nome_produto = EXCLUDED.nome_produto,
                                    classificacao = EXCLUDED.classificacao;
                                """,
                                (id_produto, row.get(col_pronom) or 'Produto sem nome', classificacao),
                            )
                        else:
                            id_produto = None

                        # -------------------------
                        # PEDIDO
                        # -------------------------
                        n_nota = row.get('_nfnumero_int')
                        dt_nota = row.get('_nfdatemis_dt')
                        # insere ou atualiza pedido
                        if n_nota is not None:
                            cursor.execute(
                                """
                                INSERT INTO pedido (n_nota, dt_nota, id_cliente, id_endereco)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (n_nota) DO UPDATE
                                SET dt_nota = EXCLUDED.dt_nota,
                                    id_cliente = EXCLUDED.id_cliente,
                                    id_endereco = EXCLUDED.id_endereco;
                                """,
                                (n_nota, dt_nota, id_cliente, id_endereco),
                            )

                        # -------------------------
                        # PRODUTO_PEDIDO (itens)
                        # -------------------------
                        if id_produto is not None and n_nota is not None:
                            quant = row.get('_itemqt_float') if col_itemqtidade else None
                            if quant is None:
                                quant = 1.0
                            cursor.execute(
                                """
                                INSERT INTO produto_pedido (pedido_n_nota, produto_id_produto, quant_pedido)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (pedido_n_nota, produto_id_produto) DO UPDATE
                                SET quant_pedido = EXCLUDED.quant_pedido;
                                """,
                                (n_nota, id_produto, quant),
                            )

                        total_processadas += 1
                        if total_processadas % tamanho_lote == 0:
                            conn.commit()
                            print(f"DEBUG: committed {total_processadas} registros até agora.")

                    except Exception as linha_erro:
                        # loga a linha e o erro para facilitar debug e faz rollback parcial
                        print(f"Erro na linha {index}: {linha_erro} -- dados linha: {row.to_dict()}")
                        conn.rollback()

                # commit final
                conn.commit()
                print(f"DEBUG: importação finalizada. Total processadas: {total_processadas}")

            return True, "Importação concluída com sucesso!"

        except Exception as e:
            return False, f"Erro ao processar arquivo: {e}"

    # -----------------------------------------------------------------
    # FUNÇÕES DE CONSULTA
    # -----------------------------------------------------------------

    def buscar_clientes(self):
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT id_cliente, nome_cliente
                    FROM cliente
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
                cursor.execute("SELECT COUNT(*) FROM pedido;")
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
                    FROM pedido p
                    LEFT JOIN cliente c ON c.id_cliente = p.id_cliente
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
