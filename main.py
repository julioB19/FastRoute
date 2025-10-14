from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import psycopg2
import io
from form_importador import importar_dados_csv

app = Flask(__name__)
app.secret_key = 'fastrout'

# CONFIGURAÇÕES DO BANCO DE DADOS (POSTGRESQL)
DB_USER = "postgres"
DB_PASSWORD = "fastrout"
DB_HOST = "127.0.0.1"
DB_PORT = "3380"
DB_NAME = "FastRoute"

# === CONFIGURAÇÕES DE CONEXÃO AO BANCO ===
def conecta_db():
    conn = psycopg2.connect(
        dbname = DB_NAME,
        user = DB_USER,
        password = DB_PASSWORD,
        host = DB_HOST,
        port = DB_PORT
    )
    return conn

conn = conecta_db()
cursor = conn.cursor()

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
        # Use placeholders do psycopg2: %s (não :param)
        cursor.execute(
            "SELECT id_usuario FROM USUARIO WHERE nome = %s AND senha = %s;",
            (nome, senha)
        )

        # Recupera o resultado
        usuario = cursor.fetchone()

        if usuario:
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

@app.route('/processar_importacao', methods=['POST'])
def processar_importacao():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return render_template('importar.html', erro="Nenhum arquivo selecionado.")

    sucesso, mensagem = importar_dados_csv(arquivo)

    if sucesso:
        return render_template('importar.html', sucesso=mensagem)
    else:
        return render_template('importar.html', erro=mensagem)

if __name__ == '__main__':
    app.run(debug=True)

