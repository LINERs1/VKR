# Подтянуть модели в Ollama на ХОСТЕ (Windows/WSL), не в Docker.
# Запуск из любой папки (нужен ollama в PATH):
#   powershell -ExecutionPolicy Bypass -File docker/pull-ollama-models.ps1

$ErrorActionPreference = "Stop"

Write-Host "Скачивание qwen2.5, qwen2.5:14b, nomic-embed-text на хосте..." -ForegroundColor Cyan

ollama pull qwen2.5
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

ollama pull qwen2.5:14b
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

ollama pull nomic-embed-text
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nГотово:" -ForegroundColor Green
ollama list
