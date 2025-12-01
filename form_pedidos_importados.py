from typing import List, Dict, Any, Optional, Tuple
import math
import datetime


class ServicoPedidosImportados:
    def __init__(self, banco_dados=None, por_pagina: int = 99999):
        self.banco = banco_dados
        self.por_pagina = por_pagina

    # -----------------------------------------------------
    # EXECUTOR DE SELECT 100% COMPATÍVEL COM SEU BancoDados
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
    # Lista de clientes para filtro
    # -----------------------------------------------------
    def buscar_clientes(self):
        query = """
            SELECT id_cliente AS id, nome_cliente AS nome
            FROM CLIENTE
            ORDER BY nome_cliente;
        """
        return self._execute_select(query)

    # -----------------------------------------------------
    # Funções NOVAS para o dashboard
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
    # Construção dos filtros do frontend
    # -----------------------------------------------------
    def _build_filtros_sql(self, filtros: Optional[Dict[str, Any]]):
        where_parts = []
        params = []

        if not filtros:
            return "", params

        if filtros.get("cliente_id"):
            where_parts.append("p.id_cliente = %s")
            params.append(int(filtros["cliente_id"]))

        if filtros.get("data_inicio"):
            where_parts.append("p.dt_nota >= %s")
            params.append(filtros["data_inicio"])

        if filtros.get("data_fim"):
            where_parts.append("p.dt_nota <= %s")
            params.append(filtros["data_fim"])

        if filtros.get("coords_not_null"):
            where_parts.append("ec.coordenadas IS NOT NULL AND ec.coordenadas <> ''")

        if filtros.get("coords_null"):
            where_parts.append("ec.coordenadas IS NULL OR ec.coordenadas = ''")

        if filtros.get("entregues"):
            where_parts.append(
                "EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota)"
            )

        if filtros.get("excluir_entregues"):
            where_parts.append(
                "NOT EXISTS (SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota)"
            )

        if where_parts:
            return " WHERE " + " AND ".join(where_parts), params

        return "", params

    # -----------------------------------------------------
    # Mapeamento do pedido → frontend
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

        # PADRÃO: usar ENTREGUE (singular) para consistência com o mapa
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
            "status": status,
            "_orig": row,
        }

    # -----------------------------------------------------
    # Contar total para paginação
    # -----------------------------------------------------
    def contar_pedidos(self, filtros: Optional[Dict[str, Any]] = None) -> int:
        where_sql, params = self._build_filtros_sql(filtros)
        query = f"""
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql};
        """
        rows = self._execute_select(query, tuple(params))
        return int(rows[0]["total"]) if rows else 0

    # -----------------------------------------------------
    # Listar pedidos
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
    # Buscar pedido (header da modal)
    # -----------------------------------------------------
    def buscar_pedido_por_id(self, pedido_id: int):
        query = """
            SELECT
                p.n_nota,
                p.dt_nota,
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
    # Itens do pedido (com texto Normal / Agrotóxico)
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

    def contar_com_filtros(self, filtros):
        # Usa o MESMO builder correto
        where_sql, params = self._build_filtros_sql(filtros)

        sql = f"""
            SELECT COUNT(*) AS total
            FROM PEDIDO p
            LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
            {where_sql};
        """

        rows = self._execute_select(sql, tuple(params))
        return rows[0]["total"] if rows else 0
