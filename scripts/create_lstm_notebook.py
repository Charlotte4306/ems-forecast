"""
create_lstm_notebook.py — Tạo notebooks/lstm_experiment.ipynb
(thử nghiệm huấn luyện & đánh giá các mô hình LSTM).
Notebook Queueing: xem scripts/create_queueing_notebook.py
"""
import os
import sys
from pathlib import Path
import nbformat as nbf

# Fix UTF-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Script nằm trong scripts/ → notebooks/ ở thư mục gốc dự án
NOTEBOOKS_DIR = str(Path(__file__).resolve().parents[1] / "notebooks")
os.makedirs(NOTEBOOKS_DIR, exist_ok=True)


# ==============================================================================
# NOTEBOOK 1: LSTM EXPERIMENT (Chuyên sâu huấn luyện & so sánh mô hình dự báo)
# ==============================================================================
def create_lstm_experiment_notebook():
    nb = nbf.v4.new_notebook()
    cells = []

    # ── Cell 0: Title markdown ───────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""# 🚑 EMS Demand Forecasting — LSTM Experiment
**Dự báo số lượt gọi xe cứu thương San Francisco theo từng giờ**

Notebook này tập trung vào pipeline Machine Learning & Deep Learning:
1. **Setup & Imports**: Cấu hình môi trường, nạp cấu hình và thiết bị (CPU/GPU).
2. **Naive Baseline**: Đánh giá mô hình cơ sở Lag-1 làm mốc so sánh tối thiểu.
3. **Experiment A (seq_len=24)**: Huấn luyện Vanilla LSTM với chuỗi quan sát 24 giờ (1 ngày).
4. **Experiment B (seq_len=168)**: Huấn luyện Vanilla LSTM với chuỗi quan sát 168 giờ (1 tuần).
5. **So sánh & Đánh giá**: Tổng hợp các chỉ số (MAE, RMSE, MAPE, R²) và vẽ biểu đồ so sánh.
6. **Bước tiếp theo**: Các kiến trúc nâng cao (BiLSTM, LSTM + Attention).

> 📌 **Lưu ý**: Để xem phần **Lý thuyết Hàng đợi & Hoạch định Đội xe** (biến dự báo $\\hat{\\lambda}(t)$ thành số xe cần $s(t)$), vui lòng mở notebook riêng: [`queueing_theory.ipynb`](queueing_theory.ipynb).
"""))

    # ── Cell 1: Setup & imports ──────────────────────────────────────────────
    cells.append(nbf.v4.new_code_cell("""\
from pathlib import Path
import sys, os
ROOT = Path.cwd().resolve()
if not (ROOT / "ems").is_dir():
    ROOT = ROOT.parent
if not (ROOT / "ems").is_dir():
    raise RuntimeError("Run from project root or notebooks directory")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams["figure.dpi"] = 120

from ems.models.lstm.config     import *
from ems.models.lstm.preprocess import build_dataloaders
from ems.models.lstm.model      import build_model
from ems.models.lstm.train      import train, load_checkpoint
from ems.models.lstm.evaluate   import (predict, compute_metrics, print_metrics,
                             plot_loss_curve, plot_predictions,
                             plot_comparison, naive_baseline, evaluate_all)

print(f"PyTorch version : {torch.__version__}")
print(f"Device          : {DEVICE}")
print(f"Output dir      : {OUTPUT_DIR}")
"""))

    # ── Cell 2: Naive baseline ───────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## 0. Naive Baseline (Đường cơ sở)
Mô hình đơn giản nhất: Dùng giá trị của giờ trước đó (lag-1) làm dự báo cho giờ tiếp theo:
$$\\hat{y}_t = y_{t-1}$$
Đây là mốc chuẩn tối thiểu mà bất kỳ mô hình Deep Learning nào cũng phải vượt qua."""))
    cells.append(nbf.v4.new_code_cell("""\
# Load raw y_test để tính baseline
import pandas as pd
from ems.models.lstm.config import DATA_DIR, TARGET_COL

y_test_raw = pd.read_csv(os.path.join(DATA_DIR, "y_test.csv"))[TARGET_COL].values
baseline_metrics = naive_baseline(y_test_raw)
print_metrics(baseline_metrics, run_name="Naive Lag-1 Baseline")
"""))

    # ── Cell 3: Experiment 1 — seq_len=24 ───────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## 1. Experiment A — Vanilla LSTM, seq_len=24 (1 ngày)
Sử dụng chu kỳ 24 giờ quá khứ để dự báo nhu cầu giờ tiếp theo."""))
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
# 1.3 Train model
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
    cells.append(nbf.v4.new_markdown_cell("""## 2. Experiment B — Vanilla LSTM, seq_len=168 (1 tuần = 7 × 24h)
Chuỗi quan sát dài hơn cho phép mô hình học được cả chu kỳ theo ngày trong tuần (ví dụ: Thứ Bảy/Chủ Nhật thường có lưu lượng cuộc gọi khác ngày thường).
> ⚠️ *seq_len=168 tiêu tốn nhiều bộ nhớ hơn, batch_size được giảm xuống 32.*"""))
    cells.append(nbf.v4.new_code_cell("""\
SEQ_LEN = 168
RUN_NAME = f"vanilla_seq{SEQ_LEN}"

# 2.1 Build DataLoaders
train_dl_168, val_dl_168, test_dl_168, feat_scaler, tgt_scaler = build_dataloaders(
    seq_len=SEQ_LEN, batch_size=32, verbose=True
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
    cells.append(nbf.v4.new_markdown_cell("## 3. So sánh kết quả các mô hình"))
    cells.append(nbf.v4.new_code_cell("""\
# Tổng hợp tất cả kết quả
results = {
    "Naive Lag-1":  baseline_metrics,
    "LSTM seq=24":  metrics_24,
    "LSTM seq=168": metrics_168,
}

# Print bảng so sánh
print(f"{'Model':<20} {'MAE':>8} {'RMSE':>8} {'MAPE%':>8} {'R2':>8}")
print("─" * 56)
for name, m in results.items():
    print(f"{name:<20} {m['MAE']:>8.3f} {m['RMSE']:>8.3f} "
          f"{m['MAPE (%)']:>8.2f} {m['R\\u00b2']:>8.4f}")

# Bar chart so sánh
fig = plot_comparison(results)
plt.show()
"""))

    # ── Cell 6: Next steps ───────────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## 4. Bước tiếp theo: Cải tiến Kiến trúc
Các tùy chọn mở rộng mô hình có thể thử nghiệm tiếp theo:

### 1. Stacked Bidirectional LSTM (`stacked_bi`)
```python
model_bi = build_model("stacked_bi", n_features=N_FEATURES, hidden_size=128, num_layers=2, dropout=0.3)
history_bi = train(model_bi, train_dl_24, val_dl_24, run_name="stacked_bi_seq24")
y_true_bi, y_pred_bi, metrics_bi = evaluate_all(model_bi, test_dl_24, tgt_scaler, "stacked_bi_seq24", history_bi)
```

### 2. LSTM kết hợp Cơ chế Attention (`attention`)
```python
model_att = build_model("attention", n_features=N_FEATURES, hidden_size=128, num_layers=2, dropout=0.2)
history_att = train(model_att, train_dl_24, val_dl_24, run_name="attention_seq24")
y_true_att, y_pred_att, metrics_att = evaluate_all(model_att, test_dl_24, tgt_scaler, "attention_seq24", history_att)
```

---
👉 **Chuyển sang bước tiếp theo trong quy trình**: Mở notebook [`queueing_theory.ipynb`](queueing_theory.ipynb) để áp dụng Lý thuyết Hàng đợi chuyển kết quả dự báo $\\hat{\\lambda}(t)$ thành số lượng xe cứu thương cần thiết $s(t)$ cho từng giờ!
"""))

    nb.cells = cells
    out_path = os.path.join(NOTEBOOKS_DIR, "lstm_experiment.ipynb")
    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"[OK] Notebook saved: {out_path}")


if __name__ == "__main__":
    create_lstm_experiment_notebook()
    # Notebook Queueing được tạo riêng bởi scripts/create_queueing_notebook.py
