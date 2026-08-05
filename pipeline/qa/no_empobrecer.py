"""Salvaguarda: una serie publicada nunca se sustituye por otra mas pobre.

Un observatorio que se actualiza solo tiene un riesgo especifico: que una ejecucion con la
cache fria, una fuente caida o un fallo de red produzca una serie mas corta que la ya
publicada y la sobrescriba. El dato bueno se perderia sin que nadie lo notase, porque el
workflow habria terminado "correctamente".

La regla es simple: si el resultado nuevo tiene MENOS meses con dato que el fichero que ya
esta publicado, no se escribe. Un recorte legitimo (cambio de metodo, depuracion de datos
dudosos) se fuerza a proposito con --forzar, que es justamente cuando debe ser deliberado.
"""

from __future__ import annotations

import json

from config import DIR_PROCESSED


def _meses_con_dato(serie: list) -> int:
    return sum(1 for r in serie if r.get("valor") is not None)


def permite_escribir(clave: str, resultado: dict, forzar: bool = False) -> tuple[bool, str]:
    """Decide si el resultado nuevo puede sustituir al publicado. Devuelve (permite, motivo)."""
    if forzar:
        return True, ""

    ruta = DIR_PROCESSED / f"{clave}.json"
    if not ruta.exists():
        return True, ""

    try:
        previo = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return True, ""  # si el fichero previo no es legible, el nuevo siempre es mejor

    antes = _meses_con_dato(previo.get("serie", []))
    ahora = _meses_con_dato(resultado.get("serie", []))
    if ahora < antes:
        return False, (
            f"el resultado tiene {ahora} meses con dato frente a los {antes} ya publicados; "
            f"no se sobrescribe. Usar --forzar si el recorte es deliberado"
        )
    return True, ""
