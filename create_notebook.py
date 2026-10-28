import os
import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

# ── Cell 0: Title markdown ───────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("""# 🚑 EMS Demand Forecasting — LSTM Experiment
**Dự báo số lượt gọi xe cứu thương San Francisco theo giờ**

Notebook này chạy toàn bộ pipeline:
1. Preprocessing & Sequence building (seq_len = 24 và 168)
2. Vanilla LSTM baseline
3. Evaluation & Comparison
"""))

# ── Cell 1: Setup & imports ──────────────────────────────────────────────
cells.append(nbf.v4.new_code_cell("""\
import sys, os
# Thêm root vào sys.path để import src.*
ROOT = os.path.abspath("..")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import torch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams["figure.dpi"] = 120

from src.config     import *
from src.preprocess import build_dataloaders
from src.model      import build_model
from src.train      import train, load_checkpoint
from src.evaluate   import (predict, compute_metrics, print_metrics,
                             plot_loss_curve, plot_predictions,
                             plot_comparison, naive_baseline, evaluate_all)

print(f"PyTorch version : {torch.__version__}")
print(f"Device          : {DEVICE}")
print(f"Output dir      : {OUTPUT_DIR}")
"""))

# ── Cell 2: Naive baseline ───────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## 0. Naive Baseline\nDùng giá trị giờ trước (lag-1) làm dự báo. Đây là mức tối thiểu model LSTM cần vượt qua."))
cells.append(nbf.v4.new_code_cell("""\
# Load raw y_test để tính baseline
import pandas as pd
from src.config import DATA_DIR, TARGET_COL

y_test_raw = pd.read_csv(os.path.join(DATA_DIR, "y_test.csv"))[TARGET_COL].values
baseline_metrics = naive_baseline(y_test_raw)
print_metrics(baseline_metrics, run_name="Naive Lag-1 Baseline")
"""))

# ── Cell 3: Experiment 1 — seq_len=24 ───────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("""## 1. Experiment A — Vanilla LSTM, seq_len=24 (1 ngày)"""))
cells.append(nbf.v4.new_code_cell("""\
SEQ_LEN = 24
RUN_NAME = f"vanilla_seq{SEQ_LEN}"

# 1.1 Build DataLoaders
train_dl_24, val_dl_24, test_dl_24, feat_scaler, tgt_scaler = build_dataloaders(
    seq_len=SEQ_LEN, batch_size=BATCH_SIZE, verbose=True
)
"""))

cells.append(nbf.v4.new_code_cell("""\
# 1.2 Build model
model_24 = build_model(
    name="vanilla",
    n_features=N_FEATURES,
    hidden_size=HIDDEN_SIZE,
    num_layers=NUM_LAYERS,
    dropout=DROPOUT,
)
print(model_24)
total_params = sum(p.numel() for p in model_24.parameters() if p.requires_grad)
print(f"\\nTotal trainable params: {total_params:,}")
"""))

cells.append(nbf.v4.new_code_cell("""\
# 1.3 Train
history_24 = train(
    model=model_24,
    train_dl=train_dl_24,
    val_dl=val_dl_24,
    run_name=RUN_NAME,
    num_epochs=NUM_EPOCHS,
    lr=LEARNING_RATE,
)
"""))

cells.append(nbf.v4.new_code_cell("""\
# 1.4 Evaluate on Test set
y_true_24, y_pred_24, metrics_24 = evaluate_all(
    model=model_24,
    test_dl=test_dl_24,
    tgt_scaler=tgt_scaler,
    run_name=RUN_NAME,
    history=history_24,
)
plt.show()
"""))

# ── Cell 4: Experiment 2 — seq_len=168 ──────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("""## 2. Experiment B — Vanilla LSTM, seq_len=168 (1 tuần)
> ⚠️ seq_len=168 dùng nhiều RAM hơn. Nếu bị OOM, giảm batch_size xuống 32.
"""))
cells.append(nbf.v4.new_code_cell("""\
SEQ_LEN = 168
RUN_NAME = f"vanilla_seq{SEQ_LEN}"

# 2.1 Build DataLoaders
train_dl_168, val_dl_168, test_dl_168, feat_scaler, tgt_scaler = build_dataloaders(
    seq_len=SEQ_LEN, batch_size=32, verbose=True   # batch_size nhỏ hơn cho seq dài
)
"""))

cells.append(nbf.v4.new_code_cell("""\
# 2.2 Build model (cùng kiến trúc)
model_168 = build_model(
    name="vanilla",
    n_features=N_FEATURES,
    hidden_size=HIDDEN_SIZE,
    num_layers=NUM_LAYERS,
    dropout=DROPOUT,
)
"""))

cells.append(nbf.v4.new_code_cell("""\
# 2.3 Train
history_168 = train(
    model=model_168,
    train_dl=train_dl_168,
    val_dl=val_dl_168,
    run_name=RUN_NAME,
    num_epochs=NUM_EPOCHS,
    lr=LEARNING_RATE,
)
"""))

cells.append(nbf.v4.new_code_cell("""\
# 2.4 Evaluate
y_true_168, y_pred_168, metrics_168 = evaluate_all(
    model=model_168,
    test_dl=test_dl_168,
    tgt_scaler=tgt_scaler,
    run_name=RUN_NAME,
    history=history_168,
)
plt.show()
"""))

# ── Cell 5: Comparison ───────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("## 3. So sánh kết quả"))
cells.append(nbf.v4.new_code_cell("""\
# Tổng hợp tất cả kết quả
results = {
    "Naive Lag-1":       baseline_metrics,
    "LSTM seq=24":       metrics_24,
    "LSTM seq=168":      metrics_168,
}

# Print bảng so sánh
print(f"{'Model':<20} {'MAE':>8} {'RMSE':>8} {'MAPE%':>8} {'R²':>8}")
print("─" * 56)
for name, m in results.items():
    print(f"{name:<20} {m['MAE']:>8.3f} {m['RMSE']:>8.3f} "
          f"{m['MAPE (%)']:>8.2f} {m['R²']:>8.4f}")

# Bar chart so sánh
fig = plot_comparison(results)
plt.show()
"""))

# ── Cell 6: Next steps ───────────────────────────────────────────────────
cells.append(nbf.v4.new_markdown_cell("""\
## 4. Bước tiếp theo

Nếu muốn cải thiện:

```python
# Option B — Stacked Bidirectional LSTM
model_bi = build_model("stacked_bi", n_features=N_FEATURES,
                        hidden_size=128, num_layers=2, dropout=0.3)
history_bi = train(model_bi, train_dl_24, val_dl_24, run_name="stacked_bi_seq24")

# Option C — LSTM + Attention
model_att = build_model("attention", n_features=N_FEATURES,
                         hidden_size=128, num_layers=2, dropout=0.2)
history_att = train(model_att, train_dl_24, val_dl_24, run_name="attention_seq24")
```

Thêm kết quả vào dict `results` rồi chạy lại `plot_comparison(results)` để so sánh.
"""))

nb.cells = cells

# Save
out_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "notebooks",
    "lstm_experiment.ipynb"
)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Notebook saved -> {out_path}")
