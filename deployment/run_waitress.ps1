param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5000
)

$env:ELD_HOST = $HostName
$env:ELD_PORT = "$Port"
$env:ELD_DEBUG = "0"

if (-not $env:ELD_ADMIN_PASSWORD) {
    Write-Host "[WARN] ELD_ADMIN_PASSWORD is not set. The app will use the local default password."
}

python serve.py
