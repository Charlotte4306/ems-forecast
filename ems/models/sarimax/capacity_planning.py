import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("BƯỚC 10: KẾ HOẠCH NĂNG LỰC & ĐÁNH GIÁ CHI PHÍ KHI DỰ BÁO SAI")
print("=" * 70)

# Đọc kết quả dự báo SARIMAX từ pred_sarimax.csv
df = pd.read_csv("pred_sarimax.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.set_index("timestamp")

# Đọc dữ liệu lịch sử để tính baseline profile
X_train = pd.read_csv("data/X_train.csv")
y_train = pd.read_csv("data/y_train.csv")
X_val = pd.read_csv("data/X_val.csv")
y_val = pd.read_csv("data/y_val.csv")

def make_dt_idx(X):
    return pd.to_datetime(X[['year', 'month', 'day_of_month', 'hour']].rename(columns={'day_of_month': 'day'}))

idx_tr = make_dt_idx(X_train)
idx_va = make_dt_idx(X_val)

train_series = pd.Series(y_train['call_count'].values, index=idx_tr).asfreq('h')
val_series = pd.Series(y_val['call_count'].values, index=idx_va).asfreq('h')
y_full = pd.concat([train_series, val_series]).iloc[-8760:]

# Profile theo giờ và thứ trong tuần
df_hist = pd.DataFrame({"actual": y_full.values, "hour": y_full.index.hour, "dow": y_full.index.dayofweek})
profile_map = df_hist.groupby(["hour", "dow"])["actual"].mean()

test_dow_hour = list(zip(df.index.hour, df.index.dayofweek))
pred_profile = np.array([profile_map.get(k, y_full.mean()) for k in test_dow_hour])

# Seasonal naive (168 giờ trước)
full_hist_and_test = pd.concat([y_full, df["actual"]])
pred_snaive = full_hist_and_test.shift(168).loc[df.index].fillna(pd.Series(pred_profile, index=df.index))

# BÀI TOÁN BỐ TRÍ NHÂN SỰ & NĂNG LỰC ĐIỀU PHỐI CẤP CỨU (911 Medical Dispatchers)
# Giả định bài toán thực tế:
# - Mỗi điều phối viên trực tổng đài tiếp nhận & xử lý trung bình MU cuộc gọi/giờ (ví dụ MU = 3 cuộc gọi/giờ, bao gồm cả phân loại rủi ro, định vị xe và tư vấn hỗ trợ tim phổi CPR từ xa).
# - Chi phí ca trực thừa (Over-staffing cost, C_over): $30 / giờ nhân viên rảnh rỗi.
# - Chi phí ca trực thiếu (Under-staffing penalty, C_under): $75 / giờ phạt chậm trễ, vi phạm SLA thời gian chờ cấp cứu hoặc phụ cấp huy động khẩn cấp.

MU = 3.0
C_OVER = 30.0   # $/giờ
C_UNDER = 75.0  # $/giờ

S_actual = np.ceil(df["actual"] / MU).astype(int)

# Các chiến lược bố trí nhân sự:
strategies = {
    "Seasonal Naive (168h)": np.ceil(pred_snaive / MU).astype(int),
    "Lịch sử Giờ x Thứ": np.ceil(pred_profile / MU).astype(int),
    "SARIMAX (Dự báo điểm)": np.ceil(df["pred"] / MU).astype(int),
    "SARIMAX (Chặn trên 80% CI)": np.ceil(df["hi"] / MU).astype(int)
}

cost_summary = []
for strat_name, S_pred in strategies.items():
    over_hours = np.maximum(0, S_pred - S_actual)
    under_hours = np.maximum(0, S_actual - S_pred)
    
    cost_over = float((over_hours * C_OVER).sum())
    cost_under = float((under_hours * C_UNDER).sum())
    total_cost = cost_over + cost_under
    
    under_pct = float(100.0 * (S_pred < S_actual).mean())
    over_pct = float(100.0 * (S_pred > S_actual).mean())
    exact_pct = float(100.0 * (S_pred == S_actual).mean())
    
    cost_summary.append({
        "Chiến lược": strat_name,
        "Đúng công suất (%)": round(exact_pct, 1),
        "Thừa nhân sự (%)": round(over_pct, 1),
        "Thiếu nhân sự (%)": round(under_pct, 1),
        "Tổng giờ thiếu": int(under_hours.sum()),
        "Tổng giờ thừa": int(over_hours.sum()),
        "Chi phí Thừa ($)": round(cost_over, 0),
        "Chi phí Thiếu ($)": round(cost_under, 0),
        "TỔNG CHI PHÍ ($)": round(total_cost, 0),
    })

df_cost = pd.DataFrame(cost_summary)
base_cost = df_cost.loc[df_cost["Chiến lược"] == "Lịch sử Giờ x Thứ", "TỔNG CHI PHÍ ($)"].values[0]
df_cost["Tiết kiệm vs Baseline ($)"] = base_cost - df_cost["TỔNG CHI PHÍ ($)"]
df_cost["% Giảm chi phí"] = round(100.0 * df_cost["Tiết kiệm vs Baseline ($)"] / base_cost, 2)

print("\n--- BẢNG ĐÁNH GIÁ CHI PHÍ KHI DỰ BÁO SAI TRÊN TẬP TEST (6,796 GIỜ) ---")
print(df_cost.to_string(index=False))

# Xuất kết quả chi phí ra CSV
df_cost.to_csv("capacity_cost_evaluation.csv", index=False)
print("\nĐã lưu: capacity_cost_evaluation.csv")

# TẠO CÁC BIỂU ĐỒ BÁO CÁO
fig_dir = os.path.abspath("figures")
os.makedirs(fig_dir, exist_ok=True)

# 1. Biểu đồ dự báo một tuần
sample_week = df.iloc[24*7:24*14]
plt.figure(figsize=(13, 5))
plt.plot(sample_week.index, sample_week["actual"], label="Nhu cầu thực tế (Actual)", color="#1f77b4", linewidth=2)
plt.plot(sample_week.index, sample_week["pred"], label="SARIMAX Dự báo", color="#d62728", linestyle="--", linewidth=1.8)
plt.fill_between(sample_week.index, sample_week["lo"], sample_week["hi"], color="#ff9896", alpha=0.35, label="Khoảng tin cậy 80%")
plt.title("Dự báo nhu cầu cuộc gọi cấp cứu 911 (Một tuần mẫu trên tập Test)", fontsize=13, fontweight="bold", pad=12)
plt.xlabel("Thời gian")
plt.ylabel("Số cuộc gọi / giờ")
plt.legend(loc="upper right", frameon=True)
plt.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "forecast_sample_week.png"), dpi=200)
plt.close()

# 2. Biểu đồ bố trí nhân sự (Staffing schedule 4 ngày mẫu)
sample_days = slice(24*7, 24*11)
plt.figure(figsize=(13, 5))
plt.step(df.index[sample_days], S_actual.iloc[sample_days], label="Nhân sự thực tế cần (Actual needed)", color="black", linewidth=2.2, where="mid")
plt.step(df.index[sample_days], pd.Series(strategies["SARIMAX (Dự báo điểm)"], index=df.index).iloc[sample_days], label="Bố trí theo SARIMAX", color="#2ca02c", linestyle="--", linewidth=1.6, where="mid")
plt.step(df.index[sample_days], pd.Series(strategies["Lịch sử Giờ x Thứ"], index=df.index).iloc[sample_days], label="Bố trí theo Baseline Lịch sử", color="#ff7f0e", linestyle=":", linewidth=1.6, where="mid")
plt.title("Kế hoạch năng lực: Số nhân sự điều phối trực theo giờ (4 ngày mẫu)", fontsize=13, fontweight="bold", pad=12)
plt.xlabel("Thời gian")
plt.ylabel("Số nhân viên trực / giờ")
plt.legend(loc="upper right", frameon=True)
plt.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "staffing_schedule.png"), dpi=200)
plt.close()

# 3. Biểu đồ so sánh chi phí (Cost breakdown bar chart)
plt.figure(figsize=(10, 5))
strats = df_cost["Chiến lược"].tolist()
cost_o = df_cost["Chi phí Thừa ($)"].tolist()
cost_u = df_cost["Chi phí Thiếu ($)"].tolist()

x = np.arange(len(strats))
width = 0.35

plt.bar(x - width/2, cost_o, width, label="Chi phí Thừa nhân sự (Overstaffing)", color="#3498db")
plt.bar(x + width/2, cost_u, width, label="Chi phí Thiếu nhân sự (Understaffing penalty)", color="#e74c3c")

plt.xticks(x, strats, rotation=10, ha="right", fontsize=9)
plt.ylabel("Tổng chi phí ($)")
plt.title("So sánh tổn thất chi phí khi dự báo sai giữa các chiến lược", fontsize=12, fontweight="bold", pad=12)
plt.legend()
plt.grid(True, axis="y", linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "cost_comparison.png"), dpi=200)
plt.close()

# 4. Biểu đồ sai số theo khung giờ
df["hour"] = df.index.hour
df["period"] = pd.cut(
    df["hour"],
    bins=[-1, 5, 11, 17, 23],
    labels=["Đêm (0h-5h)", "Sáng (6h-11h)", "Chiều (12h-17h)", "Tối (18h-23h)"]
)
period_err = df.groupby("period", observed=False).apply(
    lambda g: pd.Series({
        "MAE": (g["actual"] - g["pred"]).abs().mean(),
        "Nhu cầu thực TB": g["actual"].mean()
    })
)

plt.figure(figsize=(8, 4.5))
bars = plt.bar(period_err.index, period_err["MAE"], color=["#2c3e50", "#e67e22", "#e74c3c", "#8e44ad"], width=0.55)
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.05, f"{yval:.2f}", ha='center', va='bottom', fontweight='bold')
plt.title("Sai số MAE của SARIMAX theo từng khung giờ trong ngày", fontsize=12, fontweight="bold", pad=12)
plt.ylabel("MAE (cuộc gọi / giờ)")
plt.ylim(0, max(period_err["MAE"]) * 1.25)
plt.grid(True, axis="y", linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "hourly_mae.png"), dpi=200)
plt.close()

print("\nĐã tạo thành công 4 biểu đồ trong figures/:")
print(f"1. {os.path.join(fig_dir, 'forecast_sample_week.png')}")
print(f"2. {os.path.join(fig_dir, 'staffing_schedule.png')}")
print(f"3. {os.path.join(fig_dir, 'cost_comparison.png')}")
print(f"4. {os.path.join(fig_dir, 'hourly_mae.png')}")
