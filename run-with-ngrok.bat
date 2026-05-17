@echo off
chcp 65001 >nul
echo.
echo === EduAI: backend + frontend + ngrok (для Ultravox RAG) ===
echo.

where ngrok >nul 2>&1
if errorlevel 1 (
  echo [ОШИБКА] ngrok не найден. Установите: winget install Ngrok.Ngrok
  pause
  exit /b 1
)

echo Запуск бэкенда на порту 8000...
start "Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 4 /nobreak >nul

echo Запуск туннеля (cloudflared) и обновление .env ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\scripts\start-tunnel.ps1"
if errorlevel 1 (
  echo.
  echo Установите cloudflared: winget install Cloudflare.cloudflared
  echo Или ngrok: setup-ngrok.ps1 + start-tunnel.ps1 -Provider ngrok
  pause
  exit /b 1
)

timeout /t 2 /nobreak >nul

echo Запуск фронтенда...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Готово. Не закрывайте процесс туннеля — иначе RAG в голосе перестанет работать.
pause
