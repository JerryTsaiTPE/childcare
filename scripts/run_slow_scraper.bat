@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS DisableDelayedExpansion

rem Service-only proxy: 設定只作用於此批次檔及其子行程（Python 爬蟲）
set "CHILDCARE_API_PROXY=http://100.85.96.12:8888"

rem 通用 Python 網路庫（如 requests, httpx）自動讀取的代理變數
set "HTTP_PROXY=%CHILDCARE_API_PROXY%"
set "HTTPS_PROXY=%CHILDCARE_API_PROXY%"

set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare\scripts"
cd /d "%PROJECT_ROOT%"

echo =======================================================
echo 🐢 開始執行【重度爬蟲】（經由代理伺服器），這會花費大約 3 分鐘...
echo =======================================================

:: 執行爬蟲
python scrape_info.py

echo.
echo =======================================================
echo 爬蟲結束，觸發一次高速更新以套用最新說明文字...
echo =======================================================

:: 呼叫同資料夾下的快速更新腳本
call run_update_via_proxy.bat

echo ✅ 緩慢爬蟲任務徹底結束！
pause