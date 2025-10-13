import pandas as pd
import psycopg2

# === CONFIGURAÇÕES DE CONEXÃO AO BANCO ===
conn = psycopg2.connect(
    dbname="db_fr",
    user="postgres",
    password="1234",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# === LEITURA DA PLANILHA ===
arquivo = "PPI.xlsx"  # caminho do arquivo
df = pd.read_excel(arquivo)

# === TRATAMENTO DE DADOS ===

# Remover linhas com NF nula
df = df[df['NfNumero'].notnull()]

# Preenche nomes fictícios para clientes
clientes_unicos = df['NfForCod'].unique()
clientes_dict = {codigo: f"Cliente {i+1}" for i, codigo in enumerate(clientes_unicos)}

# Função de classificação do produto
def classificar(familia, grupo):
    if familia == 2 and grupo == 11:
        return 2
    return 1

# === INSERÇÃO DOS DADOS ===
for _, linha in df.iterrows():
    try:
        # --- CLIENTE ---
        id_cliente = int(linha['NfForCod'])
        nome_cliente = clientes_dict[id_cliente]

        cursor.execute("SELECT 1 FROM CLIENTE WHERE ID_CLIENTE = %s", (id_cliente,))
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO CLIENTE (ID_CLIENTE, NOME_CLIENTE)
                VALUES (%s, %s)
            """, (id_cliente, nome_cliente))

        # --- ENDEREÇO ---
        cidade = str(linha['MunNom']) if pd.notnull(linha['MunNom']) else ''
        bairro = str(linha['TraBairro']) if pd.notnull(linha['TraBairro']) else ''
        numero = str(linha['TraNumEnd']) if pd.notnull(linha['TraNumEnd']) else ''
        tipo_logradouro = str(linha['TraEnd']) if pd.notnull(linha['TraEnd']) else ''
        complemento = str(linha['TraComplemento']) if pd.notnull(linha['TraComplemento']) else ''

        cursor.execute("""
            SELECT ID_ENDERECO FROM ENDERECO_CLIENTE
            WHERE ID_CLIENTE = %s AND CIDADE = %s AND BAIRRO = %s AND NUMERO = %s
                  AND TIPO_LOGRADOURO = %s AND COALESCE(COMPLEMENTO, '') = %s
        """, (id_cliente, cidade, bairro, numero, tipo_logradouro, complemento))
        endereco_existente = cursor.fetchone()

        if endereco_existente:
            id_endereco = endereco_existente[0]
        else:
            cursor.execute("""
                INSERT INTO ENDERECO_CLIENTE (ID_CLIENTE, CIDADE, BAIRRO, NUMERO, TIPO_LOGRADOURO, COMPLEMENTO)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING ID_ENDERECO
            """, (id_cliente, cidade, bairro, numero, tipo_logradouro, complemento))
            id_endereco = cursor.fetchone()[0]

        # --- PRODUTO ---
        id_produto = int(linha['ItemProCod'])
        nome_produto = str(linha['ProNom'])
        familia = int(linha['ProFamCod'])
        grupo = int(linha['ProGrpCod'])
        classificacao = classificar(familia, grupo)

        cursor.execute("SELECT 1 FROM PRODUTO WHERE ID_PRODUTO = %s", (id_produto,))
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO PRODUTO (ID_PRODUTO, NOME_PRODUTO, CLASSIFICACAO)
                VALUES (%s, %s, %s)
            """, (id_produto, nome_produto, classificacao))

        # --- PEDIDO ---
        n_nota = int(linha['NfNumero'])
        dt_nota = linha['NfDatEmis']

        cursor.execute("SELECT 1 FROM PEDIDO WHERE N_NOTA = %s", (n_nota,))
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO PEDIDO (N_NOTA, DT_NOTA, ID_CLIENTE, ID_ENDERECO)
                VALUES (%s, %s, %s, %s)
            """, (n_nota, dt_nota, id_cliente, id_endereco))

        # --- PRODUTO_PEDIDO ---
        qtd = float(linha['ItemQtdade'])
        cursor.execute("""
            SELECT 1 FROM PRODUTO_PEDIDO
            WHERE PEDIDO_N_NOTA = %s AND PRODUTO_ID_PRODUTO = %s
        """, (n_nota, id_produto))
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO PRODUTO_PEDIDO (PEDIDO_N_NOTA, PRODUTO_ID_PRODUTO, QUANT_PEDIDO)
                VALUES (%s, %s, %s)
            """, (n_nota, id_produto, qtd))

        conn.commit()

    except Exception as e:
        print(f"Erro ao processar linha {linha.get('NfNumero', '?')}: {e}")
        conn.rollback()

cursor.close()
conn.close()

print("✅ Importação concluída com sucesso!")
