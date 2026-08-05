"""Fuente AEMET OpenData: temperatura y precipitacion medidas en estacion.

Complementa la temperatura superficial de Landsat, que mide la piel del terreno a media
manana. AEMET mide temperatura del AIRE en garita, que es varios grados inferior en verano y
la que se usa en climatologia.

Requiere una clave gratuita. Se solicita en
https://opendata.aemet.es/centrodedescargas/altaUsuario y llega por correo en minutos. Se
define como variable de entorno AEMET_API_KEY o en el .env; nunca en el codigo.

Peculiaridad del servicio: NO devuelve los datos en la primera llamada. Responde un JSON con
un campo "datos" que contiene una URL temporal, y hay que hacer una segunda peticion a esa
URL. Los ficheros vienen en ISO-8859-15, no en UTF-8, y los decimales con coma.
"""

from __future__ import annotations

import json
import math
import time

import requests

from config import DIR_RAW, credencial

BASE = "https://opendata.aemet.es/opendata/api"


def _peticion(ruta: str, reintentos: int = 3) -> list | dict:
    """Resuelve el doble salto de AEMET: primero la URL, luego los datos."""
    clave = credencial("AEMET_API_KEY")
    ultimo = ""
    for intento in range(1, reintentos + 1):
        r = requests.get(f"{BASE}{ruta}", params={"api_key": clave}, timeout=120)
        if r.status_code == 429:
            # AEMET limita la cadencia; espera y reintenta
            time.sleep(20 * intento)
            continue
        if r.status_code != 200:
            ultimo = f"HTTP {r.status_code}: {r.text[:200]}"
            if intento < reintentos:
                time.sleep(5 * intento)
                continue
            break
        sobre = r.json()
        url = sobre.get("datos")
        if not url:
            ultimo = f"respuesta sin campo 'datos': {str(sobre)[:200]}"
            break
        d = requests.get(url, timeout=180)
        d.raise_for_status()
        # Los ficheros de AEMET vienen en ISO-8859-15, no en UTF-8
        d.encoding = "ISO-8859-15"
        return json.loads(d.text)
    raise RuntimeError(f"AEMET fallo en {ruta} :: {ultimo}")


def _a_float(v) -> float | None:
    """Los decimales llegan con coma; los valores inapreciables como 'Ip'."""
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if s in ("", "Ip", "Acum"):
        return 0.0 if s == "Ip" else None
    try:
        return float(s)
    except ValueError:
        return None


def estacion_mas_cercana(lat: float, lon: float, forzar: bool = False) -> dict:
    """Estacion de la red de AEMET mas proxima al punto dado."""
    destino = DIR_RAW / "aemet"
    destino.mkdir(parents=True, exist_ok=True)
    cache = destino / "inventario_estaciones.json"

    if cache.exists() and not forzar:
        estaciones = json.loads(cache.read_text(encoding="utf-8"))
    else:
        estaciones = _peticion("/valores/climatologicos/inventarioestaciones/todasestaciones")
        cache.write_text(json.dumps(estaciones, ensure_ascii=False), encoding="utf-8")

    def grados(sexagesimal: str) -> float | None:
        # AEMET codifica la posicion como GGMMSSH, con H = N/S/E/W
        s = str(sexagesimal).strip()
        if len(s) < 7:
            return None
        try:
            g, m, seg = int(s[:2]), int(s[2:4]), int(s[4:6])
        except ValueError:
            return None
        v = g + m / 60 + seg / 3600
        return -v if s[-1] in ("S", "W") else v

    mejor, distancia_min = None, float("inf")
    for e in estaciones:
        la, lo = grados(e.get("latitud")), grados(e.get("longitud"))
        if la is None or lo is None:
            continue
        # Distancia aproximada en km, suficiente para elegir la mas cercana
        dx = (lo - lon) * 111 * math.cos(math.radians(lat))
        dy = (la - lat) * 111
        d = math.hypot(dx, dy)
        if d < distancia_min:
            mejor, distancia_min = e, d
    if mejor is None:
        raise RuntimeError("No se pudo determinar la estacion mas cercana")
    mejor = dict(mejor)
    mejor["distancia_km"] = round(distancia_min, 1)
    return mejor


def climatologia_mensual(idema: str, anio_inicio: int, anio_fin: int,
                         forzar: bool = False) -> list[dict]:
    """Valores climatologicos mensuales de una estacion, por tramos de tres anios.

    AEMET limita el rango por peticion, de modo que se trocea. Cada tramo se cachea aparte.
    """
    destino = DIR_RAW / "aemet"
    destino.mkdir(parents=True, exist_ok=True)
    filas = []
    for desde in range(anio_inicio, anio_fin + 1, 3):
        hasta = min(desde + 2, anio_fin)
        cache = destino / f"{idema}_{desde}_{hasta}.json"
        if cache.exists() and not forzar:
            filas.extend(json.loads(cache.read_text(encoding="utf-8")))
            continue
        try:
            tramo = _peticion(
                f"/valores/climatologicos/mensualesanuales/datos/anioini/{desde}"
                f"/aniofin/{hasta}/estacion/{idema}"
            )
        except RuntimeError:
            # Un tramo sin dato no debe tumbar la serie entera
            tramo = []
        cache.write_text(json.dumps(tramo, ensure_ascii=False), encoding="utf-8")
        filas.extend(tramo)
        time.sleep(1)  # cortesia con el servicio
    return filas


def a_series(filas: list[dict]) -> dict[str, dict]:
    """Normaliza a {periodo: {tm_mes, tm_max, tm_min, precipitacion}}.

    Se descartan los registros anuales: AEMET mezcla en la misma respuesta los meses (fecha
    terminada en -01 a -12) y el resumen anual (terminado en -13).
    """
    salida: dict[str, dict] = {}
    for f in filas:
        fecha = str(f.get("fecha", ""))
        if "-" not in fecha:
            continue
        anio, mes = fecha.split("-")[0], fecha.split("-")[1]
        if not mes.isdigit() or not 1 <= int(mes) <= 12:
            continue  # el sufijo -13 es el resumen anual, no un mes
        salida[f"{anio}-{int(mes):02d}"] = {
            "tm_mes": _a_float(f.get("tm_mes")),
            "tm_max": _a_float(f.get("tm_max")),
            "tm_min": _a_float(f.get("tm_min")),
            "precipitacion": _a_float(f.get("p_mes")),
        }
    return salida
