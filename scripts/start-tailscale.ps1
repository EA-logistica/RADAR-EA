# Arranca Radar (PostgreSQL portatil + worker + API) y lo publica en la tailnet
# con "tailscale serve" (solo dispositivos de la tailnet, no Internet publico).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$Port = 8000
$TsPort = 10000
$Tailscale = 'C:\Program Files\Tailscale\tailscale.exe'
New-Item -ItemType Directory -Force data/logs | Out-Null

function Test-Port($p) { try { $c = [Net.Sockets.TcpClient]::new('127.0.0.1', $p); $c.Dispose(); $true } catch { $false } }

if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Falta .venv. Ejecutar primero la instalacion (ver README).' }
if (-not (Test-Path web/dist/index.html)) { & npm.cmd --prefix web run build; if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la interfaz' } }

# 1. PostgreSQL portatil (puerto 54329)
if (-not (Test-Port 54329)) {
    Write-Host 'Iniciando PostgreSQL...'
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'scripts/local-db.mjs' -WindowStyle Hidden `
        -RedirectStandardOutput data/logs/postgres.out.log -RedirectStandardError data/logs/postgres.err.log | Out-Null
    for ($i = 0; $i -lt 60 -and -not (Test-Port 54329); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Test-Port 54329)) { throw 'PostgreSQL no inicio. Ver data/logs/postgres.err.log' }
}
& ./.venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Fallo la migracion. Revisar DATABASE_URL en .env' }

# Restos de una ejecucion anterior (API o worker en segundo plano de este proyecto): se detienen para arrancar limpio.
$venvPython = (Resolve-Path .venv/Scripts/python.exe).Path
$stale = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match 'uvicorn radar\.api|-m radar\.worker' -and ($_.ExecutablePath -eq $venvPython -or $_.CommandLine -like "*$venvPython*")
}
if ($stale) {
    Write-Host "Cerrando $(@($stale).Count) proceso(s) de Radar que quedaron abiertos..."
    $stale | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    for ($i = 0; $i -lt 10 -and (Test-Port $Port); $i++) { Start-Sleep -Seconds 1 }
}
if (Test-Port $Port) { throw "El puerto $Port esta ocupado por otro programa (no es Radar). Cierralo e intenta de nuevo." }

# 2. Worker de cargas (cola de "Actualizar datos")
$worker = Start-Process -FilePath (Resolve-Path .venv/Scripts/python.exe) -ArgumentList '-m', 'radar.worker' -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput data/logs/worker.out.log -RedirectStandardError data/logs/worker.err.log

# 3. Publicacion en la tailnet
$url = "http://127.0.0.1:$Port"
if (Test-Path $Tailscale) {
    & $Tailscale serve --bg --https=$TsPort "http://127.0.0.1:$Port" | Out-Null
    $dns = ((& $Tailscale status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')
    if ($dns) { $url = "https://${dns}:$TsPort" }
}
$token = (Select-String -Path .env -Pattern '^API_TOKEN=(.*)$').Matches | ForEach-Object { $_.Groups[1].Value }
Write-Host ''
Write-Host '=========================================================='
Write-Host " Radar local:     http://127.0.0.1:$Port"
Write-Host " Radar tailnet:   $url"
if ($token) { Write-Host " Token de acceso: $token" }
Write-Host ' Cerrar esta ventana detiene Radar.'
Write-Host '=========================================================='
Start-Process $url

# 4. API + interfaz (primer plano)
try { & ./.venv/Scripts/python.exe -m uvicorn radar.api:app --host 127.0.0.1 --port $Port }
finally {
    if (-not $worker.HasExited) { Stop-Process -Id $worker.Id -ErrorAction SilentlyContinue }
    if (Test-Path $Tailscale) { & $Tailscale serve --https=$TsPort off 2>$null | Out-Null }
}
