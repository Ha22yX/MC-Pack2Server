param(
    [string]$HostName = "0.0.0.0",
    [int]$Port = 8766,
    [string]$Workspace = "data"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "C:\Python314\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$LogDir = Join-Path $Root "data"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "panel-process.log"

try {
    "Starting Pack2Serve panel on $HostName`:$Port at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Encoding utf8 -Append
    & $Python -m pack2serve.cli serve-panel --host $HostName --port $Port --workspace $Workspace *>> $LogPath
    "Panel process exited with code $LASTEXITCODE at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Encoding utf8 -Append
    exit $LASTEXITCODE
} catch {
    $_ | Out-String | Out-File -FilePath $LogPath -Encoding utf8 -Append
    exit 1
}
