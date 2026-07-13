#!/usr/bin/env python3
"""Safely remove a selected timestamp interval from dashboard history files."""
from __future__ import annotations

import json
import queue
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_user_time(value: str) -> datetime:
    value = value.strip().replace("T", " ")
    for fmt in (TIME_FORMAT, "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError("時間格式必須是 YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS")


def parse_record_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def in_range(timestamp: str | None, start: datetime, end: datetime) -> bool:
    point = parse_record_time(timestamp)
    return point is not None and start <= point <= end


def snapshot_files_in_range(snapshot_dir: Path, start: datetime, end: datetime) -> list[Path]:
    matched: list[Path] = []
    for path in snapshot_dir.glob("*.json") if snapshot_dir.exists() else []:
        try:
            item = load_json(path, {})
        except (OSError, json.JSONDecodeError):
            continue
        if in_range(item.get("fetched_at"), start, end):
            matched.append(path)
    return matched


def selected_org_ids(data_dir: Path) -> list[str]:
    if not data_dir.exists():
        return []
    return sorted(path.name for path in data_dir.iterdir() if path.is_dir() and path.name != "history_cleanup_backups")


def preview_cleanup(
    data_dir: Path,
    org_ids: list[str],
    start_value: str,
    end_value: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, dict[str, Any]]:
    start = parse_user_time(start_value)
    end = parse_user_time(end_value)
    if start > end:
        raise ValueError("開始時間不可晚於結束時間")

    preview: dict[str, dict[str, Any]] = {}
    total = len(org_ids)
    for completed, org_id in enumerate(org_ids):
        if progress_callback:
            progress_callback(completed, total, org_id)
        org_dir = data_dir / org_id
        history = load_json(org_dir / "history.json", [])
        changes = load_json(org_dir / "changes.json", [])
        latest = load_json(org_dir / "latest_snapshot.json", {})
        snapshots = snapshot_files_in_range(org_dir / "snapshots", start, end)
        preview[org_id] = {
            "history": sum(in_range(item.get("fetched_at"), start, end) for item in history if isinstance(item, dict)),
            "changes": sum(in_range(item.get("fetched_at"), start, end) for item in changes if isinstance(item, dict)),
            "snapshots": len(snapshots),
            "latest_in_range": in_range(latest.get("fetched_at") if isinstance(latest, dict) else None, start, end),
        }
        if progress_callback:
            progress_callback(completed + 1, total, org_id)
    return preview


def backup_org_files(org_dir: Path, backup_org_dir: Path) -> None:
    backup_org_dir.mkdir(parents=True, exist_ok=True)
    for name in ("history.json", "changes.json", "latest_snapshot.json"):
        path = org_dir / name
        if path.exists():
            shutil.copy2(path, backup_org_dir / name)
    snapshots = org_dir / "snapshots"
    if snapshots.exists():
        shutil.copytree(snapshots, backup_org_dir / "snapshots", dirs_exist_ok=True)


def latest_remaining_snapshot(snapshot_dir: Path) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for path in snapshot_dir.glob("*.json") if snapshot_dir.exists() else []:
        try:
            item = load_json(path, {})
        except (OSError, json.JSONDecodeError):
            continue
        stamp = parse_record_time(item.get("fetched_at")) if isinstance(item, dict) else None
        if stamp:
            candidates.append((stamp, item))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def cleanup_history(data_dir: Path, org_ids: list[str], start_value: str, end_value: str) -> dict[str, Any]:
    start = parse_user_time(start_value)
    end = parse_user_time(end_value)
    if start > end:
        raise ValueError("開始時間不可晚於結束時間")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir / "history_cleanup_backups" / stamp
    preview = preview_cleanup(data_dir, org_ids, start_value, end_value)
    results: dict[str, Any] = {"backup_dir": backup_dir, "orgs": {}}

    for org_id in org_ids:
        org_dir = data_dir / org_id
        if not org_dir.is_dir():
            continue
        backup_org_files(org_dir, backup_dir / org_id)
        history_path, changes_path = org_dir / "history.json", org_dir / "changes.json"
        history = load_json(history_path, [])
        changes = load_json(changes_path, [])
        write_json(history_path, [item for item in history if not (isinstance(item, dict) and in_range(item.get("fetched_at"), start, end))])
        write_json(changes_path, [item for item in changes if not (isinstance(item, dict) and in_range(item.get("fetched_at"), start, end))])

        for path in snapshot_files_in_range(org_dir / "snapshots", start, end):
            path.unlink()

        latest_path = org_dir / "latest_snapshot.json"
        if preview[org_id]["latest_in_range"]:
            replacement = latest_remaining_snapshot(org_dir / "snapshots")
            if replacement is None:
                raise RuntimeError(f"{org_id} 沒有可作為 latest_snapshot 的保留快照，已保留備份，請由備份手動復原。")
            write_json(latest_path, replacement)
        results["orgs"][org_id] = preview[org_id]
    return results


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("NTPC Childcare 歷史紀錄清理工具")
    root.geometry("840x610")
    root.minsize(760, 530)

    data_dir_var = tk.StringVar(value=str(DEFAULT_DATA_DIR))
    start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d 00:00:00"))
    end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    status_var = tk.StringVar(value="先選擇中心與時間區間，再按「預覽清理範圍」。")
    progress_var = tk.DoubleVar(value=0)
    progress_text_var = tk.StringVar(value="尚未開始預覽")
    preview_running = False

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="歷史紀錄清理工具", font=("Microsoft JhengHei UI", 16, "bold")).pack(anchor="w")
    ttk.Label(frame, text="會先完整備份，再同步移除 history / changes / snapshots；若刪到最新快照，會自動回復為最後保留快照。", wraplength=780).pack(anchor="w", pady=(4, 14))

    inputs = ttk.Frame(frame)
    inputs.pack(fill="x")
    for row, label, variable in ((0, "資料目錄", data_dir_var), (1, "開始時間", start_var), (2, "結束時間", end_var)):
        ttk.Label(inputs, text=label, width=12).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(inputs, textvariable=variable, width=55).grid(row=row, column=1, sticky="ew", pady=4)
    inputs.columnconfigure(1, weight=1)

    ttk.Label(frame, text="選擇要清理的中心（未勾選任何中心時，會清理全部中心）：").pack(anchor="w", pady=(14, 4))
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill="both", expand=False)
    org_list = tk.Listbox(list_frame, selectmode="multiple", height=9, exportselection=False)
    org_list.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=org_list.yview)
    scrollbar.pack(side="right", fill="y")
    org_list.configure(yscrollcommand=scrollbar.set)

    preview_box = tk.Text(frame, height=11, wrap="word", state="disabled", font=("Consolas", 10))
    preview_box.pack(fill="both", expand=True, pady=(12, 8))

    progress_frame = ttk.Frame(frame)
    progress_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(progress_frame, textvariable=progress_text_var).pack(anchor="w")
    progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100, mode="determinate")
    progress_bar.pack(fill="x", pady=(3, 0))

    def orgs() -> list[str]:
        all_ids = list(org_list.get(0, "end"))
        chosen = [all_ids[i] for i in org_list.curselection()]
        return chosen or all_ids

    def render_preview(preview: dict[str, dict[str, Any]], heading: str) -> None:
        lines = [heading, ""]
        for org_id, data in preview.items():
            latest_note = "；最新快照會回復" if data["latest_in_range"] else ""
            lines.append(f"{org_id}: history {data['history']} 筆、changes {data['changes']} 筆、snapshots {data['snapshots']} 檔{latest_note}")
        text = "\n".join(lines)
        preview_box.config(state="normal")
        preview_box.delete("1.0", "end")
        preview_box.insert("1.0", text)
        preview_box.config(state="disabled")

    def refresh_orgs() -> None:
        path = Path(data_dir_var.get()).expanduser()
        org_list.delete(0, "end")
        for org_id in selected_org_ids(path):
            org_list.insert("end", org_id)
        status_var.set(f"已載入 {org_list.size()} 個中心。")

    def preview() -> None:
        nonlocal preview_running
        if preview_running:
            return
        try:
            data_dir = Path(data_dir_var.get()).expanduser()
            chosen_orgs = orgs()
            start_value, end_value = start_var.get(), end_var.get()
            parse_user_time(start_value)
            parse_user_time(end_value)
            if parse_user_time(start_value) > parse_user_time(end_value):
                raise ValueError("開始時間不可晚於結束時間")
        except Exception as exc:
            messagebox.showerror("無法預覽", str(exc), parent=root)
            return

        preview_running = True
        progress_var.set(0)
        progress_text_var.set(f"正在預覽：0 / {len(chosen_orgs)} 個中心")
        status_var.set("正在掃描歷史資料，視資料量可能需要一些時間；視窗仍可移動。")
        preview_button.state(["disabled"])
        cleanup_button.state(["disabled"])
        event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        def report_progress(completed: int, total: int, org_id: str) -> None:
            event_queue.put(("progress", (completed, total, org_id)))

        def worker() -> None:
            try:
                report = preview_cleanup(data_dir, chosen_orgs, start_value, end_value, report_progress)
                event_queue.put(("done", report))
            except Exception as exc:
                event_queue.put(("error", exc))

        def poll_worker() -> None:
            nonlocal preview_running
            try:
                while True:
                    kind, payload = event_queue.get_nowait()
                    if kind == "progress":
                        completed, total, org_id = payload
                        percent = (completed / total * 100) if total else 100
                        progress_var.set(percent)
                        progress_text_var.set(f"正在預覽：{completed} / {total} 個中心（目前：{org_id}）")
                    elif kind == "done":
                        render_preview(payload, "預覽：下列項目將被移除（尚未寫入檔案）")
                        progress_var.set(100)
                        progress_text_var.set(f"預覽完成：已掃描 {len(chosen_orgs)} 個中心")
                        status_var.set("預覽完成；確認數量後才可執行清理。")
                        preview_running = False
                        preview_button.state(["!disabled"])
                        cleanup_button.state(["!disabled"])
                        return
                    elif kind == "error":
                        preview_running = False
                        preview_button.state(["!disabled"])
                        cleanup_button.state(["!disabled"])
                        progress_text_var.set("預覽失敗")
                        messagebox.showerror("無法預覽", str(payload), parent=root)
                        return
            except queue.Empty:
                pass
            root.after(75, poll_worker)

        threading.Thread(target=worker, daemon=True).start()
        root.after(75, poll_worker)

    def cleanup() -> None:
        try:
            data_dir = Path(data_dir_var.get()).expanduser()
            report = preview_cleanup(data_dir, orgs(), start_var.get(), end_var.get())
            total = sum(item["history"] + item["changes"] + item["snapshots"] for item in report.values())
            if not total:
                messagebox.showinfo("沒有資料", "指定區間沒有可清理的歷史資料。", parent=root)
                return
            if not messagebox.askyesno("最後確認", f"將清理 {len(report)} 個中心，共 {total} 個歷史項目。\n執行前會自動建立完整備份。\n\n確定要繼續嗎？", icon="warning", parent=root):
                return
            result = cleanup_history(data_dir, orgs(), start_var.get(), end_var.get())
            render_preview(result["orgs"], f"清理完成。備份位置：\n{result['backup_dir']}")
            status_var.set("清理完成。請重新執行 update_dashboard.py 產生新的 index.html。")
        except Exception as exc:
            messagebox.showerror("清理失敗", str(exc), parent=root)

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=(4, 6))
    ttk.Button(buttons, text="重新載入中心", command=refresh_orgs).pack(side="left")
    preview_button = ttk.Button(buttons, text="預覽清理範圍", command=preview)
    preview_button.pack(side="left", padx=8)
    cleanup_button = ttk.Button(buttons, text="建立備份並執行清理", command=cleanup)
    cleanup_button.pack(side="right")
    ttk.Label(frame, textvariable=status_var, foreground="#176b3a", wraplength=780).pack(anchor="w")

    refresh_orgs()
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
