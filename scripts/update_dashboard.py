#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time

import urllib.request
import ssl
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

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
API_BACKOFF_FILE = DATA_DIR / 'api_backoff.json'
CENTER_REQUEST_INTERVAL_SECONDS = 2.0
DEFAULT_BACKOFF_SECONDS = 15 * 60
MINIMUM_BACKOFF_SECONDS = 2 * 60


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> int | None:
    """Return Retry-After as seconds, supporting delta-seconds and HTTP-date."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        retry_at = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    return max(0, int((retry_at - current_time).total_seconds()))


def load_api_backoff_state(path: Path) -> dict:
    state = load_json(path, {})
    return state if isinstance(state, dict) else {}


def is_api_circuit_open(state: dict, *, now: datetime | None = None) -> bool:
    blocked_until = state.get('blocked_until')
    if not blocked_until:
        return False
    try:
        deadline = datetime.fromisoformat(str(blocked_until))
    except ValueError:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    return current_time < deadline


def decode_error_body(body: bytes, headers) -> str:
    """Decode an HTTP error body using its header or HTML-declared charset."""
    encodings = []
    if headers:
        content_charset = headers.get_content_charset()
        if content_charset:
            encodings.append(content_charset)
    declared = re.search(br"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)", body[:1024], re.IGNORECASE)
    if declared:
        encodings.append(declared.group(1).decode("ascii"))
    encodings.extend(["utf-8", "big5"])
    for encoding in dict.fromkeys(encodings):
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def open_api_circuit(*, state_path: Path, error: HTTPError, org_id: str | None, now: datetime | None = None) -> dict:
    """Persist the full HTTP failure evidence and a conservative cooldown."""
    current_time = now or datetime.now(timezone.utc)
    retry_after_raw = error.headers.get('Retry-After') if error.headers else None
    retry_after_seconds = parse_retry_after(retry_after_raw, now=current_time)
    cooldown_seconds = max(
        retry_after_seconds if retry_after_seconds is not None else DEFAULT_BACKOFF_SECONDS,
        MINIMUM_BACKOFF_SECONDS,
    )
    try:
        response_body_preview = decode_error_body(error.read(2000), error.headers)
    except Exception:
        response_body_preview = ''
    headers = dict(error.headers.items()) if error.headers else {}
    state = {
        'opened_at': current_time.isoformat(),
        'blocked_until': (current_time + timedelta(seconds=cooldown_seconds)).isoformat(),
        'status_code': error.code,
        'reason': str(error.reason),
        'org_id': org_id,
        'url': error.url,
        'retry_after_raw': retry_after_raw,
        'retry_after_seconds': retry_after_seconds,
        'applied_cooldown_seconds': cooldown_seconds,
        'headers': headers,
        'headers_raw': str(error.headers) if error.headers else '',
        'response_body_preview': response_body_preview,
    }

    save_json(state_path, state)
    return state


def wait_for_center_request(*, previous_started_at: float | None, interval_seconds: float = CENTER_REQUEST_INTERVAL_SECONDS, monotonic_now=time.monotonic, sleep=time.sleep) -> None:
    """Space center request start times without delaying the first request."""
    if previous_started_at is None:
        return
    remaining = interval_seconds - (monotonic_now() - previous_started_at)
    if remaining > 0:
        sleep(remaining)

def get_service_proxy_url(raw_value: str | None = None) -> str | None:
    """Read the opt-in proxy for this updater only, rejecting unsafe values."""
    value = os.environ.get('CHILDCARE_API_PROXY') if raw_value is None else raw_value
    if value is None or not str(value).strip():
        return None
    proxy_url = str(value).strip()
    parsed = urlsplit(proxy_url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError(
            'CHILDCARE_API_PROXY 必須是完整的 http:// 或 https:// proxy URL，例如 http://127.0.0.1:8080'
        )
    if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('CHILDCARE_API_PROXY 只能是 proxy 的主機與連接埠，不能包含路徑、query 或 fragment')
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError('CHILDCARE_API_PROXY 的連接埠格式不正確') from error
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('CHILDCARE_API_PROXY 的連接埠必須介於 1 到 65535')
    return proxy_url


def redact_proxy_url(proxy_url: str) -> str:
    """Return proxy endpoint for logs without exposing embedded credentials."""
    parsed = urlsplit(proxy_url)
    host = parsed.hostname or 'invalid-host'
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    return f'{parsed.scheme}://{host}{":" + str(parsed.port) if parsed.port else ""}'


def fetch_json(url: str, *, proxy_url: str | None = None) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Referer': 'https://lovebaby.sw.ntpc.gov.tw/',
        },
    )
    context = ssl._create_unverified_context()
    if proxy_url:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}),
            urllib.request.HTTPSHandler(context=context),
        )
        response_context = opener.open(req, timeout=30)
    else:
        response_context = urllib.request.urlopen(req, timeout=30, context=context)
    with response_context as response:
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

    try:
        api_proxy_url = get_service_proxy_url()
    except ValueError as error:
        print(f"❌ {error}")
        return 1
    if api_proxy_url:
        print(f"🌐 此更新服務將透過獨立 proxy 出口：{redact_proxy_url(api_proxy_url)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    backoff_state = load_api_backoff_state(API_BACKOFF_FILE)

    circuit_open = is_api_circuit_open(backoff_state)
    if circuit_open:
        print(
            "🛑 API 融斷冷卻中；不會發送任何 LoveBaby API 請求。"
            f" 冷卻截止：{backoff_state.get('blocked_until')}"
        )
        org_info_map = {}
    else:
        print("🚀 [低頻模式] 獲取新北市公托清單...")
        try:
            orgs_payload = fetch_json(API_ORGS, proxy_url=api_proxy_url)
            org_info_map = {item.get('orgid'): item for item in orgs_payload.get('data') or []}
        except HTTPError as error:
            print(f"獲取公托清單失敗: HTTP {error.code} {error.reason}")
            org_info_map = {}
            if error.code in (403, 429):
                backoff_state = open_api_circuit(
                    state_path=API_BACKOFF_FILE, error=error, org_id=None
                )
                circuit_open = True
                print(
                    "🛑 已開啟 API 融斷，停止本輪後續請求。"
                    f" 冷卻截止：{backoff_state['blocked_until']}"
                )
        except Exception as error:
            print(f"獲取公托清單失敗: {error}")
            org_info_map = {}

    info_cache = load_json(CACHE_FILE, {})
    all_org_data = {}
    last_center_request_started_at = None

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

        if circuit_open:
            cached_data = load_cached_center_data(
                latest_path=latest_path, history_path=history_path, changes_path=changes_path,
                admissions=admissions, admissions_path=admissions_path,
                related_info_text=center_memo, validity_text=center_validity,
            )
            if cached_data:
                all_org_data[org_id] = cached_data
            print(f"   ⏭️ {org_id} 因 API 融斷而略過，保留上次有效資料。")
            continue

        api_standby = f'https://lovebaby.sw.ntpc.gov.tw/webapi/NpsApply/GetStandbyList?orgid={org_id}'
        wait_for_center_request(previous_started_at=last_center_request_started_at)
        last_center_request_started_at = time.monotonic()
        try:
            standby_payload = fetch_json(api_standby, proxy_url=api_proxy_url)
        except HTTPError as error:
            cached_data = load_cached_center_data(
                latest_path=latest_path, history_path=history_path, changes_path=changes_path,
                admissions=admissions, admissions_path=admissions_path,
                related_info_text=center_memo, validity_text=center_validity,
            )
            if cached_data:
                all_org_data[org_id] = cached_data
            if error.code in (403, 429):
                backoff_state = open_api_circuit(
                    state_path=API_BACKOFF_FILE, error=error, org_id=org_id
                )
                circuit_open = True
                print(
                    f"   🛑 {org_id} 回傳 HTTP {error.code}，已開啟 API 融斷並停止後續請求。"
                    f" 冷卻截止：{backoff_state['blocked_until']}"
                )
            else:
                print(f"   ⚠️ {org_id} HTTP {error.code} {error.reason}，保留上次有效資料。")
            continue
        except Exception as error:
            cached_data = load_cached_center_data(
                latest_path=latest_path, history_path=history_path, changes_path=changes_path,
                admissions=admissions, admissions_path=admissions_path,
                related_info_text=center_memo, validity_text=center_validity,
            )
            if cached_data:
                all_org_data[org_id] = cached_data
            print(f"   ⚠️ 抓取 {org_id} API 失敗 ({error})，保留上次有效資料。")
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
    print("🎉 儀表板更新完成！")
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)