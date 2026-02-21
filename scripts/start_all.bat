@echo off
title Viral Content Automation - Local

echo ========================================
echo   Viral Content Automation Dashboard
echo ========================================
echo.

:: Crear directorios si no existen
if not exist "downloads" mkdir downloads
if not exist "processed" mkdir processed
if not exist "temp" mkdir temp
if not exist "cookies" mkdir cookies
if not exist "cache" mkdir cache

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.10+
    pause
    exit /b 1
)

:: Verificar dependencias
echo Verificando dependencias...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    pip install -r requirements.txt
)

echo.
echo Iniciando servicios...
echo.

:: Iniciar Backend en una ventana
start "Backend API" cmd /k "cd /d %~dp0.. && python -m uvicorn app:app --reload --port 8000"

:: Esperar que el backend inicie
timeout /t 3 /nobreak >nul

:: Iniciar Frontend en otra ventana
start "Frontend React" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo ========================================
echo   Servicios iniciados:
echo   - Backend:  http://localhost:8000
echo   - Frontend: http://localhost:3000
echo   - API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Presiona cualquier tecla para abrir el dashboard...
pause >nul

:: Abrir navegador
start http://localhost:3000
