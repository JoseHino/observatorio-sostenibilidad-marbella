"""Carga de configuracion y credenciales del pipeline.

Las credenciales se leen de variables de entorno. Si existe un fichero .env en la raiz del
repositorio se cargan desde ahi, lo que permite ejecutar en local sin exportar nada a mano.
En GitHub Actions las variables llegan por el entorno y el .env no existe.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "pipeline" / "config.yaml"

DIR_RAW = ROOT / "data" / "raw"
DIR_PROCESSED = ROOT / "data" / "processed"
DIR_METADATA = ROOT / "data" / "metadata"


def _cargar_dotenv() -> None:
    """Vuelca el .env en el entorno sin pisar variables ya definidas."""
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return
    for linea in dotenv.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        # Las variables de entorno reales tienen prioridad sobre el .env
        os.environ.setdefault(clave.strip(), valor.strip())


def cargar_config() -> dict:
    """Devuelve el config.yaml como diccionario y asegura los directorios de trabajo."""
    _cargar_dotenv()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for d in (DIR_RAW, DIR_PROCESSED, DIR_METADATA):
        d.mkdir(parents=True, exist_ok=True)
    return cfg


def credencial(nombre_variable: str, obligatoria: bool = True) -> str:
    """Lee una credencial del entorno. Nunca se registra su valor."""
    valor = os.environ.get(nombre_variable, "").strip()
    if not valor and obligatoria:
        raise RuntimeError(
            f"Falta la credencial {nombre_variable}. "
            f"Definela en el .env local o como secret del repositorio."
        )
    return valor
