@echo off
REM Vehicle Counting AI — Start Script (Windows)

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the application
python main.py
