from __future__ import annotations

from datetime import datetime
from typing import Any


def entry_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("encname", "")),
        str(entry.get("cbirthday", "")),
        str(entry.get("displaydesc", "")),
    )


def parse_standby_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") or {}
    entries = [
        {
            "index": int(item.get("index", 0)),
            "encname": str(item.get("encname", "")),
            "cbirthday": str(item.get("cbirthday", "")),
            "displaydesc": str(item.get("displaydesc", "")),
        }
        for item in list(data.get("data") or [])
    ]
    entries.sort(key=lambda item: item["index"])
    return {
        "waiting_count": len(entries),
        "last_month_enrolled": data.get("lastnum"),
        "preshow": bool(data.get("preshow")),
        "entries": entries,
    }


def diff_snapshots(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    previous_map = {entry_key(item): item for item in previous}
    current_map = {entry_key(item): item for item in current}

    removed = [
        {
            "name": key[0],
            "birthday": key[1],
            "category": key[2],
            "previous_index": previous_map[key]["index"],
        }
        for key in previous_map
        if key not in current_map
    ]

    added = [
        {
            "name": key[0],
            "birthday": key[1],
            "category": key[2],
            "current_index": current_map[key]["index"],
        }
        for key in current_map
        if key not in previous_map
    ]

    moved = []
    for key in current_map:
        if key not in previous_map:
            continue
        previous_index = previous_map[key]["index"]
        current_index = current_map[key]["index"]
        if previous_index != current_index:
            moved.append(
                {
                    "name": key[0],
                    "birthday": key[1],
                    "category": key[2],
                    "previous_index": previous_index,
                    "current_index": current_index,
                    "delta": current_index - previous_index,
                }
            )

    moved.sort(key=lambda item: (item["current_index"], item["name"]))
    removed.sort(key=lambda item: (item["previous_index"], item["name"]))
    added.sort(key=lambda item: (item["current_index"], item["name"]))

    return {
        "removed": removed,
        "added": added,
        "moved": moved,
    }


def classify_removed_indexes(diff: dict[str, list[dict[str, Any]]], fetched_at: str) -> tuple[list[int], list[int], list[int]]:
    """
    將消失的名單分類為：屆齡取消、遞補入托、家長自行取消
    """
    removed_items = diff["removed"]
    if not removed_items:
        return [], [], []

    # 準備比對日期
    # fetched_at 格式為 2026-04-21T21:00:47+08:00
    current_date = datetime.fromisoformat(fetched_at.split('T')[0])
    
    likely_age_out = []
    likely_admitted = []
    likely_withdrawn = []

    THRESHOLD_INDEX = 15

    for item in removed_items:
        idx = item["previous_index"]
        birth_str = item["birthday"] # 格式 2025-01-22
        
        try:
            birth_date = datetime.strptime(birth_str, "%Y-%m-%d")
            # 計算差距天數
            days_old = (current_date - birth_date).days
            
            # 判斷是否為屆齡：滿兩歲是 730 天。
            # 規則：滿兩歲(>=730) 或 兩歲前14天 (>= 730 - 14 = 716)
            if days_old >= 716:
                likely_age_out.append(idx)
                continue
        except Exception:
            pass

        # 若不是屆齡，則依序號判斷
        if idx <= THRESHOLD_INDEX:
            likely_admitted.append(idx)
        else:
            likely_withdrawn.append(idx)
    
    return likely_age_out, likely_withdrawn, likely_admitted


def build_highlight_shift(diff: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    if not diff["moved"]:
        return None
    first = min(diff["moved"], key=lambda item: (item["current_index"], item["previous_index"]))
    return {
        "previous_index": first["previous_index"],
        "current_index": first["current_index"],
        "name": first["name"],
        "delta": first["delta"],
    }


def build_summary_lines(*, diff: dict[str, list[dict[str, Any]]], current_count: int, previous_count: int, highlight_shift: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    removed_indexes = [item["previous_index"] for item in diff["removed"]]
    added_indexes = [item["current_index"] for item in diff["added"]]

    if removed_indexes:
        if len(removed_indexes) == 1:
            lines.append(f"{removed_indexes[0]} 號離開名單")
        else:
            lines.append(f"{removed_indexes[0]} 等 {len(removed_indexes)} 筆序號離開名單")
    if added_indexes:
        if len(added_indexes) == 1:
            lines.append(f"新增候補出現在 {added_indexes[0]} 號")
        else:
            lines.append(f"新增 {len(added_indexes)} 筆候補，最前面出現在 {added_indexes[0]} 號")
    if highlight_shift:
        lines.append(
            f"{highlight_shift['previous_index']} → {highlight_shift['current_index']}（只顯示第一個代表性變動）"
        )
    if not lines and current_count == previous_count:
        lines.append("名單無變動")
    return lines


def infer_change_kind(*, diff: dict[str, list[dict[str, Any]]], previous_count: int, current_count: int) -> str:
    if current_count < previous_count:
        return "shrink"
    if current_count > previous_count:
        return "grow"
    if diff["moved"]:
        return "reorder"
    if diff["added"] or diff["removed"]:
        return "mixed"
    return "stable"


def build_change_record(*, fetched_at: str, diff: dict[str, list[dict[str, Any]]], previous_count: int | None, current_count: int) -> dict[str, Any]:
    baseline = previous_count is None
    normalized_previous_count = current_count if baseline else previous_count
    
    if baseline:
        likely_age_out: list[int] = []
        likely_withdrawn: list[int] = []
        likely_admitted: list[int] = []
        highlight_shift = None
        summary_lines = ["首次建立基線快照"]
        change_kind = "baseline"
        removed_details: list[dict[str, Any]] = []
        added_details: list[dict[str, Any]] = []
    else:
        likely_age_out, likely_withdrawn, likely_admitted = classify_removed_indexes(diff, fetched_at)
        highlight_shift = build_highlight_shift(diff)
        summary_lines = build_summary_lines(
            diff=diff,
            current_count=current_count,
            previous_count=normalized_previous_count,
            highlight_shift=highlight_shift,
        )
        change_kind = infer_change_kind(diff=diff, previous_count=normalized_previous_count, current_count=current_count)
        removed_details = diff["removed"]
        added_details = diff["added"]

    return {
        "fetched_at": fetched_at,
        "removed_previous_indexes": [] if baseline else [item["previous_index"] for item in diff["removed"]],
        "removed": [] if baseline else diff["removed"],
        "removed_details": removed_details,
        "added_current_indexes": [] if baseline else [item["current_index"] for item in diff["added"]],
        "added": [] if baseline else diff["added"],
        "added_details": added_details,
        "moved": [] if baseline else diff["moved"],
        "changed": False if baseline else bool(diff["removed"] or diff["added"] or diff["moved"]),
        "baseline": baseline,
        "previous_waiting_count": normalized_previous_count,
        "current_waiting_count": current_count,
        "net_waiting_count_change": current_count - normalized_previous_count,
        "likely_age_out_previous_indexes": likely_age_out,
        "likely_withdrawn_previous_indexes": likely_withdrawn,
        "likely_admitted_previous_indexes": likely_admitted,
        "highlight_shift": highlight_shift,
        "summary_lines": summary_lines,
        "change_kind": change_kind,
    }


def make_history_entry(snapshot: dict[str, Any], change_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(snapshot["fetched_at"])[:10],
        "fetched_at": snapshot["fetched_at"],
        "waiting_count": snapshot["waiting_count"],
        "last_month_enrolled": snapshot.get("last_month_enrolled"),
        "changed": bool(change_record.get("changed")),
        "change_kind": change_record.get("change_kind", "stable"),
        "summary_lines": list(change_record.get("summary_lines") or []),
        "highlight_shift": change_record.get("highlight_shift"),
        "removed_details": list(change_record.get("removed_details") or []),
        "added_details": list(change_record.get("added_details") or []),
        "likely_age_out_previous_indexes": list(change_record.get("likely_age_out_previous_indexes") or []),
    }