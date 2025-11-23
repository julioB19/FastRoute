from typing import List, Dict, Any, Optional, Tuple
import math
import datetime

class ServicoPedidosImportados:
    def __init__(self, banco_dados=None, por_pagina: int = 10):
        """
        banco_dados: instância do seu módulo BancoDados (pode ser None para modo local)
        por_pagina: quantidade de registros por página para paginação
        """
        self.banco = banco_dados
        self.por_pagina = por_pagina

        # Dados de fallback/local para desenvolvimento sem BD
        self._clientes_demo = [
            {"id": 1, "nome": "Cliente A"},
            {"id": 2, "nome": "Cliente B"},
            {"id": 3, "nome": "Cliente C"},
        ]
        self._pedidos_demo = [
            {
                "id": 1,
                "numero_pedido": "IMP-0001",
                "cliente_id": 1,
                "cliente_nome": "Cliente A",
                "data_importacao": datetime.datetime.now().isoformat(),
                "status": "PENDENTE",
                "peso": 120.5,
                "endereco_entrega": "Rua A, 123",
                "observacoes": "",
            },
            {
                "id": 2,
                "numero_pedido": "IMP-0002",
                "cliente_id": 2,
                "cliente_nome": "Cliente B",
                "data_importacao": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
                "status": "ENTREGUE",
                "peso": 45.0,
                "endereco_entrega": "Av. B, 456",
                "observacoes": "Fragil",
            },
        ]

    # Utilitários para executar SELECT no banco de dados de forma genérica
    def _execute_select(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        if not self.banco:
            return []

        # Se o objeto banco_dados fornecer um método genérico, use-o
        if hasattr(self.banco, "executar_query"):
            try:
                result = self.banco.executar_query(query, params or ())
                # assumir que executar_query já devolve lista de dicts
                return result
            except Exception:
                pass

        # Tentar usar conexão/cursor (psycopg2-style)
        conn = getattr(self.banco, "conn", None) or getattr(self.banco, "connection", None) or None
        cursor = None
        try:
            if conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                cols = [d[0] for d in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return [dict(zip(cols, r)) for r in rows]
            # Alguns wrappers expõem cursor diretamente
            if hasattr(self.banco, "cursor"):
                cursor = self.banco.cursor()
                cursor.execute(query, params or ())
                cols = [d[0] for d in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return [dict(zip(cols, r)) for r in rows]
        finally:
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass

        # Se nenhum método funcionou, retornar lista vazia
        return []

    # Buscar clientes (para filtro na tela)
    def buscar_clientes(self) -> List[Dict[str, Any]]:
        if not self.banco:
            return self._clientes_demo
        query = "SELECT id, nome FROM cliente ORDER BY nome;"
        rows = self._execute_select(query)
        if rows:
            return rows
        # fallback vazio se não houver resultado
        return []

    def _build_filtros_sql(self, filtros: Optional[Dict[str, Any]]) -> Tuple[str, List[Any]]:
        where_parts = []
        params: List[Any] = []
        if not filtros:
            return "", params
        if filtros.get("cliente_id"):
            where_parts.append("p.cliente_id = %s")
            params.append(int(filtros["cliente_id"]))
        if filtros.get("status"):
            where_parts.append("p.status = %s")
            params.append(filtros["status"])
        if filtros.get("data_inicio"):
            where_parts.append("p.data_importacao >= %s")
            params.append(filtros["data_inicio"])
        if filtros.get("data_fim"):
            where_parts.append("p.data_importacao <= %s")
            params.append(filtros["data_fim"])
        if where_parts:
            return " WHERE " + " AND ".join(where_parts), params
        return "", params

    def contar_pedidos(self, filtros: Optional[Dict[str, Any]] = None) -> int:
        if not self.banco:
            return len(self._pedidos_demo)
        where_sql, params = self._build_filtros_sql(filtros)
        query = "SELECT COUNT(1) AS total FROM pedidos_importados p" + where_sql + ";"
        rows = self._execute_select(query, tuple(params))
        if rows and "total" in rows[0]:
            return int(rows[0]["total"])
        # tentar outras chaves se o wrapper devolver outro formato
        if rows and len(rows) > 0:
            first = rows[0]
            v = list(first.values())[0]
            return int(v)
        return 0

    def listar_pedidos(self, pagina: int = 1, filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Retorna:
        {
            "pedidos": [ ... ],
            "pagina": pagina,
            "total_paginas": total_paginas,
            "total_registros": total_registros
        }
        """
        if pagina < 1:
            pagina = 1

        if not self.banco:
            total = len(self._pedidos_demo)
            total_paginas = math.ceil(total / self.por_pagina) if total else 1
            start = (pagina - 1) * self.por_pagina
            end = start + self.por_pagina
            return {
                "pedidos": self._pedidos_demo[start:end],
                "pagina": pagina,
                "total_paginas": total_paginas,
                "total_registros": total,
            }

        where_sql, params = self._build_filtros_sql(filtros)
        # Selecionar campos (ajuste conforme seu schema)
        query = (
            "SELECT p.id, p.numero_pedido, p.cliente_id, c.nome AS cliente_nome, "
            "p.data_importacao, p.status, p.peso, p.endereco_entrega, p.observacoes "
            "FROM pedidos_importados p "
            "LEFT JOIN cliente c ON c.id = p.cliente_id "
            + where_sql +
            " ORDER BY p.data_importacao DESC, p.id DESC "
            "LIMIT %s OFFSET %s;"
        )
        # calcular paginação
        offset = (pagina - 1) * self.por_pagina
        params_for_query = (params or []) + [self.por_pagina, offset]
        rows = self._execute_select(query, tuple(params_for_query))

        total = self.contar_pedidos(filtros)
        total_paginas = math.ceil(total / self.por_pagina) if total else 1
        return {
            "pedidos": rows,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "total_registros": total,
        }

    def buscar_pedido_por_id(self, pedido_id: int) -> Optional[Dict[str, Any]]:
        if not self.banco:
            for p in self._pedidos_demo:
                if p["id"] == int(pedido_id):
                    return p
            return None
        query = (
            "SELECT p.id, p.numero_pedido, p.cliente_id, c.nome AS cliente_nome, "
            "p.data_importacao, p.status, p.peso, p.endereco_entrega, p.observacoes "
            "FROM pedidos_importados p "
            "LEFT JOIN cliente c ON c.id = p.cliente_id "
            "WHERE p.id = %s LIMIT 1;"
        )
        rows = self._execute_select(query, (int(pedido_id),))
        return rows[0] if rows else None

    # Opcional: método para atualizar status/entrega (pode ser usado pelo controller)
    def atualizar_status(self, pedido_id: int, novo_status: str) -> Tuple[bool, str]:
        if not self.banco:
            for p in self._pedidos_demo:
                if p["id"] == int(pedido_id):
                    p["status"] = novo_status
                    return True, "Status atualizado (modo local)."
            return False, "Pedido não encontrado (modo local)."
        # Executar update parametizado
        try:
            # tentar usar método de execução do wrapper
            if hasattr(self.banco, "executar_comando"):
                self.banco.executar_comando("UPDATE pedidos_importados SET status = %s WHERE id = %s;", (novo_status, int(pedido_id)))
                return True, "Status atualizado."
            # fallback para conexão raw
            conn = getattr(self.banco, "conn", None) or getattr(self.banco, "connection", None) or None
            if conn:
                cur = conn.cursor()
                cur.execute("UPDATE pedidos_importados SET status = %s WHERE id = %s;", (novo_status, int(pedido_id)))
                conn.commit()
                cur.close()
                return True, "Status atualizado."
        except Exception as e:
            return False, f"Erro ao atualizar status: {e}"
        return False, "Não foi possível atualizar status: interface do banco desconhecida."