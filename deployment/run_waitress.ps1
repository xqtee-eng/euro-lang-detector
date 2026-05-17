param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5000
)

$env:ELD_HOST = $HostName
$env:ELD_PORT = "$Port"
$env:ELD_DEBUG = "0"

if (-not $env:ELD_ADMIN_PASSWORD) {
    Write-Error "ELD_ADMIN_PASSWORD is required when ELD_DEBUG=0."
    exit 1
}

if (-not $env:ELD_SECRET_KEY) {
    Write-Error "ELD_SECRET_KEY is required when ELD_DEBUG=0."
    exit 1
}

python serve.py
