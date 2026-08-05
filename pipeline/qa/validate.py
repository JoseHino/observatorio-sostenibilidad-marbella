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


def validar_serie_indice(resultado: dict) -> list[str]:
    """Comprueba rango fisico, orden temporal y ausencia de duplicados."""
    fallos = []
    serie = resultado.get("serie", [])
    if not serie:
        return ["La serie del indice esta vacia"]

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
            fallos.append(f"{r['periodo']}: indice {v} fuera del rango fisico [-1, 1]")
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


def validar_serie_lst(resultado: dict) -> list[str]:
    """Rango fisico plausible para temperatura superficial en el litoral mediterraneo."""
    fallos = []
    serie = resultado.get("serie", [])
    if not serie:
        return ["La serie LST esta vacia"]

    periodos = [r["periodo"] for r in serie]
    if periodos != sorted(periodos):
        fallos.append("La serie LST no esta ordenada cronologicamente")

    for r in serie:
        v = r["valor"]
        if v is None:
            if "motivo" not in r:
                fallos.append(f"{r['periodo']}: hueco sin motivo declarado")
            continue
        # Margen amplio a proposito: se busca detectar errores de escalado, no acotar el clima
        if not 0.0 <= v <= 60.0:
            fallos.append(f"{r['periodo']}: LST media {v} C fuera del recorrido esperable [0, 60]")
        if r.get("p10") is not None and r.get("p90") is not None and r["p10"] > r["p90"]:
            fallos.append(f"{r['periodo']}: percentil 10 mayor que el 90")
    return fallos


def validar_serie_radiacion(resultado: dict) -> list[str]:
    """Rango plausible de irradiacion mensual en latitud mediterranea."""
    fallos = []
    serie = resultado.get("serie", [])
    if not serie:
        return ["La serie de radiacion esta vacia"]
    for r in serie:
        v = r["valor"]
        if v is None:
            continue
        # Diciembre ronda 75 y julio 250 kWh/m2: fuera de [30, 320] hay un error de unidades
        if not 30.0 <= v <= 320.0:
            fallos.append(f"{r['periodo']}: irradiacion {v} kWh/m2 fuera del rango [30, 320]")
        if r.get("minimo_espacial") is not None and r["minimo_espacial"] > r["maximo_espacial"]:
            fallos.append(f"{r['periodo']}: minimo espacial mayor que el maximo")
    return fallos


def validar_serie_clorofila(resultado: dict) -> list[str]:
    """Rango fisicamente admisible de clorofila en aguas costeras mediterraneas.

    La comprobacion clave es el signo: CHL_NN se distribuye en log10(mg/m3) y, si no se
    deshace la escala, la serie sale con valores negativos. Una concentracion negativa es
    imposible, asi que basta ese control para detectar el error de unidades.
    """
    fallos = []
    serie = resultado.get("serie", [])
    if not serie:
        return ["La serie de clorofila esta vacia"]
    for r in serie:
        v = r["valor"]
        if v is None:
            continue
        if v <= 0:
            fallos.append(
                f"{r['periodo']}: clorofila {v} mg/m3 no positiva. Probable escala "
                f"logaritmica sin deshacer"
            )
        elif v > 100:
            fallos.append(f"{r['periodo']}: clorofila {v} mg/m3 fuera de lo plausible")
    return fallos
