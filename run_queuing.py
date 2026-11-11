"""
run_queuing.py — Chạy Queuing Theory Module độc lập
====================================================
Load model vanilla_seq24 đã train, chạy inference trên test set,
rồi áp dụng queuing theory để tính số xe cần mỗi giờ.

Chạy từ thư mục gốc:
    python run_queuing.py
"""
import sys, os

# Fix UTF-8 output trên Windows (tránh UnicodeEncodeError với ký tự box-drawing)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend
import matplotlib.pyplot as plt

from ems.models.lstm.config     import DATA_DIR, OUTPUT_DIR, TARGET_COL, N_FEATURES, \
                                       HIDDEN_SIZE, NUM_LAYERS, DROPOUT, BATCH_SIZE
from ems.models.lstm.preprocess import build_dataloaders
from ems.models.lstm.model      import build_model
from ems.models.lstm.train      import load_checkpoint
from ems.models.lstm.evaluate   import predict, compute_metrics, print_metrics, naive_baseline
from ems.queuing                import (
    estimate_service_params,
    forecast_to_vehicles,
    print_summary,
    plot_vehicles_timeline,
    plot_hourly_profile,
    plot_model_comparison,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("  EMS Queuing Theory — Capacity Planning")
print("=" * 60)

# ── 1. Load data & model ────────────────────────────────────────────────
print("\n[1] Loading data & model (vanilla_seq24)...")
train_dl, val_dl, test_dl, feat_scaler, tgt_scaler = build_dataloaders(
    seq_len=24, batch_size=BATCH_SIZE, verbose=True
)

model = build_model("vanilla", n_features=N_FEATURES,
                     hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS,
                     dropout=DROPOUT)
history = load_checkpoint(model, run_name="vanilla_seq24")

# ── 2. Predict on test set ─────────────────────────────────────────────
print("\n[2] Inference trên test set...")
y_true, y_pred_lstm = predict(model, test_dl, tgt_scaler)
metrics = compute_metrics(y_true, y_pred_lstm)
print_metrics(metrics, run_name="LSTM seq=24 (test set)")

# ── 3. Naive baseline ───────────────────────────────────────────────────
print("\n[3] Naive baseline (lag-1)...")
y_test_raw = pd.read_csv(os.path.join(DATA_DIR, "y_test.csv"))[TARGET_COL].values
y_pred_naive = np.roll(y_test_raw, 1)
y_pred_naive[0] = y_test_raw[0]
naive_m = naive_baseline(y_test_raw)
print_metrics(naive_m, run_name="Naive Lag-1")

# ── 4. Queuing: ước lượng tham số ─────────────────────────────────────
print("\n[4] Ước lượng tham số dịch vụ...")
params = estimate_service_params(
    raw_df=None,
    default_E_S_hr=0.60,   # 36 phút bận / xe
    default_u=1.35,         # xe / cuộc gọi
)

# ── 5. Tính số xe cần theo 3 tiêu chí ─────────────────────────────────
print("\n[5] Tính số xe cần...")

# Align lengths (LSTM seq24 bắt đầu từ index 24)
n_test = len(y_pred_lstm)
y_naive_aligned = y_pred_naive[-n_test:]   # lấy phần cuối khớp chiều dài

y_pred_dict = {
    "Naive Lag-1":  y_naive_aligned,
    "LSTM seq=24":  y_pred_lstm,
}

df_vehicles = forecast_to_vehicles(
    y_pred_dict = y_pred_dict,
    u           = params["u"],
    E_S_hr      = params["E_S_hr"],
    rho_max     = 0.80,
    p_block     = 0.05,
    z           = 2.05,
)

# ── 6. Tóm tắt ──────────────────────────────────────────────────────────
print("\n[6] Tóm tắt:")
summary = print_summary(df_vehicles)

# ── 7. Xuất CSV ─────────────────────────────────────────────────────────
csv_path = os.path.join(OUTPUT_DIR, "vehicle_requirements.csv")
df_vehicles.to_csv(csv_path, index=False)
print(f"\n[7] CSV saved → {csv_path}")

# Mẫu bảng 48 giờ đầu — LSTM
sample = (df_vehicles[df_vehicles["model"] == "LSTM seq=24"]
          .head(48)[["hour_index","lambda_pred","erlang_load_a",
                      "s_rho80","s_erlangB5pct","s_poisson98"]])
print("\n── Mẫu bảng giờ → số xe (LSTM seq=24, 48 giờ đầu) ──")
print(sample.to_string(index=False))

# ── 8. Vẽ biểu đồ ──────────────────────────────────────────────────────
print("\n[8] Generating plots...")

# 8a. Timeline
for model_name in y_pred_dict:
    safe = model_name.replace(" ", "_").replace("=", "")
    fig = plot_vehicles_timeline(
        df         = df_vehicles,
        model_name = model_name,
        n_hours    = 24 * 14,
        save_path  = os.path.join(OUTPUT_DIR, f"vehicles_timeline_{safe}.png"),
    )
    plt.close(fig)

# 8b. 24h profile
fig = plot_hourly_profile(
    df        = df_vehicles,
    save_path = os.path.join(OUTPUT_DIR, "vehicles_hourly_profile.png"),
)
plt.close(fig)

# 8c. Model comparison (Erlang B)
fig = plot_model_comparison(
    df        = df_vehicles,
    criterion = "s_erlangB5pct",
    save_path = os.path.join(OUTPUT_DIR, "vehicles_model_comparison_erlangB.png"),
)
plt.close(fig)

# 8d. Model comparison (Poisson 98%)
fig = plot_model_comparison(
    df        = df_vehicles,
    criterion = "s_poisson98",
    save_path = os.path.join(OUTPUT_DIR, "vehicles_model_comparison_poisson98.png"),
)
plt.close(fig)

# ── 9. Sensitivity analysis ─────────────────────────────────────────────
print("\n[9] Sensitivity Analysis...")
import itertools

base_model  = "LSTM seq=24"
lambda_base = y_pred_dict[base_model]
rows_sens   = []

for e_fac, u_fac in itertools.product([0.8, 1.0, 1.2], [0.8, 1.0, 1.2]):
    E_S_try = params["E_S_hr"] * e_fac
    u_try   = params["u"]      * u_fac
    df_try  = forecast_to_vehicles(
        {base_model: lambda_base}, u=u_try, E_S_hr=E_S_try
    )
    agg = df_try.agg({
        "s_rho80":       "mean",
        "s_erlangB5pct": "mean",
        "s_poisson98":   "mean",
    }).to_dict()
    agg["E_S_factor"] = e_fac
    agg["u_factor"]   = u_fac
    rows_sens.append(agg)

df_sens = (pd.DataFrame(rows_sens)
             .round(2)
             [["E_S_factor","u_factor","s_rho80","s_erlangB5pct","s_poisson98"]])
print("\nSensitivity — Số xe TB (mean) khi E[S] và u thay đổi ±20%:")
print(df_sens.to_string(index=False))
df_sens.to_csv(os.path.join(OUTPUT_DIR, "sensitivity_analysis.csv"), index=False)
print(f"\n  Saved → {os.path.join(OUTPUT_DIR, 'sensitivity_analysis.csv')}")

print("\n" + "=" * 60)
print("  DONE — Tất cả kết quả đã lưu vào outputs/")
print("=" * 60)
print(f"\n  Files tạo ra:")
for f in sorted(os.listdir(OUTPUT_DIR)):
    fp = os.path.join(OUTPUT_DIR, f)
    size = os.path.getsize(fp)
    print(f"    {f:<50} {size:>10,} bytes")
