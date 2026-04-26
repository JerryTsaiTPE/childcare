@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS

:: ==========================================
:: 設定您的路徑
:: ==========================================
set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare"
set "WEB_ROOT=Z:\childcare"

cd /d "%PROJECT_ROOT%"

echo [%date% %time%] 🚀 開始執行【裝甲版】儀表板自動更新...

:: 1. 執行 Python 更新資料與產出 HTML
python scripts\update_dashboard.py
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo ❌ [錯誤] Python 腳本執行失敗，已終止。
    goto :finish
)

:: 2. 套用 Git 強力傳輸設定 (避免 RPC failed)
git config --global http.postBuffer 524288000
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999

:: 3. 備份 index.html 到您的同步空間
if exist "%WEB_ROOT%" (
    copy /Y index.html "%WEB_ROOT%\index.html" >nul
)

:: 4. 執行全自動 Git 存檔與推送
echo 📦 正在同步雲端狀態並推送更新...

:: (A) 先把所有變動（含手動修改或自動生成的資料）加入暫存
git add .

:: (B) 存檔。如果沒有任何變動，這行會跳過不報錯
git commit -m "Auto-update: %date% %time%" || echo ℹ️ 本次無新變更需要儲存

:: (C) 關鍵：先拉取雲端更新並合併，解決 rejected 問題
git pull --rebase

:: (D) 推送上 GitHub
git push origin main
if not %errorlevel% == 0 (
    echo ⚠️ 第一次推送失敗，嘗試第二次...
    git push origin main
)

echo =======================================================
echo ✅ 所有任務已圓滿完成！儀表板已同步至 GitHub Pages。
echo =======================================================

:finish
:: 如果您是手動點擊想看結果，可以留著 pause；如果是純排程跑，可以把 pause 刪掉
:: pause
exit /b %EXIT_CODE%