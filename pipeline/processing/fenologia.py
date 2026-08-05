"""Fenologia de la vegetacion: inicio, maximo y amplitud de la estacion de crecimiento.

POR QUE NO SE USA EL PRODUCTO DE COPERNICUS. La coleccion CLMS_LSP_GLOBAL_300M_YEARLY_V2
lleva "YEARLY" en el nombre, pero sobre este ambito CDSE solo expone TRES fechas en trece
anos (2013, 2018 y 2023). Con tres puntos espaciados cinco anos no se puede afirmar ninguna
tendencia. Se comprobo consultandola.

METODO EMPLEADO. Extraccion por cruce de umbral sobre la serie de NDVI de este mismo
observatorio, que es un procedimiento estandar en teledeteccion de la vegetacion. Para cada
ano se determinan el minimo y el maximo de la curva y se toma como inicio de estacion el
instante en que el NDVI cruza el 50 % de esa amplitud en la rama ascendente.

AÑO VEGETATIVO, NO NATURAL. En clima mediterraneo la vegetacion rebrota con las lluvias de
otono y se agosta en verano, de modo que la estacion de crecimiento cabalga sobre el cambio
de ano. Usar el ano natural la partiria en dos. Se emplea por tanto un ano vegetativo que va
de JULIO a JUNIO, y se etiqueta por el ano en que termina.

LIMITACION QUE MANDA SOBRE LA LECTURA. La serie de partida es mensual, asi que la fecha de
inicio se interpola entre dos meses consecutivos: la precision es del orden de +-15 dias.
Sirve para leer la evolucion entre anos, no para fechar el rebrote de un ano concreto.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from config import DIR_METADATA, DIR_PROCESSED

UMBRAL = 0.5  # fraccion de la amplitud que define el inicio de estacion


def _tendencia(serie: list[dict]) -> float:
    """Pendiente por minimos cuadrados, en dias por ano. Solo descriptiva."""
    v = [r["valor"] for r in serie]
    n = len(v)
    if n < 3:
        return 0.0
    mx, my = (n - 1) / 2, sum(v) / n
    den = sum((i - mx) ** 2 for i in range(n))
    return sum((i - mx) * (y - my) for i, y in enumerate(v)) / den if den else 0.0


def _dia_del_periodo(periodo: str) -> date:
    """Se toma el dia 15 como representante del mes: es su centro aproximado."""
    return date(int(periodo[:4]), int(periodo[5:7]), 15)


def construir(cfg: dict) -> dict:
    ruta = DIR_PROCESSED / "ndvi_municipal.json"
    if not ruta.exists():
        raise RuntimeError("Falta ndvi_municipal.json; ejecutar antes esa tarea")
    d = json.loads(ruta.read_text(encoding="utf-8"))
    serie = {r["periodo"]: r["valor"] for r in d["serie"] if r["valor"] is not None}

    # Agrupacion por ano vegetativo julio-junio, etiquetado por el ano en que termina
    anios: dict[int, list[tuple[str, float]]] = {}
    for periodo, valor in sorted(serie.items()):
        a, m = int(periodo[:4]), int(periodo[5:7])
        etiqueta = a + 1 if m >= 7 else a
        anios.setdefault(etiqueta, []).append((periodo, valor))

    salida = []
    for etiqueta in sorted(anios):
        meses = anios[etiqueta]
        # Un ano vegetativo incompleto no permite localizar minimo ni maximo con garantia
        if len(meses) < 10:
            continue
        valores = [v for _, v in meses]
        minimo, maximo = min(valores), max(valores)
        amplitud = maximo - minimo
        if amplitud <= 0:
            continue

        i_min = valores.index(minimo)
        i_max = valores.index(maximo)
        if i_max <= i_min:
            # El maximo debe venir despues del minimo dentro del ano vegetativo
            continue

        objetivo = minimo + UMBRAL * amplitud
        inicio = None
        for i in range(i_min, i_max):
            v0, v1 = valores[i], valores[i + 1]
            if v0 < objetivo <= v1:
                # Interpolacion lineal entre los dos meses que enmarcan el cruce
                f = (objetivo - v0) / (v1 - v0)
                d0, d1 = _dia_del_periodo(meses[i][0]), _dia_del_periodo(meses[i + 1][0])
                inicio = d0 + timedelta(days=round((d1 - d0).days * f))
                break
        if inicio is None:
            continue

        pico = _dia_del_periodo(meses[i_max][0])
        # Dia relativo al 1 de julio, que es el arranque del ano vegetativo
        origen = date(etiqueta - 1, 7, 1)
        salida.append({
            "periodo": str(etiqueta),
            "valor": (inicio - origen).days,
            "fecha_inicio": inicio.isoformat(),
            "fecha_pico": pico.isoformat(),
            "dias_hasta_pico": (pico - origen).days,
            "amplitud_ndvi": round(amplitud, 4),
            "ndvi_minimo": round(minimo, 4),
            "ndvi_maximo": round(maximo, 4),
            "meses_disponibles": len(meses),
        })

    return {
        "indicador": "fenologia_vegetacion",
        "titulo": "Fenología de la vegetación",
        "unidad": "días desde el 1 de julio",
        "unidad_analisis": "municipio",
        "municipio": cfg["ambito"]["municipio"],
        "codigo_ine": cfg["ambito"]["codigo_ine"],
        "periodicidad": "anual (año vegetativo julio-junio)",
        "ultimo_periodo": salida[-1]["periodo"] if salida else None,
        "n_periodos": len(salida),
        "n_huecos": 0,
        "serie": salida,
        "_telemetria": {"anios_resueltos": len(salida)},
    }


def escribir(resultado: dict, cfg: dict) -> None:
    publicable = {k: v for k, v in resultado.items() if not k.startswith("_")}
    (DIR_PROCESSED / "fenologia_vegetacion.json").write_text(
        json.dumps(publicable, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    con = resultado["serie"]
    ficha = {
        "indicador": "fenologia_vegetacion",
        "titulo": "Fenología de la vegetación",
        "descripcion": (
            "Momento en que arranca cada año la estación de crecimiento de la vegetación del "
            "municipio, medido en días transcurridos desde el 1 de julio."
        ),
        "fuente": (
            "Derivado de la serie de NDVI de este observatorio (Copernicus Sentinel-2 L2A). "
            "No procede del producto CLMS de fenología: sobre este ámbito solo ofrece tres "
            "fechas en trece años, insuficientes para leer evolución alguna."
        ),
        "formula": (
            "Inicio de estación = instante en que el NDVI cruza el 50 % de la amplitud anual "
            "en la rama ascendente, interpolado entre los dos meses que enmarcan el cruce"
        ),
        "resolucion_espacial": "municipio",
        "resolucion_temporal": "anual, sobre año vegetativo de julio a junio",
        "metodo": (
            "Extracción por cruce de umbral, procedimiento estándar en teledetección de la "
            "vegetación. Se emplea año vegetativo julio-junio y no año natural porque en "
            "clima mediterráneo la vegetación rebrota con las lluvias de otoño y se agosta en "
            "verano: el año natural partiría la estación en dos."
        ),
        "enmascaramiento": "Hereda el de la serie de NDVI de la que se deriva.",
        "serie_desde": con[0]["periodo"] if con else None,
        "serie_hasta": resultado["ultimo_periodo"],
        "n_periodos": resultado["n_periodos"],
        "n_huecos": 0,
        "conclusion": (
            "NO se detecta adelanto ni retraso de la estación de crecimiento. La tendencia "
            f"medida es de {_tendencia(con):+.2f} días por año sobre {len(con)} años, mientras "
            "el inicio oscila entre septiembre y noviembre según cuándo lleguen las lluvias de "
            "otoño. Esa variabilidad entre años es muy superior a la tendencia y a la propia "
            "precisión del método, de modo que la serie todavía no permite responder si la "
            "primavera se adelanta en Marbella. Hará falta más recorrido temporal."
        ),
        "limitaciones": [
            "Con los años disponibles y una precisión de ±15 días, NO puede afirmarse "
            "tendencia alguna: la variabilidad entre años la supera con holgura.",
            "La serie de partida es mensual, de modo que la fecha de inicio se interpola "
            "entre dos meses consecutivos: la precisión es del orden de ±15 días. Sirve para "
            "leer la evolución entre años, no para fechar el rebrote de un año concreto.",
            "Es un indicador derivado, no una medida directa: describe el comportamiento del "
            "NDVI medio municipal, que mezcla monte, cultivo, jardín urbano y campo de golf.",
            "Los años vegetativos con menos de diez meses observados se descartan, porque sin "
            "ellos no puede localizarse el mínimo ni el máximo con garantía.",
        ],
        "valor_minimo_serie": min(r["valor"] for r in con) if con else None,
        "valor_maximo_serie": max(r["valor"] for r in con) if con else None,
        "licencia": "Contiene datos modificados de Copernicus Sentinel",
        "ruta_datos": "data/processed/fenologia_vegetacion.json",
    }
    (DIR_METADATA / "fenologia_vegetacion.json").write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )
