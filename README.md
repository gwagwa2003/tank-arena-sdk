# 坦克競技場 SDK（Tank Arena SDK）

[坦克競技場](https://arena.gwagwa.de5.net) 是一個 **1 對 1 坦克 AI 對戰**的天梯：你訓練一個神經網路來開坦克，上傳到網站，
伺服器拿你的模型跟其他玩家的模型對打，用像 LoL 的段位（鐵牌 → 大師）排名，打的時候可以看直播、打完可以看重播。

這個 SDK 讓你在自己的電腦上：

- 跑**跟伺服器完全相同**的遊戲（同樣的規則、物理、地圖）；
- 拿到伺服器餵給模型的**同一份 91 維觀測**，訓練出來的模型上線後表現一致；
- 用現成的規則 bot 當對手或老師，幾分鐘就訓練出第一個模型；
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

# 2. 訓練第一個模型（模仿 ChaserBot，CPU 幾分鐘）
python examples/02_behavior_cloning.py --loadout gunner:shield

# 3. 本機跑一遍伺服器的檢查
python -m tank_arena check model.pt

# 4. 到網站註冊帳號，在「我的」頁選同樣的配裝（速射＋護盾），然後上傳、排位
python -m tank_arena --user 你的帳號 upload model.pt
python -m tank_arena --user 你的帳號 queue --wait        # 打的時候可以在網站的「直播」頁看
```

`python -m tank_arena play` 的對手可以是 bot 名稱（`idle`、`turret`、`chaser`）或 `model.pt` 檔，
所以也能拿自己的新舊模型互打：`python -m tank_arena play new.pt old.pt --games 20`。

## 遊戲在玩什麼

- 800 × 800 的場地，兩張地圖（十字堡壘、城區巷戰），最多 60 秒（1,200 步，每秒 20 步）。
- 每一步你的模型輸出 5 個動作：移動、車身轉向、砲塔轉向、開火、技能。
- 選一種**機體**（標準、重裝、輕裝、速射、長砲、攻城、散彈）和一個**模組**（護盾、隱身、透視、煙霧、過載、抗毒、雷達）。
- 毒圈會縮小，圈外持續扣血。活下來的贏；都陣亡撐比較久的贏；時間到剩血多的贏。
- 模型**看不到完整的場面**：只看得到視線內、沒被牆或煙霧擋住的敵人，和身邊的子彈。

完整規則見 [docs/rules.md](docs/rules.md)。

## SDK 裡有什麼

| 模組 | 用途 |
|---|---|
| `tank_arena.engine` | 遊戲本體：`play()` 打一整局，`Game` 一步一步打（訓練用） |
| `tank_arena.observation` | `observation(state)`：模型每一步看到的 91 個數字（[說明](docs/observation.md)） |
| `tank_arena.env` | `TankEnv`：reset / step 介面的訓練環境（跟 Gymnasium 相同的形式），可自訂獎勵 |
| `tank_arena.bots` | 規則 bot：`IdleBot`（不動）、`TurretBot`（定點射擊）、`ChaserBot`（完整的簡單戰術） |
| `tank_arena.agent` | `ModelPolicy`：照伺服器的方式執行 model.pt；`FrameStack`：伺服器的疊幀方式 |
| `tank_arena.export` | `export_model()`：把 PyTorch 網路匯出成網站接受的 model.pt（[格式](docs/model-format.md)） |
| `tank_arena.check` | `check_model()`：伺服器的上傳檢查（格式、輸出、速度、試打一局） |
| `tank_arena.client` | `ArenaClient`：網站 API（註冊、登入、配裝、上傳、排位、天梯、重播）（[API](docs/api.md)） |
| `tank_arena.viewer` | `replay_html()`：把重播存成可以直接打開的 HTML |

## 範例

| 檔案 | 內容 |
|---|---|
| [examples/01_rule_bot.py](examples/01_rule_bot.py) | 自己寫一個規則 bot，跟 ChaserBot 對打、看重播，熟悉遊戲 |
| [examples/02_behavior_cloning.py](examples/02_behavior_cloning.py) | 模仿學習＋DAgger：從規則 bot 學出第一個模型，匯出、檢查、評估 |
| [examples/03_upload_and_queue.py](examples/03_upload_and_queue.py) | 用 Python 登入、設定配裝、上傳、排位、等結果 |

想再變強：用 `TankEnv` 做強化學習（PPO 等）微調、拿自己的舊模型當對手自我對戰、改用 LSTM（`export_model(..., recurrent=True)`）。

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
