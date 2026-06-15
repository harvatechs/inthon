@echo off
title Inthon IDE Launcher
color 0B

echo.
echo  ██████████████████████████████████████
echo  ██  INTHON IDE  —  Agent-Level Code  ██
echo  ██████████████████████████████████████
echo.
echo  [*] Starting Inthon compiler server...

:: Kill any existing server on port 7474
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find "7474" ^| find "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start server in background
start /B "" python "%~dp0inthon_server.py"

:: Wait for server to start
echo  [*] Waiting for server to initialize...
timeout /t 2 /nobreak >nul

:: Verify server is up
curl -s -o nul -w "%%{http_code}" http://localhost:7474/health >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Server is running on http://localhost:7474
) else (
    echo  [?] Server starting... opening IDE anyway
)

echo  [*] Opening Inthon IDE in your browser...
echo.

:: Open the IDE in the default browser
start "" "%~dp0inthon-ide.html"

echo  IDE launched! Close this window to stop the server.
echo  (Press Ctrl+C or close this window to shut down)
echo.

:: Keep window open (server running in background)
:: Wait for Ctrl+C
:wait_loop
timeout /t 30 /nobreak >nul
goto wait_loop
