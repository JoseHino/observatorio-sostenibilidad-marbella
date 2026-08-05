"""Indicador de temperatura del aire y precipitacion medidas en estacion (AEMET).

Complementa la temperatura superficial de Landsat. Son cosas distintas y conviene no
confundirlas: Landsat mide la piel del terreno a media manana, que en verano supera con
holgura la del aire; AEMET mide temperatura del aire en garita, que es la de uso
climatologico y la que percibe una persona.

Si no hay clave configurada, la tarea no falla: se salta y lo declara. Asi el resto del
pipeline sigue funcionando mientras la clave no este dada de alta.
"""

from __future__ import annotations

import json
import os

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED
from sources import aemet


def hay_clave() -> bool:
    return bool(os.environ.get("AEMET_API_KEY", "").strip())


def construir(cfg: dict, forzar: bool = False) -> dict:
    g = gpd.read_file(DIR_PROCESSED / "limite_municipal.geojson").to_crs(4326)
    centro = g.geometry.iloc[0].representative_point()

    estacion = aemet.estacion_mas_cercana(centro.y, centro.x, forzar=forzar)
    idema = estacion["indicativo"]

    anio_ini = int(cfg["serie"]["fecha_inicio"][:4])
    from datetime import date
    filas = aemet.climatologia_mensual(idema, anio_ini, date.today().year, forzar=forzar)
    valores = aemet.a_series(filas)

    serie = []
    for periodo in sorted(valores):
        v = valores[periodo]
        if v["tm_mes"] is None and v["precipitacion"] is None:
            serie.append({"periodo": periodo, "valor": None,
                          "motivo": "la estación no registró dato ese mes"})
            continue
        serie.append({
            "periodo": periodo,
            "valor": v["tm_mes"],
            "temperatura_maxima_media": v["tm_max"],
            "temperatura_minima_media": v["tm_min"],
            "precipitacion_mm": v["precipitacion"],
        })

    con = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": "clima_aemet",
        "titulo": "Temperatura del aire y precipitación",
        "unidad": "°C",
        "unidad_analisis": f"estación {idema}",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "estacion": {
            "indicativo": idema,
            "nombre": estacion.get("nombre"),
            "provincia": estacion.get("provincia"),
            "altitud_m": estacion.get("altitud"),
            "distancia_km": estacion.get("distancia_km"),
        },
        "ultimo_periodo": con[-1]["periodo"] if con else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con),
        "serie": serie,
        "_telemetria": {"estacion": idema, "filas_crudas": len(filas)},
    }


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "clima_aemet.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    con = [r for r in resultado["serie"] if r["valor"] is not None]
    est = resultado["estacion"]
    ficha = {
        "indicador": "clima_aemet",
        "titulo": "Temperatura del aire y precipitación",
        "descripcion": (
            "Temperatura media mensual del aire y precipitación acumulada, medidas en la "
            f"estación de AEMET más próxima al municipio ({est.get('nombre')}, a "
            f"{est.get('distancia_km')} km, {est.get('altitud_m')} m de altitud)."
        ),
        "fuente": f"Agencia Estatal de Meteorología, AEMET OpenData, estación {est.get('indicativo')}",
        "formula": "Valores climatológicos mensuales publicados por AEMET",
        "resolucion_espacial": "puntual: una estación",
        "resolucion_temporal": "mensual",
        "metodo": (
            "Se selecciona la estación de la red de AEMET más próxima al punto representativo "
            "del término y se descargan sus valores climatológicos mensuales."
        ),
        "enmascaramiento": "No aplica: es dato medido en estación.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "Es una medida PUNTUAL de una estación, no un promedio del término. En un "
            "municipio con 1.200 m de desnivel entre la costa y Sierra Blanca, una sola "
            "estación no representa todo el ámbito.",
            "NO debe confundirse con la temperatura superficial terrestre publicada en el "
            "Bloque 2: aquella mide la piel del terreno a media mañana y en verano supera con "
            "holgura a la del aire. Son magnitudes distintas.",
            "Los meses sin registro de la estación se publican como hueco. No se interpolan.",
            "La serie presenta lagunas importantes en 2018 y 2020, y un escalón entre 2019 y "
            "2021 que no puede atribuirse con seguridad al clima: con 2020 casi entero "
            "ausente, cabe que responda a un cambio en el registro de la estación. Debe "
            "leerse con cautela y contrastarse con la temperatura superficial de Landsat, "
            "que no muestra ese escalón.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con) if con else None,
        "valor_maximo_serie": max(r["valor"] for r in con) if con else None,
        "licencia": "Elaboración propia a partir de datos de la Agencia Estatal de Meteorología",
        "ruta_datos": "data/processed/clima_aemet.json",
    }
    (DIR_METADATA / "clima_aemet.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
