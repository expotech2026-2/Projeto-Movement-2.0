param([switch]$BancoLocal)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Prepare o ambiente conforme README.md.' }
$occupiedPorts = Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue
if ($occupiedPorts) { throw 'A porta 8000 ou 5173 já está em uso. Confira os serviços em execução.' }
if ($BancoLocal) {
    Push-Location $projectRoot
    try { & $pythonPath -m app.localdev start; if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar PostgreSQL local.' } }
    finally { Pop-Location }
}
$logsPath = Join-Path $projectRoot '.local\logs'
New-Item -ItemType Directory -Force -Path $logsPath | Out-Null
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:create_app', '--factory', '--app-dir', ('"' + (Join-Path $projectRoot 'backend') + '"'), '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -RedirectStandardOutput (Join-Path $logsPath 'api.log') -RedirectStandardError (Join-Path $logsPath 'api-error.log') -WindowStyle Hidden -PassThru
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$webProcess = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @(('"' + $vitePath + '"'), '--host', '127.0.0.1') -WorkingDirectory (Join-Path $projectRoot 'frontend') -RedirectStandardOutput (Join-Path $logsPath 'web.log') -RedirectStandardError (Join-Path $logsPath 'web-error.log') -WindowStyle Hidden -PassThru
@{ ApiPid = $apiProcess.Id; WebPid = $webProcess.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logsPath 'processos.json') -Encoding utf8
Write-Host 'Movement: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs'
Write-Host 'Para encerrar, use scripts/parar.ps1. Logs privados em .local/logs.'
