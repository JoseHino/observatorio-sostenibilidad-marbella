"""Orquestador del pipeline.

Ejecuta las fuentes activas en secuencia. Si una falla, se registra el error y se continua
con las demas: el sitio nunca queda roto por una fuente caida, muestra el ultimo dato valido.

Uso:
    python pipeline/run_all.py              # incremental
    python pipeline/run_all.py --forzar     # reprocesa toda la serie ignorando la cache
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest
from config import DIR_METADATA, DIR_PROCESSED, ROOT, cargar_config
from processing import lst as proc_lst
from processing import presion_turistica as proc_presion
from processing import radiacion as proc_rad
from processing import calidad_agua as proc_agua
from processing import indices_s2
from processing import no2 as proc_no2
from qa import no_empobrecer, validate
from sources import buffer_marino, cnig

WEB_DATA = ROOT / "web" / "data"


def log(fuente: str, estado: str, detalle: str = "") -> None:
    print(f"[{manifest.ahora_utc()}] {estado:8s} {fuente:22s} {detalle}")


def sincronizar_web() -> None:
    """Copia los productos ligeros a web/data para que el frontend los sirva."""
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    for f in list(DIR_PROCESSED.glob("*.json")) + list(DIR_PROCESSED.glob("*.geojson")):
        shutil.copy2(f, WEB_DATA / f.name)
    destino_meta = WEB_DATA / "metadata"
    destino_meta.mkdir(exist_ok=True)
    for f in DIR_METADATA.glob("*.json"):
        shutil.copy2(f, destino_meta / f.name)


def escribir_estado(telemetria: dict, caidas: list, fallos_qa: list) -> None:
    """Marca de comprobacion y telemetria, para el sitio desplegado.

    No se versiona: es lo que permite que una pasada sin dato nuevo no genere commit.
    Llega al sitio publicado a traves del artefacto de despliegue, no del repositorio.
    """
    estado = {
        "ultima_comprobacion": manifest.ahora_utc(),
        "fuentes_con_error": caidas,
        "incidencias_qa": fallos_qa,
        "telemetria": telemetria,
    }
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "estado.json").write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def tarea_limite(cfg: dict, forzar: bool) -> list[str]:
    ficha = cnig.obtener_limite_municipal(cfg, forzar=forzar)
    log("cnig.limite", "OK", f"{ficha['superficie_ha']} ha")
    fallos = validate.validar_limite(ficha)
    manifest.actualizar(
        "limite_municipal",
        superficie_ha=ficha["superficie_ha"],
        fuente="CNIG WFS INSPIRE",
    )
    return fallos


def tarea_indice_s2(clave: str):
    """Fabrica la tarea de un indice de Sentinel-2 (NDVI, NDBI...)."""
    def tarea(cfg: dict, forzar: bool) -> list[str]:
        ind = cfg["indicadores"][clave]
        if not ind.get("activo", True):
            return []
        huella = manifest.hash_config(ind)
        # Si cambia la configuracion de calculo, la serie historica deja de ser comparable
        reproceso = forzar or manifest.requiere_reproceso(clave, huella)
        if reproceso and not forzar:
            log(clave, "INFO", "cambio de configuracion: se recalcula la serie completa")

        resultado = indices_s2.construir_serie(cfg, clave, forzar=reproceso)
        fallos = validate.validar_serie_indice(resultado)
        permite, motivo = no_empobrecer.permite_escribir(clave, resultado, forzar)
        if not permite:
            log(clave, "AVISO", motivo)
            return fallos
        indices_s2.escribir(resultado, cfg, clave)

        tele = resultado["_telemetria"]
        previo = manifest.entrada(clave).get("ultima_fecha_dato")
        novedad = "sin cambios" if previo == resultado["ultimo_periodo"] else "dato nuevo"
        log(clave, "OK",
            f"{resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
            f"hasta {resultado['ultimo_periodo']} ({novedad}), {tele['pu_consumidas']} PU")
        manifest.actualizar(
            clave,
            ultima_fecha_dato=resultado["ultimo_periodo"],
            n_periodos=resultado["n_periodos"],
            n_huecos=resultado["n_huecos"],
            hash_config=huella,
        )
        TELEMETRIA[clave] = tele
        return fallos
    return tarea


# Telemetria acumulada de la pasada, volcada a estado.json al final
TELEMETRIA: dict = {}


def tarea_lst(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["lst_municipal"]
    if not ind.get("activo", True):
        return []
    huella = manifest.hash_config(ind)
    reproceso = forzar or manifest.requiere_reproceso("lst_municipal", huella)
    if reproceso and not forzar:
        log("lst", "INFO", "cambio de configuracion: se recalcula la serie completa")

    resultado = proc_lst.construir_serie(cfg, forzar=reproceso)
    fallos = validate.validar_serie_lst(resultado)
    permite, motivo = no_empobrecer.permite_escribir("lst_municipal", resultado, forzar)
    if not permite:
        log("lst", "AVISO", motivo)
        return fallos
    proc_lst.escribir(resultado, cfg)

    tele = resultado["_telemetria"]
    previo = manifest.entrada("lst_municipal").get("ultima_fecha_dato")
    novedad = "sin cambios" if previo == resultado["ultimo_periodo"] else "dato nuevo"
    log(
        "lst",
        "OK",
        f"{resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
        f"hasta {resultado['ultimo_periodo']} ({novedad}); "
        f"{tele['escenas_leidas']} escenas nuevas, {tele['escenas_reutilizadas']} en cache, "
        f"{tele['escenas_descartadas']} descartadas",
    )
    manifest.actualizar(
        "lst_municipal",
        ultima_fecha_dato=resultado["ultimo_periodo"],
        n_periodos=resultado["n_periodos"],
        n_huecos=resultado["n_huecos"],
        hash_config=huella,
    )
    TELEMETRIA["lst_municipal"] = tele
    return fallos


def tarea_radiacion(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["radiacion_solar"]
    if not ind.get("activo", True):
        return []
    huella = manifest.hash_config(ind)
    reproceso = forzar or manifest.requiere_reproceso("radiacion_solar", huella)
    resultado = proc_rad.construir_serie(cfg, forzar=reproceso)
    fallos = validate.validar_serie_radiacion(resultado)
    proc_rad.escribir(resultado, cfg)
    tele = resultado["_telemetria"]
    log("radiacion", "OK",
        f"{resultado['n_periodos']} periodos hasta {resultado['ultimo_periodo']} "
        f"(reanalisis cerrado); {resultado['n_puntos_muestreo']} puntos, "
        f"{tele['puntos_leidos']} consultados, {tele['puntos_reutilizados']} en cache")
    manifest.actualizar(
        "radiacion_solar",
        ultima_fecha_dato=resultado["ultimo_periodo"],
        n_periodos=resultado["n_periodos"],
        hash_config=huella,
    )
    TELEMETRIA["radiacion_solar"] = {k: v for k, v in tele.items() if k != "puntos"}
    return fallos


def tarea_presion(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["presion_turistica"]
    if not ind.get("activo", True):
        return []
    huella = manifest.hash_config(ind)
    resultado = proc_presion.construir(cfg, forzar=forzar)
    proc_presion.escribir(resultado, cfg)
    c = {x["variable"]: x.get("correlacion_pearson") for x in resultado["cruces"]}
    log("presion_turistica", "OK",
        f"{resultado['n_periodos']} periodos hasta {resultado['ultimo_periodo']}; "
        f"r(pernoct,NDVI)={c.get('ndvi')}  r(pernoct,LST)={c.get('lst')}")
    manifest.actualizar(
        "presion_turistica",
        ultima_fecha_dato=resultado["ultimo_periodo"],
        n_periodos=resultado["n_periodos"],
        hash_config=huella,
    )
    TELEMETRIA["presion_turistica"] = resultado["_telemetria"]
    return []


def tarea_buffer_marino(cfg: dict, forzar: bool) -> list[str]:
    ficha = buffer_marino.construir(cfg)
    log("buffer_marino", "OK", f"{ficha['superficie_ha']} ha de franja marina")
    return []


def tarea_no2(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["no2_troposferico"]
    if not ind.get("activo", True):
        return []
    huella = manifest.hash_config(ind)
    reproceso = forzar or manifest.requiere_reproceso("no2_troposferico", huella)
    resultado = proc_no2.construir_serie(cfg, forzar=reproceso)
    proc_no2.escribir(resultado, cfg)
    log("no2", "OK",
        f"{resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
        f"hasta {resultado['ultimo_periodo']}, {resultado['_telemetria']['pu_consumidas']} PU")
    manifest.actualizar("no2_troposferico", ultima_fecha_dato=resultado["ultimo_periodo"],
                        n_periodos=resultado["n_periodos"], hash_config=huella)
    TELEMETRIA["no2_troposferico"] = resultado["_telemetria"]
    return []


def tarea_clorofila(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["clorofila_litoral"]
    if not ind.get("activo", True):
        return []
    huella = manifest.hash_config(ind)
    reproceso = forzar or manifest.requiere_reproceso("clorofila_litoral", huella)
    # La carga historica de esta fuente lleva horas. En una ejecucion desatendida no se
    # intenta: se compone con lo que haya en cache y los meses que falten quedan como hueco
    # declarado. El relleno se lanza aparte con pipeline/processing/rellenar_clorofila.py.
    if os.environ.get("CI") and not reproceso:
        resultado = proc_agua.componer_desde_cache(cfg)
    else:
        resultado = proc_agua.construir_serie(cfg, forzar=reproceso)
    fallos = validate.validar_serie_clorofila(resultado)
    permite, motivo = no_empobrecer.permite_escribir("clorofila_litoral", resultado, forzar)
    if not permite:
        log("clorofila", "AVISO", motivo)
        return fallos
    proc_agua.escribir(resultado, cfg)
    log("clorofila", "OK",
        f"{resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
        f"hasta {resultado['ultimo_periodo']}")
    manifest.actualizar("clorofila_litoral", ultima_fecha_dato=resultado["ultimo_periodo"],
                        n_periodos=resultado["n_periodos"], hash_config=huella)
    TELEMETRIA["clorofila_litoral"] = resultado["_telemetria"]
    return fallos


TAREAS = [
    ("limite_municipal", tarea_limite),
    ("buffer_marino", tarea_buffer_marino),
    ("ndvi_municipal", tarea_indice_s2("ndvi_municipal")),
    ("ndbi_municipal", tarea_indice_s2("ndbi_municipal")),
    ("lst_municipal", tarea_lst),
    ("no2_troposferico", tarea_no2),
    ("clorofila_litoral", tarea_clorofila),
    ("radiacion_solar", tarea_radiacion),
    ("presion_turistica", tarea_presion),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline del Observatorio de Sostenibilidad")
    ap.add_argument("--forzar", action="store_true", help="ignora la cache y recalcula todo")
    args = ap.parse_args()

    cfg = cargar_config()
    log("pipeline", "INICIO", f"{cfg['ambito']['municipio']} ({cfg['ambito']['codigo_ine']})")

    fallos_qa: list[str] = []
    caidas: list[str] = []

    for nombre, tarea in TAREAS:
        try:
            fallos_qa.extend(tarea(cfg, args.forzar))
        except Exception as e:  # una fuente caida no debe tumbar el resto del pipeline
            caidas.append(f"{nombre}: {e}")
            log(nombre, "ERROR", str(e)[:200])
            traceback.print_exc(limit=2)

    fallos_qa.extend(validate.validar_tamanos())
    sincronizar_web()
    escribir_estado(TELEMETRIA, caidas, fallos_qa)

    if fallos_qa:
        log("qa", "AVISO", f"{len(fallos_qa)} incidencia(s)")
        for f in fallos_qa:
            print(f"    - {f}")
    else:
        log("qa", "OK", "sin incidencias")

    if caidas:
        log("pipeline", "FIN", f"{len(caidas)} fuente(s) con error")
        return 1
    log("pipeline", "FIN", "todas las fuentes correctas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
