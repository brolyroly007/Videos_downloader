@echo off
echo ========================================
echo   Viral Content Automation Dashboard
echo ========================================
echo.

REM Verificar FFmpeg
echo [1/4] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: FFmpeg not found!
    echo Please install FFmpeg and add it to your PATH
    pause
    exit /b 1
)
echo FFmpeg OK!

REM Iniciar Backend FastAPI
echo.
echo [2/4] Starting FastAPI Backend on port 8000...
start "FastAPI Backend" cmd /c "cd /d D:\proyectojudietha && python app.py"
timeout /t 3 /nobreak >nul

REM Iniciar Frontend Next.js
echo.
echo [3/4] Starting Next.js Frontend on port 3000...
start "Next.js Frontend" cmd /c "cd /d D:\proyectojudietha\frontend && npm run dev"
timeout /t 5 /nobreak >nul

echo.
echo [4/4] All services started!
echo.
echo ========================================
echo   Dashboard URLs:
echo.
echo   React Frontend:  http://localhost:3000
echo   FastAPI Backend: http://localhost:8000
echo   API Docs:        http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to open the dashboard...
pause >nul

start http://localhost:3000
