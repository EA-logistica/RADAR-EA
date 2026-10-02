$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv/Scripts/python.exe)) { python -m venv .venv }
& ./.venv/Scripts/python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python' }
& ./.venv/Scripts/python.exe -m playwright install chromium
& npm.cmd --prefix web ci
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias de la interfaz' }
& npm.cmd --prefix web run build
if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la interfaz' }
& ./.venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Revisa DATABASE_URL y el servidor PostgreSQL' }
New-Item -ItemType Directory -Force data/logs | Out-Null
$worker = Start-Process -FilePath (Resolve-Path .venv/Scripts/python.exe) -ArgumentList '-m','radar.worker' -WindowStyle Hidden -PassThru -RedirectStandardOutput data/logs/worker.out.log -RedirectStandardError data/logs/worker.err.log
try { & ./.venv/Scripts/python.exe -m uvicorn radar.api:app --host 127.0.0.1 --port 8000 }
finally { if (-not $worker.HasExited) { Stop-Process -Id $worker.Id } }
