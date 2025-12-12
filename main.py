from flask import Flask, render_template, request, redirect, url_for, session, abort, jsonify
from banco_dados import ConfiguracaoBanco, BancoDados
from servico_autenticacao import ServicoAutenticacao
from form_importador import ServicoImportacao
from form_cadastro_veiculos import ServicoVeiculo
from form_cadastro_usuarios import ServicoUsuario
from form_pedidos_importados import ServicoPedidosImportados
from jinja2 import TemplateNotFound
import json
import re
import datetime

app = Flask(__name__)
app.secret_key = 'fastrout'  # Troque para uma chave mais segura em producao

DEPOSITO_COORD = (-27.367681114267935, -53.40115242306388)

# Config BG
DB_USER = "postgres"
#DB_PASSWORD = "fastrout"
DB_PASSWORD = "1234"
DB_HOST = "localhost"
#DB_PORT = "3380"
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
    # Totais para o dashboard
    total_completos = servico_pedidos.contar_com_filtros({
        "coords_not_null": True,
        "excluir_entregues": True
    })
    total_incompletos = servico_pedidos.contar_incompletos()

    # contar entregas no último mês -> agora conta Nº DE PEDIDOS ENTREGUES (últimos 30 dias)
    entregas_ultimo_mes = 0
    try:
        q = """
            SELECT COUNT(*) AS total
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
        total_pedidos=total_completos,         # BLOCO 1
        pedidos_incompletos=total_incompletos, # BLOCO 2
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
    pagina = request.args.get('pagina', default=1, type=int)
    filtro = request.args.get('filtro', default='todos')
    data_nota = request.args.get('data_nota', default='').strip()

    itens_por_pagina = request.args.get('itens', default=20, type=int)
    if itens_por_pagina not in (20, 50, 100):
        itens_por_pagina = 20

    filtros = {}
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        filtros["cliente_id"] = cliente_id

    if filtro == "completos":
        filtros["coords_not_null"] = True
        filtros["excluir_entregues"] = True
    elif filtro == "incompletos":
        filtros["coords_null"] = True
    elif filtro == "entregues":
        filtros["entregues"] = True

    if data_nota:
        filtros["data_inicio"] = data_nota
        filtros["data_fim"] = data_nota

    filtros["itens_por_pagina"] = itens_por_pagina

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
            itens_por_pagina=itens_por_pagina,
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

@app.route('/otimizacao_rotas')
@login_obrigatorio
def pagina_otimizacao_rotas():
    cliente_id = request.args.get('cliente_id', type=int)
    limite = request.args.get('limite', default=50, type=int)

    pedidos = servico_pedidos.listar_completos_para_otimizacao(
        limite=limite,
        cliente_id=cliente_id,
    )
    clientes = servico_pedidos.buscar_clientes()

    return render_template(
        'otimizacao_rotas.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        pedidos=pedidos,
        clientes=clientes,
        limite=limite,
        cliente_id=cliente_id,
        deposito_coord=DEPOSITO_COORD,
    )

@app.route('/rotas_otimizadas')
@login_obrigatorio
def rotas_otimizadas():
    data_filtro = (request.args.get("data") or "").strip()
    origem_resultado = "banco"

    def carregar_otimizacao(data_ref=None):
        try:
            return servico_pedidos.recuperar_ultima_otimizacao_salva(data_ref)
        except Exception as e:
            print("Nao foi possivel recuperar otimizacoes do banco:", e)
            return None

    dados = carregar_otimizacao(data_filtro) if data_filtro else carregar_otimizacao()
    if not dados:
        dados = {}

    rotas = dados.get("rotas_por_veiculo", {})
    distancia = dados.get("distancia_total_km", 0.0)
    pedidos = dados.get("pedidos_considerados", [])
    pedidos_sem = dados.get("pedidos_sem_coordenadas", [])
    pedidos_sem_compativeis = dados.get("pedidos_sem_compativeis", [])
    clientes_por_pedido = dados.get("clientes_por_pedido", {})
    coordenadas = dados.get("coordenadas_usadas", []) or []
    mapa_indices = dados.get("mapa_indices", {}) or {}

    clientes_filtrados = [c.strip().lower() for c in request.args.getlist("cliente") if c.strip()]
    veiculos_filtrados = [v.strip().lower() for v in request.args.getlist("veiculo") if v.strip()]

    if not clientes_filtrados and request.args.get("cliente"):
        clientes_filtrados = [(request.args.get("cliente") or "").strip().lower()]
    if not veiculos_filtrados and request.args.get("veiculo"):
        veiculos_filtrados = [(request.args.get("veiculo") or "").strip().lower()]

    rotas_filtradas = {}
    rotas_info_map = {}
    for veic, seq in rotas.items():
        veic_ok = True
        cliente_ok = True
        veic_base, veic_extra = (str(veic).split("-", 1) + [""])[:2]

        if veiculos_filtrados:
            veic_ok = any(fv in veic_base.lower() for fv in veiculos_filtrados)

        if clientes_filtrados:
            cliente_ok = any(
                any(fc in (clientes_por_pedido.get(str(n).split("#")[0], "") or "").lower() for fc in clientes_filtrados)
                for n in (seq or [])
            )

        if veic_ok and cliente_ok:
            rotas_filtradas[veic] = seq
            rotas_info_map[veic] = {
                "veiculo": veic_base,
                "rota_id": veic_extra,
                "label": veic_base if not veic_extra else f"{veic_base} (rota {veic_extra})",
            }

    clientes_disponiveis = sorted({v for v in clientes_por_pedido.values() if v})
    veiculos_disponiveis = sorted({(str(v).split("-", 1)[0]) for v in rotas.keys()})
    rotas_clientes = {}

    rotas_para_mapa = []
    for idx, (veic, seq) in enumerate(rotas_filtradas.items()):
        rota_coords = []
        pontos = []
        if coordenadas:
            rota_coords.append(coordenadas[0])
            pontos.append({"lat": coordenadas[0][0], "lng": coordenadas[0][1], "label": "0"})

        for i_ent, pedido in enumerate(seq or []):
            coord_idx = mapa_indices.get(str(pedido))
            if coord_idx is None:
                continue
            try:
                lat, lng = coordenadas[int(coord_idx)]
            except Exception:
                continue
            rota_coords.append([lat, lng])
            pontos.append({"lat": lat, "lng": lng, "label": str(i_ent + 1)})

        if coordenadas:
            rota_coords.append(coordenadas[0])

        rotas_para_mapa.append(
            {
                "veiculo": veic,
                "map_id": f"mapa_rota_{idx}",
                "rota": rota_coords,
                "pontos": pontos,
                "notas": seq or [],
            }
        )
    rotas_para_mapa_map = {r["veiculo"]: r for r in rotas_para_mapa}

    # Dados consolidados para o relatorio gerencial/impresso
    total_paradas = 0
    clientes_unicos = set()
    rotas_resumo = []
    for veic, seq in rotas_filtradas.items():
        notas_seq = seq or []
        total_paradas += len(notas_seq)

        clientes_seq = []
        for nota in notas_seq:
            nota_base = str(nota).split("#")[0]
            cliente_nome = clientes_por_pedido.get(nota_base, "")
            if cliente_nome:
                clientes_seq.append(cliente_nome)
                clientes_unicos.add(cliente_nome)
            else:
                clientes_seq.append("")
        rotas_clientes[veic] = clientes_seq

        rotas_resumo.append(
            {
                "veiculo": veic,
                "total_paradas": len(notas_seq),
                "notas": notas_seq,
                "clientes": clientes_seq,
                "clientes_legiveis": [c for c in clientes_seq if c],
                "primeira_entrega": notas_seq[0] if notas_seq else None,
                "ultima_entrega": notas_seq[-1] if notas_seq else None,
            }
        )

    relatorio_rotas = {
        "data_emissao": datetime.datetime.now(),
        "total_veiculos": len(rotas_filtradas),
        "total_paradas": total_paradas,
        "total_pedidos_considerados": len(pedidos or []),
        "total_clientes_unicos": len(clientes_unicos),
        "distancia_total": distancia,
        "pedidos_sem_coordenadas": pedidos_sem,
        "pedidos_sem_compativeis": pedidos_sem_compativeis,
    }

    data_referencia_raw = dados.get("data_referencia")
    if isinstance(data_referencia_raw, (datetime.date, datetime.datetime)):
        data_referencia = data_referencia_raw.strftime("%d/%m/%Y")
    elif data_referencia_raw:
        data_referencia = str(data_referencia_raw)
    else:
        data_referencia = None

    mensagem_alerta = None
    if not rotas:
        if data_filtro:
            mensagem_alerta = f"Nenhuma rota encontrada para a data {data_filtro}."
        else:
            mensagem_alerta = "Nenhuma rota encontrada."

    return render_template(
        'rotas_otimizadas.html',
        usuario=session.get('usuario_nome'),
        cargo=session.get('usuario_cargo'),
        rotas=rotas_filtradas,
        distancia=distancia,
        pedidos_considerados=pedidos,
        pedidos_sem_coordenadas=pedidos_sem,
        clientes_filtrados=clientes_filtrados,
        veiculos_filtrados=veiculos_filtrados,
        clientes_disponiveis=clientes_disponiveis,
        veiculos_disponiveis=veiculos_disponiveis,
        rotas_para_mapa=rotas_para_mapa,
        rotas_para_mapa_map=rotas_para_mapa_map,
        relatorio_rotas=relatorio_rotas,
        rotas_resumo=rotas_resumo,
        rotas_clientes=rotas_clientes,
        rotas_info_map=rotas_info_map,
        origem_resultado=origem_resultado,
        data_referencia=data_referencia,
        data_filtro=data_filtro,
        mensagem_alerta=mensagem_alerta,
    )

@app.route("/otimizar_rotas", methods=["POST"])
@login_obrigatorio
def otimizar_rotas():
    payload = request.get_json(silent=True) or {}
    pedido_ids = payload.get("pedido_ids") or []
    deposito_payload = payload.get("deposito") or {}
    parametros_algoritmo = payload.get("parametros") or {}

    if not isinstance(pedido_ids, list):
        return jsonify({"erro": "pedido_ids deve ser uma lista de notas/pedidos."}), 400

    try:
        pedido_ids = [int(pid) for pid in pedido_ids]
    except Exception:
        return jsonify({"erro": "pedido_ids contem valores invalidos."}), 400

    deposito_tuple = None
    if isinstance(deposito_payload, dict):
        deposito_tuple = (deposito_payload.get("lat"), deposito_payload.get("lng"))
    elif isinstance(deposito_payload, (list, tuple)) and len(deposito_payload) >= 2:
        deposito_tuple = (deposito_payload[0], deposito_payload[1])

    if not deposito_tuple or deposito_tuple[0] is None or deposito_tuple[1] is None:
        deposito_tuple = DEPOSITO_COORD

    try:
        resultado = servico_pedidos.otimizar_rotas(
            pedido_ids, deposito_tuple, parametros_algoritmo
        )
        # registra entregas/rotas como concluidas
        try:
            ok_reg, erro_reg = servico_pedidos.registrar_entregas_otimizadas(
                resultado.get("rotas_por_veiculo", {}),
                session.get("usuario_id"),
            )
            if not ok_reg:
                print("Falha ao registrar entregas otimizadas:", erro_reg)
        except Exception as e:
            print("Erro inesperado ao registrar entregas otimizadas:", e)

        # guarda resultado na sessao para consulta posterior
        try:
            clientes_por_pedido = {}
            for pid in pedido_ids:
                try:
                    pedido_info = servico_pedidos.buscar_pedido_por_id(pid)
                    if pedido_info:
                        clientes_por_pedido[str(pid)] = pedido_info.get("nome_cliente") or ""
                except Exception:
                    continue

            serializado = {
                "rotas_por_veiculo": resultado.get("rotas_por_veiculo", {}),
                "distancia_total_km": float(resultado.get("distancia_total_km", 0.0)),
                "custo_fitness": float(resultado.get("custo_fitness", 0.0)),
                "coordenadas_usadas": [
                    [float(c[0]), float(c[1])] for c in resultado.get("coordenadas_usadas", [])
                ],
                "pedidos_considerados": resultado.get("pedidos_considerados", []),
                "pedidos_sem_coordenadas": resultado.get("pedidos_sem_coordenadas", []),
                "pedidos_sem_compativeis": resultado.get("pedidos_sem_compativeis", []),
                "mapa_indices": resultado.get("mapa_indices", {}),
                "clientes_por_pedido": clientes_por_pedido,
                "data_referencia": datetime.date.today().isoformat(),
            }
            session["ultima_otimizacao"] = serializado
        except Exception as e:
            print("Nao foi possivel armazenar resultado de otimizacao na sessao:", e)
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        print("Erro ao otimizar rotas:", e)
        return jsonify({"erro": "Falha interna ao otimizar rotas."}), 500

# -----------------------------
# RELATORIOS
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
        return value  # caso já venha formatada


@app.route("/entregas-mapa")
@login_obrigatorio
def entregas_mapa():
    """
    Retorna marcadores agregados por coordenadas.
    Se existir pelo menos uma entrega (entregue=True) para uma coordenada,
    o status daquela coordenada será 'ENTREGUE'. Caso contrário 'COMPLETO'
    (OBS: o JS filtra para mostrar apenas não-entregues).
    """
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

    # Agregamos por coordenadas para evitar múltiplos marcadores sobrepostos
    agregados = {}  # chave = coords, valor = dict { lat, lng, n_notas: [..], status }
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
                # se qualquer um for entregue, marca ENTREGUE
                "status": "ENTREGUE" if entregado else "COMPLETO"
            }
        else:
            # append nota
            current["n_notas"].append(r.get("n_nota"))
            # se algum for entregue, força ENTREGUE
            if entregado:
                current["status"] = "ENTREGUE"

    marcadores = []
    for v in agregados.values():
        marcadores.append({
            "n_notas": v["n_notas"],            # agora pode ser lista
            "lat": v["lat"],
            "lng": v["lng"],
            "status": v["status"]
        })

    return jsonify(marcadores)


@app.route("/entregas-datas")
@login_obrigatorio
def entregas_datas():
    """
    Retorna lista de dias (YYYY-MM-DD) e contagem de pedidos entregues
    para o mês/ano solicitado: /entregas-datas?ano=2025&mes=12
    Se ano/mes não informados, retorna todas as datas.
    """
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)

    params = []
    extra_where = ""
    if ano and mes:
        extra_where = "AND EXTRACT(YEAR FROM e.data_entrega) = %s AND EXTRACT(MONTH FROM e.data_entrega) = %s"
        params.extend([ano, mes])

    query = f"""
        SELECT DATE(e.data_entrega) AS dia, COUNT(*) AS total
        FROM ENTREGA e
        WHERE e.data_entrega IS NOT NULL
        {extra_where}
        GROUP BY DATE(e.data_entrega)
        ORDER BY DATE(e.data_entrega);
    """

    rows = servico_pedidos._execute_select(query, tuple(params))

    result = []
    for r in rows:
        dt = r.get("dia")
        cnt = int(r.get("total") or 0)
        try:
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = str(dt)
        result.append({"date": date_str, "count": cnt})

    return jsonify(result)


# -----------------------------
# MAIN
# -----------------------------
if __name__ == '__main__':
    app.run(debug=True)
