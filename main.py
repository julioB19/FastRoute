from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
import psycopg2
import io
import re
from functools import wraps
from form_importador import importar_dados_csv
from form_cadastro_veiculos import cadastrar_veiculo_db, listar_veiculos_db, excluir_veiculo_db, atualizar_veiculo_db

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


# === ROTAS DE VEÍCULOS ===

@app.route('/veiculos', methods=['GET'])
@login_obrigatorio
def veiculos_page():
    """
    Página principal de gerenciamento de veículos.
    Exibe o formulário e a lista de veículos cadastrados.
    """
    conn = conecta_db()
    cursor = conn.cursor()
    
    # Busca a lista de veículos para exibir na tabela
    veiculos = listar_veiculos_db(conn, cursor)
    
    cursor.close()
    conn.close()
    
    # Obtém mensagens de sucesso ou erro da query string (após redirecionamento)
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    erro = request.args.get('erro')
    
    return render_template(
        'cadastro_veiculo.html',
        usuario=session.get('usuario_nome'),
        veiculos=veiculos,
        mensagem_sucesso=mensagem_sucesso,
        erro=erro
    )

@app.route('/cadastrar_veiculo', methods=['POST'])
@login_obrigatorio
def cadastrar_veiculo():
    """
    Processa o formulário de cadastro de um novo veículo.
    """
    conn = conecta_db()
    cursor = conn.cursor()
    
    PLACA_REGEX = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', re.IGNORECASE)
    dados_form = request.form
    placa_input = dados_form.get('placa', '').strip().upper()

    if not PLACA_REGEX.match(placa_input):
        # Em caso de erro, redireciona de volta para a página de veículos com a mensagem de erro
        return redirect(url_for('veiculos_page', erro="Formato de Placa inválido. Use o padrão brasileiro de 7 caracteres (Ex: ABC1234 ou ABC1D23)."))

    try:
        dados_veiculo = {
            'placa': placa_input,
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso'])
        }
    except (ValueError, TypeError):
        return redirect(url_for('veiculos_page', erro="Erro de formato: Verifique se todos os campos foram preenchidos corretamente."))

    sucesso, mensagem = cadastrar_veiculo_db(conn, cursor, dados_veiculo)
    
    cursor.close()
    conn.close()

    if sucesso:
        return redirect(url_for('veiculos_page', mensagem_sucesso=mensagem))
    else:
        return redirect(url_for('veiculos_page', erro=mensagem))

@app.route('/atualizar_veiculo', methods=['POST'])
@login_obrigatorio
def atualizar_veiculo():
    """
    Processa o formulário de atualização de um veículo existente.
    """
    conn = conecta_db()
    cursor = conn.cursor()
    
    dados_form = request.form
    
    try:
        # A placa original está em 'placa_original' e não pode ser alterada.
        dados_veiculo = {
            'placa': dados_form['placa_original'],
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso'])
        }
    except (ValueError, TypeError):
        return redirect(url_for('veiculos_page', erro="Erro de formato: Verifique se todos os campos foram preenchidos corretamente."))

    sucesso, mensagem = atualizar_veiculo_db(conn, cursor, dados_veiculo)
    
    cursor.close()
    conn.close()

    if sucesso:
        return redirect(url_for('veiculos_page', mensagem_sucesso=mensagem))
    else:
        return redirect(url_for('veiculos_page', erro=mensagem))


@app.route("/excluir_veiculo/<placa>", methods=["POST"])
@login_obrigatorio
def excluir_veiculo(placa):
    """
    Processa a exclusão (lógica) de um veículo.
    """
    conn = conecta_db()
    cursor = conn.cursor()

    sucesso, mensagem = excluir_veiculo_db(conn, cursor, placa)
    
    cursor.close()
    conn.close()

    if sucesso:
        return redirect(url_for('veiculos_page', mensagem_sucesso=mensagem))
    else:
        return redirect(url_for('veiculos_page', erro=mensagem))


if __name__ == '__main__':
    app.run(debug=True)