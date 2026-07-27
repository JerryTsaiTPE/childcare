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

    # --- 過濾無效歷史紀錄，並保留首尾端點以支撐連續圖表繪製 ---
    for org_id, org_data in all_data.items():
        if "history" in org_data:
            history = org_data["history"]
            if history:
                # 1. 僅保留 changed 為 True (有變動) 的紀錄
                filtered_history = [item for item in history if item.get("changed", False)]
                
                # 2. 保留最起點，讓圖表知道起點端點
                if not filtered_history or filtered_history[0].get("fetched_at") != history[0].get("fetched_at"):
                    filtered_history.insert(0, history[0])
                    
                # 3. 保留最末點，讓圖表能連線到當下最新時刻
                if filtered_history[-1].get("fetched_at") != history[-1].get("fetched_at"):
                    filtered_history.append(history[-1])
                    
                org_data["history"] = filtered_history
    # -------------------------------------------------------------------------

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
    
    .dist-stats-table { width: 100%; border-collapse: collapse; margin-top: 10px; background: rgba(0,0,0,0.2); border-radius: 12px; overflow: hidden; table-layout: fixed; }
    .dist-stats-table th, .dist-stats-table td { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .dist-stats-table th { font-size: 12px; color: var(--muted); background: rgba(255,255,255,0.02); text-transform: uppercase; letter-spacing: 1px; }
    
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
    .panels.panels-single { grid-template-columns: 1fr; }
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
    .footer { color: var(--muted); font-size: 13px; margin-top: 16px; text-align: center; }
    
    @media (max-width: 980px) { .panels { grid-template-columns: 1fr; } }
    @media (max-width: 720px) { 
        .hero { flex-direction: column; align-items: flex-start; gap: 20px; } 
        .org-switch-wrapper { align-items: flex-start; width: 100%; } 
        .org-controls { justify-content: flex-start; width: 100%; } 
        .org-select { flex-grow: 1; width: auto; } 
    }
    
    /* 手機版 500px 以下的最佳化：長條圖兩層排版 */
    @media (max-width: 500px) {
        .bar-row { grid-template-columns: 1fr auto; gap: 4px; margin-bottom: 14px; }
        .bar-row > div:nth-child(1) { grid-column: 1; font-size: 13px; }
        .bar-row > div:nth-child(3) { grid-column: 2; font-size: 12px; }
        .bar-track { grid-column: 1 / -1; }
    }
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
      
      <div class="card" style="border: 1px solid var(--accent-2); background: rgba(142, 247, 194, 0.05);">
        <div class="metric" style="color: var(--accent-2); font-weight:bold; font-size: 14px;">🎉 近 48 小時遞補入托</div>
        <div id="latest-admission-info" style="font-size: 15px; line-height: 1.6; margin-top: 12px;">
          <span style="color:var(--muted)">載入中...</span>
        </div>
      </div>

      <div class="card">
        <div class="metric">公托中心總數</div>
        <div class="value" id="global-org-count">--</div>
      </div>
      <div class="card">
        <div class="metric">公托總核定名額 <span style="font-size:12px">(加總)</span></div>
        <div class="value" id="global-cap-count">--</div>
      </div>
      <div class="card" style="border: 1px solid var(--danger);">
        <div class="metric">目前排隊備取總人數 <span style="font-size:12px; color:var(--danger)">(已去除重複)</span></div>
        <div class="value" id="global-unique-waitlist">--</div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">※ 不計入重複登記：<br>「姓名 + 生日 + 報名身分別」完全相同者，視為同一幼兒，僅計算 1 人。</div>
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

  <div id="links-overlay" class="overlay"></div>
  <div id="links-panel" class="slide-panel">
    <div class="slide-panel-header">
      <h2>🔗 相關連結</h2>
      <button id="btn-close-links" class="close-btn" title="關閉">✖</button>
    </div>
    <div class="slide-panel-content">

      <div class="card" style="border: 1px solid var(--border); transition: 0.3s; cursor: pointer;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'" onclick="window.open('https://lovebaby.sw.ntpc.gov.tw/#/nursery-signup', '_blank')">
        <div style="color: var(--accent); font-weight:bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          🔗 115年度公托招生簡章 ↗
        </div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">報名日期115/7/1 - 115 7/8。</div>
      </div>

      <div class="card" style="border: 1px solid var(--border); transition: 0.3s; cursor: pointer;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'" onclick="window.open('https://jerrytsaitpe.github.io/childcare/calculator/', '_blank')">
        <div style="color: var(--accent); font-weight:bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          🧮 幼兒園招生日期計算機 ↗
        </div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">快速計算幼兒入學年齡與對應學年度，幫助家長提早規劃入學時程。</div>
      </div>

      <div class="card" style="border: 1px solid var(--border); transition: 0.3s; cursor: pointer;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'" onclick="window.open('https://kiang.github.io/preschools', '_blank')">
        <div style="color: var(--accent); font-weight:bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          🔗 台灣幼兒園地圖 ↗
        </div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">快速查詢幼兒園資訊/平均月費。</div>
      </div>

      <div class="card" style="border: 1px solid var(--border); transition: 0.3s; cursor: pointer;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'" onclick="window.open('https://www.kindyinfo.com', '_blank')">
        <div style="color: var(--accent); font-weight:bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          🔗 幼園通 ↗
        </div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">快速查詢幼兒園資訊/裁罰紀錄。</div>
      </div>
      
      <div class="card" style="border: 1px solid var(--border); transition: 0.3s; cursor: pointer; margin-top: 14px;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'" id="btn-open-name-stats">
        <div style="color: var(--accent); font-weight:bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          🔤 姓名統計 (第三個字) ↗
        </div>
        <div class="sub" style="margin-top: 8px; font-size: 13px;">分析全區備取名單中，名字第三個字的出現次數與佔比。</div>
      </div>
    </div>
  </div>

  <div id="name-stats-overlay" class="overlay"></div>
  <div id="name-stats-panel" class="slide-panel">
    <div class="slide-panel-header">
      <h2>🔤 姓名第三字統計</h2>
      <button id="btn-close-name-stats" class="close-btn" title="關閉">✖</button>
    </div>
    <div class="slide-panel-content">
      <input type="text" id="name-char-search" class="select-input" style="width:100%; margin-bottom: 10px; font-size:16px; padding:12px;" placeholder="輸入一個字搜尋 (如：明)..." maxlength="1">
      <div id="name-stats-results"></div>
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
          <select id="academic-year-selector" class="org-select" style="display:none; max-width: 150px;" title="備取名單年度"><option>待選擇年度</option></select>
          <button id="btn-favorite" class="fav-btn" title="將目前中心設為預設"><span class="star">☆</span> 設為預設</button>
          
          <button id="btn-city-stats" class="fav-btn" style="padding: 10px 14px; border-radius: 8px;" title="查看全新北市統計">📊 全區統計</button>
          
          <button id="btn-links" class="fav-btn" style="padding: 10px 14px; border-radius: 8px;" title="相關連結">🔗 相關連結</button>
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
        <div class="card"><div class="metric">遞補入托</div><div class="value small" id="admitted-count"></div><div class="sub" id="admitted-summary"></div></div>
        <div class="card"><div class="metric">自行取消候補</div><div class="value small" id="withdrawn-count"></div><div class="sub" id="withdrawn-summary"></div></div>
        <div class="card"><div class="metric">屆齡取消</div><div class="value small" id="age-out-count"></div><div class="sub" id="age-out-summary"></div></div>
        <div class="card"><div class="metric">近一次影響人數</div><div class="value small" id="moved-count"></div><div class="sub" id="moved-summary"></div></div>
      </section>

            <section class="panels">
        <div class="panel chart-box">
          <h2>📈 近一週備取總數</h2>
          <svg id="history-chart" width="100%" height="300"></svg>
        </div>
        <div class="panel">
          <h2>全名單備取身分比例</h2>
          <div class="sub" style="margin:-6px 0 12px; font-size:13px;">依目前選定年度的全數備取名單計算，切換年度時會同步更新。</div>
          <div id="top20-bars"></div>
        </div>
      </section>

      <section class="panels panels-single">
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
              <h3>遞補入托</h3>
              <div class="chips" id="admitted-chips"></div>
            </div>
            <div class="list-block">
              <h3>屆齡取消 (滿兩歲)</h3>
              <div class="chips" id="age-out-chips"></div>
            </div>
            <div class="list-block">
              <h3>自行取消候補</h3>
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
        <h2>📅 近一個月走勢</h2>
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
        <h2>所有名單 <span class="sub" style="font-size:14px; font-weight:normal; margin-left:10px; color:var(--danger);">※ 紅色字體代表該幼兒距滿兩歲不到 14 天，即將被系統自動取消候補。</span></h2>
        
        <div class="sub" style="margin-bottom: 15px; color: var(--muted); border-left: 3px solid var(--accent); padding-left: 10px; font-size: 13px;">
          如果 [同步候補] 超過一家公托，是去識別化名單容易導致同名同生日(或是雙胞台姓名近似)，依規定一人同時只能登記備取兩間。
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
          <button id="admission-history-filter" class="fav-btn" type="button">顯示所有遞補入托</button>
        </div>
        <div class="sub" id="admission-history-note" style="display:none; margin-bottom:12px;">遞補入托資訊會永久保留，不受一般歷史紀錄清理或筆數上限影響。</div>
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
    let permanentAdmissionData = [];
    let showPermanentAdmissions = false;
    let nameStatsData = []; 
    let totalValidNameCount = 0;
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

    // 💡 跨中心搜尋幼兒是否依然存活於「同步候補」名單中
    function isChildStillWaitingElsewhere(childName, childBirthday, childCategory, excludeOrgId) {
        for (let i = 0; i < orgIds.length; i++) {
            const oid = orgIds[i];
            if (oid !== excludeOrgId) {
                const otherSnapshot = allData[oid].snapshot;
                if (otherSnapshot && otherSnapshot.entries) {
                    const found = otherSnapshot.entries.find(e => 
                        e.encname === childName && 
                        e.cbirthday === childBirthday && 
                        e.displaydesc === childCategory
                    );
                    if (found) return true;
                }
            }
        }
        return false;
    }

    function historicalChildKey(child) {
        return `${child.name || child.encname || ''}|${child.birthday || child.cbirthday || ''}|${child.category || child.displaydesc || ''}`;
    }

    function sameChildAcrossYears(removed, added) {
        return historicalChildKey(removed) === historicalChildKey(added)
            && String(removed.apyear || '') !== String(added.apyear || '');
    }

    function classifyHistoricalRemovalStatuses(item, orgId) {
        const removed = item.removed_details || [];
        const enrollDelta = Object.prototype.hasOwnProperty.call(item, 'enroll_delta') ? item.enroll_delta : 0;
        const candidates = removed.filter((rd) => !isStrictlyTwo(rd.birthday, item.fetched_at)
            && !isChildStillWaitingElsewhere(rd.name, rd.birthday, rd.category, orgId))
            .sort((a, b) => a.previous_index - b.previous_index);
        const statuses = new Map();

        removed.forEach((rd) => {
            let status;
            if (isStrictlyTwo(rd.birthday, item.fetched_at)) {
                status = '屆齡取消';
            } else if (enrollDelta <= 0) {
                status = '自行取消';
            } else {
                const rank = candidates.findIndex((candidate) => candidate.previous_index === rd.previous_index);
                const admitted = rank !== -1 && (candidates.length <= enrollDelta || rank < enrollDelta - 1 || rank === candidates.length - 1);
                status = admitted ? '遞補入托' : '自行取消';
            }
            statuses.set(historicalChildKey(rd), { removed: rd, status });
        });
        return statuses;
    }

    function classifyHistoricalAddedStatus(ad, removedStatusByKey) {
        const crossYearDuplicate = Array.from(removedStatusByKey.values()).some((record) =>
            record.status === '遞補入托' && sameChildAcrossYears(record.removed, ad));
        if (crossYearDuplicate) return '自行取消';
        return '新增候補';
    }

    function formatHistoricalStatus(status) {
        if (status === '遞補入托') return '<span style="color:var(--ok)">遞補入托</span>';
        if (status === '屆齡取消') return '<span style="color:var(--danger)">屆齡取消</span>';
        return status;
    }

    // --- 全區統計計算：結合跨中心連動與頭尾錄取防呆收斂法則 ---
    function calculateGlobalStats() {
        let totalCap = 0;
        let globalUniqueChildren = new Set();
        let districtUniqueMap = {}; 
        
        let globalLatestMs = 0;
        orgIds.forEach(id => {
            const snap = allData[id].snapshot;
            if(snap && snap.fetched_at) {
                globalLatestMs = Math.max(globalLatestMs, new Date(snap.fetched_at).getTime());
            }
        });
        const thresholdMs = globalLatestMs - (48 * 60 * 60 * 1000); 
        
        let recentAdmissions = [];

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
            
            const history = allData[id].history || [];
            history.forEach(item => {
                if (item.enroll_delta && item.enroll_delta > 0) {
                    const timeMs = new Date(item.fetched_at).getTime();
                    if (timeMs >= thresholdMs) {
                        let actualAdmittedCount = 0;
                        
                        if (item.removed_details && item.removed_details.length > 0) {
                            // 1. 抓出非屆齡且全網消失的純淨候選人
                            let pureAdmittedCandidates = [];
                            item.removed_details.forEach(rd => {
                                if (!isStrictlyTwo(rd.birthday, item.fetched_at)) {
                                    const stillWaiting = isChildStillWaitingElsewhere(rd.name, rd.birthday, rd.category, id);
                                    if (!stillWaiting) {
                                        pureAdmittedCandidates.push(rd);
                                    }
                                }
                            });
                            
                            // 2. 依原序號排序
                            pureAdmittedCandidates.sort((a, b) => a.previous_index - b.previous_index);
                            
                            // 3. 針對收斂後計算有效入托數量
                            let countValid = 0;
                            const enrollDelta = item.enroll_delta;
                            pureAdmittedCandidates.forEach((rd, idx) => {
                                if (pureAdmittedCandidates.length <= enrollDelta) {
                                    countValid++;
                                } else {
                                    // 吻合現場通知順序：取前 (N-1) 名與最後 1 名做為真正入托
                                    if (idx < enrollDelta - 1 || idx === pureAdmittedCandidates.length - 1) {
                                        countValid++;
                                    }
                                }
                            });
                            actualAdmittedCount = countValid;
                        }

                        if (actualAdmittedCount > 0) {
                            recentAdmissions.push({
                                timeMs: timeMs,
                                orgName: snap.org.orgshort || id,
                                count: actualAdmittedCount
                            });
                        }
                    }
                }
            });
        });
        
        recentAdmissions.sort((a, b) => b.timeMs - a.timeMs);

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
        
        const laEl = $('latest-admission-info');
        if (laEl) {
            if (recentAdmissions.length > 0) {
                let htmlStr = '';
                recentAdmissions.forEach(adm => {
                    const d = new Date(adm.timeMs);
                    const timeStr = `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                    
                    htmlStr += `
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <div>
                            <span style="color:var(--muted); font-size:13px; margin-right:8px;">${timeStr}</span>
                            <span style="font-weight:bold; color:#fff;">${adm.orgName}</span>
                        </div>
                        <div style="color:var(--ok); font-family:Consolas, monospace; font-weight:bold;">+${adm.count} 人</div>
                    </div>`;
                });
                laEl.innerHTML = htmlStr;
            } else {
                laEl.innerHTML = '<span style="color:var(--muted)">近 48 小時無入托紀錄</span>';
            }
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
    
    function toggleLinksPanel() {
        const linksPanel = $('links-panel');
        const linksOverlay = $('links-overlay');
        linksPanel.classList.toggle('active');
        linksOverlay.classList.toggle('active');
    }

    function toggleNameStatsPanel() {
        const panel = $('name-stats-panel');
        const overlay = $('name-stats-overlay');
        const isActive = panel.classList.contains('active');
        
        if (!isActive) {
            if (nameStatsData.length === 0) calculateNameStats();
            renderNameStats('');
            $('name-char-search').value = '';
        }
        
        panel.classList.toggle('active');
        overlay.classList.toggle('active');
    }

    function calculateNameStats() {
        let uniqueNames = new Map();
        
        orgIds.forEach(id => {
            const snap = allData[id].snapshot;
            if (snap && snap.entries) {
                snap.entries.forEach(entry => {
                    const key = `${entry.encname}|${entry.cbirthday}|${entry.displaydesc || ''}`;
                    if (!uniqueNames.has(key)) {
                        uniqueNames.set(key, entry.encname);
                    }
                });
            }
        });

        let charCounts = {};
        let totalValidChars = 0;
        const excludeChars = ['O', 'o', '0', '〇', '○', 'Ｏ', ' ', '　'];

        uniqueNames.forEach(name => {
            if (name && name.length >= 3) {
                const thirdChar = name.charAt(2);
                if (!excludeChars.includes(thirdChar)) {
                    charCounts[thirdChar] = (charCounts[thirdChar] || 0) + 1;
                    totalValidChars++;
                }
            }
        });

        totalValidNameCount = totalValidChars;

        nameStatsData = Object.keys(charCounts).map(char => {
            return {
                char: char,
                count: charCounts[char],
                pct: totalValidChars > 0 ? ((charCounts[char] / totalValidChars) * 100).toFixed(2) : 0
            };
        });

        nameStatsData.sort((a, b) => b.count - a.count);
    }

    function renderNameStats(filterChar) {
        const container = $('name-stats-results');
        if (!container) return;

        let filtered = nameStatsData;
        if (filterChar) {
            filtered = nameStatsData.filter(item => item.char === filterChar);
        }

        if (filtered.length === 0) {
            container.innerHTML = '<div style="color:var(--muted); padding: 10px; text-align:center;">找不到符合的字</div>';
            return;
        }

        let html = `<div style="margin-bottom: 12px; font-size: 14px; color: var(--muted); text-align: right;">統計基數：共 <span style="color:var(--text); font-weight:bold; font-family:Consolas, monospace;">${totalValidNameCount}</span> 人</div>`;
        
        html += '<table class="dist-stats-table" style="margin-top:0;"><thead><tr><th style="text-align:left;">第三字</th><th style="text-align:right;">人數</th><th style="text-align:right;">佔比</th></tr></thead><tbody>';
        filtered.forEach(item => {
            html += `<tr>
                <td style="font-weight:bold; color:var(--accent); font-size:18px;">${item.char}</td>
                <td style="text-align:right; font-family:Consolas, monospace; font-size:16px;">${item.count}</td>
                <td style="text-align:right; color:var(--muted); font-family:Consolas, monospace;">${item.pct}%</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    function getAcademicYears() {
        const byYear = snapshot && snapshot.entries_by_year;
        if (byYear && Object.keys(byYear).length) return Object.keys(byYear).sort((a, b) => Number(a) - Number(b));
        const entries = (snapshot && snapshot.entries) || [];
        return [...new Set(entries.map(entry => String(entry.apyear || '')).filter(Boolean))].sort((a, b) => Number(a) - Number(b));
    }

    function getSelectedAcademicYear() {
        const selector = $('academic-year-selector');
        return selector && selector.value ? selector.value : null;
    }

    function getEntriesForSelectedYear() {
        if (!snapshot) return [];
        const selectedYear = getSelectedAcademicYear();
        if (!selectedYear) return snapshot.entries || [];
        if (snapshot.entries_by_year && snapshot.entries_by_year[selectedYear]) return snapshot.entries_by_year[selectedYear];
        return (snapshot.entries || []).filter(entry => String(entry.apyear || '') === selectedYear);
    }

    function formatRank(index, apyear) {
        const years = getAcademicYears();
        const newestYear = years.length > 1 ? years[years.length - 1] : null;
        if (newestYear && String(apyear || '') === newestYear) return `${index}(新)`;
        return String(index);
    }

    function populateAcademicYearSelector() {
        const selector = $('academic-year-selector');
        if (!selector) return;
        const years = getAcademicYears();
        const previousSelection = selector.value;
        selector.innerHTML = '';
        if (years.length <= 1) {
            selector.style.display = 'none';
            return;
        }
        selector.style.display = '';
        years.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = `${year} 年度${year === years[years.length - 1] ? '（新）' : ''}`;
            selector.appendChild(option);
        });
        selector.value = years.includes(previousSelection) ? previousSelection : years[years.length - 1];
    }

    function formatChangeRank(index, apyear) {
        return formatRank(index, apyear);
    }

    function renderPermanentAdmissionTimeline() {
        const timeline = $('history-timeline');
        const note = $('admission-history-note');
        const button = $('admission-history-filter');
        if (!timeline) return;
        if (note) note.style.display = '';
        if (button) button.textContent = '返回一般歷史紀錄';
        timeline.innerHTML = '';

        const records = [].concat(permanentAdmissionData || []).reverse();
        if (!records.length) {
            timeline.innerHTML = '<div class="timeline-item" style="color: var(--muted); text-align: center;">尚無已保存的遞補入托紀錄</div>';
            return;
        }
        records.forEach((record) => {
            const card = document.createElement('div');
            card.className = 'timeline-item';
            const people = (record.admitted_details || []).map((person) => {
                const rank = formatChangeRank(person.previous_index, person.apyear);
                const age = getAgeString(person.birthday, record.fetched_at);
                return `<tr><td>${rank}</td><td>${person.name || '—'}</td><td>${person.birthday || '—'}</td><td>${age}</td><td>${person.category || '—'}</td><td><span style="color:var(--ok)">${person.status || '遞補入托'}</span></td></tr>`;
            }).join('');
            const enrolled = record.prev_enroll != null && record.curr_enroll != null
                ? `入托數：${record.prev_enroll} → ${record.curr_enroll} 人`
                : `本次推定遞補：${record.admitted_count || 0} 人`;
            card.innerHTML = `
                <div class="timeline-meta"><div>${fmt.format(new Date(record.fetched_at))}</div><div style="color:var(--ok); font-weight:bold;">${enrolled}</div></div>
                <div class="table-wrap"><table class="panel-table" style="font-size:13px; border-left:3px solid var(--ok);"><thead><tr><th>原序號</th><th>兒童姓名</th><th>出生日期</th><th>當時歲數</th><th>身分別</th><th>狀態</th></tr></thead><tbody>${people}</tbody></table></div>`;
            timeline.appendChild(card);
        });
    }

    // --- 終極版單一中心判定：完美兼顧跨中心比對存活與電話連號放棄現場 ---
    function renderCurrentOrg() {
        try {
            const data = allData[currentOrgId];
            if (!data) throw new Error("找不到指定的中心資料");
            
            snapshot = data.snapshot;
            latest = data.latest_change || {};
            historyData = data.history || [];
            permanentAdmissionData = data.admissions || [];
            showPermanentAdmissions = false;
            const admissionFilterButton = $('admission-history-filter');
            const admissionHistoryNote = $('admission-history-note');
            if (admissionFilterButton) admissionFilterButton.textContent = '顯示所有遞補入托';
            if (admissionHistoryNote) admissionHistoryNote.style.display = 'none';

            latest.added_details = latest.added_details || [];
            latest.removed = latest.removed || [];
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
                    
                    let enrollDelta = matchingHistory.hasOwnProperty('enroll_delta') ? matchingHistory.enroll_delta : 0;
                    
                    // 1. 抓出非屆齡的潛在候選人
                    let potentialCandidates = [];
                    matchingHistory.removed_details.forEach(rd => {
                        if (isStrictlyTwo(rd.birthday, matchingHistory.fetched_at)) {
                            strictAgeOut.push(rd.previous_index);
                        } else {
                            potentialCandidates.push(rd);
                        }
                    });
                    
                    // 🌟 鐵律守門員：若官方當次增長數 <= 0，全部強制視為棄權
                    if (enrollDelta <= 0) {
                        potentialCandidates.forEach(rd => {
                            strictWithdrawn.push(rd.previous_index);
                        });
                    } else {
                        // 2. 進行「跨中心同步候補連動」過濾：被別家保留 = 鐵證棄權者
                        let pureAdmittedCandidates = [];
                        potentialCandidates.forEach(rd => {
                            const stillWaiting = isChildStillWaitingElsewhere(rd.name, rd.birthday, rd.category, currentOrgId);
                            if (stillWaiting) {
                                strictWithdrawn.push(rd.previous_index);
                            } else {
                                pureAdmittedCandidates.push(rd);
                            }
                        });
                        
                        // 3. 第三層收斂：依原序號由小到大排序
                        pureAdmittedCandidates.sort((a, b) => a.previous_index - b.previous_index);
                        
                        // 現場收斂規則：若全網消失者超出缺額數，取前 (N-1) 名與最後 1 名做為正式錄取
                        pureAdmittedCandidates.forEach((rd, idx) => {
                            if (pureAdmittedCandidates.length <= enrollDelta) {
                                strictAdmitted.push(rd.previous_index);
                            } else {
                                if (idx < enrollDelta - 1 || idx === pureAdmittedCandidates.length - 1) {
                                    strictAdmitted.push(rd.previous_index);
                                } else {
                                    strictWithdrawn.push(rd.previous_index);
                                }
                            }
                        });
                    }
                    
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
            
            populateAcademicYearSelector();
            const selectedEntries = getEntriesForSelectedYear();
            const wcEl = $('waiting-count');
            if (wcEl) wcEl.textContent = selectedEntries.length;
            
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
            if (rsEl) rsEl.textContent = latest.removed_previous_indexes.length ? '序號 ' + latest.removed.map(item => formatChangeRank(item.previous_index, item.apyear)).join('、') + changeText : '尚無紀錄';
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
                return `序號 ${formatChangeRank(idx, v.apyear)}`;
            });

            renderChips('removed-chips', latest.removed, '尚無紀錄', (v) => `序號 ${formatChangeRank(v.previous_index, v.apyear)}`);
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
                        movedTable.insertAdjacentHTML('beforeend', `<tr><td>${item.name}</td><td>${formatChangeRank(item.previous_index, item.apyear)}</td><td>${formatChangeRank(item.current_index, item.apyear)}</td><td class="${cls}">${item.delta}</td></tr>`);
                    });
                }
            }

            // 全名單備取身分比例（依選定年度變動）
            const top20Bars = $('top20-bars');
            if (top20Bars) {
                top20Bars.innerHTML = '';
                const counts = new Map();
                const entriesList = getEntriesForSelectedYear();
                entriesList.forEach((entry) => counts.set(entry.displaydesc, (counts.get(entry.displaydesc) || 0) + 1));
                const topCategoryTotal = Math.max(1, entriesList.length);
                const maxCount = Math.max(1, ...Array.from(counts.values(), (v) => v), 1);
                const sortedEntries = [];
                counts.forEach((v, k) => sortedEntries.push([k, v]));
                sortedEntries.sort((a, b) => b[1] - a[1]);
                if (!sortedEntries.length) {
                  top20Bars.innerHTML = '<div class="sub">此年度尚無名單資料</div>';
                } else {
                  sortedEntries.forEach((pair) => {
                    const label = pair[0] || '未分類';
                    const count = pair[1];
                    const pct = Math.round((count / topCategoryTotal) * 1000) / 10;
                    const widthPct = (count / maxCount) * 100;
                    top20Bars.insertAdjacentHTML('beforeend', `<div class="bar-row"><div>${label}</div><div class="bar-track"><div class="bar-fill" style="width:${widthPct}%"></div></div><div>${count} 人 / ${pct}%</div></div>`);
                  });
                }
            }

            renderAllListTable();

            // 💡 歷史紀錄明細表完整對齊跨中心過濾、前端頭尾保留演算法與手機橫向滑動
            const timeline = $('history-timeline');
            if (timeline) {
                timeline.innerHTML = '';
                
                const visibleHistory = historyData.filter(item => item.changed);
                
                if (!visibleHistory.length) {
                  timeline.innerHTML = '<div class="timeline-item" style="color: var(--muted); text-align: center;">尚無變動紀錄</div>';
                } else {
                  const revHistory = [].concat(visibleHistory).reverse();
                  revHistory.forEach((item) => {
                    const card = document.createElement('div');
                    card.className = 'timeline-item';
                    card.dataset.changeKind = item.change_kind || 'stable';
                    
                    let detailsHtml = '';
                    const removedStatusByKey = classifyHistoricalRemovalStatuses(item, currentOrgId);
                    if (item.added_details && item.added_details.length > 0) {
                        // 💡 加上 class="table-wrap" 確保手機上可以橫向滑動
                        detailsHtml += '<div class="table-wrap" style="margin-top:10px; margin-bottom:15px;"><table class="panel-table" style="font-size:13px; border-left: 3px solid var(--accent);"><thead><tr><th>新序號</th><th>兒童姓名</th><th>目前歲數</th><th>身分別</th><th>狀態</th><th style="color:var(--accent)">同步候補(目前)</th></tr></thead><tbody>';
                        item.added_details.forEach(ad => {
                            const age = getAgeString(ad.birthday || ad.cbirthday, item.fetched_at);
                            const categoryStr = ad.category || ad.displaydesc || '—';
                            const name = ad.name || ad.encname || '未知';
                            const idx = ad.current_index || ad.index || '?';
                            
                            let syncOrgs = [];
                            orgIds.forEach(oid => {
                                if (oid !== currentOrgId) {
                                    const otherSnapshot = allData[oid].snapshot;
                                    if (otherSnapshot && otherSnapshot.entries) {
                                        const searchBirthday = ad.birthday || ad.cbirthday;
                                        const found = otherSnapshot.entries.find(e => e.encname === name && e.cbirthday === searchBirthday && e.displaydesc === categoryStr);
                                        if (found) {
                                            syncOrgs.push(`${otherSnapshot.org.orgshort}(${found.index})`);
                                        }
                                    }
                                }
                            });
                            const syncText = syncOrgs.length > 0 ? syncOrgs.join(', ') : '—';
                            const addedStatus = classifyHistoricalAddedStatus(ad, removedStatusByKey);
                            
                            detailsHtml += `<tr><td>${formatChangeRank(idx, ad.apyear)}</td><td>${name}</td><td>${age}</td><td>${categoryStr}</td><td>${formatHistoricalStatus(addedStatus)}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`;
                        });
                        detailsHtml += '</tbody></table></div>';
                    }

                    if (item.removed_details && item.removed_details.length > 0) {
                        // 💡 加上 class="table-wrap" 確保手機上可以橫向滑動
                        detailsHtml += '<div class="table-wrap" style="margin-top:10px;"><table class="panel-table" style="font-size:13px;"><thead><tr><th>原序號</th><th>兒童姓名</th><th>當時歲數</th><th>身分別</th><th>狀態</th><th style="color:var(--accent)">同步候補(目前)</th></tr></thead><tbody>';
                        
                        item.removed_details.forEach(rd => {
                            const age = getAgeString(rd.birthday, item.fetched_at);
                            const type = formatHistoricalStatus(removedStatusByKey.get(historicalChildKey(rd))?.status || '自行取消');
                            
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
                            detailsHtml += `<tr><td>${formatChangeRank(rd.previous_index, rd.apyear)}</td><td>${rd.name}</td><td>${age}</td><td>${categoryStr}</td><td>${type}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`;
                        });
                        detailsHtml += '</tbody></table></div>';
                    }

                    let enrollDeltaHtml = '';
                    if (item.hasOwnProperty('enroll_delta') && item.enroll_delta !== 0) {
                        let deltaColor = item.enroll_delta > 0 ? 'var(--ok)' : 'var(--danger)';
                        if (item.hasOwnProperty('prev_enroll') && item.hasOwnProperty('curr_enroll')) {
                            enrollDeltaHtml = `<div style="color:${deltaColor}; font-weight:bold; border-left: 2px solid ${deltaColor}; padding-left: 8px; margin-left: 4px;">入托數：${item.prev_enroll} → ${item.curr_enroll} 人</div>`;
                        } else {
                            let deltaSign = item.enroll_delta > 0 ? '+' : '';
                            enrollDeltaHtml = `<div style="color:${deltaColor}; font-weight:bold; border-left: 2px solid ${deltaColor}; padding-left: 8px; margin-left: 4px;">入托變化：${deltaSign}${item.enroll_delta} 人</div>`;
                        }
                    }

                    // 舊歷史資料可能含「排序變動，只顯示第一個代表」；改由 highlight_shift 統一顯示
                    const linesArray = (item.summary_lines || ['名單無變動']).filter((line) => {
                        const text = String(line || '');
                        return !text.includes('排序變動，只顯示第一個代表') && !text.includes('只顯示第一個代表性變動');
                    });
                    const lines = (linesArray.length ? linesArray : []).map((line) => `<li>${line}</li>`).join('');
                    let highlight = item.highlight_shift ? `<div class="timeline-highlight">排序變動：${formatChangeRank(item.highlight_shift.previous_index, item.highlight_shift.apyear)} → ${formatChangeRank(item.highlight_shift.current_index, item.highlight_shift.apyear)}（${item.highlight_shift.name}）</div>` : '';
                    card.innerHTML = `
                        <div class="timeline-meta">
                            <div>${fmt.format(new Date(item.fetched_at))}</div>
                            <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
                                <div style="color:var(--accent-2)">當下候補總數：${item.waiting_count} 人</div>
                                ${enrollDeltaHtml}
                            </div>
                        </div>
                        <ul class="timeline-lines">${lines}</ul>
                        ${highlight}${detailsHtml}
                    `;
                    timeline.appendChild(card);
                  });
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
      const rows = sortEntries(getEntriesForSelectedYear(), keyEl.value, dirEl.value);
      target.innerHTML = '';
      rows.forEach((e) => {
        const ageStr = getAgeString(e.cbirthday, snapshot.fetched_at);
        const daysOld = getDaysOld(e.cbirthday, snapshot.fetched_at);
        const className = daysOld >= 716 ? ' class="aging-out"' : ''; 
        const syncText = (e.sync_list && e.sync_list.length > 0) ? e.sync_list.join(', ') : '—';
        target.insertAdjacentHTML('beforeend', `<tr${className}><td>${formatRank(e.index, e.apyear)}</td><td>${e.encname}</td><td>${e.cbirthday}</td><td>${ageStr}</td><td>${e.displaydesc}</td><td style="color:var(--accent-2)">${syncText}</td></tr>`);
      });
    }

    function getTrendPoint(point) {
        const counts = point.waiting_count_by_year || {};
        const fetchedDate = String(point.fetched_at || '').slice(0, 10);
        const match = fetchedDate.match(/^(\d{4})-(\d{2})-/);
        if (match && Object.keys(counts).length) {
            const gregorianYear = Number(match[1]);
            const month = Number(match[2]);
            const expectedYear = String(gregorianYear - 1911 - (month < 8 ? 1 : 0));
            if (Object.prototype.hasOwnProperty.call(counts, expectedYear)) {
                return { waiting_count: counts[expectedYear], academic_year: expectedYear };
            }
            const oldestYear = Object.keys(counts).sort((a, b) => Number(a) - Number(b))[0];
            return { waiting_count: counts[oldestYear], academic_year: oldestYear };
        }
        return {
            waiting_count: point.trend_waiting_count ?? point.waiting_count,
            academic_year: point.trend_academic_year || null
        };
    }

    function getTrendWaitingCount(point) {
        return getTrendPoint(point).waiting_count;
    }

    function getTrendAcademicYear(point) {
        return getTrendPoint(point).academic_year;
    }

    function getDailyHistory() {
        if (!historyData || historyData.length === 0) return [];
        const firstDateStr = historyData[0].fetched_at.split('T')[0];
        const lastDateStr = historyData[historyData.length - 1].fetched_at.split('T')[0];
        
        let curr = new Date(firstDateStr + 'T12:00:00');
        let end = new Date(lastDateStr + 'T12:00:00');
        const vals = [];
        
        while (curr <= end) {
            const yyyy = curr.getFullYear();
            const mm = String(curr.getMonth() + 1).padStart(2, '0');
            const dd = String(curr.getDate()).padStart(2, '0');
            const dStr = `${yyyy}-${mm}-${dd}`;
            
            const targetTime = `${dStr}T23:59:59`;
            let currentPoint = historyData[0];
            let currentCount = getTrendWaitingCount(currentPoint);
            for (let j = 0; j < historyData.length; j++) {
                if (historyData[j].fetched_at <= targetTime) {
                    currentPoint = historyData[j];
                    currentCount = getTrendWaitingCount(currentPoint);
                } else {
                    break;
                }
            }
            
            vals.push({
                fetched_at: `${dStr}T23:59:59`,
                waiting_count: currentCount,
                trend_academic_year: getTrendAcademicYear(currentPoint)
            });
            
            curr.setDate(curr.getDate() + 1);
        }
        return vals;
    }

    function initDateSelector() {
        const selector = $('date-selector');
        if(!selector) return;
        selector.innerHTML = '';
        
        const daily = getDailyHistory();
        const uniqueDates = daily.map(p => p.fetched_at.split('T')[0]);
        uniqueDates.reverse().forEach(d => {
            const opt = document.createElement('option');
            opt.value = opt.textContent = d;
            selector.appendChild(opt);
        });
    }
    
    function renderHourlyChart() {
        const dateSel = $('date-selector');
        if(!dateSel) return;
        const date = dateSel.value;
        if(!date) return;
        
        const dayPoints = [];
        for (let i = 0; i <= 23; i++) {
            const hh = String(i).padStart(2, '0');
            const targetTime = `${date}T${hh}:59:59`;
            
            let currentPoint = historyData.length > 0 ? historyData[0] : null;
            let currentCount = currentPoint ? getTrendWaitingCount(currentPoint) : 0;
            for (let j = 0; j < historyData.length; j++) {
                if (historyData[j].fetched_at <= targetTime) {
                    currentPoint = historyData[j];
                    currentCount = getTrendWaitingCount(currentPoint);
                } else {
                    break; 
                }
            }
            
            dayPoints.push({
                fetched_at: `${date}T${hh}:00:00`,
                waiting_count: currentCount,
                trend_academic_year: currentPoint ? getTrendAcademicYear(currentPoint) : null
            });
        }
        drawChart('hourly-chart', dayPoints, 'time');
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
        const trendYearText = p.trend_academic_year ? `<br><span style='color:#9bb2c8;'>歷史學年度：${p.trend_academic_year}</span>` : '';
        const tooltipHtml = `${fullTime}${trendYearText}<br><span style='color:${color}; font-size:16px; font-weight:bold;'>${p.waiting_count} 人</span>`;
        
        html += `<circle cx="${x}" cy="${y}" r="4" fill="${color}" style="pointer-events:none;"></circle>`;
        html += `<circle cx="${x}" cy="${y}" r="14" fill="transparent" class="hover-target" data-info="${tooltipHtml}" style="cursor:pointer;"></circle>`;
      });
      
      svg.innerHTML = html;
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
            // 分區下拉預設順序：跟 org_ids.txt 一致，板橋區固定第一個
            const preferredDistrictOrder = ['板橋區','土城區','新莊區','中和區','永和區','新店區','三峽區','樹林區','蘆洲區','三重區','五股區','淡水區','八里區','林口區','汐止區','泰山區','三芝區','金山區','瑞芳區','深坑區','鶯歌區'];
            const districts = Object.keys(orgsByDistrict).sort((a, b) => {
                const ia = preferredDistrictOrder.indexOf(a);
                const ib = preferredDistrictOrder.indexOf(b);
                if (ia === -1 && ib === -1) return a.localeCompare(b, 'zh-Hant');
                if (ia === -1) return 1;
                if (ib === -1) return -1;
                return ia - ib;
            });
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
            
            const linksBtn = $('btn-links');
            const closeLinksBtn = $('btn-close-links');
            const linksOverlay = $('links-overlay');
            if (linksBtn) linksBtn.addEventListener('click', toggleLinksPanel);
            if (closeLinksBtn) closeLinksBtn.addEventListener('click', toggleLinksPanel);
            if (linksOverlay) linksOverlay.addEventListener('click', toggleLinksPanel);

            const openNameStatsBtn = $('btn-open-name-stats');
            const closeNameStatsBtn = $('btn-close-name-stats');
            const nameStatsOverlay = $('name-stats-overlay');
            const nameCharSearch = $('name-char-search');

            if (openNameStatsBtn) {
                openNameStatsBtn.addEventListener('click', () => {
                    toggleLinksPanel(); 
                    toggleNameStatsPanel(); 
                });
            }
            if (closeNameStatsBtn) closeNameStatsBtn.addEventListener('click', toggleNameStatsPanel);
            if (nameStatsOverlay) nameStatsOverlay.addEventListener('click', toggleNameStatsPanel);
            
            if (nameCharSearch) {
                nameCharSearch.addEventListener('input', (e) => {
                    renderNameStats(e.target.value.trim());
                });
            }

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

            const academicYearSelector = $('academic-year-selector');
            if (academicYearSelector) academicYearSelector.addEventListener('change', renderCurrentOrg);
            const sortKeyEl = $('all-list-sort-key');
            if(sortKeyEl) sortKeyEl.addEventListener('change', renderAllListTable);
            const sortDirEl = $('all-list-sort-direction');
            if(sortDirEl) sortDirEl.addEventListener('change', renderAllListTable);
            const dateSelEl = $('date-selector');
            if(dateSelEl) dateSelEl.addEventListener('change', renderHourlyChart);
            const admissionFilterButton = $('admission-history-filter');
            if (admissionFilterButton) {
                admissionFilterButton.addEventListener('click', () => {
                    showPermanentAdmissions = !showPermanentAdmissions;
                    if (showPermanentAdmissions) renderPermanentAdmissionTimeline();
                    else renderCurrentOrg();
                });
            }
            
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