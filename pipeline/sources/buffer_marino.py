"""Geometria del buffer marino de 2 km frente a la costa de Marbella.

El buffer no puede obtenerse dilatando el municipio y restandolo: eso deja tambien un anillo
tierra adentro. Como el GML del CNIG trae ademas los municipios colindantes, se resta la union
de TODA la tierra descargada, y lo que queda del anillo es agua.
"""

from __future__ import annotations

import json
import warnings

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW

warnings.filterwarnings("ignore")


def construir(cfg: dict) -> dict:
    crs_calculo = cfg["crs"]["calculo"]
    distancia = cfg["geometria"]["buffer_marino_m"]
    codigo = cfg["ambito"]["codigo_nacional_cnig"]

    gml = DIR_RAW / "cnig_unidades_administrativas.gml"
    if not gml.exists():
        raise RuntimeError("Falta el GML del CNIG; ejecutar antes la tarea del limite municipal")

    g = gpd.read_file(gml).to_crs(crs_calculo)
    g["_codigo"] = g["nationalCode"].astype(str).str.strip()

    # Solo los municipios: se excluyen Estado, comunidad y provincia, cuyos poligonos
    # solapan a los municipales y desvirtuarian la union de tierra
    municipios = g[g["_codigo"].str.len() >= 11]
    tierra = municipios.geometry.union_all()

    marbella = g[g["_codigo"] == str(codigo)].geometry.iloc[0]
    anillo = marbella.buffer(distancia).difference(tierra)

    marino = gpd.GeoDataFrame({"ambito": ["buffer_marino"]}, geometry=[anillo], crs=crs_calculo)
    salida = DIR_PROCESSED / "buffer_marino.geojson"
    marino.to_crs(cfg["crs"]["publicacion"]).to_file(salida, driver="GeoJSON")

    superficie_ha = round(marino.geometry.area.sum() / 10_000, 1)
    ficha = {
        "indicador": "buffer_marino",
        "titulo": f"Franja marina de {distancia // 1000} km frente a la costa",
        "fuente": "Derivado del límite municipal del CNIG y de los municipios colindantes",
        "metodo": (
            f"Dilatación de {distancia} m del término municipal, restando la unión de todos "
            "los términos municipales descargados. Lo que resta del anillo es superficie "
            "marina."
        ),
        "superficie_ha": superficie_ha,
        "epsg_calculo": crs_calculo,
        "limitaciones": [
            "La franja se deriva del límite administrativo terrestre, no de la línea de "
            "costa cartografiada a escala de detalle."
        ],
        "ruta_datos": "data/processed/buffer_marino.geojson",
    }
    (DIR_METADATA / "buffer_marino.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ficha
