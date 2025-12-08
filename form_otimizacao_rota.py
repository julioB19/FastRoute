import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple


# -----------------------------
# Distancias via Haversine
# -----------------------------
def haversine(p1: Tuple[float, float], p2: Tuple[float, float], raio_km: float = 6371.0) -> float:
    """Retorna a distancia em km entre dois pontos (lat, lon) usando Haversine."""
    lat1, lon1 = p1
    lat2, lon2 = p2

    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return raio_km * c


def gerar_matriz_distancias(coordenadas: List[Tuple[float, float]]) -> List[List[float]]:
    """Gera matriz NxN de distancias a partir de uma lista de coordenadas (lat, lon)."""
    n = len(coordenadas)
    matriz = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine(coordenadas[i], coordenadas[j])
            matriz[i][j] = dist
            matriz[j][i] = dist  # garante simetria
    return matriz


# -----------------------------
# Modelo para algoritmo genetico de rota
# -----------------------------
@dataclass(frozen=True)
class Veiculo:
    id: str  # placa ou identificador
    limite_peso: float
    tipo_carga: int  # 1 = normal, 2 = agrotoxico


@dataclass(frozen=True)
class Entrega:
    id: str  # codigo do pedido
    peso: float
    tipo_carga: int  # 1 = normal, 2 = agrotoxico
    indice_matriz: int  # posicao do ponto na matriz de distancias


def _entrega_compativel(veiculo: Veiculo, entrega: Entrega) -> bool:
    """
    Valida compatibilidade de tipo de carga.
    - Veiculo tipo 2 (agrotoxico) somente leva carga tipo 2.
    - Carga tipo 2 somente pode ir em veiculo tipo 2.
    - Para os demais tipos, exige igualdade.
    """
    if entrega.tipo_carga == 2 and veiculo.tipo_carga != 2:
        return False
    if veiculo.tipo_carga == 2 and entrega.tipo_carga != 2:
        return False
    return veiculo.tipo_carga == entrega.tipo_carga


def _distancia_rota(indices: List[int], matriz: List[List[float]], deposito: int) -> float:
    """Calcula distancia deposito -> pontos -> deposito para uma rota."""
    if not indices:
        return 0.0
    distancia = matriz[deposito][indices[0]]
    for i in range(len(indices) - 1):
        distancia += matriz[indices[i]][indices[i + 1]]
    distancia += matriz[indices[-1]][deposito]
    return distancia


def _peso_rota(ids_entregas: List[str], entregas_map: Dict[str, Entrega]) -> float:
    return sum(entregas_map[eid].peso for eid in ids_entregas)


def _avaliar_rota_ids(
    rota_ids: List[str],
    matriz: List[List[float]],
    entregas_map: Dict[str, Entrega],
    deposito: int,
) -> float:
    """Calcula custo da rota (deposito -> pontos -> deposito) usando ids de entrega."""
    if not rota_ids:
        return 0.0
    indices = [entregas_map[eid].indice_matriz for eid in rota_ids]
    return _distancia_rota(indices, matriz, deposito)


def _criar_solucao_inicial(entregas: List[Entrega], veiculos: List[Veiculo]) -> Dict[str, List[str]]:
    solucao = {v.id: [] for v in veiculos}
    pesos = {v.id: 0.0 for v in veiculos}
    embaralhadas = entregas[:]
    random.shuffle(embaralhadas)

    for entrega in embaralhadas:
        candidatos = [
            v for v in veiculos
            if _entrega_compativel(v, entrega) and pesos[v.id] + entrega.peso <= v.limite_peso
        ]
        if not candidatos:
            raise ValueError(f"Nenhum veiculo suporta a entrega {entrega.id} (peso ou tipo de carga).")
        veiculo_escolhido = random.choice(candidatos)
        solucao[veiculo_escolhido.id].append(entrega.id)
        pesos[veiculo_escolhido.id] += entrega.peso

    for rota in solucao.values():
        random.shuffle(rota)
    return solucao


def _veiculo_da_entrega(entrega_id: str, solucao: Dict[str, List[str]]) -> str:
    for vid, rotas in solucao.items():
        if entrega_id in rotas:
            return vid
    return ""


def _ordenacao_referencia(solucao: Dict[str, List[str]]) -> Dict[str, Dict[str, int]]:
    # mapa veiculo -> posicao da entrega (serve para preservar parte da ordem no crossover)
    ref = {}
    for vid, rota in solucao.items():
        ref[vid] = {entrega_id: idx for idx, entrega_id in enumerate(rota)}
    return ref


def _crossover(
    pai: Dict[str, List[str]],
    mae: Dict[str, List[str]],
    entregas: List[Entrega],
    veiculos: List[Veiculo],
) -> Dict[str, List[str]]:
    filho = {v.id: [] for v in veiculos}
    pesos = {v.id: 0.0 for v in veiculos}

    ref_pai = _ordenacao_referencia(pai)
    ref_mae = _ordenacao_referencia(mae)
    veiculos_map = {v.id: v for v in veiculos}

    for entrega in entregas:
        origem = pai if random.random() < 0.5 else mae
        candidato = _veiculo_da_entrega(entrega.id, origem)
        escolhido = None

        if candidato:
            veic = veiculos_map[candidato]
            if (
                _entrega_compativel(veic, entrega)
                and pesos[candidato] + entrega.peso <= veic.limite_peso
            ):
                escolhido = candidato

        if not escolhido:
            compat = [
                v.id for v in veiculos
                if _entrega_compativel(v, entrega) and pesos[v.id] + entrega.peso <= v.limite_peso
            ]
            if compat:
                escolhido = random.choice(compat)
            else:
                # fallback: coloca no veiculo do pai/mae mesmo que gere penalidade
                escolhido = candidato or veiculos[0].id

        filho[escolhido].append(entrega.id)
        pesos[escolhido] += entrega.peso

    for vid, rota in filho.items():
        ref = {}
        ref.update(ref_pai.get(vid, {}))
        ref.update({k: v + 1000 for k, v in ref_mae.get(vid, {}).items()})
        rota.sort(key=lambda eid: ref.get(eid, 9999))
    return filho


def _mutacao(
    solucao: Dict[str, List[str]],
    entregas_map: Dict[str, Entrega],
    veiculos_map: Dict[str, Veiculo],
    taxa_mutacao: float,
) -> Dict[str, List[str]]:
    novo = {vid: rotas[:] for vid, rotas in solucao.items()}

    def pesos_atualizados():
        return {vid: _peso_rota(rotas, entregas_map) for vid, rotas in novo.items()}

    if random.random() < taxa_mutacao:
        vid = random.choice(list(novo.keys()))
        rota = novo[vid]
        if len(rota) > 1:
            i, j = random.sample(range(len(rota)), 2)
            rota[i], rota[j] = rota[j], rota[i]

    if random.random() < taxa_mutacao:
        pesos = pesos_atualizados()
        origens = [v for v, r in novo.items() if r]
        if origens:
            origem_vid = random.choice(origens)
            origem_rota = novo[origem_vid]
            entrega_id = random.choice(origem_rota)
            entrega = entregas_map[entrega_id]
            destinos = [
                vid for vid, veic in veiculos_map.items()
                if vid != origem_vid
                and _entrega_compativel(veic, entrega)
                and pesos[vid] + entrega.peso <= veic.limite_peso
            ]
            if destinos:
                destino_vid = random.choice(destinos)
                origem_rota.remove(entrega_id)
                novo[destino_vid].append(entrega_id)
    return novo


def _movimento_2opt_ids(rota_ids: List[str], i: int, j: int) -> List[str]:
    """Aplica movimento 2-opt invertendo trecho (i+1..j) da rota."""
    return rota_ids[: i + 1] + list(reversed(rota_ids[i + 1 : j + 1])) + rota_ids[j + 1 :]


def _busca_local_2opt(
    rota_ids: List[str],
    matriz: List[List[float]],
    entregas_map: Dict[str, Entrega],
    deposito: int,
) -> Tuple[List[str], float]:
    """
    Melhor vizinho com 2-opt dentro de uma rota (mantem veiculo/capacidade).
    Retorna rota refinada e custo.
    """
    melhor_rota = rota_ids[:]
    melhor_custo = _avaliar_rota_ids(melhor_rota, matriz, entregas_map, deposito)
    n = len(melhor_rota)
    if n < 3:
        return melhor_rota, melhor_custo

    while True:
        melhor_iter = None
        custo_iter = melhor_custo
        for i in range(0, n - 2):
            for j in range(i + 2, n):
                candidata = _movimento_2opt_ids(melhor_rota, i, j)
                custo = _avaliar_rota_ids(candidata, matriz, entregas_map, deposito)
                if custo < custo_iter:
                    melhor_iter = candidata
                    custo_iter = custo
        if melhor_iter is None:
            break
        melhor_rota = melhor_iter
        melhor_custo = custo_iter
    return melhor_rota, melhor_custo


def _aplicar_busca_local_por_rota(
    solucao: Dict[str, List[str]],
    matriz: List[List[float]],
    entregas_map: Dict[str, Entrega],
    deposito: int,
) -> Dict[str, List[str]]:
    """
    Refina a ordem interna das rotas com 2-opt (nao altera atribuicao de veiculo).
    """
    ajustada = {vid: rotas[:] for vid, rotas in solucao.items()}
    for vid, rota_ids in ajustada.items():
        if len(rota_ids) < 3:
            continue
        melhor, _ = _busca_local_2opt(rota_ids, matriz, entregas_map, deposito)
        ajustada[vid] = melhor
    return ajustada


def _fitness(
    solucao: Dict[str, List[str]],
    matriz: List[List[float]],
    entregas_map: Dict[str, Entrega],
    veiculos_map: Dict[str, Veiculo],
    deposito: int,
    penalidade_peso: float = 10_000.0,
    penalidade_tipo: float = 1_000_000.0,
) -> float:
    custo = 0.0
    for vid, rota_ids in solucao.items():
        veic = veiculos_map[vid]
        rota_indices = [entregas_map[eid].indice_matriz for eid in rota_ids]
        custo += _distancia_rota(rota_indices, matriz, deposito)

        peso = _peso_rota(rota_ids, entregas_map)
        if peso > veic.limite_peso:
            custo += (peso - veic.limite_peso) * penalidade_peso

        for entrega_id in rota_ids:
            entrega = entregas_map[entrega_id]
            if entrega.tipo_carga == 2 and veic.tipo_carga != 2:
                custo += penalidade_tipo
            if veic.tipo_carga == 2 and entrega.tipo_carga != 2:
                custo += penalidade_tipo
    return custo


def encontrar_melhor_rota_genetico(
    matriz_distancias: List[List[float]],
    entregas: List[Entrega],
    veiculos: List[Veiculo],
    deposito: int = 0,
    tamanho_populacao: int = 60,
    geracoes: int = 150,
    taxa_mutacao: float = 0.12,
    tamanho_torneio: int = 3,
    usar_busca_local: bool = True,
) -> Dict[str, object]:
    """
    Minimiza a distancia percorrida usando algoritmo genetico.
    Respeita limite de carga do veiculo e a regra de carga tipo 2 (agrotoxico).

    Retorna:
        {
            "rotas_por_veiculo": {veiculo_id: [lista de entregas na ordem]},
            "distancia_total_km": distancia sem penalidades,
            "custo_fitness": valor usado para ranquear (com penalidades)
        }
    """
    if not entregas:
        rotas_vazias = {v.id: [] for v in veiculos}
        return {"rotas_por_veiculo": rotas_vazias, "distancia_total_km": 0.0, "custo_fitness": 0.0}

    entregas_map = {e.id: e for e in entregas}
    veiculos_map = {v.id: v for v in veiculos}

    populacao = []
    for _ in range(tamanho_populacao):
        inicial = _criar_solucao_inicial(entregas, veiculos)
        if usar_busca_local:
            inicial = _aplicar_busca_local_por_rota(inicial, matriz_distancias, entregas_map, deposito)
        populacao.append(inicial)

    melhor_solucao = None
    melhor_custo = float("inf")

    for _ in range(geracoes):
        custos = [
            (sol, _fitness(sol, matriz_distancias, entregas_map, veiculos_map, deposito))
            for sol in populacao
        ]

        for sol, custo in custos:
            if custo < melhor_custo:
                melhor_custo = custo
                melhor_solucao = sol

        nova_populacao = []
        while len(nova_populacao) < tamanho_populacao:
            candidatos = random.sample(populacao, tamanho_torneio)
            pai = min(candidatos, key=lambda s: _fitness(s, matriz_distancias, entregas_map, veiculos_map, deposito))
            candidatos = random.sample(populacao, tamanho_torneio)
            mae = min(candidatos, key=lambda s: _fitness(s, matriz_distancias, entregas_map, veiculos_map, deposito))

            filho = _crossover(pai, mae, entregas, veiculos)
            filho = _mutacao(filho, entregas_map, veiculos_map, taxa_mutacao)
            if usar_busca_local:
                filho = _aplicar_busca_local_por_rota(filho, matriz_distancias, entregas_map, deposito)
            nova_populacao.append(filho)

        populacao = nova_populacao

    distancia_total = 0.0
    for vid, rota_ids in (melhor_solucao or {}).items():
        rota_indices = [entregas_map[eid].indice_matriz for eid in rota_ids]
        distancia_total += _distancia_rota(rota_indices, matriz_distancias, deposito)

    return {
        "rotas_por_veiculo": melhor_solucao or {},
        "distancia_total_km": distancia_total,
        "custo_fitness": melhor_custo,
    }
