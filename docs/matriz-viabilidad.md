# Matriz de viabilidad de indicadores

**Fase 0** — Marbella (29069) — 3 de agosto de 2026

Evaluación de cada indicador previsto frente a la disponibilidad real de datos abiertos.
Las fuentes se han consultado efectivamente; no se declara viable ningún indicador cuyo
servicio no haya respondido.

## Leyenda

| Símbolo | Significado |
|---|---|
| **V** | Viable. Fuente verificada y resolución adecuada al ámbito. |
| **VR** | Viable con reservas. Fuente verificada, pero con limitación que debe declararse junto al dato. |
| **P** | Pendiente. Fuente no resuelta en Fase 0; requiere trabajo adicional de localización. |
| **NV** | No viable como se plantea. Debe redefinirse o descartarse. |

---

## Bloque 1 — Vegetación y espacios verdes

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| NDVI medio municipal, serie mensual desde 2017 | **V** | Sentinel-2 L2A (SH Statistical API) | Verificado extremo a extremo. 5,1 PU/mes. Tile único T30SUF. |
| NDVI por sección censal | **VR** | Sentinel-2 + cartografía censal INE | Las secciones censales de Marbella son muy desiguales: densas en el núcleo, enormes en suelo rústico. La media por sección rural mezcla monte y urbanización y pierde significado. Se recomienda publicar solo las secciones urbanas y declarar el resto. |
| Superficie verde per cápita (m²/hab) | **VR** | SITMA Marbella (WFS municipal) + padrón INE | El GeoServer municipal publica «Sistema de Espacios Libres» del PGOU. Mide **suelo calificado**, no verde real ejecutado. Debe titularse como superficie calificada, no como verde existente, o contrastarse con NDVI. |
| Densidad de cobertura arbórea | **P** | CLMS Tree Cover Density | Endpoint no resuelto. La API de descarga de CLMS exige autenticación. Pendiente de localizar servicio WMS/WCS operativo. |
| Altura media de vegetación | **NV** *(como serie)* | LiDAR PNOA | No es serie temporal. Las coberturas LiDAR son campañas espaciadas años y se descargan manualmente por hojas, sin API. **Reformular como determinación puntual**, no como indicador de evolución. |

## Bloque 2 — Clima urbano

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| LST media estival e invernal | **VR** | Sentinel-3 SLSTR L2 LST | Resolución 1 km sobre 117 km² ⇒ del orden de 117 píxeles. Suficiente para media municipal y contraste costa/sierra. Insuficiente para detalle urbano. |
| Delta de isla de calor urbana | **VR** | Sentinel-3 SLSTR | Con 1 km, el contraste urbano/periurbano es detectable pero grosero. **Alternativa recomendada: Landsat 8/9 TIRS (100 m), abierto vía USGS.** No es Copernicus, pero es la única vía abierta con resolución adecuada. |
| Mapa de puntos calientes por barrio | **NV** | Sentinel-3 | Un barrio de Marbella ocupa del orden de 1 km² o menos: **1 píxel**. El indicador no es representable con Sentinel-3. Exige Landsat (100 m) o ECOSTRESS (70 m). Debe descartarse o rehacerse sobre otra fuente. |
| Serie de temperatura y precipitación | **V** | AEMET OpenData + ERA5 | Servicio AEMET verificado y operativo. **Requiere clave gratuita, aún no dada de alta.** ERA5 exige registro adicional en el Climate Data Store. |
| Evapotranspiración de referencia | **P** | REDIAM | Servicio no localizado. Los nombres de servicio REDIAM no son deducibles: de tres candidatos probados, dos no existían. Requiere resolución contra el catálogo GeoNetwork servicio a servicio. |

## Bloque 3 — Suelo y urbanización

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| Superficie sellada, evolución | **P** | CLMS Imperviousness | Endpoint no resuelto. Además, cadencia trienal: la «serie» tendría del orden de 6 puntos desde 2006. |
| Cambios de usos del suelo | **VR** | CORINE Land Cover (WMS EEA verificado) | Cadencia ~6 años y unidad mínima cartografiable de 25 ha. **Demasiado grosero para detectar cambio urbano fino** en un municipio ya consolidado. Útil para tendencia estructural, no para seguimiento anual. |
| Ratio suelo urbanizado / natural | **V** | CORINE + PGOM 2025 | Las cifras oficiales del PGOM (urbano 5.374 ha, rústico 6.339 ha) permiten anclar y validar el cálculo. |
| Crecimiento de superficie construida | **VR** | Sentinel-2 NDBI | Se recomienda NDBI sobre Sentinel-2. **Se desaconseja Sentinel-1 en primera iteración**: alto coste de proceso y elevada incertidumbre interpretativa en terreno de fuerte relieve como Sierra Blanca. |

## Bloque 4 — Litoral y aguas

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| Clorofila-a y turbidez | **VR** | Sentinel-3 OLCI L2 WATER | Resolución 300 m. Los productos oceánicos estándar pierden fiabilidad en aguas costeras someras, que es justamente la franja de interés. Debe declararse. |
| Temperatura superficial del mar | **V** | Sentinel-3 SLSTR | Adecuado para el buffer marino de 2 km. |
| Evolución de la línea de costa | **V** | Sentinel-2 NDWI (10 m) | Técnicamente sólido y de alto valor para un municipio litoral. Requiere corrección por estado de marea para comparar fechas. |
| Oleaje y régimen de vientos | **VR** | **CMEMS**, no Puertos del Estado | Puertos del Estado **no ofrece API REST pública documentada**; la descarga es por formulario, máximo 5 series por petición, no automatizable de forma fiable. Se propone Copernicus Marine como fuente automatizable y Puertos del Estado como contraste puntual. |

## Bloque 5 — Energía y atmósfera

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| Radiación solar global horizontal | **V** | PVGIS v5_3 (JRC) | Verificado y operativo. **Sin registro ni cuota.** Serie mensual SARAH3 + ERA5. La fuente de menor fricción de todo el proyecto. |
| Potencial fotovoltaico en cubiertas | **NV** *(como serie)* | LiDAR PNOA + PVGIS | Determinación puntual, no serie. Además exige procesado pesado de nube de puntos y cartografía de edificación. **Alcance muy superior al resto de indicadores**; debe tratarse como línea de trabajo propia, no como un indicador más. |
| NO₂ troposférico | **VR** | Sentinel-5P | Píxel de 5,5 × 3,5 km ≈ 19 km². Sobre 117 km² son **del orden de 6 píxeles**. No permite lectura municipal fina. Publicable únicamente como tendencia y estacionalidad de ámbito comarcal, nunca como mapa municipal. |
| Emisiones evitadas por potencial solar | **VR** | Derivado | Cálculo derivado, no medición. Depende del potencial FV, que no es viable como serie. Debe publicarse como estimación con hipótesis explícitas o posponerse. |

## Bloque transversal — Presión turística

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| Correlación pernoctaciones ↔ NDVI / LST | **V** | INE Tempus3 (EOH) + Sentinel-2/3 | Ambas series verificadas. **Prioritario: es el elemento diferencial del observatorio.** La oposición de fase ya es visible en los datos preliminares (NDVI mínimo en agosto, máximo turístico en agosto). |
| Indicadores ambientales por plaza hotelera | **V** | INE Tempus3 + series ambientales | Normalización directa. |
| Estacionalidad ambiental vs turística | **V** | INE Tempus3 + Sentinel-2 | Amplitud NDVI intraanual medida: 0,187 puntos. |

**Advertencia técnica sobre INE Tempus3.** El campo `Fecha` de la API se expresa en hora de
Madrid; interpretado como UTC desplaza la serie un mes completo. Debe construirse el periodo a
partir de los campos `Anyo` y `FK_Periodo`, nunca de `Fecha`.

---

## Resumen

| Estado | Indicadores |
|---|---|
| **V** — Viable | 10 |
| **VR** — Viable con reservas | 11 |
| **P** — Pendiente de resolver fuente | 3 |
| **NV** — No viable como se plantea | 3 |

## Cuestiones que requieren decisión

1. **Puntos calientes por barrio (Bloque 2).** No es viable con Copernicus. ¿Se incorpora
   Landsat 8/9 como fuente adicional, o se descarta el indicador?
2. **Potencial fotovoltaico en cubiertas (Bloque 5).** Su alcance excede al del resto de
   indicadores. ¿Línea de trabajo separada o fuera del alcance?
3. **Altura de vegetación y LiDAR (Bloque 1).** ¿Se acepta como determinación puntual sin
   serie temporal?
4. **Oleaje (Bloque 4).** ¿Se sustituye Puertos del Estado por CMEMS, con el registro
   adicional que ello supone?
