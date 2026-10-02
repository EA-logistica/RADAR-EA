$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force data/logs | Out-Null
if (-not (Test-Path .env)) { Set-Content .env 'DATABASE_URL=postgresql+psycopg://radar:radar_local@localhost:54329/radar' -Encoding utf8 }
if (-not (Test-Path node_modules/embedded-postgres)) { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Falló PostgreSQL portátil' } }
$taskDb = $null
try { $taskProbe = [System.Net.Sockets.TcpClient]::new('127.0.0.1',54329); $taskProbe.Dispose() }
catch { $taskDb = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'scripts/local-db.mjs' -WindowStyle Hidden -PassThru -RedirectStandardOutput data/logs/postgres.out.log -RedirectStandardError data/logs/postgres.err.log }
try {
    $taskReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        try { $taskSocket = [System.Net.Sockets.TcpClient]::new('127.0.0.1',54329); $taskSocket.Dispose(); $taskReady = $true; break } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $taskReady) { throw 'PostgreSQL no inició. Ver data/logs/postgres.err.log' }
    & ./scripts/start-local.ps1
} finally {
    if ($null -ne $taskDb -and -not $taskDb.HasExited) {
        $taskControl = Join-Path (Get-Location) 'node_modules/@embedded-postgres/windows-x64/native/bin/pg_ctl.exe'
        if (Test-Path $taskControl) { & $taskControl -D .runtime/postgres stop -m fast }
        Stop-Process -Id $taskDb.Id -ErrorAction SilentlyContinue
    }
}
