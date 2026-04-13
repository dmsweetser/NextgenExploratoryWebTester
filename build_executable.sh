#!/bin/bash

echo "Building Windows and Linux executables for NEWT..."
echo ""

# Check if pyinstaller is available
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller is not installed."
    echo "Please install pyinstaller first: pip install pyinstaller"
    exit 1
fi

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not detected."
    echo "Trying to activate it..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo "Error: No virtual environment found."
        exit 1
    fi
fi

# Build Linux executable
echo "Building Linux executable with PyInstaller..."
pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" app.py

if [ $? -ne 0 ]; then
    echo "Error: PyInstaller build failed."
    exit 1
fi

# Move Linux executable to the project root
if [ -f "dist/app" ]; then
    chmod +x "dist/app"
    mv "dist/app" "NEWT"
    echo "Executable created: NEWT"
    echo ""
    echo "To run NEWT, execute: ./NEWT"
    echo ""
    echo "To create a .env file, copy .env.example to .env and edit as needed."
else
    echo "Error: Executable not found in dist folder."
    exit 1
fi

# Build Windows executable (using Wine if available)
echo "Building Windows executable..."
if command -v wine &> /dev/null; then
    echo "Wine found. Building Windows binary..."

    # Create a batch file to run PyInstaller for Windows
    cat > build_windows.bat << EOF
@echo off
pyinstaller --onefile --windowed --add-data "templates;templates" --add-data "static;static" app.py
EOF

    # Run the batch file using Wine
    wine build_windows.bat

    if [ $? -eq 0 ]; then
        # Check if the Windows executable was created
        if [ -f "dist/app.exe" ]; then
            mv "dist/app.exe" "NEWT-win.exe"
            echo "Windows executable created: NEWT-win.exe"
            echo ""
            echo "To run NEWT on Windows, execute: NEWT-win.exe"
        else
            echo "Error: Windows executable not found in dist folder."
        fi
    else
        echo "Error: Windows build failed."
    fi

    # Clean up the batch file
    rm -f build_windows.bat
else
    echo "Wine not found. Skipping Windows build."
fi

# Clean up
rm -rf build
rm -rf dist
rm -f "*.spec"

echo "Build complete!"
exit 0
