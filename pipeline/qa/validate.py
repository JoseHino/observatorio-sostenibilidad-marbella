"""Control de calidad de los productos generados.

Las validaciones no corrigen datos: informan. Un fallo de QA se registra y se comunica, pero
nunca se resuelve alterando el dato en silencio.
"""

from __future__ import annotations

from config import DIR_PROCESSED

TAMANO_MAXIMO_MB = 5.0


def validar_limite(ficha: dict, tolerancia_ha: float = 5.0) -> list[str]:
    """Contrasta la superficie calculada con la cifra oficial de referencia."""
    fallos = []
    referencia = ficha.get("superficie_ha_referencia_pgom")
    if referencia:
        desvio = abs(ficha["superficie_ha"] - referencia)
        if desvio > tolerancia_ha:
            fallos.append(
                f"Superficie {ficha['superficie_ha']} ha se desvia {desvio:.1f} ha "
                f"de la referencia oficial ({referencia} ha)"
            )
    return fallos


def validar_serie_ndvi(resultado: dict) -> list[str]:
    """Comprueba rango fisico, orden temporal y ausencia de duplicados."""
    fallos = []
    serie = resultado.get("serie", [])
    if not serie:
        return ["La serie NDVI esta vacia"]

    periodos = [r["periodo"] for r in serie]
    if periodos != sorted(periodos):
        fallos.append("La serie no esta ordenada cronologicamente")
    if len(periodos) != len(set(periodos)):
        fallos.append("Hay periodos duplicados en la serie")

    for r in serie:
        v = r["valor"]
        if v is None:
            # Un hueco es un resultado valido: debe llevar motivo declarado
            if "motivo" not in r:
                fallos.append(f"{r['periodo']}: hueco sin motivo declarado")
            continue
        if not -1.0 <= v <= 1.0:
            fallos.append(f"{r['periodo']}: NDVI {v} fuera del rango fisico [-1, 1]")
        if r.get("cobertura_pct") is not None and r["cobertura_pct"] > 105:
            fallos.append(f"{r['periodo']}: cobertura {r['cobertura_pct']}% imposible")
    return fallos


def validar_tamanos() -> list[str]:
    """Ningun fichero publicado puede superar el umbral de la regla de oro."""
    fallos = []
    for f in DIR_PROCESSED.glob("*"):
        mb = f.stat().st_size / (1024 * 1024)
        if mb > TAMANO_MAXIMO_MB:
            fallos.append(f"{f.name} pesa {mb:.1f} MB y supera el limite de {TAMANO_MAXIMO_MB} MB")
    return fallos
