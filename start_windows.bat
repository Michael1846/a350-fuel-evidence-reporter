@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or 3.12 (64-bit) required. https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 py -3.12 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo Could not create Python virtual environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -q -r requirements-lock.txt
if errorlevel 1 (echo Dependency installation failed. & pause & exit /b 1)
".venv\Scripts\python.exe" app.py
pause
