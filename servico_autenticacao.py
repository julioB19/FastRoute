from banco_dados import BancoDados


class ServicoAutenticacao:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def autenticar_usuario(self, nome: str, senha: str):
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    "SELECT id_usuario, nome FROM USUARIO WHERE nome = %s AND senha = %s;",
                    (nome, senha),
                )
                usuario = cursor.fetchone()

            if usuario:
                return True, {"id": usuario[0], "nome": usuario[1]}, None
            return False, None, "Usuario ou senha invalidos."

        except Exception as e:
            print(f"Erro ao autenticar usuario: {e}")
            return False, None, "Erro ao comunicar com o banco de dados."
