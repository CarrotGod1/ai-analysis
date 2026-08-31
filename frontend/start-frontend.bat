@echo off
cd /d "%~dp0"
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
)
echo.
echo Starting frontend dev server on http://localhost:5173
echo (backend must be running on http://localhost:8000 for the app to work)
echo.
call npm run dev
pause
