"""Fuente PVGIS (Joint Research Centre): irradiacion solar mensual.

No requiere registro ni consume cuota. Es la fuente de menor friccion del observatorio.

Naturaleza del dato, que condiciona como se publica: PVGIS-SARAH3 es un REANALISIS con
recorrido cerrado (2005-2023 en la version 5.3), no una serie viva. No se actualiza cada mes,
de modo que el indicador no debe marcarse como desactualizado por no crecer: sencillamente su
serie termina donde termina la base de radiacion.

PVGIS entrega el dato por coordenada, no por poligono. Para no reducir un municipio con
1.200 m de desnivel a un unico punto, se muestrea una rejilla interior y se publica la media
junto con el recorrido entre puntos, que describe la variabilidad espacial.
"""

from __future__ import annotations

import time

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import Point

URL = "https://re.jrc.ec.europa.eu/api/v5_3/MRcalc"

ANIO_INICIO, ANIO_FIN = 2005, 2023  # recorrido de PVGIS-SARAH3 en la version 5.3


def puntos_de_muestreo(limite_gdf, n_lado: int = 4) -> list[tuple[float, float]]:
    """Rejilla regular recortada al termino municipal, en coordenadas geograficas.

    Se trabaja la rejilla en EPSG:25830 para que el espaciado sea metrico y homogeneo, y
    despues se convierte a 4326, que es lo que espera PVGIS.
    """
    g = limite_gdf.to_crs(25830)
    poligono = g.geometry.iloc[0]
    x0, y0, x1, y1 = poligono.bounds
    xs = np.linspace(x0, x1, n_lado + 2)[1:-1]
    ys = np.linspace(y0, y1, n_lado + 2)[1:-1]
    dentro = [Point(x, y) for x in xs for y in ys if poligono.contains(Point(x, y))]
    if not dentro:
        dentro = [poligono.representative_point()]
    serie = gpd.GeoSeries(dentro, crs=25830).to_crs(4326)
    return [(round(p.y, 5), round(p.x, 5)) for p in serie]


def serie_mensual(lat: float, lon: float, reintentos: int = 3) -> list[dict]:
    """Irradiacion global horizontal mensual, en kWh/m2, para un punto."""
    ultimo = ""
    for intento in range(1, reintentos + 1):
        try:
            r = requests.get(
                URL,
                params={
                    "lat": lat, "lon": lon, "horirrad": 1, "outputformat": "json",
                    "startyear": ANIO_INICIO, "endyear": ANIO_FIN,
                },
                timeout=180,
            )
        except requests.exceptions.RequestException as e:
            ultimo = f"excepcion de red: {e}"
            if intento < reintentos:
                time.sleep(5 * intento)
                continue
            break
        if r.status_code == 200:
            return r.json()["outputs"]["monthly"]
        ultimo = f"HTTP {r.status_code}: {r.text[:200]}"
        if r.status_code in (429, 500, 502, 503, 504) and intento < reintentos:
            time.sleep(5 * intento)
            continue
        break
    raise RuntimeError(f"PVGIS fallo en ({lat}, {lon}) :: {ultimo}")
