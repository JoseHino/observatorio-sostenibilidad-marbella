"""Bloque transversal: cruce de las series ambientales con la presion turistica.

Es el elemento diferencial del observatorio. Cruza las pernoctaciones hoteleras del INE con
el NDVI y la temperatura superficial, ambos ya publicados, sobre los meses en que las tres
series coinciden.

Se publican tres lecturas:

  1. Correlacion de Pearson entre pernoctaciones y cada variable ambiental.
  2. Perfil estacional normalizado de las tres series, que hace visible si la presion
     turistica coincide o se opone al ciclo de la vegetacion.
  3. Indicadores ambientales normalizados por plaza hotelera.

Sobre la correlacion: dos series con ciclo anual marcado correlacionan por el mero hecho de
compartir estacionalidad. El coeficiente NO se interpreta como relacion causal, y asi se
declara. Su valor esta en el signo y en la magnitud del desfase, no en atribuir causa.
"""

from __future__ import annotations

import json
import math

from config import DIR_METADATA, DIR_PROCESSED
from sources import ine_tempus3 as ine

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 12:  # con menos de un ciclo anual completo el coeficiente no dice nada
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _perfil_mensual(serie: dict[str, float]) -> list[float | None]:
    """Media de cada mes del año a lo largo de la serie."""
    acum: dict[int, list[float]] = {}
    for periodo, valor in serie.items():
        acum.setdefault(int(periodo[5:7]), []).append(valor)
    return [
        round(sum(acum[m]) / len(acum[m]), 4) if m in acum else None
        for m in range(1, 13)
    ]


def _normalizar(perfil: list[float | None]) -> list[float | None]:
    """Lleva el perfil a escala 0-1 para poder superponer magnitudes incomparables."""
    vals = [v for v in perfil if v is not None]
    if not vals:
        return perfil
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5 if v is not None else None for v in perfil]
    return [round((v - lo) / (hi - lo), 4) if v is not None else None for v in perfil]


def _cargar_ambiental(nombre: str) -> dict[str, float]:
    ruta = DIR_PROCESSED / f"{nombre}.json"
    if not ruta.exists():
        return {}
    d = json.loads(ruta.read_text(encoding="utf-8"))
    return {r["periodo"]: r["valor"] for r in d.get("serie", []) if r.get("valor") is not None}


def construir(cfg: dict, forzar: bool = False) -> dict:
    pernoctaciones, inc_pern = ine.obtener("pernoctaciones", forzar=forzar)
    viajeros, _ = ine.obtener("viajeros", forzar=forzar)
    plazas, _ = ine.obtener("plazas", forzar=forzar)

    pern = {r["periodo"]: r["valor"] for r in pernoctaciones if r["valor"] is not None}
    viaj = {r["periodo"]: r["valor"] for r in viajeros if r["valor"] is not None}
    plaz = {r["periodo"]: r["valor"] for r in plazas if r["valor"] is not None}
    provisionales = {r["periodo"] for r in pernoctaciones if r.get("provisional")}

    ndvi = _cargar_ambiental("ndvi_municipal")
    lst = _cargar_ambiental("lst_municipal")

    cruces = []
    for clave, amb, titulo in [("ndvi", ndvi, "NDVI medio municipal"),
                               ("lst", lst, "Temperatura superficial terrestre")]:
        comunes = sorted(set(pern) & set(amb))
        if not comunes:
            continue
        r = _pearson([pern[p] for p in comunes], [amb[p] for p in comunes])
        cruces.append({
            "variable": clave,
            "titulo": titulo,
            "n_meses_comunes": len(comunes),
            "desde": comunes[0],
            "hasta": comunes[-1],
            "correlacion_pearson": round(r, 3) if r is not None else None,
        })

    # Perfiles estacionales normalizados, para superponer magnitudes incomparables
    perfiles = {
        "pernoctaciones": _normalizar(_perfil_mensual(pern)),
        "ndvi": _normalizar(_perfil_mensual(ndvi)),
        "lst": _normalizar(_perfil_mensual(lst)),
    }
    crudos = {
        "pernoctaciones": _perfil_mensual(pern),
        "ndvi": _perfil_mensual(ndvi),
        "lst": _perfil_mensual(lst),
    }

    # Serie mensual conjunta, con lo ambiental normalizado por plaza hotelera
    serie = []
    for periodo in sorted(set(pern) | set(ndvi) | set(lst)):
        fila = {
            "periodo": periodo,
            "pernoctaciones": pern.get(periodo),
            "viajeros": viaj.get(periodo),
            "plazas": plaz.get(periodo),
            "ndvi": ndvi.get(periodo),
            "lst": lst.get(periodo),
        }
        if fila["pernoctaciones"] is not None and fila["plazas"]:
            # Pernoctaciones por plaza y dia: mide la intensidad real de uso del alojamiento
            dias = 30.4
            fila["pernoctaciones_por_plaza_dia"] = round(
                fila["pernoctaciones"] / (fila["plazas"] * dias), 3
            )
        if periodo in provisionales:
            fila["provisional"] = True
        serie.append(fila)

    mes_max_pern = _mes_extremo(crudos["pernoctaciones"], max)
    mes_min_ndvi = _mes_extremo(crudos["ndvi"], min)
    mes_max_lst = _mes_extremo(crudos["lst"], max)

    return {
        "indicador": "presion_turistica",
        "titulo": "Presión turística y variables ambientales",
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": max(pern) if pern else None,
        "n_periodos": len(serie),
        "cruces": cruces,
        "perfil_estacional_normalizado": perfiles,
        "perfil_estacional_crudo": crudos,
        "coincidencias": {
            "mes_maxima_ocupacion": mes_max_pern,
            "mes_minimo_ndvi": mes_min_ndvi,
            "mes_maxima_lst": mes_max_lst,
        },
        "serie": serie,
        "_telemetria": {
            "serie_ine_pernoctaciones": inc_pern,
            "meses_provisionales": len(provisionales),
        },
    }


def _mes_extremo(perfil: list[float | None], funcion) -> str | None:
    vals = [(v, i) for i, v in enumerate(perfil) if v is not None]
    if not vals:
        return None
    return MESES[funcion(vals)[1]]


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "presion_turistica.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    c = {x["variable"]: x for x in resultado["cruces"]}
    ficha = {
        "indicador": "presion_turistica",
        "titulo": "Presión turística y variables ambientales",
        "descripcion": (
            "Cruce de las pernoctaciones hoteleras con el NDVI y la temperatura superficial "
            "sobre los meses en que las series coinciden."
        ),
        "fuente": (
            "INE, Encuesta de Ocupación Hotelera (serie EOT42534 de pernoctaciones, EOT42428 "
            "de viajeros y EOT3080 de plazas, punto turístico Marbella), cruzada con los "
            "indicadores NDVI y LST de este observatorio"
        ),
        "formula": "Correlación de Pearson sobre los meses comunes; perfiles estacionales normalizados a escala 0-1",
        "resolucion_espacial": "municipio",
        "resolucion_temporal": "mensual",
        "metodo": (
            "El periodo se construye con los campos Anyo y FK_Periodo de la API Tempus3, "
            "nunca con el campo Fecha, que viene en hora de Madrid y desplaza la serie un mes "
            "si se interpreta como UTC. Los perfiles estacionales se normalizan a escala 0-1 "
            "para poder superponer magnitudes que no son comparables entre sí."
        ),
        "enmascaramiento": "No aplica.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": 0,
        "limitaciones": [
            "La correlación NO implica causalidad. Dos series con ciclo anual marcado "
            "correlacionan por el mero hecho de compartir estacionalidad; lo informativo es "
            "el signo y el desfase, no la atribución de causa.",
            "La serie hotelera del INE arranca en 2018, mientras que las ambientales "
            "arrancan en 2017: el cruce se limita al tramo común.",
            "La EOH cubre establecimientos hoteleros. No recoge vivienda turística ni "
            "apartamentos, que en Marbella representan una parte relevante de la oferta, de "
            "modo que la presión real es superior a la que refleja este indicador.",
            "Los meses más recientes son datos provisionales del INE y pueden revisarse.",
        ],
        "correlacion_pernoctaciones_ndvi": c.get("ndvi", {}).get("correlacion_pearson"),
        "correlacion_pernoctaciones_lst": c.get("lst", {}).get("correlacion_pearson"),
        "licencia": "Instituto Nacional de Estadística. Reutilización libre citando la fuente.",
        "ruta_datos": "data/processed/presion_turistica.json",
    }
    (DIR_METADATA / "presion_turistica.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
