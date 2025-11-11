import psycopg2

def cadastrar_veiculo_db(conn, cursor, dados_veiculo):
    """
    Realiza a lógica de validação de duplicidade e inserção de um novo veículo
    no banco de dados.

    Args:
        conn: Objeto de conexão com o banco de dados (psycopg2).
        cursor: Objeto cursor do banco de dados (psycopg2).
        dados_veiculo (dict): Dicionário contendo os dados do veículo.

    Returns:
        tuple: (True, mensagem_sucesso) em caso de sucesso, 
               (False, mensagem_erro) em caso de falha.
    """
    try:
        placa = dados_veiculo['placa']
        marca = dados_veiculo['marca']
        modelo = dados_veiculo['modelo']
        tipo_carga = dados_veiculo['tipo_carga']
        limite_peso = dados_veiculo['limite_peso']

        # 1. VERIFICAR EXISTÊNCIA (RNF07)
        # Verifica se já existe um veículo com a mesma PLACA (chave primária)
        cursor.execute("SELECT 1 FROM VEICULO WHERE PLACA = %s", (placa,))
        if cursor.fetchone() is not None:
            conn.rollback() 
            return False, f"Já existe um veículo cadastrado com a placa {placa}. A Placa é uma chave única e não pode ser duplicada."
        
        # 2. INSERÇÃO (INSERT)
        cursor.execute("""
            INSERT INTO VEICULO (PLACA, MARCA, MODELO, TIPO_CARGA, LIMITE_PESO)
            VALUES (%s, %s, %s, %s, %s)
        """, (placa, marca, modelo, tipo_carga, limite_peso))
        
        # 3. TRANSAÇÃO BEM SUCEDIDA (COMMIT)
        conn.commit()

        return True, f"Veículo de placa {placa} cadastrado com sucesso!"

    except Exception as e:
        # 4. TRANSAÇÃO FALHA (ROLLBACK)
        conn.rollback()
        print(f"Erro no DRM ao cadastrar veículo: {e}")
        return False, f"Erro interno do sistema ao cadastrar o veículo: {e}"