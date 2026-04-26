@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS

set "PROJECT_ROOT=C:\Users\JerryPC\Desktop\childcare"
set "WEB_ROOT=Z:\childcare"

cd /d "%PROJECT_ROOT%"
echo [%date% %time%] 🚀 開始執行【高速】儀表板自動更新...
python scripts\update_dashboard.py
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo ❌ [錯誤] Python 腳本執行失敗，已終止後續推送。
    goto :finish
)

copy /Y index.html "%WEB_ROOT%\index.html" >nul
git add data/ index.html
git commit -m "Auto-update: %date% %time%"
git push
echo ✅ 更新與推送完成！
PAUSE
:finish
exit /b %EXIT_CODE%