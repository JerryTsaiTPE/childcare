# 板橋柏翠托育備取名單 Dashboard Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 建立一個可每日更新的新北市板橋柏翠公托備取名單 dashboard，自動保存快照、比對差異，並記錄離開名單與名次推進情況。

**Architecture:** 採用純 Python 標準函式庫方案。後端用腳本抓取 NTPC LoveBaby 公開 API、產生快照 JSON 與差異紀錄，再輸出單一 `dashboard.html` 檔；前端儀表板使用內嵌 CSS/JS 與嵌入式資料，避免額外相依與本機 CORS 問題。每日更新由排程觸發 `update_dashboard.py` 完成。

**Tech Stack:** Python 3.12、urllib/json/pathlib/unittest、單一靜態 HTML dashboard。

---

### Task 1: 建立專案骨架與測試檔

**Objective:** 建立專案目錄、測試入口與核心模組檔案位置。

**Files:**
- Create: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/__init__.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/tracker.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/render.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/scripts/update_dashboard.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/tests/test_tracker.py`

### Task 2: 先寫 diff 測試

**Objective:** 以 TDD 驗證前後快照的新增、移除與名次變動邏輯。

**Files:**
- Create: `/home/jerry/ntpc-childcare-dashboard/tests/test_tracker.py`
- Modify: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/tracker.py`

**Verification:** `python3 -m unittest discover -s tests -v`

### Task 3: 實作 API payload 解析與快照摘要

**Objective:** 從 LoveBaby API payload 解析有效名單、總數、上月入托數與可追蹤欄位。

**Files:**
- Modify: `/home/jerry/ntpc-childcare-dashboard/tests/test_tracker.py`
- Modify: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/tracker.py`

**Verification:** `python3 -m unittest discover -s tests -v`

### Task 4: 實作 dashboard HTML 產生器

**Objective:** 產生可直接開啟的單檔 HTML dashboard，內含摘要卡、趨勢、差異表與遞補原則區塊。

**Files:**
- Modify: `/home/jerry/ntpc-childcare-dashboard/src/ntpc_childcare_dashboard/render.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/tests/test_render.py`

**Verification:** `python3 -m unittest discover -s tests -v`

### Task 5: 串接更新腳本與資料落地

**Objective:** 抓取遠端 API、載入前一次快照、寫入新快照、重建 dashboard。

**Files:**
- Modify: `/home/jerry/ntpc-childcare-dashboard/scripts/update_dashboard.py`
- Create: `/home/jerry/ntpc-childcare-dashboard/data/.gitkeep`

**Verification:** `python3 /home/jerry/ntpc-childcare-dashboard/scripts/update_dashboard.py`

### Task 6: 設定每日排程

**Objective:** 讓 dashboard 每日自動更新，並保存變更紀錄。

**Files:**
- Modify: `/home/jerry/ntpc-childcare-dashboard/README.md`

**Verification:** 列出排程設定並手動執行一次排程任務。
