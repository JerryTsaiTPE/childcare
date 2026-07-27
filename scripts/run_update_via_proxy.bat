@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Service-only proxy: this applies only to this batch process and its children.
rem It does not change Windows, browser, Git, NAS, or any other application's proxy.
set "CHILDCARE_API_PROXY=http://100.85.96.12:8888"

call "%~dp0run_update_windows.bat"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
