# 板橋柏翠托育備取名單 Dashboard

這個專案會每天抓取新北育兒資訊網公開 API：
- 備取名單：`/webapi/NpsApply/GetStandbyList?orgid=Z0130`
- 中心資訊：`/webapi/Org/GetPublicNpsOrgList`

並產出：
- `dashboard.html`：可直接開啟的單檔 dashboard
- `data/latest_snapshot.json`：最新完整快照
- `data/snapshots/*.json`：歷史快照
- `data/history.json`：每日總數歷史
- `data/changes.json`：每日差異摘要

## 手動更新

```bash
python3 /home/jerry/ntpc-childcare-dashboard/scripts/update_dashboard.py
```

Windows 也可直接執行：

```powershell
python scripts\update_dashboard.py
```

## Windows 11 VM 自動更新

專案附帶 `scripts/run_update_windows.bat`，可供 Windows 工作排程器每小時執行一次。

建議排程：每 1 小時執行一次。

## dashboard 內容

- 目前備取總數
- 上月入托人數
- 核定名額 / 已入托
- 最新可能離開名單序號
- 最新新增候補序號
- 名次推進明細
- 每日備取總數走勢
- 缺額遞補原則

## 重要說明

此系統根據每日快照推估「誰離開名單、誰名次前進」。
若網站在一天內多次更新，而排程只跑一次，則只能看到該次抓取時的最新狀態。
若你要更細緻追蹤，可把排程改成每 1 小時或每 30 分鐘執行一次。
