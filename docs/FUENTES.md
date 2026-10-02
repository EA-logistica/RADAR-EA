# Investigación de fuentes — 1 de octubre de 2026 (Perú)

Investigación realizada antes de implementar los adaptadores. No se presume cobertura nacional completa ni actualización en tiempo real.

## 1. Bases oficiales de regímenes definitivos (prioridad)

- Índice: http://www.aduanet.gob.pe/aduanas/informae/presentacion_bases_web.htm
- Diccionario descargado: http://www.aduanet.gob.pe/aduanas/informae/estructura_bases.xls
- La página anuncia publicación cada siete días y permanencia durante dos meses. Esto es una declaración del portal, no un SLA verificado.
- En la inspección se listan archivos desde 20–26 julio hasta 21–27 septiembre de 2026. No se infiere que todos los años estén disponibles.
- Descargados para verificar: `ma21270926.zip` (formato A) y `mb21270926.zip` (formato B). Ambos contienen DBF.
- MA: aduana, año, declaración, serie, fecha de numeración, documento y razón social del importador, subpartida, cinco descripciones, origen/adquisición, FOB de la serie, flete, seguro, peso neto/bruto, cantidades/unidades, tributos, fecha de modificación.
- MB: clave de declaración, secuencia y código de proveedor, nombre de proveedor, partida, número de ítem, descripción, marca, modelo, cantidad/unidad, origen y valores FOB. El cruce ítem/serie necesita validación de subpartida y valor agregado; las correspondencias ambiguas deben quedar pendientes, sin multiplicar las series MA.
- Sin autenticación observada para descargar. HTTP disponible; el acceso HTTPS falló en el buscador. Se conservan URL, checksum y originales; HTTP no proporciona autenticidad criptográfica del servidor.
- El diccionario tiene columnas desplazadas en parte del formato A: se usan nombres reales de cabecera DBF, no posición visual del Excel.
- No se ha verificado una API oficial de acceso masivo que sustituya estos archivos.
- Comprobación posterior al ETL: los proveedores MB de las 1.700 series seleccionadas de cuatro semanas están redactados como `No Disponible`. El campo existe en el esquema, pero **no contiene identidades aprovechables en esta muestra**.

## 2. Consulta detallada por importador o subpartida (Playwright)

http://www.aduanet.gob.pe/cl-ad-consdepa/ConsImpoIAServlet?accion=cargarConsulta&tipoConsulta=14

Formulario verificado: `fec_inicio`, `fec_fin`, selector `tipo` (1 importador, 5 partida), `documento`, botón `btnConsultar`. Permite exportar a Excel. Fechas dd/mm/yyyy.

Se reprodujo la consulta RUC 20100367395 del 22/09/2026 al 01/10/2026: declaración 118-26-484781, serie 1, 28/09/2026, partida 3901200000, 24 750 kg, FOB de serie USD 27 690,57, origen US. No se ha verificado el horizonte histórico completo ni el máximo de resultados.

La tabla tiene 35 columnas y dos bloques de valores: total de declaración y serie. Nunca sumar los primeros montos repetidos ni dividir FOB total entre peso de una serie. La consulta muestra RUC, no necesariamente razón social, y no ofrece proveedor en esas columnas.

Se conservan las páginas y la exportación original. Hay paginación; el extractor debe detectar cobertura incompleta, controles de acceso, cambios de esquema y errores. La frecuencia de actualización no está publicada en el formulario inspeccionado. Fecha de numeración no equivale a llegada física.

## 3. Consulta individual de DUA

Enlace real observado: http://www.aduanet.gob.pe/servlet/SgCDUI2?codaduana=118&numecorre=484781&&anoprese=2026&option=una&n=10

Presenta CAPTCHA. No se automatiza su resolución ni se utiliza como dependencia de la carga masiva. Radar puede abrir el enlace para consulta humana. No se atribuyen campos no observados.

## 4. Estadísticas agregadas

https://www.sunat.gob.pe/estadisticasestudios/importaciones.html

Cuadros F1–F16 con descargas; F11 por subpartida y F15 por actividad/principales importadores. Útiles para contrastes agregados. No sustituyen microdatos ni permiten deducir proveedores o grados. Cobertura y revisión deben leerse en cada archivo; no se confirmó el calendario de publicación.

## Criterios de producto

- Importación declarada para consumo; no representa todos los manifiestos, tránsitos ni regímenes.
- FOB USD/kg y CIF declarado (FOB + flete + seguro) se mantienen separados. Ninguno es costo final en almacén.
- Proveedor, fabricante y marca son conceptos distintos.
- No se deduce equivalencia técnica entre grados. Las coincidencias de búsqueda son textuales o por términos relacionados.
- La cobertura mostrada debe ser la de los archivos y consultas cargados, con faltantes y revisiones visibles.
