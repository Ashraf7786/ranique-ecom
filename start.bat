@echo off
:: ============================================================
:: Ranique Shipping Label Generator — Quick Setup & Launch
:: ============================================================
:: This script installs dependencies and starts the Flask server.
:: Run as Administrator if pip install fails.

setlocal

:: Try to find Python
set PYTHON=
:: Confirmed working location (installed 2026-08-19)
if exist "C:\Python313\python.exe"          set PYTHON=C:\Python313\python.exe
if exist "C:\Python312\python.exe"          set PYTHON=C:\Python312\python.exe
if exist "C:\Python311\python.exe"          set PYTHON=C:\Python311\python.exe
if exist "C:\Python310\python.exe"          set PYTHON=C:\Python310\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe

:: If still not found, try PATH
if "%PYTHON%"=="" (
    where python >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=python
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 set PYTHON=py
    )
)

if "%PYTHON%"=="" (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    echo         or from the Microsoft Store.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON%
"%PYTHON%" --version

echo.
echo [Step 1] Installing dependencies...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARN] pip install failed. Trying with --user flag...
    "%PYTHON%" -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Could not install packages. Try running as Administrator.
        pause
        exit /b 1
    )
)

echo.
echo [Step 2] Starting Flask server...
echo.
echo =====================================================
echo   Ranique Label Generator
echo   Open your browser at:  http://localhost:5000
echo =====================================================
echo.
"%PYTHON%" app.py

pause
