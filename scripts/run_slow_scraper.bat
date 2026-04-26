@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS

set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare\scripts"
cd /d "%PROJECT_ROOT%"

echo =======================================================
echo 🐢 開始執行【重度爬蟲】，這會花費大約 1-2 分鐘...
echo =======================================================

:: 執行爬蟲
python scrape_info.py

echo.
echo =======================================================
echo 爬蟲結束，觸發一次高速更新以套用最新說明文字...
echo =======================================================

:: 呼叫同資料夾下的快速更新腳本
call run_update_windows.bat

echo ✅ 緩慢爬蟲任務徹底結束！
pause