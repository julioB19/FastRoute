import math


# Calcula a distância entre dois pontos (lat, lon) usando a fórmula de Haversine
def haversine(p1, p2, raio_km=6371.0):
    lat1, lon1 = p1
    lat2, lon2 = p2

    # Converte graus para radianos
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return raio_km * c


# Gera a matriz de distâncias NxN para uma lista de coordenadas
def gerar_matriz_distancias(coordenadas):
    n = len(coordenadas)
    matriz = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine(coordenadas[i], coordenadas[j])
            matriz[i][j] = dist
            matriz[j][i] = dist  # garante simetria
    return matriz


if __name__ == "__main__":
    coordenadas_exemplo = [
        (-27.358885, -53.398043),
        (-27.350000, -53.400000),
        (-27.360000, -53.395000),
    ]

    matriz = gerar_matriz_distancias(coordenadas_exemplo)

    print("Matriz de distâncias (km):")
    for linha in matriz:
        print("  ".join(f"{valor:8.3f}" for valor in linha))
