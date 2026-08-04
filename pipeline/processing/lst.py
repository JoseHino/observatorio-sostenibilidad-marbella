"""Indicador de temperatura superficial terrestre (LST) media municipal, serie mensual.

Fuente: Landsat 8 y 9, coleccion 2 nivel 2, banda ST_B10 (temperatura superficial corregida
por emisividad por el USGS). Rejilla de 30 m.

Enmascaramiento: banda QA_PIXEL. Se exige el bit 6 (pixel despejado) y se excluye el bit 7
(agua), de modo que la LST publicada es terrestre. Una escena cuya cobertura valida sobre el
municipio no alcance el umbral se descarta entera: en una escena medio nublada, los pixeles
que sobreviven no son una muestra representativa del municipio, sino los claros entre nubes.

El valor mensual es la media de las escenas validas del mes. Los meses sin ninguna escena
valida se publican como hueco explicito. No se interpolan.

Observacion importante para la lectura: Landsat sobrevuela hacia las 11:00 hora local. La
serie describe por tanto la temperatura superficial de media manana, no la maxima diaria ni
la temperatura del aire, que es sensiblemente inferior.
"""

from __future__ import annotations

import json
from datetime import date

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import landsat_pc as lsat

# Por debajo de esta cobertura valida, la escena no representa al municipio y se descarta
UMBRAL_COBERTURA_ESCENA = 70.0

# Amplitud minima entre percentiles dentro de una escena. Sobre 117 km2 con 1.200 m de
# desnivel, una superficie real SIEMPRE presenta varianza espacial. Una escena sin ella no
# es una medida: es un fichero relleno con un valor constante. Se ha observado al menos un
# caso real (2024-10-11) enteramente a 150,0 K, que es el fondo del rango valido de ST_B10.
# Este criterio descarta el fichero completo; no recorta la distribucion de una escena buena.
AMPLITUD_MINIMA_ESCENA = 1.0

# Recorrido fisicamente admisible para la mediana de una escena en el litoral mediterraneo.
# Solo sirve para detectar productos corruptos o errores de escalado, no para acotar el clima.
LST_MIN_ADMISIBLE, LST_MAX_ADMISIBLE = -10.0, 70.0


def escena_utilizable(r: dict) -> tuple[bool, str]:
    """Decide si una escena entra en la serie, y por que no si no entra."""
    if r.get("error"):
        return False, r["error"]
    if "lst_media" not in r:
        return False, "sin píxeles válidos"
    if r.get("cobertura_pct", 0) < UMBRAL_COBERTURA_ESCENA:
        return False, "cobertura insuficiente"
    if r.get("amplitud_p10_p90", 0) < AMPLITUD_MINIMA_ESCENA:
        return False, "escena degenerada: sin varianza espacial"
    if not LST_MIN_ADMISIBLE <= r.get("lst_mediana", 0) <= LST_MAX_ADMISIBLE:
        return False, "valor fuera del recorrido físicamente admisible"
    return True, ""


def _cache_escena(id_escena: str):
    return DIR_RAW / "landsat" / f"{id_escena}.json"


def construir_serie(cfg: dict, forzar: bool = False) -> dict:
    ind = cfg["indicadores"]["lst_municipal"]
    ruta_limite = DIR_PROCESSED / "limite_municipal.geojson"
    limite = gpd.read_file(ruta_limite)
    bbox = [float(v) for v in limite.total_bounds]

    (DIR_RAW / "landsat").mkdir(parents=True, exist_ok=True)

    hoy = date.today()
    desde = f"{cfg['serie']['fecha_inicio']}-01"
    escenas = lsat.buscar_escenas(bbox, desde, hoy.isoformat(), limite=2000)

    registros, leidas, reutilizadas, fallidas = [], 0, 0, 0
    for e in escenas:
        cache = _cache_escena(e["id"])
        if cache.exists() and not forzar:
            registros.append(json.loads(cache.read_text(encoding="utf-8")))
            reutilizadas += 1
            continue
        st = lsat.estadisticas_escena(e, limite)
        cache.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        registros.append(st)
        if st.get("error"):
            fallidas += 1
        else:
            leidas += 1

    serie = _componer(registros)
    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": "lst_municipal",
        "titulo": "Temperatura superficial terrestre media municipal",
        "unidad": "grados Celsius",
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": con_dato[-1]["periodo"] if con_dato else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "resolucion_m": 30,
        "hora_paso": "hacia las 11:00 hora local",
        "serie": serie,
        "_telemetria": {
            "escenas_totales": len(escenas),
            "escenas_leidas": leidas,
            "escenas_reutilizadas": reutilizadas,
            "escenas_fallidas": fallidas,
            "escenas_descartadas": sum(1 for r in registros if not escena_utilizable(r)[0]),
            "motivos_descarte": _resumen_motivos(registros),
        },
    }


def _resumen_motivos(registros: list[dict]) -> dict:
    """Recuento por motivo de descarte. Ningun recorte de cobertura queda sin declarar."""
    conteo: dict[str, int] = {}
    for r in registros:
        ok, motivo = escena_utilizable(r)
        if not ok:
            clave = motivo.split(":")[0][:60]
            conteo[clave] = conteo.get(clave, 0) + 1
    return dict(sorted(conteo.items(), key=lambda x: -x[1]))


def _componer(registros: list[dict]) -> list[dict]:
    """Agrupa las escenas validas por mes. Los meses sin escena valida quedan como hueco."""
    validas: dict[str, list[dict]] = {}
    descartadas: dict[str, int] = {}
    motivos: dict[str, set] = {}
    for r in registros:
        periodo = r["fecha"][:7]
        ok, motivo = escena_utilizable(r)
        if ok:
            validas.setdefault(periodo, []).append(r)
        else:
            descartadas[periodo] = descartadas.get(periodo, 0) + 1
            motivos.setdefault(periodo, set()).add(motivo)

    periodos = sorted(set(validas) | set(descartadas))
    if not periodos:
        return []

    # Se recorre el calendario completo para que los meses sin ninguna escena tambien
    # aparezcan como hueco, y no simplemente falten de la serie
    ini_a, ini_m = int(periodos[0][:4]), int(periodos[0][5:7])
    fin_a, fin_m = int(periodos[-1][:4]), int(periodos[-1][5:7])
    salida = []
    a, m = ini_a, ini_m
    while (a, m) <= (fin_a, fin_m):
        p = f"{a:04d}-{m:02d}"
        lote = validas.get(p, [])
        if lote:
            n = len(lote)
            p10 = round(sum(x["lst_p10"] for x in lote) / n, 2)
            p90 = round(sum(x["lst_p90"] for x in lote) / n, 2)
            salida.append({
                "periodo": p,
                "valor": round(sum(x["lst_media"] for x in lote) / n, 2),
                "mediana": round(sum(x["lst_mediana"] for x in lote) / n, 2),
                "p10": p10,
                "p90": p90,
                # Se deriva de los percentiles ya publicados, no del promedio de las
                # amplitudes por escena: promediar valores previamente redondeados hacia
                # deriva de centesimas entre maquinas y provocaba commits sin dato nuevo.
                "amplitud_p10_p90": round(p90 - p10, 2),
                "n_escenas": n,
                "cobertura_pct": round(sum(x["cobertura_pct"] for x in lote) / n, 1),
                "escenas_descartadas": descartadas.get(p, 0),
            })
        else:
            salida.append({
                "periodo": p,
                "valor": None,
                "motivo": (
                    f"sin escena válida: {descartadas.get(p, 0)} descartada(s) por "
                    + ", ".join(sorted(motivos.get(p, {"causa no registrada"})))
                    if descartadas.get(p) else "sin paso de satélite utilizable en el mes"
                ),
            })
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return salida


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "lst_municipal.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    ficha = {
        "indicador": "lst_municipal",
        "titulo": "Temperatura superficial terrestre media municipal",
        "descripcion": (
            "Temperatura de la superficie del terreno promediada sobre el término municipal, "
            "a partir de los pasos de Landsat 8 y 9. No es temperatura del aire."
        ),
        "fuente": "USGS Landsat 8/9 Collection 2 Level-2, banda ST_B10, vía Microsoft Planetary Computer",
        "formula": "LST (°C) = ST_B10 × 0,00341802 + 149,0 − 273,15",
        "resolucion_espacial": "30 m",
        "resolucion_temporal": "mensual (media de las escenas válidas del mes)",
        "hora_de_paso": "hacia las 11:00 hora local",
        "metodo": (
            "Lectura por ventana del polígono municipal sobre los ficheros COG mediante "
            "peticiones de rango HTTP; no se descargan las escenas completas. Estadística "
            "zonal calculada en local."
        ),
        "enmascaramiento": (
            "Banda QA_PIXEL. Se exige el bit 6 (píxel despejado: sin nube, nube dilatada, "
            "cirro ni sombra) y se excluye el bit 7 (agua). Las escenas cuya cobertura válida "
            f"sobre el municipio no alcanza el {UMBRAL_COBERTURA_ESCENA:.0f}% se descartan "
            "enteras, porque los píxeles que sobreviven en una escena medio nublada no son "
            "una muestra representativa del término."
        ),
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "Es temperatura de la superficie, no del aire: en verano la supera con holgura.",
            "Corresponde al paso de media mañana, no a la máxima diaria.",
            "La media municipal enmascara el gradiente entre la costa y Sierra Blanca; su "
            "lectura exige estratificación por altitud, aún pendiente.",
            "Los meses sin escena válida se publican como hueco. No se interpolan.",
            "La nubosidad invernal reduce el número de escenas útiles, por lo que los meses "
            "de invierno se apoyan en menos observaciones que los de verano.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Datos Landsat de dominio público (USGS). Distribución vía Microsoft Planetary Computer.",
        "ruta_datos": "data/processed/lst_municipal.json",
    }
    (DIR_METADATA / "lst_municipal.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
