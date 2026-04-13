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

# Create release directories
mkdir -p dist/release/Linux
mkdir -p dist/release/Windows

# Copy .env.example to release directories
cp .env.example dist/release/Linux/.env.example
cp .env.example dist/release/Windows/.env.example

# Build Linux executable
echo "Building Linux executable with PyInstaller..."
pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" --distpath dist/release/Linux app.py

if [ $? -ne 0 ]; then
    echo "Error: PyInstaller build failed."
    exit 1
fi

# Move Linux executable to the project root
if [ -f "dist/release/Linux/app" ]; then
    chmod +x "dist/release/Linux/app"
    mv "dist/release/Linux/app" "dist/release/Linux/NEWT-linux.bin"
    echo "Linux executable created: dist/release/Linux/NEWT-linux.bin"
    echo ""
    echo "To run NEWT, execute: ./dist/release/Linux/NEWT"
    echo ""
    echo "To create a .env file, copy .env.example to .env and edit as needed."
else
    echo "Error: Executable not found in dist/release/Linux folder."
    exit 1
fi

# Build Windows executable (using Wine if available)
echo "Building Windows executable..."
if command -v wine &> /dev/null; then
    echo "Wine found. Building Windows binary..."

    # Create a temporary batch file
    cat > build_windows.sh << 'EOF'
#!/bin/bash
pyinstaller --onefile --windowed --add-data=templates:templates --add-data=static:static --distpath=dist/release/Windows app.py
EOF

    chmod +x build_windows.sh
    ./build_windows.sh

    if [ $? -eq 0 ]; then
        # Check if the Windows executable was created
        if [ -f "dist/release/Windows/app" ]; then
            mv "dist/release/Windows/app" "dist/release/Windows/NEWT-win.exe"
            echo "Windows executable created: dist/release/Windows/NEWT-win.exe"
            echo ""
            echo "To run NEWT on Windows, execute: dist/release/Windows/NEWT-win.exe"
        else
            echo "Error: Windows executable not found in dist/release/Windows folder."
        fi
    else
        echo "Error: Windows build failed."
    fi

    # Clean up the temporary script
    rm -f build_windows.sh
else
    echo "Wine not found. Skipping Windows build."
fi

# Clean up
rm -rf build
rm -f "*.spec"

echo "Build complete!"
exit 0
