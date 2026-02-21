#!/usr/bin/env bash
set -e

echo "========================================"
echo "Viral Content Automation - Installation"
echo "========================================"
echo

# Check Python
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi
python3 --version
echo

# Check FFmpeg
echo "Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: FFmpeg not found!"
    echo "FFmpeg is REQUIRED for video processing"
    echo "Install with: sudo apt install ffmpeg (Ubuntu) or brew install ffmpeg (macOS)"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
else
    echo "FFmpeg found!"
fi
echo

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created!"
else
    echo "Virtual environment already exists."
fi
echo

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo

# Update pip
echo "Updating pip..."
python -m pip install --upgrade pip
echo

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium
echo

# Create directories
echo "Creating directories..."
mkdir -p downloads processed temp cookies static cache
echo "Directories created!"
echo

# Copy .env
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ".env file created!"
else
    echo ".env file already exists."
fi
echo

echo "========================================"
echo "Installation completed successfully!"
echo "========================================"
echo
echo "To start the application:"
echo "  ./scripts/run.sh"
echo "  or: python app.py"
echo "  then open: http://localhost:8000"
