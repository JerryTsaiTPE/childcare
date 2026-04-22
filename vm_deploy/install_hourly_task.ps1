param(
    [string]$TaskName = "NTPC Childcare Dashboard Hourly Update"
)

# 為了防止執行時出現錯誤，我們將設定保持為 Stop
$ErrorActionPreference = 'Stop'

# Define paths
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BatchPath = Join-Path $ProjectRoot 'scripts\run_update_windows.bat'
$StartTime = (Get-Date).AddMinutes(1).ToString('HH:mm')

if (-not (Test-Path $BatchPath)) {
    Write-Error "Error: Batch file not found at $BatchPath"
    exit 1
}

Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "BatchPath  : $BatchPath"
Write-Host "TaskName   : $TaskName"
Write-Host "StartTime  : $StartTime"

# --- 修正後的區塊 ---
# 使用 try/catch 包覆查詢指令，這樣就算找不到任務導致錯誤，
# PowerShell 也不會因為 $ErrorActionPreference = 'Stop' 而崩潰
try {
    Write-Host "Checking for existing task..."
    $null = schtasks /Query /TN "$TaskName" 2>$null
    # 如果執行成功 (ExitCode 0)，表示任務存在，執行刪除
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Existing task found. Removing..."
        schtasks /Delete /TN "$TaskName" /F | Out-Null
    }
} catch {
    # 如果這裡報錯，代表任務不存在，我們直接忽略並繼續執行
    Write-Host "No existing task found, proceeding."
}
# --------------------

# Create new task
$taskCommand = '"' + $BatchPath + '"'
Write-Host "Creating new task..."

schtasks /Create /TN "$TaskName" /TR $taskCommand /SC HOURLY /MO 1 /ST $StartTime /RL HIGHEST /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "Task created successfully." -ForegroundColor Green
} else {
    Write-Error "Failed to create task. Error Code: $LASTEXITCODE"
}