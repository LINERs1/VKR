@echo off
echo ========================================
echo    EduAI - Запуск двух сервисов
echo ========================================
echo.
echo [1/2] Запуск AI Service (порт 8000)...
start "AI Service" cmd /k "cd /d %~dp0ai_service && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Запуск Platform Service (порт 8001)...
start "Platform Service" cmd /k "cd /d %~dp0platform_service\backend && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 3 /nobreak >nul

echo.
echo [3/3] Запуск Frontend (Vite, порт 5173)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  AI Service:       http://localhost:8000/docs
echo  Platform Service: http://localhost:8001/docs
echo  Frontend:         http://localhost:5173
echo ========================================

echo Opening Browser...
start http://localhost:5173

pause
