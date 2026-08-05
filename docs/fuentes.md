# Fuentes de datos y condiciones de uso

Estado de verificación a 3 de agosto de 2026. La columna «Verificado» indica que se ha
efectuado una consulta real al servicio y se ha obtenido respuesta válida.

## 1. Endpoints verificados

| Fuente | Endpoint | Verificado | Autenticación |
|---|---|---|---|
| CDSE — Sentinel Hub Statistical API | `https://sh.dataspace.copernicus.eu/api/v1/statistics` | Sí | OAuth client credentials |
| CDSE — token OAuth | `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token` | Sí | — |
| CDSE — catálogo OData | `https://catalogue.dataspace.copernicus.eu/odata/v1/Products` | Sí | No requiere |
| CDSE — openEO | `https://openeo.dataspace.copernicus.eu/openeo/1.2/` | Sí (83 colecciones) | OIDC, **`scope=openid` obligatorio** |
| REDIAM — catálogo GeoNetwork | `https://portalrediam.cica.es/geonetwork/srv/api/search/records/_search` | Sí | No requiere |
| CNIG — WFS INSPIRE Unidades Administrativas | `https://www.ign.es/wfs-inspire/unidades-administrativas` | Sí | No requiere |
| PVGIS (JRC) | `https://re.jrc.ec.europa.eu/api/v5_3/MRcalc` | Sí | No requiere |
| INE — Tempus3 | `https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{tabla}` | Sí | No requiere |
| AEMET OpenData | `https://opendata.aemet.es/opendata/api/` | Sí (responde 401 sin clave) | Clave gratuita |
| REDIAM — WMS RENPA | `https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_RENPA` | Sí | No requiere |
| CORINE Land Cover — WMS EEA | `https://copernicus.discomap.eea.europa.eu/arcgis/services/Corine/CLC2018_WM/MapServer/WMSServer` | Sí | No requiere |
| IECA — BADEA | `https://www.juntadeandalucia.es/institutodeestadisticaycartografia/badea/` | Sí | No requiere |

## 2. Incidencias y limitaciones de servicio

**CNIG — WFS INSPIRE.** No admite el parámetro `CQL_FILTER`; su uso provoca respuesta 504.
La descarga debe hacerse por `bbox` y el filtrado por `nationalCode` en local. La respuesta
para el entorno de Marbella pesa del orden de 26 MB e incluye la jerarquía administrativa
completa (Estado, comunidad, provincia y municipios colindantes). Formato de salida: GML.
No ofrece GeoJSON.

**CDSE — Sentinel Hub.** Rechaza EPSG:25830 para colecciones Sentinel-2, exigiendo EPSG:32630.
Los parámetros `resx` y `resy` se interpretan en las unidades del CRS del `bounds`: enviando
el ámbito en EPSG:4326 se interpretan como grados. La Statistical API exige declarar la salida
`dataMask` en el `setup()` del evalscript, y aborta la ejecución completa si el evalscript
genera valores no finitos.

**CDSE — openEO.** Las credenciales de cliente de Sentinel Hub sirven también para openEO,
pero **solo si el token se solicita con `scope=openid`**; sin ese parámetro el servicio
responde 403 `TokenInvalid`. El token se presenta como `Bearer oidc/CDSE/<token>`, no como
`Bearer` a secas. Las peticiones síncronas a `/result` tardan del orden de 200 s por trimestre
y fallan de forma intermitente con 500 y con cierres de conexión: exigen reintentos, y la
carga de series históricas largas requiere trabajos por lotes.

**CDSE — modelo digital de elevaciones.** No accesible por las vías gratuitas. Sentinel Hub
responde que las colecciones DEM se sirven desde `services.sentinel-hub.com`, que es la
plataforma comercial, y openEO no expone ninguna colección de elevación. Para estratificar por
altitud debe usarse el MDT del CNIG.

**REDIAM.** Los identificadores de servicio no son deducibles por convención. De tres nombres
ensayados, únicamente `REDIAM_RENPA` existía. Cada servicio debe localizarse en el catálogo
GeoNetwork, que **sí admite consulta por API** (endpoint en la tabla anterior, POST con
Elasticsearch DSL). Los productos climáticos publicados son normales estáticas 1971-2000; no
consta servicio OGC de evapotranspiración.

**CLMS — Imperviousness y Tree Cover Density.** No se ha localizado un endpoint operativo. El
servicio histórico de `image.discomap.eea.europa.eu` responde 400. La API de descarga de
`land.copernicus.eu` exige autenticación. Pendiente de resolución.

**Puertos del Estado.** No consta API REST pública documentada. La descarga de series
oceanográficas se realiza mediante formulario en `bancodatos.puertos.es`, con un máximo de
5 series por petición. No es una vía automatizable de forma fiable.

## 3. Cuotas

Copernicus Data Space Ecosystem, plan gratuito:

- 10.000 unidades de proceso mensuales en openEO
- 10.000 unidades de proceso mensuales en Sentinel Hub
- 50.000 peticiones mensuales a Sentinel Hub
- 12 TB de transferencia en ventana móvil de 30 días

**No existe facturación automática por exceso.** Agotada la cuota, el servicio deja de atender
peticiones hasta el siguiente periodo. El proyecto no incurre en riesgo de gasto.

Consumo medido del indicador NDVI: 5,1 PU por mes de serie.

## 4. Condiciones de uso y atribución

**Copernicus.** Datos gratuitos y abiertos conforme al Reglamento Delegado (UE) n.º 1159/2013
y al Reglamento (UE) n.º 377/2014. Atribución requerida:
*«Contiene datos modificados de Copernicus Sentinel [año]»*.

**CNIG / Instituto Geográfico Nacional.** Los productos digitales de descarga libre se rigen
por la licencia CC BY 4.0. Atribución requerida:
*«CC BY 4.0 scne.es»* o *«Instituto Geográfico Nacional de España»*.

**AEMET.** Condiciones específicas de AEMET OpenData. Atribución requerida:
*«Elaboración propia a partir de datos de la Agencia Estatal de Meteorología»*.
El uso comercial exige consulta previa a la Agencia.

**REDIAM / Junta de Andalucía.** Condiciones de la Red de Información Ambiental de Andalucía.
Atribución requerida: *«Fuente: REDIAM. Consejería de Sostenibilidad y Medio Ambiente.
Junta de Andalucía»*.

**INE.** Reutilización libre citando la fuente conforme a la Ley 37/2007 y al Real Decreto
1495/2011. Atribución requerida: *«Instituto Nacional de Estadística»*.

**PVGIS / JRC.** Uso libre con atribución al Joint Research Centre de la Comisión Europea.

**IECA.** Atribución: *«Instituto de Estadística y Cartografía de Andalucía»*.

## 5. Licencia del observatorio

- **Código:** MIT
- **Datos elaborados:** CC BY 4.0, sin perjuicio de las condiciones propias de cada fuente de
  origen, que prevalecen sobre esta licencia.

Todas las atribuciones anteriores deben figurar en el pie del sitio publicado.
