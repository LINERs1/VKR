# Публичный HTTPS-туннель на localhost:8000 (для Ultravox RAG)
# Предпочитает cloudflared (не требует версии ngrok 3.20+)
param(
    [int]$Port = 8000,
    [ValidateSet("cloudflared", "ngrok")]
    [string]$Provider = "cloudflared"
)

$ErrorActionPreference = "Stop"
$EnvFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$PidFile = Join-Path $PSScriptRoot ".tunnel.pid"

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

function Start-CloudflaredTunnel {
    $log = Join-Path $env:TEMP "cloudflared-eduai.log"
    Remove-Item $log -ErrorAction SilentlyContinue
    $proc = Start-Process cloudflared -ArgumentList @(
        "tunnel", "--url", "http://127.0.0.1:$Port",
        "--logfile", $log, "--loglevel", "info"
    ) -PassThru -WindowStyle Hidden

    $url = $null
    for ($i = 0; $i -lt 35; $i++) {
        Start-Sleep -Seconds 1
        if (-not (Test-Path $log)) { continue }
        $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
        if ($m) { $url = $m.Matches[0].Value.TrimEnd('/'); break }
    }
    if (-not $url) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "cloudflared: не удалось получить URL. Проверьте интернет и порт $Port."
    }
    Set-Content -Path $PidFile -Value "cloudflared:$($proc.Id)" -Encoding UTF8
    return $url
}

function Start-NgrokTunnel {
    $existing = $null
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
        $existing = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
    } catch {}
    if (-not $existing) {
        Start-Process ngrok -ArgumentList "http", $Port -WindowStyle Normal | Out-Null
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 800
            try {
                $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
                $existing = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
                if ($existing) { break }
            } catch {}
        }
    }
    if (-not $existing.public_url) {
        throw "ngrok: не запустился. Обновите: ngrok update (нужна версия 3.20+)"
    }
    return $existing.public_url.TrimEnd('/')
}

if ($Provider -eq "cloudflared") {
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Host "Установка cloudflared..." -ForegroundColor Yellow
        winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements | Out-Null
    }
    $publicUrl = Start-CloudflaredTunnel
} else {
    $publicUrl = Start-NgrokTunnel
}

Update-EnvPublicUrl $EnvFile $publicUrl
Write-Host ""
Write-Host "BACKEND_PUBLIC_URL = $publicUrl" -ForegroundColor Green
Write-Host "Перезапустите uvicorn. Туннель должен оставаться запущенным." -ForegroundColor Yellow
