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
    build_admission_archive_record,
    build_change_record,
    diff_snapshots,
    is_suspicious_empty_waitlist,
    make_history_entry,
    parse_standby_payload,
)

def get_target_orgs():
    org_file = ROOT / 'scripts' / 'org_ids.txt'
    if not org_file.exists():
        return []
    
    orgs = []
    with open(org_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('['):
                continue
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


def is_strictly_two_years_old(birthday: str, fetched_at: str) -> bool:
    """Match the dashboard's calendar-age rule for age-out candidates."""
    try:
        birth = datetime.fromisoformat(str(birthday)).date()
        observed = datetime.fromisoformat(str(fetched_at)[:10]).date()
        return (observed.year - birth.year, observed.month, observed.day) >= (2, birth.month, birth.day)
    except (TypeError, ValueError):
        return False


def select_archived_admissions(
    history_entry: dict, other_current_entries: set[tuple[str, str, str]]
) -> list[dict]:
    """Freeze the same admission inference used by the dashboard at update time."""
    enroll_delta = int(history_entry.get("enroll_delta") or 0)
    if enroll_delta <= 0:
        return []

    candidates = []
    for removed in history_entry.get("removed_details") or []:
        identity = (str(removed.get("name", "")), str(removed.get("birthday", "")), str(removed.get("category", "")))
        if not is_strictly_two_years_old(removed.get("birthday", ""), history_entry.get("fetched_at", "")) and identity not in other_current_entries:
            candidates.append(removed)
    candidates.sort(key=lambda item: int(item.get("previous_index") or 0))
    if len(candidates) <= enroll_delta:
        return candidates
    # Keep the established display rule: first N-1 candidates plus the final
    # candidate, which reflects the observed notification ordering.
    return candidates[: max(0, enroll_delta - 1)] + candidates[-1:]


def load_cached_center_data(
    *,
    latest_path: Path,
    history_path: Path,
    changes_path: Path,
    admissions: list,
    admissions_path: Path,
    related_info_text: str,
    validity_text: str,
) -> dict | None:
    """Keep a center visible with its last verified data when a fetch is unsafe."""
    snapshot = load_json(latest_path, {})
    if not isinstance(snapshot, dict) or not snapshot.get("org"):
        return None
    history = load_json(history_path, [])
    changes = load_json(changes_path, [])
    if not isinstance(history, list):
        history = []
    if not isinstance(changes, list):
        changes = []
    latest_change = next((item for item in reversed(changes) if item.get("changed")), {})
    return {
        "snapshot": snapshot,
        "latest_change": latest_change,
        "history": history,
        "admissions": admissions,
        "admissions_path": admissions_path,
        "related_info_text": related_info_text,
        "validity_text": validity_text,
    }


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
        admissions_path = org_dir / 'admissions.json'
        admissions = load_json(admissions_path, [])
        if not isinstance(admissions, list): admissions = []

        org_info = org_info_map.get(org_id, {"orgid": org_id, "orgname": "未知中心", "orgshort": org_id, "distdesc": "未知"})
        cached_org_info = info_cache.get(org_id, {})
        center_memo = cached_org_info.get("related_info_text", "尚未抓取中心說明，請手動執行一次 run_slow_scraper.bat")
        center_validity = cached_org_info.get("validity_text", "未知 (需執行快取更新)")

        api_standby = f'https://lovebaby.sw.ntpc.gov.tw/webapi/NpsApply/GetStandbyList?orgid={org_id}'
        try:
            standby_payload = fetch_json(api_standby)
        except Exception:
            cached_data = load_cached_center_data(
                latest_path=latest_path, history_path=history_path, changes_path=changes_path,
                admissions=admissions, admissions_path=admissions_path,
                related_info_text=center_memo, validity_text=center_validity,
            )
            if cached_data:
                all_org_data[org_id] = cached_data
            print(f"   ⚠️ 抓取 {org_id} API 失敗，保留上次有效資料。")
            continue

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
        if not isinstance(previous_entries, list): previous_entries = []
        if is_suspicious_empty_waitlist(previous_entries, snapshot['entries']):
            cached_data = load_cached_center_data(
                latest_path=latest_path, history_path=history_path, changes_path=changes_path,
                admissions=admissions, admissions_path=admissions_path,
                related_info_text=center_memo, validity_text=center_validity,
            )
            if cached_data:
                all_org_data[org_id] = cached_data
            print(f"   ⚠️ {org_id} 回傳空名單但上次有 {len(previous_entries)} 筆，判定來源異常；保留上次有效資料。")
            continue

        prev_enroll = 0
        if previous_snapshot and 'org' in previous_snapshot and 'enroll_count' in previous_snapshot['org']:
            try:
                prev_enroll = int(previous_snapshot['org']['enroll_count'])
            except:
                pass
                
        curr_enroll = 0
        if 'org' in snapshot and 'enroll_count' in snapshot['org']:
            try:
                curr_enroll = int(snapshot['org']['enroll_count'])
            except:
                pass
                
        enroll_delta = curr_enroll - prev_enroll if previous_snapshot else 0

        diff = diff_snapshots(previous_entries, snapshot['entries'])
        change_record = build_change_record(
            fetched_at=fetched_at,
            diff=diff,
            previous_count=(previous_snapshot or {}).get('waiting_count'),
            current_count=snapshot['waiting_count'],
            active_years=list((snapshot.get('entries_by_year') or {}).keys()),
        )
        
        # 將變化量與前後數值都塞入變動紀錄中
        change_record['enroll_delta'] = enroll_delta
        change_record['prev_enroll'] = prev_enroll
        change_record['curr_enroll'] = curr_enroll

        history = load_json(history_path, [])
        if not isinstance(history, list): history = []
        
        # 💡 關鍵修正：繞過過濾器，強制將入托數據寫入歷史紀錄的節點中
        new_hist_entry = make_history_entry(snapshot, change_record)
        new_hist_entry['enroll_delta'] = enroll_delta
        new_hist_entry['prev_enroll'] = prev_enroll
        new_hist_entry['curr_enroll'] = curr_enroll
        history.append(new_hist_entry)
        
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
            "admissions": admissions,
            "admissions_path": admissions_path,
            "related_info_text": center_memo,
            "validity_text": center_validity
        }
        
        print(f"✅ {org_id} 高速更新完成。")

    if not all_org_data:
        print("沒有成功抓取任何中心資料，終止執行。")
        return 1

    global_map = {}
    for oid, data in all_org_data.items():
        o_name = data['snapshot']['org']['orgshort']
        for entry in data['snapshot']['entries']:
            key = (entry['encname'], entry['cbirthday'], entry.get('displaydesc', '')) 
            if key not in global_map: 
                global_map[key] = []
            global_map[key].append({"org_name": o_name, "index": entry['index'], "org_id": oid})

    for oid, data in all_org_data.items():
        for entry in data['snapshot']['entries']:
            key = (entry['encname'], entry['cbirthday'], entry.get('displaydesc', ''))
            others = [m for m in global_map[key] if m['org_id'] != oid]
            entry['sync_list'] = [f"{o['org_name']}({o['index']})" for o in others]

    # `history.json` is deliberately bounded for dashboard performance, but
    # admissions must remain queryable forever.  Freeze the current inference
    # once, write it to a separate append-only per-center archive, then expose
    # that archive to the static page.
    for oid, data in all_org_data.items():
        other_current_entries = set()
        for other_oid, other_data in all_org_data.items():
            if other_oid == oid:
                continue
            for entry in other_data['snapshot'].get('entries') or []:
                other_current_entries.add((
                    str(entry.get('encname', '')),
                    str(entry.get('cbirthday', '')),
                    str(entry.get('displaydesc', '')),
                ))

        archived_timestamps = {str(item.get('fetched_at', '')) for item in data['admissions']}
        for history_entry in data['history']:
            fetched_at = str(history_entry.get('fetched_at', ''))
            if not fetched_at or fetched_at in archived_timestamps:
                continue
            admitted_details = select_archived_admissions(history_entry, other_current_entries)
            if admitted_details:
                data['admissions'].append(build_admission_archive_record(history_entry, admitted_details))
                archived_timestamps.add(fetched_at)

        data['admissions'].sort(key=lambda item: str(item.get('fetched_at', '')))
        save_json(data.pop('admissions_path'), data['admissions'])

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