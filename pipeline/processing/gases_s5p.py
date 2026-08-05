"""Gases y aerosoles atmosfericos de Sentinel-5P, series mensuales.

Todos los productos comparten la misma forma: una banda unica que se promedia sobre el
termino municipal. Solo cambian la banda, el factor de escala y la unidad de publicacion.

ADVERTENCIA COMUN A TODOS ELLOS, que se repite en cada ficha: el pixel de Sentinel-5P mide
del orden de 5,5 x 3,5 km. Sobre los 117 km2 del termino caben menos de veinte valores y la
huella de cada uno desborda ampliamente el municipio. Estas series describen TENDENCIA y
ESTACIONALIDAD de ambito comarcal. No son la calidad del aire de un punto concreto de
Marbella y no admiten representacion por barrios.
"""

from __future__ import annotations

import json
from datetime import date

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import copernicus_sh as sh

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["%s", "dataMask"]}],
    output: [
      {id: "indice", bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  var v = s.%s;
  var m = s.dataMask;
  // Los valores no finitos abortan la peticion entera: ese pixel se descarta
  if (!isFinite(v)) { v = 0.0; m = 0; }
  return {indice: [v], dataMask: [m]};
}"""


def construir_serie(cfg: dict, clave: str, forzar: bool = False) -> dict:
    ind = cfg["indicadores"][clave]
    banda = ind["banda"]
    factor = float(ind.get("factor_escala", 1))
    epsg = cfg["crs"]["peticion_sh"]

    geometria = sh.geometria_para_peticion(
        DIR_PROCESSED / "limite_municipal.geojson", epsg,
        cfg["geometria"]["tolerancia_simplificacion_m"],
    )
    hoy = date.today()
    cache_dir = DIR_RAW / "sh_statistics"
    cache_dir.mkdir(parents=True, exist_ok=True)
    script = EVALSCRIPT % (banda, banda)

    intervalos, pu_total, anios = [], 0.0, []
    # Sentinel-5P no ofrece producto consolidado antes de 2019
    for anio in range(max(2019, int(cfg["serie"]["fecha_inicio"][:4])), hoy.year + 1):
        cache = cache_dir / f"{clave}_{anio}.json"
        if cache.exists() and anio < hoy.year and not forzar:
            datos = json.loads(cache.read_text(encoding="utf-8"))
        else:
            hasta = f"{anio + 1}-01-01" if anio < hoy.year else hoy.isoformat()
            datos, pu = sh.pedir_estadistica(
                geometria=geometria, epsg_peticion=epsg, coleccion="sentinel-5p-l2",
                evalscript=script, desde=f"{anio}-01-01", hasta=hasta,
                intervalo="P1M", resolucion_m=ind.get("resolucion_m", 3500),
                mosaico="mostRecent", salida_id="indice",
            )
            cache.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            pu_total += pu
            anios.append(anio)
        intervalos.extend(datos.get("data", []))

    serie = []
    for it in sorted(intervalos, key=lambda x: x["interval"]["from"]):
        periodo = it["interval"]["from"][:7]
        if "outputs" not in it:
            serie.append({"periodo": periodo, "valor": None,
                          "motivo": "sin observación válida en el mes"})
            continue
        st = it["outputs"]["indice"]["bands"]["B0"]["stats"]
        media = st.get("mean")
        # Sentinel Hub devuelve la cadena "NaN" cuando el mes no deja ningun pixel valido
        if not isinstance(media, (int, float)):
            serie.append({"periodo": periodo, "valor": None,
                          "motivo": "sin píxel válido en el mes"})
            continue
        mediana = st.get("percentiles", {}).get("50.0", media)
        if not isinstance(mediana, (int, float)):
            mediana = media
        serie.append({
            "periodo": periodo,
            "valor": round(media * factor, 3),
            "mediana": round(mediana * factor, 3),
            "pixeles_validos": st["sampleCount"] - st["noDataCount"],
        })

    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": clave,
        "titulo": ind["titulo"],
        "unidad": ind["unidad"],
        "unidad_analisis": "municipio (lectura de ámbito comarcal)",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": con_dato[-1]["periodo"] if con_dato else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "serie": serie,
        "_telemetria": {"pu_consumidas": round(pu_total, 3), "anios_descargados": anios},
    }


def escribir(resultado: dict, cfg: dict, clave: str) -> None:
    ind = cfg["indicadores"][clave]
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / f"{clave}.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    pix = [r.get("pixeles_validos") for r in con_dato if r.get("pixeles_validos")]
    ficha = {
        "indicador": clave,
        "titulo": ind["titulo"],
        "descripcion": ind["descripcion"],
        "fuente": f"Copernicus Sentinel-5P Nivel 2, banda {ind['banda']}, vía Sentinel Hub (CDSE)",
        "formula": f"Media zonal de {ind['banda']} sobre el término, expresada en {ind['unidad']}",
        "resolucion_espacial": "aproximadamente 5,5 × 3,5 km",
        "resolucion_temporal": "mensual",
        "metodo": "Agregación zonal en servidor sobre el polígono municipal.",
        "enmascaramiento": "El producto de nivel 2 incorpora sus propios filtros de calidad.",
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "La resolución del sensor es muy inferior al tamaño del municipio: sobre 117 km² "
            f"caben del orden de {int(sum(pix) / len(pix)) if pix else 18} valores, y la "
            "huella de cada uno desborda el término. La serie describe tendencia y "
            "estacionalidad de ámbito comarcal, no la calidad del aire de un punto concreto.",
            "No es representable como mapa municipal ni por barrios.",
            "La serie arranca en 2019: Sentinel-5P no ofrece producto consolidado antes.",
            "Los meses sin observación válida se publican como hueco. No se interpolan.",
        ] + ind.get("limitaciones_extra", []),
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos modificados de Copernicus Sentinel",
        "ruta_datos": f"data/processed/{clave}.json",
    }
    (DIR_METADATA / f"{clave}.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
