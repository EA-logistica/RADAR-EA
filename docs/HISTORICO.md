# Métricas e histórico

La sección **Histórico y métricas** usa los registros reales cargados y respeta los filtros de búsqueda, empresa/RUC, proveedor, origen, material, subpartida y alcance. Las fechas son de numeración aduanera, no de llegada física.

## Períodos y cobertura

- El gráfico y la tabla permiten agrupar por día, semana de lunes a domingo o mes calendario.
- Sin fechas seleccionadas, el gráfico muestra todo lo disponible. Las tarjetas comparan los últimos 28 días hasta la última ventana semanal confirmada, con los 28 días inmediatamente anteriores. Así, una consulta aislada más reciente no hace parecer completa una semana en curso.
- Los filtros de fecha fijan el período analizado. Se puede elegir un período anterior personalizado; los accesos de 4 y 8 semanas fijan las fechas globales y «Todo el histórico» las limpia.
- Una ventana se considera respaldada cuando están registrados ambos archivos MA/MB y existe un resultado semanal confirmado en una ejecución de carga del alcance correspondiente. Tener un archivo descargado no demuestra que haya sido procesado.
- Una carga sólo de plásticos no acredita cobertura de todos los rubros. Una carga con alcance `all` sí respalda la selección de plásticos.
- Una semana puede contener rectificaciones de otras fechas. «Base cargada» describe la evidencia de publicación procesada; no garantiza exhaustividad nacional.
- Un intervalo sin registros y sin base se muestra vacío, no cero. Con una base cargada y sin filas que coincidan con el filtro, la tabla muestra cero observado. Un mes/semana recortado o sin todas sus fechas respaldadas se marca parcial.
- Se omiten porcentajes entre períodos de distinta duración, superpuestos o sin todas sus ventanas cargadas. También se omiten cuando el denominador es cero o falta. La tabla no calcula una variación atravesando una semana sin base.

## Definiciones

| Métrica | Cálculo y límite |
| --- | --- |
| Valor FOB | Suma de FOB conocido de las series filtradas; USD declarado, no costo final en almacén. |
| Toneladas | Suma de kg verificables / 1.000. |
| Operaciones | Declaraciones distintas por país, aduana, año, régimen y número. Varias series de una declaración cuentan una vez. |
| Precio ponderado | Suma FOB / suma kg **de las mismas series con USD/kg válido**. No incorpora el valor de una fila sin peso comparable. |
| Precio mediano y P25–P75 | Percentiles continuos por serie con precio válido, sin ponderación por volumen. |
| Ticket por operación | FOB conocido / declaraciones distintas. |
| Volumen por operación | Toneladas conocidas / declaraciones distintas. |
| Concentración top 5 | FOB de los cinco RUC con mayor valor / FOB con RUC identificado. |
| Importadores recurrentes | RUC con al menos dos declaraciones distintas en el período. |
| Primeras observaciones | RUC presentes en el período sin registros anteriores en la cobertura y filtro actuales. No significa nueva empresa ni primer importador del mercado. |
| RUC ya observados | Importadores del período con registros anteriores bajo el mismo filtro. |
| Días activos | Fechas distintas con al menos una serie observada. |
| Calidad | Proporciones de series con peso, precio calculable y clasificación por revisar. |
| FOB acumulado observado | Suma progresiva de los valores disponibles dentro del rango seleccionado. No completa vacíos históricos. |

Los precios agregados pueden cambiar por mezcla de materiales, grados, origen y empresas. Filtrar reduce esa mezcla, pero una coincidencia comercial nunca acredita equivalencia técnica de grados.

## Interfaz y API

Las tarjetas resumidas se incorporaron al panel general y a los perfiles de empresa/material. La página completa incluye evolución, comparación, ocho indicadores adicionales, ranking de empresas y tabla histórica exportable a CSV UTF-8.

- `GET /api/analytics`: filtros habituales y `grain=day|week|month`; admite `compare_start` y `compare_end` juntos.
- `GET /api/analytics/export`: exportación del gráfico/tabla, con estado de cobertura, fechas y nota metodológica. No es una exportación de las tarjetas de comparación personalizada.
- Pruebas: `tests/test_analytics.py` y `scripts/verify-history.py`.

## Persistencia y recuperación

Los resultados de cada ventana se guardan después del commit. Una ejecución fallida conserva todos los checkpoints anteriores y puede reanudarse sin duplicar series. Se corrigió la persistencia JSON para que no quedara únicamente la primera ventana del lote.

La instalación local antigua estaba en WIN1252. Se copió a una nueva base UTF-8, verificando igualdad de todas las filas y conservando la base anterior y una instantánea lógica JSON en `data/backups`. La configuración privada `.env` apunta a la base nueva. Las instalaciones portátiles nuevas se inicializan directamente en UTF-8. El script `scripts/migrate-utf8.py` requiere detener API y worker antes de ejecutarse.
