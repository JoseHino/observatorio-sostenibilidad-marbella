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
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest
from config import DIR_METADATA, DIR_PROCESSED, ROOT, cargar_config
from processing import ndvi as proc_ndvi
from qa import validate
from sources import cnig

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


def tarea_ndvi(cfg: dict, forzar: bool) -> list[str]:
    ind = cfg["indicadores"]["ndvi_municipal"]
    huella = manifest.hash_config(ind)
    # Si cambia la configuracion de calculo, la serie historica deja de ser comparable
    reproceso = forzar or manifest.requiere_reproceso("ndvi_municipal", huella)
    if reproceso and not forzar:
        log("ndvi", "INFO", "cambio de configuracion: se recalcula la serie completa")

    resultado = proc_ndvi.construir_serie(cfg, forzar=reproceso)
    fallos = validate.validar_serie_ndvi(resultado)
    proc_ndvi.escribir(resultado, cfg)

    previo = manifest.entrada("ndvi_municipal").get("ultima_fecha_dato")
    novedad = "sin cambios" if previo == resultado["ultimo_periodo"] else "dato nuevo"
    log(
        "ndvi",
        "OK",
        f"{resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
        f"hasta {resultado['ultimo_periodo']} ({novedad}), "
        f"{resultado['pu_consumidas_ejecucion']} PU",
    )
    manifest.actualizar(
        "ndvi_municipal",
        ultima_fecha_dato=resultado["ultimo_periodo"],
        n_periodos=resultado["n_periodos"],
        n_huecos=resultado["n_huecos"],
        hash_config=huella,
        pu_ultima_ejecucion=resultado["pu_consumidas_ejecucion"],
    )
    return fallos


TAREAS = [
    ("limite_municipal", tarea_limite),
    ("ndvi_municipal", tarea_ndvi),
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
