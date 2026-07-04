$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $backendRoot

$venvActivate = Join-Path $backendRoot ".venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $venvActivate) {
  . $venvActivate
}

$envFile = Join-Path $backendRoot ".env"
if (Test-Path -LiteralPath $envFile) {
  Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match "^\s*(BACKEND_HOST|BACKEND_PORT)\s*=\s*(.*?)\s*$") {
      $key = $Matches[1]
      $value = $Matches[2].Trim("'`"")
      if (-not [Environment]::GetEnvironmentVariable($key, "Process")) {
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
      }
    }
  }
}

$hostAddress = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$port = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8001 }

uvicorn app.main:app --reload --host $hostAddress --port $port
