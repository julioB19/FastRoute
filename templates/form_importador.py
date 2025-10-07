# Importando a biblioteca pandas
import pandas as pd

# Caminho do arquivo CSV (altere conforme o nome do seu arquivo)
caminho_arquivo = "dados.csv"

# Lendo o arquivo CSV e armazenando o conteúdo em um DataFrame
df = pd.read_csv(caminho_arquivo)

# Exibindo as primeiras 5 linhas do DataFrame
# O comando .head() mostra as primeiras linhas (por padrão, 5)
print("Visualização inicial dos dados:")
print(df.head())

# ============================================================
# INFORMAÇÕES BÁSICAS SOBRE O DATAFRAME
# ============================================================
# O comando .info() mostra um resumo das colunas,
# tipos de dados e quantidade de valores não nulos.
# ============================================================
print("\nInformações do DataFrame:")
df.info()

# ============================================================
# ESTATÍSTICAS DESCRITIVAS
# ============================================================
# O comando .describe() mostra estatísticas básicas
# (média, desvio padrão, mínimo, máximo, quartis)
# apenas para colunas numéricas.
# ============================================================
print("\nEstatísticas descritivas:")
print(df.describe())

# ============================================================
# VISUALIZAÇÃO DE NOMES DAS COLUNAS
# ============================================================
# O atributo .columns lista os nomes de todas as colunas do DataFrame.
# ============================================================
print("\nNomes das colunas:")
print(df.columns)

# ============================================================
# DICAS:
# - Você pode usar parâmetros em pd.read_csv() como:
#     sep=";"      → se o separador for ponto e vírgula
#     encoding="utf-8"  → para definir a codificação
#     header=0     → define qual linha é o cabeçalho
# ============================================================
