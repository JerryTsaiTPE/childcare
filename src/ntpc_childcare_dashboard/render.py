from __future__ import annotations

import html
import json
from typing import Any


def _json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_dashboard(
    *,
    snapshot: dict[str, Any],
    latest_change: dict[str, Any],
    history: list[dict[str, Any]],
    rule_text: str,
    validity_text: str,
    related_info_text: str,
) -> str:
    title = f"{snapshot['org']['orgshort']}托育備取追蹤 Dashboard"
    payload = {
        "snapshot": snapshot,
        "latest_change": latest_change,
        "history": history,
        "rule_text": rule_text,
        "validity_text": validity_text,
        "related_info_text": related_info_text,
    }
    safe_title = html.escape(title)
    safe_orgid = html.escape(snapshot["org"]["orgid"])
    safe_orgname = html.escape(snapshot["org"]["orgname"])
    data_json = _json_script(payload)

    # 完整原生字串 (防跳脫崩潰)
    html_template = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__SAFE_TITLE__</title>
  <style>
    :root {
      --bg: #07111f;
      --panel: #0d1b2a;
      --card: #13253a;
      --border: #284864;
      --accent: #52d1ff;
      --accent-2: #8ef7c2;
      --text: #edf6ff;
      --muted: #9bb2c8;
      --danger: #ff7b7b;
      --warn: #ffd166;
      --ok: #8ef7c2;
      --tab-bg: #0a1624;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, 'Noto Sans TC', sans-serif; background: linear-gradient(180deg, #06101b, #0b1626 30%, #09131f); color: var(--text); }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .hero { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 20px; }
    .hero h1 { margin: 0 0 8px; font-size: 34px; }
    .sub { color: var(--muted); line-height: 1.6; }
    .tabs { display: flex; gap: 10px; margin-bottom: 18px; overflow-x: auto; padding-bottom: 4px; }
    .tab-btn { border: 1px solid var(--border); background: var(--tab-bg); color: var(--muted); border-radius: 999px; padding: 10px 16px; cursor: pointer; white-space: nowrap; flex: 0 0 auto; transition: 0.2s; }
    .tab-btn.active { color: var(--text); background: #13314d; border-color: var(--accent); }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; animation: fadeIn 0.3s ease; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    .history-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
    .toggle { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 18px; }
    .card, .panel { background: rgba(16, 30, 48, 0.88); border: 1px solid var(--border); border-radius: 18px; box-shadow: 0 14px 30px rgba(0,0,0,0.22); }
    .card { padding: 18px; }
    .metric { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
    .value { font-size: 34px; font-weight: 700; }
    .value.small { font-size: 24px; }
    .delta-up { color: var(--ok); }
    .delta-down { color: var(--danger); }
    .delta-flat { color: var(--muted); }
    .panels { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 16px; margin-bottom: 18px; }
    .panel { padding: 20px; }
    .panel h2 { margin: 0 0 14px; font-size: 20px; }
    .chart-box { min-height: 320px; width: 100%; position: relative; }
    .bar-row { display: grid; grid-template-columns: 80px 1fr 110px; align-items: center; gap: 10px; margin-bottom: 10px; }
    .bar-track { height: 12px; border-radius: 999px; background: #08121f; overflow: hidden; border: 1px solid #17324c; }
    .bar-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }
    .pill { display: inline-flex; padding: 5px 10px; border-radius: 999px; border: 1px solid var(--border); background: #0a1624; color: var(--muted); font-size: 12px; }
    .list { display: grid; gap: 12px; }
    .list-block { padding: 14px; border-radius: 14px; background: #0a1624; border: 1px solid #16304a; }
    .list-block h3 { margin: 0 0 8px; font-size: 16px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { padding: 7px 10px; border-radius: 999px; background: #13273d; border: 1px solid #214361; font-size: 13px; }
    .timeline { display: grid; gap: 14px; }
    .timeline-item { padding: 18px; border-radius: 16px; background: rgba(16, 30, 48, 0.88); border: 1px solid var(--border); }
    .timeline-item.stable-hidden { display: none; }
    .timeline-meta { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; color: var(--muted); }
    .timeline-lines { margin: 0; padding-left: 20px; line-height: 1.8; }
    .timeline-highlight { margin-top: 10px; color: var(--accent-2); }
    .history-details { margin-top: 14px; overflow-x: auto; }
    .section-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
    .control-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
    .control-group { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); }
    .select-input { background: #0a1624; color: var(--text); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; cursor: pointer; }
    .table-wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .panel-table { min-width: 520px; }
    .all-list-table-wrap { margin-top: 10px; }
    .history-table-wrap { margin-top: 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid rgba(107, 139, 168, 0.18); }
    th { color: var(--muted); font-weight: 600; }
    tr:hover td { background: rgba(255,255,255,0.02); }
    
    /* 屆齡幼兒紅字標示 */
    .aging-out td { color: var(--danger); font-weight: 500; }
    
    .rule { white-space: pre-wrap; line-height: 1.7; color: #d9ebff; background: #091522; padding: 18px; border-radius: 14px; border: 1px solid #18324d; }
    .related-section { padding: 12px 0; border-bottom: 1px solid rgba(107, 139, 168, 0.18); }
    .related-section:last-child { border-bottom: none; }
    .related-block-title { font-weight: 700; color: var(--text); margin-bottom: 8px; }
    .related-list { margin: 0; padding-left: 20px; line-height: 1.8; }
    .related-note { line-height: 1.8; color: #d9ebff; }
    .rule-highlight { margin: 14px 0; padding: 14px 16px; border-radius: 12px; background: linear-gradient(90deg, rgba(82, 209, 255, 0.12), rgba(142, 247, 194, 0.10)); border: 1px solid rgba(82, 209, 255, 0.38); box-shadow: inset 0 0 0 1px rgba(142, 247, 194, 0.08); }
    .rule-highlight strong { display: block; margin-bottom: 8px; color: var(--accent-2); font-size: 16px; }
    .info-stack { display: grid; gap: 16px; }
    .footer { color: var(--muted); font-size: 13px; margin-top: 16px; text-align: center; }
    @media (max-width: 980px) { .panels { grid-template-columns: 1fr; } }
    @media (max-width: 720px) {
      .wrap { padding: 14px; }
      .hero { gap: 12px; margin-bottom: 16px; }
      .hero h1 { font-size: 28px; }
      .pill { width: 100%; border-radius: 14px; }
      .tabs { overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin; }
      .grid { grid-template-columns: 1fr; }
      .card { padding: 16px; }
      .panel { padding: 16px; }
      .value { font-size: 30px; }
      .value.small { font-size: 22px; }
      .bar-row { grid-template-columns: 1fr; gap: 6px; }
      .control-group { flex-wrap: wrap; width: 100%; }
      .select-input { width: 100%; }
      .panel-table { min-width: 480px; }
      th, td { padding: 9px 6px; font-size: 13px; }
      .rule { padding: 14px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div>
        <h1>__SAFE_TITLE__</h1>
        <div class="sub">追蹤來源：新北育兒資訊網公開備取 API（orgid=__SAFE_ORGID__）<br>系統最後更新：<span id="updated-at"></span></div>
      </div>
      <div class="pill">板橋區／__SAFE_ORGNAME__</div>
    </section>

    <section class="tabs">
      <button class="tab-btn active" data-tab="overview">總覽</button>
      <button class="tab-btn" data-tab="all-list">所有名單</button>
      <button class="tab-btn" data-tab="hourly-detail">歷史走勢</button>
      <button class="tab-btn" data-tab="history">歷史變動紀錄</button>
    </section>

    <section id="tab-overview" class="tab-panel active">
      <section class="grid">
        <div class="card"><div class="metric">目前備取總數</div><div class="value" id="waiting-count"></div></div>
        <div class="card"><div class="metric">上月入托人數</div><div class="value" id="lastnum"></div></div>
        <div class="card"><div class="metric">中心核定名額 / 已入托</div><div class="value small" id="capacity"></div></div>
        
        <div class="card"><div class="metric">最近離開名單序號</div><div class="value small" id="removed-count"></div><div class="sub" id="removed-summary"></div></div>
        <div class="card"><div class="metric">推測遞補/入托</div><div class="value small" id="admitted-count"></div><div class="sub" id="admitted-summary"></div></div>
        <div class="card"><div class="metric">推測屆齡取消</div><div class="value small" id="age-out-count"></div><div class="sub" id="age-out-summary"></div></div>
        <div class="card"><div class="metric">推測家長取消候補</div><div class="value small" id="withdrawn-count"></div><div class="sub" id="withdrawn-summary"></div></div>
      </section>

      <section class="panels">
        <div class="panel chart-box">
          <h2>📈 每日備取總數走勢 <span class="sub" style="font-size:13px; font-weight:normal;">(顯示每日最終狀態)</span></h2>
          <svg id="history-chart" width="100%" height="300" viewBox="0 0 760 300" preserveAspectRatio="none"></svg>
        </div>
        <div class="panel">
          <h2>前 20 名備取身分</h2>
          <div id="top20-bars"></div>
        </div>
      </section>

      <section class="panels">
        <div class="panel">
          <h2>最新變動摘要 <span id="latest-change-time" style="font-size: 14px; font-weight: normal; color: var(--warn); margin-left: 8px;"></span></h2>
          <div class="list">
            <div class="list-block">
              <h3>離開名單序號</h3>
              <div class="chips" id="removed-chips"></div>
            </div>
            <div class="list-block">
              <h3>推測為遞補/入托 (15號內)</h3>
              <div class="chips" id="admitted-chips"></div>
            </div>
            <div class="list-block">
              <h3>推測為屆齡取消 (滿兩歲或14天內)</h3>
              <div class="chips" id="age-out-chips"></div>
            </div>
            <div class="list-block">
              <h3>推測為自行取消 (15號外)</h3>
              <div class="chips" id="withdrawn-chips"></div>
            </div>
            <div class="list-block">
              <h3>名次推進明細</h3>
              <div class="table-wrap">
                <table class="panel-table">
                  <thead><tr><th>姓名</th><th>原序號</th><th>新序號</th><th>變化</th></tr></thead>
                  <tbody id="moved-table"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        <div class="panel">
          <h2>前 20 名備取名單 <span class="sub" style="font-size:13px; font-weight:normal; margin-left:8px;">(紅色為已屆齡尚未被系統移除者)</span></h2>
          <div class="table-wrap">
            <table class="panel-table">
              <thead><tr><th>序號</th><th>姓名</th><th>出生日期</th><th>目前歲數</th><th>身分別</th></tr></thead>
              <tbody id="top20-table"></tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="panel info-stack">
        <div>
          <h2>名單有效期限</h2>
          <div class="rule" id="validity-text"></div>
        </div>
        <div>
          <h2>相關說明</h2>
          <div class="rule" id="related-info-text"></div>
        </div>
      </section>
    </section>

    <section id="tab-hourly-detail" class="tab-panel">
      <div class="panel chart-box">
        <h2>🕒 每小時詳細變動</h2>
        <div class="control-row" style="margin-bottom: 15px;">
          <label>選擇日期查看當日趨勢：</label>
          <select id="date-selector" class="select-input"></select>
        </div>
        <svg id="hourly-chart" width="100%" height="300" viewBox="0 0 760 300" preserveAspectRatio="none"></svg>
      </div>
    </section>

    <section id="tab-all-list" class="tab-panel">
      <div class="panel">
        <h2>所有名單 <span class="sub" style="font-size:14px; font-weight:normal; margin-left:10px; color:var(--danger);">※ 紅色字體代表該幼兒已滿兩歲或距滿兩歲不到 14 天，即將被系統自動取消候補。</span></h2>
        <div class="control-row" style="margin-bottom:15px;">
          <div class="control-group">
            <label>排序欄位</label>
            <select id="all-list-sort-key" class="select-input">
              <option value="index">序號</option>
              <option value="encname">姓名</option>
              <option value="cbirthday">出生日期</option>
              <option value="age">目前歲數</option>
              <option value="displaydesc">身分別</option>
            </select>
            <label>排序方向</label>
            <select id="all-list-sort-direction" class="select-input">
              <option value="asc">由小到大</option>
              <option value="desc">由大到小</option>
            </select>
          </div>
        </div>
        <div class="all-list-table-wrap table-wrap">
          <table class="panel-table">
            <thead><tr><th>序號</th><th>姓名</th><th>出生日期</th><th>目前歲數</th><th>身分別</th></tr></thead>
            <tbody id="all-list-table"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="tab-history" class="tab-panel">
      <div class="panel">
        <h2>歷史紀錄</h2>
        <div class="history-toolbar">
          <div class="sub">只保留每次更新的重點變動；若整串名次都往前，僅顯示第一個代表性變動。</div>
          <label class="toggle"><input id="toggle-stable" type="checkbox" /> 顯示無變動紀錄</label>
        </div>
        <div id="history-timeline" class="timeline"></div>
      </div>
    </section>

    <div class="footer">NTPC Childcare Dashboard Auto-Update System &copy; 2026</div>
  </div>

  <script id="dashboard-data" type="application/json">__DATA_JSON__</script>
  
  <script>
    const data = JSON.parse(document.getElementById('dashboard-data').textContent);
    const snapshot = data.snapshot;
    const latest = data.latest_change || { removed_previous_indexes: [], added_current_indexes: [], moved: [], likely_admitted_previous_indexes: [], likely_withdrawn_previous_indexes: [], likely_age_out_previous_indexes: [] };
    const history = data.history || [];

    const $ = (id) => document.getElementById(id);
    const fmt = new Intl.DateTimeFormat('zh-TW', { dateStyle: 'medium', timeStyle: 'short' });
    
    // --- 日期計算工具 ---
    function getDaysOld(birthStr, targetStr) {
        if (!birthStr || !targetStr) return 0;
        const bDate = new Date(birthStr);
        const tDate = new Date(targetStr.split('T')[0]);
        return Math.floor((tDate - bDate) / (1000 * 60 * 60 * 24));
    }

    function getAgeString(birthStr, targetStr) {
        if (!birthStr || !targetStr) return '—';
        const [bY, bM, bD] = birthStr.split('-').map(Number);
        const targetDate = new Date(targetStr);
        const tY = targetDate.getFullYear();
        const tM = targetDate.getMonth() + 1;
        const tD = targetDate.getDate();

        let years = tY - bY;
        let months = tM - bM;
        let days = tD - bD;

        if (days < 0) {
            months--;
            const prevMonth = new Date(tY, tM - 1, 0); 
            days += prevMonth.getDate();
        }
        if (months < 0) {
            years--;
            months += 12;
        }
        
        if (years < 0) return '尚未出生';
        return `${years}Y / ${months}M / ${days}D`;
    }

    // --- 卡片數值更新 ---
    let changeText = '';
    if (latest.changed && latest.fetched_at) {
        const cDate = new Date(latest.fetched_at);
        changeText = ` (發生於 ${cDate.getMonth() + 1}/${cDate.getDate()} ${cDate.getHours()}:${String(cDate.getMinutes()).padStart(2, '0')})`;
        const cEl = $('latest-change-time');
        if (cEl) cEl.textContent = changeText;
    }
    
    $('updated-at').textContent = fmt.format(new Date(snapshot.fetched_at));
    $('waiting-count').textContent = snapshot.waiting_count;
    $('lastnum').textContent = snapshot.last_month_enrolled ?? '—';
    $('capacity').textContent = `${snapshot.org.capnum ?? '—'} / ${snapshot.org.enroll_count ?? '—'}`;
    
    $('removed-count').textContent = latest.removed_previous_indexes.length;
    $('admitted-count').textContent = (latest.likely_admitted_previous_indexes || []).length;
    $('age-out-count').textContent = (latest.likely_age_out_previous_indexes || []).length;
    $('withdrawn-count').textContent = (latest.likely_withdrawn_previous_indexes || []).length;
    
    $('removed-summary').textContent = latest.removed_previous_indexes.length ? '序號 ' + latest.removed_previous_indexes.join('、') + changeText : '尚無紀錄';
    $('admitted-summary').textContent = latest.likely_admitted_previous_indexes?.length ? '序號 ' + latest.likely_admitted_previous_indexes.join('、') : '無';
    $('age-out-summary').textContent = latest.likely_age_out_previous_indexes?.length ? '序號 ' + latest.likely_age_out_previous_indexes.join('、') : '無';
    $('withdrawn-summary').textContent = latest.likely_withdrawn_previous_indexes?.length ? '序號 ' + latest.likely_withdrawn_previous_indexes.join('、') : '無';

    // --- Chip標籤 ---
    function renderChips(targetId, values, emptyText, formatter) {
      const target = $(targetId);
      if(!target) return;
      target.innerHTML = '';
      if (!values || !values.length) {
        target.innerHTML = `<div class="chip">${emptyText}</div>`;
        return;
      }
      values.forEach((value) => {
        const el = document.createElement('div');
        el.className = 'chip'; el.textContent = formatter(value);
        target.appendChild(el);
      });
    }

    renderChips('removed-chips', latest.removed_previous_indexes, '尚無紀錄', (v) => `序號 ${v}`);
    renderChips('admitted-chips', latest.likely_admitted_previous_indexes, '無', (v) => `序號 ${v}`);
    renderChips('age-out-chips', latest.likely_age_out_previous_indexes, '無', (v) => `序號 ${v}`);
    renderChips('withdrawn-chips', latest.likely_withdrawn_previous_indexes, '無', (v) => `序號 ${v}`);

    // --- 名次推進明細 ---
    const movedTable = $('moved-table');
    if (movedTable) {
        if (!latest.moved || !latest.moved.length) {
          movedTable.innerHTML = '<tr><td colspan="4">尚無紀錄</td></tr>';
        } else {
          latest.moved.forEach((item) => {
            const cls = item.delta < 0 ? 'delta-up' : (item.delta > 0 ? 'delta-down' : 'delta-flat');
            movedTable.insertAdjacentHTML('beforeend', `<tr><td>${item.name}</td><td>${item.previous_index}</td><td>${item.current_index}</td><td class="${cls}">${item.delta}</td></tr>`);
          });
        }
    }

    // --- 前20名表格 (加入屆齡紅字判定) ---
    const top20Body = $('top20-table');
    if (top20Body) {
        snapshot.entries.slice(0, 20).forEach(e => {
            const ageStr = getAgeString(e.cbirthday, snapshot.fetched_at);
            const daysOld = getDaysOld(e.cbirthday, snapshot.fetched_at);
            const className = daysOld >= 716 ? ' class="aging-out"' : '';
            top20Body.insertAdjacentHTML('beforeend', `<tr${className}><td>${e.index}</td><td>${e.encname}</td><td>${e.cbirthday}</td><td>${ageStr}</td><td>${e.displaydesc}</td></tr>`);
        });
    }

    // --- 所有名單表格 (加入屆齡紅字判定) ---
    function sortEntries(entries, key, direction) {
      const sorted = [...entries].sort((a, b) => {
        if (key === 'index') return Number(a[key]) - Number(b[key]);
        if (key === 'age') return String(b.cbirthday).localeCompare(String(a.cbirthday));
        return String(a[key]).localeCompare(String(b[key]), 'zh-Hant');
      });
      return direction === 'desc' ? sorted.reverse() : sorted;
    }

    function renderAllListTable() {
      const key = $('all-list-sort-key').value;
      const dir = $('all-list-sort-direction').value;
      const rows = sortEntries(snapshot.entries, key, dir);
      const target = $('all-list-table');
      if(!target) return;
      target.innerHTML = '';
      rows.forEach((e) => {
        const ageStr = getAgeString(e.cbirthday, snapshot.fetched_at);
        const daysOld = getDaysOld(e.cbirthday, snapshot.fetched_at);
        const className = daysOld >= 716 ? ' class="aging-out"' : '';
        target.insertAdjacentHTML('beforeend', `<tr${className}><td>${e.index}</td><td>${e.encname}</td><td>${e.cbirthday}</td><td>${ageStr}</td><td>${e.displaydesc}</td></tr>`);
      });
    }

    const sortKeyEl = $('all-list-sort-key');
    const sortDirEl = $('all-list-sort-direction');
    if(sortKeyEl) sortKeyEl.addEventListener('change', renderAllListTable);
    if(sortDirEl) sortDirEl.addEventListener('change', renderAllListTable);
    renderAllListTable();

    // --- 前20名身分長條圖 ---
    const top20Bars = $('top20-bars');
    if (top20Bars) {
        const counts = new Map();
        snapshot.entries.slice(0, 20).forEach((entry) => counts.set(entry.displaydesc, (counts.get(entry.displaydesc) || 0) + 1));
        const topCategoryTotal = Math.max(1, snapshot.entries.slice(0, 20).length);
        const maxCount = Math.max(1, ...counts.values());
        [...counts.entries()].sort((a, b) => b[1] - a[1]).forEach(([label, count]) => {
          const pct = Math.round((count / topCategoryTotal) * 1000) / 10;
          const widthPct = (count / maxCount) * 100;
          top20Bars.insertAdjacentHTML('beforeend', `<div class="bar-row"><div>${label}</div><div class="bar-track"><div class="bar-fill" style="width:${widthPct}%"></div></div><div>${count} 人 / ${pct}%</div></div>`);
        });
    }

    // --- 畫圖引擎 ---
    function getDailyHistory() {
        const dailyMap = {};
        history.forEach(p => { dailyMap[p.fetched_at.split('T')[0]] = p; });
        return Object.values(dailyMap);
    }

    function initDateSelector() {
        const dates = [...new Set(history.map(p => p.fetched_at.split('T')[0]))].reverse();
        const selector = $('date-selector');
        if(!selector) return;
        dates.forEach(d => {
            const opt = document.createElement('option');
            opt.value = opt.textContent = d;
            selector.appendChild(opt);
        });
        selector.onchange = () => renderHourlyChart();
    }

    function drawChart(svgId, points, labelMode) {
      const svg = $(svgId);
      if(!svg) return;
      if (!points || !points.length) {
        svg.innerHTML = '<text x="20" y="40" fill="#9bb2c8">尚無歷史資料</text>';
        return;
      }
      
      svg.innerHTML = '';
      const width = 760, height = 300, pad = 36;
      const vals = points.map((p) => p.waiting_count);
      const min = Math.min(...vals), max = Math.max(...vals);
      const range = Math.max(1, max - min);
      const xStep = points.length === 1 ? 0 : (width - pad * 2) / (points.length - 1);
      const toX = (i) => pad + i * xStep;
      const toY = (value) => height - pad - ((value - min) / range) * (height - pad * 2);
      
      let html = '';
      for (let i = 0; i <= 4; i++) {
        const y = pad + i * ((height - pad * 2) / 4);
        html += `<line x1="${pad}" y1="${y}" x2="${width - pad}" y2="${y}" stroke="#17324c" stroke-width="1" />`;
      }
      
      const linePath = points.map((p, i) => `${toX(i)},${toY(p.waiting_count)}`).join(' ');
      const color = labelMode === 'time' ? '#8ef7c2' : '#52d1ff';
      html += `<polyline fill="none" stroke="${color}" stroke-width="3" points="${linePath}" />`;
      html += `<text x="${pad}" y="20" fill="#9bb2c8" font-size="12">最少 ${min} / 最多 ${max}</text>`;
      
      points.forEach((p, i) => {
        const x = toX(i), y = toY(p.waiting_count);
        const labelText = labelMode === 'date' ? p.fetched_at.split('T')[0].substring(5) : p.fetched_at.split('T')[1].substring(0,5);
        if (points.length <= 15 || i % Math.ceil(points.length / 10) === 0) {
            html += `<text x="${x}" y="${height - 10}" fill="#9bb2c8" font-size="11" text-anchor="middle">${labelText}</text>`;
        }
        html += `<circle cx="${x}" cy="${y}" r="4" fill="#52d1ff"><title>${p.fetched_at.replace('T', ' ')}：${p.waiting_count} 人</title></circle>`;
      });
      svg.innerHTML = html;
    }

    function renderHourlyChart() {
        const date = $('date-selector').value;
        if(!date) return;
        const dayPoints = history.filter(p => p.fetched_at.startsWith(date));
        drawChart('hourly-chart', dayPoints, 'time');
    }

    // --- 歷史紀錄清單 ---
    const timeline = $('history-timeline');
    const stableToggle = $('toggle-stable');

    function updateStableVisibility() {
      document.querySelectorAll('.timeline-item[data-change-kind="stable"]').forEach((node) => {
        node.classList.toggle('stable-hidden', !stableToggle.checked);
      });
    }

    if(stableToggle) stableToggle.addEventListener('change', updateStableVisibility);

    if (timeline) {
        if (!history.length) {
          timeline.innerHTML = '<div class="timeline-item">尚無歷史紀錄</div>';
        } else {
          [...history].reverse().forEach((item) => {
            const card = document.createElement('div');
            card.className = 'timeline-item';
            card.style.background = '#13253a'; card.style.padding = '15px'; card.style.borderRadius = '10px'; card.style.marginBottom = '10px';
            card.dataset.changeKind = item.change_kind || 'stable';
            if ((item.change_kind || 'stable') === 'stable') card.classList.add('stable-hidden');
            
            let detailsHtml = '';
            if (item.removed_details && item.removed_details.length > 0) {
                detailsHtml = '<div style="margin-top:10px;"><table class="panel-table" style="font-size:13px;"><thead><tr><th>原序號</th><th>兒童姓名</th><th>當時歲數</th><th>推測類型</th></tr></thead><tbody>';
                item.removed_details.forEach(rd => {
                    const age = getAgeString(rd.birthday, item.fetched_at);
                    let type = '自行取消';
                    if ((item.likely_age_out_previous_indexes || []).includes(rd.previous_index)) type = '<span style="color:var(--danger)">屆齡取消</span>';
                    else if (rd.previous_index <= 15) type = '<span style="color:var(--ok)">遞補入托</span>';
                    detailsHtml += `<tr><td>${rd.previous_index}</td><td>${rd.name}</td><td>${age}</td><td>${type}</td></tr>`;
                });
                detailsHtml += '</tbody></table></div>';
            }

            const lines = (item.summary_lines || ['名單無變動']).map((line) => `<li>${line}</li>`).join('');
            let highlight = item.highlight_shift ? `<div class="timeline-highlight">代表性變動：${item.highlight_shift.previous_index} → ${item.highlight_shift.current_index}（${item.highlight_shift.name}）</div>` : '';
            
            card.innerHTML = `
                <div class="timeline-meta" style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <div>${fmt.format(new Date(item.fetched_at))}</div>
                    <div style="color:var(--accent-2)">總數：${item.waiting_count} 人</div>
                </div>
                <ul class="timeline-lines" style="margin:0; padding-left:20px; color:var(--muted);">${lines}</ul>
                ${highlight}${detailsHtml}
            `;
            timeline.appendChild(card);
          });
          updateStableVisibility();
        }
    }

    // --- 相關說明區 ---
    function renderRelatedInfo(text) {
      const target = $('related-info-text');
      if(!target) return;
      const marker = '三、缺額遞補原則：';
      const start = text.indexOf(marker);
      if (start === -1) { target.textContent = text; return; }
      const before = text.slice(0, start).trim();
      const afterMarker = text.slice(start + marker.length);
      let end = afterMarker.length;
      ['四、不列入備取名單情形：', '五、', '六、'].forEach(c => {
        const idx = afterMarker.indexOf(c);
        if (idx !== -1 && idx < end) end = idx;
      });
      const highlightBody = afterMarker.slice(0, end).trim();
      const after = afterMarker.slice(end).trim();
      const regexHeading = /^(相關說明：|[一二三四五六七八九十]+、.*|備註：.*)$/;
      const regexBullet = /^\d+\./;

      function buildSections(t) {
        const sections = []; let current = null;
        t.split('\n').map(l => l.trim()).filter(Boolean).forEach(l => {
          if (regexHeading.test(l) && !regexBullet.test(l)) {
            if (current) sections.push(current);
            const parts = l.split('：');
            current = { title: parts[0] + (parts.length > 1 ? '：' : ''), notes: parts.slice(1).join('：').trim() ? [parts.slice(1).join('：').trim()] : [], bullets: [] };
          } else if (regexBullet.test(l)) {
            if (!current) current = { title: '', notes: [], bullets: [] };
            current.bullets.push(l.replace(regexBullet, '').trim());
          } else {
            if (!current) current = { title: '', notes: [], bullets: [] };
            current.notes.push(l);
          }
        });
        if (current) sections.push(current);
        return sections;
      }
      function renderSection(s) {
        return `<section class="related-section">${s.title ? `<div class="related-block-title">${s.title}</div>` : ''}${s.notes.map(n => `<div class="related-note">${n}</div>`).join('')}${s.bullets.length ? `<ul class="related-list">${s.bullets.map(b => `<li>${b}</li>`).join('')}</ul>` : ''}</section>`;
      }
      const blocks = buildSections(before).map(renderSection);
      blocks.push(`<section class="related-section rule-highlight"><strong>三、缺額遞補原則</strong><div class="related-note">${highlightBody.replace(/\n/g, '<br>')}</div></section>`);
      blocks.push(...buildSections(after).map(renderSection));
      target.innerHTML = blocks.join('');
    }
    renderRelatedInfo(data.related_info_text || '');

    // --- 分頁切換 ---
    document.querySelectorAll('.tab-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const tab = button.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.toggle('active', btn === button));
        document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
        $('tab-' + tab).classList.add('active');
        if (tab === 'hourly-detail') renderHourlyChart();
      });
    });

    // --- 啟動初始化 ---
    window.onload = () => {
        drawChart('history-chart', getDailyHistory(), 'date');
        initDateSelector();
        renderHourlyChart();
    };
  </script>
</body>
</html>"""

    return (html_template
            .replace("__SAFE_TITLE__", safe_title)
            .replace("__SAFE_ORGID__", safe_orgid)
            .replace("__SAFE_ORGNAME__", safe_orgname)
            .replace("__DATA_JSON__", data_json))