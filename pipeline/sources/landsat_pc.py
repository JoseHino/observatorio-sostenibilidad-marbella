"""Fuente Landsat: coleccion 2 nivel 2 del USGS, servida por Microsoft Planetary Computer.

Por que Landsat y no Sentinel-3: el producto SENTINEL3_SLSTR_L2_LST tiene 1 km de pixel, que
sobre 117 km2 da del orden de 117 valores; no permite lectura por barrios. Landsat entrega la
temperatura superficial en rejilla de 30 m.

Por que ST_B10 y no una estimacion propia: la coleccion 2 nivel 2 publica la temperatura
superficial YA corregida por emisividad. Es un producto oficial del USGS. Convertir bandas de
brillo a temperatura superficial con una correccion propia seria una aproximacion no
documentada.

Por que Planetary Computer y no landsatlook.usgs.gov: las URL de USGS redirigen a un login de
EROS. Planetary Computer firma los mismos ficheros con un token SAS anonimo y gratuito. La
alternativa en S3 (usgs-landsat) es requester-pays y queda descartada por no incurrir en gasto.
"""

from __future__ import annotations

import time
import warnings

import numpy as np
import rasterio
import requests
from rasterio.mask import mask as rio_mask

warnings.filterwarnings("ignore")

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
URL_SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"

# Escalado oficial de la coleccion 2 nivel 2 para pasar ST_B10 a kelvin
ESCALA, DESPLAZAMIENTO = 0.00341802, 149.0

# Bits documentados de QA_PIXEL en la coleccion 2
BIT_DESPEJADO = 6   # 1 = sin nube, sin nube dilatada, sin cirro y sin sombra
BIT_AGUA = 7        # 1 = agua; se excluye para que la LST sea terrestre

# Configuracion de GDAL para leer COG por rangos HTTP sin listar el directorio remoto
CFG_GDAL = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_USE_HEAD="NO",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="2",
)

_sas: dict = {"token": None, "expira": 0.0}


def token_sas() -> str:
    """Token SAS anonimo. Caduca en menos de una hora, asi que se renueva solo."""
    if _sas["token"] and time.monotonic() < _sas["expira"]:
        return _sas["token"]
    r = requests.get(URL_SAS, timeout=60)
    r.raise_for_status()
    _sas["token"] = r.json()["token"]
    _sas["expira"] = time.monotonic() + 40 * 60  # margen amplio sobre la caducidad real
    return _sas["token"]


def buscar_escenas(bbox: list, desde: str, hasta: str, limite: int = 500) -> list[dict]:
    """Escenas Landsat que intersectan el ambito en el intervalo dado, en orden temporal."""
    escenas, siguiente = [], None
    cuerpo = {
        "collections": ["landsat-c2-l2"],
        "bbox": bbox,
        "datetime": f"{desde}T00:00:00Z/{hasta}T00:00:00Z",
        "limit": 100,
    }
    while True:
        peticion = dict(cuerpo)
        if siguiente:
            peticion["token"] = siguiente
        r = requests.post(STAC, json=peticion, timeout=180)
        r.raise_for_status()
        d = r.json()
        escenas.extend(d.get("features", []))
        enlaces = [x for x in d.get("links", []) if x.get("rel") == "next"]
        if not enlaces or len(escenas) >= limite:
            break
        siguiente = (enlaces[0].get("body") or {}).get("token")
        if not siguiente:
            break
    return sorted(escenas, key=lambda x: x["properties"]["datetime"])


def estadisticas_escena(escena: dict, limite_gdf) -> dict | None:
    """Estadistica de LST sobre el municipio para una escena. None si no se pudo leer.

    Se lee solo la ventana del poligono mediante rangos HTTP: no se descarga la escena.
    """
    sas = token_sas()
    try:
        with rasterio.Env(**CFG_GDAL):
            with rasterio.open(f"{escena['assets']['lwir11']['href']}?{sas}") as src:
                geom = limite_gdf.to_crs(src.crs).geometry.tolist()
                st, _ = rio_mask(src, geom, crop=True, filled=True, nodata=0)
            with rasterio.open(f"{escena['assets']['qa_pixel']['href']}?{sas}") as src:
                qa, _ = rio_mask(src, geom, crop=True, filled=True, nodata=1)
    except Exception:
        return None

    st = st[0].astype("float64")
    qa = qa[0].astype("uint16")
    despejado = (qa >> BIT_DESPEJADO) & 1
    agua = (qa >> BIT_AGUA) & 1
    valido = (st > 0) & (despejado == 1) & (agua == 0)

    n_recorte = int((st > 0).sum())
    n_valido = int(valido.sum())
    if n_valido == 0 or n_recorte == 0:
        return {
            "id": escena["id"],
            "fecha": escena["properties"]["datetime"][:10],
            "plataforma": escena["properties"].get("platform"),
            "nubes_escena_pct": escena["properties"].get("eo:cloud_cover"),
            "pixeles_validos": 0,
            "cobertura_pct": 0.0,
        }

    lst = st[valido] * ESCALA + DESPLAZAMIENTO - 273.15
    p10, p50, p90 = (float(x) for x in np.percentile(lst, [10, 50, 90]))
    return {
        "id": escena["id"],
        "fecha": escena["properties"]["datetime"][:10],
        "plataforma": escena["properties"].get("platform"),
        "nubes_escena_pct": escena["properties"].get("eo:cloud_cover"),
        "pixeles_validos": n_valido,
        "cobertura_pct": round(100 * n_valido / n_recorte, 1),
        "lst_media": round(float(lst.mean()), 2),
        "lst_p10": round(p10, 2),
        "lst_mediana": round(p50, 2),
        "lst_p90": round(p90, 2),
        # Amplitud termica interna: separacion entre las superficies mas frias y mas calidas
        "amplitud_p10_p90": round(p90 - p10, 2),
    }
