@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
set "EXIT_CODE=1"

rem ==========================================
rem 本機部署路徑 (第一批次完整部署版)
rem ==========================================
set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare"
set "WEB_ROOT=\\192.168.68.58\jerry0423\web\childcare"
set "REMOTE_REPO=https://github.com/JerryTsaiTPE/childcare.git"

if not exist "%PROJECT_ROOT%\scripts\update_dashboard.py" (
    echo ❌ [錯誤] 找不到 %PROJECT_ROOT%\scripts\update_dashboard.py
    goto :finish
)

pushd "%PROJECT_ROOT%"
if errorlevel 1 (
    echo ❌ [錯誤] 無法進入專案資料夾：%PROJECT_ROOT%
    goto :finish
)
set "DID_PUSHD=1"

echo [%date% %time%] 🚀 開始執行【第一批次】儀表板自動更新與完整 GitHub 部署...

rem 1. 只更新第一批次公托資料 (帶入 --first-batch-only 參數)
python scripts\update_dashboard.py --first-batch-only
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo ❌ [錯誤] Python 腳本執行失敗，已終止。
    goto :finish
)

rem 2. 備份 index.html 到同步空間。
if exist "%WEB_ROOT%" (
    copy /Y index.html "%WEB_ROOT%\index.html" >nul
    if errorlevel 1 (
        echo ❌ [錯誤] 無法同步 index.html 至 %WEB_ROOT%
        set "EXIT_CODE=1"
        goto :finish
    )
) else (
    echo ⚠️ [略過] 找不到網站同步資料夾：%WEB_ROOT%
)

rem 3. 將程式碼備份到 main。
echo 📦 正在備份程式碼變更至 main 分支...
git add .
if errorlevel 1 (
    echo ❌ [錯誤] git add 失敗。
    set "EXIT_CODE=1"
    goto :finish
)
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update First Batch: %date% %time%"
    if errorlevel 1 (
        echo ❌ [錯誤] git commit 失敗。
        set "EXIT_CODE=1"
        goto :finish
    )
) else (
    echo ℹ️ 程式碼無新變更需要儲存。
)
git pull origin main --rebase
if errorlevel 1 (
    echo ❌ [錯誤] git pull --rebase 失敗；未繼續發布。
    set "EXIT_CODE=1"
    goto :finish
)
git push origin main
if errorlevel 1 (
    echo ❌ [錯誤] git push main 失敗；未繼續發布。
    set "EXIT_CODE=1"
    goto :finish
)

rem 4. 建置單一 commit 的 gh-pages 分支。
echo 🌐 正在建置並發布單一 Commit 的 gh-pages 分支...
set "DEPLOY_DIR=%PROJECT_ROOT%\_deploy_tmp"
if exist "%DEPLOY_DIR%" rmdir /S /Q "%DEPLOY_DIR%"
mkdir "%DEPLOY_DIR%"
if errorlevel 1 (
    echo ❌ [錯誤] 無法建立發布暫存資料夾。
    set "EXIT_CODE=1"
    goto :finish
)

copy /Y index.html "%DEPLOY_DIR%\index.html" >nul
if errorlevel 1 (
    echo ❌ [錯誤] 無法複製 index.html 至發布暫存資料夾。
    set "EXIT_CODE=1"
    goto :cleanup
)
if exist "calculator" xcopy "calculator" "%DEPLOY_DIR%\calculator" /E /I /H /Y >nul
if errorlevel 1 (
    echo ❌ [錯誤] 無法複製 calculator 資料夾。
    set "EXIT_CODE=1"
    goto :cleanup
)

pushd "%DEPLOY_DIR%"
git init
if errorlevel 1 goto :publish_failed
git add .
if errorlevel 1 goto :publish_failed
git commit -m "Deploy dashboard first-batch update: %date% %time%"
if errorlevel 1 goto :publish_failed
git push --force "%REMOTE_REPO%" master:gh-pages
if errorlevel 1 goto :publish_failed
popd

:cleanup
if exist "%DEPLOY_DIR%" rmdir /S /Q "%DEPLOY_DIR%"
if not "%EXIT_CODE%"=="0" goto :finish

echo =======================================================
echo ✅ 第一批次驗證發布完成！儀表板已同步至 GitHub Pages。
echo =======================================================
set "EXIT_CODE=0"
goto :finish

:publish_failed
popd
echo ❌ [錯誤] gh-pages 發布失敗。
set "EXIT_CODE=1"
goto :cleanup

:finish
if defined DID_PUSHD popd
endlocal & exit /b %EXIT_CODE%