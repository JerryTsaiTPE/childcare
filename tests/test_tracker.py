import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ntpc_childcare_dashboard.tracker import (
    build_change_record,
    diff_snapshots,
    make_history_entry,
    parse_standby_payload,
)


class TrackerTests(unittest.TestCase):
    def test_diff_snapshots_detects_removed_added_and_moved_entries(self):
        previous = [
            {"index": 1, "encname": "王O安", "cbirthday": "2025-01-01", "displaydesc": "一般市民"},
            {"index": 2, "encname": "李O晴", "cbirthday": "2025-01-02", "displaydesc": "一般市民"},
            {"index": 3, "encname": "陳O宇", "cbirthday": "2025-01-03", "displaydesc": "優先收托"},
        ]
        current = [
            {"index": 1, "encname": "李O晴", "cbirthday": "2025-01-02", "displaydesc": "一般市民"},
            {"index": 2, "encname": "周O樂", "cbirthday": "2025-01-04", "displaydesc": "一般市民"},
            {"index": 3, "encname": "陳O宇", "cbirthday": "2025-01-03", "displaydesc": "優先收托"},
        ]

        diff = diff_snapshots(previous, current)

        self.assertEqual([item["previous_index"] for item in diff["removed"]], [1])
        self.assertEqual([item["current_index"] for item in diff["added"]], [2])
        self.assertEqual(diff["moved"][0]["name"], "李O晴")
        self.assertEqual(diff["moved"][0]["delta"], -1)

    def test_parse_standby_payload_extracts_summary_fields(self):
        payload = {
            "state": 1,
            "data": {
                "lastnum": 42,
                "preshow": True,
                "data": [
                    {"index": 1, "encname": "王O安", "cbirthday": "2025-01-01", "displaydesc": "一般市民"},
                    {"index": 2, "encname": "李O晴", "cbirthday": "2025-01-02", "displaydesc": "優先收托"},
                ],
            },
        }

        parsed = parse_standby_payload(payload)

        self.assertEqual(parsed["waiting_count"], 2)
        self.assertEqual(parsed["last_month_enrolled"], 42)
        self.assertTrue(parsed["preshow"])
        self.assertEqual(parsed["entries"][1]["displaydesc"], "優先收托")

    def test_build_change_record_summarizes_indexes(self):
        diff = {
            "removed": [{"previous_index": 1, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
            "added": [{"current_index": 99, "name": "周O樂", "birthday": "2025-01-04", "category": "一般市民"}],
            "moved": [{"name": "李O晴", "previous_index": 2, "current_index": 1, "delta": -1, "birthday": "2025-01-02", "category": "一般市民"}],
        }

        record = build_change_record(
            fetched_at="2026-04-21T13:30:00+08:00",
            diff=diff,
            previous_count=100,
            current_count=99,
        )

        self.assertTrue(record["changed"])
        self.assertEqual(record["removed_previous_indexes"], [1])
        self.assertEqual(record["added_current_indexes"], [99])
        self.assertEqual(record["net_waiting_count_change"], -1)
        self.assertEqual(record["likely_admitted_previous_indexes"], [1])
        self.assertEqual(record["likely_withdrawn_previous_indexes"], [])

    def test_build_change_record_identifies_likely_withdrawal_when_no_backfill_and_no_movement(self):
        diff = {
            "removed": [{"previous_index": 15, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
            "added": [],
            "moved": [],
        }

        record = build_change_record(
            fetched_at="2026-04-21T13:30:00+08:00",
            diff=diff,
            previous_count=200,
            current_count=199,
        )

        self.assertEqual(record["likely_withdrawn_previous_indexes"], [15])
        self.assertEqual(record["likely_admitted_previous_indexes"], [])

    def test_build_change_record_creates_highlight_shift_and_summary_lines(self):
        diff = {
            "removed": [{"previous_index": 100, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
            "added": [],
            "moved": [
                {"name": "李O晴", "previous_index": 101, "current_index": 100, "delta": -1, "birthday": "2025-01-02", "category": "一般市民"},
                {"name": "周O樂", "previous_index": 102, "current_index": 101, "delta": -1, "birthday": "2025-01-03", "category": "一般市民"},
            ],
        }

        record = build_change_record(
            fetched_at="2026-04-21T14:05:00+08:00",
            diff=diff,
            previous_count=266,
            current_count=265,
        )

        self.assertEqual(record["highlight_shift"], {"previous_index": 101, "current_index": 100, "name": "李O晴", "delta": -1})
        self.assertIn("100 號離開名單", record["summary_lines"][0])
        self.assertIn("101 → 100", record["summary_lines"][1])
        self.assertEqual(record["change_kind"], "shrink")
        self.assertEqual(record["removed_details"][0]["name"], "王O安")
        self.assertEqual(record["removed_details"][0]["birthday"], "2025-01-01")
        self.assertEqual(record["removed_details"][0]["category"], "一般市民")

    def test_build_change_record_treats_first_snapshot_as_baseline(self):
        diff = {
            "removed": [],
            "added": [{"current_index": 1, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
            "moved": [],
        }

        record = build_change_record(
            fetched_at="2026-04-21T13:30:00+08:00",
            diff=diff,
            previous_count=None,
            current_count=1,
        )

        self.assertFalse(record["changed"])
        self.assertEqual(record["added_current_indexes"], [])
        self.assertEqual(record["net_waiting_count_change"], 0)
        self.assertTrue(record["baseline"])

    def test_make_history_entry_marks_changed_status(self):
        snapshot = {
            "fetched_at": "2026-04-21T13:30:00+08:00",
            "waiting_count": 266,
            "last_month_enrolled": 42,
        }
        change = {
            "changed": True,
            "change_kind": "shrink",
            "summary_lines": ["100 號離開名單", "101 → 100"],
            "highlight_shift": {"previous_index": 101, "current_index": 100, "name": "李O晴", "delta": -1},
            "removed_details": [{"previous_index": 100, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
        }

        entry = make_history_entry(snapshot, change)

        self.assertEqual(entry["date"], "2026-04-21")
        self.assertEqual(entry["waiting_count"], 266)
        self.assertTrue(entry["changed"])
        self.assertEqual(entry["last_month_enrolled"], 42)
        self.assertEqual(entry["change_kind"], "shrink")
        self.assertEqual(entry["summary_lines"][1], "101 → 100")
        self.assertEqual(entry["removed_details"][0]["name"], "王O安")


if __name__ == '__main__':
    unittest.main()
