"""
create_notebook.py — Tạo 2 Jupyter Notebooks độc lập:
1. notebooks/lstm_experiment.ipynb  : Thử nghiệm huấn luyện & đánh giá các mô hình LSTM
2. notebooks/queueing_theory.ipynb  : Lý thuyết Hàng đợi & Hoạch định số xe cứu thương
"""
import os
from pathlib import Path
import nbformat as nbf

# Fix UTF-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTEBOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notebooks")
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

# Save
out_path = os.path.join(
    str(Path(__file__).resolve().parents[1]),
    "notebooks",
    "lstm_experiment.ipynb"
)

print("Environment ready! Imports successful.")
"""))

    # ── Cell 2: Load Forecast Predictions ────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 1: Nạp Dữ liệu & Kết quả Dự báo $\\hat{\\lambda}(t)$
Notebook này tự động nạp mô hình LSTM đã huấn luyện (`vanilla_seq24`), thực hiện inference trên tập Test, và tạo mô hình cơ sở Naive Lag-1 để đối chiếu."""))
    cells.append(nbf.v4.new_code_cell("""\
# 1.1 Load DataLoaders & Scalers
train_dl, val_dl, test_dl, feat_scaler, tgt_scaler = build_dataloaders(
    seq_len=24, batch_size=BATCH_SIZE, verbose=False
)

# 1.2 Load checkpoint LSTM seq=24 đã huấn luyện
model_24 = build_model("vanilla", n_features=N_FEATURES,
                       hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS,
                       dropout=DROPOUT)
load_checkpoint(model_24, run_name="vanilla_seq24")

# 1.3 Dự báo trên Test set
y_true_24, y_pred_24 = predict(model_24, test_dl, tgt_scaler)
metrics_24 = compute_metrics(y_true_24, y_pred_24)
print_metrics(metrics_24, run_name="LSTM seq=24 Test Set")

# 1.4 Tạo Naive Baseline (Lag-1)
y_test_raw = pd.read_csv(os.path.join(DATA_DIR, "y_test.csv"))[TARGET_COL].values
y_pred_naive_full = np.roll(y_test_raw, 1)
y_pred_naive_full[0] = y_test_raw[0]

# Cắt độ dài Naive Baseline cho khớp với Test set của LSTM (do seq_len=24 mất 24 mẫu đầu)
n_test = len(y_pred_24)
y_pred_naive = y_pred_naive_full[-n_test:]

# Tập hợp vào dictionary các mô hình dự báo
y_pred_dict = {
    "Naive Lag-1":  y_pred_naive,
    "LSTM seq=24":  y_pred_24,
}

print(f"\\nĐã chuẩn bị dự báo cho {len(y_pred_dict)} mô hình trên {n_test:,} giờ kiểm thử.")
"""))

    # ── Cell 3: Estimate Service Parameters ──────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 2: Ước lượng Tham số Dịch vụ ($E[S]$ và $u$)
* **$E[S]$ (Thời gian bận trung bình của xe)**: Được tính từ thời điểm xe xuất phát, đến hiện trường, sơ cứu, đưa đến bệnh viện, bàn giao bệnh nhân và dọn dẹp xe để sẵn sàng ca tiếp theo.
* **$u$ (Số xe trung bình/cuộc gọi)**: Một số cuộc gọi nghiêm trọng (tai nạn giao thông nhiều nạn nhân, hỏa hoạn) cần điều động nhiều hơn 1 xe cứu thương.

> Trong thực tế, nếu có dữ liệu thô sự cố với cột `total_busy_sec` và `n_units_dispatched`, hàm `estimate_service_params(raw_df=...)` sẽ tính trực tiếp. Nếu không, hệ thống sử dụng chuẩn vận hành EMS San Francisco: $E[S] = 36$ phút ($0.60$ giờ) và $u = 1.35$ xe/cuộc gọi."""))
    cells.append(nbf.v4.new_code_cell("""\
params = estimate_service_params(
    raw_df=None,
    default_E_S_hr=0.60,   # 36 phút / ca cấp cứu
    default_u=1.35,         # xe / cuộc gọi
)

print("Tham số Lý thuyết Hàng đợi:")
print(f"  Thời gian bận trung bình E[S] : {params['E_S_sec']:.0f} giây  =  {params['E_S_hr']:.2f} giờ ({params['E_S_hr']*60:.0f} phút)")
print(f"  Số xe trung bình mỗi cuộc u   : {params['u']:.2f} xe / cuộc gọi")
print(f"  Nguồn tham số                 : {params['source']}")
"""))

    # ── Cell 4: Calculate Vehicles ───────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 3: Tính Tải Erlang $a(t)$ và Số Xe Cần $s(t)$ theo 3 Tiêu chí
Hàm `forecast_to_vehicles` sẽ tính toán đồng thời:
1. Tải $a(t) = \\hat{\\lambda}(t) \\times u \\times E[S]$
2. `s_rho80`: Số xe thỏa mãn $\\rho = a/s \\le 0.80$
3. `s_erlangB5pct`: Số xe tối thiểu thỏa mãn xác suất nghẽn Erlang B $B(s, a) \\le 0.05$
4. `s_poisson98`: Số xe theo phân vị 98% của phân phối Poisson $s = \\lceil a + 2.05\\sqrt{a} \\rceil$
"""))
    cells.append(nbf.v4.new_code_cell("""\
df_vehicles = forecast_to_vehicles(
    y_pred_dict = y_pred_dict,
    u           = params["u"],
    E_S_hr      = params["E_S_hr"],
    rho_max     = 0.80,   # Tiêu chí 1: ρ ≤ 0.80
    p_block     = 0.05,   # Tiêu chí 2: Erlang B ≤ 5%
    z           = 2.05,   # Tiêu chí 3: Poisson quantile 98%
)

print(f"Tổng số dòng kết quả: {len(df_vehicles):,}")
print(f"Các cột dữ liệu      : {list(df_vehicles.columns)}")
df_vehicles.head(12)
"""))

    # ── Cell 5: Summary Table ────────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 4: Bảng Tổng hợp Thống kê (Mô hình × Tiêu chí)
So sánh số lượng xe cần trực chiến: Nhỏ nhất (Min), Trung bình (Mean), Lớn nhất (Max) và giờ cao điểm (Peak hour)."""))
    cells.append(nbf.v4.new_code_cell("""\
summary_df = print_summary(df_vehicles)
summary_df
"""))

    # ── Cell 6: Export CSV & Sample ──────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 5: Xuất Báo cáo CSV & Mẫu Phân bổ 48 Giờ
Lưu kết quả chi tiết ra file `vehicle_requirements.csv` phục vụ lập kế hoạch vận hành."""))
    cells.append(nbf.v4.new_code_cell("""\
os.makedirs(OUTPUT_DIR, exist_ok=True)
csv_path = os.path.join(OUTPUT_DIR, "vehicle_requirements.csv")
df_vehicles.to_csv(csv_path, index=False)
print(f"✓ Đã lưu bảng phân bổ xe chi tiết: {csv_path}")

# Xem mẫu lịch điều xe 48 giờ đầu tiên của mô hình LSTM seq=24
sample_48h = (df_vehicles[df_vehicles["model"] == "LSTM seq=24"]
              .head(48)[["hour_index", "lambda_pred", "erlang_load_a",
                          "s_rho80", "s_erlangB5pct", "s_poisson98"]])
print("\\nMẫu phân bổ xe 48 giờ đầu (LSTM seq=24):")
sample_48h.head(24)
"""))

    # ── Cell 7: Timeline Plot ────────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 6: Trực quan hóa Dữ liệu

### 6.1 Timeline Nhu cầu Xe Cứu thương (14 ngày liên tục)
Quan sát sự dao động số lượng xe cần trực theo từng giờ giữa các ngày trong tuần và cuối tuần."""))
    cells.append(nbf.v4.new_code_cell("""\
# Vẽ timeline cho LSTM seq=24
fig = plot_vehicles_timeline(
    df         = df_vehicles,
    model_name = "LSTM seq=24",
    n_hours    = 24 * 14,   # 14 ngày
    save_path  = os.path.join(OUTPUT_DIR, "vehicles_timeline_LSTM_seq24.png"),
)
plt.show()
"""))

    # ── Cell 8: Hourly Profile ───────────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""### 6.2 Profile 24 Giờ — Nhu cầu Xe Trung bình theo Giờ trong Ngày
Biểu đồ này cực kỳ quan trọng cho các nhà quản lý để thiết kế **ca trực (shifts)** trong ngày:
* **Thấp điểm**: Đêm và sáng sớm (03:00 - 06:00).
* **Cao điểm**: Chiều và đầu giờ tối (14:00 - 20:00)."""))
    cells.append(nbf.v4.new_code_cell("""\
fig = plot_hourly_profile(
    df        = df_vehicles,
    save_path = os.path.join(OUTPUT_DIR, "vehicles_hourly_profile.png"),
)
plt.show()
"""))

    # ── Cell 9: Model Comparison Plot ────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""### 6.3 So sánh Giữa các Mô hình Dự báo (LSTM vs Naive Baseline)
Kiểm tra xem mô hình LSTM có giúp điều phối xe chủ động hơn so với Naive Baseline hay không."""))
    cells.append(nbf.v4.new_code_cell("""\
fig = plot_model_comparison(
    df        = df_vehicles,
    criterion = "s_erlangB5pct",
    n_hours   = 24 * 7,   # 1 tuần
    save_path = os.path.join(OUTPUT_DIR, "vehicles_model_comparison_erlangB.png"),
)
plt.show()
"""))

    # ── Cell 10: Sensitivity Analysis ────────────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 7: Phân tích Độ nhạy (Sensitivity Analysis)
Trong thực tế, điều kiện thời tiết xấu hoặc kẹt xe có thể làm tăng thời gian bận của xe $E[S]$, hoặc các sự cố nghiêm trọng có thể làm tăng số xe điều động $u$.
Ta tiến hành thử nghiệm biến thiên cả 2 tham số $\\pm 20\\%$ để đánh giá mức độ ảnh hưởng đến số xe cần bố trí."""))
    cells.append(nbf.v4.new_code_cell("""\
import itertools

base_model  = "LSTM seq=24"
lambda_base = y_pred_dict[base_model]

rows_sens = []
for e_fac, u_fac in itertools.product([0.8, 1.0, 1.2], [0.8, 1.0, 1.2]):
    E_S_try = params["E_S_hr"] * e_fac
    u_try   = params["u"]      * u_fac
    df_try  = forecast_to_vehicles({base_model: lambda_base},
                                    u=u_try, E_S_hr=E_S_try)
    agg = df_try.agg({
        "s_rho80":       "mean",
        "s_erlangB5pct": "mean",
        "s_poisson98":   "mean",
    }).to_dict()
    agg["E_S_factor"] = f"{e_fac:.1f}x"
    agg["u_factor"]   = f"{u_fac:.1f}x"
    rows_sens.append(agg)

df_sens = (pd.DataFrame(rows_sens)
             [["E_S_factor","u_factor","s_rho80","s_erlangB5pct","s_poisson98"]])
sens_path = os.path.join(OUTPUT_DIR, "sensitivity_analysis.csv")
df_sens.to_csv(sens_path, index=False)
print("Bảng Phân tích Độ nhạy — Số xe Trung bình (Mean) khi tham số thay đổi ±20%:")
df_sens
"""))

    # ── Cell 11: Operational Recommendations ─────────────────────────────────
    cells.append(nbf.v4.new_markdown_cell("""## Bước 8: Đề xuất Chiến lược Vận hành & Phân ca (Operational Shift Recommendations)

Dựa trên kết quả thực nghiệm lý thuyết hàng đợi:

1. **Lựa chọn Tiêu chuẩn Vận hành**:
   * **Tiêu chuẩn An toàn Khuyến nghị — Erlang B $\\le 5\\%$**: Trung bình cần **19 xe**, giờ cao điểm cần tối đa **31 xe**. Đây là tiêu chuẩn cân bằng tốt nhất giữa độ an toàn cho bệnh nhân và chi phí hoạt động của thành phố.
   * **Tiêu chuẩn Giờ Cao điểm / Khẩn cấp — Poisson 98%**: Trung bình cần **23 xe**, đỉnh điểm **35 xe**. Áp dụng trong các dịp lễ hội lớn, thời tiết cực đoan hoặc mùa dịch.

2. **Kế hoạch Phân ca Trực chiến (2 Ca 12 tiếng)**:
   * **Ca Ngày (07:00 - 19:00 — Cao điểm)**: Trung bình cần **22 - 25 xe**. Cần bố trí thêm các xe cơ động tại các khu vực trọng điểm nội đô.
   * **Ca Đêm (19:00 - 07:00 — Thấp điểm)**: Nhu cầu giảm xuống **14 - 17 xe**. Có thể rút bớt xe về trạm để bảo dưỡng kỹ thuật, khử khuẩn và cho nhân sự nghỉ ngơi.

3. **Lợi ích so với Naive Baseline**:
   * Mô hình LSTM seq=24 đón trước được xu hướng tăng tải trước 1-2 giờ, giúp xe có mặt sẵn sàng tại vị trí trực chiến trước khi cuộc gọi tăng đột biến.
"""))

    nb.cells = cells
    
    # Save standard name
    out_path = os.path.join(NOTEBOOKS_DIR, "queueing_theory.ipynb")
    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"[OK] Notebook saved: {out_path}")

    # Also save with the exact filename with space if needed so existing IDE tabs work seamlessly
    out_path_spaced = os.path.join(NOTEBOOKS_DIR, "queueing _theory.ipynb")
    shutil.copyfile(out_path, out_path_spaced)
    print(f"[OK] Copied to: {out_path_spaced}")


if __name__ == "__main__":
    print("Generating separated notebooks...")
    create_lstm_experiment_notebook()
    create_queueing_theory_notebook()
    print("Done! Both notebooks created successfully.")
