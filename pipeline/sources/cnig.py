"""Fuente CNIG: limite municipal oficial desde el WFS INSPIRE de Unidades Administrativas.

Limitacion del servicio: no admite CQL_FILTER (responde 504). Hay que descargar por bbox y
filtrar en local por nationalCode. La descarga ronda los 26 MB e incluye toda la jerarquia
administrativa, por lo que se cachea en data/raw y no se repite si ya existe.
"""

from __future__ import annotations

import json
import warnings

import geopandas as gpd
import requests

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW

warnings.filterwarnings("ignore")

ENDPOINT = "https://www.ign.es/wfs-inspire/unidades-administrativas"


def _descargar_gml(bbox_4326: list, destino) -> None:
    """Descarga las unidades administrativas que intersectan el bbox indicado."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "au:AdministrativeUnit",
        "srsName": "urn:ogc:def:crs:EPSG::4326",
        # El orden del bbox en este servicio es lat_min, lon_min, lat_max, lon_max
        "bbox": ",".join(str(v) for v in bbox_4326) + ",urn:ogc:def:crs:EPSG::4326",
    }
    r = requests.get(ENDPOINT, params=params, timeout=300)
    r.raise_for_status()
    destino.write_bytes(r.content)


def obtener_limite_municipal(cfg: dict, forzar: bool = False) -> dict:
    """Genera limite_municipal.geojson y su ficha de metadatos. Devuelve la ficha."""
    geo = cfg["geometria"]
    crs = cfg["crs"]
    codigo = geo["codigo_nacional_cnig"] if "codigo_nacional_cnig" in geo else cfg["ambito"]["codigo_nacional_cnig"]

    cache = DIR_RAW / "cnig_unidades_administrativas.gml"
    if forzar or not cache.exists():
        _descargar_gml(geo["bbox_descarga_4326"], cache)

    g = gpd.read_file(cache)
    # geopandas tipa nationalCode como entero: se normaliza a texto para comparar
    g["_codigo"] = g["nationalCode"].astype(str).str.strip()
    municipio = g[g["_codigo"] == str(codigo)][["geometry"]].copy()
    if municipio.empty:
        raise RuntimeError(f"No se encontro la unidad administrativa {codigo} en el GML del CNIG")

    municipio["codigo_ine"] = cfg["ambito"]["codigo_ine"]
    municipio["municipio"] = cfg["ambito"]["municipio"]

    salida = DIR_PROCESSED / "limite_municipal.geojson"
    municipio.to_file(salida, driver="GeoJSON")

    # La superficie SIEMPRE se calcula en el CRS de calculo (25830), nunca en el de peticion
    en_metros = municipio.to_crs(crs["calculo"])
    superficie_ha = round(en_metros.geometry.area.sum() / 10_000, 1)

    ficha = {
        "indicador": "limite_municipal",
        "titulo": "Limite del termino municipal",
        "fuente": "CNIG - WFS INSPIRE Unidades Administrativas (au:AdministrativeUnit)",
        "endpoint": ENDPOINT,
        "codigo_nacional": str(codigo),
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "superficie_ha": superficie_ha,
        "superficie_ha_referencia_pgom": geo.get("superficie_ha_referencia"),
        "bbox_epsg25830": [round(v, 1) for v in en_metros.total_bounds],
        "bbox_epsg4326": [round(v, 6) for v in municipio.total_bounds],
        "epsg_calculo": crs["calculo"],
        "metodo": "Descarga por bbox y filtrado local por nationalCode",
        "limitaciones": "El servicio no admite CQL_FILTER (responde 504).",
        "licencia": "CC BY 4.0 scne.es",
    }
    (DIR_METADATA / "limite_municipal.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ficha
