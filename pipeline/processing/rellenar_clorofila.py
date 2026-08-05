"""Relleno paralelo de la serie de clorofila.

La carga historica completa por peticiones sincronas a openEO lleva horas. openEO admite dos
peticiones concurrentes por cuenta, asi que se lanzan dos hilos: no mas, para no chocar con
el limite del servicio.

Se recorre del presente hacia atras, de modo que si el proceso se interrumpe lo ya obtenido
sea el tramo reciente. Cada trimestre se cachea por separado, asi que una nueva ejecucion
retoma donde quedo.

Uso:
    python pipeline/processing/rellenar_clorofila.py
"""

from __future__ import annotations

import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd  # noqa: E402

from config import DIR_PROCESSED, cargar_config  # noqa: E402
from processing import calidad_agua  # noqa: E402
from sources import copernicus_openeo as oeo  # noqa: E402

warnings.filterwarnings("ignore")

CONCURRENCIA = 2  # limite de peticiones simultaneas de openEO


def tramos_pendientes(cfg: dict) -> list[tuple[str, str, str]]:
    """(nombre, desde, hasta) de cada trimestre que aun no esta en cache, del mas reciente."""
    hoy = date.today()
    inicio = int(cfg["serie"]["fecha_inicio"][:4])
    pendientes = []
    for anio in range(hoy.year, inicio - 1, -1):
        if oeo.leer_cache(f"chl_{anio}") is not None:
            continue  # ese anio ya se obtuvo entero en una ejecucion anterior
        for trimestre in range(4):
            mes = trimestre * 3 + 1
            desde = f"{anio}-{mes:02d}-01"
            if desde > hoy.isoformat():
                continue
            fa, fm = (anio, mes + 3) if mes + 3 <= 12 else (anio + 1, 1)
            hasta = min(f"{fa}-{fm:02d}-01", hoy.isoformat())
            if hasta <= desde:
                continue
            nombre = f"chl_{anio}T{trimestre + 1}"
            if oeo.leer_cache(nombre) is None:
                pendientes.append((nombre, desde, hasta))
    return pendientes


def main() -> int:
    cfg = cargar_config()
    g = gpd.read_file(DIR_PROCESSED / "buffer_marino.geojson")
    simple = gpd.GeoSeries(
        [g.to_crs(32630).geometry.iloc[0].simplify(150)], crs=32630
    ).to_crs(4326)
    fc = json.loads(simple.to_json())
    bbox = simple.total_bounds

    pendientes = tramos_pendientes(cfg)
    print(f"tramos pendientes: {len(pendientes)}", flush=True)
    if not pendientes:
        print("nada que rellenar", flush=True)
        return 0

    def trabajar(t):
        nombre, desde, hasta = t
        datos = oeo.ejecutar(calidad_agua._grafo(fc, bbox, desde, hasta))
        oeo.cachear(nombre, datos)
        return nombre, len(datos)

    hechos, fallidos = 0, []
    with ThreadPoolExecutor(max_workers=CONCURRENCIA) as pool:
        futuros = {pool.submit(trabajar, t): t for t in pendientes}
        for f in as_completed(futuros):
            nombre = futuros[f][0]
            try:
                n, meses = f.result()
                hechos += 1
                print(f"  [{hechos}/{len(pendientes)}] {n}: {meses} meses", flush=True)
            except Exception as e:
                fallidos.append(nombre)
                print(f"  FALLO {nombre}: {type(e).__name__}: {str(e)[:120]}", flush=True)

    # Se recompone la serie con todo lo que haya en cache, completo o no
    resultado = calidad_agua.construir_serie(cfg)
    calidad_agua.escribir(resultado, cfg)
    con = [r for r in resultado["serie"] if r["valor"] is not None]
    print(
        f"SERIE: {resultado['n_periodos']} periodos, {resultado['n_huecos']} huecos, "
        f"{resultado['serie'][0]['periodo']} a {resultado['ultimo_periodo']}",
        flush=True,
    )
    if con:
        print("rango %.3f a %.3f mg/m3" % (min(r["valor"] for r in con), max(r["valor"] for r in con)), flush=True)
    if fallidos:
        print("tramos fallidos:", fallidos, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
