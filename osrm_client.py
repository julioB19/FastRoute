import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests


class OSRMError(Exception):
    """Erro generico para chamadas ao OSRM."""


class OSRMClient:
    """
    Cliente simples para OSRM.

    Aceita coordenadas como (lat, lon) e converte para o formato lon,lat esperado pelo OSRM.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        profile: str = "driving",
        timeout: int = 10,
        max_concurrency: int = 5,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (base_url or os.getenv("OSRM_URL") or "http://localhost:5000").rstrip("/")
        self.profile = profile
        self.timeout = timeout
        self.max_concurrency = max_concurrency
        self.session = session or requests.Session()

    def _format_coords(self, coords: List[Tuple[float, float]]) -> str:
        """Converte lista [(lat, lon), ...] em 'lon,lat;lon,lat'."""
        return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)

    def _request(self, url: str, params: Dict[str, str]) -> Dict:
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.Timeout as e:
            raise OSRMError("OSRM: timeout ao consultar o servico.") from e
        except requests.RequestException as e:
            raise OSRMError(f"OSRM: falha na requisicao: {e}") from e

        if resp.status_code >= 500:
            raise OSRMError("OSRM: erro no servidor ao processar a rota.")
        if resp.status_code >= 400:
            raise OSRMError(f"OSRM: requisicao invalida ({resp.status_code}).")

        try:
            return resp.json()
        except ValueError as e:
            raise OSRMError("OSRM: resposta nao eh JSON valido.") from e

    def route(
        self,
        origem: Tuple[float, float],
        destino: Tuple[float, float],
        *,
        overview: str = "false",
        geometries: Optional[str] = None,
        steps: bool = False,
    ) -> Dict[str, object]:
        """
        Consulta /route e retorna distancia (m), duracao (s) e, opcionalmente, geometria/steps.
        """
        coord_str = self._format_coords([origem, destino])
        url = f"{self.base_url}/route/v1/{self.profile}/{coord_str}"
        params: Dict[str, str] = {
            "overview": overview,
            "steps": "true" if steps else "false",
        }
        if geometries:
            params["geometries"] = geometries

        data = self._request(url, params)

        if data.get("code") != "Ok" or not data.get("routes"):
            raise OSRMError(f"OSRM: resposta invalida em /route: {data}")

        route_info = data["routes"][0]
        result = {
            "distance": float(route_info.get("distance") or 0.0),
            "duration": float(route_info.get("duration") or 0.0),
        }

        if geometries:
            result["geometry"] = route_info.get("geometry")
        if steps:
            result["steps"] = route_info.get("legs", [])

        return result

    def table(
        self,
        coordenadas: List[Tuple[float, float]],
        *,
        annotations: str = "distance,duration",
        fallback_to_route: bool = True,
    ) -> Dict[str, List[List[float]]]:
        """
        Usa /table para obter matrizes de distancia (m) e duracao (s).
        Se falhar, pode fazer fallback chamando /route em pares com limite de concorrencia.
        """
        if not coordenadas:
            return {"distances": [], "durations": []}

        coord_str = self._format_coords(coordenadas)
        url = f"{self.base_url}/table/v1/{self.profile}/{coord_str}"
        params = {"annotations": annotations}

        try:
            data = self._request(url, params)
            if data.get("code") != "Ok":
                raise OSRMError(f"OSRM: resposta invalida em /table: {data}")

            return {
                "distances": data.get("distances") or [],
                "durations": data.get("durations") or [],
            }
        except OSRMError:
            if not fallback_to_route:
                raise
            # Fallback: calcula via chamadas /route em pares com concorrencia controlada
            return self._table_via_route(coordenadas)

    def _table_via_route(self, coordenadas: List[Tuple[float, float]]) -> Dict[str, List[List[float]]]:
        n = len(coordenadas)
        dist = [[0.0 for _ in range(n)] for _ in range(n)]
        dur = [[0.0 for _ in range(n)] for _ in range(n)]

        def calcular(i: int, j: int):
            return i, j, self.route(coordenadas[i], coordenadas[j], overview="false")

        futures = []
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for i in range(n):
                for j in range(i + 1, n):
                    futures.append(executor.submit(calcular, i, j))

            for future in as_completed(futures):
                i, j, resultado = future.result()
                dist[i][j] = dist[j][i] = float(resultado.get("distance") or 0.0)
                dur[i][j] = dur[j][i] = float(resultado.get("duration") or 0.0)

        return {"distances": dist, "durations": dur}
