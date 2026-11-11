"""Validate saved forecasts and regenerate forecast reports without fitting."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ems.models.sarimax.model import load_series, metrics
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


def evaluate_saved(data_dir=DATA_DIR, prediction_path=OUTPUT_DIR / "sarimax/norefit/pred_sarimax.csv",
                   output_dir=OUTPUT_DIR / "sarimax/norefit"):
    frame = read_predictions(prediction_path, load_series(Path(data_dir))["test"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"rows": len(frame), "unit": "dispatches/hour", "metrics": metrics(frame),
              "interval_level": 0.8,
              "interval_coverage_percent": float(((frame.actual >= frame.lo) & (frame.actual <= frame.hi)).mean() * 100)}
    (output_dir / "forecast_evaluation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = output_dir / "figures"
    figures.mkdir(exist_ok=True)
    sample = frame.iloc[168:336] if len(frame) > 168 else frame
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(sample.index, sample.actual, label="Observed")
    ax.plot(sample.index, sample.pred, "--", label="SARIMAX")
    ax.fill_between(sample.index, sample.lo, sample.hi, alpha=.2, label="80% prediction interval")
    ax.set(title="Historical test forecast", ylabel="MEDIC dispatches / hour")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "forecast_sample_week.png", dpi=180)
    plt.close(fig)

    errors = (frame.actual - frame.pred).abs().groupby(frame.index.hour).mean()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(errors.index, errors.values)
    ax.set(title="SARIMAX error by hour", xlabel="Hour", ylabel="MAE (dispatches / hour)")
    fig.tight_layout()
    fig.savefig(figures / "hourly_mae.png", dpi=180)
    plt.close(fig)
    return report
