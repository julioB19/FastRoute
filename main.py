from flask import Flask, render_template, request, redirect, url_for, session, abort
import re
from banco_dados import ConfiguracaoBanco, BancoDados
from servico_autenticacao import ServicoAutenticacao
from form_importador import ServicoImportacao
from form_cadastro_veiculos import ServicoVeiculo
from form_cadastro_usuarios import ServicoUsuario

app = Flask(__name__)
app.secret_key = 'fastrout'  # Troque para uma chave mais segura em producao

# Configuracoes do banco de dados (PostgreSQL)
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
        if session.get('usuario_cargo') != '1':
            return abort(403)
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


# Rotas de autenticacao
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
        session['usuario_cargo'] = str(usuario["cargo"])
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
    pagina = request.args.get('pagina', default=1, type=int)
    paginacao_pedidos = servico_importacao.listar_pedidos(pagina)
    return render_template(
        'importar.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        clientes=clientes,
        pedidos=paginacao_pedidos["pedidos"],
        pagina_atual=paginacao_pedidos["pagina"],
        total_paginas=paginacao_pedidos["total_paginas"],
        total_registros=paginacao_pedidos["total_registros"],
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
        return redirect(
            url_for(
                'pagina_veiculos',
                erro="Formato de placa invalido. Use o padrao brasileiro de 7 caracteres (Ex: ABC1234 ou ABC1D23).",
            )
        )

    try:
        dados_veiculo = {
            'placa': placa_input,
            'marca': dados_form['marca'],
            'modelo': dados_form['modelo'],
            'tipo_carga': int(dados_form['tipo_carga']),
            'limite_peso': float(dados_form['limite_peso']),
        }
    except (ValueError, TypeError):
        return redirect(url_for('pagina_veiculos', erro="Erro de formato: verifique os campos."))

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
    except (ValueError, TypeError):
        return redirect(url_for('pagina_veiculos', erro="Erro de formato: verifique os campos."))

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


# Rotas de usuarios
@app.route('/usuarios', methods=['GET'])
@admin_obrigatorio
def pagina_usuarios():
    usuarios = servico_usuario.listar_usuarios()
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    erro = request.args.get('erro')

    return render_template(
        'cadastro_usuario.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        usuarios=usuarios,
        mensagem_sucesso=mensagem_sucesso,
        erro=erro,
    )


@app.route('/cadastrar_usuario', methods=['POST'])
@admin_obrigatorio
def cadastrar_usuario():
    dados_form = request.form
    try:
        dados_usuario = {
            'nome': dados_form['nome'].strip(),
            'senha': dados_form['senha'],
            'cargo': dados_form['cargo'],
        }
    except (ValueError, TypeError, KeyError):
        return redirect(url_for('pagina_usuarios', erro="Erro de formato: verifique os campos."))

    sucesso, mensagem = servico_usuario.cadastrar_usuario(dados_usuario)
    if sucesso:
        return redirect(url_for('pagina_usuarios', mensagem_sucesso=mensagem))
    return redirect(url_for('pagina_usuarios', erro=mensagem))


@app.route('/atualizar_usuario', methods=['POST'])
@admin_obrigatorio
def atualizar_usuario():
    dados_form = request.form
    try:
        dados_usuario = {
            'id': int(dados_form['usuario_id']),
            'nome': dados_form['nome'].strip(),
            'senha': dados_form['senha'],
            'cargo': dados_form['cargo'],
        }
    except (ValueError, TypeError, KeyError):
        return redirect(url_for('pagina_usuarios', erro="Erro de formato: verifique os campos."))

    sucesso, mensagem = servico_usuario.atualizar_usuario(dados_usuario)
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

# -------------------------------------------------------------------------
# ROTAS QUE ESTÃO SENDO CHAMADAS NO DASHBOARD
# -------------------------------------------------------------------------

@app.route('/pedidos_importados')
@login_obrigatorio
def pedidos_importados():
    """Página onde lista pedidos importados (placeholder)."""
    pedidos = servico_importacao.listar_pedidos(1)["pedidos"]
    return render_template(
        'pedidos_importados.html',
        pedidos=pedidos,
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo')
    )


@app.route('/relatorios')
@login_obrigatorio
def relatorios():
    """Página de relatórios (placeholder)."""
    return render_template(
        'relatorios.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo')
    )


@app.route('/entregas_pendentes')
@login_obrigatorio
def entregas_pendentes():
    """Página de entregas pendentes (placeholder)."""
    pedidos_pendentes = servico_importacao.listar_pedidos_pendentes() if hasattr(servico_importacao, "listar_pedidos_pendentes") else []
    
    return render_template(
        'entregas_pendentes.html',
        pedidos=pedidos_pendentes,
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo')
    )

if __name__ == '__main__':
    app.run(debug=True)