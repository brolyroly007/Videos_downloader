@echo off
echo ========================================
echo Viral Content Automation - Installation
echo ========================================
echo.

REM Verificar Python
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python found!
echo.

REM Verificar FFmpeg
echo Checking FFmpeg installation...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: FFmpeg not found!
    echo FFmpeg is REQUIRED for video processing
    echo.
    echo Please install FFmpeg:
    echo 1. Download from: https://ffmpeg.org/download.html
    echo 2. Extract to C:\ffmpeg
    echo 3. Add C:\ffmpeg\bin to your PATH environment variable
    echo.
    echo Continue anyway? (Y/N)
    choice /c YN /n
    if errorlevel 2 exit /b 1
) else (
    echo FFmpeg found!
)
echo.

REM Crear entorno virtual
echo Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo Virtual environment created!
) else (
    echo Virtual environment already exists.
)
echo.

REM Activar entorno virtual
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Actualizar pip
echo Updating pip...
python -m pip install --upgrade pip
echo.

REM Instalar dependencias
echo Installing dependencies...
echo This may take several minutes...
pip install -r requirements.txt
echo.

REM Instalar Playwright browsers
echo Installing Playwright browsers...
playwright install chromium
echo.

REM Crear directorios necesarios
echo Creating directories...
if not exist downloads mkdir downloads
if not exist processed mkdir processed
if not exist temp mkdir temp
if not exist cookies mkdir cookies
if not exist static mkdir static
echo Directories created!
echo.

REM Copiar .env.example si no existe .env
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo .env file created!
) else (
    echo .env file already exists.
)
echo.

echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo To start the application:
echo 1. Run: run.bat
echo 2. Or manually: python app.py
echo 3. Open browser at: http://localhost:8000
echo.
echo IMPORTANT NOTES:
echo - Make sure FFmpeg is installed and in PATH
echo - First TikTok upload requires manual login
echo - GPU recommended for faster subtitle generation
echo.
pause
