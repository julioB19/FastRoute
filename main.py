from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from sqlalchemy import create_engine, text

app = Flask(__name__)

# CONFIGURAÇÕES DO BANCO DE DADOS (POSTGRESQL)
DB_USER = "postgres"
DB_PASSWORD = "fastrout"
DB_HOST = "127.0.0.1"
DB_PORT = "3380"
DB_NAME = "FastRoute"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Inicialização da Engine (Global)
try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    engine = None
    print(f"Erro ao conectar ao banco de dados: {e}")


# Primeira tela -> Login
@app.route('/')
def login_page():
    return render_template('login.html')

# Rota que processa o formulário de login
@app.route('/login', methods=['POST'])
def login():
    nome = request.form['usuario'] 
    senha = request.form['senha']

    try:
        sql_query = text("SELECT id FROM USUARIO WHERE nome = :username AND senha = :password;")

        DF = pd.read_sql_query(
            sql=sql_query,
            con=engine,
            params={"username": nome, "password": senha}
        )
        
        if not DF.empty:
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos.")

    except Exception as e:
        print(f"Erro Crítico de Banco de Dados: {e}")
        return render_template('login.html', erro="Erro de comunicação com o banco de dados. Tente novamente mais tarde.")

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/importar', methods=['GET', 'POST'])
def importar_dados():
    return render_template('importar.html')

if __name__ == '__main__':
    app.run(debug=True)

