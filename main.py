from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import re
from banco_dados import ConfiguracaoBanco, BancoDados
from servico_autenticacao import ServicoAutenticacao
from form_importador import ServicoImportacao
from form_cadastro_veiculos import ServicoVeiculo
from form_cadastro_usuarios import ServicoUsuario

app = Flask(__name__)
app.secret_key = 'fastrout'  # Troque para uma chave mais segura em produção

# Configurações do banco PostgreSQL
DB_USER = "postgres"
DB_PASSWORD = "1234"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "FastRoute"

config_banco = ConfiguracaoBanco(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
banco_dados = BancoDados(config_banco)
servico_autenticacao = ServicoAutenticacao(banco_dados)
servico_importacao = ServicoImportacao(banco_dados)
servico_veiculo = ServicoVeiculo(banco_dados)
servico_usuario = ServicoUsuario(banco_dados)


# Decorator para login obrigatório
def login_obrigatorio(func):
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


# ----------------------------
# LOGIN
# ----------------------------
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def realizar_login():
    nome = request.form['usuario']
    senha = request.form['senha']

    sucesso, usuario, mensagem = servico_autenticacao.autenticar_usuario(nome, senha)
    if sucesso:
        session['usuario_id'] = usuario["id"]
        session['usuario_nome'] = usuario["nome"]
        return redirect(url_for('home'))
    return render_template('login.html', erro=mensagem)


@app.route('/logout')
def realizar_logout():
    session.clear()
    return redirect(url_for('login_page'))


# ---------------------------------------------------
#   HOME / DASHBOARD
# ---------------------------------------------------
@app.route('/home')
@login_obrigatorio
def home():
    total_pedidos = servico_importacao.contar_pedidos()
    pedidos_divergentes = servico_importacao.contar_pedidos_divergentes()
    entregas_ultimo_mes = servico_importacao.contar_entregas_ultimo_mes()

    return render_template(
        'home.html',
        usuario=session.get('usuario_nome'),
        total_pedidos=total_pedidos,
        pedidos_divergentes=pedidos_divergentes,
        entregas_ultimo_mes=entregas_ultimo_mes
    )


# ---------------------------------------------------
#   API – CALENDÁRIO (FullCalendar)
# ---------------------------------------------------
@app.route('/entregas-datas')
@login_obrigatorio
def entregas_datas():
    datas = servico_importacao.listar_datas_entregas()
    eventos = [{"title": "Entrega", "start": d.isoformat()} for d in datas]
    return jsonify(eventos)


@app.route('/entregas-pendentes')
@login_obrigatorio
def entregas_pendentes():
    pontos = servico_importacao.listar_entregas_pendentes()
    return jsonify(pontos)



# ---------------------------------------------------
#   IMPORTAÇÃO DE PEDIDOS
# ---------------------------------------------------
@app.route('/importar', methods=['GET'])
@login_obrigatorio
def pagina_importacao():
    clientes = servico_importacao.buscar_clientes()
    return render_template('importar.html', usuario=session.get('usuario_nome'), clientes=clientes)


@app.route('/processar_importacao', methods=['POST'])
@login_obrigatorio
def processar_importacao():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return render_template('importar.html', erro="Nenhum arquivo selecionado.", usuario=session.get('usuario_nome'))

    sucesso, mensagem = servico_importacao.importar_dados_csv(arquivo)
    if sucesso:
        return render_template('importar.html', sucesso=mensagem, usuario=session.get('usuario_nome'))
    return render_template('importar.html', erro=mensagem, usuario=session.get('usuario_nome'))


# ---------------------------------------------------
#   VEÍCULOS
# ---------------------------------------------------
@app.route('/veiculos')
@login_obrigatorio
def pagina_veiculos():
    veiculos = servico_veiculo.listar_veiculos()
    return render_template(
        'cadastro_veiculo.html',
        usuario=session.get('usuario_nome'),
        veiculos=veiculos,
        mensagem_sucesso=request.args.get('mensagem_sucesso'),
        erro=request.args.get('erro')
    )


@app.route('/cadastrar_veiculo', methods=['POST'])
@login_obrigatorio
def cadastrar_veiculo():
    placa_regex = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', re.IGNORECASE)
    dados_form = request.form
    placa = dados_form.get('placa', '').strip().upper()

    if not placa_regex.match(placa):
        return redirect(url_for('pagina_veiculos', erro="Formato de placa inválido."))

    try:
        dados_veiculo = {
            'placa': placa,
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso']),
        }
    except:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados."))

    sucesso, mensagem = servico_veiculo.cadastrar_veiculo(dados_veiculo)
    if sucesso:
        return redirect(url_for('pagina_veiculos', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_veiculos', erro=mensagem))


@app.route('/atualizar_veiculo', methods=['POST'])
@login_obrigatorio
def atualizar_veiculo():
    dados_form = request.form
    try:
        dados_veiculo = {
            'placa': dados_form['placa_original'],
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso']),
        }
    except:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados."))

    sucesso, mensagem = servico_veiculo.atualizar_veiculo(dados_veiculo)
    if sucesso:
        return redirect(url_for('pagina_veiculos', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_veiculos', erro=mensagem))


@app.route('/excluir_veiculo/<placa>', methods=['POST'])
@login_obrigatorio
def excluir_veiculo(placa):
    sucesso, mensagem = servico_veiculo.excluir_veiculo(placa)
    if sucesso:
        return redirect(url_for('pagina_veiculos', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_veiculos', erro=mensagem))


# ---------------------------------------------------
#   USUÁRIOS
# ---------------------------------------------------
@app.route('/usuarios')
@login_obrigatorio
def pagina_usuarios():
    usuarios = servico_usuario.listar_usuarios()
    return render_template(
        'cadastro_usuario.html',
        usuario=session.get('usuario_nome'),
        usuarios=usuarios,
        mensagem_sucesso=request.args.get('mensagem_sucesso'),
        erro=request.args.get('erro'),
    )


@app.route('/cadastrar_usuario', methods=['POST'])
@login_obrigatorio
def cadastrar_usuario():
    dados_form = request.form
    try:
        dados_usuario = {
            'nome': dados_form['nome'].strip(),
            'senha': dados_form['senha'],
            'cargo': int(dados_form['cargo']),
        }
    except:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados."))

    sucesso, mensagem = servico_usuario.cadastrar_usuario(dados_usuario)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


@app.route('/atualizar_usuario', methods=['POST'])
@login_obrigatorio
def atualizar_usuario():
    dados_form = request.form
    try:
        dados_usuario = {
            'id': int(dados_form['usuario_id']),
            'nome': dados_form['nome'].strip(),
            'senha': dados_form['senha'],
            'cargo': int(dados_form['cargo']),
        }
    except:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados."))

    sucesso, mensagem = servico_usuario.atualizar_usuario(dados_usuario)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


@app.route('/excluir_usuario/<int:usuario_id>', methods=['POST'])
@login_obrigatorio
def excluir_usuario(usuario_id):
    sucesso, mensagem = servico_usuario.excluir_usuario(usuario_id)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))

# ROTA: lista de pedidos importados
@app.route('/pedidos')
@login_obrigatorio
def pedidos_importados():
    filtro = request.args.get('filtro', 'todos')
    data_prevista = request.args.get('data_prevista', None)
    # paginação simples (opcional)
    page = int(request.args.get('page', 1))
    per_page = 100
    offset = (page - 1) * per_page

    pedidos = servico_importacao.buscar_pedidos(filtro=filtro, data_prevista=data_prevista, limit=per_page, offset=offset)

    return render_template(
        'pedidos_importados.html',
        usuario=session.get('usuario_nome'),
        pedidos=pedidos,
        filtro=filtro,
        data_prevista=data_prevista
    )

# ROTA: detalhes do pedido
@app.route('/pedidos/<int:n_nota>')
@login_obrigatorio
def detalhar_pedido(n_nota):
    pedido = servico_importacao.buscar_pedido_por_id(n_nota)
    if not pedido:
        return redirect(url_for('pedidos_importados'))
    return render_template('detalhe_pedido.html', usuario=session.get('usuario_nome'), pedido=pedido)

# ---------------------------------------------------
#   RELATÓRIOS
# ---------------------------------------------------
@app.route('/relatorios')
@login_obrigatorio
def relatorios():
    return render_template(
        'relatorios.html',
        usuario=session.get('usuario_nome')
    )


# ---------------------------------------------------
# EXECUÇÃO
# ---------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
