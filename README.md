# Observatorio de Sostenibilidad Territorial de Marbella

[![Actualización semanal](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/weekly.yml/badge.svg)](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/weekly.yml)
[![GitHub Pages](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/pages.yml/badge.svg)](https://github.com/JoseHino/observatorio-sostenibilidad-marbella/actions/workflows/pages.yml)

Indicadores ambientales del término municipal de Marbella (código INE 29069) derivados de
fuentes de observación de la Tierra y series estadísticas oficiales, publicados como sitio
estático.

**Sitio publicado: <https://josehino.github.io/observatorio-sostenibilidad-marbella/>**

## Estado

**Fase 0 — Diseño y validación de fuentes: cerrada.**

- Límite municipal obtenido del CNIG y validado: **11.714,2 ha**, coincidente con la
  superficie oficial del PGOM 2025.
- 11 endpoints verificados mediante consulta real.
- Viabilidad evaluada indicador por indicador: 10 viables, 11 viables con reservas,
  3 pendientes de resolver fuente, 3 no viables tal como se plantearon.
- Acceso a Copernicus operativo y consumo de cuota medido sobre una cuota mensual de
  10.000 PU. Sin riesgo de gasto.

**Fase 1 — Piloto vertical NDVI: cerrada.**

- Serie NDVI mensual municipal **2017-01 a 2026-07: 115 periodos, sin huecos**.
- Coste: 583,5 PU la carga histórica completa, **35,5 PU la actualización incremental**.
- Ciclo estacional mediterráneo: máximo en marzo (0,547) y mínimo en julio y agosto (0,396).
  El mínimo interanual corresponde a 2022 (0,447), año de sequía severa en Andalucía.
- Automatización verificada en CI: si no hay dato nuevo, no se genera commit; el sitio se
  redespliega igualmente para refrescar la fecha de comprobación.

Fase 2 (bloques de vegetación y clima urbano) pendiente de las decisiones abiertas
recogidas en [`docs/matriz-viabilidad.md`](docs/matriz-viabilidad.md).

## Arquitectura

Separación estricta en dos capas, sin servidor ni base de datos:

- **Capa A — Pipeline** (`pipeline/`). Python. Descarga, procesa y reduce los datos a series
  ligeras en `data/processed/`. Agrega en origen siempre que el servicio lo permite, para no
  transferir rásters.
- **Capa B — Frontend** (`web/`). HTML, JS y CSS sin frameworks pesados. Lee únicamente los
  ficheros ligeros de la Capa A. Las capas ráster se sirven por WMS bajo demanda.

Ningún fichero de `data/processed/` puede superar 5 MB.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/metodologia.md`](docs/metodologia.md) | Arquitectura, sistemas de referencia, método de cálculo |
| [`docs/matriz-viabilidad.md`](docs/matriz-viabilidad.md) | Evaluación de viabilidad de cada indicador |
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

## Advertencias técnicas

- Sentinel Hub **rechaza EPSG:25830**; las peticiones se formulan en EPSG:32630. Los cálculos
  de superficie se hacen en local sobre EPSG:25830.
- El WFS del IGN **no admite `CQL_FILTER`**; se descarga por bbox y se filtra en local.
- En la API Tempus3 del INE, el campo `Fecha` va en hora de Madrid y desplaza la serie un mes
  si se interpreta como UTC. Debe usarse `Anyo` + `FK_Periodo`.
- Los huecos de serie **no se interpolan**; se publican como ausencia explícita.

## Licencia

Código bajo licencia MIT. Datos elaborados bajo CC BY 4.0, sin perjuicio de las condiciones
propias de cada fuente de origen, recogidas en [`docs/fuentes.md`](docs/fuentes.md).

Contiene datos Copernicus modificados 2026 · CC BY 4.0 scne.es · Instituto Nacional de
Estadística · REDIAM, Junta de Andalucía · PVGIS, Joint Research Centre
