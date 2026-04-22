#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.request
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 定義專案路徑
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# 匯入自定義模組
from ntpc_childcare_dashboard.render import render_dashboard
from ntpc_childcare_dashboard.tracker import (
    build_change_record,
    diff_snapshots,
    make_history_entry,
    parse_standby_payload,
)

# API 與常數設定
API_STANDBY = 'https://lovebaby.sw.ntpc.gov.tw/webapi/NpsApply/GetStandbyList?orgid=Z0130'
API_ORGS = 'https://lovebaby.sw.ntpc.gov.tw/webapi/Org/GetPublicNpsOrgList'
ORG_ID = 'Z0130'
VALIDITY_TEXT = '有效期限至116/07/31'
RULE_TEXT = """三、缺額遞補原則：

因中心收托涉及各班人數、幼兒年齡發展、師生比及身分別等差異因素，因此如有缺額時，依下列原則遞補：

1.若為優先收托名額出缺時，優先收托對象優先於一般家庭，再依出缺年齡適齡遞補

2.若為一般收托名額出缺時，依出缺年齡於全數備取名單中適齡遞補"""

RELATED_INFO_TEXT = """相關說明：

一、備取序號：係指現行實際之備取順序（未分齡）

二、本表係依幼兒備取編號順序排列

備註：優先對象指

1.本府列冊之低收入戶及中低收入戶兒童。

2.具有本市特殊境遇家庭及弱勢兒童少年生活補助身分資格之兒童。

3.父母之一方為中重度身心障礙、服常備兵役（以徵兵者為限，不含後備役）、或處一年以上有期徒刑或受拘束人身自由之保安處分一年以上且執行中，致無法自行照顧家中未滿二歲兒童，而須送請托育人員照顧之兒童。

4.家庭有同胞兄弟姐妹三名以上之兒童。

5.原住民兒童。

6.父母雙方或單親一方為未成年。

三、缺額遞補原則：

因中心收托涉及各班人數、幼兒年齡發展、師生比及身分別等差異因素，因此如有缺額時，依下列原則遞補：

1.若為優先收托名額出缺時，優先收托對象優先於一般家庭，再依出缺年齡適齡遞補

2.若為一般收托名額出缺時，依出缺年齡於全數備取名單中適齡遞補

四、不列入備取名單情形：

幼兒已入托、家長自行取消備取或電話通知取消、年滿2歲已逾法定入托年齡、經簡訊或電話備取通知未回覆者。

五、114年7月報名期間結束後，自114年8月1日起開放候補登記，依其報名時間排序於114年7月備取抽籤順序之後，其備取名額有效期間至115年7月31日止。 ※建議於有效期間未被通知遞補入托且未滿兩歲者，皆應參與當年度7月備取登記，並請留意登記時間。

六、上個月入托 42 名。"""

# 檔案路徑設定
DATA_DIR = ROOT / 'data'
SNAPSHOT_DIR = DATA_DIR / 'snapshots'
LATEST_PATH = DATA_DIR / 'latest_snapshot.json'
CHANGES_PATH = DATA_DIR / 'changes.json'
HISTORY_PATH = DATA_DIR / 'history.json'
INDEX_PATH = ROOT / 'index.html'


def fetch_json(url: str) -> dict:
    """抓取 API 資料並處理 SSL 驗證與 User-Agent"""
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Referer': 'https://lovebaby.sw.ntpc.gov.tw/',
        },
    )
    # 建立不驗證 SSL 的環境以繞過政府網站憑證問題
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        return json.load(response)


def load_json(path: Path, default):
    """安全載入 JSON 檔案"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, payload) -> None:
    """存檔 JSON 並確保縮排與中文顯示正常"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def load_org_info() -> dict:
    """取得中心的基本資訊"""
    payload = fetch_json(API_ORGS)
    for item in payload.get('data') or []:
        if item.get('orgid') == ORG_ID:
            return item
    raise RuntimeError(f'找不到 orgid={ORG_ID} 的中心資料')


def trim_history(history: list[dict], limit: int = 1000) -> list[dict]:
    """將歷史紀錄上限提升至 1000 筆，供前端進行每日走勢分析"""
    if len(history) <= limit:
        return history
    return history[-limit:]


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 抓取遠端資料
    standby_payload = fetch_json(API_STANDBY)
    org_info = load_org_info()
    parsed = parse_standby_payload(standby_payload)
    
    # 2. 定義時區 (UTC+8 台北時間)
    tz_taipei = timezone(timedelta(hours=8))
    fetched_at = datetime.now(tz_taipei).isoformat(timespec='seconds')

    snapshot = {
        'org': org_info,
        'fetched_at': fetched_at,
        **parsed,
    }

    # 3. 處理快照比對與歷史紀錄
    previous_snapshot = load_json(LATEST_PATH, None)
    previous_entries = previous_snapshot.get('entries', []) if previous_snapshot else []
    
    # 比對新舊快照差異
    diff = diff_snapshots(previous_entries, snapshot['entries'])
    change_record = build_change_record(
        fetched_at=fetched_at,
        diff=diff,
        previous_count=(previous_snapshot or {}).get('waiting_count'),
        current_count=snapshot['waiting_count'],
    )

    # 更新歷史紀錄 (用於圖表走勢)
    history = load_json(HISTORY_PATH, [])
    history.append(make_history_entry(snapshot, change_record))
    history = trim_history(history)

    # 更新變動摘要紀錄
    changes = load_json(CHANGES_PATH, [])
    changes.append(change_record)
    changes = trim_history(changes, limit=500)

    # --- 核心邏輯修改：找出「最後一次有意義的變動」傳給前端總覽頁面 ---
    last_meaningful_change = change_record
    for c in reversed(changes):
        if c.get("changed"):
            last_meaningful_change = c
            break

    # 4. 呼叫渲染函數產生 HTML
    html = render_dashboard(
        snapshot=snapshot,
        latest_change=last_meaningful_change, # 傳入最後變動，確保總覽卡片不歸零
        history=history,
        rule_text=RULE_TEXT,
        validity_text=VALIDITY_TEXT,
        related_info_text=RELATED_INFO_TEXT,
    )

    # 5. 儲存結果
    # 檔名格式化處理 (避免 Windows 不支援冒號字元)
    stamp = fetched_at.replace(':', '-').replace('+08-00', '+08_00')
    
    save_json(SNAPSHOT_DIR / f'{stamp}.json', snapshot)
    save_json(LATEST_PATH, snapshot)
    save_json(HISTORY_PATH, history)
    save_json(CHANGES_PATH, changes)
    
    # 寫入最後的 HTML 檔案
    INDEX_PATH.write_text(html, encoding='utf-8')

    # 輸出狀態供 Log 查看
    print(json.dumps({
        'status': 'success',
        'waiting_count': snapshot['waiting_count'],
        'history_size': len(history),
        'fetched_at': fetched_at,
    }, ensure_ascii=False, indent=2))
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)