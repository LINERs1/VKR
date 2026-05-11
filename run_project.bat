@echo off
echo ==========================================
echo    EduAI: Запуск проекта...
echo ==========================================

:: 1. Запуск бэкенда в новом окне
echo Starting Backend...
start "EduAI Backend" cmd /k "cd backend && .\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 2. Ждем пару секунд, чтобы бэкенд начал подниматься
timeout /t 3 /nobreak > nul

:: 3. Открываем браузер
echo Opening Browser...
start http://localhost:5173

:: 4. Запуск фронтенда в текущем окне
echo Starting Frontend...
cd frontend && npm run dev

pause
