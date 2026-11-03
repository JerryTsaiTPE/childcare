#!/usr/bin/env python3
"""Telegram Notifier & Alert Manager for NTPC Childcare Dashboard.

Handles Telegram notifications with state-aware deduplication and rate limiting
to avoid alert fatigue during extended outages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "telegram.json"
STATE_FILE = ROOT / "data" / "alert_state.json"

TAIPEI_TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"enabled": False}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ [Telegram] 無法讀取設定檔 {CONFIG_FILE}: {e}", file=sys.stderr)
        return {"enabled": False}


def load_state() -> dict:
    default_state = {
        "is_failing": False,
        "first_failed_at": None,
        "last_failed_at": None,
        "fail_count": 0,
        "last_notified_at": None,
        "last_error_reason": None,
    }
    if not STATE_FILE.exists():
        return default_state
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return {**default_state, **json.load(f)}
    except Exception as e:
        print(f"⚠️ [Telegram] 無法讀取狀態檔 {STATE_FILE}: {e}", file=sys.stderr)
        return default_state


def save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ [Telegram] 無法儲存狀態檔 {STATE_FILE}: {e}", file=sys.stderr)


def send_telegram_message(text: str, *, parse_mode: str = "HTML", timeout: float = 15.0) -> bool:
    """Send message via Telegram Bot API safely without crashing callers."""
    config = load_config()
    if not config.get("enabled", False):
        return False

    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        print("⚠️ [Telegram] 缺少 bot_token 或 chat_id", file=sys.stderr)
        return False

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"❌ [Telegram] 發送失敗 HTTP {e.code}: {err_body}", file=sys.stderr)
    except URLError as e:
        print(f"❌ [Telegram] 連線失敗 (URLError): {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"❌ [Telegram] 未知發送錯誤: {e}", file=sys.stderr)

    return False


def record_failure(error_reason: str, *, detail: str | None = None, log_file: str | None = None) -> bool:
    """Record an update failure, alerting immediately on first failure and throttling thereafter."""
    config = load_config()
    if not config.get("enabled", False):
        return False

    now_dt = datetime.now(TAIPEI_TZ)
    now_str = _now_iso()
    state = load_state()
    silence_hours = float(config.get("silence_interval_hours", 6))

    was_failing = state.get("is_failing", False)
    fail_count = state.get("fail_count", 0) + 1
    last_notified_at_str = state.get("last_notified_at")

    state["is_failing"] = True
    state["fail_count"] = fail_count
    state["last_failed_at"] = now_str
    state["last_error_reason"] = error_reason
    if not was_failing:
        state["first_failed_at"] = now_str

    should_notify = False
    is_first_failure = not was_failing

    if is_first_failure:
        should_notify = True
    elif last_notified_at_str:
        try:
            last_notified_dt = datetime.fromisoformat(last_notified_at_str)
            if (now_dt - last_notified_dt) >= timedelta(hours=silence_hours):
                should_notify = True
        except Exception:
            should_notify = True
    else:
        should_notify = True

    if should_notify:
        title = "🚨 <b>【新北市公托儀表板】更新異常警報</b>" if is_first_failure else f"⚠️ <b>【公托儀表板】持續異常提醒 (已連續 {fail_count} 次)</b>"
        lines = [
            title,
            "━━━━━━━━━━━━━━━━━━━━",
            f"🕒 <b>發生時間</b>：{now_str}",
            f"❌ <b>錯誤原因</b>：<code>{error_reason}</code>",
        ]
        if detail:
            clean_detail = detail[:300].strip()
            lines.append(f"📝 <b>詳細摘要</b>：\n<pre>{clean_detail}</pre>")
        if log_file:
            lines.append(f"📁 <b>日誌位置</b>：<code>{os.path.basename(log_file)}</code>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        if is_first_failure:
            lines.append(f"ℹ️ <i>若異常持續，系統將每 {int(silence_hours)} 小時彙整提醒一次，避免打擾。</i>")

        msg = "\n".join(lines)
        sent = send_telegram_message(msg)
        if sent:
            state["last_notified_at"] = now_str
            print("📣 [Telegram] 異常警報已成功發送。")

    save_state(state)
    return should_notify


def record_success() -> bool:
    """Record a successful run. Sends recovery alert only if previously failing."""
    config = load_config()
    if not config.get("enabled", False):
        return False

    state = load_state()
    if not state.get("is_failing", False):
        return False

    fail_count = state.get("fail_count", 0)
    first_failed_at = state.get("first_failed_at", "未知時間")
    now_str = _now_iso()

    msg = "\n".join([
        "🎉 <b>【新北市公托儀表板】服務已恢復正常！</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕒 <b>恢復時間</b>：{now_str}",
        f"📊 <b>異常統計</b>：自 {first_failed_at} 起共失敗 <b>{fail_count}</b> 次",
        "✅ <b>狀態說明</b>：資料已成功抓取並完成靜態網頁與 GitHub Pages 發布。",
        "━━━━━━━━━━━━━━━━━━━━",
    ])

    sent = send_telegram_message(msg)
    if sent:
        print("📣 [Telegram] 服務恢復正常通知已發送。")

    save_state({
        "is_failing": False,
        "first_failed_at": None,
        "last_failed_at": None,
        "fail_count": 0,
        "last_notified_at": None,
        "last_error_reason": None,
    })
    return True


def main():
    parser = argparse.ArgumentParser(description="Telegram Alert Utility for Childcare Dashboard")
    parser.add_argument("--test", action="store_true", help="Send a test message")
    parser.add_argument("--notify-failure", type=str, help="Manually trigger failure alert")
    parser.add_argument("--detail", type=str, default=None, help="Optional error detail")
    parser.add_argument("--notify-success", action="store_true", help="Manually trigger success/recovery check")
    args = parser.parse_args()

    if args.test:
        test_msg = (
            "🤖 <b>新北市公托儀表板 - Telegram 機器人連線成功！</b>\n\n"
            "此頻道將在此專案遇到網路斷線、Proxy 逾時或更新失敗時發送即時告警通知。"
        )
        ok = send_telegram_message(test_msg)
        if ok:
            print("✅ 測試訊息發送成功！")
            sys.exit(0)
        else:
            print("❌ 測試訊息發送失敗，請確認已在 Telegram 對機器人按過 Start。")
            sys.exit(1)

    if args.notify_failure:
        record_failure(args.notify_failure, detail=args.detail)
        sys.exit(0)

    if args.notify_success:
        record_success()
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
