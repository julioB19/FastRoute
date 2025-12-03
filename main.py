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

# Config BG
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
    banco_dados = None  # fallback

servico_autenticacao = ServicoAutenticacao(banco_dados)
servico_importacao = ServicoImportacao(banco_dados)
servico_veiculo = ServicoVeiculo(banco_dados)
servico_usuario = ServicoUsuario(banco_dados)
servico_pedidos = ServicoPedidosImportados(banco_dados)


# Decorators
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
        if str(cargo) != '1':
            abort(403)
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# -----------------------------
# LOGIN
# -----------------------------
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def realizar_login():
    nome = request.form.get('usuario', '').strip()
    senha = request.form.get('senha', '').strip()

    sucesso, usuario, mensagem = servico_autenticacao.autenticar_usuario(nome, senha)
    if sucesso:
        session['usuario_id'] = usuario.get('id')
        session['usuario_nome'] = usuario.get('nome')
        session['usuario_cargo'] = usuario.get('cargo')
        return redirect(url_for('home'))
    return render_template('login.html', erro=mensagem)


@app.route('/logout')
def realizar_logout():
    session.clear()
    return redirect(url_for('login_page'))


# -----------------------------
# HOME (DASHBOARD)
# -----------------------------
@app.route('/home')
@login_obrigatorio
def home():
    total_completos = servico_pedidos.contar_com_filtros({
        "coords_not_null": True,
        "excluir_entregues": True
    })
    total_incompletos = servico_pedidos.contar_incompletos()

    entregas_ultimo_mes = 0
    try:
        q = """
            SELECT COUNT(DISTINCT DATE(e.data_entrega)) AS total
            FROM ENTREGA e
            WHERE e.data_entrega >= (CURRENT_DATE - INTERVAL '30 days');
        """
        rows = servico_pedidos._execute_select(q)
        entregas_ultimo_mes = rows[0]["total"] if rows else 0
    except Exception:
        entregas_ultimo_mes = 0

    return render_template(
        'home.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        total_pedidos=total_completos,
        pedidos_incompletos=total_incompletos,
        entregas_ultimo_mes=entregas_ultimo_mes
    )


# -----------------------------
# IMPORTAÇÃO
# -----------------------------
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


# -----------------------------
# VEÍCULOS
# -----------------------------
@app.route('/veiculos', methods=['GET'])
@login_obrigatorio
def pagina_veiculos():
    veiculos = servico_veiculo.listar_veiculos()
    return render_template(
        'cadastro_veiculo.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        veiculos=veiculos,
        mensagem_sucesso=request.args.get('mensagem_sucesso'),
        erro=request.args.get('erro'),
    )


@app.route('/cadastrar_veiculo', methods=['POST'])
@login_obrigatorio
def cadastrar_veiculo():
    dados_form = request.form
    placa = dados_form.get('placa', '').strip().upper()

    placa_regex = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', re.IGNORECASE)
    if not placa_regex.match(placa):
        return redirect(url_for('pagina_veiculos', erro="Formato de placa inválido."))

    try:
        dados = {
            'placa': placa,
            'marca': dados_form.get('marca', '').strip(),
            'modelo': dados_form.get('modelo', '').strip(),
            'tipo_carga': int(dados_form.get('tipo_carga', 0)),
            'limite_peso': float(dados_form.get('limite_peso', 0)),
        }
    except:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados."))

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
            'limite_peso': float(dados_form.get('limite_peso', 0)),
        }
    except:
        return redirect(url_for('pagina_veiculos', erro="Erro nos dados."))

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


# -----------------------------
# USUÁRIOS
# -----------------------------
@app.route('/usuarios', methods=['GET'])
@admin_obrigatorio
def pagina_usuarios():
    usuarios = servico_usuario.listar_usuarios()
    return render_template(
        'cadastro_usuario.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        usuarios=usuarios,
        mensagem_sucesso=request.args.get('mensagem_sucesso'),
        erro=request.args.get('erro'),
    )


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
    except:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados."))

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
            'id': int(dados_form.get('usuario_id')),
            'nome': dados_form.get('nome', '').strip(),
            'senha': dados_form.get('senha', ''),
            'cargo': int(dados_form.get('cargo', 0)),
        }
    except:
        return redirect(url_for('pagina_usuarios', erro="Erro nos dados."))

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


# -----------------------------
# PEDIDOS IMPORTADOS
# -----------------------------
@app.route('/pedidos_importados')
@login_obrigatorio
def pedidos_importados():

    # ------------------------------------------------
    # LENDO ARGUMENTOS DA URL
    # ------------------------------------------------
    pagina = request.args.get('pagina', default=1, type=int)
    filtro = request.args.get('filtro', default='todos')
    data_nota = request.args.get('data_nota', default='').strip()
    data_entrega = request.args.get('data_entrega', default='').strip()

    itens_por_pagina = request.args.get('itens', default=20, type=int)
    if itens_por_pagina not in (20, 50, 100):
        itens_por_pagina = 20

    # CAMPOS NOVOS
    cliente_nome = request.args.get('cliente_nome', default='').strip()
    clientes_multi = request.args.getlist('clientes_multi[]')  # MULTI
    endereco = request.args.get('endereco', default='').strip()
    cidade = request.args.get('cidade', default='').strip()

    numero_nota = request.args.get('numero_nota', default='').strip()
    notas_multi = request.args.getlist('notas_multi[]')  # MULTI

    filtros = {}

    # ------------------------------------------------
    # FILTRO PRINCIPAL
    # ------------------------------------------------
    if filtro == "completos":
        filtros["coords_not_null"] = True
        filtros["excluir_entregues"] = True
    elif filtro == "incompletos":
        filtros["coords_null"] = True
    elif filtro == "entregues":
        filtros["entregues"] = True

    # ------------------------------------------------
    # DATA ÚNICA → PERÍODO
    # ------------------------------------------------
    if data_nota:
        filtros["data_inicio"] = data_nota
        filtros["data_fim"] = data_nota

    if data_entrega:
        filtros["entrega_inicio"] = data_entrega
        filtros["entrega_fim"] = data_entrega

    # ------------------------------------------------
    # MULTI-SELEÇÃO DE CLIENTES (OR)
    # ------------------------------------------------
    clientes_lista = []

    # cliente_nome separado por vírgula
    if cliente_nome:
        partes = [x.strip() for x in cliente_nome.split(",") if x.strip()]
        clientes_lista.extend(partes)

    # cliente_multi[] do HTML
    if clientes_multi:
        clientes_lista.extend([x.strip() for x in clientes_multi if x.strip()])

    # remove duplicados
    clientes_lista = list(set(clientes_lista))

    if clientes_lista:
        filtros["cliente_nome_lista"] = clientes_lista

    # ------------------------------------------------
    # MULTI-SELEÇÃO DE NOTAS (OR)
    # ------------------------------------------------
    notas_lista = []

    if numero_nota:
        partes = [x.strip() for x in numero_nota.split(",") if x.strip()]
        notas_lista.extend(partes)

    if notas_multi:
        notas_lista.extend([x.strip() for x in notas_multi if x.strip()])

    notas_lista = list(set(notas_lista))

    if notas_lista:
        filtros["notas_lista"] = notas_lista

    # ------------------------------------------------
    # CAMPOS SIMPLES
    # ------------------------------------------------
    if endereco:
        filtros["endereco"] = endereco
    if cidade:
        filtros["cidade"] = cidade

    filtros["itens_por_pagina"] = itens_por_pagina

    # ------------------------------------------------
    # EXECUTAR LISTAGEM
    # ------------------------------------------------
    pag = servico_pedidos.listar_pedidos(pagina, filtros)
    clientes = servico_pedidos.buscar_clientes()

    try:
        return render_template(
            'pedidos_importados.html',
            usuario=session.get('usuario_nome'),
            cargo=session.get('usuario_cargo'),
            pedidos=pag["pedidos"],
            pagina=pag["pagina"],
            total_paginas=pag["total_paginas"],
            total_registros=pag["total_registros"],
            clientes=clientes,
            filtro=filtro,
            data_nota=data_nota,
            data_entrega=data_entrega,
            itens_por_pagina=itens_por_pagina,
            cliente_nome=cliente_nome,
            endereco=endereco,
            cidade=cidade,
            numero_nota=numero_nota
        )
    except TemplateNotFound:
        return render_template(
            'home.html',
            usuario=session.get('usuario_nome'),
            pedidos=pag["pedidos"],
            clientes=clientes,
        )

@app.route("/detalhar_pedido/<int:n_nota>")
@login_obrigatorio
def detalhar_pedido(n_nota):
    pedido = servico_pedidos.buscar_pedido_por_id(n_nota)
    itens = servico_pedidos.buscar_itens_pedido(n_nota)

    if not pedido:
        return {"erro": "Pedido não encontrado"}, 404

    return {"pedido": pedido, "itens": itens}


# -----------------------------
# RELATÓRIOS
# -----------------------------
@app.route('/relatorios')
@login_obrigatorio
def relatorios():
    pagina = request.args.get('pagina', default=1, type=int)
    filtros = {}
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        filtros['cliente_id'] = cliente_id

    pag = servico_pedidos.listar_pedidos(pagina, filtros)

    try:
        return render_template(
            'relatorios.html',
            usuario=session.get('usuario_nome'),
            pedidos=pag["pedidos"],
            pagina=pag["pagina"],
            total_paginas=pag["total_paginas"],
        )
    except TemplateNotFound:
        return jsonify(pag)


@app.route('/entregas_pendentes')
@login_obrigatorio
def entregas_pendentes():
    pagina = request.args.get('pagina', default=1, type=int)
    filtros = {'status': 'PENDENTE'}

    pag = servico_pedidos.listar_pedidos(pagina, filtros)

    try:
        return render_template(
            'entregas_pendentes.html',
            usuario=session.get('usuario_nome'),
            pedidos=pag["pedidos"],
            pagina=pag["pagina"],
            total_paginas=pag["total_paginas"],
        )
    except TemplateNotFound:
        return jsonify(pag)

@app.template_filter("data_br")
def data_br(value):
    if not value:
        return "-"
    try:
        return value.strftime("%d/%m/%Y")
    except:
        return value


@app.route("/entregas-mapa")
@login_obrigatorio
def entregas_mapa():
    query = """
        SELECT
            p.n_nota,
            ec.coordenadas,
            EXISTS(SELECT 1 FROM ENTREGA e WHERE e.pedido_n_nota = p.n_nota) AS entregue
        FROM PEDIDO p
        LEFT JOIN ENDERECO_CLIENTE ec ON ec.id_endereco = p.id_endereco
        WHERE ec.coordenadas IS NOT NULL
        AND ec.coordenadas <> '';
    """

    rows = servico_pedidos._execute_select(query)

    agregados = {}
    for r in rows:
        coords = r.get("coordenadas")
        if not coords:
            continue
        try:
            lat, lng = map(float, coords.split(","))
        except Exception:
            continue

        key = f"{lat:.6f},{lng:.6f}"
        entregado = bool(r.get("entregue"))

        current = agregados.get(key)
        if not current:
            agregados[key] = {
                "lat": lat,
                "lng": lng,
                "n_notas": [r.get("n_nota")],
                "status": "ENTREGUE" if entregado else "COMPLETO"
            }
        else:
            current["n_notas"].append(r.get("n_nota"))
            if entregado:
                current["status"] = "ENTREGUE"

    marcadores = []
    for v in agregados.values():
        marcadores.append({
            "n_notas": v["n_notas"],
            "lat": v["lat"],
            "lng": v["lng"],
            "status": v["status"]
        })

    return jsonify(marcadores)


@app.route("/entregas-datas")
@login_obrigatorio
def entregas_datas():
    query = """
        SELECT DISTINCT DATE(e.data_entrega) AS data_entrega
        FROM ENTREGA e
        WHERE e.data_entrega IS NOT NULL
        ORDER BY data_entrega;
    """

    rows = servico_pedidos._execute_select(query)

    datas = []
    for r in rows:
        dt = r.get("data_entrega")
        try:
            datas.append({"start": dt.strftime("%Y-%m-%d")})
        except Exception:
            datas.append({"start": str(dt)})

    return jsonify(datas)


# -----------------------------
# MAIN
# -----------------------------
if __name__ == '__main__':
    app.run(debug=True)
