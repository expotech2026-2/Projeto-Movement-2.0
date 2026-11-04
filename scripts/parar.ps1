$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$processFile = Join-Path $projectRoot '.local\logs\processos.json'
if (-not (Test-Path -LiteralPath $processFile)) { Write-Host 'Nenhum processo registrado.'; return }
$registered = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
foreach ($processId in @($registered.ApiPid, $registered.WebPid)) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($processInfo -and $processInfo.CommandLine -like ('*' + $projectRoot + '*')) { Stop-Process -Id $processId }
    elseif ($processInfo -and $processInfo.CommandLine -like '*uvicorn app.main:create_app*') { Write-Host 'Confira o processo da API antes de encerrá-lo manualmente.' }
}
Remove-Item -LiteralPath $processFile
