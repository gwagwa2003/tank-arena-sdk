# 模型格式：model.pt

伺服器只接受 **TorchScript** 模型，不會執行任何你上傳的 Python 程式。用 SDK 匯出最簡單：

```python
from tank_arena.export import export_model
export_model(net, "model.pt", stack=4, mean=mean, std=std)          # 非循環網路
export_model(lstm, "model.pt", recurrent=True, hidden=128, layers=1, mean=mean, std=std)   # LSTM
```

## forward 的規格

伺服器每一步呼叫：

```
logits, h, c = model(x, h, c)
```

| 參數 | 形狀 | 說明 |
|---|---|---|
| `x` | `[1, 91 × stack]` | 正規化、疊好的觀測（見 [observation.md](observation.md)） |
| `h`, `c` | `[layers, 1, hidden]` | LSTM 狀態，每局開始是 0；非循環模型是 `[1, 1, 1]` 的 0，原樣傳回即可 |
| `logits` | `[1, 13]` | 5 個動作頭的分數，依序 3 + 3 + 3 + 2 + 2（移動、車身、砲塔、開火、技能） |

伺服器對每個動作頭取最大值（`sample: false`），或依 softmax 抽樣（`sample: true`）。

`export_model` 會幫你包好：非循環網路只要寫 `forward(x) -> logits`，LSTM 寫 `forward(x, h, c) -> (logits, h, c)`。

## config.json

匯出時一起打包在 model.pt 裡：

| 欄位 | 說明 |
|---|---|
| `format` | 固定是 `"tank-arena-v1"` |
| `stack` | 疊幾幀，1–16；LSTM 必須是 1 |
| `recurrent` | 是不是 LSTM |
| `hidden`, `layers` | LSTM 的狀態大小（1–2048）和層數（1–4）；非循環模型填 1 |
| `sample` | 動作要不要抽樣 |
| `mean`, `std` | 各 91 個數，正規化用；`std` 必須大於 0 |

## 上傳檢查

上傳後伺服器馬上檢查，沒通過的檔案不會保留（原因只顯示一次）：

1. 檔案不超過 **20 MB**，是 TorchScript（zip 格式），`config.json` 符合上面的規格。
2. `forward` 回傳 `(logits, h, c)`，`logits` 形狀 `(1, 13)` 且是有限數字。
3. **推論速度**：在伺服器上以單執行緒量 400 步，p95 不能超過上限（目前的上限看 `GET /api/config` 的 `speed_limit_ms`）。
   伺服器的 CPU 可能比你的電腦慢不少，本機量的時間請留餘裕。
4. 用你的配裝跟規則 bot 試打一局，不能有任何一步出錯。

本機先跑一次：`python -m tank_arena check model.pt`（會向網站查詢目前的速度上限）。

## 配裝要一致

觀測裡的數字（例如射線長度的縮放、裝填比例、技能冷卻）跟機體和模組有關。
在網站「我的」頁選的配裝，要跟你訓練時用的一樣，模型才會發揮正常。
