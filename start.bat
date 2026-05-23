@echo off
echo ==============================================
echo        Zapusk AI-chata (Backend + Frontend)
echo ==============================================

echo Zapusk backend (FastAPI)...
start "Backend" cmd /k "cd backend && call uvicorn app.main:app --reload"

echo Zapusk frontend (Vue)...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo ==============================================
echo Frontend dostupen po adresu: http://localhost:5173
echo ==============================================
pause
