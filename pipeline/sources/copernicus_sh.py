"""Fuente Copernicus: Sentinel Hub del Data Space Ecosystem.

Se usa la Statistical API en lugar de descargar rasters: la reduccion de raster a estadistico
se hace en el servidor del proveedor y solo viaja el JSON agregado. Es lo que permite que el
observatorio sea estatico y que el consumo de cuota se mantenga en unidades de proceso bajas.

Restricciones del servicio comprobadas empiricamente (03/08/2026):
  - Rechaza EPSG:25830 para Sentinel-2. Exige EPSG:32630. El error que devuelve primero es
    un generico "Too many execution errors", que no menciona el CRS.
  - resx/resy se interpretan en las unidades del CRS del bounds: con bounds en 4326 serian
    grados.
  - La salida dataMask debe declararse en el setup() del evalscript.
  - Si el evalscript produce NaN o infinito, aborta la peticion completa.
"""

from __future__ import annotations

import json
import time
import warnings

import geopandas as gpd
import requests

from config import DIR_RAW, credencial

warnings.filterwarnings("ignore")

URL_TOKEN = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
URL_STATS = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

_token_cache: dict = {"valor": None, "expira": 0.0}


def obtener_token() -> str:
    """Token OAuth con reutilizacion mientras siga vigente (dura 1800 s)."""
    if _token_cache["valor"] and time.monotonic() < _token_cache["expira"]:
        return _token_cache["valor"]
    r = requests.post(
        URL_TOKEN,
        data={
            "grant_type": "client_credentials",
            "client_id": credencial("CDSE_CLIENT_ID"),
            "client_secret": credencial("CDSE_CLIENT_SECRET"),
        },
        timeout=60,
    )
    r.raise_for_status()
    d = r.json()
    _token_cache["valor"] = d["access_token"]
    # Margen de 60 s para no apurar la expiracion a mitad de una tanda de peticiones
    _token_cache["expira"] = time.monotonic() + int(d.get("expires_in", 1800)) - 60
    return _token_cache["valor"]


def geometria_para_peticion(ruta_geojson, epsg_peticion: int, tolerancia_m: int) -> dict:
    """Reproyecta y simplifica el limite municipal para aligerar la peticion.

    La simplificacion afecta solo al borde del poligono enviado al servicio; los calculos de
    superficie del observatorio no se derivan nunca de esta geometria simplificada.
    """
    g = gpd.read_file(ruta_geojson).to_crs(epsg_peticion)
    simplificada = g.geometry.iloc[0].simplify(tolerancia_m)
    return json.loads(gpd.GeoSeries([simplificada], crs=epsg_peticion).to_json())["features"][0][
        "geometry"
    ]


def pedir_estadistica(
    geometria: dict,
    epsg_peticion: int,
    coleccion: str,
    evalscript: str,
    desde: str,
    hasta: str,
    intervalo: str,
    resolucion_m: int,
    mosaico: str,
    salida_id: str,
    reintentos: int = 3,
) -> tuple[dict, float]:
    """Lanza una peticion a la Statistical API. Devuelve (respuesta, PU consumidas)."""
    cuerpo = {
        "input": {
            "bounds": {
                "geometry": geometria,
                "properties": {"crs": f"http://www.opengis.net/def/crs/EPSG/0/{epsg_peticion}"},
            },
            "data": [{"type": coleccion, "dataFilter": {"mosaickingOrder": mosaico}}],
        },
        "aggregation": {
            "timeRange": {"from": f"{desde}T00:00:00Z", "to": f"{hasta}T00:00:00Z"},
            "aggregationInterval": {"of": intervalo},
            "resx": resolucion_m,
            "resy": resolucion_m,
            "evalscript": evalscript,
        },
        "calculations": {salida_id: {"statistics": {"default": {"percentiles": {"k": [25, 50, 75]}}}}},
    }

    ultimo_error = ""
    for intento in range(1, reintentos + 1):
        r = requests.post(
            URL_STATS,
            headers={"Authorization": f"Bearer {obtener_token()}"},
            json=cuerpo,
            timeout=600,
        )
        pu = float(r.headers.get("x-processingunits-spent") or 0)
        if r.status_code == 200:
            return r.json(), pu
        ultimo_error = r.text[:300]
        # 429 y 5xx son transitorios: se reintenta con espera creciente
        if r.status_code in (429, 500, 502, 503, 504) and intento < reintentos:
            time.sleep(5 * intento)
            continue
        break
    raise RuntimeError(f"Statistical API fallo ({desde} a {hasta}): {ultimo_error}")


def guardar_respuesta_cruda(nombre: str, datos: dict) -> None:
    """Cachea la respuesta cruda para poder reconstruir sin volver a gastar cuota."""
    destino = DIR_RAW / "sh_statistics"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{nombre}.json").write_text(
        json.dumps(datos, ensure_ascii=False), encoding="utf-8"
    )
