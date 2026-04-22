# 板橋柏翠托育備取名單 Dashboard

這個專案會抓取新北育兒資訊網公開 API：
- 備取名單：`/webapi/NpsApply/GetStandbyList?orgid=Z0130`
- 中心資訊：`/webapi/Org/GetPublicNpsOrgList`

並產出：
- `index.html`：可直接開啟的單檔 dashboard
- `data/latest_snapshot.json`：最新完整快照
- `data/snapshots/*.json`：歷史快照
- `data/history.json`：歷史總數與變動摘要
- `data/changes.json`：每次更新差異摘要

## Windows 11 VM 環境需求

本專案目前只使用 Python 標準庫，不需要額外安裝第三方套件。

必要條件：
- Windows 11
- Python 3.11 或 3.12（建議安裝時勾選 Add Python to PATH）

驗證指令：

```powershell
python --version
```

若系統使用 Python Launcher，也可用：

```powershell
py -3 --version
```

## 是否一定要用 venv？

不是絕對必要。

原因：
- 專案程式目前只依賴 Python 標準庫
- 沒有 `requirements.txt`
- 沒有 `pyproject.toml`
- 沒有需要另外安裝的套件

所以在 Windows VM 上，可直接用系統 Python 執行。

但若您之後要加入額外套件，仍建議再補上 venv。

## 手動更新

在專案根目錄執行：

```powershell
python scripts\update_dashboard.py
```

或：

```powershell
py -3 scripts\update_dashboard.py
```

## 每小時自動更新（Windows 工作排程器）

專案已附上批次檔：

- `scripts\run_update_windows.bat`

此批次檔會：
- 自動切到專案根目錄
- 執行 `scripts\update_dashboard.py`
- 將執行紀錄寫入 `logs\update_yyyy-MM-dd_HH-mm-ss.log`

### 建立排程

1. 開啟「工作排程器」
2. 選擇「建立工作」
3. 一般：
   - 名稱：`NTPC Childcare Dashboard Hourly Update`
   - 勾選「不論使用者是否登入都要執行」
4. 觸發程序：
   - 新增觸發程序
   - 開始工作：依排程
   - 設定為：每天
   - 進階設定：
     - 勾選「重複工作間隔」
     - 選 `1 小時`
     - 持續時間選 `無限期`
5. 動作：
   - 動作：啟動程式
   - 程式或指令碼：指向
     `C:\您的路徑\ntpc-childcare-dashboard\scripts\run_update_windows.bat`
6. 條件：如不希望受電源限制，可取消「僅在使用交流電源時才啟動工作」
7. 設定：可勾選「如果工作失敗，重新啟動」

## 開發與測試

單元測試使用 Python 內建 `unittest`，不是 `pytest`。

執行方式：

```powershell
python -m unittest discover -s tests -v
```

## 重要路徑相容性說明

目前專案主程式已使用 `pathlib.Path` 依據專案根目錄組路徑，適合在 Windows 與 WSL 間移植。

輸出重點：
- 首頁檔名是 `index.html`
- 不是 `dashboard.html`

## 資料存放位置

- `data\latest_snapshot.json`：最新快照
- `data\history.json`：歷史紀錄
- `data\changes.json`：變動摘要
- `data\snapshots\`：每次抓取的快照檔
- `logs\`：Windows 批次執行紀錄
