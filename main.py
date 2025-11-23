from flask import Flask, render_template, request, redirect, url_for, session, abort, jsonify
from banco_dados import ConfiguracaoBanco, BancoDados
from servico_autenticacao import ServicoAutenticacao
from form_importador import ServicoImportacao
from form_cadastro_veiculos import ServicoVeiculo
from form_cadastro_usuarios import ServicoUsuario
from form_pedidos_importados import ServicoPedidosImportados
from jinja2 import TemplateNotFound
import re

app = Flask(__name__)
app.secret_key = 'fastrout'  # Troque para uma chave mais segura em producao

# Configuracoes do banco de dados (PostgreSQL)
DB_USER = "postgres"
DB_PASSWORD = "1234"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "FastRoute"

config_banco = ConfiguracaoBanco(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
banco_dados = None
try:
    banco_dados = BancoDados(config_banco)
except Exception:
    # Falha ao conectar: continuar com None (modo local/fallback nos serviços)
    banco_dados = None

servico_autenticacao = ServicoAutenticacao(banco_dados)
servico_importacao = ServicoImportacao(banco_dados)
servico_veiculo = ServicoVeiculo(banco_dados)
servico_usuario = ServicoUsuario(banco_dados)
servico_pedidos = ServicoPedidosImportados(banco_dados)


# Decorator para exigir login
def login_obrigatorio(func):
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def admin_obrigatorio(func):
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        cargo = session.get('usuario_cargo')
        # aceitar '1' ou 1
        if str(cargo) != '1':
            abort(403)
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


# Rotas de autenticacao
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def realizar_login():
    nome = request.form.get('usuario', '').strip()
    senha = request.form.get('senha', '').strip()

    sucesso, usuario, mensagem = servico_autenticacao.autenticar_usuario(nome, senha)
    if sucesso:
        # usuario pode ser dict com id/nome/cargo conforme servico
        session['usuario_id'] = usuario.get('id') if isinstance(usuario, dict) else usuario
        session['usuario_nome'] = usuario.get('nome') if isinstance(usuario, dict) else nome
        session['usuario_cargo'] = usuario.get('cargo') if isinstance(usuario, dict) and usuario.get('cargo') is not None else '0'
        return redirect(url_for('home'))
    return render_template('login.html', erro=mensagem)


@app.route('/logout')
def realizar_logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/home')
@login_obrigatorio
def home():
    return render_template(
        'home.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
    )


# Rotas de importacao
@app.route('/importar', methods=['GET'])
@login_obrigatorio
def pagina_importacao():
    clientes = servico_importacao.buscar_clientes()
    return render_template(
        'importar.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        clientes=clientes,
        sucesso=request.args.get('sucesso'),
        erro=request.args.get('erro'),
    )


@app.route('/processar_importacao', methods=['POST'])
@login_obrigatorio
def processar_importacao():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return redirect(url_for('pagina_importacao', erro="Nenhum arquivo selecionado."))
    sucesso, mensagem = servico_importacao.importar_dados_csv(arquivo)
    if sucesso:
        return redirect(url_for('pagina_importacao', sucesso=mensagem))
    return redirect(url_for('pagina_importacao', erro=mensagem))


# Rotas de veiculos
@app.route('/veiculos', methods=['GET'])
@login_obrigatorio
def pagina_veiculos():
    veiculos = servico_veiculo.listar_veiculos()
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    erro = request.args.get('erro')

    return render_template(
        'cadastro_veiculo.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        veiculos=veiculos,
        mensagem_sucesso=mensagem_sucesso,
        erro=erro,
    )


@app.route('/cadastrar_veiculo', methods=['POST'])
@login_obrigatorio
def cadastrar_veiculo():
    placa_regex = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', re.IGNORECASE)
    dados_form = request.form
    placa_input = dados_form.get('placa', '').strip().upper()

    if not placa_regex.match(placa_input):
        return redirect(url_for('pagina_veiculos', erro="Formato de placa invalido."))

    try:
        dados = {
            'placa': placa_input,
            'marca': dados_form.get('marca', '').strip(),
            'modelo': dados_form.get('modelo', '').strip(),
            'tipo_carga': int(dados_form.get('tipo_carga', 0)),
            'limite_peso': float(dados_form.get('limite_peso', 0.0)),
        }
    except Exception:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados do veículo."))

    sucesso, mensagem = servico_veiculo.cadastrar_veiculo(dados)
    if sucesso:
        return redirect(url_for('pagina_veiculos', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_veiculos', erro=mensagem))


@app.route('/atualizar_veiculo', methods=['POST'])
@login_obrigatorio
def atualizar_veiculo():
    dados_form = request.form
    try:
        dados = {
            'placa': dados_form.get('placa_original', '').strip().upper(),
            'marca': dados_form.get('marca', '').strip(),
            'modelo': dados_form.get('modelo', '').strip(),
            'tipo_carga': int(dados_form.get('tipo_carga', 0)),
            'limite_peso': float(dados_form.get('limite_peso', 0.0)),
        }
    except Exception:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados do veículo."))

    sucesso, mensagem = servico_veiculo.atualizar_veiculo(dados)
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


# Rotas de usuarios
@app.route('/usuarios', methods=['GET'])
@admin_obrigatorio
def pagina_usuarios():
    usuarios = servico_usuario.listar_usuarios()
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    erro = request.args.get('erro')
    return render_template('cadastro_usuario.html', usuario=session.get('usuario_nome'), usuarios=usuarios, mensagem_sucesso=mensagem_sucesso, erro=erro)


@app.route('/cadastrar_usuario', methods=['POST'])
@admin_obrigatorio
def cadastrar_usuario():
    dados_form = request.form
    try:
        dados = {
            'nome': dados_form.get('nome', '').strip(),
            'senha': dados_form.get('senha', ''),
            'cargo': int(dados_form.get('cargo', 0)),
        }
    except Exception:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados do usuário."))

    sucesso, mensagem = servico_usuario.cadastrar_usuario(dados)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


@app.route('/atualizar_usuario', methods=['POST'])
@admin_obrigatorio
def atualizar_usuario():
    dados_form = request.form
    try:
        dados = {
            'id': int(dados_form.get('usuario_id', 0)),
            'nome': dados_form.get('nome', '').strip(),
            'senha': dados_form.get('senha', ''),
            'cargo': int(dados_form.get('cargo', 0)),
        }
    except Exception:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados do usuário."))

    sucesso, mensagem = servico_usuario.atualizar_usuario(dados)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


@app.route('/excluir_usuario/<int:usuario_id>', methods=['POST'])
@admin_obrigatorio
def excluir_usuario(usuario_id):
    sucesso, mensagem = servico_usuario.excluir_usuario(usuario_id)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


#Rotas de Pedidos
@app.route('/pedidos_importados')
@login_obrigatorio
def pedidos_importados():
    pagina = request.args.get('pagina', default=1, type=int)
    filtros = {}
    cliente_id = request.args.get('cliente_id')
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    if cliente_id:
        filtros['cliente_id'] = cliente_id
    if status:
        filtros['status'] = status
    if data_inicio:
        filtros['data_inicio'] = data_inicio
    if data_fim:
        filtros['data_fim'] = data_fim

    pag = servico_pedidos.listar_pedidos(pagina, filtros)
    clientes = servico_pedidos.buscar_clientes()
    try:
        return render_template('pedidos_importados.html',
                               usuario=session.get('usuario_nome'),
                               cargo=session.get('usuario_cargo'),
                               pedidos=pag.get('pedidos'),
                               pagina=pag.get('pagina'),
                               total_paginas=pag.get('total_paginas'),
                               total_registros=pag.get('total_registros'),
                               clientes=clientes)
    except TemplateNotFound:
        # fallback para exibir no home caso o template não exista
        return render_template('home.html',
                               usuario=session.get('usuario_nome'),
                               pedidos=pag.get('pedidos'),
                               clientes=clientes)


@app.route('/relatorios')
@login_obrigatorio
def relatorios():
    # gerar relatório simples por filtros (reutiliza listar_pedidos)
    pagina = request.args.get('pagina', default=1, type=int)
    filtros = {}
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        filtros['cliente_id'] = cliente_id
    pag = servico_pedidos.listar_pedidos(pagina, filtros)
    try:
        return render_template('relatorios.html', usuario=session.get('usuario_nome'), pedidos=pag.get('pedidos'), pagina=pag.get('pagina'), total_paginas=pag.get('total_paginas'))
    except TemplateNotFound:
        return jsonify({"pedidos": pag.get('pedidos'), "pagina": pag.get('pagina'), "total_paginas": pag.get('total_paginas')})


@app.route('/entregas_pendentes')
@login_obrigatorio
def entregas_pendentes():
    pagina = request.args.get('pagina', default=1, type=int)
    filtros = {'status': 'PENDENTE'}
    pag = servico_pedidos.listar_pedidos(pagina, filtros)
    try:
        return render_template('entregas_pendentes.html', usuario=session.get('usuario_nome'), pedidos=pag.get('pedidos'), pagina=pag.get('pagina'), total_paginas=pag.get('total_paginas'))
    except TemplateNotFound:
        return jsonify({"pedidos": pag.get('pedidos'), "pagina": pag.get('pagina'), "total_paginas": pag.get('total_paginas')})

if __name__ == '__main__':
    app.run(debug=True)