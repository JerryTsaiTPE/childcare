from __future__ import annotations

import html
import json
from typing import Any


def _json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_dashboard(
    *,
    all_data: dict[str, dict[str, Any]],
    rule_text: str,
    validity_text: str,
    related_info_text: str,
) -> str:
    safe_title = "新北市公托候補追蹤Dashboard"

    payload = {
        "all_data": all_data
    }
    data_json = _json_script(payload)

    html_template = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__SAFE_TITLE__</title>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-FV2WPFKJTZ"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());

    gtag('config', 'G-FV2WPFKJTZ');
  </script>
  <style>
    :root {
      --bg: #07111f; --panel: #0d1b2a; --card: #13253a; --border: #284864;
      --accent: #52d1ff; --accent-2: #8ef7c2; --text: #edf6ff; --muted: #9bb2c8;
      --danger: #ff7b7b; --warn: #ffd166; --ok: #8ef7c2; --tab-bg: #0a1624;
      --fav: #ffc107;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, 'Noto Sans TC', sans-serif; background: linear-gradient(180deg, #06101b, #0b1626 30%, #09131f); color: var(--text); }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .hero { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 20px; }
    .hero h1 { margin: 0 0 8px; font-size: 34px; }
    .sub { color: var(--muted); line-height: 1.6; }
    
    .org-switch-wrapper { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
    .org-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .org-select { background: #13314d; color: var(--text); border: 2px solid var(--accent); border-radius: 8px; padding: 10px 16px; font-size: 16px; font-weight: bold; cursor: pointer; outline: none; transition: 0.3s; }
    .org-select:hover { border-color: var(--accent-2); }
    
    .fav-btn { background: var(--tab-bg); color: var(--muted); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 14px; cursor: pointer; transition: 0.2s; display: inline-flex; align-items: center; gap: 6px; font-weight: bold; }
    .fav-btn:hover { background: #13253a; border-color: var(--muted); }
    .fav-btn.active { color: #fff; background: rgba(255, 193, 7, 0.15); border-color: var(--fav); box-shadow: 0 0 10px rgba(255, 193, 7, 0.2); }
    .fav-btn.active .star { color: var(--fav); }
    .star { font-size: 16px; line-height: 1; }
    
    .overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.6); z-index: 999; opacity: 0; pointer-events: none; transition: 0.3s; backdrop-filter: blur(3px); }
    .overlay.active { opacity: 1; pointer-events: auto; }
    .slide-panel { position: fixed; top: 0; right: -420px; width: 100%; max-width: 400px; height: 100vh; background: var(--panel); z-index: 1000; box-shadow: -5px 0 30px rgba(0,0,0,0.5); transition: 0.4s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column; }
    .slide-panel.active { right: 0; }
    .slide-panel-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid var(--border); background: #0a1624; }
    .slide-panel-header h2 { margin: 0; font-size: 20px; color: var(--accent); display: flex; align-items: center; gap: 8px;}
    .close-btn { background: transparent; border: none; color: var(--muted); font-size: 24px; cursor: pointer; transition: 0.2s; padding: 0; line-height: 1;}
    .close-btn:hover { color: var(--danger); transform: scale(1.1); }
    .slide-panel-content { padding: 24px; overflow-y: auto; flex-grow: 1; display: grid; gap: 16px; align-content: flex-start; }
    
    /* 💡 優化：行政區統計清單樣式 (修復對齊問題) */
    .dist-stats-table { width: 100%; border-collapse: collapse; margin-top: 10px; background: rgba(0,0,0,0.2); border-radius: 12px; overflow: hidden; table-layout: fixed; }
    .dist-stats-table th, .dist-stats-table td { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .dist-stats-table th { font-size: 12px; color: var(--muted); background: rgba(255,255,255,0.02); text-transform: uppercase; letter-spacing: 1px; }
    
    /* 欄位寬度與對齊控制 */
    .dist-col-name { text-align: left; width: 40%; }
    .dist-col-num { text-align: right; width: 35%; }
    .dist-col-pct { text-align: right; width: 25%; }

    .dist-stats-table td { font-size: 14px; }
    .dist-stats-table tr:last-child td { border-bottom: none; }
    .dist-name { font-weight: bold; color: var(--accent-2); }
    .dist-count { font-weight: bold; font-family: Consolas, monospace; }
    .dist-pct { color: var(--muted); font-size: 12px; font-family: Consolas, monospace; }

    .tabs { display: flex; gap: 10px; margin-bottom: 18px; overflow-x: auto; padding-bottom: 4px; }
    .tab-btn { border: 1px solid var(--border); background: var(--tab-bg); color: var(--muted); border-radius: 999px; padding: 10px 16px; cursor: pointer; white-space: nowrap; flex: 0 0 auto; transition: 0.2s; }
    .tab-btn.active { color: var(--text); background: #13314d; border-color: var(--accent); }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; animation: fadeIn 0.3s ease; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
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
    
    .chart-tooltip { position: absolute; background: rgba(13, 27, 42, 0.95); border: 1px solid var(--border); color: var(--text); padding: 10px 14px; border-radius: 8px; font-size: 13px; pointer-events: none; opacity: 0; transition: opacity 0.2s ease; box-shadow: 0 4px 16px rgba(0,0,0,0.4); z-index: 100; white-space: nowrap; line-height: 1.5; }

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
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid rgba(107, 139, 168, 0.18); }
    th { color: var(--muted); font-weight: 600; }
    tr:hover td { background: rgba(255,255,255,0.02); }
    
    .aging-out td { color: var(--danger); font-weight: 500; }
    
    .rule { white-space: pre-wrap; line-height: 1.8; color: #d9ebff; background: #091522; padding: 18px; border-radius: 14px; border: 1px solid #18324d; }
    .info-stack { display: grid; gap: 16px; }
    .history-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
    .toggle { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); }
    .footer { color: var(--muted); font-size: 13px; margin-top: 16px; text-align: center; }
    @media (max-width: 980px) { .panels { grid-template-columns: 1fr; } }
    @media (max-width: 720px) { .hero { flex-direction: column; align-items: flex-start; gap: 20px; } .org-switch-wrapper { align-items: flex-start; width: 100%; } .org-controls { justify-content: flex-start; width: 100%; } .org-select { flex-grow: 1; width: auto; } }
  </style>
  <script>
    window.onerror = function(message, source, lineno, colno, error) {
        const errDiv = document.createElement('div');
        errDiv.style.cssText = 'position:fixed; top:0; left:0; width:100%; background:var(--danger); color:#000; padding:20px; z-index:9999; font-weight:bold;';
        errDiv.innerHTML = `<h3>⚠️ 介面渲染發生致命錯誤</h3><p>${message}</p><p>發生在行數: ${lineno}</p>`;
        document.body.prepend(errDiv);
    };
  </script>
</head>
<body>
  
  <div id="chart-tooltip" class="chart-tooltip"></div>

  <div id="stats-overlay" class="overlay"></div>
  <div id="stats-panel" class="slide-panel">
    <div class="slide-panel-header">
      <h2>🌍 全新北市統計概況</h2>
      <button id="btn-close-stats" class="close-btn" title="關閉">✖</button>
    </div>
    <div class="slide-panel-content">
      <div class="card" style="background: rgba(19, 49, 77, 0.4); border-color: var(--accent);">
        <div class="metric">公托中心總數</div>
        <div class="value" id="global-org-count" style="color: var(--accent);">--</div>
      </div>
      <div class="card">
        <div class="metric">公托總核定名額 <span style="font-size:12px">(加總)</span></div>
        <div class="value" id="global-cap-count">--</div>
      </div>
      <div class="card" style="border: 1px solid var(--danger);">
        <div class="metric">目前排隊備取總人數 <span style="font-size:12px; color:var(--danger)">(已去除重複)</span></div>
        <div class="value" id="global-unique-waitlist">--</div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">※ 比對條件：<br>「姓名 + 生日 + 報名身分別」完全相同者，視為同一幼兒，僅計算 1 人。</div>
      </div>
      
      <div class="panel" style="padding: 15px; background: transparent; border-color: var(--border);">
        <h3 style="margin-top:0; font-size:16px; color: var(--accent-2);">各行政區備取概況</h3>
        <table class="dist-stats-table">
          <thead>
            <tr>
                <th class="dist-col-name">行政區</th>
                <th class="dist-col-num">人數</th>
                <th class="dist-col-pct">占比</th>
            </tr>
          </thead>
          <tbody id="district-stats-body">
            </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="wrap">
    <section class="hero">
      <div>
        <h1 id="main-title">公托備取追蹤 Dashboard</h1>
        <div class="sub">資料來源：新北育兒資訊網公開備取 API<br>系統最後更新：<span id="updated-at"></span></div>
      </div>
      <div class="org-switch-wrapper">
        <div class="org-controls">
          <select id="district-selector" class="org-select" style="max-width: 140px;"></select>
          <select id="global-org-selector" class="org-select"></select>
          <button id="btn-favorite" class="fav-btn" title="將目前中心設為預設"><span class="star">☆</span> 設為預設</button>
          
          <button id="btn-city-stats" class="fav-btn" style="padding: 10px 14px; border-radius: 8px;" title="查看全新北市統計">📊 全區統計</button>
        </div>
        <div class="pill" id="org-pill">載入中...</div>
      </div>
    </section>

    <section class="tabs">
      <button class="tab-btn active" data-tab="overview">總覽</button>
      <button class="tab-btn" data-tab="all-list">所有備取名單</button>
      <button class="tab-btn" data-tab="hourly-detail">歷史走勢</button>
      <button class="tab-btn" data-tab="history">歷史紀錄</button>
    </section>

    <section id="tab-overview" class="tab-panel active">
      <section class="grid">
        <div class="card"><div class="metric">目前備取總數</div><div class="value" id="waiting-count"></div></div>
        <div class="card"><div class="metric">中心核定名額 / 已入托</div><div class="value" id="capacity"></div></div>
        <div class="card"><div class="metric">上月入托人數</div><div class="value" id="lastnum"></div></div>
        <div class="card"><div class="metric">近一次離開名單人數</div><div class="value small" id="removed-count"></div><div class="sub" id="removed-summary"></div></div>
        <div class="card"><div class="metric">推測遞補/入托</div><div class="value small" id="admitted-count"></div><div class="sub" id="admitted-summary"></div></div>
        <div class="card"><div class="metric">推測自行取消候補</div><div class="value small" id="withdrawn-count"></div><div class="sub" id="withdrawn-summary"></div></div>
        <div class="card"><div class="metric">屆齡取消</div><div class="value small" id="age-out-count"></div><div class="sub" id="age-out-summary"></div></div>
        <div class="card"><div class="metric">近一次影響人數</div><div class="value small" id="moved-count"></div><div class="sub" id="moved-summary"></div></div>
      </section>

      <section class="panels">
        <div class="panel chart-box">
          <h2>📈 近一週備取總數 <span class="sub" style="font-size:13px; font-weight:normal;">(顯示每日最後狀態)</span></h2>
          <svg id="history-chart" width="100%" height="300"></svg>
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
              <h3>新增候補</h3>
              <div class="chips" id="added-chips"></div>
            </div>
            <div class="list-block">
              <h3>離開名單序號</h3>
              <div class="chips" id="removed-chips"></div>
            </div>
            <div class="list-block">
              <h3>推測為遞補入托 (20號內)</h3>
              <div class="chips" id="admitted-chips"></div>
            </div>
            <div class="list-block">
              <h3>屆齡取消 (滿兩歲)</h3>
              <div class="chips" id="age-out-chips"></div>
            </div>
            <div class="list-block">
              <h3>推測為自行取消 (20號外)</h3>
              <div class="chips" id="withdrawn-chips"></div>
            </div>
            <div class="list-block">
              <h3>名次變動明細</h3>
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
          <h2>前 20 名備取名單 <span class="sub" style="font-size:13px; font-weight:normal; margin-left:8px;">(紅色為已屆齡or14天內屆齡者)</span></h2>
          <div class="table-wrap">
            <table class="panel-table">
              <thead><tr><th>序號</th><th>姓名</th><th>出生日期</th><th>目前歲數</th><th>身分別</th><th style="color:var(--accent)">同步候補</th></tr></thead>
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
          <h2>相關說明 (依中心不同而異)</h2>
          <div class="rule" id="related-info-text"></div>
        </div>
      </section>
    </section>

    <section id="tab-hourly-detail" class="tab-panel">
      <div class="panel chart-box" style="margin-bottom: 18px;">
        <h2>📅 近一個月走勢 <span class="sub" style="font-size:13px; font-weight:normal;">(顯示每日最後狀態)</span></h2>
        <svg id="monthly-chart" width="100%" height="300"></svg>
      </div>
      <div class="panel chart-box">
        <h2>🕒 單日詳細走勢</h2>
        <div class="control-row" style="margin-bottom: 15px;">
          <label>選擇日期查看當日趨勢：</label>
          <select id="date-selector" class="select-input"></select>
        </div>
        <svg id="hourly-chart" width="100%" height="300"></svg>
      </div>
    </section>

    <section id="tab-all-list" class="tab-panel">
      <div class="panel">
        <h2>所有名單 <span class="sub" style="font-size:14px; font-weight:normal; margin-left:10px; color:var(--danger);">※ 紅色字體代表該幼兒已滿兩歲或距滿兩歲不到 14 天，即將被系統自動取消候補。</span></h2>
        
        <div class="sub" style="margin-bottom: 15px; color: var(--muted); border-left: 3px solid var(--accent); padding-left: 10px; font-size: 13px;">
          如果同步候補超過一家公托屬於正常現象，去識別化容易導致同名同生日，依規定一人同時只能候補兩間。
        </div>

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
            <thead><tr><th>序號</th><th>姓名</th><th>出生日期</th><th>目前歲數</th><th>身分別</th><th style="color:var(--accent)">同步候補</th></tr></thead>
            <tbody id="all-list-table"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="tab-history" class="tab-panel">
      <div class="panel">
        <h2>歷史紀錄</h2>
        <div class="history-toolbar">
          <div class="sub">紀錄每次更新的變動；若整串名次都往前，僅顯示第一個作為代表。</div>
          <label class="toggle"><input id="toggle-stable" type="checkbox" /> 顯示無變動紀錄</label>
        </div>
        <div id="history-timeline" class="timeline"></div>
      </div>
    </section>

    <div class="footer">NTPC Childcare Dashboard Auto-Update System &copy; 2026</div>
  </div>

  <script id="dashboard-data" type="application/json">__DATA_JSON__</script>
  
  <script>
    let payload, allData, orgIds, currentOrgId;
    let snapshot = null;
    let latest = null;
    let historyData = [];
    const STORAGE_KEY = 'ntpc_childcare_default_org';
    let orgsByDistrict = {}; 

    const $ = (id) => document.getElementById(id);
    const fmt = new Intl.DateTimeFormat('zh-TW', { dateStyle: 'medium', timeStyle: 'short' });
    
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

    function isStrictlyTwo(birthStr, targetStr) {
        if (!birthStr || !targetStr) return false;
        const [bY, bM, bD] = birthStr.split('-').map(Number);
        const tDate = new Date(targetStr.split('T')[0]);
        let y = tDate.getFullYear() - bY;
        let m = (tDate.getMonth() + 1) - bM;
        let d = tDate.getDate() - bD;
        if (d < 0) m--;
        if (m < 0) y--;
        return y >= 2;
    }

    function calculateGlobalStats() {
        let totalCap = 0;
        let globalUniqueChildren = new Set();
        let districtUniqueMap = {}; 

        orgIds.forEach(id => {
            const snap = allData[id].snapshot;
            if(!snap) return;
            
            const dist = snap.org.distdesc || '其他地區';
            if (!districtUniqueMap[dist]) districtUniqueMap[dist] = new Set();
            
            let cap = parseInt(snap.org.capnum, 10);
            if (!isNaN(cap)) totalCap += cap;

            if (snap.entries) {
                snap.entries.forEach(entry => {
                    const key = `${entry.encname}|${entry.cbirthday}|${entry.displaydesc || ''}`;
                    globalUniqueChildren.add(key);
                    districtUniqueMap[dist].add(key);
                });
            }
        });

        const totalUniqueCount = globalUniqueChildren.size;

        const gcEl = $('global-cap-count');
        const guEl = $('global-unique-waitlist');
        const goEl = $('global-org-count');
        
        if (goEl) goEl.textContent = orgIds.length + ' 間';
        if (gcEl) gcEl.textContent = totalCap + ' 名';
        if (guEl) guEl.textContent = '約 ' + totalUniqueCount + ' 人';

        const distBody = $('district-stats-body');
        if (distBody) {
            distBody.innerHTML = '';
            const sortedDistricts = Object.keys(districtUniqueMap).sort((a, b) => districtUniqueMap[b].size - districtUniqueMap[a].size);
            
            sortedDistricts.forEach(d => {
                const count = districtUniqueMap[d].size;
                const percentage = totalUniqueCount > 0 ? ((count / totalUniqueCount) * 100).toFixed(1) : 0;
                
                const row = `
                    <tr>
                        <td class="dist-name dist-col-name">${d}</td>
                        <td class="dist-count dist-col-num">${count} 人</td>
                        <td class="dist-pct dist-col-pct">${percentage}%</td>
                    </tr>`;
                distBody.insertAdjacentHTML('beforeend', row);
            });
        }
    }

    function toggleStatsPanel() {
        const statsPanel = $('stats-panel');
        const statsOverlay = $('stats-overlay');
        const isActive = statsPanel.classList.contains('active');
        
        if (!isActive) calculateGlobalStats(); 
        
        statsPanel.classList.toggle('active');
        statsOverlay.classList.toggle('active');
    }

    function renderCurrentOrg() {
        try {
            const data = allData[currentOrgId];
            if (!data) throw new Error("找不到指定的中心資料");
            
            snapshot = data.snapshot;
            latest = data.latest_change || {};
            historyData = data.history || [];

            latest.added_details = latest.added_details || [];
            latest.removed_previous_indexes = latest.removed_previous_indexes || [];
            latest.likely_admitted_previous_indexes = latest.likely_admitted_previous_indexes || [];
            latest.likely_age_out_previous_indexes = latest.likely_age_out_previous_indexes || [];
            latest.likely_withdrawn_previous_indexes = latest.likely_withdrawn_previous_indexes || [];
            latest.moved = latest.moved || [];
            
            if (latest.fetched_at && latest.removed_previous_indexes.length > 0) {
                const matchingHistory = historyData.find(h => h.fetched_at === latest.fetched_at);
                if (matchingHistory && matchingHistory.removed_details) {
                    let strictAgeOut = [];
                    let strictAdmitted = [];
                    let strictWithdrawn = [];
                    
                    matchingHistory.removed_details.forEach(rd => {
                        if (isStrictlyTwo(rd.birthday, matchingHistory.fetched_at)) {
                            strictAgeOut.push(rd.previous_index);
                        } 
                        else if ((latest.likely_admitted_previous_indexes || []).includes(rd.previous_index) || rd.previous_index <= 20) {
                            strictAdmitted.push(rd.previous_index);
                        } 
                        else {
                            strictWithdrawn.push(rd.previous_index);
                        }
                    });
                    
                    latest.likely_age_out_previous_indexes = strictAgeOut;
                    latest.likely_admitted_previous_indexes = strictAdmitted;
                    latest.likely_withdrawn_previous_indexes = strictWithdrawn;
                }
            }

            const favBtn = $('btn-favorite');
            if (favBtn) {
                const savedOrgId = localStorage.getItem(STORAGE_KEY);
                if (savedOrgId === currentOrgId) {
                    favBtn.classList.add('active');
                    favBtn.innerHTML = '<span class="star">⭐</span> 預設中心';
                } else {
                    favBtn.classList.remove('active');
                    favBtn.innerHTML = '<span class="star">☆</span> 設為預設';
                }
            }

            const titleEl = $('main-title');
            if (titleEl && snapshot.org) titleEl.textContent = `${snapshot.org.orgshort} 公托備取追蹤`;
            const pillEl = $('org-pill');
            if (pillEl && snapshot.org) pillEl.textContent = `${snapshot.org.distdesc}／${snapshot.org.orgname}`;
            
            let changeText = '';
            if (latest.changed && latest.fetched_at) {
                const cDate = new Date(latest.fetched_at);
                changeText = ` (發生於 ${cDate.getMonth() + 1}/${cDate.getDate()} ${cDate.getHours()}:${String(cDate.getMinutes()).padStart(2, '0')})`;
            }
            const cEl = $('latest-change-time');
            if (cEl) cEl.textContent = changeText;
            
            const upEl = $('updated-at');
            if (upEl) upEl.textContent = fmt.format(new Date(snapshot.fetched_at));
            
            const wcEl = $('waiting-count');
            if (wcEl) wcEl.textContent = snapshot.waiting_count;
            
            const lnEl = $('lastnum');
            if (lnEl) lnEl.textContent = snapshot.last_month_enrolled || '—';
            
            const capEl = $('capacity');
            if (capEl) capEl.textContent = `${snapshot.org.capnum || '—'} / ${snapshot.org.enroll_count || '—'}`;
            
            const rcEl = $('removed-count');
            if (rcEl) rcEl.textContent = latest.removed_previous_indexes.length;
            const acEl = $('admitted-count');
            if (acEl) acEl.textContent = latest.likely_admitted_previous_indexes.length;
            const aocEl = $('age-out-count');
            if (aocEl) aocEl.textContent = latest.likely_age_out_previous_indexes.length;
            const wdcEl = $('withdrawn-count');
            if (wdcEl) wdcEl.textContent = latest.likely_withdrawn_previous_indexes.length;
            
            const mcEl = $('moved-count');
            if (mcEl) mcEl.textContent = latest.moved.length;
            const msEl = $('moved-summary');
            if (msEl) msEl.textContent = latest.moved.length ? `共有 ${latest.moved.length} 位推進` + changeText : '尚無紀錄';
            
            const rsEl = $('removed-summary');
            if (rsEl) rsEl.textContent = latest.removed_previous_indexes.length ? '序號 ' + latest.removed_previous_indexes.join('、') + changeText : '尚無紀錄';
            const asEl = $('admitted-summary');
            if (asEl) asEl.textContent = latest.likely_admitted_previous_indexes.length ? '序號 ' + latest.likely_admitted_previous_indexes.join('、') : '無';
            const aosEl = $('age-out-summary');
            if (aosEl) aosEl.textContent = latest.likely_age_out_previous_indexes.length ? '序號 ' + latest.likely_age_out_previous_indexes.join('、') : '無';
            const wdsEl = $('withdrawn-summary');
            if (wdsEl) wdsEl.textContent = latest.likely_withdrawn_previous_indexes.length ? '序號 ' + latest.likely_withdrawn_previous_indexes.join('、') : '無';

            function renderChips(targetId, values, emptyText, formatter) {
              const target = $(targetId);
              if(!target) return;
              target.innerHTML = '';
              if (!values || !values.length) {
                target.innerHTML = `<div class="chip">${emptyText}</div>`; return;
              }
              values.forEach((value) => {
                const el = document.createElement('div');
                el.className = 'chip'; el.textContent = formatter(value);
                target.appendChild(el);
              });
            }
            
            renderChips('added-chips', latest.added_details, '無', (v) => {
                let idx = (typeof v === 'object') ? (v.current_index || v.index || '?') : v;
                return `序號 ${idx}`;
            });

            renderChips('removed-chips', latest.removed_previous_indexes, '尚無紀錄', (v) => `序號 ${v}`);
            renderChips('admitted-chips', latest.likely_admitted_previous_indexes, '無', (v) => `序號 ${v}`);
            renderChips('age-out-chips', latest.likely_age_out_previous_indexes, '無', (v) => `序號 ${v}`);
            renderChips('withdrawn-chips', latest.likely_withdrawn_previous_indexes, '無', (v) => `序號 ${v}`);

            const movedTable = $('moved-table');
            if (movedTable) {
                movedTable.innerHTML = '';
                if (!latest.moved || !latest.moved.length) {
                    movedTable.innerHTML = '<tr><td colspan="4">尚無紀錄</td></tr>';
                } else {
                    latest.moved.forEach((item) => {
                        const cls = item.delta < 0 ? 'delta-up' : (item.delta > 0 ? 'delta-down' : 'delta-flat');
                        movedTable.insertAdjacentHTML('beforeend', `<tr><td>${item.name}</td><td>${item.previous_index}</td><td>${item.current_index}</td><td class="${cls}">${item.delta}</td></tr>`);
                    });
                }
            }

            const top20Body = $('top20-table');
            if (top20Body) {
                top20Body.innerHTML = '';
                const entriesList = snapshot.entries || [];
                entriesList.slice(0, 20).forEach(e => {
                    const ageStr = getAgeString(e.cbirthday, snapshot.fetched_at);
                    const daysOld = getDaysOld(e.cbirthday, snapshot.fetched_at);
                    const className = daysOld >= 716 ? ' class="aging-out"' : ''; 
                    const syncText = (e.sync_list && e.sync_list.length > 0) ? e.sync_list.join(', ') : '—';
                    top20Body.insertAdjacentHTML('beforeend', `<tr${className}><td>${e.index}</td><td>${e.encname}</td><td>${e.cbirthday}</td><td>${ageStr}</td><td>${e.displaydesc}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`);
                });
            }

            const top20Bars = $('top20-bars');
            if (top20Bars) {
                top20Bars.innerHTML = '';
                const counts = new Map();
                const entriesList = snapshot.entries || [];
                entriesList.slice(0, 20).forEach((entry) => counts.set(entry.displaydesc, (counts.get(entry.displaydesc) || 0) + 1));
                const topCategoryTotal = Math.max(1, entriesList.slice(0, 20).length);
                const maxCount = Math.max(1, ...counts.values());
                const sortedEntries = [];
                counts.forEach((v, k) => sortedEntries.push([k, v]));
                sortedEntries.sort((a, b) => b[1] - a[1]);
                sortedEntries.forEach((pair) => {
                  const label = pair[0];
                  const count = pair[1];
                  const pct = Math.round((count / topCategoryTotal) * 1000) / 10;
                  const widthPct = (count / maxCount) * 100;
                  top20Bars.insertAdjacentHTML('beforeend', `<div class="bar-row"><div>${label}</div><div class="bar-track"><div class="bar-fill" style="width:${widthPct}%"></div></div><div>${count} 人 / ${pct}%</div></div>`);
                });
            }

            renderAllListTable();

            const timeline = $('history-timeline');
            if (timeline) {
                timeline.innerHTML = '';
                if (!historyData.length) {
                  timeline.innerHTML = '<div class="timeline-item">尚無歷史紀錄</div>';
                } else {
                  const revHistory = [].concat(historyData).reverse();
                  revHistory.forEach((item) => {
                    const card = document.createElement('div');
                    card.className = 'timeline-item';
                    card.dataset.changeKind = item.change_kind || 'stable';
                    
                    let detailsHtml = '';
                    if (item.added_details && item.added_details.length > 0) {
                        detailsHtml += '<div style="margin-top:10px; margin-bottom:15px;"><table class="panel-table" style="font-size:13px; border-left: 3px solid var(--accent);"><thead><tr><th>新序號</th><th>兒童姓名</th><th>目前歲數</th><th>身分別</th><th>狀態</th></tr></thead><tbody>';
                        item.added_details.forEach(ad => {
                            const age = getAgeString(ad.birthday || ad.cbirthday, item.fetched_at);
                            const categoryStr = ad.category || ad.displaydesc || '—';
                            const name = ad.name || ad.encname || '未知';
                            const idx = ad.current_index || ad.index || '?';
                            detailsHtml += `<tr><td>${idx}</td><td>${name}</td><td>${age}</td><td>${categoryStr}</td><td><span style="color:var(--accent)">新增候補</span></td></tr>`;
                        });
                        detailsHtml += '</tbody></table></div>';
                    }

                    if (item.removed_details && item.removed_details.length > 0) {
                        detailsHtml += '<div style="margin-top:10px;"><table class="panel-table" style="font-size:13px;"><thead><tr><th>原序號</th><th>兒童姓名</th><th>當時歲數</th><th>身分別</th><th>狀態</th><th style="color:var(--accent)">目前其他候補</th></tr></thead><tbody>';
                        item.removed_details.forEach(rd => {
                            const age = getAgeString(rd.birthday, item.fetched_at);
                            let type = '推測自行取消';
                            if (isStrictlyTwo(rd.birthday, item.fetched_at)) {
                                type = '<span style="color:var(--danger)">屆齡取消</span>';
                            } else if ((item.likely_admitted_previous_indexes || []).includes(rd.previous_index) || rd.previous_index <= 20) {
                                type = '<span style="color:var(--ok)">推測遞補入托</span>';
                            }
                            let syncOrgs = [];
                            orgIds.forEach(oid => {
                                if (oid !== currentOrgId) {
                                    const otherSnapshot = allData[oid].snapshot;
                                    if (otherSnapshot && otherSnapshot.entries) {
                                        const found = otherSnapshot.entries.find(e => e.encname === rd.name && e.cbirthday === rd.birthday && e.displaydesc === rd.category);
                                        if (found) {
                                            syncOrgs.push(`${otherSnapshot.org.orgshort}(${found.index})`);
                                        }
                                    }
                                }
                            });
                            const syncText = syncOrgs.length > 0 ? syncOrgs.join(', ') : '—';
                            const categoryStr = rd.category || '—';
                            detailsHtml += `<tr><td>${rd.previous_index}</td><td>${rd.name}</td><td>${age}</td><td>${categoryStr}</td><td>${type}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`;
                        });
                        detailsHtml += '</tbody></table></div>';
                    }

                    const linesArray = item.summary_lines || ['名單無變動'];
                    const lines = linesArray.map((line) => `<li>${line}</li>`).join('');
                    let highlight = item.highlight_shift ? `<div class="timeline-highlight">代表性變動：${item.highlight_shift.previous_index} → ${item.highlight_shift.current_index}（${item.highlight_shift.name}）</div>` : '';
                    card.innerHTML = `
                        <div class="timeline-meta">
                            <div>${fmt.format(new Date(item.fetched_at))}</div>
                            <div style="color:var(--accent-2)">總數：${item.waiting_count} 人</div>
                        </div>
                        <ul class="timeline-lines">${lines}</ul>
                        ${highlight}${detailsHtml}
                    `;
                    timeline.appendChild(card);
                  });
                  updateStableVisibility();
                }
            }

            const valEl = $('validity-text');
            if (valEl) {
                valEl.textContent = data.validity_text || '請詳閱下方相關說明';
            }
            renderRelatedInfo(data.related_info_text || '無相關說明');

            initDateSelector();
            
            drawChart('history-chart', getDailyHistory().slice(-7), 'date');
            drawChart('monthly-chart', getDailyHistory().slice(-30), 'date');
            renderHourlyChart();
            
        } catch(err) {
            console.error("渲染期間發生錯誤:", err);
            const titleEl = $('main-title');
            if(titleEl) titleEl.textContent = "⚠️ 渲染失敗，請按 F12 查看錯誤日誌";
            const pillEl = $('org-pill');
            if(pillEl) pillEl.textContent = "Error: " + err.message;
        }
    }

    function sortEntries(entries, key, direction) {
      if (!entries) return [];
      const sorted = [].concat(entries).sort((a, b) => {
        if (key === 'index') return Number(a[key]) - Number(b[key]);
        if (key === 'age') return String(b.cbirthday).localeCompare(String(a.cbirthday));
        return String(a[key]).localeCompare(String(b[key]), 'zh-Hant');
      });
      return direction === 'desc' ? sorted.reverse() : sorted;
    }

    function renderAllListTable() {
      const keyEl = $('all-list-sort-key');
      const dirEl = $('all-list-sort-direction');
      const target = $('all-list-table');
      if(!target || !keyEl || !dirEl || !snapshot || !snapshot.entries) return;
      const rows = sortEntries(snapshot.entries, keyEl.value, dirEl.value);
      target.innerHTML = '';
      rows.forEach((e) => {
        const ageStr = getAgeString(e.cbirthday, snapshot.fetched_at);
        const daysOld = getDaysOld(e.cbirthday, snapshot.fetched_at);
        const className = daysOld >= 716 ? ' class="aging-out"' : ''; 
        const syncText = (e.sync_list && e.sync_list.length > 0) ? e.sync_list.join(', ') : '—';
        target.insertAdjacentHTML('beforeend', `<tr${className}><td>${e.index}</td><td>${e.encname}</td><td>${e.cbirthday}</td><td>${ageStr}</td><td>${e.displaydesc}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`);
      });
    }

    function updateStableVisibility() {
      const stableToggle = $('toggle-stable');
      const isChecked = stableToggle ? stableToggle.checked : false;
      document.querySelectorAll('.timeline-item').forEach((node) => {
        if(node.dataset.changeKind === 'stable') {
           node.classList.toggle('stable-hidden', !isChecked);
        }
      });
    }

    function getDailyHistory() {
        const dailyMap = {};
        historyData.forEach(p => { dailyMap[p.fetched_at.split('T')[0]] = p; });
        const vals = [];
        for (let k in dailyMap) vals.push(dailyMap[k]);
        return vals;
    }

    function initDateSelector() {
        const selector = $('date-selector');
        if(!selector) return;
        selector.innerHTML = '';
        const rawDates = historyData.map(p => p.fetched_at.split('T')[0]);
        const uniqueDates = [];
        rawDates.forEach(d => { if(uniqueDates.indexOf(d) === -1) uniqueDates.push(d); });
        uniqueDates.reverse().forEach(d => {
            const opt = document.createElement('option');
            opt.value = opt.textContent = d;
            selector.appendChild(opt);
        });
    }

    function drawChart(svgId, points, labelMode) {
      const svg = $(svgId);
      if(!svg) return;
      if (!points || !points.length) {
        svg.innerHTML = '<text x="20" y="40" fill="#9bb2c8">尚無歷史資料</text>';
        return;
      }
      
      const pRect = svg.parentElement.getBoundingClientRect();
      const width = pRect.width > 0 ? pRect.width : 760;
      const height = 300, pad = 40;
      
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      
      const vals = points.map((p) => p.waiting_count);
      const min = Math.min.apply(null, vals);
      const max = Math.max.apply(null, vals);
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
        
        const fullTime = p.fetched_at.substring(0, 19).replace('T', ' ');
        const tooltipHtml = `${fullTime}<br><span style='color:${color}; font-size:16px; font-weight:bold;'>${p.waiting_count} 人</span>`;
        
        html += `<circle cx="${x}" cy="${y}" r="4" fill="${color}" style="pointer-events:none;"></circle>`;
        html += `<circle cx="${x}" cy="${y}" r="14" fill="transparent" class="hover-target" data-info="${tooltipHtml}" style="cursor:pointer;"></circle>`;
      });
      
      svg.innerHTML = html;
    }

    function renderHourlyChart() {
        const dateSel = $('date-selector');
        if(!dateSel) return;
        const date = dateSel.value;
        if(!date) return;
        const dayPoints = historyData.filter(p => p.fetched_at.startsWith(date));
        drawChart('hourly-chart', dayPoints, 'time');
    }

    function renderRelatedInfo(text) {
        const target = $('related-info-text');
        if(!target) return;
        let safeText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        safeText = safeText.replace(/(三、缺額遞補原則.*?)/g, '<br><strong style="color:var(--accent-2); font-size:16px;">$1</strong>');
        safeText = safeText.replace(/(四、不列入備取名單情形.*?)/g, '<br><strong style="color:var(--accent-2); font-size:16px;">$1</strong>');
        safeText = safeText.replace(/\n/g, '<br>');
        target.innerHTML = `<div style="white-space: pre-wrap;">${safeText}</div>`;
    }

    window.onload = () => {
        try {
            const dataEl = document.getElementById('dashboard-data');
            if(!dataEl) throw new Error("找不到資料區塊 (dashboard-data)");
            payload = JSON.parse(dataEl.textContent);
            allData = payload.all_data || {};
            orgIds = Object.keys(allData);
            if(orgIds.length === 0) throw new Error("無可用中心資料");
            
            orgIds.forEach(id => {
                const dist = allData[id].snapshot.org.distdesc || '其他地區';
                if (!orgsByDistrict[dist]) orgsByDistrict[dist] = [];
                orgsByDistrict[dist].push(id);
            });
            const districts = Object.keys(orgsByDistrict);
            const savedOrgId = localStorage.getItem(STORAGE_KEY);
            let initialDist = districts[0];
            if (savedOrgId && orgIds.includes(savedOrgId)) {
                initialDist = allData[savedOrgId].snapshot.org.distdesc || '其他地區';
                currentOrgId = savedOrgId;
            } else {
                currentOrgId = orgsByDistrict[initialDist][0];
            }
            const distSelector = $('district-selector');
            const orgSelector = $('global-org-selector');
            if(distSelector) {
                districts.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d; opt.textContent = d;
                    distSelector.appendChild(opt);
                });
                distSelector.value = initialDist;
            }
            function populateOrgSelector(dist) {
                if(!orgSelector) return;
                orgSelector.innerHTML = '';
                orgsByDistrict[dist].forEach(id => {
                    const orgInfo = allData[id].snapshot.org;
                    const opt = document.createElement('option');
                    opt.value = id; opt.textContent = `${orgInfo.orgshort || id} (${id})`;
                    orgSelector.appendChild(opt);
                });
            }
            if(distSelector && orgSelector) {
                populateOrgSelector(initialDist);
                orgSelector.value = currentOrgId;
                distSelector.addEventListener('change', (e) => {
                    const newDist = e.target.value;
                    populateOrgSelector(newDist);
                    currentOrgId = orgSelector.value;
                    renderCurrentOrg();
                });
                orgSelector.addEventListener('change', (e) => {
                    currentOrgId = e.target.value;
                    renderCurrentOrg();
                });
            }
            const favBtn = $('btn-favorite');
            if (favBtn) {
                favBtn.addEventListener('click', () => {
                    const currentSaved = localStorage.getItem(STORAGE_KEY);
                    if (currentSaved === currentOrgId) localStorage.removeItem(STORAGE_KEY);
                    else localStorage.setItem(STORAGE_KEY, currentOrgId);
                    renderCurrentOrg();
                });
            }
            
            const statsBtn = $('btn-city-stats');
            const closeStatsBtn = $('btn-close-stats');
            const statsOverlay = $('stats-overlay');
            if (statsBtn) statsBtn.addEventListener('click', toggleStatsPanel);
            if (closeStatsBtn) closeStatsBtn.addEventListener('click', toggleStatsPanel);
            if (statsOverlay) statsOverlay.addEventListener('click', toggleStatsPanel);

            const tooltip = $('chart-tooltip');
            document.addEventListener('mouseover', (e) => {
                if (e.target && e.target.classList && e.target.classList.contains('hover-target')) {
                    tooltip.innerHTML = e.target.getAttribute('data-info');
                    tooltip.style.opacity = '1';
                }
            });
            document.addEventListener('mousemove', (e) => {
                if (tooltip.style.opacity === '1') {
                    tooltip.style.left = (e.pageX + 15) + 'px';
                    tooltip.style.top = (e.pageY + 15) + 'px';
                }
            });
            document.addEventListener('mouseout', (e) => {
                if (e.target && e.target.classList && e.target.classList.contains('hover-target')) {
                    tooltip.style.opacity = '0';
                }
            });
            
            let resizeTimer;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(() => {
                    drawChart('history-chart', getDailyHistory().slice(-7), 'date');
                    drawChart('monthly-chart', getDailyHistory().slice(-30), 'date');
                    renderHourlyChart();
                }, 200);
            });

            const sortKeyEl = $('all-list-sort-key');
            if(sortKeyEl) sortKeyEl.addEventListener('change', renderAllListTable);
            const sortDirEl = $('all-list-sort-direction');
            if(sortDirEl) sortDirEl.addEventListener('change', renderAllListTable);
            const dateSelEl = $('date-selector');
            if(dateSelEl) dateSelEl.addEventListener('change', renderHourlyChart);
            const stableToggleEl = $('toggle-stable');
            if(stableToggleEl) stableToggleEl.addEventListener('change', updateStableVisibility);
            document.querySelectorAll('.tab-btn').forEach((button) => {
              button.addEventListener('click', () => {
                const tab = button.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.toggle('active', btn === button));
                document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
                const tp = $('tab-' + tab);
                if(tp) tp.classList.add('active');
                if (tab === 'hourly-detail') {
                    drawChart('monthly-chart', getDailyHistory().slice(-30), 'date');
                    renderHourlyChart();
                }
              });
            });
            renderCurrentOrg();
        } catch(err) {
            console.error("初始化失敗:", err);
            const titleEl = $('main-title');
            if(titleEl) titleEl.textContent = "⚠️ 系統初始化失敗，請檢查資料";
        }
    };
  </script>
</body>
</html>"""

    return (html_template
            .replace("__SAFE_TITLE__", safe_title)
            .replace("__DATA_JSON__", data_json))