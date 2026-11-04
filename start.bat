@echo off
REM Vehicle Counting AI — Start Script (Windows)

REM Run from the folder this script is in, even when double-clicked elsewhere
cd /d "%~dp0"

REM Use the virtual environment's Python directly. This does not depend on
REM activate.bat, which can be missing from a partially created venv.
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

REM Run the application
"%PY%" main.py

REM Keep the window open if the app exits with an error, so it can be read
if errorlevel 1 pause
