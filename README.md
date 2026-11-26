# 坦克競技場 SDK（Tank Arena SDK）

[坦克競技場](https://arena.gwagwa.de5.net) 是一個 **1 對 1 坦克 AI 對戰**的天梯：你訓練一個神經網路來開坦克，上傳到網站，
伺服器拿你的模型跟其他玩家的模型對打，用像 LoL 的段位（鐵牌 → 大師）排名，打的時候可以看直播、打完可以看重播。

這個 SDK 讓你在自己的電腦上：

- 跑**跟伺服器完全相同**的遊戲（同樣的規則、物理、地圖）；
- **拿到伺服器餵給模型的同一份 118 維觀測**（同時相容舊版 91 維模型），訓練出來的模型上線後表現一致；
- 內建幾個基礎 bot，方便在本機測試、對打與錄製重播；
- 匯出成網站接受的 `model.pt`，先在本機跑一遍伺服器的檢查，再上傳、排位。

## 安裝

需要 Python 3.10 以上。

```bash
git clone https://github.com/gwagwa2003/tank-arena-sdk
cd tank-arena-sdk
pip install -e ".[torch]"        # 只想跑遊戲、不訓練模型的話：pip install -e .
```

## 五分鐘上手

```bash
# 1. 看看遊戲：兩個內建 bot 對打，存成重播，用瀏覽器打開 replay.html
python -m tank_arena play chaser turret --games 5 --html replay.html

# 2. 匯出一個最簡模型範例（確認模型格式與推論介面）
python examples/02_minimal_mlp.py

# 3. 本機跑一遍伺服器的檢查
python -m tank_arena check model.pt

# 4. 到網站註冊帳號，在「我的」頁選同樣的配裝（速射＋護盾），然後上傳、排位
python -m tank_arena --user 你的帳號 upload model.pt
python -m tank_arena --user 你的帳號 queue --wait        # 打的時候可以在網站的「直播」頁看
```

`python -m tank_arena play` 的對手可以是 bot 名稱（`idle`、`turret`、`chaser`）或 `model.pt` 檔，
所以也能拿自己的新舊模型互打：`python -m tank_arena play new.pt old.pt --games 20`。

## 遊戲在玩什麼

- 800 × 800 的點對稱隨機戰場（含可破壞掩體、草叢與能量核心），最多 60 秒（1,200 步，每秒 20 步）。
- 慣性移動、方向裝甲（前甲 0.8×／側甲 1.0×／後甲 1.35×）與槍管熱量系統。
- 每一步你的模型輸出 5 個動作：移動、車身轉向、砲塔轉向、開火、技能。
- 選一種**機體**（速射、散彈、遊擊、狙擊）和一個**模組**（隱身、護盾、雷達、側閃、專注）。
- 毒圈會縮小，圈外持續扣血。活下來的贏；都陣亡撐比較久的贏；時間到剩血多的贏。
- 模型**看不到完整的場面**：只看得到視野錐內、沒被牆／草叢／隱身遮蔽的敵人，以及聲波與身邊子彈；需匯出為 TorchScript `model.pt` 上傳（詳見 [docs/model-format.md](docs/model-format.md)）。

完整規則見 [docs/rules.md](docs/rules.md)。

## SDK 裡有什麼

| 模組 | 用途 |
|---|---|
| `tank_arena.engine` | 遊戲本體：`play()` 打一整局，`Game` 一步一步打（訓練用） |
| `tank_arena.observation` | `observation(state)`：模型每一步看到的 118 個數字（[說明](docs/observation.md)） |
| `tank_arena.env` | `TankEnv`：reset / step 介面的訓練環境（跟 Gymnasium 相同的形式），可自訂獎勵 |
| `tank_arena.bots` | 基礎測試 bot：`IdleBot`（不動）、`TurretBot`（定點射擊）、`ChaserBot`（基礎移動射擊） |
| `tank_arena.agent` | `ModelPolicy`：照伺服器的方式執行 model.pt；`FrameStack`：伺服器的疊幀方式 |
| `tank_arena.export` | `export_model()`：把 PyTorch 網路匯出成網站接受的 model.pt（[格式](docs/model-format.md)） |
| `tank_arena.check` | `check_model()`：伺服器的上傳檢查（格式、輸出、速度、試打一局） |
| `tank_arena.client` | `ArenaClient`：網站 API（註冊、登入、配裝、上傳、排位、天梯、重播）（[API](docs/api.md)） |
| `tank_arena.viewer` | `replay_html()`：把重播存成可以直接打開的 HTML |

## 範例

| 檔案 | 內容 |
|---|---|
| [examples/01_rule_bot.py](examples/01_rule_bot.py) | 寫一個基礎規則 bot 與 `ChaserBot` 對打並輸出重播 HTML |
| [examples/02_minimal_mlp.py](examples/02_minimal_mlp.py) | 最簡前饋網路（MLP）匯出、通過安檢與本機試打範例 |
| [examples/03_minimal_recurrent.py](examples/03_minimal_recurrent.py) | 最簡循環網路（GRU / LSTM）匯出、通過安檢與本機試打範例 |
| [examples/04_upload_and_queue.py](examples/04_upload_and_queue.py) | 用 Python 登入、設定配裝、上傳、排位、等結果 |

## 給模型的小提醒

- **配裝要一致**：網站上選的機體和模組要跟訓練時一樣，觀測裡有些數字跟配裝有關。
- **速度有上限**：伺服器用單執行緒量推論時間，上限看 `GET /api/config` 的 `speed_limit_ms`（目前每步 p95 20 ms）。伺服器的 CPU 可能比你的電腦慢，請留餘裕。
- **檔案上限 10 MB**（以 `GET /api/config` 的 `max_model_mb` 為準）；伺服器只載入 TorchScript，不會執行你的 Python 程式。
- 規則 bot 只能在本機用，天梯上只有模型能打。

## 測試

```bash
pip install -e ".[dev]"
pytest -q
```

## 授權

MIT，見 [LICENSE](LICENSE)。
