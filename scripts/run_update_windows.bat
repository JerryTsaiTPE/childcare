@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS

:: ==========================================
:: 設定您的路徑
:: ==========================================
set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare"
set "WEB_ROOT=Z:\childcare"
:: 設定 GitHub 遠端網址 (請確認大小寫正確)
set "REMOTE_REPO=https://github.com/JerryTsaiTPE/childcare.git"

cd /d "%PROJECT_ROOT%"

echo [%date% %time%] 🚀 開始執行【裝甲版】儀表板自動更新...

:: 1. 執行 Python 更新資料與產出 HTML
python scripts\update_dashboard.py
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo ❌ [錯誤] Python 腳本執行失敗，已終止。
    goto :finish
)

:: 2. 備份 index.html 到您的同步空間
if exist "%WEB_ROOT%" (
    copy /Y index.html "%WEB_ROOT%\index.html" >nul
)

:: ==========================================
:: 3. 處理程式碼與腳本的備份 (提交到 main 分支)
:: ==========================================
echo 📦 正在備份程式碼變更至 main 分支...
git add .
git commit -m "Auto-update Scripts: %date% %time%" || echo ℹ️ 程式碼無新變更需要儲存
git pull origin main --rebase
git push origin main

:: ==========================================
:: 4. 處理網頁發布 (強制推送到 gh-pages 分支，不留歷史)
:: ==========================================
echo 🌐 正在建置並發布單一 Commit 的 gh-pages 分支...

:: 建立暫存的發布資料夾
set "DEPLOY_DIR=%PROJECT_ROOT%\_deploy_tmp"
if exist "%DEPLOY_DIR%" rmdir /S /Q "%DEPLOY_DIR%"
mkdir "%DEPLOY_DIR%"

:: 將最新的 index.html 複製過去
copy /Y index.html "%DEPLOY_DIR%\index.html" >nul

:: 💡【新增這段】將 calculator 資料夾及其內容整個複製過去
if exist "calculator" (
    xcopy "calculator" "%DEPLOY_DIR%\calculator" /E /I /H /Y >nul
)

:: 進入暫存資料夾，初始化一個全新的 git
cd /d "%DEPLOY_DIR%"
git init
git add .
git commit -m "Deploy dashboard update: %date% %time%"

:: 強制推送到遠端的 gh-pages 分支
git push --force "%REMOTE_REPO%" master:gh-pages
if not %errorlevel% == 0 (
    echo ⚠️ 第一次推送網頁失敗，嘗試第二次...
    git push --force "%REMOTE_REPO%" master:gh-pages
)

:: 清理暫存資料夾並回到根目錄
cd /d "%PROJECT_ROOT%"
rmdir /S /Q "%DEPLOY_DIR%"

echo =======================================================
echo ✅ 所有任務已圓滿完成！儀表板已同步至 GitHub Pages。
echo =======================================================

:finish
:: pause
exit /b %EXIT_CODE%