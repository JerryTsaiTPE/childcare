#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import re
import socket
import sys
import time
import argparse

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
ORG_LIST_CACHE_FILE = DATA_DIR / 'org_list_cache.json'
UPDATE_CURSOR_FILE = DATA_DIR / 'update_cursor.json'
UPDATE_HISTORY_FILE = DATA_DIR / 'update_history.jsonl'
UPDATE_LOCK_FILE = DATA_DIR / 'update.lock'
CENTER_REQUEST_INTERVAL_MIN_SECONDS = 2.0
CENTER_REQUEST_INTERVAL_MAX_SECONDS = 5.0
MAX_CENTER_REQUESTS_PER_BATCH = 10
BATCH_REST_MIN_SECONDS = 30.0
BATCH_REST_MAX_SECONDS = 70.0
ORG_LIST_CACHE_TTL_SECONDS = 24 * 60 * 60
LOCK_STALE_AFTER_SECONDS = 3 * 60 * 60
DEFAULT_BACKOFF_SECONDS = 60 * 60
MINIMUM_BACKOFF_SECONDS = 60 * 60


def _as_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)


def _parse_iso_datetime(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return _as_utc(parsed)


def plan_update_batches(target_orgs: list[str], *, start_index: int, batch_size: int = MAX_CENTER_REQUESTS_PER_BATCH) -> list[list[tuple[int, str]]]:
    """Return one complete, cursor-rotated cycle split into bounded batches."""
    if not target_orgs:
        return []
    if batch_size < 1:
        raise ValueError('batch_size 必須至少為 1')
    start = start_index % len(target_orgs)
    ordered = [((start + offset) % len(target_orgs), target_orgs[(start + offset) % len(target_orgs)]) for offset in range(len(target_orgs))]
    return [ordered[offset: offset + batch_size] for offset in range(0, len(ordered), batch_size)]


def center_request_interval_seconds(*, uniform=random.uniform) -> float:
    """Draw a fresh request-start interval for each center."""
    return uniform(CENTER_REQUEST_INTERVAL_MIN_SECONDS, CENTER_REQUEST_INTERVAL_MAX_SECONDS)


def batch_rest_seconds(*, batch_index: int, batch_count: int, uniform=random.uniform) -> float:
    if batch_index >= batch_count - 1:
        return 0
    return uniform(BATCH_REST_MIN_SECONDS, BATCH_REST_MAX_SECONDS)


def load_fresh_org_info_map(path: Path, *, ttl_seconds: int = ORG_LIST_CACHE_TTL_SECONDS, now: datetime | None = None) -> dict | None:
    payload = load_json(path, {})
    fetched_at = _parse_iso_datetime(payload.get('fetched_at')) if isinstance(payload, dict) else None
    data = payload.get('data') if isinstance(payload, dict) else None
    current_time = _as_utc(now)
    if not fetched_at or not isinstance(data, list) or current_time - fetched_at > timedelta(seconds=ttl_seconds):
        return None
    return {item.get('orgid'): item for item in data if isinstance(item, dict) and item.get('orgid')}


def save_org_info_cache(path: Path, payload: dict, *, now: datetime | None = None) -> None:
    save_json(path, {'fetched_at': _as_utc(now).isoformat(), 'data': list(payload.get('data') or [])})


def load_update_cursor(path: Path, *, total_orgs: int) -> dict:
    saved = load_json(path, {})
    if not isinstance(saved, dict) or total_orgs < 1:
        return {'next_index': 0, 'last_successful_org_id': None}
    try:
        next_index = int(saved.get('next_index', 0)) % total_orgs
    except (TypeError, ValueError):
        next_index = 0
    return {'next_index': next_index, 'last_successful_org_id': saved.get('last_successful_org_id')}


def save_update_cursor(path: Path, *, next_index: int, last_successful_org_id: str, total_orgs: int) -> None:
    save_json(path, {
        'next_index': next_index % total_orgs if total_orgs else 0,
        'last_successful_org_id': last_successful_org_id,
        'updated_at': _as_utc().isoformat(),
    })


def acquire_run_lock(path: Path, *, run_id: str, now: datetime | None = None, stale_after_seconds: int = LOCK_STALE_AFTER_SECONDS) -> bool:
    """Atomically acquire the updater lock; only reclaim locks older than the safe bound."""
    path.parent.mkdir(parents=True, exist_ok=True)
    current_time = _as_utc(now)
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing = load_json(path, {})
        created_at = _parse_iso_datetime(existing.get('created_at')) if isinstance(existing, dict) else None
        if not created_at or current_time - created_at <= timedelta(seconds=stale_after_seconds):
            return False
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return acquire_run_lock(path, run_id=run_id, now=current_time, stale_after_seconds=stale_after_seconds)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump({'run_id': run_id, 'created_at': current_time.isoformat(), 'pid': os.getpid()}, handle, ensure_ascii=False)
    return True


def release_run_lock(path: Path, *, run_id: str) -> None:
    existing = load_json(path, {})
    if isinstance(existing, dict) and existing.get('run_id') == run_id:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def append_update_history(path: Path, event: dict, *, now: datetime | None = None) -> None:
    """Append a secret-free event record for later, non-invasive rate-limit analysis."""
    current_time = _as_utc(now)
    blocked_terms = ('proxy', 'password', 'secret', 'token', 'authorization', 'cookie', 'credential')
    safe_event = {key: value for key, value in event.items() if not any(term in key.lower() for term in blocked_terms)}
    record = {
        'timestamp_utc': current_time.isoformat(),
        'timestamp_taipei': current_time.astimezone(timezone(timedelta(hours=8))).isoformat(),
        **safe_event,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')


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


def wait_for_center_request(*, previous_started_at: float | None, interval_seconds: float = CENTER_REQUEST_INTERVAL_MAX_SECONDS, monotonic_now=time.monotonic, sleep=time.sleep) -> None:
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


def probe_service_proxy(
    proxy_url: str, *, create_connection=socket.create_connection, timeout_seconds: float = 3.0
) -> str | None:
    """Return a safe diagnostic when the configured proxy TCP endpoint is unavailable."""
    parsed = urlsplit(proxy_url)
    host = parsed.hostname
    if not host:
        return f'Proxy 位址無效：{redact_proxy_url(proxy_url)}'
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        connection = create_connection((host, port), timeout=timeout_seconds)
    except OSError as error:
        return f'無法連線至 {redact_proxy_url(proxy_url)}：{error}'
    connection.close()
    return None


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

    removed_details = list(history_entry.get("removed_details") or [])
    active_years = sorted(
        (str(year) for year in (history_entry.get("waiting_count_by_year") or {}) if str(year)),
        key=lambda year: int(year) if year.isdigit() else -1,
    )
    newest_year = active_years[-1] if len(active_years) > 1 else None
    # During the annual overlap, a departure from the newly published list is
    # not evidence of a replacement admission when total departures exceed the
    # observed enrollment increase.  Only the outgoing list remains eligible.
    exclude_newest_year = bool(newest_year and len(removed_details) > enroll_delta)

    candidates = []
    for removed in removed_details:
        identity = (str(removed.get("name", "")), str(removed.get("birthday", "")), str(removed.get("category", "")))
        if (
            not is_strictly_two_years_old(removed.get("birthday", ""), history_entry.get("fetched_at", ""))
            and identity not in other_current_entries
            and not (exclude_newest_year and str(removed.get("apyear", "")) == newest_year)
        ):
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


def _run_update_cycle(*, run_id: str, first_batch_only: bool = False) -> int:
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
    update_history_path = DATA_DIR / UPDATE_HISTORY_FILE.name
    cursor_path = DATA_DIR / UPDATE_CURSOR_FILE.name
    org_list_cache_path = DATA_DIR / ORG_LIST_CACHE_FILE.name
    append_update_history(update_history_path, {
        'event': 'run_started', 'run_id': run_id, 'target_org_count': len(TARGET_ORGS),
        'batch_size': MAX_CENTER_REQUESTS_PER_BATCH,
        'center_interval_min_seconds': CENTER_REQUEST_INTERVAL_MIN_SECONDS,
        'center_interval_max_seconds': CENTER_REQUEST_INTERVAL_MAX_SECONDS,
        'batch_rest_min_seconds': BATCH_REST_MIN_SECONDS,
        'batch_rest_max_seconds': BATCH_REST_MAX_SECONDS,
    })
    backoff_state = load_api_backoff_state(API_BACKOFF_FILE)
    circuit_open = is_api_circuit_open(backoff_state)
    if api_proxy_url and not circuit_open:
        proxy_error = probe_service_proxy(api_proxy_url)
        if proxy_error:
            append_update_history(update_history_path, {
                'event': 'proxy_probe_failed', 'run_id': run_id, 'error_type': 'ProxyConnectionError',
            })
            print(f"❌ 更新已停止：{proxy_error}")
            print("   請先確認 proxy 主機已開機、Tailscale 連線正常，且 HTTP CONNECT proxy 正在監聽該連接埠。")
            return 1

    # `enroll_count` drives admission inference.  The source exposes it only
    # through the full center-list endpoint, so refresh that endpoint at the
    # beginning of every batch and use only the current batch's entries.  This
    # bounds the list/enrollment timing gap to one batch rather than one run.
    if circuit_open:
        print(
            "🛑 API 融斷冷卻中；不會發送任何 LoveBaby API 請求。"
            f" 冷卻截止：{backoff_state.get('blocked_until')}"
        )
        append_update_history(update_history_path, {'event': 'circuit_open_at_run_start', 'run_id': run_id, 'blocked_until': backoff_state.get('blocked_until')})
    else:
        print("🚀 [分批低頻模式] 每批開始前重新取得該批中心的 enroll_count...")

    cursor = load_update_cursor(cursor_path, total_orgs=len(TARGET_ORGS))
    batches = plan_update_batches(
        TARGET_ORGS, start_index=cursor['next_index'], batch_size=MAX_CENTER_REQUESTS_PER_BATCH
    )

    if first_batch_only and batches:
        print("⚡ [快速模式] 僅執行第一批次 (First Batch Only)...")
        batches = batches[:1]

    # 💡【關鍵修復】將 info_cache 移到這裡（在 planned_orgs 與迴圈開始前載入）
    info_cache = load_json(CACHE_FILE, {})

    planned_orgs = [(batch_index, org_index, org_id) for batch_index, batch in enumerate(batches) for org_index, org_id in batch]
    all_org_data = {}
    last_center_request_started_at = None
    active_batch_index = None
    batch_org_info_map: dict[str, dict] = {}
    batch_started_at = None
    enroll_count_fetched_at = None

    for batch_index, org_index, org_id in planned_orgs:
        if active_batch_index != batch_index:
            if active_batch_index is not None and not circuit_open:
                rest_seconds = batch_rest_seconds(batch_index=active_batch_index, batch_count=len(batches))
                if rest_seconds:
                    print(f"   ⏸️ 第 {active_batch_index + 1} 批完成，隨機休息 {rest_seconds:.1f} 秒。")
                    append_update_history(update_history_path, {'event': 'batch_rest_started', 'run_id': run_id, 'batch_index': active_batch_index + 1, 'rest_seconds': rest_seconds})
                    time.sleep(rest_seconds)
                    append_update_history(update_history_path, {'event': 'batch_rest_completed', 'run_id': run_id, 'batch_index': active_batch_index + 1})
            active_batch_index = batch_index
            batch_started_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
            append_update_history(update_history_path, {
                'event': 'batch_started', 'run_id': run_id, 'batch_index': batch_index + 1,
                'batch_size': len(batches[batch_index]), 'batch_started_at': batch_started_at,
            })

            if not circuit_open:
                org_list_started_at = time.monotonic()
                append_update_history(update_history_path, {
                    'event': 'batch_org_list_request_started', 'run_id': run_id,
                    'batch_index': batch_index + 1,
                })
                try:
                    orgs_payload = fetch_json(API_ORGS, proxy_url=api_proxy_url)
                    save_org_info_cache(org_list_cache_path, orgs_payload)
                    all_current_org_info = {
                        item.get('orgid'): item
                        for item in orgs_payload.get('data') or []
                        if isinstance(item, dict) and item.get('orgid')
                    }
                    batch_org_info_map = {
                        batch_org_id: all_current_org_info[batch_org_id]
                        for _, batch_org_id in batches[batch_index]
                        if batch_org_id in all_current_org_info
                    }
                    enroll_count_fetched_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
                    missing_org_ids = [
                        batch_org_id for _, batch_org_id in batches[batch_index]
                        if batch_org_id not in batch_org_info_map
                    ]
                    append_update_history(update_history_path, {
                        'event': 'batch_org_list_request_completed', 'run_id': run_id,
                        'batch_index': batch_index + 1, 'status': 'success',
                        'duration_ms': round((time.monotonic() - org_list_started_at) * 1000),
                        'enroll_count_fetched_at': enroll_count_fetched_at,
                        'missing_org_count': len(missing_org_ids),
                    })
                    if missing_org_ids:
                        print(
                            f"❌ 第 {batch_index + 1} 批中心清單未包含 {len(missing_org_ids)} 間目標中心，"
                            "為避免以不明入托數推定異動，本輪停止。"
                        )
                        return 1
                except HTTPError as error:
                    print(f"獲取第 {batch_index + 1} 批公托入托數失敗: HTTP {error.code} {error.reason}")
                    append_update_history(update_history_path, {
                        'event': 'batch_org_list_request_completed', 'run_id': run_id,
                        'batch_index': batch_index + 1, 'status': 'http_error',
                        'http_status': error.code,
                        'duration_ms': round((time.monotonic() - org_list_started_at) * 1000),
                    })
                    if error.code in (403, 429):
                        backoff_state = open_api_circuit(
                            state_path=API_BACKOFF_FILE, error=error, org_id=None
                        )
                        append_update_history(update_history_path, {
                            'event': 'circuit_opened', 'run_id': run_id,
                            'http_status': error.code, 'blocked_until': backoff_state['blocked_until'],
                            'scope': 'batch_org_list', 'batch_index': batch_index + 1,
                        })
                        print(
                            "🛑 已開啟 API 融斷，停止本輪後續請求。"
                            f" 冷卻截止：{backoff_state['blocked_until']}"
                        )
                    return 1
                except Exception as error:
                    print(f"獲取第 {batch_index + 1} 批公托入托數失敗: {error}")
                    append_update_history(update_history_path, {
                        'event': 'batch_org_list_request_completed', 'run_id': run_id,
                        'batch_index': batch_index + 1, 'status': 'error',
                        'error_type': type(error).__name__,
                        'duration_ms': round((time.monotonic() - org_list_started_at) * 1000),
                    })
                    return 1

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

        org_info = batch_org_info_map.get(org_id, {"orgid": org_id, "orgname": "未知中心", "orgshort": org_id, "distdesc": "未知"})
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
        request_interval_seconds = center_request_interval_seconds()
        wait_for_center_request(
            previous_started_at=last_center_request_started_at,
            interval_seconds=request_interval_seconds,
        )
        last_center_request_started_at = time.monotonic()
        request_started_at = last_center_request_started_at
        append_update_history(update_history_path, {
            'event': 'center_request_started', 'run_id': run_id, 'batch_index': batch_index + 1,
            'org_id': org_id, 'cursor_index': org_index,
            'request_interval_seconds': request_interval_seconds,
        })
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
            append_update_history(update_history_path, {
                'event': 'center_request_completed', 'run_id': run_id, 'batch_index': batch_index + 1,
                'org_id': org_id, 'cursor_index': org_index, 'status': 'http_error',
                'http_status': error.code, 'duration_ms': round((time.monotonic() - request_started_at) * 1000),
            })
            if error.code in (403, 429):
                backoff_state = open_api_circuit(
                    state_path=API_BACKOFF_FILE, error=error, org_id=org_id
                )
                circuit_open = True
                append_update_history(update_history_path, {
                    'event': 'circuit_opened', 'run_id': run_id, 'scope': 'center', 'org_id': org_id,
                    'http_status': error.code, 'blocked_until': backoff_state['blocked_until'],
                })
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
            append_update_history(update_history_path, {
                'event': 'center_request_completed', 'run_id': run_id, 'batch_index': batch_index + 1,
                'org_id': org_id, 'cursor_index': org_index, 'status': 'error',
                'error_type': type(error).__name__, 'duration_ms': round((time.monotonic() - request_started_at) * 1000),
            })
            print(f"   ⚠️ 抓取 {org_id} API 失敗 ({error})，保留上次有效資料。")
            continue

        parsed = parse_standby_payload(standby_payload)
        tz_taipei = timezone(timedelta(hours=8))
        fetched_at = datetime.now(tz_taipei).isoformat(timespec='seconds')

        snapshot = {
            'org': org_info,
            'fetched_at': fetched_at,
            'batch': {
                'index': batch_index + 1,
                'size': len(batches[batch_index]),
                'started_at': batch_started_at,
                'enroll_count_fetched_at': enroll_count_fetched_at,
            },
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
        change_record['batch_index'] = batch_index + 1
        change_record['batch_started_at'] = batch_started_at
        change_record['enroll_count_fetched_at'] = enroll_count_fetched_at

        history = load_json(history_path, [])
        if not isinstance(history, list): history = []
        
        # 💡 關鍵修正：繞過過濾器，強制將入托數據寫入歷史紀錄的節點中
        new_hist_entry = make_history_entry(snapshot, change_record)
        new_hist_entry['enroll_delta'] = enroll_delta
        new_hist_entry['prev_enroll'] = prev_enroll
        new_hist_entry['curr_enroll'] = curr_enroll
        new_hist_entry['batch_index'] = batch_index + 1
        new_hist_entry['batch_started_at'] = batch_started_at
        new_hist_entry['enroll_count_fetched_at'] = enroll_count_fetched_at
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
        save_update_cursor(
            cursor_path, next_index=org_index + 1, last_successful_org_id=org_id, total_orgs=len(TARGET_ORGS)
        )
        append_update_history(update_history_path, {
            'event': 'center_request_completed', 'run_id': run_id, 'batch_index': batch_index + 1,
            'org_id': org_id, 'cursor_index': org_index, 'status': 'success',
            'duration_ms': round((time.monotonic() - request_started_at) * 1000),
        })

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


def main() -> int:
    """Run exactly one lock-protected, observable update cycle."""
    # 💡 解析命令列參數
    parser = argparse.ArgumentParser(description="NTPC Childcare Dashboard Updater")
    parser.add_argument(
        "--first-batch-only",
        action="store_true",
        help="僅更新第一批次的機構，用於測試與快速驗證"
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}-{time.time_ns() % 1_000_000}"
    lock_path = DATA_DIR / UPDATE_LOCK_FILE.name
    update_history_path = DATA_DIR / UPDATE_HISTORY_FILE.name
    
    if not acquire_run_lock(lock_path, run_id=run_id):
        append_update_history(update_history_path, {'event': 'run_skipped_lock_held', 'run_id': run_id})
        print("🛑 已有更新程序執行中；本次不會發送任何 LoveBaby API 請求。")
        return 2
        
    append_update_history(update_history_path, {'event': 'run_lock_acquired', 'run_id': run_id})
    try:
        # 💡 將參數傳遞進 _run_update_cycle
        result = _run_update_cycle(run_id=run_id, first_batch_only=args.first_batch_only)
        append_update_history(update_history_path, {'event': 'run_completed', 'run_id': run_id, 'exit_code': result})
        return result
    except Exception as error:
        append_update_history(update_history_path, {'event': 'run_failed', 'run_id': run_id, 'error_type': type(error).__name__})
        raise
    finally:
        release_run_lock(lock_path, run_id=run_id)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)