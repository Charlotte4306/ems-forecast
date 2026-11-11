"""Illustrative hourly dispatcher staffing; not ambulance fleet optimization."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ems.models.sarimax.model import baselines, load_series, metrics
from ems.paths import DATA_DIR, OUTPUT_DIR


def read_predictions(path, expected):
    frame = pd.read_csv(path, parse_dates=["timestamp"]).set_index("timestamp")
    columns = ["actual", "pred", "lo", "hi"]
    if not set(columns).issubset(frame.columns):
        raise ValueError("Predictions require timestamp, actual, pred, lo and hi")
    if not frame.index.equals(expected.index) or not np.array_equal(frame.actual, expected):
        raise ValueError("Saved prediction timestamps/actual values must match the complete test split")
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Saved predictions require finite non-negative values")
    if not ((frame.lo <= frame.pred) & (frame.pred <= frame.hi)).all():
        raise ValueError("Prediction interval bounds must enclose the point forecast")
    return frame[columns]


def capacity_summary(frame, baseline_predictions, mu=3.0, cost_over=30.0, cost_under=75.0):
    if not np.isfinite([mu, cost_over, cost_under]).all() or mu <= 0 or min(cost_over, cost_under) < 0:
        raise ValueError("Productivity must be positive and costs must be finite and non-negative")
    required = np.ceil(frame.actual / mu).astype(int)
    strategies = {**baseline_predictions, "SARIMAX (Dự báo điểm)": frame.pred,
                  "SARIMAX (Chặn trên 80% CI)": frame.hi}
    records, schedules = [], {}
    for name, values in strategies.items():
        assigned = np.ceil(values / mu).astype(int)
        schedules[name] = assigned
        excess, shortage = (assigned - required).clip(lower=0), (required - assigned).clip(lower=0)
        over, under = float(excess.sum() * cost_over), float(shortage.sum() * cost_under)
        records.append({
            "Chiến lược": name, "Đúng công suất (%)": round(float((assigned == required).mean() * 100), 1),
            "Thừa nhân sự (%)": round(float((assigned > required).mean() * 100), 1),
            "Thiếu nhân sự (%)": round(float((assigned < required).mean() * 100), 1),
            "Tổng giờ thiếu": int(shortage.sum()), "Tổng giờ thừa": int(excess.sum()),
            "Chi phí Thừa ($)": over, "Chi phí Thiếu ($)": under, "TỔNG CHI PHÍ ($)": over + under,
        })
    summary = pd.DataFrame(records)
    reference = float(summary.loc[summary["Chiến lược"] == "Lịch sử Giờ x Thứ", "TỔNG CHI PHÍ ($)"].iloc[0])
    summary["Tiết kiệm vs Baseline ($)"] = reference - summary["TỔNG CHI PHÍ ($)"]
    summary["% Giảm chi phí"] = (100 * summary["Tiết kiệm vs Baseline ($)"] / reference).round(2) if reference else None
    schedule = pd.DataFrame({"actual_required": required, **schedules}, index=frame.index)
    return summary, schedule


def plot_reports(frame, summary, schedule, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = Path(output_dir) / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    start = 168 if len(frame) > 168 else 0
    sample = frame.iloc[start:start + 168]
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(sample.index, sample.actual, label="Observed", color="#376fad")
    ax.plot(sample.index, sample.pred, "--", label="SARIMAX", color="#087e8b")
    ax.fill_between(sample.index, sample.lo, sample.hi, alpha=.2, color="#087e8b", label="80% prediction interval")
    ax.set(title="Hourly EMS demand - historical test replay", ylabel="Calls / hour")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "forecast_sample_week.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    sample_schedule = schedule.iloc[start:start + 96]
    for column, label in [("actual_required", "Required under assumed productivity"),
                          ("SARIMAX (Dự báo điểm)", "SARIMAX point forecast"),
                          ("Lịch sử Giờ x Thứ", "Historical profile")]:
        ax.step(sample_schedule.index, sample_schedule[column], where="mid", label=label)
    ax.set(title="Illustrative dispatcher staffing (not ambulance fleet)", ylabel="Dispatchers / hour")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "staffing_schedule.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(summary))
    ax.bar(x - .18, summary["Chi phí Thừa ($)"], .36, label="Excess staffing cost")
    ax.bar(x + .18, summary["Chi phí Thiếu ($)"], .36, label="Shortage penalty")
    ax.set_xticks(x, ["Seasonal naive", "Historical profile", "SARIMAX point", "SARIMAX upper bound"])
    ax.set(title="Illustrative costs under stated assumptions", ylabel="USD (scenario)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "cost_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    errors = (frame.actual - frame.pred).abs().groupby(frame.index.hour // 6).mean()
    bars = ax.bar(errors.index, errors.values, color="#376fad")
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.set_xticks(range(4), ["00-05", "06-11", "12-17", "18-23"])
    ax.set(title="SARIMAX error by hour of day", ylabel="MAE (calls / hour)", xlabel="Hour range")
    ax.set_ylim(0, float(errors.max()) * 1.2)
    fig.tight_layout()
    fig.savefig(figures / "hourly_mae.png", dpi=180)
    plt.close(fig)


def run_capacity(data_dir=DATA_DIR, prediction_path=OUTPUT_DIR / "sarimax/pred_sarimax.csv",
                 output_dir=OUTPUT_DIR / "sarimax", mu=3.0, cost_over=30.0,
                 cost_under=75.0, window_hours=8760):
    if window_hours < 168:
        raise ValueError("History window must contain at least 168 hours")
    splits = load_series(Path(data_dir))
    frame = read_predictions(prediction_path, splits["test"])
    history = pd.concat([splits["train"], splits["val"]]).iloc[-window_hours:]
    predictions = baselines(history, frame.actual)
    summary, schedule = capacity_summary(frame, predictions, mu, cost_over, cost_under)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "capacity_cost_evaluation.csv", index=False)
    schedule.rename_axis("timestamp").to_csv(output_dir / "staffing_schedule.csv")
    report = {
        "source_predictions": str(Path(prediction_path).resolve()),
        "assumptions": {"calls_per_dispatcher_hour": mu, "excess_cost_per_person_hour_usd": cost_over,
                        "shortage_cost_per_person_hour_usd": cost_under, "history_window_hours": window_hours},
        "limitations": "Illustrative dispatcher-hour scenario, not actual costs, staffing roster optimization, waiting-time SLA or ambulance fleet needs. The upper endpoint of a central 80% interval is the nominal 90th percentile, not an 80% service-level guarantee.",
        "all_test": {"rows": len(frame), **metrics(frame)},
        "lstm_seq24_aligned": {"rows": len(frame.iloc[24:]), **metrics(frame.iloc[24:])},
        "baselines": {name: metrics(pd.DataFrame({"actual": frame.actual, "pred": values}))
                      for name, values in predictions.items()},
    }
    (output_dir / "capacity_metadata.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    plot_reports(frame, summary, schedule, output_dir)
    print(f"Evaluated {len(frame)} hours; reports: {output_dir}", flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--predictions", type=Path, default=OUTPUT_DIR / "sarimax/pred_sarimax.csv")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "sarimax")
    parser.add_argument("--mu", type=float, default=3.0)
    parser.add_argument("--cost-over", type=float, default=30.0)
    parser.add_argument("--cost-under", type=float, default=75.0)
    parser.add_argument("--window-hours", type=int, default=8760)
    args = parser.parse_args(argv)
    run_capacity(args.data_dir, args.predictions, args.output_dir,
                 args.mu, args.cost_over, args.cost_under, args.window_hours)


if __name__ == "__main__":
    main()
