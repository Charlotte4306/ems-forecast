"""Dispatch workload, fleet scenarios and complete-shift evaluation.

The utilization cap and Erlang/Poisson criteria are modeling assumptions;
they do not establish a response-time or service-level guarantee.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Optional


def estimate_service_params(default_E_S_hr: float = 63.38 / 60,
                            default_u: float = 1.0) -> Dict[str, float]:
    """Frozen 2025 service-duration estimate, in hours per dispatch.

    Raw audit: 100,320 MEDIC response rows, 99,708 positive valid durations;
    99,694 completed within the calibration window, mean 63.3805 minutes.
    The planning scenario retains the rounded 63.38-minute value. Since the
    target already counts individual dispatches, the multiplicity factor u=1.
    This helper does not infer service durations from hourly counts.
    """
    return {"E_S_sec": default_E_S_hr * 3600, "E_S_hr": default_E_S_hr,
            "u": default_u, "source": "default (raw 2025 estimate)"}


def _erlang_b_scalar(s: int, a: float) -> float:
    """Stable Erlang B recursion for the stationary M/M/s/s loss-system scenario.

    This assumption has not been validated as a description of SF EMS dispatch."""
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
    """Smallest fleet meeting the Erlang B blocking threshold, capped at s_max.

    The threshold applies within the stationary M/M/s/s model, not to measured
    EMS waiting times or an operational service-level guarantee."""
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
    """Normal approximation ceil(a + z*sqrt(a)) under a Poisson occupancy scenario.

    z=2.05 is approximately the 98th normal percentile. This is not an exact
    Poisson quantile or a guarantee of empirical dispatch coverage."""
    return np.maximum(np.ceil(a + z * np.sqrt(a)).astype(int), 1)


# Frozen 2025 carryover kernel. See reports/medic_busy_time.md for
# provenance and limits; the raw-duration audit does not regenerate this kernel.


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
    "3 ca × 8h (00–08, 08–16, 16–24)": (0, 8),
    "2 ca × 12h (00–12, 12–24)": (0, 12),
}


def shift_plan(timestamps, hourly_vehicles, start_hour: int = 0, length: int = 8):
    """
    Quy đổi nhu cầu xe theo giờ thành số xe mỗi ca: lấy mức CAO NHẤT trong ca.

    Trả về (plan_theo_giờ, shift_start) — cả hai là Series theo từng giờ;
    shift_start là thời điểm bắt đầu ca chứa giờ đó (dùng để gom theo ca).
    Ca thiếu giờ ở đầu/cuối được đánh dấu NaN, không suy lịch ca từ một phần ca.
    """
    ts = pd.DatetimeIndex(timestamps)
    if not len(ts) or ts.hasnans or not ts.is_unique or not ts.is_monotonic_increasing:
        raise ValueError("Expected non-empty, ordered, unique hourly timestamps")
    if not ((ts.minute == 0) & (ts.second == 0) & (ts.microsecond == 0) & (ts.nanosecond == 0)).all():
        raise ValueError("Shift timestamps must start at an exact hour")
    if len(ts) > 1 and not ((ts[1:] - ts[:-1]) == pd.Timedelta(hours=1)).all():
        raise ValueError("Shift timestamps must be contiguous hourly observations")
    if length not in (8, 12) or not isinstance(start_hour, int) or not 0 <= start_hour < 24:
        raise ValueError("Expected an 8h/12h shift and start_hour in 0..23")
    hourly_vehicles = np.asarray(hourly_vehicles, dtype=float)
    if hourly_vehicles.shape != (len(ts),) or not np.isfinite(hourly_vehicles).all() or (hourly_vehicles < 0).any():
        raise ValueError("Expected aligned finite non-negative hourly vehicle counts")
    values = pd.Series(hourly_vehicles, index=ts)
    shift_start = (ts - pd.Timedelta(hours=start_hour)).floor(f"{length}h") + pd.Timedelta(hours=start_hour)
    shift_start = pd.Series(shift_start, index=ts)
    plan = values.groupby(shift_start.values).transform("max")
    complete = values.groupby(shift_start.values).transform("size") == length
    plan = plan.where(complete)
    return plan, shift_start


def evaluate_plan(plan, need, shift_start=None, cost_ratios=(2, 3, 5)) -> Dict[str, float]:
    """
    So kế hoạch với nhu cầu xe đối chiếu theo mô hình (cùng từng giờ).

    Chi phí tính theo đơn vị "xe-giờ thừa": 1 xe-giờ thừa = 1, 1 xe-giờ thiếu = r
    (r = cost_ratios) — chưa phải chi phí tiền thật, dùng để so các phương án.
    Có shift_start: bỏ các giờ plan=NaN do ca chưa đầy đủ; xuất rõ số giờ bị loại.
    Không có shift_start: chấm toàn bộ giờ, không cho phép giá trị thiếu.
    """
    plan, need = np.asarray(plan, dtype=float), np.asarray(need, dtype=float)
    if plan.ndim != 1 or plan.shape != need.shape or not len(plan):
        raise ValueError("Expected aligned non-empty hourly plan and need arrays")
    if not np.isfinite(need).all() or (need < 0).any() or np.isinf(plan).any():
        raise ValueError("Expected finite need values and no infinite plan values")
    excluded = 0
    if shift_start is not None:
        shift_start = np.asarray(shift_start)
        if shift_start.shape != plan.shape:
            raise ValueError("Shift identifiers must match the plan hours")
        valid = np.isfinite(plan)
        excluded = int((~valid).sum())
        plan, need, shift_start = plan[valid], need[valid], shift_start[valid]
    if not len(plan) or not np.isfinite(plan).all() or (plan < 0).any():
        raise ValueError("No complete shifts to evaluate, or invalid hourly plan")
    short = np.clip(need - plan, 0, None)
    excess = np.clip(plan - need, 0, None)
    result = {
        "Số giờ đánh giá": len(plan),
        "Số giờ loại (ca chưa đủ)": excluded,
        "Xe-giờ bố trí": plan.sum(),
        "Xe-giờ thiếu": short.sum(),
        "Xe-giờ thừa": excess.sum(),
        "% giờ thiếu xe": (short > 0).mean() * 100,
        "Thiếu TB khi thiếu (xe)": short[short > 0].mean() if (short > 0).any() else 0.0,
        "Thiếu lớn nhất (xe)": short.max(),
    }
    if shift_start is not None:
        any_short = pd.Series(short > 0).groupby(np.asarray(shift_start)).any()
        result["Số ca đánh giá"] = len(any_short)
        result["% ca có giờ thiếu"] = any_short.mean() * 100
    for r in cost_ratios:
        result[f"Chi phí (thiếu = {r}× thừa)"] = excess.sum() + r * short.sum()
    return result
