"""Fuente Copernicus: openEO del Data Space Ecosystem.

Se usa openEO, y no Sentinel Hub, para los productos de nivel 2 ya elaborados por la ESA,
como la temperatura superficial terrestre. Sentinel Hub solo expone las bandas de
temperatura de brillo de Sentinel-3; convertirlas a LST exigiria implementar una correccion
de emisividad propia, es decir, una aproximacion no documentada. El producto
SENTINEL3_SLSTR_L2_LST evita ese problema.

Restricciones del servicio comprobadas empiricamente (04/08/2026):
  - Las credenciales de cliente de Sentinel Hub SIRVEN para openEO, pero solo si se pide el
    token con scope=openid. Sin ese scope el servicio responde 403 TokenInvalid.
  - El token se presenta como "Bearer oidc/CDSE/<token>", no como Bearer a secas.
  - Las peticiones sincronas a /result fallan de forma intermitente con 500; hay que
    reintentar. Una peticion de tres meses tarda del orden de 200 s.
"""

from __future__ import annotations

import json
import time

import requests

from config import DIR_RAW, credencial

BASE = "https://openeo.dataspace.copernicus.eu/openeo/1.2"
URL_TOKEN = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

_token_cache: dict = {"valor": None, "expira": 0.0}

# Reductor "media" reutilizable en los distintos nodos del grafo
REDUCTOR_MEDIA = {
    "process_graph": {
        "m": {
            "process_id": "mean",
            "arguments": {"data": {"from_parameter": "data"}},
            "result": True,
        }
    }
}


def obtener_token() -> str:
    if _token_cache["valor"] and time.monotonic() < _token_cache["expira"]:
        return _token_cache["valor"]
    r = requests.post(
        URL_TOKEN,
        data={
            "grant_type": "client_credentials",
            "client_id": credencial("CDSE_CLIENT_ID"),
            "client_secret": credencial("CDSE_CLIENT_SECRET"),
            "scope": "openid",  # imprescindible: sin el, openEO devuelve 403
        },
        timeout=60,
    )
    r.raise_for_status()
    d = r.json()
    _token_cache["valor"] = d["access_token"]
    _token_cache["expira"] = time.monotonic() + int(d.get("expires_in", 1800)) - 60
    return _token_cache["valor"]


def cabeceras() -> dict:
    return {"Authorization": f"Bearer oidc/CDSE/{obtener_token()}"}


def ejecutar(grafo: dict, reintentos: int = 4, espera_base: int = 20) -> dict:
    """Ejecuta un grafo de proceso de forma sincrona, con reintentos.

    Los 500 del backend son frecuentes y transitorios: el mismo grafo que falla suele
    funcionar al reintentarlo. Un fallo persistente si es un error real y se propaga.
    """
    ultimo = ""
    for intento in range(1, reintentos + 1):
        try:
            r = requests.post(
                f"{BASE}/result", headers=cabeceras(), json={"process": grafo}, timeout=1800
            )
        except requests.exceptions.RequestException as e:
            ultimo = f"excepcion de red: {e}"
            if intento < reintentos:
                time.sleep(espera_base * intento)
                continue
            break
        if r.status_code == 200:
            return r.json()
        ultimo = f"HTTP {r.status_code}: {r.text[:250]}"
        if r.status_code in (429, 500, 502, 503, 504) and intento < reintentos:
            time.sleep(espera_base * intento)
            continue
        break
    raise RuntimeError(f"openEO fallo tras {reintentos} intentos :: {ultimo}")


def cachear(nombre: str, datos: dict) -> None:
    destino = DIR_RAW / "openeo"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def leer_cache(nombre: str):
    ruta = DIR_RAW / "openeo" / f"{nombre}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return None
