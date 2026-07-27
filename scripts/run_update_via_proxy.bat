@echo off
setlocal EnableExtensions

rem Only update_dashboard.py reads this variable.
rem It is inherited by the called batch and its Python process only.
set "CHILDCARE_API_PROXY=http://100.85.96.12:8888"

call "C:\Users\JerryPC\Desktop\childcare\scripts\run_update_windows.bat"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%