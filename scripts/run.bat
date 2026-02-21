@echo off
echo ========================================
echo Viral Content Automation Dashboard
echo ========================================
echo.

REM Activar entorno virtual si existe
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found!
    echo Please run: python -m venv venv
    echo.
)

REM Verificar FFmpeg
echo Checking FFmpeg installation...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: FFmpeg not found!
    echo Please install FFmpeg and add it to your PATH
    echo Download from: https://ffmpeg.org/download.html
    pause
    exit /b 1
)
echo FFmpeg found!
echo.

REM Iniciar servidor
echo Starting server...
echo Dashboard will be available at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python app.py

pause
