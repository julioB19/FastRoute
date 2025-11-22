from typing import Dict, List
from banco_dados import BancoDados


class ServicoUsuario:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def cadastrar_usuario(self, dados_usuario: Dict) -> (bool, str):
        try:
            nome = dados_usuario["nome"]
            senha = dados_usuario["senha"]
            cargo = dados_usuario["cargo"]

            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("SELECT 1 FROM USUARIO WHERE NOME = %s", (nome,))
                if cursor.fetchone() is not None:
                    conn.rollback()
                    return False, f"Ja existe um usuario cadastrado com o nome {nome}."

                cursor.execute(
                    """
                    INSERT INTO USUARIO (NOME, SENHA, CARGO)
                    VALUES (%s, %s, %s)
                    """,
                    (nome, senha, cargo),
                )
                conn.commit()
                return True, f"Usuario {nome} cadastrado com sucesso!"
        except Exception as e:
            print(f"Erro ao cadastrar usuario: {e}")
            return False, f"Erro ao cadastrar usuario: {e}"

    def listar_usuarios(self) -> List[Dict]:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT ID_USUARIO, NOME, CARGO
                    FROM USUARIO
                    WHERE CARGO <> 99
                    ORDER BY NOME
                    """
                )
                registros = cursor.fetchall()
                usuarios = []
                for r in registros:
                    usuarios.append({"id": r[0], "nome": r[1], "cargo": r[2]})
                return usuarios
        except Exception as e:
            print(f"Erro ao listar usuarios: {e}")
            return []

    def excluir_usuario(self, usuario_id: int) -> (bool, str):
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    UPDATE USUARIO
                    SET CARGO = 99
                    WHERE ID_USUARIO = %s
                    """,
                    (usuario_id,),
                )

                if cursor.rowcount == 0:
                    conn.rollback()
                    return False, "Nenhum usuario encontrado para exclusao."

                conn.commit()
                return True, "Usuario excluido com sucesso!"
        except Exception as e:
            print(f"Erro ao excluir usuario: {e}")
            return False, f"Erro ao excluir usuario: {e}"

    def atualizar_usuario(self, dados_usuario: Dict) -> (bool, str):
        try:
            usuario_id = dados_usuario["id"]
            nome = dados_usuario["nome"]
            senha = dados_usuario["senha"]
            cargo = dados_usuario["cargo"]

            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    UPDATE USUARIO
                    SET NOME = %s,
                        SENHA = %s,
                        CARGO = %s
                    WHERE ID_USUARIO = %s
                    """,
                    (nome, senha, cargo, usuario_id),
                )

                if cursor.rowcount == 0:
                    conn.rollback()
                    return False, f"Nenhum usuario encontrado com o ID {usuario_id} para atualizar."

                conn.commit()
                return True, f"Usuario {nome} atualizado com sucesso!"
        except Exception as e:
            print(f"Erro ao atualizar usuario: {e}")
            return False, f"Erro ao atualizar usuario: {e}"
