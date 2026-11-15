# 網站 API

`tank_arena.client.ArenaClient` 已經包好下面這些呼叫；這裡列出原始的 HTTP 介面，方便用其他語言串接。

- 網址：`https://arena.gwagwa.de5.net`
- 請求和回應都是 JSON（上傳除外）。登入後伺服器會設定 `arena_session` cookie，之後的請求帶著它即可。
- 錯誤時回傳 `{"error": "原因"}` 和對應的 HTTP 狀態碼。
- 每個 IP 有請求頻率限制，太快會收到 `429`，請不要高頻率輪詢。

## 帳號

| 方法 | 路徑 | 內容 |
|---|---|---|
| POST | `/api/register` | `{"student_id": 帳號, "key": 密碼, "tank_name": 坦克名}`，註冊並登入；名額滿了回 403 |
| POST | `/api/login` | `{"student_id": 帳號, "key": 密碼}` |
| POST | `/api/logout` | |
| POST | `/api/password` | `{"old": 舊密碼, "new": 新密碼}` |
| GET | `/api/me` | 自己的段位、配裝、上場模型、上傳紀錄、最近幾輪排位 |
| POST | `/api/loadout` | `{"chassis": 機體, "module": 模組, "tank_name": 坦克名}` |
| POST | `/api/sit-out` | `{"sit_out": true/false}`，休息（不排位、不會被配對）或回到天梯 |

帳號 3–32 個字元（英數字和 `_ . -`），密碼 6–128 個字元。

## 模型

| 方法 | 路徑 | 內容 |
|---|---|---|
| POST | `/api/upload` | multipart：`file`（model.pt）、`activate`（`true`＝上傳後直接上場）、`label`（自己看的名稱）。會等檢查完才回應：`{"id", "version", "status": "通過"/"不通過", "message", "summary", "active"}` |
| GET | `/api/models` | 自己的模型版本（保留最近 5 個） |
| POST | `/api/active` | `{"model_id": id}`，換上場模型 |
| POST | `/api/models/{id}/label` | `{"label": 名稱}` |
| DELETE | `/api/models/{id}` | 刪除版本 |

## 排位

| 方法 | 路徑 | 內容 |
|---|---|---|
| POST | `/api/queue` | 開始排位（一次一場） |
| DELETE | `/api/queue` | 取消 |

排位的進度和結果在 `GET /api/me` 的 `rounds`（`status`：排隊中、進行中、完成、取消）。

## 公開資料

| 方法 | 路徑 | 內容 |
|---|---|---|
| GET | `/api/config` | 網站設定：`speed_limit_ms`、`max_model_mb`、段位規則、機體和模組清單 |
| GET | `/api/leaderboard` | 天梯 |
| GET | `/api/players/{user_id}` | 個人頁數據 |
| GET | `/api/games?limit=&mine=&user_id=&season=&tier=` | 對戰列表 |
| GET | `/api/games/{id}/results` | 一場的詳細結果 |
| GET | `/api/replay/{id}` | 重播（gzip 壓縮的 JSON，見下方） |
| GET | `/api/live` | 正在打的對戰 |
| GET | `/api/live/{id}?since=N` | 一場直播從第 N 格開始的畫面 |

## 重播格式

```json
{"map": "fort", "walls": [[x, y, w, h], ...], "zone": [圓心x, 圓心y], "every": 2, "steps": 812,
 "frames": [[步數, 安全區半徑, [[x, y, 車身角, 砲塔角, 血量比例, 活著, 技能中, 護盾中], ...], [[子彈x, 子彈y, 射手], ...]], ...],
 "events": [[步數, "kill", 射手, 被擊殺者], [步數, "zone", null, 死者], ...]}
```

每 2 步存一格。`python -m tank_arena replay 遊戲ID` 會把它存成可以直接用瀏覽器打開的 HTML。
SDK 本機對戰的 `play(..., replay=True)` 也輸出同樣的格式。
