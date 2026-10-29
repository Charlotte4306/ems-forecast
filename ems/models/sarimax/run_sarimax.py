import time
import warnings
import os
import sys
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX
from pandas.tseries.holiday import USFederalHolidayCalendar
import statsmodels.api as sm

# Set UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("SARIMAX MODEL CHO DỰ BÁO NHU CẦU DỊCH VỤ CẤP CỨU & KẾ HOẠCH NĂNG LỰC")
print("=" * 70)

# 1. Tải dữ liệu và đồng bộ datetime index
def load_data(split):
    X = pd.read_csv(f"data/X_{split}.csv")
    y = pd.read_csv(f"data/y_{split}.csv")
    idx = pd.to_datetime(X[['year', 'month', 'day_of_month', 'hour']].rename(columns={'day_of_month': 'day'}))
    return pd.Series(y['call_count'].values, index=idx).asfreq('h')

train = load_data('train')
val   = load_data('val')
test  = load_data('test')

print(f"Train period : {train.index.min()} -> {train.index.max()} ({len(train):,} giờ)")
print(f"Val period   : {val.index.min()} -> {val.index.max()} ({len(val):,} giờ)")
print(f"Test period  : {test.index.min()} -> {test.index.max()} ({len(test):,} giờ)")
print(f"Missing (Train/Val/Test): {train.isna().sum()}/{val.isna().sum()}/{test.isna().sum()}")

# 2. Chọn cửa sổ huấn luyện 1 năm gần nhất (8,760 giờ)
y_tr = train.iloc[-8760:]
print(f"Train window : {y_tr.index.min()} -> {y_tr.index.max()} ({len(y_tr):,} giờ)")

# 3. Tạo biến ngoại sinh Fourier + Lịch + Ngày lễ liên bang Mỹ
hol = USFederalHolidayCalendar().holidays("2019-01-01", "2026-12-31")

def make_exog(idx, K=4):
    h, dow = idx.hour.values, idx.dayofweek.values
    wkend = (dow >= 5).astype(float)
    X = pd.DataFrame(index=idx)
    for k in range(1, K + 1):
        s, c = np.sin(2 * np.pi * k * h / 24), np.cos(2 * np.pi * k * h / 24)
        X[f"s{k}"], X[f"c{k}"] = s, c
        X[f"s{k}_we"], X[f"c{k}_we"] = s * wkend, c * wkend
    for d in range(1, 7):
        X[f"dow{d}"] = (dow == d).astype(float)
    X["holiday"] = idx.normalize().isin(hol).astype(float)
    return X

# Hàm tính độ đo đánh giá
def metrics(df):
    e = (df['actual'] - df['pred']).abs()
    nz = df['actual'] > 0
    mae = float(e.mean())
    wape = float(100.0 * e.sum() / df['actual'].sum())
    mape = float(100.0 * (e[nz] / df['actual'][nz]).mean())
    rmse = float(np.sqrt(((df['actual'] - df['pred']) ** 2).mean()))
    cov80 = float(((df['actual'] >= df['lo']) & (df['actual'] <= df['hi'])).mean() * 100.0) if 'lo' in df else np.nan
    return {"MAE": mae, "WAPE%": wape, "MAPE%": mape, "RMSE": rmse, "Cov80%": cov80}

# Hàm dự báo cuốn chiếu 24h
def rolling_forecast(res, y, X, horizon=24):
    rows = []
    cur_res = res
    for s in range(0, len(y), horizon):
        yc, Xc = y.iloc[s:s+horizon], X.iloc[s:s+horizon]
        fc = cur_res.get_forecast(steps=len(yc), exog=Xc)
        ci = fc.conf_int(alpha=0.2)  # Khoảng tin cậy 80%
        rows.append(pd.DataFrame({
            "actual": yc.values,
            "pred": fc.predicted_mean.values,
            "lo": ci.iloc[:, 0].values,
            "hi": ci.iloc[:, 1].values
        }, index=yc.index))
        cur_res = cur_res.append(yc, exog=Xc, refit=False)
    out = pd.concat(rows)
    out[["pred", "lo", "hi"]] = out[["pred", "lo", "hi"]].clip(lower=0)
    return out

# 4. Thử nghiệm Grid Search các cấu hình trên tập Validation
print("\n" + "=" * 70)
print("BƯỚC 8: GRID SEARCH TRÊN TẬP VALIDATION")
print("=" * 70)

grid_candidates = [
    ((1, 0, 1), 3),
    ((1, 0, 1), 4),
    ((2, 0, 1), 4),
    ((1, 0, 2), 4),
    ((2, 0, 2), 4),
]

val_results = []
for order, K in grid_candidates:
    t0 = time.time()
    Xa = make_exog(y_tr.index, K)
    Xv = make_exog(val.index, K)
    r = SARIMAX(y_tr, exog=Xa, order=order, trend="c").fit(disp=False, maxiter=100)
    pred_val = rolling_forecast(r, val, Xv)
    m = metrics(pred_val)
    elapsed = time.time() - t0
    val_results.append({
        "order": str(order),
        "K": K,
        "AIC": round(r.aic, 1),
        "MAE": round(m["MAE"], 3),
        "WAPE%": round(m["WAPE%"], 2),
        "MAPE%": round(m["MAPE%"], 2),
        "Cov80%": round(m["Cov80%"], 1),
        "Time_s": round(elapsed, 1),
        "model_obj": r,
        "pred_val": pred_val
    })
    print(f"Order: {order} | K={K} | AIC: {round(r.aic, 1):<8} | MAE: {m['MAE']:.3f} | WAPE: {m['WAPE%']:.2f}% | MAPE: {m['MAPE%']:.2f}% | Cov80: {m['Cov80%']:.1f}% | Time: {elapsed:.1f}s")

df_grid = pd.DataFrame([{k: v for k, v in res.items() if k not in ["model_obj", "pred_val"]} for res in val_results])
print("\nBảng so sánh cấu hình:")
print(df_grid.to_string(index=False))

# Chọn cấu hình tốt nhất theo MAE trên validation
best_idx = df_grid["MAE"].idxmin()
best_res = val_results[best_idx]
BEST_ORDER = eval(best_res["order"])
BEST_K = best_res["K"]
print(f"\n=> Cấu hình tối ưu được chọn: order={BEST_ORDER}, K={BEST_K} (MAE val: {best_res['MAE']})")

# 5. Huấn luyện lại trên dữ liệu gộp Train + Val (cửa sổ 1 năm gần nhất) và dự báo trên Test
print("\n" + "=" * 70)
print("BƯỚC 9: HUẤN LUYỆN LẠI VÀ DỰ BÁO TRÊN TẬP TEST")
print("=" * 70)
y_full = pd.concat([train, val]).iloc[-8760:]
X_full = make_exog(y_full.index, BEST_K)
X_test = make_exog(test.index, BEST_K)

print(f"Cửa sổ huấn luyện mô hình cuối cùng: {y_full.index.min()} -> {y_full.index.max()} ({len(y_full):,} giờ)")
t_final_start = time.time()
final_model = SARIMAX(y_full, exog=X_full, order=BEST_ORDER, trend="c").fit(disp=False, maxiter=100)
pred_test = rolling_forecast(final_model, test, X_test)
final_time = time.time() - t_final_start

m_test = metrics(pred_test)
print(f"\n--- KẾT QUẢ ĐÁNH GIÁ TRÊN TEST ({len(test):,} giờ) ---")
print(f"Fit + Rolling Test Time: {final_time:.1f}s")
print(f"MAE   : {m_test['MAE']:.3f}")
print(f"RMSE  : {m_test['RMSE']:.3f}")
print(f"WAPE  : {m_test['WAPE%']:.2f}%")
print(f"MAPE  : {m_test['MAPE%']:.2f}%")
print(f"Coverage 80%: {m_test['Cov80%']:.1f}%")

# Lưu file kết quả dự báo đúng format yêu cầu
pred_test_out = pred_test.rename_axis("timestamp").reset_index()
pred_test_out.to_csv("pred_sarimax.csv", index=False)
print("Đã lưu kết quả dự báo ra: pred_sarimax.csv")

# 6. Đánh giá sai số theo khung giờ
pred_test["hour"] = pred_test.index.hour
pred_test["period"] = pd.cut(
    pred_test["hour"],
    bins=[-1, 5, 11, 17, 23],
    labels=["Đêm (0h-5h)", "Sáng (6h-11h)", "Chiều (12h-17h)", "Tối (18h-23h)"]
)

period_metrics = pred_test.groupby("period", observed=False).apply(
    lambda g: pd.Series({
        "Số giờ": len(g),
        "Nhu cầu thực TB": round(g["actual"].mean(), 2),
        "Dự báo TB": round(g["pred"].mean(), 2),
        "MAE": round((g["actual"] - g["pred"]).abs().mean(), 3),
        "WAPE%": round(100.0 * (g["actual"] - g["pred"]).abs().sum() / g["actual"].sum(), 2),
        "MAPE%": round(100.0 * ((g["actual"] - g["pred"]).abs() / g["actual"].clip(lower=1)).mean(), 2)
    })
)
print("\n--- SAI SỐ THEO KHUNG GIỜ TRONG NGÀY (TẬP TEST) ---")
print(period_metrics.to_string())

# 7. Baseline so sánh (Seasonal Naive 168h & Lịch sử giờ x thứ)
# Lấy hồ sơ trung bình theo (hour, day_of_week) từ y_full
df_yfull = pd.DataFrame({"actual": y_full.values, "hour": y_full.index.hour, "dow": y_full.index.dayofweek})
hod_dow_profile = df_yfull.groupby(["hour", "dow"])["actual"].mean()

test_dow_hour = list(zip(test.index.hour, test.index.dayofweek))
pred_profile = np.array([hod_dow_profile.get(k, y_full.mean()) for k in test_dow_hour])

df_profile = pd.DataFrame({"actual": test.values, "pred": pred_profile}, index=test.index)
m_profile = metrics(df_profile)

# Seasonal naive (lấy giá trị đúng 168 giờ trước)
full_series = pd.concat([y_full, test])
pred_snaive = full_series.shift(168).loc[test.index]
df_snaive = pd.DataFrame({"actual": test.values, "pred": pred_snaive.values}, index=test.index).dropna()
m_snaive = metrics(df_snaive)

print("\n--- BẢNG SO SÁNH VỚI BASELINES TRÊN TEST ---")
comparison = pd.DataFrame([
    {"Mô hình": "Seasonal Naive (168h)", "MAE": round(m_snaive["MAE"], 3), "WAPE%": round(m_snaive["WAPE%"], 2), "MAPE%": round(m_snaive["MAPE%"], 2)},
    {"Mô hình": "Trung bình Giờ x Thứ", "MAE": round(m_profile["MAE"], 3), "WAPE%": round(m_profile["WAPE%"], 2), "MAPE%": round(m_profile["MAPE%"], 2)},
    {"Mô hình": "SARIMAX (Fourier + ARMA)", "MAE": round(m_test["MAE"], 3), "WAPE%": round(m_test["WAPE%"], 2), "MAPE%": round(m_test["MAPE%"], 2)},
])
print(comparison.to_string(index=False))

# 8. KẾ HOẠCH NĂNG LỰC & ĐÁNH GIÁ CHI PHÍ KHI DỰ BÁO SAI
print("\n" + "=" * 70)
print("BƯỚC 10: NỐI DỰ BÁO VÀO QUYẾT ĐỊNH NĂNG LỰC & ĐÁNH GIÁ CHI PHÍ")
print("=" * 70)

# Giả định bài toán vận hành tổng đài cấp cứu 911:
# - Mỗi tổng đài viên/điều phối viên xử lý trung bình mu cuộc gọi mỗi giờ
#   (Ví dụ: tiếp nhận, định vị, hỏi bệnh, tư vấn sơ cấp cứu & dispatch xe mất ~4 phút -> ~15 cuộc/giờ/người,
#   hoặc nếu xét năng lực kíp xe cứu thương: mỗi kíp xe xử lý 1 ca/giờ).
# - Ở đây ta mô hình hóa cho cả 2 kịch bản hoặc kịch bản ĐIỀU PHỐI VIÊN TỔNG ĐÀI (Dispatchers / Call-takers):
#   Năng suất: 1 nhân viên xử lý mu = 3 cuộc gọi/giờ (cho phép thời gian hỗ trợ và buffer nghỉ ngơi)
MU = 3.0 # Cuộc gọi/giờ/nhân viên
C_OVER = 30.0   # $30/giờ lương nhân viên nhàn rỗi (Overstaffing)
C_UNDER = 75.0  # $75/giờ chi phí thiếu hụt: gọi khẩn cấp tăng ca, phạt SLA chậm trễ cứu thương (Understaffing)

# 4 chiến lược bố trí nhân sự:
# 1. Staffing theo Seasonal Naive
# 2. Staffing theo Trung bình Giờ x Thứ
# 3. Staffing theo Điểm dự báo SARIMAX (mean)
# 4. Staffing an toàn theo Chặn trên khoảng tin cậy 80% của SARIMAX (hi_80)
# Năng lực thực tế cần có: S_actual = ceil(actual / MU)

S_actual = np.ceil(pred_test["actual"] / MU).astype(int)

strategies = {
    "Seasonal Naive": np.ceil(df_snaive["pred"].reindex(test.index).fillna(pred_profile) / MU).astype(int),
    "Lịch sử Giờ x Thứ": np.ceil(pred_profile / MU).astype(int),
    "SARIMAX (Dự báo điểm)": np.ceil(pred_test["pred"] / MU).astype(int),
    "SARIMAX (Chặn trên 80% CI)": np.ceil(pred_test["hi"] / MU).astype(int),
}

cost_results = []
for strat_name, S_pred in strategies.items():
    over_hours = np.maximum(0, S_pred - S_actual)
    under_hours = np.maximum(0, S_actual - S_pred)
    cost_over = (over_hours * C_OVER).sum()
    cost_under = (under_hours * C_UNDER).sum()
    total_cost = cost_over + cost_under
    
    under_pct = 100.0 * (S_pred < S_actual).mean()
    over_pct = 100.0 * (S_pred > S_actual).mean()
    exact_pct = 100.0 * (S_pred == S_actual).mean()
    
    cost_results.append({
        "Chiến lược bố trí": strat_name,
        "Đúng công suất (%)": round(exact_pct, 1),
        "Thừa nhân sự (%)": round(over_pct, 1),
        "Thiếu nhân sự (%)": round(under_pct, 1),
        "Chi phí Thừa ($)": round(cost_over, 0),
        "Chi phí Thiếu ($)": round(cost_under, 0),
        "TỔNG CHI PHÍ ($)": round(total_cost, 0),
        "Tiết kiệm so với Lịch sử ($)": 0
    })

df_cost = pd.DataFrame(cost_results)
baseline_cost = df_cost.loc[df_cost["Chiến lược bố trí"] == "Lịch sử Giờ x Thứ", "TỔNG CHI PHÍ ($)"].values[0]
df_cost["Tiết kiệm so với Lịch sử ($)"] = baseline_cost - df_cost["TỔNG CHI PHÍ ($)"]
print(df_cost.to_string(index=False))

# 9. Vẽ biểu đồ trực quan hóa
os.makedirs("figures", exist_ok=True)

# Biểu đồ 1: Một tuần dự báo điển hình (168 giờ đầu của Test)
sample_week = pred_test.iloc[24*7:24*14]  # Tuần thứ 2 của Test
plt.figure(figsize=(14, 5))
plt.plot(sample_week.index, sample_week["actual"], label="Thực tế (Actual)", color="#1f77b4", linewidth=2)
plt.plot(sample_week.index, sample_week["pred"], label="SARIMAX Dự báo", color="#d62728", linestyle="--", linewidth=1.8)
plt.fill_between(sample_week.index, sample_week["lo"], sample_week["hi"], color="#ff9896", alpha=0.35, label="Khoảng tin cậy 80%")
plt.title("Dự báo nhu cầu cuộc gọi cứu thương 911 (Một tuần điển hình trên Test)", fontsize=13, fontweight="bold")
plt.xlabel("Thời gian")
plt.ylabel("Số cuộc gọi / giờ")
plt.legend(loc="upper right")
plt.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig("figures/forecast_sample_week.png", dpi=200)
plt.close()

# Biểu đồ 2: So sánh nhân sự bố trí và chi phí
sample_staff = pd.DataFrame({
    "Thực tế cần": S_actual.iloc[24*7:24*10],
    "SARIMAX bố trí": strategies["SARIMAX (Dự báo điểm)"].iloc[24*7:24*10],
    "Lịch sử bố trí": strategies["Lịch sử Giờ x Thứ"].iloc[24*7:24*10]
})
plt.figure(figsize=(14, 5))
plt.step(sample_staff.index, sample_staff["Thực tế cần"], label="Nhu cầu nhân viên thực tế", color="black", linewidth=2, where="mid")
plt.step(sample_staff.index, sample_staff["SARIMAX bố trí"], label="SARIMAX Staffing", color="#2ca02c", linestyle="--", linewidth=1.5, where="mid")
plt.step(sample_staff.index, sample_staff["Lịch sử bố trí"], label="Lịch sử Giờ x Thứ Staffing", color="#ff7f0e", linestyle=":", linewidth=1.5, where="mid")
plt.title("Kế hoạch năng lực: Số nhân sự điều phối bố trí theo giờ (3 ngày mẫu)", fontsize=13, fontweight="bold")
plt.xlabel("Thời gian")
plt.ylabel("Số nhân viên trực / ca giờ")
plt.legend(loc="upper right")
plt.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig("figures/staffing_schedule.png", dpi=200)
plt.close()

print("\nĐã lưu các biểu đồ vào thư mục figures/ (forecast_sample_week.png, staffing_schedule.png)")
print("=" * 70)
print("HOÀN TẤT!")
print("=" * 70)
