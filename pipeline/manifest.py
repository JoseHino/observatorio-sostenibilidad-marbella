"""Manifiesto de ejecucion: deteccion de cambios e idempotencia.

Antes de descargar nada, cada modulo consulta que hay disponible en origen y lo compara con
este manifiesto. Si no hay nada nuevo, la ejecucion termina sin commit. Si la configuracion
del indicador cambia (detectable por hash_config), se fuerza el reproceso completo de la serie.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from config import DIR_METADATA

RUTA_MANIFIESTO = DIR_METADATA / "manifest.json"


def ahora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_config(cfg_indicador: dict) -> str:
    """Huella de la configuracion de un indicador.

    Si cambia la resolucion, el intervalo, las clases SCL validas o cualquier otro parametro
    de calculo, la huella cambia y la serie historica deja de ser comparable: hay que
    recalcularla entera.
    """
    serializado = json.dumps(cfg_indicador, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()[:16]


def leer() -> dict:
    if RUTA_MANIFIESTO.exists():
        return json.loads(RUTA_MANIFIESTO.read_text(encoding="utf-8"))
    return {}


def entrada(indicador: str) -> dict:
    return leer().get(indicador, {})


def actualizar(indicador: str, **campos) -> None:
    """Actualiza la entrada de un indicador conservando el resto del manifiesto.

    El manifiesto se versiona, asi que solo puede contener campos derivados del dato.
    Un sello de tiempo de ejecucion cambiaria en cada pasada y forzaria un commit aunque
    no hubiera dato nuevo: la marca de comprobacion viaja en estado.json, que no se versiona.
    """
    m = leer()
    registro = m.get(indicador, {})
    registro.update(campos)
    # Se purgan las claves volatiles que pudieran arrastrarse de versiones anteriores
    for volatil in ("ultima_ejecucion", "pu_ultima_ejecucion"):
        registro.pop(volatil, None)
    m[indicador] = registro
    RUTA_MANIFIESTO.write_text(
        json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def requiere_reproceso(indicador: str, huella_actual: str) -> bool:
    """True si nunca se ejecuto o si la configuracion del indicador ha cambiado."""
    previo = entrada(indicador).get("hash_config")
    return previo != huella_actual
