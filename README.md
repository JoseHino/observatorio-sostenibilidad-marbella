# Observatorio de Sostenibilidad Territorial de Marbella

[![Actualización semanal](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/weekly.yml/badge.svg)](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/weekly.yml)
[![GitHub Pages](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/pages.yml/badge.svg)](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/pages.yml)

Indicadores ambientales del término municipal de Marbella (código INE 29069) derivados de
fuentes de observación de la Tierra y series estadísticas oficiales, publicados como sitio
estático.

**Sitio publicado: <https://josehino.github.io/observatorio-sostenibilidad-marbella/>**

## El hallazgo

**Agosto concentra a la vez el máximo de ocupación hotelera, el mínimo de vegetación y el
máximo de temperatura superficial.** El municipio recibe en ese mes 4,5 veces más
pernoctaciones que en el más tranquilo, y lo hace cuando la vegetación está en su punto más
bajo y las superficies alcanzan su temperatura máxima.

| Cruce | Coeficiente |
|---|---|
| Pernoctaciones ↔ NDVI | **−0,699** |
| Pernoctaciones ↔ temperatura superficial | **+0,840** |

La correlación no implica causalidad —dos series con ciclo anual marcado correlacionan por
compartir estacionalidad—, pero el signo y la coincidencia de fase son inequívocos.

## Indicadores publicados

| Bloque | Indicador | Fuente | Serie | Resolución |
|---|---|---|---|---|
| 1 · Vegetación | NDVI medio municipal | Sentinel-2 L2A | 2017-01 → 2026-07, sin huecos | 20 m |
| 2 · Clima urbano | Temperatura superficial terrestre | Landsat 8/9 (ST_B10) | 2017-01 → 2026-07, 14 huecos | 30 m |
| 3 · Suelo | NDBI, superficie construida | Sentinel-2 L2A | 2017-01 → 2026-07, sin huecos | 20 m |
| 4 · Litoral | Clorofila-a en aguas litorales | Sentinel-3 OLCI L2 (CHL_NN) | 2017 → 2026 | 300 m |
| 5 · Energía | Irradiación solar global horizontal | PVGIS-SARAH3 | 2005-01 → 2023-12 (reanálisis cerrado) | 9 puntos |
| 5 · Atmósfera | NO₂ troposférico | Sentinel-5P L2 | 2019-01 → 2026-07 | ~5,5 × 3,5 km |
| Transversal | Presión turística × ambiente | INE, Encuesta de Ocupación Hotelera | 2018-01 → 2026-06 | municipio |

Cada indicador publica su ficha de metadatos con fuente, fórmula, método de cálculo,
enmascaramiento y **limitaciones declaradas**.

## Arquitectura

Separación estricta en dos capas, sin servidor ni base de datos:

- **Capa A — Pipeline** (`pipeline/`). Python. Descarga, procesa y reduce los datos a series
  ligeras en `data/processed/`. Agrega en origen siempre que el servicio lo permite, para no
  transferir rásters.
- **Capa B — Frontend** (`web/`). HTML, JS y CSS sin frameworks pesados. Lee únicamente los
  ficheros ligeros de la Capa A. Las capas ráster se sirven por WMS bajo demanda.

Ningún fichero de `data/processed/` supera 5 MB.

## Principios que el observatorio respeta

1. **Los huecos no se interpolan.** Un mes sin observación válida se publica como
   discontinuidad, con el motivo declarado.
2. **Ningún descarte es silencioso.** El pipeline publica el recuento y la causa de cada
   escena u observación rechazada.
3. **Nada se estima sin declararlo.** Cuando un producto oficial existe, se usa el producto
   oficial en lugar de derivarlo con una corrección propia.
4. **La resolución se declara junto al dato.** El NO₂ se publica advirtiendo de que su lectura
   es comarcal, no municipal.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/metodologia.md`](docs/metodologia.md) | Arquitectura, sistemas de referencia y método de cada indicador |
| [`docs/matriz-viabilidad.md`](docs/matriz-viabilidad.md) | Viabilidad indicador por indicador, con lo descartado y por qué |
| [`docs/fuentes.md`](docs/fuentes.md) | Endpoints verificados, incidencias, licencias y atribución |

## Configuración

Las credenciales se leen de variables de entorno y **nunca** se versionan. Copiar
`.env.example` a `.env` y completar:

```
CDSE_CLIENT_ID=
CDSE_CLIENT_SECRET=
AEMET_API_KEY=
```

Las credenciales de Copernicus se obtienen en <https://dataspace.copernicus.eu> y la clave de
AEMET en <https://opendata.aemet.es/centrodedescargas/altaUsuario>. Ambas son gratuitas.

Ejecución:

```
pip install -r pipeline/requirements.txt
python pipeline/run_all.py            # incremental
python pipeline/run_all.py --forzar   # recalcula todo ignorando la caché
```

## Advertencias técnicas

- Sentinel Hub **rechaza EPSG:25830**; las peticiones se formulan en EPSG:32630. Los cálculos
  de superficie se hacen en local sobre EPSG:25830.
- openEO acepta las credenciales de Sentinel Hub **solo si el token se pide con
  `scope=openid`**; sin él responde 403.
- El WFS del IGN **no admite `CQL_FILTER`**; se descarga por bbox y se filtra en local.
- En la API Tempus3 del INE, el campo `Fecha` va en hora de Madrid y desplaza la serie un mes
  si se interpreta como UTC. Debe usarse `Anyo` + `FK_Periodo`. Además los datos llegan en
  orden **ascendente**, y alguna serie arrastra registros huérfanos muy anteriores al tramo
  continuo.
- Landsat se sirve desde Microsoft Planetary Computer: las URL de USGS redirigen a un acceso
  autenticado y el bucket de S3 es *requester-pays*.

## Lo que no está publicado, y por qué

- **Temperatura y precipitación (AEMET)**: requiere una clave gratuita aún no dada de alta.
- **Oleaje**: Puertos del Estado no expone API pública; la alternativa (CMEMS) exige un
  registro adicional que está pendiente de decidir.
- **Potencial fotovoltaico en cubiertas y altura de vegetación**: no son series temporales,
  sino determinaciones puntuales que exigen procesado de LiDAR. Quedan fuera del alcance.
- **Estratificación por altitud**: no hay modelo digital de elevaciones accesible por las vías
  gratuitas de Copernicus; requiere el MDT del CNIG.

El detalle completo está en [`docs/matriz-viabilidad.md`](docs/matriz-viabilidad.md).

## Licencia

Código bajo licencia MIT. Datos elaborados bajo CC BY 4.0, sin perjuicio de las condiciones
propias de cada fuente de origen, recogidas en [`docs/fuentes.md`](docs/fuentes.md).

Contiene datos modificados de Copernicus Sentinel 2026 · CC BY 4.0 scne.es · Instituto Nacional de
Estadística · REDIAM, Junta de Andalucía · PVGIS, Joint Research Centre · Landsat, USGS
