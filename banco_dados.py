import psycopg2
from contextlib import contextmanager
from typing import Any, Dict


class ConfiguracaoBanco:
    def __init__(self, nome: str, usuario: str, senha: str, host: str, porta: str):
        self.nome = nome
        self.usuario = usuario
        self.senha = senha
        self.host = host
        self.porta = porta

    def como_dict(self) -> Dict[str, Any]:
        return {
            "dbname": self.nome,
            "user": self.usuario,
            "password": self.senha,
            "host": self.host,
            "port": self.porta,
        }


class BancoDados:
    def __init__(self, configuracao: ConfiguracaoBanco):
        self.configuracao = configuracao

    def conectar(self):
        return psycopg2.connect(**self.configuracao.como_dict())

    @contextmanager
    def obter_cursor(self):
        conexao = self.conectar()
        cursor = conexao.cursor()
        try:
            yield conexao, cursor
        finally:
            cursor.close()
            conexao.close()
