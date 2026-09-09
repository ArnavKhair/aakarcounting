@echo off
REM Vehicle Counting AI — Setup Script (Windows)
REM Creates virtual environment and installs dependencies.

echo === Vehicle Counting AI — Setup ===
echo.

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.10 or later from https://python.org
    pause
    exit /b 1
)

python --version
echo.

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
pip install --upgrade pip --quiet

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo === Setup Complete ===
echo.
echo To run the application:
echo   venv\Scripts\activate
echo   python main.py
echo.
echo Or simply run: start.bat
echo.
pause
