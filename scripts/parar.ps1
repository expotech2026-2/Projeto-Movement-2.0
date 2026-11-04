$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$processFile = Join-Path $projectRoot '.local\logs\processos.json'
if (-not (Test-Path -LiteralPath $processFile)) { Write-Host 'Nenhum processo registrado.'; return }
$projectProcesses = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'node.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    ($_.CommandLine -like '*uvicorn*app.main:create_app*' -or $_.CommandLine -like '*vite*bin*vite.js*')
}
foreach ($projectProcess in $projectProcesses) {
    Stop-Process -Id $projectProcess.ProcessId -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $processFile
Write-Host 'Servidores deste projeto encerrados. O banco de dados foi preservado.'
