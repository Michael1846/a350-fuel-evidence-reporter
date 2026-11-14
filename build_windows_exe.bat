@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
if not exist ".venv\Scripts\python.exe" (echo Python 3.11 x64 is required & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 (echo Dependency installation failed & pause & exit /b 1)
".venv\Scripts\python.exe" scripts\prepare_windows_runtime.py
if errorlevel 1 (echo Official Windows runtime preparation failed & pause & exit /b 1)
".venv\Scripts\python.exe" scripts\collect_licenses.py
if errorlevel 1 (echo License collection failed & pause & exit /b 1)
".venv\Scripts\python.exe" scripts\run_checks.py
if errorlevel 1 (echo Tests failed & pause & exit /b 1)
".venv\Scripts\python.exe" scripts\package_release.py --build
if errorlevel 1 (echo EXE build failed & pause & exit /b 1)
echo Local candidate packages are in release. Public release requires the checklist.
pause
