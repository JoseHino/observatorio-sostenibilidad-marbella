"""Indices normalizados de Sentinel-2, agregados sobre el termino municipal.

Todos los indices publicados tienen la misma forma, una diferencia normalizada entre dos
bandas, y solo cambian las bandas y las clases de la mascara SCL:

    indice = (A - B) / (A + B)

    NDVI  (vegetacion)          A=B08 (infrarrojo cercano)  B=B04 (rojo)
    NDBI  (superficie contruida) A=B11 (infrarrojo de onda corta) B=B08

La mascara tambien depende del indice: para vegetacion y superficie construida se excluye el
agua, porque falsearia la media; un indice de agua, en cambio, tendria que incluirla.

El valor mensual es un COMPUESTO: con mosaickingOrder leastCC el servicio elige para cada
pixel la observacion menos nubosa del mes. No es una observacion de fecha unica.

Los meses sin observacion valida se publican como hueco explicito. No se interpolan.
"""

from __future__ import annotations

import json
from datetime import date

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import copernicus_sh as sh

# Por debajo de este porcentaje de superficie municipal observada, el mes se marca como
# de cobertura baja. No se elimina: se publica con la advertencia.
UMBRAL_COBERTURA_BAJA = 70.0


def evalscript(banda_a: str, banda_b: str, scl_validas: list[int]) -> str:
    """Evalscript de diferencia normalizada con mascara SCL.

    El denominador nulo genera NaN y aborta la peticion entera: ese pixel se descarta.
    """
    condicion = " || ".join(f"s.SCL == {c}" for c in scl_validas)
    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{bands: ["{banda_a}", "{banda_b}", "SCL", "dataMask"]}}],
    output: [
      {{id: "indice", bands: 1, sampleType: "FLOAT32"}},
      {{id: "dataMask", bands: 1}}
    ]
  }};
}}
function evaluatePixel(s) {{
  var valid = ({condicion}) ? 1 : 0;
  var den = s.{banda_a} + s.{banda_b};
  var v = 0.0;
  if (den > 0) {{ v = (s.{banda_a} - s.{banda_b}) / den; }} else {{ valid = 0; }}
  if (!isFinite(v)) {{ v = 0.0; valid = 0; }}
  return {{indice: [v], dataMask: [s.dataMask * valid]}};
}}"""


def construir_serie(cfg: dict, clave: str, forzar: bool = False) -> dict:
    ind = cfg["indicadores"][clave]
    crs = cfg["crs"]
    epsg_peticion = crs["peticion_sh"]
    resolucion = ind["resolucion_m"]
    banda_a, banda_b = ind["bandas_indice"]

    ruta_limite = DIR_PROCESSED / "limite_municipal.geojson"
    geometria = sh.geometria_para_peticion(
        ruta_limite, epsg_peticion, cfg["geometria"]["tolerancia_simplificacion_m"]
    )
    superficie_m2 = gpd.read_file(ruta_limite).to_crs(crs["calculo"]).geometry.area.sum()
    pixeles_teoricos = superficie_m2 / (resolucion**2)

    hoy = date.today()
    cache_dir = DIR_RAW / "sh_statistics"
    cache_dir.mkdir(parents=True, exist_ok=True)
    script = evalscript(banda_a, banda_b, ind["scl_validas"])

    intervalos, pu_total, anios = [], 0.0, []
    for anio in range(int(cfg["serie"]["fecha_inicio"][:4]), hoy.year + 1):
        cache = cache_dir / f"{clave}_{anio}_{resolucion}m.json"
        # Los anios cerrados no cambian: se reutiliza la cache y no se gasta cuota.
        # El anio en curso se vuelve a pedir siempre porque puede traer meses nuevos.
        if cache.exists() and anio < hoy.year and not forzar:
            datos = json.loads(cache.read_text(encoding="utf-8"))
        else:
            hasta = f"{anio + 1}-01-01" if anio < hoy.year else hoy.isoformat()
            datos, pu = sh.pedir_estadistica(
                geometria=geometria, epsg_peticion=epsg_peticion,
                coleccion=ind["coleccion"], evalscript=script,
                desde=f"{anio}-01-01", hasta=hasta, intervalo=ind["intervalo"],
                resolucion_m=resolucion, mosaico=ind["mosaico"], salida_id="indice",
            )
            cache.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            pu_total += pu
            anios.append(anio)
        intervalos.extend(datos.get("data", []))

    serie = _componer(intervalos, pixeles_teoricos)
    con_dato = [r for r in serie if r["valor"] is not None]
    return {
        "indicador": clave,
        "titulo": ind["titulo"],
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": con_dato[-1]["periodo"] if con_dato else None,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "pixeles_teoricos": int(pixeles_teoricos),
        "resolucion_m": resolucion,
        "serie": serie,
        "_telemetria": {"pu_consumidas": round(pu_total, 1), "anios_descargados": anios},
    }


def _componer(intervalos: list[dict], pixeles_teoricos: float) -> list[dict]:
    por_periodo: dict[str, dict] = {}
    for it in intervalos:
        periodo = it["interval"]["from"][:7]
        if "outputs" not in it:
            por_periodo.setdefault(periodo, {
                "periodo": periodo, "valor": None,
                "motivo": "sin observación válida en el mes"})
            continue
        st = it["outputs"]["indice"]["bands"]["B0"]["stats"]
        validos = st["sampleCount"] - st["noDataCount"]
        cobertura = round(100 * validos / pixeles_teoricos, 1) if pixeles_teoricos else None
        pc = st.get("percentiles", {})
        registro = {
            "periodo": periodo,
            "valor": round(st["mean"], 4),
            "mediana": round(pc.get("50.0", st["mean"]), 4),
            "p25": round(pc.get("25.0", st["mean"]), 4),
            "p75": round(pc.get("75.0", st["mean"]), 4),
            "desviacion": round(st["stDev"], 4),
            "pixeles_validos": validos,
            "cobertura_pct": cobertura,
        }
        if cobertura is not None and cobertura < UMBRAL_COBERTURA_BAJA:
            registro["aviso"] = "cobertura baja: dato menos representativo"
        por_periodo[periodo] = registro
    return [por_periodo[k] for k in sorted(por_periodo)]


def escribir(resultado: dict, cfg: dict, clave: str) -> None:
    ind = cfg["indicadores"][clave]
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / f"{clave}.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    a, b = ind["bandas_indice"]
    ficha = {
        "indicador": clave,
        "titulo": ind["titulo"],
        "descripcion": ind["descripcion"],
        "fuente": "Copernicus Sentinel-2 L2A vía Sentinel Hub Statistical API (CDSE)",
        "formula": f"({a} − {b}) / ({a} + {b})",
        "resolucion_espacial": f"{ind['resolucion_m']} m",
        "resolucion_temporal": "mensual (compuesto)",
        "metodo": (
            "Agregación zonal en servidor sobre el polígono municipal. Mosaico mensual con "
            "criterio leastCC: para cada píxel se toma la observación menos nubosa del mes."
        ),
        "enmascaramiento": (
            "Banda SCL del producto L2A. Clases válidas: "
            + ", ".join(str(c) for c in ind["scl_validas"])
            + ". Se excluyen nubes, cirros, sombras, nieve y saturados."
        ),
        "epsg_peticion": cfg["crs"]["peticion_sh"],
        "epsg_calculo": cfg["crs"]["calculo"],
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": ind["limitaciones"],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos Copernicus modificados",
        "ruta_datos": f"data/processed/{clave}.json",
    }
    (DIR_METADATA / f"{clave}.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
