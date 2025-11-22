from typing import Dict, List, Optional
from banco_dados import BancoDados


class ServicoVeiculo:
    def __init__(self, banco: BancoDados):
        self.banco = banco

    def cadastrar_veiculo(self, dados_veiculo: Dict) -> (bool, str):
        try:
            placa = dados_veiculo['placa']
            marca = dados_veiculo['marca']
            modelo = dados_veiculo['modelo']
            tipo_carga = dados_veiculo['tipo_carga']
            limite_peso = dados_veiculo['limite_peso']

            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute("SELECT 1 FROM VEICULO WHERE PLACA = %s", (placa,))
                if cursor.fetchone() is not None:
                    conn.rollback()
                    return False, f"Ja existe um veiculo cadastrado com a placa {placa}."

                cursor.execute(
                    """
                    INSERT INTO VEICULO (PLACA, MARCA, MODELO, TIPO_CARGA, LIMITE_PESO)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (placa, marca, modelo, tipo_carga, limite_peso),
                )
                conn.commit()
                return True, f"Veiculo de placa {placa} cadastrado com sucesso!"

        except Exception as e:
            print(f"Erro ao cadastrar veiculo: {e}")
            return False, f"Erro ao cadastrar veiculo: {e}"

    def listar_veiculos(self) -> List[Dict]:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT PLACA, MARCA, MODELO, TIPO_CARGA, LIMITE_PESO
                    FROM VEICULO
                    WHERE TIPO_CARGA <> 99
                    ORDER BY PLACA
                    """
                )
                registros = cursor.fetchall()
                veiculos = []
                for r in registros:
                    veiculos.append(
                        {
                            "placa": r[0],
                            "marca": r[1],
                            "modelo": r[2],
                            "tipo_carga": r[3],
                            "limite_peso": r[4],
                        }
                    )
                return veiculos
        except Exception as e:
            print(f"Erro ao listar veiculos: {e}")
            return []

    def excluir_veiculo(self, placa: str) -> (bool, str):
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    UPDATE VEICULO
                    SET TIPO_CARGA = 99
                    WHERE PLACA = %s
                    """,
                    (placa,),
                )

                if cursor.rowcount == 0:
                    conn.rollback()
                    return False, f"Nenhum veiculo encontrado com a placa {placa}."

                conn.commit()
                return True, f"Veiculo de placa {placa} excluido com sucesso!"

        except Exception as e:
            print(f"Erro ao excluir veiculo: {e}")
            return False, f"Erro ao excluir veiculo: {e}"

    def buscar_por_placa(self, placa: str) -> Optional[Dict]:
        try:
            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT PLACA, MARCA, MODELO, TIPO_CARGA, LIMITE_PESO
                    FROM VEICULO
                    WHERE PLACA = %s
                    """,
                    (placa,),
                )
                r = cursor.fetchone()
                if r:
                    return {
                        "placa": r[0],
                        "marca": r[1],
                        "modelo": r[2],
                        "tipo_carga": r[3],
                        "limite_peso": r[4],
                    }
                return None
        except Exception as e:
            print(f"Erro ao buscar veiculo por placa: {e}")
            return None

    def atualizar_veiculo(self, dados_veiculo: Dict) -> (bool, str):
        try:
            placa = dados_veiculo['placa']
            marca = dados_veiculo['marca']
            modelo = dados_veiculo['modelo']
            tipo_carga = dados_veiculo['tipo_carga']
            limite_peso = dados_veiculo['limite_peso']

            with self.banco.obter_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    UPDATE VEICULO
                    SET MARCA = %s,
                        MODELO = %s,
                        TIPO_CARGA = %s,
                        LIMITE_PESO = %s
                    WHERE PLACA = %s
                    """,
                    (marca, modelo, tipo_carga, limite_peso, placa),
                )

                if cursor.rowcount == 0:
                    conn.rollback()
                    return False, f"Nenhum veiculo encontrado com a placa {placa} para atualizar."

                conn.commit()
                return True, f"Veiculo de placa {placa} atualizado com sucesso!"

        except Exception as e:
            print(f"Erro ao atualizar veiculo: {e}")
            return False, f"Erro ao atualizar veiculo: {e}"
