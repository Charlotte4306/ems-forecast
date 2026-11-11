import json
from pathlib import Path

def create_cell(cell_type, source, cell_id=None):
    c = {
        'cell_type': cell_type,
        'metadata': {},
        'source': [line + '\n' for line in source.strip().split('\n')]
    }
    if cell_id:
        c['id'] = cell_id
    if cell_type == 'code':
        c['execution_count'] = None
        c['outputs'] = []
    return c

cells = [
    create_cell('markdown', """# Thí Nghiệm LSTM: So Sánh 1-Hour Rolling vs 24-Hour Block
Dự báo nhu cầu cuộc gọi cấp cứu San Francisco (`call_count`) trên toàn bộ 6.796 giờ của tập Test năm 2026.
Notebook thực hiện huấn luyện và so sánh hai kịch bản nghiệp vụ:
- **1-Hour Rolling (Dự báo cuốn chiếu từng giờ):** Cập nhật dữ liệu quan sát sau mỗi giờ, dự báo 1 giờ tiếp theo ($t$). Phục vụ điều phối tác chiến thời gian thực (Intraday Dispatching).
- **24-Hour Block (Dự báo khối 24 giờ):** Đầu ngày dự báo một lần cho toàn bộ 24 giờ của ngày hôm sau ($t \\dots t+23$) mà không quan sát dữ liệu giữa chừng. Phục vụ lập lịch kíp trực (Day-ahead Rostering), đồng bộ chuẩn với mô hình SARIMAX.""", 'cell_0'),

    create_cell('code', """from pathlib import Path
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
from ems.models.lstm.preprocess import build_dataloaders, build_block_dataloaders
from ems.models.lstm.model      import build_model
from ems.models.lstm.train      import train, load_checkpoint
from ems.models.lstm.evaluate   import (predict, predict_24h_blocks, compute_metrics, print_metrics,
                             plot_loss_curve, plot_predictions,
                             plot_comparison, naive_baseline, evaluate_all)

print(f"PyTorch version : {torch.__version__}")
print(f"Device          : {DEVICE}")
print(f"Output dir      : {OUTPUT_DIR}")""", 'cell_1'),

    create_cell('markdown', """## 0. Naive Baseline (Lag-1)
Dùng giá trị của 1 giờ trước làm dự báo cho giờ hiện tại. Mốc cơ sở tối thiểu cần vượt qua.""", 'cell_2'),

    create_cell('code', """y_test_raw = pd.read_csv(os.path.join(DATA_DIR, "y_test.csv"))[TARGET_COL].values
baseline_metrics = naive_baseline(y_test_raw)
print_metrics(baseline_metrics, run_name="Naive Lag-1 Baseline")""", 'cell_3'),

    create_cell('markdown', """## 1. Mô Hình 1: LSTM 1-Hour Rolling (Dự Báo Từng Giờ)
- **Input:** 24 giờ lịch sử gần nhất ($[t-24, \\dots, t-1]$).
- **Output:** 1 giá trị dự báo cho giờ tiếp theo ($t$).
- **Giao thức:** Mỗi giờ nhận giá trị actual mới nhất để dự báo giờ kế tiếp.""", 'cell_4'),

    create_cell('code', """SEQ_LEN = 24
RUN_NAME_1H = "vanilla_1h_rolling"

# 1.1 Khởi tạo DataLoaders 1-Hour Rolling (đủ 6.796 giờ test)
train_dl_1h, val_dl_1h, test_dl_1h, feat_scaler_1h, tgt_scaler_1h = build_dataloaders(
    seq_len=SEQ_LEN, batch_size=BATCH_SIZE, verbose=True
)""", 'cell_5'),

    create_cell('code', """# 1.2 Khởi tạo mô hình 1-Hour Rolling (forecast_horizon=1)
model_1h = build_model(
    name="vanilla",
    n_features=N_FEATURES,
    hidden_size=HIDDEN_SIZE,
    num_layers=NUM_LAYERS,
    dropout=DROPOUT,
    forecast_horizon=1,
)
print(model_1h)
total_params_1h = sum(p.numel() for p in model_1h.parameters() if p.requires_grad)
print(f"\\nTrainable params (1-Hour Rolling): {total_params_1h:,}")""", 'cell_6'),

    create_cell('code', """# 1.3 Huấn luyện mô hình 1-Hour Rolling
history_1h = train(
    model=model_1h,
    train_dl=train_dl_1h,
    val_dl=val_dl_1h,
    run_name=RUN_NAME_1H,
    num_epochs=NUM_EPOCHS,
    lr=LEARNING_RATE,
)""", 'cell_7'),

    create_cell('code', """# 1.4 Đánh giá trên 6.796 giờ test
y_true_1h, y_pred_1h, metrics_1h = evaluate_all(
    model=model_1h,
    test_dl=test_dl_1h,
    tgt_scaler=tgt_scaler_1h,
    run_name=RUN_NAME_1H,
    history=history_1h,
    predict_fn=predict,
)
plt.show()""", 'cell_8'),

    create_cell('markdown', """## 2. Mô Hình 2: LSTM 24-Hour Block (Dự Báo Khối 24 Giờ Liên Tiếp)
- **Input:** 24 giờ lịch sử của ngày hôm trước.
- **Output:** Vector 24 giá trị dự báo cho toàn bộ 24 giờ ngày mai ($[t, t+1, \\dots, t+23]$).
- **Giao thức:** Đứng tại đầu ngày dự báo 1 lần cho cả ngày, không quan sát actual giữa ngày (chuẩn SARIMAX để xếp ca trực).""", 'cell_9'),

    create_cell('code', """HORIZON = 24
RUN_NAME_24B = "vanilla_24h_block"

# 2.1 Khởi tạo DataLoaders 24-Hour Block (284 blocks x 24h = đủ 6.796 giờ test)
train_dl_24b, val_dl_24b, test_dl_24b, feat_scaler_24b, tgt_scaler_24b = build_block_dataloaders(
    seq_len=SEQ_LEN, horizon=HORIZON, batch_size=BATCH_SIZE, verbose=True
)""", 'cell_10'),

    create_cell('code', """# 2.2 Khởi tạo mô hình 24-Hour Block (forecast_horizon=24)
model_24b = build_model(
    name="vanilla",
    n_features=N_FEATURES,
    hidden_size=HIDDEN_SIZE,
    num_layers=NUM_LAYERS,
    dropout=DROPOUT,
    forecast_horizon=HORIZON,
)
print(model_24b)
total_params_24b = sum(p.numel() for p in model_24b.parameters() if p.requires_grad)
print(f"\\nTrainable params (24-Hour Block): {total_params_24b:,}")""", 'cell_11'),

    create_cell('code', """# 2.3 Huấn luyện mô hình 24-Hour Block
history_24b = train(
    model=model_24b,
    train_dl=train_dl_24b,
    val_dl=val_dl_24b,
    run_name=RUN_NAME_24B,
    num_epochs=NUM_EPOCHS,
    lr=LEARNING_RATE,
)""", 'cell_12'),

    create_cell('code', """# 2.4 Đánh giá mô hình 24-Hour Block trên 6.796 giờ test
y_true_24b, y_pred_24b, metrics_24b = evaluate_all(
    model=model_24b,
    test_dl=test_dl_24b,
    tgt_scaler=tgt_scaler_24b,
    run_name=RUN_NAME_24B,
    history=history_24b,
    predict_fn=predict_24h_blocks,
    n_target_hours=6796,
)
plt.show()""", 'cell_13'),

    create_cell('markdown', """## 3. So Sánh Kết Quả & Phân Tích Chuyên Sâu
So sánh hiệu năng giữa 1-Hour Rolling (Real-time monitoring) và 24-Hour Block (Day-ahead planning), kèm tham chiếu mô hình SARIMAX và Prophet.""", 'cell_14'),

    create_cell('code', """# 3.1 Bảng tổng hợp so sánh các phương pháp trên 6.796 giờ test
results = {
    "Naive Lag-1":         baseline_metrics,
    "LSTM 1-Hour Rolling": metrics_1h,
    "LSTM 24-Hour Block":  metrics_24b,
}

# Đọc thêm kết quả tham chiếu của SARIMAX & Prophet từ artifacts
import json
try:
    with open(ROOT / "checkpoints/sarimax/metadata.json", encoding="utf-8") as f:
        sarimax_meta = json.load(f)
        s_m = dict(sarimax_meta["test_metrics"]["all_test"])
        if "R2" in s_m and "R²" not in s_m:
            s_m["R²"] = s_m["R2"]
        results["SARIMAX (24h Block)"] = s_m
except Exception:
    pass

try:
    with open(ROOT / "outputs/prophet/metrics.json", encoding="utf-8") as f:
        prophet_meta = json.load(f)
        p_m = dict(prophet_meta["test_metrics"]["all_test"]["prophet"])
        if "R2" in p_m and "R²" not in p_m:
            p_m["R²"] = p_m["R2"]
        results["Prophet (1h Rolling)"] = p_m
except Exception:
    pass

print(f"\\n{'='*72}")
print(f"{'MÔ HÌNH / GIAO THỨC':<26} {'MAE':>10} {'RMSE':>10} {'MAPE (%)':>12} {'R²':>10}")
print(f"{'='*72}")
for name, m in results.items():
    r2_val = m.get("R²", m.get("R2", None))
    r2_str = f"{r2_val:>10.4f}" if r2_val is not None else "       N/A"
    print(f"{name:<26} {m['MAE']:>10.4f} {m['RMSE']:>10.4f} {m['MAPE (%)']:>12.2f}% {r2_str}")
print(f"{'='*72}\\n")

# Reload hàm vẽ để nhận cập nhật mới nhất (nếu kernel chưa restart)
import importlib
import ems.models.lstm.evaluate as ev
importlib.reload(ev)
from ems.models.lstm.evaluate import plot_comparison

# Bar chart so sánh 4 metrics
fig_comp = plot_comparison(results)
plt.show()""", 'cell_15'),

    create_cell('code', """# 3.2 So sánh trực quan Timeline 1 tuần (168 giờ)
sample_hours = 168
start_h = 24 * 7  # Tuần thứ 2 của tập test
end_h   = start_h + sample_hours

plt.figure(figsize=(16, 5))
hours_axis = np.arange(sample_hours)
plt.plot(hours_axis, y_true_1h[start_h:end_h], label="Actual (Thực tế)", color="#58a6ff", linewidth=2.0)
plt.plot(hours_axis, y_pred_1h[start_h:end_h], label="LSTM 1-Hour Rolling", color="#3fb950", linestyle="--", linewidth=1.6)
plt.plot(hours_axis, y_pred_24b[start_h:end_h], label="LSTM 24-Hour Block", color="#f78166", linestyle="-.", linewidth=1.6)

for day in range(0, sample_hours + 1, 24):
    plt.axvline(day, color="#8b949e", linestyle=":", alpha=0.5)

plt.title("So Sánh Dự Báo 1 Tuần (168h): LSTM 1-Hour Rolling vs LSTM 24-Hour Block", fontsize=13, pad=10)
plt.xlabel("Giờ trong tuần (0h - 168h)", fontsize=11)
plt.ylabel("Số cuộc gọi cấp cứu (Calls/hour)", fontsize=11)
plt.legend(loc="upper right", framealpha=0.6)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "timeline_comparison_1h_vs_24h.png"), dpi=150)
plt.show()""", 'cell_16')
]

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {
            'display_name': 'Python 3',
            'language': 'python',
            'name': 'python3'
        },
        'language_info': {
            'codemirror_mode': {'name': 'ipython', 'version': 3},
            'file_extension': '.py',
            'mimetype': 'text/x-python',
            'name': 'python',
            'nbconvert_exporter': 'python',
            'pygments_lexer': 'ipython3',
            'version': '3.11.9'
        }
    },
    'nbformat': 4,
    'nbformat_minor': 5
}

with open('notebooks/lstm_experiment.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print('Updated notebooks/lstm_experiment.ipynb successfully with', len(cells), 'cells!')
