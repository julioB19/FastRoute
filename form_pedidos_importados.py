from typing import List, Dict, Any, Optional, Tuple
import math
import datetime

from form_otimizacao_rota import (
    Entrega,
    Veiculo,
    encontrar_melhor_rota_genetico,
    gerar_matriz_distancias,
)

DEPOSITO_COORD_PADRAO = (-27.367681114267935, -53.40115242306388)


class ServicoPedidosImportados:
    def __init__(self, banco_dados=None, por_pagina: int = 99999):
        self.banco = banco_dados
        self.por_pagina = por_pagina

    # -----------------------------------------------------
    # Executor de SELECT compatível com BancoDados
    # -----------------------------------------------------
    def _execute_select(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(query, params or ())
                cols = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            print("Erro no SELECT:", e)
            print("Query:", query)
            print("Params:", params)
            return []

    # -----------------------------------------------------
    # Lista de clientes (para multi-seleção e pesquisa)
    # -----------------------------------------------------
    def buscar_clientes(self):
        query = """
            SELECT id_cliente, nome_cliente AS nome
            FROM CLIENTE
            ORDER BY nome_cliente;
        """
        return self._execute_select(query)

    # Para multi-seleção de notas
    def buscar_notas(self):
        query = """
            SELECT DISTINCT n_nota
            FROM PEDIDO
            ORDER BY n_nota DESC;
        """
        return self._execute_select(query)

    # -----------------------------------------------------
    # Dashboard
    # -----------------------------------------------------
    def contar_completos(self):
        query = """
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            WHERE ec.coordenadas IS NOT NULL AND ec.coordenadas <> '';
        """
        rows = self._execute_select(query)
        return rows[0]["total"] if rows else 0

    def contar_incompletos(self):
        query = """
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            WHERE ec.coordenadas IS NULL OR ec.coordenadas = '';
        """
        rows = self._execute_select(query)
        return rows[0]["total"] if rows else 0

    # -----------------------------------------------------
    # Builder dos filtros (NOVO)
    # -----------------------------------------------------
    def _build_filtros_sql(self, filtros: Optional[Dict[str, Any]]):

        where_parts = []
        params = []

        if not filtros:
            return "", params

        # ----------------------------
        # Filtro por nome parcial (digitável)
        # ----------------------------
        if filtros.get("cliente_nome"):
            where_parts.append("c.nome_cliente ILIKE %s")
            params.append(f"%{filtros['cliente_nome']}%")

        # ----------------------------
        # Multi seleção de clientes
        # ----------------------------
        clientes_multi = filtros.get("clientes_multi")
        if clientes_multi:
            placeholders = ", ".join(["%s"] * len(clientes_multi))
            where_parts.append(f"c.nome_cliente IN ({placeholders})")
            params.extend(clientes_multi)

        # ----------------------------
        # Período da nota
        # ----------------------------
        if filtros.get("data_inicio"):
            where_parts.append("p.dt_nota >= %s")
            params.append(filtros["data_inicio"])

        if filtros.get("data_fim"):
            where_parts.append("p.dt_nota <= %s")
            params.append(filtros["data_fim"])

        # ----------------------------
        # Período da entrega
        # ----------------------------
        if filtros.get("entrega_inicio"):
            where_parts.append("p.dt_entrega >= %s")
            params.append(filtros["entrega_inicio"])

        if filtros.get("entrega_fim"):
            where_parts.append("p.dt_entrega <= %s")
            params.append(filtros["entrega_fim"])

        # ----------------------------
        # Endereço
        # ----------------------------
        if filtros.get("endereco"):
            where_parts.append("ec.endereco ILIKE %s")
            params.append(f"%{filtros['endereco']}%")

        # ----------------------------
        # Cidade
        # ----------------------------
        if filtros.get("cidade"):
            where_parts.append("ec.cidade ILIKE %s")
            params.append(f"%{filtros['cidade']}%")

        # ----------------------------
        # Multi seleção de notas
        # ----------------------------
        notas_multi = filtros.get("notas_multi")
        if notas_multi:
            placeholders = ", ".join(["%s"] * len(notas_multi))
            where_parts.append(f"p.n_nota IN ({placeholders})")
            params.extend(notas_multi)

        # ----------------------------
        # Status via coordenadas
        # ----------------------------
        if filtros.get("coords_not_null"):
            where_parts.append("ec.coordenadas IS NOT NULL AND ec.coordenadas <> ''")

        if filtros.get("coords_null"):
            where_parts.append("ec.coordenadas IS NULL OR ec.coordenadas = ''")

        if filtros.get("entregues"):
            where_parts.append("EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota)")

        if filtros.get("excluir_entregues"):
            where_parts.append("NOT EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota)")

        if where_parts:
            return " WHERE " + " AND ".join(where_parts), params

        return "", params

    # -----------------------------------------------------
    # Conversor de linha -> dicionário frontend
    # -----------------------------------------------------
    def _map_pedido(self, row: Dict[str, Any]) -> Dict[str, Any]:

        def format_data(v):
            if not v:
                return None
            if isinstance(v, (datetime.date, datetime.datetime)):
                return v.strftime("%Y-%m-%d")
            return str(v)

        endereco = (
            f"{row.get('endereco') or ''} "
            f"{row.get('numero') or ''}, "
            f"{row.get('bairro') or ''}, "
            f"{row.get('cidade') or ''}"
        ).strip(" ,")

        coordenadas = row.get("coordenadas")
        tem_coords = coordenadas is not None and str(coordenadas).strip() != ""
        entregou = bool(row.get("entregues"))

        if entregou:
            status = "ENTREGUE"
        elif tem_coords:
            status = "COMPLETO"
        else:
            status = "INCOMPLETO"

        return {
            "id": row.get("n_nota"),
            "numero_pedido": row.get("n_nota"),
            "cliente": row.get("nome_cliente"),
            "endereco": endereco or "-",
            "data_nota": format_data(row.get("dt_nota")),
            "data_entrega": format_data(row.get("dt_entrega")),
            "status": status,
            "_orig": row,
        }

    # -----------------------------------------------------
    # Contar total de registros
    # -----------------------------------------------------
    def contar_pedidos(self, filtros: Optional[Dict[str, Any]] = None) -> int:
        where_sql, params = self._build_filtros_sql(filtros)
        query = f"""
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql};
        """
        rows = self._execute_select(query, tuple(params))
        return int(rows[0]["total"]) if rows else 0

    # -----------------------------------------------------
    # Listar pedidos (com todos os filtros)
    # -----------------------------------------------------
    def listar_pedidos(self, pagina: int = 1, filtros: Optional[Dict[str, Any]] = None):

        if pagina < 1:
            pagina = 1

        where_sql, params = self._build_filtros_sql(filtros)

        itens_por_pagina = filtros.get("itens_por_pagina", self.por_pagina)
        offset = (pagina - 1) * itens_por_pagina

        query = f"""
            SELECT
                p.n_nota,
                p.dt_nota,
                p.dt_entrega,
                p.id_cliente,
                c.nome_cliente,
                ec.cidade,
                ec.bairro,
                ec.endereco,
                ec.numero,
                ec.coordenadas,
                EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota) AS entregues
            FROM PEDIDO p
            LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql}
            ORDER BY p.dt_nota DESC NULLS LAST, p.n_nota DESC
            LIMIT %s OFFSET %s;
        """

        params = (params or []) + [itens_por_pagina, offset]
        rows = self._execute_select(query, tuple(params))

        total = self.contar_pedidos(filtros)
        total_paginas = max(math.ceil(total / itens_por_pagina), 1)

        pedidos = [self._map_pedido(r) for r in rows]

        return {
            "pedidos": pedidos,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "total_registros": total,
        }

    # -----------------------------------------------------
    # Modal de detalhes do pedido
    # -----------------------------------------------------
    def buscar_pedido_por_id(self, pedido_id: int):
        query = """
            SELECT
                p.n_nota,
                p.dt_nota,
                p.dt_entrega,
                p.id_cliente,
                c.nome_cliente,
                ec.cidade,
                ec.bairro,
                ec.endereco,
                ec.numero,
                ec.coordenadas,
                EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota) AS entregues
            FROM PEDIDO p
            LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            WHERE p.n_nota = %s
            LIMIT 1;
        """
        rows = self._execute_select(query, (pedido_id,))
        return rows[0] if rows else None

    # -----------------------------------------------------
    # Itens do pedido
    # -----------------------------------------------------
    def buscar_itens_pedido(self, n_nota: int):
        query = """
            SELECT
                pp.produto_id_produto,
                p.nome_produto,
                p.classificacao,
                pp.quant_pedido
            FROM PRODUTO_PEDIDO pp
            LEFT JOIN PRODUTO p ON p.id_produto = pp.produto_id_produto
            WHERE pp.pedido_n_nota = %s;
        """

        itens = self._execute_select(query, (n_nota,))

        for item in itens:
            if item.get("classificacao") == 2:
                item["classificacao_texto"] = "Agrotóxico"
            else:
                item["classificacao_texto"] = "Normal"

        return itens

    # -----------------------------------------------------
    # Dashboard contar com filtros
    # -----------------------------------------------------
    def contar_com_filtros(self, filtros):
        where_sql, params = self._build_filtros_sql(filtros)

        sql = f"""
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql};
        """

        rows = self._execute_select(sql, tuple(params))
        return rows[0]["total"] if rows else 0

    def listar_completos_para_otimizacao(
        self,
        limite: int = 50,
        cliente_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            limite = max(1, min(int(limite), 500))
        except Exception:
            limite = 50

        params = []
        where_parts = [
            "ec.coordenadas IS NOT NULL",
            "ec.coordenadas <> ''",
            "NOT EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota)",
        ]

        if cliente_id:
            where_parts.append("p.id_cliente = %s")
            params.append(int(cliente_id))

        where_sql = " WHERE " + " AND ".join(where_parts)

        query = f"""
            SELECT
                p.n_nota,
                p.dt_nota,
                c.nome_cliente,
                ec.cidade,
                ec.bairro,
                ec.numero,
                ec.coordenadas
            FROM PEDIDO p
            LEFT JOIN CLIENTE c ON c.id_cliente = p.id_cliente
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql}
            ORDER BY p.dt_nota DESC NULLS LAST, p.n_nota DESC
            LIMIT %s;
        """

        params.append(limite)
        rows = self._execute_select(query, tuple(params))
        return [self._map_pedido(r) for r in rows]

    # -----------------------------------------------------
    # OTIMIZA��O DE ROTAS
    # -----------------------------------------------------
    def _parse_coordenadas(self, coordenadas: Optional[str]) -> Optional[Tuple[float, float]]:
        if not coordenadas:
            return None
        try:
            lat_str, lng_str = str(coordenadas).split(",")
            return float(lat_str.strip()), float(lng_str.strip())
        except Exception:
            return None

    def _buscar_resumo_pedidos_para_otimizacao(self, pedido_ids: List[int]) -> List[Dict[str, Any]]:
        if not pedido_ids:
            return []

        placeholders = ",".join(["%s"] * len(pedido_ids))
        query = f"""
            SELECT
                p.n_nota,
                ec.coordenadas,
                COALESCE(SUM(pp.quant_pedido * COALESCE(pr.peso, 0)), 0) AS peso_total,
                COALESCE(MAX(CASE WHEN pr.classificacao = 2 THEN 2 ELSE 1 END), 1) AS tipo_carga
            FROM PEDIDO p
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            LEFT JOIN PRODUTO_PEDIDO pp ON pp.pedido_n_nota = p.n_nota
            LEFT JOIN PRODUTO pr ON pr.id_produto = pp.produto_id_produto
            WHERE p.n_nota IN ({placeholders})
            GROUP BY p.n_nota, ec.coordenadas;
        """
        return self._execute_select(query, tuple(pedido_ids))

    def _buscar_veiculos_para_otimizacao(self) -> List[Veiculo]:
        query = """
            SELECT placa, limite_peso, tipo_carga
            FROM VEICULO
            WHERE tipo_carga <> 99
        """
        rows = self._execute_select(query)

        veiculos = []
        for r in rows:
            try:
                veiculos.append(
                    Veiculo(
                        id=str(r.get("placa")),
                        limite_peso=float(r.get("limite_peso") or 0.0),
                        tipo_carga=int(r.get("tipo_carga") or 1),
                    )
                )
            except Exception:
                continue
        return veiculos

    def registrar_entregas_otimizadas(
        self,
        rotas_por_veiculo: Dict[str, List[str]],
        usuario_id: Optional[int] = None,
    ):
        """
        Marca pedidos das rotas como ENTREGUE e registra rota/usuario.
        """
        if not rotas_por_veiculo:
            return False, "Nenhuma rota calculada."

        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("SELECT COALESCE(MAX(id_entrega), 0) FROM entrega;")
                next_id = (cursor.fetchone() or [0])[0] + 1

                for veic, pedidos in (rotas_por_veiculo or {}).items():
                    if not pedidos:
                        continue
                    seq_descarga = ",".join(str(p) for p in pedidos)

                    for nota in pedidos:
                        nota_str = str(nota)
                        base_nota = nota_str.split("#")[0]
                        # ENTREGAS: upsert por pedido
                        if "#" not in nota_str:
                            cursor.execute(
                                "SELECT id_entrega FROM entrega WHERE pedido_n_nota = %s LIMIT 1;",
                                (base_nota,),
                            )
                            row = cursor.fetchone()
                        else:
                            row = None

                        if row:
                            id_entrega = row[0]
                            cursor.execute(
                                """
                                UPDATE entrega
                                SET status = %s,
                                    veiculo_placa = %s,
                                    data_entrega = CURRENT_DATE
                                WHERE id_entrega = %s;
                                """,
                                ("ENTREGUE", veic, id_entrega),
                            )
                        else:
                            id_entrega = next_id
                            next_id += 1
                            cursor.execute(
                                """
                                INSERT INTO entrega (id_entrega, status, pedido_n_nota, veiculo_placa, data_entrega)
                                VALUES (%s, %s, %s, %s, CURRENT_DATE);
                                """,
                                (id_entrega, "ENTREGUE", int(base_nota), veic),
                            )

                        # ROTA: uma rota por entrega, com a sequencia daquela rota do veiculo
                        cursor.execute(
                            "SELECT id_rota FROM rota WHERE entrega_id_entrega = %s LIMIT 1;",
                            (id_entrega,),
                        )
                        rota_row = cursor.fetchone()
                        if rota_row:
                            cursor.execute(
                                "UPDATE rota SET sequencia_descarga = %s WHERE id_rota = %s;",
                                (seq_descarga, rota_row[0]),
                            )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO rota (sequencia_descarga, entrega_id_entrega)
                                VALUES (%s, %s);
                                """,
                                (seq_descarga, id_entrega),
                            )

                        # USUARIO_ENTREGA: vincula o usuario logado se informado
                        if usuario_id:
                            cursor.execute(
                                """
                                INSERT INTO usuario_entrega (entrega_id_entrega, usuario_id_usuario)
                                VALUES (%s, %s)
                                ON CONFLICT (entrega_id_entrega, usuario_id_usuario) DO NOTHING;
                                """,
                                (id_entrega, int(usuario_id)),
                            )

                conn.commit()
            return True, None
        except Exception as e:
            print("Erro ao registrar entregas otimizadas:", e)
            return False, str(e)

    def otimizar_rotas(
        self,
        pedido_ids: List[int],
        deposito: Optional[Tuple[float, float]] = None,
        parametros_algoritmo: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not pedido_ids:
            raise ValueError("Nenhum pedido informado para otimizar.")

        if deposito is None:
            deposito = DEPOSITO_COORD_PADRAO

        if not deposito or len(deposito) != 2:
            raise ValueError("Coordenadas do deposito invalidas.")

        try:
            deposito_lat = float(deposito[0])
            deposito_lng = float(deposito[1])
        except Exception:
            raise ValueError("Coordenadas do deposito invalidas.")

        pedidos_resumo = self._buscar_resumo_pedidos_para_otimizacao(pedido_ids)
        veiculos = self._buscar_veiculos_para_otimizacao()

        if not veiculos:
            raise ValueError("Nenhum veiculo cadastrado para otimizar rotas.")

        coordenadas: List[Tuple[float, float]] = [(deposito_lat, deposito_lng)]
        entregas: List[Entrega] = []
        pedidos_sem_coord = []
        pedidos_sem_compat = []

        idx_matriz = 1
        for pedido in pedidos_resumo:
            coords = self._parse_coordenadas(pedido.get("coordenadas"))
            if not coords:
                pedidos_sem_coord.append(pedido.get("n_nota"))
                continue

            peso = float(pedido.get("peso_total") or 0.0)
            tipo_carga = int(pedido.get("tipo_carga") or 1)
            def veiculo_compativel(v):
                if tipo_carga == 2 and int(v.tipo_carga) != 2:
                    return False
                if int(v.tipo_carga) == 2 and tipo_carga != 2:
                    return False
                return int(v.tipo_carga) == tipo_carga

            # capacidade maxima entre veiculos compativeis
            caps_compativeis = [v.limite_peso for v in veiculos if veiculo_compativel(v)]
            if not caps_compativeis:
                pedidos_sem_compat.append(pedido.get("n_nota"))
                continue
            cap_max = max(caps_compativeis)
            if cap_max <= 0:
                raise ValueError("Limite de peso dos veiculos inválido.")

            partes = 1
            if peso > cap_max:
                partes = math.ceil(peso / cap_max)

            peso_parte = peso / partes if partes > 0 else peso

            for parte in range(partes):
                entrega_id = str(pedido.get("n_nota")) if partes == 1 else f"{pedido.get('n_nota')}#{parte+1}"
                coordenadas.append(coords)
                entregas.append(
                    Entrega(
                        id=entrega_id,
                        peso=float(peso_parte),
                        tipo_carga=tipo_carga,
                        indice_matriz=idx_matriz,
                    )
                )
                idx_matriz += 1

        if not entregas:
            msg_partes = []
            if pedidos_sem_coord:
                msg_partes.append(f"sem coordenadas: {pedidos_sem_coord}")
            if pedidos_sem_compat:
                msg_partes.append(f"sem veiculo compativel: {pedidos_sem_compat}")
            detalhe = " | ".join(msg_partes) if msg_partes else "Nenhum pedido elegivel."
            raise ValueError(f"Nenhum pedido otimizavel. {detalhe}")

        matriz = gerar_matriz_distancias(coordenadas)
        params = parametros_algoritmo or {}

        resultado = encontrar_melhor_rota_genetico(
            matriz,
            entregas,
            veiculos,
            deposito=0,
            tamanho_populacao=int(params.get("tamanho_populacao", 60)),
            geracoes=int(params.get("geracoes", 150)),
            taxa_mutacao=float(params.get("taxa_mutacao", 0.12)),
            tamanho_torneio=int(params.get("tamanho_torneio", 3)),
        )

        mapa_indices = {e.id: e.indice_matriz for e in entregas}

        # remove veiculos sem entregas (uma rota vazia nÆo representa entrega)
        rotas_filtradas = {
            vid: seq for vid, seq in (resultado.get("rotas_por_veiculo") or {}).items() if seq
        }
        resultado["rotas_por_veiculo"] = rotas_filtradas

        resultado.update(
            {
                "coordenadas_usadas": coordenadas,
                "pedidos_considerados": [e.id for e in entregas],
                "pedidos_sem_coordenadas": pedidos_sem_coord,
                "pedidos_sem_compativeis": pedidos_sem_compat,
                "mapa_indices": mapa_indices,
            }
        )
        return resultado
