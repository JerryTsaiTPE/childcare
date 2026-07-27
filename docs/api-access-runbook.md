# LoveBaby API 存取限制與獨立出口 Runbook

## 先釐清目前狀態

- `2026-07-27` 從本機測試 `GET /webapi/Org/GetPublicNpsOrgList`，回應為 `HTTP 200`，所以本機目前使用的公開出口 IP 並未被限制。
- 先前在 Server 取得的是通用 `HTTP 403` HTML 拒絕頁。這能證明請求被入口層拒絕，但**不能單靠 403 證明一定是 IP 封鎖**；也可能是 WAF 規則、來源頻率、請求型態或暫時性防護。
- 更新程式已採低頻模式（中心請求間隔）與 403/429 融斷冷卻。看到 `data/api_backoff.json` 時，請先尊重其中的 `blocked_until`，不要重複重跑。

## 建議優先順序

1. 向新北市 LoveBaby／資料來源管理單位說明用途、更新頻率與固定出口 IP，請求確認流量限制或 IP allowlist。這是最穩定且合規的方案。
2. 將「抓 API + 產生 index.html」移至一台專用 collector VM，並使用固定公開 IP。該 VM 只跑 `scripts/update_dashboard.py`，再把 `index.html` 發布到目前 GitHub Pages／檔案同步位置。這是最容易維護的獨立出口架構。
3. 若來源方已同意使用另一個出口，使用本專案提供的**服務專屬 HTTP(S) CONNECT proxy**。只有本更新程式的 LoveBaby API 請求會走 proxy；Server 的網站、Git、其他服務仍照原本網路走。

不要使用輪換／匿名 proxy 來規避來源的封鎖或頻率限制。它通常不穩定、可能違反來源政策，也會讓問題更難追查。

## 本專案的服務專屬 Proxy 設定

`update_dashboard.py` 支援選用的環境變數：

```text
CHILDCARE_API_PROXY
```

可接受的格式：

```text
http://proxy.example.internal:3128
https://proxy.example.internal:8443
```

程式只會將此 proxy 套用到兩個 LoveBaby API 請求：

- `Org/GetPublicNpsOrgList`
- `NpsApply/GetStandbyList`

未設定時行為完全維持原本的直接連線。程式會在 log 中顯示 proxy 的 scheme、主機與連接埠，但不會輸出 URL 內的帳密。

### 手動測試（只影響這一次 cmd 視窗）

```bat
cd /d C:\Users\JerryPC\Desktop\childcare
set "CHILDCARE_API_PROXY=http://YOUR-APPROVED-PROXY:3128"
python scripts\update_dashboard.py
```

成功啟用時，起始 log 會出現：

```text
此更新服務將透過獨立 proxy 出口：https://... 或 http://...
```

### Windows 工作排程器／既有批次檔

使用 `scripts\run_update_via_proxy.bat` 作為排程入口。它以 `setlocal` 將已核准的
`CHILDCARE_API_PROXY` 只設定於該更新子程序，接著呼叫 `run_update_windows.bat`；不會改變整台 Server 的系統 proxy。

Task Scheduler 請設定：`If the task is already running: Do not start a new instance`。更新器另有 `data/update.lock` 作為第二道保護。

## 分批更新與可稽核紀錄

每輪會依 `scripts/org_ids.txt` 的中心順序輪巡（起點由 cursor 接續）：

```text
每批最多 10 間
批內 request 起始至少相隔 15 秒
每批完成後休息 120 秒
129 間約 56 分鐘（不含來源端延遲）
```

這是保守的上限，不是免於限流的保證。任一 `403` 或 `429` 會立即停止後續 API request，保留 cursor 與既有快取，並套用 `Retry-After` 與至少一小時本地冷卻，不能為了完成時程而重試或換出口。

所有執行資料均在未追蹤的 `data/`：

- `org_list_cache.json`：24 小時中心清單快取，避免每輪多一個 API request。
- `update_cursor.json`：最後一個驗證成功中心後的下一個 index；中斷後從此接續。
- `update.lock`：防止手動與排程重疊。
- `update_history.jsonl`：每個 run、batch、休息、request 起訖、耗時、HTTP 結果與 circuit 決策；同時帶 UTC 與台北時間戳。敏感欄位不寫入此檔。
- `api_backoff.json`：403/429 冷卻狀態與安全摘要。

日後只能依 `update_history.jsonl` 中正常、低頻輪次的結果分析趨勢；不可藉由提高速率、平行執行、清空冷卻或切換出口來探測限制。

建議使用以來源 IP allowlist 驗證的 proxy，避免把帳密寫入 `.bat`。如果供應商只能提供帳密，將 wrapper 批次檔與任何 credential 檔設為僅排程帳號可讀，且不要提交到 Git。

## VPN 的限制與可行作法

Windows 的 VPN 通常改變整台主機或整個目的網段的路由；它不是可靠的「僅讓單一 Python 程序走 VPN」機制。因此不建議直接在目前 Web Server 上啟用全域 VPN。

若必須使用獲授權的 VPN 出口，請改採其中一種隔離方式：

- **專用 Windows VM（建議）**：VPN 只連在 collector VM；該 VM 只執行更新器與發布動作。
- **容器／小型 VM + VPN gateway**：在隔離環境內執行更新器，並把該環境的 HTTP CONNECT proxy URL 提供給 `CHILDCARE_API_PROXY`。
- **遠端固定出口 proxy**：由已核准的 VM 建置並限制只允許這個 API service 使用；Server 不需自行連 VPN。

## 使用 Tailscale 作為服務專屬跳板

Tailscale 很適合把 Server 安全地連到另一台擁有不同公開出口 IP 的設備，但有兩種做法：

- **Exit node**：設定後通常會讓整台使用它的主機之所有預設網際網路流量改走跳板。適合短暫診斷，不適合本專案要求的「只有更新器改出口」。
- **Tailnet 內的 HTTP CONNECT proxy（建議）**：在另一台 Linux VM／NAS 上建立只聽 Tailscale IP 的 proxy，並在 Server 設定 `CHILDCARE_API_PROXY=http://<tailscale-ip>:<port>`。Python 更新器才會經由跳板，其他流量不變。

跳板設備的公開出口必須與 Server 不同；若兩台設備同在相同 NAT／WAN 下，對 LoveBaby 仍會看到相同 IP，沒有作用。**目前 NAS 與其內 VM 正是此情境，因此 NAS Exit Node、NAS proxy 或 NAS 上的 VPN 都不會單獨改變 VM 的直接出口；必須建立一個位於外部網路的 VPN／VPS egress gateway。** 跳板也應只允許 Server 的 Tailscale IP、只允許 `lovebaby.sw.ntpc.gov.tw:443`，不能公開暴露 proxy port 到 LAN 或 Internet。

### 服務專用 VPN／外部出口的建議架構

最穩定的作法是建立獨立的「API egress gateway」：使用一台位於外部網路、具固定公開 IP 的小型 VPS，或向 VPN 供應商申請專用靜態出口 IP。gateway 連入同一 Tailnet，並只提供受限 HTTP CONNECT proxy 給 Childcare Server；再由更新器設定 `CHILDCARE_API_PROXY` 使用它。

```text
NAS 內 Childcare VM ── Tailscale ── 外部 VPS / 專用 VPN Gateway ── LoveBaby API
       只讓更新器使用 proxy              固定、不同的公開出口 IP
```

不要在 NAS 或 Childcare VM 上直接啟用全域 VPN；那會改動整台設備的預設路由。若只能取得一般 VPN 帳號，請在獨立 Linux container／VM 中連 VPN 並在該隔離環境提供受限 proxy，而不是把 VPN 裝到現有 Server。

### Oracle Cloud Always Free 的適用性

Oracle Cloud Always Free 可作為**概念驗證或備援**的外部 gateway：以 Linux Ampere A1 VM 安裝 Tailscale 與 Squid/Tinyproxy，再建立並附掛 **Reserved Public IP**，即可讓 gateway 的出站來源保持固定。A1 是 ARM 架構，Ubuntu 的 Tailscale、Squid 與常用 Docker image 均需選擇 arm64 相容版本。

不建議將 Always Free 作為唯一的長期正式出口：Oracle 文件說明，若 Always Free instance 在 7 天期間 CPU、網路與（A1）記憶體使用率均偏低，instance 可能被回收；每日低頻 API 更新正可能符合此「idle」型態。若此服務不可中斷，應改用付費 VPS 或至少準備第二個 gateway。也必須使用 **Reserved** 而非 Ephemeral public IP，避免 VM 重新建立／更換時失去已 allowlist 的出口 IP。

設定前應先從跳板確認它的公開 IP 與 API 回應，並確認這個出口已被來源方允許使用。

## 403/429 發生時的處理

1. 保留 `data/api_backoff.json`，記錄其中的 `status_code`、`headers`、`response_body_preview` 和 `blocked_until`。
2. 等待冷卻到期；不得手動刪除或改寫冷卻檔來提早重試。若來源方明確提供新的規則或已核准設定變更，先保留原檔並記錄其時間，再依核准方案進行一次低頻輪次。
3. 原冷卻 state 應保留作為事件證據；程式只會在冷卻時間自然到期後恢復請求。
4. 若新的已核准出口仍回 403，將 JSON 記錄與測試時間交給 API 管理方，而不是提高頻率或切換輪換 IP。
