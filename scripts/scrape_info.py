#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import random
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

# 強制 Windows 控制台使用 UTF-8 編碼
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
CACHE_FILE = DATA_DIR / 'info_cache.json'
API_BACKOFF_FILE = DATA_DIR / 'api_backoff.json'
UPDATE_HISTORY_FILE = DATA_DIR / 'update_history.jsonl'
UPDATE_LOCK_FILE = DATA_DIR / 'update.lock'

CENTER_REQUEST_INTERVAL_MIN_SECONDS = 2.0
CENTER_REQUEST_INTERVAL_MAX_SECONDS = 5.0
MAX_CENTER_REQUESTS_PER_BATCH = 10
BATCH_REST_MIN_SECONDS = 15.0
BATCH_REST_MAX_SECONDS = 35.0
LOCK_STALE_AFTER_SECONDS = 3 * 60 * 60


def _as_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)


def _parse_iso_datetime(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return _as_utc(parsed)


def get_target_orgs() -> list[str]:
    org_file = ROOT / 'scripts' / 'org_ids.txt'
    if not org_file.exists():
        print(f"❌ 找不到中心名單檔：{org_file}")
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


def get_service_proxy_url(raw_value: str | None = None) -> str | None:
    value = os.environ.get('CHILDCARE_API_PROXY') if raw_value is None else raw_value
    if value is None or not str(value).strip():
        return None
    proxy_url = str(value).strip()
    parsed = urlsplit(proxy_url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('CHILDCARE_API_PROXY 必須是完整的 http:// 或 https:// proxy URL，例如 http://127.0.0.1:8080')
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
    parsed = urlsplit(proxy_url)
    host = parsed.hostname or 'invalid-host'
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    return f'{parsed.scheme}://{host}{":" + str(parsed.port) if parsed.port else ""}'


def probe_service_proxy(proxy_url: str, *, timeout_seconds: float = 3.0) -> str | None:
    parsed = urlsplit(proxy_url)
    host = parsed.hostname
    if not host:
        return f'Proxy 位址無效：{redact_proxy_url(proxy_url)}'
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        connection = socket.create_connection((host, port), timeout=timeout_seconds)
        connection.close()
    except OSError as error:
        return f'無法連線至 {redact_proxy_url(proxy_url)}：{error}'
    return None


def is_api_circuit_open(state_path: Path, *, now: datetime | None = None) -> bool:
    state = load_json(state_path, {})
    blocked_until = state.get('blocked_until')
    if not blocked_until:
        return False
    try:
        deadline = datetime.fromisoformat(str(blocked_until))
    except ValueError:
        return False
    current_time = _as_utc(now)
    deadline = _as_utc(deadline)
    return current_time < deadline


def acquire_run_lock(path: Path, *, run_id: str, now: datetime | None = None, stale_after_seconds: int = LOCK_STALE_AFTER_SECONDS) -> bool:
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


def fetch_info_via_playwright(page, org_id: str) -> tuple[str, str]:
    print(f"   🕷️ 爬取 {org_id} 網頁中...")
    try:
        url = f"https://lovebaby.sw.ntpc.gov.tw/#/waiting-list/{org_id}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(1.5)
        
        full_page_text = page.evaluate("document.body.innerText")
        
        memo_text = "中心未提供相關說明"
        start_idx = full_page_text.find("相關說明：")
        if start_idx != -1:
            extracted = full_page_text[start_idx:]
            footer_idx = extracted.find("福利專區")
            if footer_idx != -1:
                extracted = extracted[:footer_idx]
            memo_text = extracted.strip()

        date_match = re.search(r'有效期限至[^\d]*([0-9]{3,4}/[0-9]{1,2}/[0-9]{1,2})', full_page_text)
        validity_text = f"有效期限至 {date_match.group(1)}" if date_match else "請依各中心公告為主"

        print(f"   ✅ 成功爬取 {org_id}")
        return memo_text, validity_text
    except Exception as e:
        print(f"   ❌ 爬取 {org_id} 失敗 ({e})")
        return "自動爬取說明失敗，請手動前往網頁查看。", "無法取得期限"


def run_scraper_cycle(run_id: str) -> int:
    TARGET_ORGS = get_target_orgs()
    if not TARGET_ORGS:
        print("名單為空，終止執行。")
        return 1

    try:
        api_proxy_url = get_service_proxy_url()
    except ValueError as error:
        print(f"❌ {error}")
        return 1

    if api_proxy_url:
        print(f"🌐 爬蟲服務將透過代理出口：{redact_proxy_url(api_proxy_url)}")

    update_history_path = DATA_DIR / UPDATE_HISTORY_FILE.name
    
    if is_api_circuit_open(API_BACKOFF_FILE):
        backoff_state = load_json(API_BACKOFF_FILE, {})
        print(f"🛑 API 融斷冷卻中，停止爬蟲作業。冷卻截止：{backoff_state.get('blocked_until')}")
        append_update_history(update_history_path, {'event': 'scraper_skipped_circuit_open', 'run_id': run_id})
        return 1

    if api_proxy_url:
        proxy_error = probe_service_proxy(api_proxy_url)
        if proxy_error:
            append_update_history(update_history_path, {'event': 'scraper_proxy_probe_failed', 'run_id': run_id})
            print(f"❌ 爬蟲已停止：{proxy_error}")
            return 1

    cache = load_json(CACHE_FILE, {})
    
    # 設定 Playwright 啟動參數
    launch_options = {"headless": True}
    if api_proxy_url:
        launch_options["proxy"] = {"server": api_proxy_url}

    print("====================================")
    print("🚀 開始執行重度爬蟲 (低頻防封鎖模式)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_options)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for idx, org_id in enumerate(TARGET_ORGS, start=1):
            # 每 MAX_CENTER_REQUESTS_PER_BATCH 筆進行小休息
            if idx > 1 and (idx - 1) % MAX_CENTER_REQUESTS_PER_BATCH == 0:
                rest_s = random.uniform(BATCH_REST_MIN_SECONDS, BATCH_REST_MAX_SECONDS)
                print(f"   ⏸️ 已爬取 {idx - 1} 筆，批次休息 {rest_s:.1f} 秒...")
                time.sleep(rest_s)

            # 單一請求間的低頻防護間隔
            interval_s = random.uniform(CENTER_REQUEST_INTERVAL_MIN_SECONDS, CENTER_REQUEST_INTERVAL_MAX_SECONDS)
            time.sleep(interval_s)

            memo, val = fetch_info_via_playwright(page, org_id)
            cache[org_id] = {
                "related_info_text": memo,
                "validity_text": val,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            # 即時儲存，降低中途崩潰風險
            save_json(CACHE_FILE, cache)

        browser.close()

    print("====================================")
    print(f"🎉 爬蟲更新完畢！資料已快取至 {CACHE_FILE.name}")
    return 0


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"scraper-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    lock_path = DATA_DIR / UPDATE_LOCK_FILE.name
    update_history_path = DATA_DIR / UPDATE_HISTORY_FILE.name

    if not acquire_run_lock(lock_path, run_id=run_id):
        append_update_history(update_history_path, {'event': 'scraper_skipped_lock_held', 'run_id': run_id})
        print("🛑 已有其他更新/爬蟲程序執行中；本次爬蟲取消執行。")
        sys.exit(2)

    append_update_history(update_history_path, {'event': 'scraper_lock_acquired', 'run_id': run_id})
    try:
        result = run_scraper_cycle(run_id)
        append_update_history(update_history_path, {'event': 'scraper_completed', 'run_id': run_id, 'exit_code': result})
        sys.exit(result)
    except Exception as error:
        append_update_history(update_history_path, {'event': 'scraper_failed', 'run_id': run_id, 'error_type': type(error).__name__})
        raise
    finally:
        release_run_lock(lock_path, run_id=run_id)


if __name__ == '__main__':
    main()