#!/usr/bin/env bash
set -e

echo "========================================"
echo "Viral Content Automation Dashboard"
echo "========================================"
echo

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "WARNING: Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    echo
fi

# Check FFmpeg
echo "Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: FFmpeg not found!"
    echo "Please install FFmpeg and add it to your PATH"
    exit 1
fi
echo "FFmpeg found!"
echo

# Start server
echo "Starting server..."
echo "Dashboard will be available at: http://localhost:8000"
echo
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo

python app.py
