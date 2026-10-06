@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run: python -m venv .venv
    pause
    exit /b 1
)

echo Starting JobCopilot...
".venv\Scripts\python.exe" scripts\run_web.py

echo JobCopilot stopped.
pause
