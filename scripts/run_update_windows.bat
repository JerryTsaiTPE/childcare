@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
set "EXIT_CODE=1"

rem ==========================================
rem 本機部署路徑
rem ==========================================
set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare"
set "WEB_ROOT=Z:\childcare"
set "REMOTE_REPO=https://github.com/JerryTsaiTPE/childcare.git"

rem ==========================================
rem 防呆：git 遇到任何互動提示（憑證/編輯器）都立即失敗，
rem 絕不在背景排程中卡住等待輸入（這是「執行個體已在執行」錯誤的主因）。
rem ==========================================
set "GIT_TERMINAL_PROMPT=0"
set "GIT_ASKPASS=echo"
set "GIT_EDITOR=true"

rem 網路卡住時的 git 逾時（連線 15 秒、30 秒內平均傳輸低於 1KB/s 就放棄，避免無限期等待）
set "GIT_TIMEOUT_OPTS=-c http.connectTimeout=15 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30"

rem ==========================================
rem 日誌：每次執行寫入 logs\update_yyyy-MM-dd_HH-mm-ss.log
rem ==========================================
set "LOG_DIR=%PROJECT_ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "LOG_STAMP=%%i"
if not defined LOG_STAMP set "LOG_STAMP=manual"
set "LOG_FILE=%LOG_DIR%\update_%LOG_STAMP%.log"

call :main >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo 執行結束（代碼 %EXIT_CODE%）。完整紀錄：%LOG_FILE%
endlocal & exit /b %EXIT_CODE%

:main
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

echo [%date% %time%] 🚀 開始執行【裝甲版】儀表板自動更新...

rem 0. 清除上次殘留的 rebase 中斷狀態。abort 對「半殘」的 rebase-merge 可能失敗，
rem    此時直接刪除殘骸目錄，避免後續 rebase 被「already a rebase-merge」擋住。
if exist ".git\rebase-merge" (
    git rebase --abort >nul 2>&1
    if exist ".git\rebase-merge" (
        echo ⚠️ 偵測到殘留 rebase 狀態，強制清除 .git\rebase-merge
        rmdir /S /Q ".git\rebase-merge"
    )
)
if exist ".git\rebase-apply" (
    git rebase --abort >nul 2>&1
    if exist ".git\rebase-apply" (
        echo ⚠️ 偵測到殘留 rebase 狀態，強制清除 .git\rebase-apply
        rmdir /S /Q ".git\rebase-apply"
    )
)
if exist ".git\refs\autostash" del /Q ".git\refs\autostash" >nul 2>&1

rem 1. 只執行更新器；若由 run_update_via_proxy.bat 呼叫，會繼承該程序範圍的 CHILDCARE_API_PROXY。
python scripts\update_dashboard.py
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
    git commit -m "Auto-update Scripts: %date% %time%"
    if errorlevel 1 (
        echo ❌ [錯誤] git commit 失敗。
        set "EXIT_CODE=1"
        goto :finish
    )
) else (
    echo ℹ️ 程式碼無新變更需要儲存。
)

rem 4. 同步 main：先 fetch 再 rebase。若發生衝突，自動捨棄本機自動提交並對齊
rem    遠端（資料檔仍完整保留在磁碟），絕不卡住等待人工處理；本輪略過 push，
rem    下次執行會自動重試。
echo ⬇️ 正在同步 origin/main ...
git %GIT_TIMEOUT_OPTS% fetch origin main
if errorlevel 1 (
    echo ❌ [錯誤] git fetch 失敗（網路或憑證問題）；未繼續發布。
    set "EXIT_CODE=1"
    goto :finish
)
git -c rebase.autoStash=true rebase origin/main
if errorlevel 1 (
    echo ⚠️ rebase 發生衝突，自動復原中...
    git rebase --abort >nul 2>&1
    if exist ".git\rebase-merge" rmdir /S /Q ".git\rebase-merge"
    if exist ".git\refs\autostash" del /Q ".git\refs\autostash" >nul 2>&1
    git reset --hard origin/main
    if errorlevel 1 (
        echo ❌ [錯誤] 無法復原 git 狀態；未繼續發布。
        set "EXIT_CODE=1"
        goto :finish
    )
    echo ⚠️ 已自動捨棄衝突的本機自動提交並對齊 origin/main（data 資料保留在磁碟）。
    echo ⚠️ 本輪略過 git push；下次執行會自動重試。
    set "EXIT_CODE=1"
    goto :finish
)
git %GIT_TIMEOUT_OPTS% push origin main
if errorlevel 1 (
    echo ❌ [錯誤] git push main 失敗；未繼續發布。
    set "EXIT_CODE=1"
    goto :finish
)

rem 5. 建置單一 commit 的 gh-pages 分支。
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
git commit -m "Deploy dashboard update: %date% %time%"
if errorlevel 1 goto :publish_failed
git %GIT_TIMEOUT_OPTS% push --force "%REMOTE_REPO%" master:gh-pages
if errorlevel 1 goto :publish_failed
popd

:cleanup
if exist "%DEPLOY_DIR%" rmdir /S /Q "%DEPLOY_DIR%"
if not "%EXIT_CODE%"=="0" goto :finish

echo =======================================================
echo ✅ 所有任務已圓滿完成！儀表板已同步至 GitHub Pages。
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
exit /b %EXIT_CODE%
