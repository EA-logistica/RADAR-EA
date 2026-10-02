# Validación realizada

Entorno Windows, Python 3.14.5, Node 24.16, PostgreSQL real 18.4 mediante paquete portátil. Validación inicial del 1 y ampliación del 2 de octubre de 2026, zona de Lima.

## Resultado

- 44 pruebas pytest aprobadas, ninguna omitida en esta ejecución (TEST_DATABASE_URL configurada).
- Migraciones desde base vacía, downgrade a base y upgrade nuevamente, en esquema aislado.
- Clasificación PE/HDPE/LDPE/LLDPE/PP/PET/masterbatch/aditivos, conflictos, EVA/PETG y exclusión de falsos candidatos alimenticios.
- Conversiones exactas de unidades, rechazo de bolsas sin factor y valores no comparables.
- Inserción idempotente, revisiones, rechazo de versiones antiguas, prioridad de fuentes, bloqueo de clasificación humana y enriquecimiento de razón social sólo por RUC exacto con evidencia.
- Consulta de API, búsqueda con sinónimos y decimales, filtros, perfiles, comparación, detalle original, corrección y exportación CSV/XLSX; escape de fórmulas en texto exportado.
- Exclusión mutua de ejecución entre CLI y worker: bloqueo por ejecución durante descargas y commits.
- Creación de originales inmutables con checksum; relectura/reprocesamiento sin duplicados.
- Compilación TypeScript y Vite completada. Vite informa un bundle JS principal de aproximadamente 699 kB antes de compresión: oportunidad de dividir gráficos en una futura optimización, no error de compilación.
- Prueba Playwright de interfaz: panel, búsqueda PP inyección, grado HB5502B, detalle, CSV, empresa, material, comparador, alertas, fuentes, formulario de carga, estado sin resultados y pantalla de 390 px. Sin errores JavaScript ni respuestas de API 4xx/5xx en los flujos comprobados.

## Verificación real de SUNAT

- Descarga oficial de cuatro parejas MA/MB: semanas terminadas el 06, 13, 20 y 27/09/2026.
- Primera carga: 1.700 series. Reglas afinadas conservan 1.649 dentro del catálogo y 51 fuera del catálogo por alcance; ninguna se elimina de la auditoría.
- Consulta por RUC 20100367395, 22/09–01/10/2026: una serie adicional real, declaración 118-2026-484781, serie 1, fecha 28/09/2026, 24.750 kg, FOB USD 27.690,57. Conservados HTML y exportación original.
- Consulta por subpartida 3901200000, 21–27/09/2026: 63 series, cuatro páginas; total declarado y filas extraídas coinciden. Las 63 ya existían y quedaron como observaciones auditables de menor prioridad: **cero inserciones duplicadas**.
- Reprocesamiento final: 1.700 registros sin cambio y una razón social enriquecida con RUC exacto (referencia a MA conservada).
- Vista de catálogo: **1.650 series, 850 declaraciones, 240 importadores**, numeración del 31/08 al 28/09/2026, FOB USD 84.684.302,956; no es un total nacional.
- Proveedores identificados: cero. Las 1.700 filas MA/MB analizadas muestran `No Disponible` en el proveedor; la fila web carece de ese campo. No se inventaron identidades.
- Se archivaron las alertas históricas iniciales generadas durante la construcción y se corrigió la línea base del primer lote; queda la nueva operación observada por consulta posterior. El respaldo de esas alertas derivadas está en `data/qa/initial-baseline-alerts.json`.

## Límites de esta comprobación

No se ejecutó Docker Compose (Docker no instalado). No se probó escala nacional multianual, una identidad de proveedor real no ocultada, autenticación multiusuario ni un despliegue público. Las rutas externas pueden cambiar; el extractor falla explícitamente ante cambios de esquema o controles de acceso.

Las pruebas dejan un aviso de deprecación de Starlette TestClient/httpx, sin afectar los resultados.

## Ampliación de métricas e histórico — 02/10/2026

- Carga histórica completada: 10 parejas MA/MB, del 20/07 al 27/09/2026. Se solicitaron hasta 12 semanas; el índice ofrecía 10. Consulta adicional del 28/09 conservada como observación parcial.
- 4.113 series conservadas, 4.060 dentro del catálogo, 2.229 declaraciones y 344 RUC. FOB observado de catálogo: USD 261.172.201,483; 191.648,962585 toneladas. No es un total nacional.
- Período de comparación por defecto: 31/08–27/09 frente a 03/08–30/08, ambos de 28 días respaldados por ventanas cargadas.
- Pruebas de métricas: denominador pareado para FOB/kg, mediana/percentiles, declaraciones distintas frente a series, recurrencia, primeras observaciones, huecos desconocidos frente a cero observado, meses incompletos, cobertura por alcance, comparación sin superposición/duración desigual y exportación CSV.
- Prueba de interrupción: conserva todos los checkpoints semanales confirmados aunque falle una ventana posterior; no sólo el primero.
- Migración de la base local antigua WIN1252 a `radar_utf8`, verificando igualdad de cada fila. Base anterior e instantánea lógica en `data/backups` conservadas. La instalación portátil nueva usa UTF-8 desde su creación.
- Playwright: histórico diario/semanal/mensual, gráfico de precio, CSV, accesos de períodos, comparación personalizada no válida, navegación a empresa y pantalla de 390 px. Se corrigió el desbordamiento de tarjetas con totales monetarios mayores.
- Evidencias locales: `data/qa/history-load-results.json`, `history-ui-results.json`, `radar-history-desktop.png` y `radar-history-mobile.png`.
