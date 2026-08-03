"""Indicador NDVI medio municipal, serie mensual.

NDVI = (B08 - B04) / (B08 + B04) sobre Sentinel-2 L2A.

Enmascaramiento con la banda de clasificacion de escena (SCL): se consideran validas las
clases 4 (vegetacion), 5 (suelo desnudo) y 7 (sin clasificar). Se excluyen nubes, cirros,
sombras de nube, agua, nieve y pixeles saturados.

El valor mensual es un COMPUESTO: con mosaickingOrder leastCC el servicio elige para cada
pixel la observacion menos nubosa del mes. No es una observacion de fecha unica.

Los meses sin observacion valida se publican como hueco explicito (valor null). No se
interpolan bajo ninguna circunstancia.
"""

from __future__ import annotations

import json
from datetime import date

import geopandas as gpd

from config import DIR_METADATA, DIR_PROCESSED, DIR_RAW
from sources import copernicus_sh as sh

# El denominador nulo genera NaN y aborta la peticion entera: ese pixel se descarta
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04", "B08", "SCL", "dataMask"]}],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  var valid = (s.SCL == 4 || s.SCL == 5 || s.SCL == 7) ? 1 : 0;
  var den = s.B08 + s.B04;
  var ndvi = 0.0;
  if (den > 0) { ndvi = (s.B08 - s.B04) / den; } else { valid = 0; }
  if (!isFinite(ndvi)) { ndvi = 0.0; valid = 0; }
  return {ndvi: [ndvi], dataMask: [s.dataMask * valid]};
}"""

# Por debajo de este porcentaje de superficie municipal observada, el mes se marca como
# de cobertura baja. No se elimina: se publica con la advertencia.
UMBRAL_COBERTURA_BAJA = 70.0


def _anios(desde: str, hasta: date) -> list[int]:
    return list(range(int(desde[:4]), hasta.year + 1))


def construir_serie(cfg: dict, forzar: bool = False) -> dict:
    """Descarga (o reutiliza cache) y compone la serie NDVI mensual. Devuelve el resultado."""
    ind = cfg["indicadores"]["ndvi_municipal"]
    crs = cfg["crs"]
    epsg_peticion = crs["peticion_sh"]
    resolucion = ind["resolucion_m"]

    ruta_limite = DIR_PROCESSED / "limite_municipal.geojson"
    geometria = sh.geometria_para_peticion(
        ruta_limite, epsg_peticion, cfg["geometria"]["tolerancia_simplificacion_m"]
    )

    # Pixeles teoricos que caben en el municipio: sirve para expresar la cobertura mensual
    superficie_m2 = gpd.read_file(ruta_limite).to_crs(crs["calculo"]).geometry.area.sum()
    pixeles_teoricos = superficie_m2 / (resolucion**2)

    hoy = date.today()
    cache_dir = DIR_RAW / "sh_statistics"
    cache_dir.mkdir(parents=True, exist_ok=True)

    intervalos: list[dict] = []
    pu_total = 0.0
    anios_descargados: list[int] = []

    for anio in _anios(cfg["serie"]["fecha_inicio"], hoy):
        cache = cache_dir / f"ndvi_{anio}_{resolucion}m.json"
        # Los anios ya cerrados no cambian: se reutiliza la cache y no se gasta cuota.
        # El anio en curso siempre se vuelve a pedir porque puede tener meses nuevos.
        reutilizable = cache.exists() and anio < hoy.year and not forzar
        if reutilizable:
            datos = json.loads(cache.read_text(encoding="utf-8"))
        else:
            hasta = f"{anio + 1}-01-01" if anio < hoy.year else hoy.isoformat()
            datos, pu = sh.pedir_estadistica(
                geometria=geometria,
                epsg_peticion=epsg_peticion,
                coleccion=ind["coleccion"],
                evalscript=EVALSCRIPT,
                desde=f"{anio}-01-01",
                hasta=hasta,
                intervalo=ind["intervalo"],
                resolucion_m=resolucion,
                mosaico=ind["mosaico"],
                salida_id="ndvi",
            )
            cache.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            pu_total += pu
            anios_descargados.append(anio)
        intervalos.extend(datos.get("data", []))

    serie = _componer(intervalos, pixeles_teoricos)
    resultado = _empaquetar(cfg, serie, resolucion, pixeles_teoricos, pu_total, anios_descargados)
    return resultado


def _componer(intervalos: list[dict], pixeles_teoricos: float) -> list[dict]:
    """Convierte la respuesta cruda en serie mensual ordenada, con huecos explicitos."""
    por_periodo: dict[str, dict] = {}
    for it in intervalos:
        periodo = it["interval"]["from"][:7]
        if "outputs" not in it:
            # El servicio no devolvio estadistica para ese mes: hueco real, no se rellena
            por_periodo.setdefault(
                periodo,
                {"periodo": periodo, "valor": None, "motivo": "sin observación válida en el mes"},
            )
            continue
        st = it["outputs"]["ndvi"]["bands"]["B0"]["stats"]
        validos = st["sampleCount"] - st["noDataCount"]
        cobertura = round(100 * validos / pixeles_teoricos, 1) if pixeles_teoricos else None
        registro = {
            "periodo": periodo,
            "valor": round(st["mean"], 4),
            "mediana": round(st.get("percentiles", {}).get("50.0", st["mean"]), 4),
            "p25": round(st.get("percentiles", {}).get("25.0", st["mean"]), 4),
            "p75": round(st.get("percentiles", {}).get("75.0", st["mean"]), 4),
            "desviacion": round(st["stDev"], 4),
            "pixeles_validos": validos,
            "cobertura_pct": cobertura,
        }
        if cobertura is not None and cobertura < UMBRAL_COBERTURA_BAJA:
            registro["aviso"] = "cobertura baja: dato menos representativo"
        por_periodo[periodo] = registro
    return [por_periodo[k] for k in sorted(por_periodo)]


def _empaquetar(
    cfg: dict,
    serie: list[dict],
    resolucion: int,
    pixeles_teoricos: float,
    pu_total: float,
    anios_descargados: list[int],
) -> dict:
    con_dato = [r for r in serie if r["valor"] is not None]
    ultimo = con_dato[-1]["periodo"] if con_dato else None
    return {
        "indicador": "ndvi_municipal",
        "titulo": "NDVI medio municipal",
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "mensual",
        "ultimo_periodo": ultimo,
        "n_periodos": len(serie),
        "n_huecos": len(serie) - len(con_dato),
        "pixeles_teoricos": int(pixeles_teoricos),
        "resolucion_m": resolucion,
        "serie": serie,
        # La telemetria de ejecucion NO se publica: cambia en cada pasada y ensuciaria el
        # diff, provocando un commit aunque no haya dato nuevo. Viaja aparte.
        "_telemetria": {
            "pu_consumidas": round(pu_total, 1),
            "anios_descargados": anios_descargados,
        },
    }


def escribir(resultado: dict, cfg: dict) -> None:
    """Vuelca la serie y su ficha de metadatos."""
    ind = cfg["indicadores"]["ndvi_municipal"]
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "ndvi_municipal.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    con_dato = [r for r in resultado["serie"] if r["valor"] is not None]
    ficha = {
        "indicador": "ndvi_municipal",
        "titulo": "NDVI medio municipal",
        "descripcion": (
            "Índice de vegetación de diferencia normalizada promediado sobre el término "
            "municipal, en compuesto mensual."
        ),
        "fuente": "Copernicus Sentinel-2 L2A vía Sentinel Hub Statistical API (CDSE)",
        "formula": "NDVI = (B08 - B04) / (B08 + B04)",
        "resolucion_espacial": f"{ind['resolucion_m']} m",
        "resolucion_temporal": "mensual (compuesto)",
        "metodo": (
            "Agregación zonal en servidor sobre el polígono municipal. Mosaico mensual con "
            "criterio leastCC: para cada píxel se toma la observación menos nubosa del mes."
        ),
        "enmascaramiento": (
            "Banda SCL del producto L2A. Clases válidas: 4 vegetación, 5 suelo desnudo, "
            "7 sin clasificar. Se excluyen nubes, cirros, sombras, agua, nieve y saturados."
        ),
        "epsg_peticion": cfg["crs"]["peticion_sh"],
        "epsg_calculo": cfg["crs"]["calculo"],
        "serie_desde": resultado["serie"][0]["periodo"] if resultado["serie"] else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": resultado["n_huecos"],
        "limitaciones": [
            "El valor mensual es un compuesto, no una observación de fecha única.",
            "La media municipal enmascara el fuerte gradiente altitudinal entre la costa y "
            "Sierra Blanca; su lectura exige estratificación por altitud.",
            "Los meses sin observación válida se publican como hueco. No se interpolan.",
            "El servicio Sentinel Hub no admite EPSG:25830; la petición se formula en "
            "EPSG:32630. Las superficies se calculan aparte en EPSG:25830.",
            "La cobertura de 2017 es menor: hasta marzo de 2017 solo operaba la unidad S2A, "
            "con revisita de 10 días. Febrero de 2017 queda marcado por cobertura baja.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con_dato) if con_dato else None,
        "valor_maximo_serie": max(r["valor"] for r in con_dato) if con_dato else None,
        "licencia": "Contiene datos Copernicus modificados",
        "ruta_datos": "data/processed/ndvi_municipal.json",
    }
    (DIR_METADATA / "ndvi_municipal.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
