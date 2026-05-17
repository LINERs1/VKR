# Туннель на локальный бэкенд (порт 8000) + запись BACKEND_PUBLIC_URL в .env
$ErrorActionPreference = "Stop"
$Port = 8000
$EnvFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"

# Уже запущен?
try {
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
    $existing = $tunnels.tunnels | Where-Object { $_.config.addr -match ":$Port" } | Select-Object -First 1
    if ($existing.public_url) {
        $url = ($existing.public_url -replace '^http:', 'https:').TrimEnd('/')
        Update-EnvPublicUrl $EnvFile $url
        Write-Host "Ngrok уже работает: $url" -ForegroundColor Green
        exit 0
    }
} catch {}

Write-Host "Запуск ngrok http $Port ... (окно оставьте открытым)" -ForegroundColor Cyan
Start-Process -FilePath "ngrok" -ArgumentList "http", $Port -WindowStyle Normal

$deadline = (Get-Date).AddSeconds(25)
$url = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 800
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
        $https = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($https.public_url) {
            $url = $https.public_url.TrimEnd('/')
            break
        }
    } catch {}
}

if (-not $url) {
    Write-Host "Не удалось получить URL. Убедитесь, что выполнен setup-ngrok.ps1 и ngrok запущен." -ForegroundColor Red
    exit 1
}

Update-EnvPublicUrl $EnvFile $url
Write-Host ""
Write-Host "BACKEND_PUBLIC_URL = $url" -ForegroundColor Green
Write-Host "Перезапустите uvicorn, чтобы подхватить .env" -ForegroundColor Yellow

function Update-EnvPublicUrl($path, $publicUrl) {
    $lines = Get-Content $path -Encoding UTF8
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match '^\s*BACKEND_PUBLIC_URL=') {
            $found = $true
            "BACKEND_PUBLIC_URL=$publicUrl"
        } else { $line }
    }
    if (-not $found) { $out += "BACKEND_PUBLIC_URL=$publicUrl" }
    Set-Content -Path $path -Value $out -Encoding UTF8
}
