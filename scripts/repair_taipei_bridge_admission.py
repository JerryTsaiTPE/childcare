"""One-time, evidence-preserving correction for the 三重台北橋 admission archive.

The live archive is append-only during normal updates.  This narrow repair uses the
original history evidence for the reported timestamp, backs up admissions.json, and
replaces only that archive record.  It never calls the LoveBaby API.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ORG_ID = "Z0026"
TIMESTAMP_PREFIX = "2026-07-27T15:49"
EXPECTED_ADMITTED_NAME = "陳O軒"
EXCLUDED_NEW_YEAR_NAME = "劉O誠"


def load_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"找不到資料檔：{path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON 格式無效：{path}") from error
    if not isinstance(payload, list):
        raise ValueError(f"預期 JSON 陣列：{path}")
    return payload


def find_exactly_one(records: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    matches = [record for record in records if str(record.get("fetched_at", "")).startswith(TIMESTAMP_PREFIX)]
    if len(matches) != 1:
        raise ValueError(f"{label} 中應只有一筆 {TIMESTAMP_PREFIX} 紀錄，實際為 {len(matches)} 筆。")
    return matches[0]


def repair_archive(data_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    """Prepare or apply the single-record correction, preserving all other records."""
    center_dir = Path(data_dir) / ORG_ID
    history_path = center_dir / "history.json"
    admissions_path = center_dir / "admissions.json"
    history = load_json_list(history_path)
    admissions = load_json_list(admissions_path)

    history_record = find_exactly_one(history, label="history.json")
    archive_record = find_exactly_one(admissions, label="admissions.json")
    candidates = [
        detail for detail in (history_record.get("removed_details") or [])
        if str(detail.get("name", "")) == EXPECTED_ADMITTED_NAME
    ]
    if len(candidates) != 1:
        raise ValueError(f"history.json 中應只有一位 {EXPECTED_ADMITTED_NAME}，實際為 {len(candidates)} 位。")
    if not any(str(detail.get("name", "")) == EXCLUDED_NEW_YEAR_NAME for detail in (history_record.get("removed_details") or [])):
        raise ValueError(f"history.json 未找到預期排除的 {EXCLUDED_NEW_YEAR_NAME}，停止修改。")

    corrected_person = {**candidates[0], "status": "遞補入托"}
    corrected_record = {
        **archive_record,
        "admitted_count": 1,
        "admitted_details": [corrected_person],
    }
    repaired = [corrected_record if item is archive_record else item for item in admissions]
    result: dict[str, Any] = {
        "changed": False,
        "apply": apply,
        "history_path": history_path,
        "admissions_path": admissions_path,
        "backup_path": None,
        "admitted_name": EXPECTED_ADMITTED_NAME,
        "excluded_name": EXCLUDED_NEW_YEAR_NAME,
    }
    if not apply:
        return result

    backup_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = admissions_path.with_name(f"admissions.json.bak-{backup_stamp}")
    shutil.copy2(admissions_path, backup_path)
    temporary_path = admissions_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(admissions_path)
    result["changed"] = True
    result["backup_path"] = backup_path
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="修正三重台北橋 2026-07-27 15:49 的已入托封存紀錄")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
        help="包含 Z0026 目錄的 data 路徑",
    )
    parser.add_argument("--apply", action="store_true", help="實際寫入；省略時只驗證，不修改資料")
    args = parser.parse_args()
    try:
        result = repair_archive(args.data_dir, apply=args.apply)
    except ValueError as error:
        print(f"❌ 未修改：{error}")
        return 1
    if not args.apply:
        print("✅ 驗證成功；尚未修改資料。確認後以 --apply 執行。")
        return 0
    print(f"✅ 已修正為遞補入托：{result['admitted_name']}；已排除：{result['excluded_name']}")
    print(f"📦 備份：{result['backup_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
