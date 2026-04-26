#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.request
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8 編碼
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 定義專案路徑
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ntpc_childcare_dashboard.render import render_dashboard
from ntpc_childcare_dashboard.tracker import (
    build_change_record,
    diff_snapshots,
    make_history_entry,
    parse_standby_payload,
)

# 💡 升級版：支援 [區域] 標籤與行內 #註解 的讀取邏輯
def get_target_orgs():
    org_file = ROOT / 'scripts' / 'org_ids.txt'
    if not org_file.exists():
        return []
    
    orgs = []
    with open(org_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 略過空行、全行註解、以及 [區域] 標籤
            if not line or line.startswith('#') or line.startswith('['):
                continue
            # 處理行內註解，例如 "Z0014 #淡水淡海"，只取 # 前面的部分
            org_id = line.split('#')[0].strip()
            if org_id:
                orgs.append(org_id)
    return orgs

API_ORGS = 'https://lovebaby.sw.ntpc.gov.tw/webapi/Org/GetPublicNpsOrgList'
DATA_DIR = ROOT / 'data'
INDEX_PATH = ROOT / 'index.html'
CACHE_FILE = DATA_DIR / 'info_cache.json'

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Referer': 'https://lovebaby.sw.ntpc.gov.tw/',
        },
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        return json.load(response)

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception as e:
        print(f"⚠️ 警告：無法讀取 {path.name} ({e})，使用預設空資料。")
        return default

def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

def trim_history(history: list[dict], limit: int = 1000) -> list[dict]:
    if len(history) <= limit:
        return history
    return history[-limit:]


def main() -> int:
    TARGET_ORGS = get_target_orgs()
    if not TARGET_ORGS:
        print("❌ 無法載入中心名單 (org_ids.txt)，請檢查路徑或檔案內容。")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print("🚀 [高速模式] 獲取新北市公托清單...")
    try:
        orgs_payload = fetch_json(API_ORGS)
        org_info_map = {item.get('orgid'): item for item in orgs_payload.get('data') or []}
    except Exception as e:
        print(f"獲取公托清單失敗: {e}")
        org_info_map = {}

    # 💡 載入網頁說明快取
    info_cache = load_json(CACHE_FILE, {})

    all_org_data = {} 

    for org_id in TARGET_ORGS:
        org_dir = DATA_DIR / org_id
        org_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = org_dir / 'snapshots'
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        latest_path = org_dir / 'latest_snapshot.json'
        changes_path = org_dir / 'changes.json'
        history_path = org_dir / 'history.json'

        org_info = org_info_map.get(org_id, {"orgid": org_id, "orgname": "未知中心", "orgshort": org_id, "distdesc": "未知"})

        # --- 步驟 1: 高速抓取 API 的 JSON 數據 ---
        api_standby = f'https://lovebaby.sw.ntpc.gov.tw/webapi/NpsApply/GetStandbyList?orgid={org_id}'
        try:
            standby_payload = fetch_json(api_standby)
        except Exception as e:
            print(f"   ⚠️ 抓取 {org_id} API 失敗，略過。")
            continue

        # --- 步驟 2: 從快取讀取網頁文字 (瞬間完成) ---
        cached_org_info = info_cache.get(org_id, {})
        center_memo = cached_org_info.get("related_info_text", "尚未抓取中心說明，請手動執行一次 run_slow_scraper.bat")
        center_validity = cached_org_info.get("validity_text", "未知 (需執行快取更新)")

        parsed = parse_standby_payload(standby_payload)
        tz_taipei = timezone(timedelta(hours=8))
        fetched_at = datetime.now(tz_taipei).isoformat(timespec='seconds')

        snapshot = {
            'org': org_info,
            'fetched_at': fetched_at,
            **parsed,
        }

        previous_snapshot = load_json(latest_path, {})
        if not isinstance(previous_snapshot, dict): previous_snapshot = {}
        previous_entries = previous_snapshot.get('entries', [])

        diff = diff_snapshots(previous_entries, snapshot['entries'])
        change_record = build_change_record(
            fetched_at=fetched_at,
            diff=diff,
            previous_count=(previous_snapshot or {}).get('waiting_count'),
            current_count=snapshot['waiting_count'],
        )

        history = load_json(history_path, [])
        if not isinstance(history, list): history = []
        history.append(make_history_entry(snapshot, change_record))
        history = trim_history(history)

        changes = load_json(changes_path, [])
        if not isinstance(changes, list): changes = []
        changes.append(change_record)
        changes = trim_history(changes, limit=500)

        last_meaningful_change = change_record
        for c in reversed(changes):
            if c.get("changed"):
                last_meaningful_change = c
                break

        stamp = fetched_at.replace(':', '-').replace('+08-00', '+08_00')
        save_json(snapshot_dir / f'{stamp}.json', snapshot)
        save_json(latest_path, snapshot)
        save_json(history_path, history)
        save_json(changes_path, changes)

        all_org_data[org_id] = {
            "snapshot": snapshot,
            "latest_change": last_meaningful_change,
            "history": history,
            "related_info_text": center_memo,
            "validity_text": center_validity
        }
        
        print(f"✅ {org_id} 高速更新完成。")

    if not all_org_data:
        print("沒有成功抓取任何中心資料，終止執行。")
        return 1

    # ==========================================
    # 🔍 全域交叉比對重複登記邏輯 (包含身分別)
    # ==========================================
    global_map = {}
    for oid, data in all_org_data.items():
        o_name = data['snapshot']['org']['orgshort']
        for entry in data['snapshot']['entries']:
            # 💡 在這裡加上 displaydesc 作為比對條件
            key = (entry['encname'], entry['cbirthday'], entry.get('displaydesc', '')) 
            if key not in global_map: 
                global_map[key] = []
            global_map[key].append({"org_name": o_name, "index": entry['index'], "org_id": oid})

    for oid, data in all_org_data.items():
        for entry in data['snapshot']['entries']:
            # 💡 在這裡也加上 displaydesc
            key = (entry['encname'], entry['cbirthday'], entry.get('displaydesc', ''))
            others = [m for m in global_map[key] if m['org_id'] != oid]
            entry['sync_list'] = [f"{o['org_name']}({o['index']})" for o in others]

    print("====================================")
    print("產生 HTML 儀表板...")
    html = render_dashboard(all_data=all_org_data, rule_text="", validity_text="", related_info_text="")
    INDEX_PATH.write_text(html, encoding='utf-8')
    print("🎉 高速更新與推播全部完成！")
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)