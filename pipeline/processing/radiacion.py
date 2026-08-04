"""Indicador de irradiacion solar global horizontal, serie mensual.

Fuente: PVGIS-SARAH3 del Joint Research Centre, con datos meteorologicos ERA5.

Se muestrea una rejilla de puntos dentro del termino y se publica la media municipal junto
con el recorrido entre puntos, que describe cuanto varia la irradiacion entre la costa y la
sierra por efecto del horizonte topografico.

La serie es un REANALISIS CERRADO: termina en 2023 y no crece cada mes. El indicador lo
declara para que el sitio no lo presente como desactualizado, que seria una lectura falsa.
"""

from __future__ import annotations

import json

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import pvgis

CACHE = "pvgis"


def construir_serie(cfg: dict, forzar: bool = False) -> dict:
    ind = cfg["indicadores"]["radiacion_solar"]
    limite = gpd.read_file(DIR_PROCESSED / "limite_municipal.geojson")
    puntos = pvgis.puntos_de_muestreo(limite, n_lado=ind.get("puntos_por_lado", 4))

    destino = DIR_RAW / CACHE
    destino.mkdir(parents=True, exist_ok=True)

    por_punto, leidos, reutilizados = [], 0, 0
    for lat, lon in puntos:
        cache = destino / f"pvgis_{lat}_{lon}.json"
        if cache.exists() and not forzar:
            por_punto.append(json.loads(cache.read_text(encoding="utf-8")))
            reutilizados += 1
            continue
        datos = pvgis.serie_mensual(lat, lon)
        cache.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        por_punto.append(datos)
        leidos += 1

    serie = _componer(por_punto)
    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": "radiacion_solar",
        "titulo": "Irradiación solar global horizontal",
        "unidad": "kWh/m² y mes",
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        # Serie cerrada: el frontend no debe marcarla como desactualizada por no crecer
        "tipo_serie": "reanalisis_cerrado",
        "serie_termina_en": f"{pvgis.ANIO_FIN}-12",
        "ultimo_periodo": con_dato[-1]["periodo"] if con_dato else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "n_puntos_muestreo": len(puntos),
        "serie": serie,
        "_telemetria": {
            "puntos_leidos": leidos,
            "puntos_reutilizados": reutilizados,
            "puntos": puntos,
        },
    }


def _componer(por_punto: list[list[dict]]) -> list[dict]:
    """Media entre puntos de muestreo para cada mes, con el recorrido espacial."""
    acumulado: dict[str, list[float]] = {}
    for datos in por_punto:
        for x in datos:
            periodo = f"{int(x['year']):04d}-{int(x['month']):02d}"
            acumulado.setdefault(periodo, []).append(float(x["H(h)_m"]))

    salida = []
    for periodo in sorted(acumulado):
        v = acumulado[periodo]
        salida.append({
            "periodo": periodo,
            "valor": round(sum(v) / len(v), 1),
            "minimo_espacial": round(min(v), 1),
            "maximo_espacial": round(max(v), 1),
            "n_puntos": len(v),
        })
    return salida


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "radiacion_solar.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    # Suma anual: es la cifra que se maneja al hablar de potencial solar
    por_anio: dict[str, float] = {}
    for r in con_dato:
        por_anio[r["periodo"][:4]] = por_anio.get(r["periodo"][:4], 0) + r["valor"]
    completos = {a: v for a, v in por_anio.items() if sum(1 for r in con_dato if r["periodo"][:4] == a) == 12}

    ficha = {
        "indicador": "radiacion_solar",
        "titulo": "Irradiación solar global horizontal",
        "descripcion": (
            "Energía solar recibida por metro cuadrado de superficie horizontal, promediada "
            "sobre una rejilla de puntos del término municipal."
        ),
        "fuente": "PVGIS-SARAH3, Joint Research Centre de la Comisión Europea (meteorología ERA5)",
        "formula": "Irradiación global horizontal mensual, H(h)_m, en kWh/m²",
        "resolucion_espacial": f"{resultado['n_puntos_muestreo']} puntos de muestreo dentro del término",
        "resolucion_temporal": "mensual",
        "metodo": (
            "Se genera una rejilla regular en EPSG:25830 recortada al término municipal y se "
            "consulta PVGIS en cada punto. El valor publicado es la media entre puntos; se "
            "publican además el mínimo y el máximo espaciales de cada mes."
        ),
        "enmascaramiento": "No aplica: PVGIS entrega una serie ya elaborada por punto.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "irradiacion_anual_media_kwh_m2": round(sum(completos.values()) / len(completos)) if completos else None,
        "limitaciones": [
            "Es un reanálisis de recorrido cerrado: la base de radiación termina en "
            f"{pvgis.ANIO_FIN} y la serie no crece mes a mes como las de satélite.",
            "PVGIS entrega el dato por coordenada, no por polígono: la media municipal se "
            "obtiene muestreando puntos, no integrando toda la superficie.",
            "El cálculo incorpora el horizonte topográfico derivado de un modelo digital de "
            "elevaciones, pero no el sombreado por edificación.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "PVGIS, Joint Research Centre. Uso libre con atribución.",
        "ruta_datos": "data/processed/radiacion_solar.json",
    }
    (DIR_METADATA / "radiacion_solar.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
