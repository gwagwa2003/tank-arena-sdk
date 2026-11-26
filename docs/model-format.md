# 模型格式：model.pt

伺服器不限制神經網路內部架構（MLP、CNN、Transformer、LSTM、GRU 或自訂狀態網路皆可），僅驗證匯出的 TorchScript `model.pt` 是否符合統一介面、檔案大小上限與推論延遲（p95）。

伺服器同時相容兩種觀測格式：
- **`tank-arena-v3`**（最新預設）：118 維觀測，可搭配 `stack` 1–64 幀。
- **`tank-arena-v1`**（舊版相容）：91 維觀測（自動截取 118 維的前 91 維）。

用 SDK 匯出最簡單：

```python
from tank_arena.export import export_model

# 1. 非循環網路（例如 MLP / Transformer，疊 4 幀）
export_model(net, "model.pt", stack=4, mean=mean, std=std)

# 2. 有狀態 2 參數網路（例如 GRU / 自訂 buffer：forward(x, h) -> (logits, h)）
export_model(gru, "model.pt", recurrent=True, rnn="gru", hidden=128, layers=1, stack=2, mean=mean, std=std)

# 3. 有狀態 3 參數網路（例如 LSTM / Transformer KV-cache：forward(x, h, c) -> (logits, h, c)）
export_model(lstm, "model.pt", recurrent=True, rnn="lstm", hidden=128, layers=1, stack=1, mean=mean, std=std)
```

## forward 的規格

伺服器每一步呼叫統一的 TorchScript 介面：

```python
logits, h, c = model(x, h, c)
```

- `x`：`[1, obs_size × stack]`（`v3` 為 `118 × stack`，最新幀在最前面）
- `h`, `c`：`[layers, 1, hidden]`（`recurrent=false` 時為 `[1, 1, 1]`；若原本為 `forward(x, h)`，匯出包裝會自動原樣傳回 `c`）
- `logits`：`[1, 13]`，依序 3 + 3 + 3 + 2 + 2

## config.json

| 欄位 | 說明 |
|---|---|
| `format` | `"tank-arena-v3"`（118 維）或 `"tank-arena-v1"`（91 維） |
| `stack` | 1–64 幀（`v3` 與 `v1` 皆可） |
| `recurrent` | 是否攜帶狀態張量 `(h, c)`（`true` / `false`） |
| `rnn` / `arch` | 選填，架構名稱標籤（例如 `"lstm"`、`"gru"`、`"transformer"` 等） |
| `hidden`, `layers` | 狀態張量維度：`hidden` 1–4096、`layers` 1–128（且 `layers × hidden ≤ 131072`） |
| `sample` | 是否依 softmax 抽樣 |
| `mean`, `std` | 各 `obs_size` 個有限數字，`std > 0` |
