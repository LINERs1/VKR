# Одноразовая привязка аккаунта ngrok (бесплатно: https://dashboard.ngrok.com/signup)
param(
    [Parameter(Mandatory = $true)]
    [string]$Authtoken
)

$ErrorActionPreference = "Stop"
ngrok config add-authtoken $Authtoken
Write-Host "Authtoken сохранён. Запустите: .\scripts\start-ngrok.ps1" -ForegroundColor Green
