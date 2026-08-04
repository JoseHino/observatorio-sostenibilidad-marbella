"""Indicador de calidad de aguas litorales: clorofila-a, serie mensual.

Fuente: SENTINEL3_OLCI_L2_WATER via openEO, banda CHL_NN.

Se usa CHL_NN y no CHL_OC4ME: el algoritmo OC4Me esta pensado para aguas oceanicas de tipo 1,
mientras que la red neuronal CHL_NN es la recomendada para aguas costeras de tipo 2, que son
las de la franja de interes. Ambos son productos oficiales de la ESA; no se estima nada.

El dato se agrega sobre la franja marina de 2 km derivada del limite municipal.

Limitacion de fondo, que se declara junto al dato: los productos oceanicos estandar pierden
fiabilidad cerca de la costa por reflexion del fondo y por aportes terrestres. La serie sirve
para leer estacionalidad y tendencia, no como medida absoluta de concentracion.
"""

from __future__ import annotations

import json
from datetime import date

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import copernicus_openeo as oeo

COLECCION = "SENTINEL3_OLCI_L2_WATER"
BANDA = "CHL_NN"


def _grafo(fc: dict, bbox, desde: str, hasta: str) -> dict:
    return {"process_graph": {
        "cargar": {"process_id": "load_collection", "arguments": {
            "id": COLECCION,
            "spatial_extent": {"west": float(bbox[0]), "south": float(bbox[1]),
                               "east": float(bbox[2]), "north": float(bbox[3])},
            "temporal_extent": [desde, hasta],
            "bands": [BANDA]}},
        "mensual": {"process_id": "aggregate_temporal_period", "arguments": {
            "data": {"from_node": "cargar"}, "period": "month", "reducer": oeo.REDUCTOR_MEDIA}},
        "zonal": {"process_id": "aggregate_spatial", "arguments": {
            "data": {"from_node": "mensual"}, "geometries": fc, "reducer": oeo.REDUCTOR_MEDIA}},
        "guardar": {"process_id": "save_result", "arguments": {
            "data": {"from_node": "zonal"}, "format": "JSON"}, "result": True},
    }}


def construir_serie(cfg: dict, forzar: bool = False) -> dict:
    ruta = DIR_PROCESSED / "buffer_marino.geojson"
    if not ruta.exists():
        raise RuntimeError("Falta buffer_marino.geojson; ejecutar antes esa tarea")

    g = gpd.read_file(ruta)
    # Se simplifica para aligerar la peticion; no afecta a ningun calculo de superficie
    simple = gpd.GeoSeries([g.to_crs(32630).geometry.iloc[0].simplify(150)], crs=32630).to_crs(4326)
    fc = json.loads(simple.to_json())
    bbox = simple.total_bounds

    hoy = date.today()
    inicio = int(cfg["serie"]["fecha_inicio"][:4])
    intervalos, anios_leidos = [], []

    for anio in range(inicio, hoy.year + 1):
        nombre = f"chl_{anio}"
        cache = None if forzar else oeo.leer_cache(nombre)
        if cache is None:
            hasta = f"{anio + 1}-01-01" if anio < hoy.year else hoy.isoformat()
            cache = oeo.ejecutar(_grafo(fc, bbox, f"{anio}-01-01", hasta))
            oeo.cachear(nombre, cache)
            anios_leidos.append(anio)
        intervalos.append(cache)

    serie = _componer(intervalos)
    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": "clorofila_litoral",
        "titulo": "Clorofila-a en aguas litorales",
        "unidad": "mg/m³",
        "unidad_analisis": "franja marina de 2 km",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": con_dato[-1]["periodo"] if con_dato else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "serie": serie,
        "_telemetria": {"anios_leidos": anios_leidos},
    }


def _componer(intervalos: list[dict]) -> list[dict]:
    valores: dict[str, float] = {}
    for bloque in intervalos:
        for k, v in bloque.items():
            periodo = k[:7]
            c = v[0][0] if v and v[0] and v[0][0] is not None else None
            if c is not None:
                valores[periodo] = round(float(c), 4)

    if not valores:
        return []
    periodos = sorted(valores)
    a, m = int(periodos[0][:4]), int(periodos[0][5:7])
    fa, fm = int(periodos[-1][:4]), int(periodos[-1][5:7])
    salida = []
    while (a, m) <= (fa, fm):
        p = f"{a:04d}-{m:02d}"
        if p in valores:
            salida.append({"periodo": p, "valor": valores[p]})
        else:
            salida.append({"periodo": p, "valor": None,
                           "motivo": "sin observación válida en el mes"})
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return salida


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "clorofila_litoral.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    ficha = {
        "indicador": "clorofila_litoral",
        "titulo": "Clorofila-a en aguas litorales",
        "descripcion": (
            "Concentración de clorofila-a promediada sobre la franja marina de 2 km frente a "
            "la costa del término municipal."
        ),
        "fuente": "Copernicus Sentinel-3 OLCI Nivel 2 Water, banda CHL_NN, vía openEO (CDSE)",
        "formula": "Media zonal de CHL_NN sobre la franja marina",
        "resolucion_espacial": "300 m",
        "resolucion_temporal": "mensual",
        "metodo": (
            "Se emplea CHL_NN y no CHL_OC4ME: el algoritmo OC4Me está concebido para aguas "
            "oceánicas de tipo 1, mientras que la red neuronal es la recomendada para aguas "
            "costeras de tipo 2. La agregación temporal y zonal se ejecuta en el servidor de "
            "openEO; no se descarga ningún ráster."
        ),
        "enmascaramiento": "El producto de nivel 2 incorpora sus propios indicadores de calidad.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "Los productos oceánicos estándar pierden fiabilidad cerca de la costa, por "
            "reflexión del fondo en aguas someras y por aportes terrestres. La serie sirve "
            "para leer estacionalidad y tendencia, no como medida absoluta de concentración.",
            "La franja marina se deriva del límite administrativo terrestre, no de la línea "
            "de costa cartografiada a detalle.",
            "Los meses sin observación válida se publican como hueco. No se interpolan.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos Copernicus modificados",
        "ruta_datos": "data/processed/clorofila_litoral.json",
    }
    (DIR_METADATA / "clorofila_litoral.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
