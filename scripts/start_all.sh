#!/usr/bin/env bash
set -e

echo "========================================"
echo "  Viral Content Automation Dashboard"
echo "========================================"
echo

# Check FFmpeg
echo "[1/4] Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: FFmpeg not found!"
    exit 1
fi
echo "FFmpeg OK!"

# Activate venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Start Backend
echo
echo "[2/4] Starting FastAPI Backend on port 8000..."
python app.py &
BACKEND_PID=$!
sleep 3

# Start Frontend
echo
echo "[3/4] Starting Next.js Frontend on port 3000..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

echo
echo "[4/4] All services started!"
echo
echo "========================================"
echo "  Dashboard URLs:"
echo
echo "  React Frontend:  http://localhost:3000"
echo "  FastAPI Backend: http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "========================================"
echo
echo "Press Ctrl+C to stop all services"

# Trap Ctrl+C to kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
