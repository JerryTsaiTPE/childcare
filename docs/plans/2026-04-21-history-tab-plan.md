# 板橋柏翠歷史紀錄分頁 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 為既有托育備取 dashboard 增加「歷史紀錄」分頁，按日期/時間列出每次名單更新的重點變動，避免把整串連動名次全部攤開。

**Architecture:** 於 tracker 層新增重點摘要欄位，將每次變動整理成可直接渲染的 timeline event。render 層新增雙分頁 UI（總覽/歷史紀錄），歷史分頁僅顯示每次更新的核心變動：離開名單序號、第一個受影響的新序號、代表性名次推進、總數變化。

**Tech Stack:** Python 3.12、unittest、單檔 HTML + 原生 JS/CSS。

---

### Task 1: 為重點摘要規則寫失敗測試
- 測試 build_change_record 會產生 `highlight_shift` 與 `summary_lines`
- 規則：若 100 消失導致後續整串前移，只保留代表性的 101 -> 100

### Task 2: 實作 tracker 摘要欄位
- 在 change record 中新增：
  - `highlight_shift`
  - `summary_lines`
  - `change_kind`
- history entry 加入可供歷史分頁使用的簡化欄位

### Task 3: 為歷史分頁 UI 寫失敗測試
- 驗證 render_dashboard 會輸出「總覽 / 歷史紀錄」tab
- 驗證歷史紀錄區塊包含日期、摘要文字與代表性變動

### Task 4: 實作 render 歷史分頁
- 增加 tabs
- 總覽保留現有內容
- 歷史紀錄分頁顯示 timeline cards

### Task 5: 串接 update script 與既有資料相容
- 重新輸出 history/changes
- 保持舊資料缺欄位時也能渲染

### Task 6: 驗證
- `python3 -m unittest discover -s tests -v`
- `python3 scripts/update_dashboard.py`
- 開啟 `file:///home/jerry/ntpc-childcare-dashboard/dashboard.html` 驗證
