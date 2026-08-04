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
| LST media estival e invernal | **V** *(publicado)* | **Landsat 8/9 C2 L2, banda ST_B10** | **Publicado en Fase 2**, a 30 m. 115 periodos (2017-2026) con 14 huecos declarados, de 316 escenas. Enero 17,1 °C, agosto 38,6 °C. Se descartó Sentinel-3 (1 km y sin máscara de nubes defendible); el intento queda documentado más abajo. |
| Delta de isla de calor urbana | **V** | Landsat 8/9 + máscara de usos del suelo | Desbloqueado en Fase 2: con 30 m el contraste urbano/periurbano es medible. Falta la máscara de usos del suelo que separe ambas zonas; el candidato es CLMS Land Cover a 10 m. La infraestructura de LST ya está en producción. |
| Mapa de puntos calientes por barrio | **V** | Landsat 8/9 (30 m) | **Deja de ser inviable.** Con Sentinel-3 un barrio era un único píxel; con la rejilla de 30 m de Landsat caben del orden de mil por barrio. Requiere pasar de estadística municipal a salida ráster o por polígonos de barrio, que es trabajo de Fase 4. |
| Serie de temperatura y precipitación | **V** | AEMET OpenData + ERA5 | Servicio AEMET verificado y operativo. **Requiere clave gratuita, aún no dada de alta.** ERA5 exige registro adicional en el Climate Data Store. |
| Evapotranspiración | **VR** | **CLMS vía openEO**, no REDIAM | Revisado en Fase 2. El catálogo GeoNetwork de REDIAM **sí es consultable por API**, y en él no consta ningún servicio OGC de evapotranspiración; sus productos climáticos son **normales estáticas 1971-2000**, útiles como contexto pero no como serie. La alternativa es `CLMS_ETA_GLOBAL_300M_10DAILY_V1` (300 m, decadal), pero **su serie arranca en noviembre de 2025**: nueve meses, insuficiente para leer tendencia. Publicable solo como valor reciente, declarando la brevedad de la serie. |

## Bloque 3 — Suelo y urbanización

| Indicador | Estado | Fuente | Observaciones |
|---|---|---|---|
| Superficie sellada, evolución | **P** | CLMS Imperviousness | Endpoint no resuelto. Además, cadencia trienal: la «serie» tendría del orden de 6 puntos desde 2006. |
| Cambios de usos del suelo | **V** | **CLMS Land Cover 10 m anual vía openEO** | Mejorado en Fase 2. `CLMS_LCM_GLOBAL_10M_YEARLY_V1` da usos del suelo a **10 m con cadencia anual desde 2020**: seis cortes comparables y resolución suficiente para cambio urbano fino. Sustituye a CORINE como fuente principal (25 ha de unidad mínima y ~6 años de cadencia), que queda como serie histórica larga de contexto. |
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
| Radiación solar global horizontal | **V** *(publicado)* | PVGIS v5_3 (JRC) | **Publicado en Fase 3.** Sin registro ni cuota. 228 meses (2005-2023), 1.886 kWh/m² anuales de media municipal. Se muestrean nueve puntos del término, no un único centroide, para recoger el gradiente costa-sierra. **Es un reanálisis de recorrido cerrado**: termina en 2023 y no crece mes a mes; el sitio lo declara para no presentarlo como desactualizado. |
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

## LST con Sentinel-3: por qué se descartó esa vía

El indicador acabó publicándose con Landsat. Se conserva aquí el recorrido con Sentinel-3
porque sigue siendo pertinente para el Bloque 4: sobre el mar, 1 km de resolución sí basta,
y quien retome esa vía se ahorrará el camino andado.

**Lo que sí quedó resuelto:**

1. **Vía de acceso.** Sentinel Hub solo expone las bandas de temperatura de brillo de
   Sentinel-3 (S7-S9). Convertirlas a LST exigiría implementar una corrección de emisividad
   propia. El producto oficial `SENTINEL3_SLSTR_L2_LST` está en openEO y evita ese problema.
2. **Autenticación.** Las credenciales de Sentinel Hub sirven para openEO, pero **solo si el
   token se pide con `scope=openid`**; sin él, el servicio responde 403 `TokenInvalid`.
3. **Separación día/noche.** Sentinel-3 sobrevuela hacia las 10:30 y hacia las 22:00.
   Promediar ambas pasadas produce una media sin significado físico. Se separan con la banda
   `sunZenithAngles` (cenital < 85° es día). Diferencia medida: del orden de 5 °C.

**Lo que bloquea la publicación.** Enero de 2026, media municipal diurna:

| Tratamiento | Valor | Lectura |
|---|---|---|
| Sin máscara | 1,9 °C | Imposible: la temperatura del aire en Marbella en enero ronda 10-17 °C y la LST diurna debe ser superior |
| `exception == 0` | 2,2 °C | Apenas cambia: **esa banda no marca nubosidad** |
| `exception == 0` y LST > 0 °C | 13,4 °C | Plausible, pero **obtenido recortando la cola fría de la distribución** |

El tercer tratamiento produce una cifra creíble por construcción, no por haber identificado
nubes: sube la media porque descarta los valores bajos. Es una aproximación no documentada y
queda descartada.

**Vía pendiente.** La máscara correcta está en la banda `confidence_in`, que es un mapa de
bits con los indicadores de nubosidad de SLSTR. Falta decodificar sus bits y validar el
resultado contra la climatología conocida del municipio.

**Coste operativo, además.** Las peticiones síncronas a openEO tardan del orden de 200 s por
trimestre y fallan de forma intermitente con 500 y con cierres de conexión. La carga
histórica de 115 meses exigiría trabajar con trabajos por lotes, no con peticiones síncronas.

## Resumen

| Estado | Indicadores |
|---|---|
| **V** — Viable | 11 |
| **VR** — Viable con reservas | 11 |
| **P** — Pendiente de resolver | 3 |
| **NV** — No viable como se plantea | 3 |

De ellos, **publicado y en producción: 1** (NDVI medio municipal, Fase 1).

## Revisión de Fase 2 (4 de agosto de 2026)

El acceso a openEO cambió el cuadro respecto a la evaluación inicial:

- **El catálogo CLMS es accesible por openEO**, no solo por la vía de descarga autenticada
  que bloqueó la evaluación de Fase 0. Eso resuelve la fuente de usos del suelo (10 m
  anuales desde 2020) y abre una alternativa para evapotranspiración, aunque con serie corta.
- **REDIAM no publica evapotranspiración como servicio OGC.** Su catálogo GeoNetwork sí es
  consultable por API (`portalrediam.cica.es/geonetwork/srv/api/search/records/_search`), lo
  que elimina la necesidad de adivinar nombres de servicio. Sus productos climáticos son
  normales estáticas 1971-2000: contexto cartográfico, no series.
- **No hay modelo digital de elevaciones accesible por las vías gratuitas de CDSE.** Sentinel
  Hub responde que las colecciones DEM se sirven desde `services.sentinel-hub.com`, que es la
  plataforma comercial, y openEO no expone ninguna colección de elevación. La estratificación
  por altitud que exige el ámbito de Marbella deberá apoyarse en el MDT del CNIG, de descarga
  directa. **Queda pendiente.**

## Cuestiones que requieren decisión

1. **Puntos calientes por barrio (Bloque 2).** No es viable con Copernicus. ¿Se incorpora
   Landsat 8/9 como fuente adicional, o se descarta el indicador?
2. **Potencial fotovoltaico en cubiertas (Bloque 5).** Su alcance excede al del resto de
   indicadores. ¿Línea de trabajo separada o fuera del alcance?
3. **Altura de vegetación y LiDAR (Bloque 1).** ¿Se acepta como determinación puntual sin
   serie temporal?
4. **Oleaje (Bloque 4).** ¿Se sustituye Puertos del Estado por CMEMS, con el registro
   adicional que ello supone?
5. **LST (Bloque 2).** ¿Se invierte en decodificar la máscara `confidence_in` de SLSTR, o se
   salta directamente a Landsat 8/9, que resuelve a la vez la resolución y el detalle por
   barrio?
