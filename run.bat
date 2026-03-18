@echo off
setlocal enabledelayedexpansion

REM Activate virtual environment
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Error: Unable to activate virtual environment.
    exit /b 1
)

REM Run the application
python app.py
