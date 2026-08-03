# Metodología — Observatorio de Sostenibilidad Territorial de Marbella

**Fase 0 — Diseño y validación de fuentes**
Fecha de redacción: 3 de agosto de 2026
Ámbito: Marbella (código INE 29069), provincia de Málaga, Andalucía

---

## 1. Objeto

El presente documento recoge el diseño de arquitectura del Observatorio de Sostenibilidad
Territorial de Marbella y el resultado de la verificación empírica de las fuentes de datos
abiertas previstas. Toda afirmación de disponibilidad contenida en este documento procede de
una consulta real al servicio correspondiente, ejecutada en la fecha indicada. No se ha
asumido la existencia de ningún endpoint sin comprobarla.

## 2. Ámbito territorial

El límite municipal se obtiene del Centro Nacional de Información Geográfica mediante el
servicio WFS INSPIRE de Unidades Administrativas, seleccionando la unidad de código nacional
`34012929069`.

| Parámetro | Valor |
|---|---|
| Superficie calculada | 11.714,2 ha |
| Superficie oficial PGOM 2025 | 11.714 ha |
| Geometría | MultiPolygon, 1 polígono |
| BBox EPSG:25830 | 319.549,0 – 4.036.789,3 – 345.030,8 – 4.047.224,7 |
| BBox EPSG:4326 | −5,014670 – 36,459530 – −4,730700 – 36,554970 |
| Extensión aproximada | 25,5 km (E–O) × 10,4 km (N–S) |

La coincidencia entre la superficie calculada sobre la geometría descargada y la superficie
oficial recogida en el PGOM constituye la validación de la capa de referencia. Todos los
cálculos de superficie del observatorio se realizan sobre esta geometría en EPSG:25830.

## 3. Sistemas de referencia

Se emplean tres sistemas de referencia con funciones diferenciadas:

| Uso | EPSG | Justificación |
|---|---|---|
| Cálculo de superficies y estadística zonal local | 25830 | ETRS89 / UTM 30N, sistema oficial en España peninsular |
| Petición a Sentinel Hub | 32630 | **Impuesto por el servicio**, véase apartado 5.1 |
| Publicación de geometrías al frontend | 4326 | Requerido por Leaflet |

### 3.1 Limitación detectada en el CRS de petición

El backend de Sentinel Hub del Copernicus Data Space Ecosystem **rechaza EPSG:25830** para
las colecciones Sentinel-2, devolviendo el error
`Invalid envelope CRS. Expected: EPSG:32630, was: EPSG:25830`. Las peticiones de procesamiento
deben formularse en EPSG:32630 (WGS84 / UTM 30N).

La diferencia entre ETRS89 y WGS84 en la península ibérica en 2026 es del orden de 0,5 m, muy
inferior al tamaño de píxel de trabajo (10–20 m), por lo que la agregación zonal no se ve
afectada de forma significativa. No obstante, la circunstancia queda documentada y **los
cálculos de superficie no se derivan nunca de la petición remota**, sino de la geometría local
en EPSG:25830.

## 4. Arquitectura

Se adopta una separación estricta en dos capas, sin servidor de aplicaciones ni base de datos.

### 4.1 Capa A — Pipeline de datos

Ejecución en Python 3.11+ en local o sobre GitHub Actions. Responsabilidades:

1. Consultar la disponibilidad de datos nuevos en cada fuente.
2. Comparar con el manifiesto local `data/metadata/manifest.json`.
3. Procesar exclusivamente el incremento.
4. Reducir el resultado a series temporales ligeras en JSON o CSV.
5. Registrar la ejecución y actualizar la ficha de metadatos del indicador.

El principio rector es la **agregación en origen**. Cuando el servicio lo permite, la
reducción de ráster a estadístico se realiza en el servidor del proveedor y no se descarga
ningún ráster. Este criterio es determinante para el consumo de cuota (apartado 5.2).

### 4.2 Capa B — Frontend

HTML, JavaScript y CSS sin frameworks pesados. Lee únicamente los ficheros ligeros generados
por la Capa A. Las capas visuales ráster se sirven por WMS bajo demanda, nunca se preprocesan.

### 4.3 Regla de tamaño

Ningún fichero de `data/processed/` puede superar 5 MB. Si lo supera, la reducción debe
reforzarse en la Capa A. La serie NDVI mensual completa ocupa del orden de 30 KB, muy por
debajo del umbral.

## 5. Acceso a Copernicus

### 5.1 Vía de acceso adoptada

Se ha verificado que el Copernicus Data Space Ecosystem ofrece las colecciones necesarias
a través de openEO (83 colecciones disponibles, entre ellas `SENTINEL2_L2A`,
`SENTINEL3_SLSTR_L2_LST`, `SENTINEL_5P_L2` y `SENTINEL1_GRD`).

Para los indicadores de serie temporal agregada se adopta, sin embargo, la **Statistical API
de Sentinel Hub**, por resultar más eficiente: devuelve directamente la serie estadística
agregada sobre el polígono municipal en formato JSON, sin transferencia de ráster. openEO se
reserva para los productos que requieran salida ráster o composición multitemporal compleja.

### 5.2 Consumo de cuota verificado

La cuenta dispone del plan gratuito del Copernicus Data Space Ecosystem:

| Recurso | Cuota mensual |
|---|---|
| Unidades de proceso (PU) openEO | 10.000 |
| Unidades de proceso (PU) Sentinel Hub | 10.000 |
| Peticiones Sentinel Hub | 50.000 |
| Transferencia de datos | 12 TB / 30 días |

**No existe facturación automática por exceso de cuota.** Al agotarse, el servicio deja de
atender peticiones hasta el siguiente periodo. El proyecto no incurre por tanto en riesgo de
gasto.

Medición real efectuada sobre el indicador NDVI:

- 19 intervalos mensuales, resolución 20 m, polígono municipal completo: **96,4 PU**
- Coste unitario: **≈ 5,1 PU por mes de serie**
- Carga histórica completa (enero 2017 – julio 2026, 115 meses): **≈ 585 PU**
- Actualización mensual en régimen permanente: **≈ 5 PU**

El margen es amplio. Aun añadiendo los indicadores de LST, NDWI, NDBI y NO₂ con el mismo
patrón, el consumo previsto se mantiene en torno al 10–15 % de la cuota mensual.

### 5.3 Cobertura Sentinel-2

Marbella queda cubierta **íntegramente por un solo tile, T30SUF**, lo que elimina la necesidad
de mosaicar entre tiles. En julio de 2026 se registraron 19 escenas L2A sobre el ámbito,
procedentes de las unidades S2A, S2B y S2C. La revisita efectiva es de 2 a 3 días.

## 6. Metodología del indicador NDVI

Índice de vegetación de diferencia normalizada, calculado sobre Sentinel-2 L2A:

```
NDVI = (B08 − B04) / (B08 + B04)
```

**Enmascaramiento.** Se emplea la banda de clasificación de escena (SCL) del producto L2A. Se
consideran válidas únicamente las clases 4 (vegetación), 5 (suelo desnudo) y 7 (sin
clasificar). Se excluyen explícitamente nubes, cirros, sombras de nube, agua, nieve y píxeles
saturados. Los píxeles con denominador nulo se descartan, dado que generan valores no finitos
que interrumpen la ejecución del servicio.

**Agregación temporal.** Intervalo mensual (`P1M`) con criterio de mosaico `leastCC`, que
selecciona para cada píxel la observación menos afectada por nubosidad dentro del mes. El
valor mensual es por tanto un **compuesto**, no una observación de fecha única. Esta
circunstancia debe constar en la ficha del indicador.

**Resolución de trabajo.** 20 m. Se ha optado por 20 m en lugar de los 10 m nativos de las
bandas B04 y B08 porque duplicar la resolución cuadruplica el consumo de PU sin aportar
precisión relevante a un estadístico agregado sobre 117 km².

**Cobertura efectiva.** El recuento de píxeles válidos se mantiene estable en torno a 292.000
por mes, equivalente a 116,8 km², coherente con la superficie municipal de 117,1 km². El
mosaico mensual resuelve satisfactoriamente la nubosidad en este ámbito.

### 6.1 Resultado preliminar y lectura

Serie mensual 2025 (valores medios municipales):

| Mes | NDVI | Mes | NDVI |
|---|---|---|---|
| Enero | 0,593 | Julio | 0,419 |
| Febrero | 0,590 | Agosto | 0,406 |
| Marzo | 0,558 | Septiembre | 0,422 |
| Abril | 0,557 | Octubre | 0,431 |
| Mayo | 0,450 | Noviembre | 0,525 |
| Junio | 0,433 | Diciembre | 0,543 |

El perfil responde a la fenología mediterránea: máximo invernal asociado al periodo de lluvias
y mínimo estival por agostamiento. La amplitud intraanual es de 0,187 puntos de NDVI.

**Este comportamiento es de signo opuesto a la curva de ocupación turística**, que alcanza su
máximo en los meses de menor actividad vegetativa. La cuantificación de esta oposición
constituye el objeto del bloque transversal.

## 7. Estrategia de actualización

Se descarta el reprocesado íntegro de la serie. El pipeline opera por incremento, contrastando
la disponibilidad en origen contra `data/metadata/manifest.json`. Si no hay dato nuevo, la
ejecución termina sin commit.

Los flujos se separan por cadencia real de publicación de cada fuente, no en un único
workflow: diario, semanal, mensual y trimestral. Todos admiten disparo manual.

Si una fuente falla, el flujo registra el error, continúa con las restantes y abre una
incidencia en el repositorio. El sitio muestra en todo caso el último dato válido con su fecha.

## 8. Tratamiento de huecos de serie

**No se interpolan huecos.** Si un mes carece de observación válida, la serie lo refleja
explícitamente como ausencia y el frontend lo representa como discontinuidad, no como línea
continua. Cualquier valor estimado, en caso de introducirse en el futuro, deberá ir marcado
con un campo `estimado: true` y quedar visualmente diferenciado.

## 9. Limitaciones generales declaradas

1. La resolución de Sentinel-3 (1 km) y de Sentinel-5P (5,5 × 3,5 km) es insuficiente para el
   análisis intraurbano en un municipio de 117 km². Véase la matriz de viabilidad.
2. Los productos de cadencia plurianual (CORINE, Imperviousness) no constituyen series
   temporales densas, sino cortes comparables espaciados años.
3. Los productos derivados de LiDAR no son series temporales, sino determinaciones puntuales.
4. El fuerte gradiente altitudinal entre la línea de costa y Sierra Blanca hace que la media
   municipal de NDVI y LST oculte comportamientos contrapuestos. La estratificación por
   altitud mediante MDT es necesaria para la interpretación, no opcional.

## 10. Documentos asociados

- `docs/matriz-viabilidad.md` — evaluación indicador por indicador
- `docs/fuentes.md` — endpoints verificados y condiciones de licencia
- `data/metadata/` — ficha individual por indicador
