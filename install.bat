@echo off
setlocal enabledelayedexpansion

echo Setting up Python virtual environment...

REM Check if Python is installed
where py > nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed. Please install Python before running this script.
    exit /b 1
)

REM Check if virtual environment directory already exists
if not exist venv (
    REM Create a virtual environment
    py -m venv venv
    if %errorlevel% neq 0 (
        echo Error: Unable to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)

REM Activate the virtual environment
call venv\Scripts\Activate.bat
if %errorlevel% neq 0 (
    echo Error: Unable to activate virtual environment.
    exit /b 1
)

echo Virtual environment activated successfully.

echo Installing required Python packages...

REM Install required Python packages
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error: Unable to install required Python packages.
    exit /b 1
)

echo Required Python packages installed successfully.

echo Installing llama.cpp with CMake...

if not exist llama.cpp (
    git clone https://github.com/ggerganov/llama.cpp
) else (
    cd llama.cpp
    git pull
    cd ..
)

cd llama.cpp
mkdir build
cd build

cmake ..
cmake --build . --config Release -j%NUMBER_OF_PROCESSORS%

cd ..\..

echo llama.cpp built successfully.
echo Binary located at: llama.cpp\build\bin\llama-cli

echo Environment setup complete.
echo To activate the virtual environment, run: venv\Scripts\Activate
