"""Indicador de dioxido de nitrogeno troposferico, serie mensual.

Fuente: Sentinel-5P nivel 2, banda NO2 (columna troposferica), via Sentinel Hub.

Advertencia esencial sobre la escala: el pixel de Sentinel-5P mide del orden de 5,5 x 3,5 km.
Sobre los 117 km2 del termino caben apenas una veintena de valores, y la huella de cada uno
desborda ampliamente el municipio. La serie es por tanto util para leer TENDENCIA y
ESTACIONALIDAD de ambito comarcal, y NO admite lectura municipal fina ni representacion
cartografica por barrios. Asi consta en la ficha del indicador.
"""

from __future__ import annotations

import json
from datetime import date

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import copernicus_sh as sh

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["NO2", "dataMask"]}],
    output: [
      {id: "indice", bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  var v = s.NO2;
  var m = s.dataMask;
  // Los valores no finitos abortan la peticion entera: ese pixel se descarta
  if (!isFinite(v)) { v = 0.0; m = 0; }
  return {indice: [v], dataMask: [m]};
}"""


def construir_serie(cfg: dict, forzar: bool = False) -> dict:
    ind = cfg["indicadores"]["no2_troposferico"]
    epsg = cfg["crs"]["peticion_sh"]
    geometria = sh.geometria_para_peticion(
        DIR_PROCESSED / "limite_municipal.geojson", epsg,
        cfg["geometria"]["tolerancia_simplificacion_m"],
    )
    hoy = date.today()
    cache_dir = DIR_RAW / "sh_statistics"
    cache_dir.mkdir(parents=True, exist_ok=True)

    intervalos, pu_total, anios = [], 0.0, []
    # Sentinel-5P empieza a dar producto util a finales de 2018
    for anio in range(max(2019, int(cfg["serie"]["fecha_inicio"][:4])), hoy.year + 1):
        cache = cache_dir / f"no2_{anio}.json"
        if cache.exists() and anio < hoy.year and not forzar:
            datos = json.loads(cache.read_text(encoding="utf-8"))
        else:
            hasta = f"{anio + 1}-01-01" if anio < hoy.year else hoy.isoformat()
            datos, pu = sh.pedir_estadistica(
                geometria=geometria, epsg_peticion=epsg, coleccion="sentinel-5p-l2",
                evalscript=EVALSCRIPT, desde=f"{anio}-01-01", hasta=hasta,
                intervalo="P1M", resolucion_m=ind["resolucion_m"],
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
        validos = st["sampleCount"] - st["noDataCount"]
        mediana = st.get("percentiles", {}).get("50.0", media)
        if not isinstance(mediana, (int, float)):
            mediana = media
        # Se publica en micromol/m2 para que la cifra sea legible
        serie.append({
            "periodo": periodo,
            "valor": round(media * 1e6, 2),
            "mediana": round(mediana * 1e6, 2),
            "pixeles_validos": validos,
        })

    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": "no2_troposferico",
        "titulo": "Dióxido de nitrógeno troposférico",
        "unidad": "µmol/m²",
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


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "no2_troposferico.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    pix = [r.get("pixeles_validos") for r in con_dato if r.get("pixeles_validos")]
    ficha = {
        "indicador": "no2_troposferico",
        "titulo": "Dióxido de nitrógeno troposférico",
        "descripcion": (
            "Columna troposférica de NO₂ sobre el término municipal, a partir de Sentinel-5P."
        ),
        "fuente": "Copernicus Sentinel-5P Nivel 2, banda NO2, vía Sentinel Hub (CDSE)",
        "formula": "Media zonal de la columna troposférica de NO₂, expresada en µmol/m²",
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
            f"caben del orden de {int(sum(pix) / len(pix)) if pix else 20} valores, y la "
            "huella de cada uno desborda el término. **La serie describe tendencia y "
            "estacionalidad de ámbito comarcal, no la calidad del aire de un punto concreto "
            "de Marbella.**",
            "No es representable como mapa municipal ni por barrios.",
            "La serie arranca en 2019: Sentinel-5P no ofrece producto consolidado antes.",
            "Los meses sin observación válida se publican como hueco. No se interpolan.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos Copernicus modificados",
        "ruta_datos": "data/processed/no2_troposferico.json",
    }
    (DIR_METADATA / "no2_troposferico.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
