@echo off
REM Starts everything on Windows: the SPIREXA server, the Arduino bridge,
REM and opens the dashboard.
REM   run.bat              plug in the Arduino first; falls back to simulation
REM   run.bat --simulate   force simulation, no board needed
setlocal

set PORT=8000
set SIM=
if "%1"=="--simulate" set SIM=--simulate

echo Clearing anything already running...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq spirexa_server*" >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq spirexa_bridge*" >nul 2>&1

if not exist "data\processed\model.pkl" (
    echo ERROR: no trained model at data\processed\model.pkl
    echo Run once:  venv\Scripts\python src\train_model.py
    exit /b 1
)

echo Starting SPIREXA server on port %PORT%...
start "spirexa_server" /min cmd /c "venv\Scripts\python src\serve.py --port %PORT% > logs_server.txt 2>&1"

echo Waiting for the server...
set READY=
for /L %%i in (1,1,25) do (
    curl -s --max-time 2 http://localhost:%PORT%/api/health >nul 2>&1
    if not errorlevel 1 (
        set READY=1
        goto :server_up
    )
    timeout /t 1 /nobreak >nul
)
:server_up
if not defined READY (
    echo Server did not come up - check logs_server.txt
    type logs_server.txt
    exit /b 1
)
echo   server ready

echo Starting the Arduino bridge (falls back to simulation if no board is found)...
start "spirexa_bridge" /min cmd /c "venv\Scripts\python hardware\serial_bridge.py %SIM% > logs_bridge.txt 2>&1"
timeout /t 3 /nobreak >nul

echo.
echo ======================================================
echo   SPIREXA is running
echo.
echo   Dashboard    http://localhost:%PORT%
echo.
echo   logs_server.txt   server
echo   logs_bridge.txt   sensor readings
echo.
echo   Close this window, or run stop.bat, to stop everything
echo ======================================================
echo.

start http://localhost:%PORT%

echo Streaming sensor readings (Ctrl+C to stop watching, servers keep running)...
timeout /t 2 /nobreak >nul
type logs_bridge.txt
powershell -command "Get-Content logs_bridge.txt -Wait -Tail 10"
