#!/usr/bin/env python3
import json
import sys
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
CACHE_FILE = DATA_DIR / 'info_cache.json'

# 💡 升級版：支援 [區域] 標籤與行內 #註解 的讀取邏輯
def get_target_orgs():
    org_file = ROOT / 'scripts' / 'org_ids.txt'
    if not org_file.exists():
        print(f"❌ 找不到中心名單檔：{org_file}")
        return []
    
    orgs = []
    with open(org_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 略過空行、全行註解、以及 [區域] 標籤
            if not line or line.startswith('#') or line.startswith('['):
                continue
            # 處理行內註解，例如 "Z0014 #淡水淡海"，只取 # 前面的部分
            org_id = line.split('#')[0].strip()
            if org_id:
                orgs.append(org_id)
    return orgs

def fetch_info_via_playwright(org_id: str) -> tuple[str, str]:
    print(f"   啟動 Playwright 爬取 {org_id} ...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://lovebaby.sw.ntpc.gov.tw/#/waiting-list/{org_id}"
            
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(2)
            full_page_text = page.evaluate("document.body.innerText")
            
            memo_text = "中心未提供相關說明"
            start_idx = full_page_text.find("相關說明：")
            if start_idx != -1:
                extracted = full_page_text[start_idx:]
                footer_idx = extracted.find("福利專區")
                if footer_idx != -1:
                    extracted = extracted[:footer_idx]
                memo_text = extracted.strip()

            date_match = re.search(r'有效期限至[^\d]*([0-9]{3,4}/[0-9]{1,2}/[0-9]{1,2})', full_page_text)
            validity_text = f"有效期限至 {date_match.group(1)}" if date_match else "請依各中心公告為主"

            browser.close()
            print(f"   ✅ 成功爬取 {org_id} 網頁資料！")
            return memo_text, validity_text
    except Exception as e:
        print(f"   ❌ 爬取失敗 ({e})。")
        return "自動爬取說明失敗，請手動前往網頁查看。", "無法取得期限"

def main():
    TARGET_ORGS = get_target_orgs()
    if not TARGET_ORGS:
        print("名單為空，終止執行。")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("====================================")
    print("🚀 開始執行重度爬蟲 (更新相關說明與期限)...")
    
    # 讀取舊的 Cache，避免某次爬取失敗導致全部洗白
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass

    for org_id in TARGET_ORGS:
        memo, val = fetch_info_via_playwright(org_id)
        cache[org_id] = {
            "related_info_text": memo,
            "validity_text": val,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        # 爬完一筆就存檔，安全第一
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')

    print("====================================")
    print(f"🎉 爬蟲更新完畢！資料已快取至 {CACHE_FILE.name}")

if __name__ == '__main__':
    main()