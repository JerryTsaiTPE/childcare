# Project Index: ntpc-childcare-dashboard

## Directory Structure

- ntpc-childcare-dashboard/
  - README.md
  - mobile-preview.html
  - index.html
  - data/
    - changes.json
    - latest_snapshot.json
    - history.json
    - snapshots/
      - 2026-04-21T15-05-19+08_00.json
      - 2026-04-21T14-09-33+08_00.json
      - 2026-04-21T15-08-32+08_00.json
      - 2026-04-21T15-25-14+08_00.json
      - 2026-04-21T13-14-48+08_00.json
      - 2026-04-21T15-41-48+08_00.json
      - 2026-04-21T14-33-15+08_00.json
      - 2026-04-21T15-07-12+08_00.json
      - 2026-04-21T15-21-35+08_00.json
      - 2026-04-21T15-02-20+08_00.json
      - 2026-04-21T14-22-52+08_00.json
      - 2026-04-21T14-52-04+08_00.json
      - 2026-04-21T15-16-29+08_00.json
  - scripts/
    - update_dashboard.py
  - docs/
    - plans/
      - 2026-04-21-history-tab-plan.md
      - 2026-04-21-banqiao-bocui-dashboard-plan.md
  - src/
    - ntpc_childcare_dashboard/
      - __init__.py
      - render.py
      - tracker.py
  - tests/
    - test_render.py
    - test_tracker.py

## File Content Summary

### File: README.md

  **Summary:** # 板橋柏翠托育備取名單 Dashboard

### File: mobile-preview.html

  (Content indexed)

### File: index.html

  (Content indexed)

### File: scripts/update_dashboard.py

  **Definitions:** def fetch_json, def load_json, def save_json, def load_org_info, def trim_history, def main

### File: docs/plans/2026-04-21-history-tab-plan.md

  **Summary:** # 板橋柏翠歷史紀錄分頁 Implementation Plan

### File: docs/plans/2026-04-21-banqiao-bocui-dashboard-plan.md

  **Summary:** # 板橋柏翠托育備取名單 Dashboard Implementation Plan

### File: src/ntpc_childcare_dashboard/__init__.py

  (No explicit definitions found)

### File: src/ntpc_childcare_dashboard/render.py

  **Definitions:** def _json_script, def render_dashboard

### File: src/ntpc_childcare_dashboard/tracker.py

  **Definitions:** def entry_key, def parse_standby_payload, def diff_snapshots, def classify_removed_indexes, def build_highlight_shift, def build_summary_lines, def infer_change_kind, def build_change_record, def make_history_entry

### File: tests/test_render.py

  **Definitions:** class RenderTests, def test_render_dashboard_includes_history_toggle_and_details, def test_update_script_outputs_to_index_html

### File: tests/test_tracker.py

  **Definitions:** class TrackerTests, def test_diff_snapshots_detects_removed_added_and_moved_entries, def test_parse_standby_payload_extracts_summary_fields, def test_build_change_record_summarizes_indexes, def test_build_change_record_identifies_likely_withdrawal_when_no_backfill_and_no_movement, def test_build_change_record_creates_highlight_shift_and_summary_lines, def test_build_change_record_treats_first_snapshot_as_baseline, def test_make_history_entry_marks_changed_status
