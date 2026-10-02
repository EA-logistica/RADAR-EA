# Radar de Importaciones

Plataforma local en español para explorar importaciones peruanas de polímeros, masterbatch y aditivos, a partir de **datos reales de SUNAT**. Incluye descarga de bases oficiales, consulta Playwright, ETL auditable, PostgreSQL, API y aplicación web.

## Abrir la instalación preparada

- Aplicación: http://127.0.0.1:8000
- API documentada: http://127.0.0.1:8000/docs
- PostgreSQL portátil de desarrollo: `127.0.0.1:54329`, base activa `radar_utf8`; configuración en `.env` (instalaciones nuevas: `radar`).
- Si los procesos se detienen, ejecutar `scripts/start-portable.ps1` desde PowerShell. Conserva la base existente.

Se cargaron **10 ventanas oficiales (20/07–27/09/2026)**, todas las que ofrecía el índice consultado al ampliar el histórico. La consulta del RUC **20100367395** del 22/09 al 01/10/2026 aporta además un registro del 28/09 obtenido en vivo.

**Cobertura actual:** 4.113 series conservadas; **4.060 candidatas a materias primas plásticas y relacionados**, correspondientes a **2.229 declaraciones y 344 RUC**. Las 53 restantes siguen auditables bajo «Todos los registros cargados». No es un censo de todas las importaciones de Perú. Fecha de numeración y llegada física son diferentes.

**Proveedores:** no hay proveedores identificados en esta carga. La fuente oculta o no aporta este dato; no se infieren identidades a partir de marcas.

**Nuevo: Histórico y métricas.** Evolución diaria/semanal/mensual, comparación entre períodos, precio ponderado y percentiles, ticket, recurrencia, concentración top 5 y tabla histórica CSV. Se distinguen vacíos y ventanas parciales. Las fórmulas, criterios de comparación y limitaciones están en [docs/HISTORICO.md](docs/HISTORICO.md).

## Stack y estructura

Python 3.14 para extracción y ETL; FastAPI para una API tipada; PostgreSQL para transacciones, claves únicas y auditoría; React + TypeScript + Vite para una interfaz mantenible. Playwright usa Chromium sin ChromeDriver. La interfaz compilada se sirve desde FastAPI, por lo que no requiere dos servidores en producción local.

```
radar/                 API, normalización, adaptadores, ETL y worker
migrations/            Migraciones Alembic versionadas
web/src/               Aplicación React en español
tests/                 Pruebas unitarias e integración PostgreSQL
scripts/               Arranque, comprobación de UI y empaquetado
docs/FUENTES.md         Investigación y campos realmente observados
docs/ARQUITECTURA.md    Modelo, reglas, cobertura y operación
data/raw/              Originales, manifiestos y checkpoints (no versionados)
data/qa/               Capturas y resultados de validación local
compose.yaml           PostgreSQL + migración + API + worker
```

## Docker Compose

Requiere Docker Desktop con contenedores Linux. No estaba instalado en la máquina de entrega: la ejecución de Compose no fue verificada aquí. Sí se probaron la aplicación, el extractor y las migraciones contra PostgreSQL real.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose logs -f worker
```

Abrir http://127.0.0.1:8000 y pulsar **Actualizar datos → Bases semanales**. El worker ejecuta la carga. Alternativa desde terminal:

```powershell
docker compose exec worker python -m radar.cli bulk --weeks 4
docker compose exec worker python -m radar.cli query --kind importer --value 20100367395 --start 2026-09-22 --end 2026-10-01
```

Los volúmenes `postgres_data` y `raw_data` persisten entre reinicios. `docker compose down` detiene los servicios; no usar `down -v` si se quiere conservar la información. El puerto web está limitado a localhost y PostgreSQL no se publica al host.

## Desarrollo sin Docker

Se requiere Python 3.14, Node.js 24 y PostgreSQL 17/18. Las versiones exactas instaladas están en `requirements.lock` y ambos `package-lock.json`.

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.lock
./.venv/Scripts/python.exe -m playwright install chromium
npm.cmd --prefix web ci
npm.cmd --prefix web run build
Copy-Item .env.example .env
# Editar DATABASE_URL según la instancia PostgreSQL
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m uvicorn radar.api:app --host 127.0.0.1 --port 8000
# En otra terminal:
./.venv/Scripts/python.exe -m radar.worker
```

Para PostgreSQL portátil sólo en desarrollo: `npm.cmd ci` y `npm.cmd run db`. El servidor queda en 54329; no confundirlo con el puerto 5432 del ejemplo de PostgreSQL externo. El paquete portátil contiene PostgreSQL real y usa una versión beta del envoltorio npm; Compose usa la imagen oficial.

## Extracción, reanudación y reprocesamiento

```powershell
# Descubre enlaces publicados, descarga MA/MB y carga el catálogo inicial.
./.venv/Scripts/python.exe -m radar.cli bulk --weeks 4
# Volver a descargar para detectar reemplazos/rectificaciones en la misma URL.
./.venv/Scripts/python.exe -m radar.cli bulk --weeks 4 --force
# Todos los rubros; necesita más memoria y tiempo. La interfaz permite scope=all.
./.venv/Scripts/python.exe -m radar.cli bulk --weeks 1 --scope all
# Consulta por subpartida con paginación.
./.venv/Scripts/python.exe -m radar.cli query --kind hs --value 3901200000 --start 2026-09-21 --end 2026-09-27
# Reanudar una ejecución fallida conservando originales y checkpoints.
./.venv/Scripts/python.exe -m radar.cli resume ID_DE_EJECUCION
# Reaplicar nuevas reglas a los originales ya presentes, sin descargarlos.
./.venv/Scripts/python.exe -m radar.cli reprocess
```

Un archivo terminado se valida por SHA-256; las descargas parciales usan Range/If-Range únicamente si hay un validador HTTP. Si no existe, reinician ese archivo. Cada pareja MA/MB se confirma transaccionalmente; las consultas se dividen en ventanas de siete días. La reanudación reprocesa de forma idempotente los bloques ya cargados. Las consultas completas se guardan por ventana; una ventana interrumpida vuelve a consultar sus páginas para evitar usar una sesión expirada.

Cada ejecución queda en `runs` con parámetros, estado, errores y conteos. Los logs van a stdout/stderr (Compose o `data/logs` en el arranque portátil). El worker recoge la cola, recupera ejecuciones interrumpidas al reiniciar y permite reintentar las fallidas desde la interfaz.

## Uso

- **Panel general:** FOB, toneladas, declaraciones, RUC y proveedores identificados; evolución y rankings.
- **Histórico y métricas:** tendencias diarias, semanales o mensuales; comparación previa/personalizada; precio mediano, percentiles, ticket, volumen por operación, recurrencia, primeras observaciones y concentración; CSV con cobertura.
- **Explorar:** texto relacionado, grado, empresa, RUC, proveedor, origen, material, subpartida y fechas; página de 25 series; CSV o Excel de toda la selección hasta 100.000 filas.
- **Empresas:** historial por RUC, productos, proveedores disponibles, países y días medios entre fechas con operaciones.
- **Materiales:** importadores, proveedores, origen y FOB USD/kg ponderado por semana.
- **Comparador:** de dos a cuatro empresas bajo los mismos filtros.
- **Alertas:** novedades posteriores a la fecha máxima de la línea base; proveedor nuevo y variaciones de ±20% de FOB/kg o ±30% de peso por serie (configurable). No representan automáticamente cambios del volumen mensual total.
- **Fuentes y calidad:** archivos, checksums, períodos, faltantes, ejecuciones y reanudación.
- **Detalle de serie:** original y revisiones, enlace a DUA y corrección manual de clasificación con motivo. Una clasificación revisada no se sobrescribe al recargar.

`HDPE soplado MI 0.35` exige coincidencia de todos los conceptos; admite sinónimos como `BLOW MOLDING` y `MELT INDEX`. No completa valores MI ausentes ni certifica equivalencia técnica. Una consulta sin resultados es válida, no se rellenan ejemplos.

## Pruebas

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://radar:radar_local@localhost:54329/radar_utf8'
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe scripts/verify-ui.py
./.venv/Scripts/python.exe scripts/verify-history.py
```

Las pruebas de integración crean esquemas temporales aislados y los eliminan; no truncan tablas de Radar. Sin `TEST_DATABASE_URL` se omiten las pruebas que requieren PostgreSQL. La comprobación UI necesita la API y frontend corriendo, y genera capturas en `data/qa`.

## Límites y despliegue

La entrega está preparada para uso local. Para exponerla a un equipo se requiere HTTPS, un sistema de identidad/roles y política de copias de seguridad. `API_TOKEN` ofrece un control compartido opcional; no sustituye un sistema multiusuario. No hay envío de alertas por correo ni automatización externa programada: las alertas se calculan al cargar datos y se consultan dentro de Radar.

El catálogo de clasificación es heurístico y revisable, no una resolución arancelaria. No se garantiza exhaustividad de masterbatch/aditivos ni disponibilidad histórica más allá de los archivos publicados. La identidad de proveedor, cuando exista, se acepta únicamente con cruce consistente de declaración, ítem/serie, subpartida y FOB agregado; las ambigüedades se preservan.

El paquete ZIP contiene el código y las instrucciones, no credenciales, dependencias instaladas ni las bases descargadas. Para trasladar la instalación completa, respaldar PostgreSQL y `data/raw` conjuntamente.
