#!/bin/bash

echo "Setting up environment and installing llama.cpp..."

# --- Check Python ---
if ! command -v python3 &> /dev/null; then
    echo "Error: Python is not installed. Please install Python before running this script."
    exit 1
fi

# --- Virtual environment ---
if [ ! -d "venv" ]; then
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Unable to create virtual environment."
        exit 1
    fi
    echo "Virtual environment created successfully."
else
    echo "Virtual environment already exists."
fi

source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Unable to activate virtual environment."
    exit 1
fi

echo "Virtual environment activated."

# --- Install Python deps (non-llama) ---
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Unable to install Python packages."
        exit 1
    fi
    echo "Python packages installed."
fi

# --- Install llama.cpp with CMake ---
echo "Installing llama.cpp with CMake..."

if [ ! -d "llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp
else
    cd llama.cpp
    git pull
    cd ..
fi

# Build with CMake
cd llama.cpp
mkdir -p build
cd build

cmake ..
cmake --build . --config Release -j$(nproc)

cd ../..

echo "llama.cpp built successfully."
echo "Binary located at: llama.cpp/build/bin/llama-cli"

echo "Setup complete."
echo "To activate the virtual environment later: source venv/bin/activate"
