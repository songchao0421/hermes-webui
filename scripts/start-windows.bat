@echo off
setlocal enabledelayedexpansion
title Hermes WebUI

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%i in ("%SCRIPT_DIR%\..") do set "PROJECT_DIR=%%~fi"
set "PORT=8080"
set "OLLAMA_URL="

echo.
echo ============================================
echo    Hermes WebUI  v2.3.1
echo ============================================
echo.

:: ============================================
:: Step 1: Check WSL2
:: ============================================
echo [1/6] Checking WSL2...
wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo     ERROR: WSL2 not found.
    echo     Run in PowerShell as Admin: wsl --install
    pause & exit /b 1
)
echo     OK: WSL2 available

:: ============================================
:: Step 2: Convert project path to WSL path
:: ============================================
echo.
echo [2/6] Mapping project path to WSL...
set "WSL_PROJECT="
for /f "tokens=*" %%P in ('wsl -- wslpath -u "%PROJECT_DIR:\=/%" 2^>nul') do set "WSL_PROJECT=%%P"
if not defined WSL_PROJECT (
    echo     ERROR: Path conversion failed.
    pause & exit /b 1
)
echo     OK: %WSL_PROJECT%

:: ============================================
:: Step 3: Detect Ollama (for AI features)
:: ============================================
echo.
echo [3/6] Detecting Ollama...

:: Check if WSL2 can reach localhost:11434 directly
wsl -- bash -lc "curl -s http://localhost:11434/api/tags >/dev/null 2>&1"
if %errorlevel% equ 0 (
    set "OLLAMA_URL=http://localhost:11434"
    echo     OK: Ollama at localhost:11434 (WSL2 direct)
    goto :setup_venv
)

:: Check if Ollama is running on Windows host
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo     Ollama running on Windows (NAT mode)
    for /f "tokens=*" %%H in ('powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 ^| Sort-Object RouteMetric ^| Select-Object -First 1).NextHop" 2^>nul') do (
        if not defined WIN_IP set "WIN_IP=%%H"
    )
    if not defined WIN_IP (
        for /f "tokens=3" %%G in ('wsl -- bash -c "ip route show default 2>/dev/null" ^| findstr /i "default"') do (
            if not defined WIN_IP set "WIN_IP=%%G"
        )
    )
    if defined WIN_IP (
        echo %WIN_IP%| findstr /r "[0-9]" >nul 2>&1 || set "WIN_IP="
    )
    if defined WIN_IP (
        wsl -- bash -lc "curl -s http://!WIN_IP!:11434/api/tags >/dev/null 2>&1"
        if !errorlevel! equ 0 (
            set "OLLAMA_URL=http://!WIN_IP!:11434"
            echo     OK: Ollama at !WIN_IP!:11434
            goto :setup_venv
        )
    )
    echo     WARNING: Ollama on Windows but not reachable from WSL.
    echo     Starting in limited mode. To fix, add to %%USERPROFILE%%\.wslconfig:
    echo       [wsl2]
    echo       networkingMode=mirrored
    echo     Then: wsl --shutdown  and  relaunch
) else (
    :: Ollama not found
    echo     Not detected (AI chat disabled)
    echo     Install from https://ollama.com/download then pull a model.
    echo     Starting in limited mode (memory editor / skills browser).
)

:: ============================================
:: Step 4: Set up Python virtual environment
:: ============================================
:setup_venv
echo.
echo [4/6] Setting up Python virtual environment...
wsl -- bash -lc "cd '%WSL_PROJECT%' && (python3 -m venv venv 2>/dev/null && echo 'venv created') || echo 'venv already exists'"

:: ============================================
:: Step 5: Install/verify dependencies
:: ============================================
echo.
echo [5/6] Installing Python dependencies...
wsl -- bash -lc "cd '%WSL_PROJECT%' && ./venv/bin/pip install -r backend/requirements.txt -q 2>&1"
if %errorlevel% equ 0 (
    echo     OK: Dependencies installed
) else (
    echo     WARNING: Some deps may be missing, trying pip3...
    wsl -- bash -lc "cd '%WSL_PROJECT%' && ./venv/bin/pip3 install -r backend/requirements.txt -q 2>&1"
)

:: ============================================
:: Step 6: Find available port
:: ============================================
echo.
echo [6/6] Finding available port...
set PORT=8080
:checkport
netstat -ano 2>nul | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    set /a PORT=PORT+1
    if %PORT% gtr 8090 (
        echo     ERROR: All ports 8080-8090 are busy.
        pause & exit /b 1
    )
    goto checkport
)
echo     OK: Port %PORT%

:: ============================================
:: Launch
:: ============================================
echo.
echo ============================================
echo    Hermes WebUI  v2.3.1
echo    Ollama : %OLLAMA_URL%
echo    Open   : http://localhost:%PORT%
echo ============================================
echo.

:: Auto-open browser after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:%PORT%"

:: Launch the Python backend in WSL
wsl -- bash -lc "cd '%WSL_PROJECT%' && OLLAMA_BASE_URL='%OLLAMA_URL%' ./venv/bin/python backend/app.py --no-auth --host 0.0.0.0 --port %PORT% --wsl-mode"

if %errorlevel% neq 0 (
    echo.
    echo     ERROR: Python server failed to start (exit code: %errorlevel%)
    pause
    exit /b 1
)

:: If we get here, the user pressed Ctrl+C
echo.
echo Server stopped.
pause
