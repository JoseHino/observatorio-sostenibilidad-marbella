"""Fuente INE: API Tempus3 (wstempus).

Trampas del servicio, todas comprobadas sobre las series de Marbella:

  - El campo `Fecha` viene en milisegundos de hora de Madrid. Interpretado como UTC cae en el
    mes anterior y desplaza la serie entera. El periodo se construye SIEMPRE con `Anyo` y
    `FK_Periodo`, nunca con `Fecha`.
  - Los datos llegan en orden ASCENDENTE pese a pedirse con `nult`. Tomar `Data[0]` como
    ultimo valor es un error: es el mas antiguo.
  - Algunas series arrastran registros huerfanos muy anteriores al tramo continuo (la de
    pernoctaciones trae un unico dato de 2007 y luego arranca en 2018). Se detectan y se
    recortan para no publicar un hueco de once anos.
  - `FK_TipoDato` distingue el dato definitivo (1) del provisional o avance (2). Se conserva
    para poder declararlo junto al dato.
"""

from __future__ import annotations

import json
import time

import requests

from config import DIR_RAW

BASE = "https://servicios.ine.es/wstempus/js/ES"

# Series de la Encuesta de Ocupacion Hotelera para Marbella (punto turistico 2822)
SERIES = {
    "pernoctaciones": "EOT42534",
    "viajeros": "EOT42428",
    "plazas": "EOT3080",
    "grado_ocupacion": "EOT3152",
}


def descargar_serie(codigo: str, nult: int = 300, reintentos: int = 3) -> dict:
    ultimo = ""
    for intento in range(1, reintentos + 1):
        try:
            r = requests.get(f"{BASE}/DATOS_SERIE/{codigo}", params={"nult": nult}, timeout=180)
        except requests.exceptions.RequestException as e:
            ultimo = f"excepcion de red: {e}"
            if intento < reintentos:
                time.sleep(4 * intento)
                continue
            break
        if r.status_code == 200:
            return r.json()
        ultimo = f"HTTP {r.status_code}: {r.text[:150]}"
        if r.status_code in (429, 500, 502, 503, 504) and intento < reintentos:
            time.sleep(4 * intento)
            continue
        break
    raise RuntimeError(f"INE Tempus3 fallo en la serie {codigo} :: {ultimo}")


def a_serie_mensual(payload: dict) -> tuple[list[dict], dict]:
    """Normaliza la respuesta a serie mensual ordenada. Devuelve (serie, incidencias)."""
    registros = []
    for x in payload.get("Data", []):
        anyo, periodo = x.get("Anyo"), x.get("FK_Periodo")
        # Solo periodos mensuales; se ignoran acumulados y otros tipos de periodo
        if not anyo or not periodo or not 1 <= int(periodo) <= 12:
            continue
        registros.append({
            "periodo": f"{int(anyo):04d}-{int(periodo):02d}",
            "valor": x.get("Valor"),
            "provisional": int(x.get("FK_TipoDato", 1)) != 1,
        })
    registros.sort(key=lambda r: r["periodo"])

    # Recorte de registros huerfanos: si entre dos observaciones consecutivas median mas de
    # dos anos, lo anterior es un resto aislado y no parte de la serie continua
    incidencias = {"registros_huerfanos_descartados": 0, "desde_original": None}
    if registros:
        incidencias["desde_original"] = registros[0]["periodo"]
        corte = 0
        for i in range(1, len(registros)):
            anterior = int(registros[i - 1]["periodo"][:4]) * 12 + int(registros[i - 1]["periodo"][5:])
            actual = int(registros[i]["periodo"][:4]) * 12 + int(registros[i]["periodo"][5:])
            if actual - anterior > 24:
                corte = i
        if corte:
            incidencias["registros_huerfanos_descartados"] = corte
            registros = registros[corte:]
    return registros, incidencias


def obtener(nombre: str, forzar: bool = False) -> tuple[list[dict], dict]:
    """Serie mensual de una de las series declaradas, con cache local."""
    codigo = SERIES[nombre]
    destino = DIR_RAW / "ine"
    destino.mkdir(parents=True, exist_ok=True)
    cache = destino / f"{codigo}.json"

    if cache.exists() and not forzar:
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        payload = descargar_serie(codigo)
        cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    serie, incidencias = a_serie_mensual(payload)
    incidencias["codigo"] = codigo
    incidencias["nombre_ine"] = payload.get("Nombre", "").strip()
    return serie, incidencias
