@echo off
setlocal ENABLEEXTENSIONS

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "LOG_DIR=%PROJECT_ROOT%\logs"
set "WEB_ROOT=Z:\childcare"
set "WEB_INDEX=%WEB_ROOT%\index.html"
set "SOURCE_INDEX=%PROJECT_ROOT%\index.html"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%WEB_ROOT%" mkdir "%WEB_ROOT%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=run"
set "LOG_FILE=%LOG_DIR%\update_%STAMP%.log"

echo [%date% %time%] Starting update > "%LOG_FILE%"
cd /d "%PROJECT_ROOT%" || exit /b 1

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 scripts\update_dashboard.py >> "%LOG_FILE%" 2>&1
    set "EXIT_CODE=%errorlevel%"
) else (
    python scripts\update_dashboard.py >> "%LOG_FILE%" 2>&1
    set "EXIT_CODE=%errorlevel%"
)

if not "%EXIT_CODE%"=="0" goto :finish

if not exist "%SOURCE_INDEX%" (
    echo [%date% %time%] ERROR: source index not found: "%SOURCE_INDEX%" >> "%LOG_FILE%"
    set "EXIT_CODE=1"
    goto :finish
)

copy /Y "%SOURCE_INDEX%" "%WEB_INDEX%" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: failed to copy index.html to "%WEB_INDEX%" >> "%LOG_FILE%"
    set "EXIT_CODE=1"
) else (
    echo [%date% %time%] Synced index.html to "%WEB_INDEX%" >> "%LOG_FILE%"
)

:finish
echo.>> "%LOG_FILE%"
echo [%date% %time%] Finished with exit code %EXIT_CODE% >> "%LOG_FILE%"
exit /b %EXIT_CODE%
