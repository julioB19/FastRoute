from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
import psycopg2
import io
import re
from functools import wraps
from form_importador import importar_dados_csv
from form_cadastro_veiculos import cadastrar_veiculo_db, listar_veiculos_db, excluir_veiculo_db

app = Flask(__name__)
app.secret_key = 'fastrout'  # ⚠️ Mude para uma chave mais segura em produção!

# === CONFIGURAÇÕES DO BANCO DE DADOS (POSTGRESQL) ===
DB_USER = "postgres"
DB_PASSWORD = "fastrout"
DB_HOST = "127.0.0.1"
DB_PORT = "3380"
DB_NAME = "FastRoute"

# === FUNÇÃO DE CONEXÃO AO BANCO ===
def conecta_db():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


# === DECORATOR PARA EXIGIR LOGIN ===
from functools import wraps
def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# === ROTA INICIAL (LOGIN) ===
@app.route('/')
def login_page():
    return render_template('login.html')


# === PROCESSAMENTO DO LOGIN ===
@app.route('/login', methods=['POST'])
def login():
    nome = request.form['usuario']
    senha = request.form['senha']

    try:
        conn = conecta_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id_usuario, nome FROM USUARIO WHERE nome = %s AND senha = %s;",
            (nome, senha)
        )
        usuario = cursor.fetchone()

        cursor.close()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario[0]
            session['usuario_nome'] = usuario[1]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos.")
    except Exception as e:
        print(f"Erro Crítico de Banco de Dados: {e}")
        return render_template('login.html', erro="Erro de comunicação com o banco de dados. Tente novamente mais tarde.")


# === LOGOUT ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# === ROTAS PROTEGIDAS ===
@app.route('/home')
@login_obrigatorio
def home():
    return render_template('home.html', usuario=session.get('usuario_nome'))


@app.route('/importar', methods=['GET', 'POST'])
@login_obrigatorio
def importar_dados():
    return render_template('importar.html', usuario=session.get('usuario_nome'))


@app.route('/processar_importacao', methods=['POST'])
@login_obrigatorio
def processar_importacao():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return render_template('importar.html', erro="Nenhum arquivo selecionado.", usuario=session.get('usuario_nome'))

    sucesso, mensagem = importar_dados_csv(arquivo)

    if sucesso:
        return render_template('importar.html', sucesso=mensagem, usuario=session.get('usuario_nome'))
    else:
        return render_template('importar.html', erro=mensagem, usuario=session.get('usuario_nome'))


def buscar_clientes():
    try:
        conn = conecta_db()
        cursor = conn.cursor()

        # 🔹 Ajuste o nome dos campos conforme sua tabela real
        cursor.execute("""
            SELECT id_cliente, nome_cliente
            FROM CLIENTE
            ORDER BY id_cliente;
        """)
        clientes = cursor.fetchall()

        cursor.close()
        conn.close()

        print(f"✅ {len(clientes)} clientes encontrados.")
        return clientes

    except Exception as e:
        print(f"❌ Erro ao buscar clientes: {e}")
        return []
    
@app.route('/importar', methods=['GET', 'POST'])
@login_obrigatorio
def buscar_dados_clientes():
    clientes = buscar_clientes()  # 🔹 Busca clientes do banco
    return render_template('importar.html', usuario=session.get('usuario_nome'), clientes=clientes)


@app.route('/cadastro_veiculo', methods=['GET', 'POST'])
@login_obrigatorio
def cadastro_veiculo():
    return render_template('cadastro_veiculo.html', usuario=session.get('usuario_nome'))    

# Rota para processar o cadastro do Veículo (POST) - Endpoint: /cadastrar_veiculo
@app.route('/cadastrar_veiculo', methods=['POST'])
def cadastrar_veiculo():
    global conn, cursor

    conn = conecta_db()
    cursor = conn.cursor()    
    # Regex para Placa Brasil: LLLNNNN (Antiga) ou LLLNLNN (Mercosul)
    # A Placa deve ter 7 caracteres alfanuméricos no padrão LLL N [L/N] NN
    PLACA_REGEX = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', re.IGNORECASE)

    if not conn or not cursor:
        return render_template('cadastro_veiculo.html', erro="Erro: Não foi possível conectar ao banco de dados.")

    dados_form = request.form
    # Limpa espaços e converte para MAIÚSCULAS para padronizar a validação
    placa_input = dados_form.get('placa', '').strip().upper()
    
    # 1. VALIDAÇÃO DE REGEX DA PLACA
    if not PLACA_REGEX.match(placa_input):
        return render_template(
            'cadastro_veiculo.html', 
            erro="Formato de Placa inválido. Use o padrão brasileiro de 7 caracteres (Ex: ABC1234 ou ABC1D23).",
            form=dados_form
        )
    
    # 2. VALIDAÇÃO DE TIPO DOS DEMAIS CAMPOS
    try:
        
        dados_veiculo = {
            'placa': placa_input, 
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso']) 
        }
    except ValueError:
        return render_template(
            'cadastro_veiculo.html', 
            erro="Erro de formato: Verifique se os campos numéricos (Tipo de Carga, Limite de Peso) foram preenchidos corretamente.",
            form=dados_form
        )

    # 3. CHAMA O DRM
    sucesso, mensagem = cadastrar_veiculo_db(conn, cursor, dados_veiculo)
    
    if sucesso:
        # Padrão PRG: Redireciona para a rota GET para evitar reenvio do formulário
        return redirect(url_for('cadastro_veiculo', mensagem_sucesso=mensagem)) 
    else:
        # Falha: retorna erro e mantém os dados no formulário
        return render_template(
            'cadastro_veiculo.html',
            erro=mensagem,
            form=dados_form
        )
    
#Consultar Veículos
@app.route("/consultar_veiculos")
def consultar_veiculos():
    global conn, cursor

    conn = conecta_db()
    cursor = conn.cursor()

    veiculos = listar_veiculos_db(conn, cursor)

    return render_template(
        "cadastro_veiculo.html",
        veiculos=veiculos,
        erro=None,
        aba="consulta"
    )    

#Excluir Veículo
@app.route("/excluir_veiculo/<placa>", methods=["POST"])
def excluir_veiculo(placa):
    global conn, cursor

    conn = conecta_db()
    cursor = conn.cursor()

    excluir_veiculo_db(conn, cursor, placa)
    return redirect(url_for("consultar_veiculos", aba="consulta"))

if __name__ == '__main__':
    app.run(debug=True)
