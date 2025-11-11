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
        # 🔹 Leitura do CSV
        df = pd.read_csv(io.StringIO(arquivo.stream.read().decode('utf-8')), sep=',')
        df = df[df['NfForCod'].notnull() & (df['NfForCod'] != '')]
        df['NfForCod'] = df['NfForCod'].apply(lambda x: int(float(x)))
        df['NfNumero'] = df['NfNumero'].apply(lambda x: int(float(x)))
        df['ItemProCod'] = df['ItemProCod'].apply(lambda x: int(float(x)) if not pd.isna(x) else None)

        conn = conecta_db()
        cursor = conn.cursor()

        for index, row in df.iterrows():
            try:
                id_cliente = row['NfForCod']
                nome_cliente = f"Cliente {id_cliente}"

                # 🧩 CLIENTE
                cursor.execute("""
                    INSERT INTO CLIENTE (id_cliente, nome_cliente)
                    VALUES (%s, %s)
                    ON CONFLICT (id_cliente) DO UPDATE
                    SET nome_cliente = EXCLUDED.nome_cliente;
                """, (id_cliente, nome_cliente))

                # 🧩 ENDERECO_CLIENTE
                cursor.execute("""
                    INSERT INTO ENDERECO_CLIENTE (id_cliente, cidade, bairro, tipo_logradouro, numero, complemento)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (
                    id_cliente,
                    row.get('MunNom'),
                    row.get('TraBairro'),
                    row.get('TraEnd'),
                    str(row.get('TraNumEnd')) if pd.notna(row.get('TraNumEnd')) else None,
                    row.get('TraComplemento')
                ))

                # 🔍 ID_ENDERECO
                cursor.execute("""
                    SELECT id_endereco
                    FROM ENDERECO_CLIENTE
                    WHERE id_cliente = %s
                    AND cidade = %s
                    AND bairro = %s
                    AND tipo_logradouro = %s
                    LIMIT 1;
                """, (id_cliente, row.get('MunNom'), row.get('TraBairro'), row.get('TraEnd')))
                id_endereco = cursor.fetchone()[0]

                # 🧩 PRODUTO
                if row.get('ItemProCod'):
                    fam = int(float(row.get('ProFamCod'))) if pd.notna(row.get('ProFamCod')) else None
                    grp = int(float(row.get('ProGrpCod'))) if pd.notna(row.get('ProGrpCod')) else None
                    classificacao = 2 if fam == 2 and grp == 11 else 1

                    cursor.execute("""
                        INSERT INTO PRODUTO (id_produto, nome_produto, classificacao)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (id_produto) DO UPDATE
                        SET nome_produto = EXCLUDED.nome_produto,
                            classificacao = EXCLUDED.classificacao;
                    """, (row['ItemProCod'], row.get('ProNom', 'Produto sem nome'), classificacao))

                # 🧩 PEDIDO
                cursor.execute("""
                    INSERT INTO PEDIDO (n_nota, dt_nota, id_cliente, id_endereco)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (n_nota) DO UPDATE
                    SET dt_nota = EXCLUDED.dt_nota;
                """, (row['NfNumero'], row['NfDatEmis'], id_cliente, id_endereco))

                # 🧩 PRODUTO_PEDIDO
                if row.get('ItemProCod'):
                    qtd = float(str(row.get('ItemQtdade')).replace(',', '.')) if pd.notna(row.get('ItemQtdade')) else 1.0
                    cursor.execute("""
                        INSERT INTO PRODUTO_PEDIDO (pedido_n_nota, produto_id_produto, quant_pedido)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (pedido_n_nota, produto_id_produto) DO UPDATE
                        SET quant_pedido = EXCLUDED.quant_pedido;
                    """, (row['NfNumero'], row['ItemProCod'], qtd))

                conn.commit()

            except Exception as e:
                print(f"❌ Erro na linha {index}: {e}")
                conn.rollback()


        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Importação completa concluída com sucesso!"

    except Exception as e:
        return False, f"Erro ao processar arquivo: {e}"
