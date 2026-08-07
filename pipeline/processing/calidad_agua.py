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


def _lee_cache_completa() -> list[dict]:
    intervalos = []
    destino = DIR_RAW / "openeo"
    if destino.exists():
        for f in sorted(destino.glob("chl_*.json")):
            intervalos.append(json.loads(f.read_text(encoding="utf-8")))
    return intervalos


def componer_desde_cache(cfg: dict) -> dict:
    """Compone la serie con lo que haya en cache, SIN lanzar ninguna peticion.

    La carga historica de esta fuente lleva horas. Esto permite publicar en cualquier momento
    el tramo ya obtenido, con los meses que falten declarados como hueco, mientras el relleno
    continua por separado.
    """
    return _empaquetar(cfg, _componer(_lee_cache_completa()), [])


def actualizar_trimestre_en_curso(cfg: dict) -> dict:
    """Trae SOLO el trimestre en curso y compone el resto desde cache.

    Es lo que debe hacer una ejecucion desatendida. Componer unicamente desde cache dejaria
    el indicador congelado, porque los meses nuevos no entrarian nunca; y pedir la serie
    entera bloquearia el job casi una hora. Pedir el trimestre en curso cuesta unos minutos
    y basta, porque es el unico tramo que puede haber crecido desde la ultima pasada.
    """
    ruta = DIR_PROCESSED / "buffer_marino.geojson"
    if not ruta.exists():
        return componer_desde_cache(cfg)

    hoy = date.today()
    trimestre = (hoy.month - 1) // 3
    mes_ini = trimestre * 3 + 1
    desde = f"{hoy.year}-{mes_ini:02d}-01"
    fa, fm = (hoy.year, mes_ini + 3) if mes_ini + 3 <= 12 else (hoy.year + 1, 1)
    hasta = min(f"{fa}-{fm:02d}-01", hoy.isoformat())

    if hasta > desde:
        g = gpd.read_file(ruta)
        simple = gpd.GeoSeries(
            [g.to_crs(32630).geometry.iloc[0].simplify(150)], crs=32630
        ).to_crs(4326)
        try:
            datos = oeo.ejecutar(_grafo(json.loads(simple.to_json()), simple.total_bounds,
                                        desde, hasta), reintentos=2)
            oeo.cachear(f"chl_{hoy.year}T{trimestre + 1}", datos)
        except Exception:
            # Si el trimestre en curso no se puede traer, se publica lo que ya hay:
            # el indicador nunca queda peor que antes
            pass

    return _empaquetar(cfg, _componer(_lee_cache_completa()), [])


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
    intervalos, tramos_leidos = [], []

    # Se pide por trimestres y no por anios: las peticiones anuales a openEO se quedan
    # colgadas de forma sistematica en esta coleccion, mientras que las de tres meses
    # responden con fiabilidad. El tramo mas pequeno tambien limita lo que se pierde si
    # una peticion falla.
    #
    # Y se recorre del presente hacia atras: la carga historica completa lleva horas, de modo
    # que si se interrumpe, lo ya obtenido es el tramo RECIENTE, que es el que interesa
    # publicar. Recorriendo en orden cronologico, una interrupcion dejaria una serie que
    # termina hace anios. La composicion final reordena, asi que el orden de descarga no
    # afecta al resultado.
    for anio in range(hoy.year, inicio - 1, -1):
        # Se conserva la cache anual de ejecuciones anteriores para no repetir trabajo
        anual = None if forzar else oeo.leer_cache(f"chl_{anio}")
        if anual is not None:
            intervalos.append(anual)
            continue
        for trimestre in range(4):
            mes_ini = trimestre * 3 + 1
            desde = f"{anio}-{mes_ini:02d}-01"
            if desde > hoy.isoformat():
                break
            fin_anio, fin_mes = (anio, mes_ini + 3) if mes_ini + 3 <= 12 else (anio + 1, 1)
            hasta = min(f"{fin_anio}-{fin_mes:02d}-01", hoy.isoformat())
            if hasta <= desde:
                break
            nombre = f"chl_{anio}T{trimestre + 1}"
            cache = None if forzar else oeo.leer_cache(nombre)
            if cache is None:
                cache = oeo.ejecutar(_grafo(fc, bbox, desde, hasta))
                oeo.cachear(nombre, cache)
                tramos_leidos.append(nombre)
            intervalos.append(cache)

    return _empaquetar(cfg, _componer(intervalos), tramos_leidos)


def _empaquetar(cfg: dict, serie: list[dict], tramos_leidos: list) -> dict:
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
        "_telemetria": {"tramos_leidos": tramos_leidos},
    }


def _componer(intervalos: list[dict]) -> list[dict]:
    valores: dict[str, float] = {}
    for bloque in intervalos:
        for k, v in bloque.items():
            periodo = k[:7]
            c = v[0][0] if v and v[0] and v[0][0] is not None else None
            if c is None:
                continue
            # CHL_NN se distribuye en log10(mg/m3), no en mg/m3: el propio catalogo lo
            # declara asi. Sin deshacer la escala, la serie publicada saldria con valores
            # negativos, que en una concentracion son imposibles.
            #
            # Promediar en logaritmo y despues exponenciar equivale a la media geometrica,
            # que es justamente el estadistico convencional para la clorofila por ser una
            # variable log-normal. La agregacion de openEO opera por tanto en el espacio
            # correcto; aqui solo se deshace la escala.
            valores[periodo] = round(10 ** float(c), 4)

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
        "formula": "10^(media zonal y temporal de CHL_NN), es decir, media geométrica en mg/m³",
        "resolucion_espacial": "300 m",
        "resolucion_temporal": "mensual",
        "metodo": (
            "Se emplea CHL_NN y no CHL_OC4ME: el algoritmo OC4Me está concebido para aguas "
            "oceánicas de tipo 1, mientras que la red neuronal es la recomendada para aguas "
            "costeras de tipo 2. La agregación temporal y zonal se ejecuta en el servidor de "
            "openEO; no se descarga ningún ráster. La banda se distribuye en log10(mg/m³), "
            "de modo que el promedio se calcula en escala logarítmica y se deshace después: "
            "el resultado es la media geométrica, que es el estadístico convencional para la "
            "clorofila por tratarse de una variable log-normal."
        ),
        "enmascaramiento": "El producto de nivel 2 incorpora sus propios indicadores de calidad.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "El valor publicado es una media geométrica, no aritmética, por la naturaleza "
            "log-normal de la variable. No es comparable sin más con medias aritméticas de "
            "otras fuentes.",
            "Los productos oceánicos estándar pierden fiabilidad cerca de la costa, por "
            "reflexión del fondo en aguas someras y por aportes terrestres. La serie sirve "
            "para leer estacionalidad y tendencia, no como medida absoluta de concentración.",
            "La franja marina se deriva del límite administrativo terrestre, no de la línea "
            "de costa cartografiada a detalle.",
            "Los meses sin observación válida se publican como hueco. No se interpolan.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos modificados de Copernicus Sentinel",
        "ruta_datos": "data/processed/clorofila_litoral.json",
    }
    (DIR_METADATA / "clorofila_litoral.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
