import pandas as pd
from sqlalchemy import create_engine

DB_USER = "postgres"
DB_PASSWORD = "fastrout"
DB_HOST = "localhost"
DB_PORT = "3380"
DB_NAME = "FastRoute"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL) 

conn = engine.connect() 

sql = 'SELECT * FROM USUARIO;'

DF = pd.read_sql_query(sql, conn)

conn.close()