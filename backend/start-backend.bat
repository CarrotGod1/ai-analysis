@echo off
cd /d "%~dp0"
echo Installing backend dependencies...
call pip install -r requirements.txt
echo.
echo Starting backend on http://localhost:8000
echo (requires Ollama running locally on http://localhost:11434)
echo.
call python main.py
pause
