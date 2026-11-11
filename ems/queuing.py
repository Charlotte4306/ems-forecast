"""
Queuing Theory Module — EMS Vehicle Capacity Planning
======================================================
Biến dự báo call_count λ̂(t) thành số xe cần s(t) theo lý thuyết hàng đợi.

Lý thuyết:
  - Định luật Little  : a(t) = λ(t) × u × E[S]           (Erlang load)
  - Tiêu chí 1 (ρ≤0.8): s = ⌈a / ρ_max⌉                 (utilization cap)
  - Tiêu chí 2 (Erlang B): s = min s s.t. B(s,a) ≤ p_block  (loss prob.)
  - Tiêu chí 3 (Poisson):  s = ⌈a + z·√a⌉               (98% quantile)

References:
  - Little (1961) — L = λW
  - Erlang B formula — M/M/s/s loss system
  - Poisson quantile approx — Normal approx when a is large
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os
from typing import Dict, Optional

# ─────────────────────────────────────────────────────────────────────────────
# 0. Ước lượng tham số từ raw data hoặc dùng mặc định SF-EMS
# ─────────────────────────────────────────────────────────────────────────────

def estimate_service_params(
    raw_df: Optional[pd.DataFrame] = None,
    busy_col: str = "total_busy_sec",
    units_col: str = "n_units_dispatched",
    calls_col:  str = "call_count",
    default_E_S_hr: float = 63.38 / 60,  # 63,38 phút / lượt xe MEDIC (raw 2025)
    default_u: float = 1.0,              # call_count đã là số lượt điều xe
) -> Dict[str, float]:
    """
    Ước lượng E[S] (giờ/xe) và u (xe/cuộc gọi).

    Nếu raw_df được cung cấp và có đủ cột → tính từ dữ liệu thực.
    Nếu không → dùng giá trị ước lượng từ dữ liệu thô năm 2025 (tập validation):
      - E[S] = trung bình (available_dttm − dispatch_dttm) của 100.320 lượt điều
        xe MEDIC nhận trong 2025, bỏ giá trị < 0 hoặc > 24h (như notebook EDA)
        → 63,38 phút (median 70,3; p90 110,6).
      - u = 1.0: `call_count` trong y_*.csv khớp 100% với SỐ LƯỢT ĐIỀU XE mỗi giờ
        (không phải số cuộc gọi duy nhất, 94.420 trong 2025), nên λ đã gồm mọi
        xe; nhân thêm u (1,0625 lượt/cuộc gọi) sẽ bị tính hai lần.

    Trả về dict:
        {
            "E_S_sec": float,   # thời gian bận trung bình (giây)
            "E_S_hr":  float,   # thời gian bận trung bình (giờ)
            "u":       float,   # xe trung bình / cuộc gọi
            "source":  str,     # "data" hoặc "default"
        }
    """
    if raw_df is not None:
        cols_needed = {busy_col, units_col}
        if cols_needed.issubset(set(raw_df.columns)):
            E_S_sec = raw_df[busy_col].dropna().mean()
            E_S_hr  = E_S_sec / 3600.0

            if calls_col in raw_df.columns:
                # Tổng xe / tổng incidents (tránh chia 0)
                u = raw_df[units_col].sum() / max(raw_df[calls_col].sum(), 1)
            else:
                u = raw_df[units_col].dropna().mean()

            print(f"[Queuing] Tham số ước lượng từ raw data:")
            print(f"  E[S] = {E_S_sec:.0f} giây  = {E_S_hr:.4f} giờ")
            print(f"  u    = {u:.4f} xe/cuộc gọi")
            return {"E_S_sec": E_S_sec, "E_S_hr": E_S_hr, "u": u,
                    "source": "data"}

    # Fallback: giá trị ước lượng từ raw 2025
    print(f"[Queuing] Dùng tham số ước lượng từ raw 2025:")
    print(f"  E[S] = {default_E_S_hr * 3600:.0f} giây  = {default_E_S_hr:.4f} giờ")
    print(f"  u    = {default_u:.4f} xe/cuộc gọi")
    return {
        "E_S_sec": default_E_S_hr * 3600,
        "E_S_hr":  default_E_S_hr,
        "u":       default_u,
        "source":  "default (raw 2025 estimate)",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Định luật Little — Tính Erlang Load a(t)
# ─────────────────────────────────────────────────────────────────────────────

def compute_erlang_load(
    lambda_pred: np.ndarray,
    u: float,
    E_S_hr: float,
) -> np.ndarray:
    """
    Tính tải Erlang a(t) = λ(t) × u × E[S_hr].

    Định luật Little: số xe bận TB = tốc độ đến × số xe/call × thời gian phục vụ.

    Args:
        lambda_pred : (T,)  — dự báo call_count theo giờ (cuộc gọi/giờ)
        u           : float — xe trung bình / cuộc gọi
        E_S_hr      : float — thời gian bận TB (đơn vị GIỜ, không phải giây)

    Returns:
        a : (T,) — Erlang load (số xe bận trung bình tại mỗi giờ)
    """
    a = np.asarray(lambda_pred, dtype=float) * u * E_S_hr
    return np.maximum(a, 1e-9)   # tránh a=0 gây lỗi Erlang B


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ba tiêu chí chọn s(t)
# ─────────────────────────────────────────────────────────────────────────────

def vehicles_utilization(a: np.ndarray, rho_max: float = 0.80) -> np.ndarray:
    """
    Tiêu chí 1: Hệ số sử dụng ρ = a/s ≤ rho_max.

    → s = ⌈a / rho_max⌉

    Khi ρ > 0.85–0.9, thời gian chờ M/M/s bùng nổ phi tuyến.
    rho_max=0.8 cho buffer an toàn hợp lý với EMS.
    """
    return np.maximum(np.ceil(a / rho_max).astype(int), 1)


def _erlang_b_scalar(s: int, a: float) -> float:
    """
    Xác suất blocking Erlang B: P(tất cả s xe đều bận) — M/M/s/s loss system.

    Dùng công thức lặp (numerically stable, tránh overflow factorial lớn):
        inv_B(k, a) = 1 + inv_B(k-1, a) * k / a   với inv_B(0, a) = 1
        B(s, a) = 1 / inv_B(s, a)

    Phù hợp EMS vì không có hàng đợi — xe không đủ → chuyển tuyến.
    """
    if a <= 0:
        return 0.0
    inv_b = 1.0
    for k in range(1, s + 1):
        inv_b = 1.0 + inv_b * k / a
    return 1.0 / inv_b


def vehicles_erlang_b(
    a: np.ndarray,
    p_block: float = 0.05,
    s_max: int = 200,
) -> np.ndarray:
    """
    Tiêu chí 2: P(tất cả xe bận) ≤ p_block theo công thức Erlang B.

    Chọn s nhỏ nhất sao cho B(s, a) ≤ p_block.
    Mặc định p_block=0.05 → tối đa 5% thời gian phải gọi hỗ trợ ngoài.

    Phù hợp với EMS: hệ thống loss (không có hàng đợi).
    """
    result = np.empty(len(a), dtype=int)
    for i, ai in enumerate(a):
        s = max(1, int(np.ceil(ai)))
        while _erlang_b_scalar(s, ai) > p_block and s < s_max:
            s += 1
        result[i] = s
    return result


def vehicles_poisson_quantile(
    a: np.ndarray,
    z: float = 2.05,
) -> np.ndarray:
    """
    Tiêu chí 3: Quantile Poisson xấp xỉ Normal.

    Số xe bận tại bất kỳ thời điểm ~ Poisson(a).
    Quantile (1-α): s ≈ a + z·√a   (xấp xỉ Normal khi a đủ lớn)

    z = 2.05 → mức 98% (P(nhu cầu ≤ s) ≥ 0.98)
    z = 1.645 → 95%, z = 2.326 → 99%
    """
    return np.maximum(np.ceil(a + z * np.sqrt(a)).astype(int), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pipeline tổng hợp
# ─────────────────────────────────────────────────────────────────────────────

def forecast_to_vehicles(
    y_pred_dict: Dict[str, np.ndarray],
    u: float,
    E_S_hr: float,
    rho_max: float = 0.80,
    p_block: float = 0.05,
    z: float = 2.05,
    hour_index: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    """
    Pipeline chính: λ̂(t) → a(t) → s(t) theo 3 tiêu chí.

    Args:
        y_pred_dict : {"model_name": array(T,), ...}
                      mỗi array là dự báo call_count theo giờ
        u           : xe / cuộc gọi
        E_S_hr      : giờ bận / xe
        rho_max     : ngưỡng hệ số sử dụng (mặc định 0.8)
        p_block     : ngưỡng Erlang B (mặc định 0.05 = 5%)
        z           : z-score quantile Poisson (mặc định 2.05 = 98%)
        hour_index  : nhãn giờ tùy chọn (array T,)

    Returns:
        DataFrame cột: model | hour_index | lambda_pred | erlang_load_a
                        | s_rho80 | s_erlangB5pct | s_poisson98
    """
    rows = []
    for model_name, lambda_pred in y_pred_dict.items():
        lp = np.asarray(lambda_pred, dtype=float)
        a  = compute_erlang_load(lp, u, E_S_hr)

        s_rho  = vehicles_utilization(a, rho_max)
        s_eB   = vehicles_erlang_b(a, p_block)
        s_pois = vehicles_poisson_quantile(a, z)

        idx = hour_index if hour_index is not None else np.arange(len(lp))

        for t in range(len(lp)):
            rows.append({
                "model":          model_name,
                "hour_index":     int(idx[t]),
                "lambda_pred":    round(float(lp[t]), 3),
                "erlang_load_a":  round(float(a[t]),  4),
                "s_rho80":        int(s_rho[t]),
                "s_erlangB5pct":  int(s_eB[t]),
                "s_poisson98":    int(s_pois[t]),
            })

    df = pd.DataFrame(rows)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. Tóm tắt thống kê
# ─────────────────────────────────────────────────────────────────────────────

def summarize_vehicles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tóm tắt số xe cần theo model × tiêu chí.

    Returns DataFrame: model | criterion | min | mean | max | peak_hour
    """
    criteria = {
        "ρ ≤ 0.80":        "s_rho80",
        "Erlang B ≤ 5%":   "s_erlangB5pct",
        "Poisson 98%":     "s_poisson98",
    }
    rows = []
    for model, grp in df.groupby("model"):
        for crit_name, col in criteria.items():
            rows.append({
                "model":       model,
                "criterion":   crit_name,
                "min_vehicles":  int(grp[col].min()),
                "mean_vehicles": round(grp[col].mean(), 2),
                "max_vehicles":  int(grp[col].max()),
                "peak_hour":     int(grp.loc[grp[col].idxmax(), "hour_index"]),
            })
    return pd.DataFrame(rows)


def print_summary(df: pd.DataFrame):
    """In bảng tóm tắt đẹp ra console."""
    summary = summarize_vehicles(df)
    print(f"\n{'═'*72}")
    print(f"  Vehicle Requirements Summary — Queueing Theory")
    print(f"{'═'*72}")
    print(f"  {'Model':<22} {'Tiêu chí':<18} {'Min':>5} {'Mean':>7} "
          f"{'Max':>5} {'Peak h':>7}")
    print(f"  {'─'*66}")
    for _, row in summary.iterrows():
        print(f"  {row['model']:<22} {row['criterion']:<18} "
              f"{row['min_vehicles']:>5} {row['mean_vehicles']:>7.1f} "
              f"{row['max_vehicles']:>5} {row['peak_hour']:>7}")
    print(f"{'═'*72}\n")
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# 5. Visualizations
# ─────────────────────────────────────────────────────────────────────────────

_DARK_BG   = "#0f1117"
_PANEL_BG  = "#1a1d27"
_GRID_CLR  = "#2d3047"
_LABEL_CLR = "#c9d1d9"
_TICK_CLR  = "#8b949e"

_COLORS = {
    "s_rho80":       "#58a6ff",   # blue
    "s_erlangB5pct": "#f78166",   # orange-red
    "s_poisson98":   "#3fb950",   # green
    "lambda_pred":   "#bc8cff",   # purple
    "erlang_load_a": "#ffa657",   # amber
}

_CRIT_LABELS = {
    "s_rho80":       "ρ ≤ 0.80",
    "s_erlangB5pct": "Erlang B ≤ 5%",
    "s_poisson98":   "Poisson 98%",
}


def _setup_dark():
    plt.rcParams.update({
        "figure.facecolor":  _DARK_BG,
        "axes.facecolor":    _PANEL_BG,
        "axes.edgecolor":    "#3a3d4d",
        "axes.labelcolor":   _LABEL_CLR,
        "xtick.color":       _TICK_CLR,
        "ytick.color":       _TICK_CLR,
        "text.color":        _LABEL_CLR,
        "grid.color":        _GRID_CLR,
        "grid.linewidth":    0.6,
        "font.family":       "DejaVu Sans",
        "font.size":         10,
        "legend.framealpha": 0.3,
        "legend.fontsize":   9,
    })


def plot_vehicles_timeline(
    df: pd.DataFrame,
    model_name: str,
    n_hours: int = 24 * 14,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot số xe cần theo giờ (3 tiêu chí) + λ̂ + a cho một model.
    """
    _setup_dark()
    grp = df[df["model"] == model_name].head(n_hours).copy()
    t   = grp["hour_index"].values

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.patch.set_facecolor(_DARK_BG)

    # ── Panel trên: số xe theo 3 tiêu chí ──
    ax = axes[0]
    for col, label in _CRIT_LABELS.items():
        ax.plot(t, grp[col].values, lw=1.6, label=label,
                color=_COLORS[col], alpha=0.9)
    ax.set_ylabel("Số xe cần  s(t)", color=_LABEL_CLR)
    ax.set_title(f"Vehicle Requirements — {model_name}  "
                 f"(first {min(n_hours, len(grp))} hours)",
                 fontsize=12, pad=8)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.4)
    ax.set_ylim(bottom=0)

    # ── Panel dưới: λ̂ và Erlang load a ──
    ax2 = axes[1]
    ax2.plot(t, grp["lambda_pred"].values,  lw=1.4, label="λ̂(t) call_count",
             color=_COLORS["lambda_pred"], alpha=0.85)
    ax2.fill_between(t, 0, grp["lambda_pred"].values,
                     color=_COLORS["lambda_pred"], alpha=0.08)
    ax_r = ax2.twinx()
    ax_r.plot(t, grp["erlang_load_a"].values, lw=1.4, ls="--",
              label="a(t) Erlang load", color=_COLORS["erlang_load_a"], alpha=0.9)
    ax_r.set_ylabel("Erlang load  a(t)", color=_COLORS["erlang_load_a"])
    ax_r.tick_params(axis="y", colors=_COLORS["erlang_load_a"])

    ax2.set_xlabel("Hour index")
    ax2.set_ylabel("call_count / hour", color=_COLORS["lambda_pred"])
    ax2.tick_params(axis="y", colors=_COLORS["lambda_pred"])
    lines1, lab1 = ax2.get_legend_handles_labels()
    lines2, lab2 = ax_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, lab1 + lab2, loc="upper right")
    ax2.grid(True, alpha=0.4)

    fig.suptitle(f"EMS Capacity Planning — Queueing Theory  |  model={model_name}",
                 fontsize=13, color="#e6edf3", fontweight="bold", y=1.01)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  [Queuing] Plot saved → {save_path}")
    return fig


def plot_hourly_profile(
    df: pd.DataFrame,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Heatmap 24h profile: xe trung bình theo giờ trong ngày × model × tiêu chí.
    """
    _setup_dark()
    models = df["model"].unique()
    criteria_cols = ["s_rho80", "s_erlangB5pct", "s_poisson98"]

    # Tính profile 24h: group by (model, hour_of_day)
    df2 = df.copy()
    df2["hour_of_day"] = df2["hour_index"] % 24

    n_models = len(models)
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 5), sharey=False)
    fig.patch.set_facecolor(_DARK_BG)
    if n_models == 1:
        axes = [axes]

    for ax, model_name in zip(axes, models):
        grp = df2[df2["model"] == model_name]
        profile = grp.groupby("hour_of_day")[criteria_cols].mean()

        for col in criteria_cols:
            ax.plot(profile.index, profile[col], lw=1.8,
                    label=_CRIT_LABELS[col], color=_COLORS[col], marker="o",
                    markersize=3, alpha=0.9)

        # Vùng tô dưới tiêu chí nghiêm ngặt nhất (Erlang B)
        ax.fill_between(profile.index, 0, profile["s_erlangB5pct"],
                        color=_COLORS["s_erlangB5pct"], alpha=0.07)

        ax.set_title(model_name, fontsize=11, pad=6)
        ax.set_xlabel("Giờ trong ngày (0–23)")
        ax.set_ylabel("Số xe trung bình")
        ax.set_xticks(range(0, 24, 2))
        ax.grid(True, alpha=0.4)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=8)

    fig.suptitle("Vehicle Requirement Profile — Trung bình theo giờ trong ngày",
                 fontsize=12, color="#e6edf3", fontweight="bold", y=1.02)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  [Queuing] Profile plot saved → {save_path}")
    return fig


def plot_model_comparison(
    df: pd.DataFrame,
    criterion: str = "s_erlangB5pct",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    So sánh số xe cần giữa các model cho một tiêu chí.
    """
    _setup_dark()
    palette = ["#58a6ff", "#f78166", "#3fb950", "#bc8cff", "#ffa657"]
    models  = df["model"].unique()

    df2 = df.copy()
    df2["hour_of_day"] = df2["hour_index"] % 24
    profile_by_model = {
        m: df2[df2["model"] == m].groupby("hour_of_day")[criterion].mean()
        for m in models
    }

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor(_DARK_BG)

    for i, (m, profile) in enumerate(profile_by_model.items()):
        clr = palette[i % len(palette)]
        ax.plot(profile.index, profile.values, lw=2, label=m,
                color=clr, marker="o", markersize=3, alpha=0.9)
        ax.fill_between(profile.index, 0, profile.values,
                        color=clr, alpha=0.05)

    ax.set_xlabel("Giờ trong ngày (0–23)")
    ax.set_ylabel("Số xe trung bình")
    ax.set_title(
        f"So sánh Model — Tiêu chí: {_CRIT_LABELS.get(criterion, criterion)}",
        fontsize=12, pad=8,
    )
    ax.set_xticks(range(0, 24, 1))
    ax.grid(True, alpha=0.4)
    ax.set_ylim(bottom=0)
    ax.legend(framealpha=0.3)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  [Queuing] Comparison plot saved → {save_path}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Khối lượng công việc có xét xe bận xuyên giờ + bố trí ca + đánh giá
# ─────────────────────────────────────────────────────────────────────────────

# Kernel lan tỏa thời gian bận, ước lượng từ 100.320 lượt điều xe MEDIC năm 2025
# (raw: available_dttm − dispatch_dttm, bỏ < 0 hoặc > 24h). Phần tử k = số
# xe-giờ bận trung bình mà MỘT lượt điều xe đóng góp vào giờ (giờ nhận cuộc gọi + k).
# Tổng = 1,0559 xe-giờ ≈ E[S] = 63,38 phút; chỉ 34% rơi vào chính giờ nhận cuộc gọi.
BUSY_KERNEL_2025 = np.array([0.36049, 0.55752, 0.12673, 0.00918, 0.00151, 0.00044])


def workload_from_rate(
    rate: np.ndarray,
    kernel: np.ndarray = BUSY_KERNEL_2025,
    history: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Khối lượng công việc W(h) = Σ_k rate(h−k) · kernel[k]  (đơn vị: xe bận trung bình).

    rate    : số lượt điều xe theo giờ (thực tế hoặc dự báo)
    history : số lượt điều xe các giờ ngay TRƯỚC rate[0], để tính phần bận tràn
              sang những giờ đầu tiên. Thiếu → coi như 0.
    """
    rate = np.asarray(rate, dtype=float)
    kernel = np.asarray(kernel, dtype=float)
    n_hist = len(kernel) - 1
    hist = np.zeros(n_hist) if history is None else np.asarray(history, dtype=float)[-n_hist:]
    hist = np.pad(hist, (n_hist - len(hist), 0))
    full = np.concatenate([hist, rate])
    return np.convolve(full, kernel)[: len(full)][n_hist:]


def vehicles_needed(workload: np.ndarray, rho_max: float = 0.80) -> np.ndarray:
    """Số xe để hệ số sử dụng trung bình W/s ≤ rho_max:  s = ⌈W / rho_max⌉ (tối thiểu 1)."""
    s = np.ceil(np.asarray(workload, dtype=float) / rho_max - 1e-9)
    return np.maximum(s, 1).astype(int)


SHIFT_PATTERNS = {
    "3 ca × 8h (07–15, 15–23, 23–07)": (7, 8),
    "2 ca × 12h (07–19, 19–07)": (7, 12),
}


def shift_plan(timestamps, hourly_vehicles, start_hour: int = 7, length: int = 8):
    """
    Quy đổi nhu cầu xe theo giờ thành số xe mỗi ca: lấy mức CAO NHẤT trong ca.

    Trả về (plan_theo_giờ, shift_start) — cả hai là Series theo từng giờ;
    shift_start là thời điểm bắt đầu ca chứa giờ đó (dùng để gom theo ca).
    """
    ts = pd.DatetimeIndex(timestamps)
    values = pd.Series(np.asarray(hourly_vehicles), index=ts)
    shift_start = (ts - pd.Timedelta(hours=start_hour)).floor(f"{length}h") + pd.Timedelta(hours=start_hour)
    shift_start = pd.Series(shift_start, index=ts)
    plan = values.groupby(shift_start.values).transform("max")
    return plan, shift_start


def evaluate_plan(plan, need, shift_start=None, cost_ratios=(2, 3, 5)) -> Dict[str, float]:
    """
    So kế hoạch với số xe thực cần (cùng từng giờ).

    Chi phí tính theo đơn vị "xe-giờ thừa": 1 xe-giờ thừa = 1, 1 xe-giờ thiếu = r
    (r = cost_ratios) — chưa phải chi phí tiền thật, dùng để so các phương án.
    """
    plan, need = np.asarray(plan, dtype=float), np.asarray(need, dtype=float)
    short = np.clip(need - plan, 0, None)
    excess = np.clip(plan - need, 0, None)
    result = {
        "Xe-giờ bố trí": plan.sum(),
        "Xe-giờ thiếu": short.sum(),
        "Xe-giờ thừa": excess.sum(),
        "% giờ thiếu xe": (short > 0).mean() * 100,
        "Thiếu TB khi thiếu (xe)": short[short > 0].mean() if (short > 0).any() else 0.0,
        "Thiếu lớn nhất (xe)": short.max(),
    }
    if shift_start is not None:
        any_short = pd.Series(short > 0).groupby(np.asarray(shift_start)).any()
        result["% ca có giờ thiếu"] = any_short.mean() * 100
    for r in cost_ratios:
        result[f"Chi phí (thiếu = {r}× thừa)"] = excess.sum() + r * short.sum()
    return result
