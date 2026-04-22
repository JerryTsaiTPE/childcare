import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
SCRIPT_PATH = ROOT / 'scripts' / 'update_dashboard.py'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ntpc_childcare_dashboard.render import render_dashboard


class RenderTests(unittest.TestCase):
    def test_render_dashboard_includes_history_toggle_and_details(self):
        snapshot = {
            "org": {"orgid": "Z0130", "orgshort": "板橋柏翠", "orgname": "板橋柏翠公共托育中心", "distdesc": "板橋區", "capnum": 40, "enroll_count": 42},
            "waiting_count": 266,
            "last_month_enrolled": 42,
            "preshow": True,
            "fetched_at": "2026-04-21T13:30:00+08:00",
            "entries": [
                {"index": 1, "encname": "王O安", "cbirthday": "2025-01-01", "displaydesc": "一般市民"},
                {"index": 2, "encname": "李O晴", "cbirthday": "2025-01-02", "displaydesc": "優先收托"},
            ],
        }
        latest_change = {
            "fetched_at": "2026-04-21T13:30:00+08:00",
            "removed_previous_indexes": [100],
            "added_current_indexes": [],
            "moved": [{"name": "李O晴", "previous_index": 101, "current_index": 100, "delta": -1}],
            "changed": True,
            "likely_withdrawn_previous_indexes": [],
            "likely_admitted_previous_indexes": [100],
            "highlight_shift": {"previous_index": 101, "current_index": 100, "name": "李O晴", "delta": -1},
            "summary_lines": ["100 號離開名單", "101 → 100（只顯示第一個代表性變動）"],
            "change_kind": "shrink",
            "removed_details": [{"previous_index": 100, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
        }
        history = [
            {
                "date": "2026-04-21",
                "fetched_at": "2026-04-21T13:30:00+08:00",
                "waiting_count": 266,
                "last_month_enrolled": 42,
                "changed": True,
                "change_kind": "shrink",
                "summary_lines": ["100 號離開名單", "101 → 100（只顯示第一個代表性變動）"],
                "highlight_shift": {"previous_index": 101, "current_index": 100, "name": "李O晴", "delta": -1},
                "removed_details": [{"previous_index": 100, "name": "王O安", "birthday": "2025-01-01", "category": "一般市民"}],
            },
            {
                "date": "2026-04-21",
                "fetched_at": "2026-04-21T12:30:00+08:00",
                "waiting_count": 266,
                "last_month_enrolled": 42,
                "changed": False,
                "change_kind": "stable",
                "summary_lines": ["名單無變動"],
                "highlight_shift": None,
                "removed_details": [],
            }
        ]
        rule_text = "缺額遞補原則：若為一般收托名額出缺時，依出缺年齡於全數備取名單中適齡遞補。"
        validity_text = "有效期限至116/07/31"
        related_info_text = """相關說明：
一、備取序號：係指現行實際之備取順序（未分齡）
二、本表係依幼兒備取編號順序排列
五、114年7月報名期間結束後，自114年8月1日起開放候補登記。"""

        html = render_dashboard(
            snapshot=snapshot,
            latest_change=latest_change,
            history=history,
            rule_text=rule_text,
            validity_text=validity_text,
            related_info_text=related_info_text,
        )

        self.assertIn("歷史紀錄", html)
        self.assertIn("總覽", html)
        self.assertIn("顯示無變動紀錄", html)
        self.assertIn("原序號", html)
        self.assertIn("兒童姓名", html)
        self.assertIn("出生日期", html)
        self.assertIn("身分別", html)
        self.assertIn("王O安", html)
        self.assertIn("2025-01-01", html)
        self.assertIn("一般市民", html)
        self.assertIn("stable-hidden", html)
        self.assertIn("所有名單", html)
        self.assertIn("tab-all-list", html)
        self.assertIn("all-list-table", html)
        self.assertIn("all-list-sort-key", html)
        self.assertIn("all-list-sort-direction", html)
        self.assertIn("renderAllListTable", html)
        self.assertIn("sortEntries", html)
        self.assertNotIn("展開目前所有名單", html)
        self.assertNotIn("all-list-toggle", html)
        self.assertNotIn("all-list-panel", html)
        self.assertNotIn("snapshot.entries.slice(20).forEach", html)
        self.assertIn("前 20 名備取身分", html)
        self.assertNotIn("目前前 20 名備取身分", html)
        self.assertNotIn("目前前 20 名身分分布", html)
        self.assertIn("前 20 名備取名單", html)
        self.assertNotIn("目前前 20 名名單", html)
        self.assertIn("名單有效期限", html)
        self.assertNotIn("<h2>有效期限</h2>", html)
        self.assertIn("有效期限至116/07/31", html)
        self.assertIn("相關說明", html)
        self.assertNotIn("<h2>缺額遞補原則</h2>", html)
        self.assertNotIn("id=\"rule-text\"", html)
        self.assertIn("一、備取序號：係指現行實際之備取順序（未分齡）", html)
        self.assertIn("二、本表係依幼兒備取編號順序排列", html)
        self.assertIn("114年7月報名期間結束後，自114年8月1日起開放候補登記", html)
        self.assertIn("related-info-text", html)
        self.assertIn("validity-text", html)
        self.assertIn("rule-highlight", html)
        self.assertIn("renderRelatedInfo", html)
        self.assertIn("related-section", html)
        self.assertIn("related-block-title", html)
        self.assertIn("related-list", html)
        self.assertIn("related-note", html)
        self.assertIn("sectionHeadingRegex", html)
        self.assertIn("bulletOnlyRegex", html)
        self.assertIn("flushSection", html)
        self.assertIn("table-wrap", html)
        self.assertIn("panel-table", html)
        self.assertIn("all-list-table-wrap", html)
        self.assertIn("history-table-wrap", html)
        self.assertIn("@media (max-width: 720px)", html)
        self.assertIn(".tabs { overflow-x: auto;", html)
        self.assertIn(".control-group { flex-wrap: wrap;", html)
        self.assertIn(".wrap { padding: 14px;", html)
        self.assertIn("Math.round((count / topCategoryTotal) * 1000) / 10", html)
        self.assertNotIn("本次新增候補", html)
        self.assertNotIn("added-count", html)
        self.assertNotIn("added-summary", html)
        self.assertNotIn("added-chips", html)

    def test_update_script_outputs_to_index_html(self):
        source = SCRIPT_PATH.read_text(encoding='utf-8')
        self.assertIn("ROOT = Path(__file__).resolve().parents[1]", source)
        self.assertIn("INDEX_PATH = ROOT / 'index.html'", source)
        self.assertNotIn("DASHBOARD_PATH = ROOT / 'dashboard.html'", source)


if __name__ == '__main__':
    unittest.main()
