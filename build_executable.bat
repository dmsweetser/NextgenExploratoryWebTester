@echo off
setlocal enabledelayedexpansion

echo Building Windows executable for NEWT...
echo.

REM Check if pyinstaller is available
where pyinstaller > nul 2>&1
if %errorlevel% neq 0 (
    echo Error: pyinstaller is not installed.
    echo Please install pyinstaller first: pip install pyinstaller
    exit /b 1
)

REM Check if virtual environment is active
if not defined VIRTUAL_ENV (
    echo Warning: Virtual environment not detected.
    echo Trying to activate it...
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
    ) else (
        echo Error: No virtual environment found.
        exit /b 1
    )
)

REM Build Windows executable
echo Building Windows executable with PyInstaller...
pyinstaller --onefile --windowed --add-data "templates;templates" --add-data "static;static" --add-data "models;models" --add-data "data;data" --icon="static/images/newt_icon.ico" app.py

if %errorlevel% neq 0 (
    echo Error: PyInstaller build failed.
    exit /b 1
)

REM Move Windows executable to the project root
if exist "dist\app.exe" (
    move "dist\app.exe" "NEWT.exe"
    echo Executable created: NEWT.exe
    echo.
    echo To run NEWT, execute: NEWT.exe
    echo.
    echo To create a .env file, copy .env.example to .env and edit as needed.
) else (
    echo Error: Executable not found in dist folder.
    exit /b 1
)

REM Clean up
rmdir /s /q "build"
rmdir /s /q "dist"
del /q "*.spec"

echo Build complete!
exit /b 0
