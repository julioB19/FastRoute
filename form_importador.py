import pandas as pd
import psycopg2
import io

def conecta_db():
    return psycopg2.connect(
        dbname="FastRoute",
        user="postgres",
        password="fastrout",
        host="127.0.0.1",
        port="3380"
    )

def importar_dados_csv(arquivo):
    try:
        df = pd.read_csv(io.StringIO(arquivo.stream.read().decode('utf-8')), sep=',')
        df = df[df['NfForCod'].notnull() & (df['NfForCod'] != '')]
        df['NfForCod'] = df['NfForCod'].apply(lambda x: int(float(x)))

        conn = conecta_db()
        cursor = conn.cursor()

        for index, row in df.iterrows():
            try:
                id_cliente = row['NfForCod']
                nome_cliente = f"Cliente {id_cliente}"

                cursor.execute("""
                    INSERT INTO CLIENTE (id_cliente, nome_cliente)
                    VALUES (%s, %s)
                    ON CONFLICT (id_cliente) DO UPDATE
                    SET nome_cliente = EXCLUDED.nome_cliente;
                """, (id_cliente, nome_cliente))

            except Exception as e:
                print(f"Erro na linha {index}: {e}")

        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Importação de clientes concluída com sucesso!"

    except Exception as e:
        return False, f"Erro ao processar arquivo: {e}"
