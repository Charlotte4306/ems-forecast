"""Day-ahead backtesting with a frozen Prophet checkpoint and recursive features."""
from collections import deque
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from ems.data import REGRESSORS, ROOT, load_data
from ems.evaluation import compute_metrics
from ems.models.prophet.model import load_model, predict


class _History:
    """Observed/recursive history; exported EWM columns are shifted by one hour."""

    def __init__(self, history):
        self.values = deque(history.y.iloc[-168:].astype(float), maxlen=168)
        last = history.iloc[-1]
        self.ewm = {
            span: (2 / (span + 1)) * float(last.y)
            + (1 - 2 / (span + 1)) * float(last[f"ewm_{span}h"])
            for span in (24, 168)
        }

    def copy(self):
        copied = object.__new__(_History)
        copied.values, copied.ewm = self.values.copy(), self.ewm.copy()
        return copied

    def observe(self, value):
        value = float(value)
        self.values.append(value)
        for span in self.ewm:
            alpha = 2 / (span + 1)
            self.ewm[span] = alpha * value + (1 - alpha) * self.ewm[span]

    def features(self, timestamp):
        values = np.asarray(self.values)
        row = {"ds": timestamp}
        for lag in (1, 2, 3, 6, 12, 24, 48, 168):
            row[f"lag_{lag}h"] = values[-lag]
        for window in (24, 168):
            row[f"rolling_mean_{window}h"] = float(values[-window:].mean())
            row[f"rolling_std_{window}h"] = float(values[-window:].std(ddof=1))
            row[f"ewm_{window}h"] = self.ewm[window]
        return pd.DataFrame([row])


def _additive_predictor(model, dates):
    """Cache calendar effects; keep recursive regressors linear on original scale.

    Equivalent to Prophet.predict for fitted MAP models with additive regressors.
    Other models fall back to the public predict path.
    """
    from prophet import Prophet
    from prophet.utilities import regressor_coefficients

    if not isinstance(model, Prophet) or model.mcmc_samples:
        return None
    if any(params["mode"] != "additive" for params in model.extra_regressors.values()):
        return None
    calendar = pd.DataFrame({"ds": dates.to_numpy()})
    names, centers, coefficients = [], [], []
    if model.extra_regressors:
        summary = regressor_coefficients(model).set_index("regressor")
        for name in model.extra_regressors:
            names.append(name)
            centers.append(float(summary.loc[name, "center"]))
            coefficients.append(float(summary.loc[name, "coef"]))
            calendar[name] = centers[-1]
    # Do not clip before adding regressor effects: only the final yhat is clipped.
    baseline = model.predict(calendar).yhat.to_numpy()
    centers, coefficients = np.asarray(centers), np.asarray(coefficients)

    def estimate(index, features):
        effect = np.dot(features[names].iloc[0].to_numpy(dtype=float) - centers,
                        coefficients) if names else 0.0
        return max(0.0, float(baseline[index] + effect))

    return estimate


def forecast_24h(model, history, evaluation, max_days=None, fast=True):
    """Forecast complete calendar days, reveal actuals only after each 24h block.

    Only ds/y and the historical EWM seed are consumed. Evaluation feature
    columns are deliberately ignored, since they can contain within-day actuals.
    forecast_origin is the issue time (00:00); history_cutoff is the last known
    hourly bucket (23:00 of the previous day). Timestamps keep input conventions.
    """
    if max_days is not None and (not isinstance(max_days, int) or max_days < 1):
        raise ValueError("max_days must be a positive integer")
    if len(history) < 168 or evaluation.empty:
        raise ValueError("Need at least 168 historical hours and non-empty evaluation")
    dates = pd.DatetimeIndex(pd.concat([history.ds, evaluation.ds], ignore_index=True))
    if dates.hasnans or not (dates[1:] - dates[:-1] == pd.Timedelta(hours=1)).all():
        raise ValueError("History/evaluation must be continuous, unique hourly timestamps")
    if evaluation.ds.iloc[0] != evaluation.ds.iloc[0].normalize():
        raise ValueError("Day-ahead evaluation must start at midnight")
    for frame in (history, evaluation):
        if not np.isfinite(frame.y).all() or (frame.y < 0).any():
            raise ValueError("Targets must be finite and non-negative")
    if not np.isfinite(history.iloc[-1][["ewm_24h", "ewm_168h"]].to_numpy(dtype=float)).all():
        raise ValueError("Historical EWM seed must be finite")
    unsupported = set(model.extra_regressors) - set(REGRESSORS)
    if unsupported:
        raise ValueError(f"Unsupported recursive regressors: {sorted(unsupported)}")
    fitted_history = getattr(model, "history", None)
    if fitted_history is not None and not fitted_history.empty:
        if pd.to_datetime(fitted_history.ds).max() >= evaluation.ds.iloc[0]:
            raise ValueError("Checkpoint was fitted on evaluation/future timestamps")
    days = len(evaluation) // 24
    if max_days is not None:
        days = min(days, max_days)
    if not days:
        raise ValueError("Need at least one complete 24-hour day")

    cached_predict = _additive_predictor(model, evaluation.ds.iloc[:days * 24]) if fast else None
    observed = _History(history)
    rows = []
    for day in range(days):
        block = evaluation.iloc[day * 24:(day + 1) * 24]
        recursive = observed.copy()
        origin = block.ds.iloc[0]
        for lead, timestamp in enumerate(block.ds, 1):
            features = recursive.features(timestamp)
            estimate = (cached_predict(day * 24 + lead - 1, features) if cached_predict
                        else float(predict(model, features).yhat.iloc[0]))
            if not np.isfinite(estimate):
                raise ValueError("Model returned a non-finite forecast")
            rows.append({"forecast_origin": origin,
                         "history_cutoff": origin - pd.Timedelta(hours=1),
                         "lead_hour": lead, "ds": timestamp, "yhat": estimate})
            recursive.observe(estimate)
        # None of this day's targets enter predictions made at its origin.
        for value in block.y:
            observed.observe(value)
    result = pd.DataFrame(rows)
    result["y"] = evaluation.y.iloc[:len(result)].to_numpy()
    return result


def run_day_ahead(data_dir=ROOT / "data", checkpoint_dir=ROOT / "checkpoints/prophet",
                  output_dir=ROOT / "outputs/prophet/day_ahead_24h", split="test",
                  max_days=None):
    """Evaluate a saved model without fitting or overwriting the checkpoint."""
    if split not in ("val", "test"):
        raise ValueError("split must be val or test")
    data_dir, checkpoint_dir, output_dir = map(Path, (data_dir, checkpoint_dir, output_dir))
    # Reserve a distinct folder so the original one-hour experiment is preserved.
    if output_dir.resolve() in {(ROOT / "outputs/prophet").resolve(), checkpoint_dir.resolve()}:
        raise ValueError("Use a separate output directory for the 24-hour experiment")
    started = time.perf_counter()
    splits = load_data(data_dir)
    history = splits["train"] if split == "val" else pd.concat(
        [splits["train"], splits["val"]], ignore_index=True)
    checkpoint = checkpoint_dir / "best_model.json"
    model = load_model(checkpoint)
    frame = forecast_24h(model, history, splits[split], max_days)
    # Lag 168 is known at every day-ahead origin, unlike naive lag 1.
    frame["seasonal_naive_168h"] = splits[split].lag_168h.iloc[:len(frame)].to_numpy()
    score = lambda part: compute_metrics(part.y, part.yhat)
    by_lead = [{"lead_hour": int(lead), "n_hours": len(part), **score(part)}
               for lead, part in frame.groupby("lead_hour")]
    by_day = [{"forecast_origin": str(origin), **score(part)}
              for origin, part in frame.groupby("forecast_origin")]
    metadata = {
        "experiment": "prophet_day_ahead_24h", "split": split,
        "target": "MEDIC dispatch-response rows per call-received hour (legacy column: call_count)",
        "horizon_hours": 24, "issue_time": "00:00 after observing the previous 23:00 bucket",
        "protocol": "Frozen checkpoint; recursive lag/rolling/EWM within each day; actuals revealed only after the full day; no refitting.",
        "model_selection": "Reuses existing checkpoint; this run does NOT select hyperparameters for 24-hour forecasting.",
        "comparability": "Compare only identical issue times, evaluated hours, training/refit policies and metrics. This run alone does not harmonize other models.",
        "time_convention": "Naive hourly timestamps from source CSV; no timezone conversion.",
        "checkpoint_fit_end": str(pd.to_datetime(model.history.ds).max()),
        "observation_cutoff_at_first_origin": str(history.ds.iloc[-1]),
        "evaluation_start": str(frame.ds.iloc[0]), "evaluation_end": str(frame.ds.iloc[-1]),
        "n_hours": len(frame), "n_days": len(frame) // 24,
        "incomplete_tail_hours_excluded": len(splits[split]) % 24,
        "max_days": max_days, "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "metrics": score(frame),
        "seasonal_naive_168h": compute_metrics(frame.y, frame.seasonal_naive_168h),
        "by_lead_hour": by_lead,
        "data_sha256": {f"{prefix}_{name}.csv": hashlib.sha256(
            (data_dir / f"{prefix}_{name}.csv").read_bytes()).hexdigest()
            for prefix in ("X", "y") for name in splits},
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "predictions_24h.csv", index=False)
    pd.DataFrame(by_lead).to_csv(output_dir / "metrics_by_lead.csv", index=False)
    pd.DataFrame(by_day).to_csv(output_dir / "metrics_by_day.csv", index=False)
    (output_dir / "metrics.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "n_days": metadata["n_days"],
                      "metrics": metadata["metrics"], "elapsed_seconds": metadata["elapsed_seconds"]},
                     indent=2), flush=True)
    return metadata
