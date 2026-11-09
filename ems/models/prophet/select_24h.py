"""Select one of the four existing Prophet configurations on day-ahead validation."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from ems.data import REGRESSORS, ROOT, load_split
from ems.evaluation import compute_metrics
from ems.models.prophet.forecast import forecast_24h
from ems.models.prophet.model import SEED, build_model, save_model


def select_day_ahead(data_dir=ROOT / "data",
                     output_dir=ROOT / "outputs/prophet/day_ahead_24h/selection",
                     checkpoint_dir=ROOT / "checkpoints/prophet/day_ahead_24h"):
    """Fit train only, rank full validation by MAE, never read or evaluate test."""
    data_dir, output_dir, checkpoint_dir = map(Path, (data_dir, output_dir, checkpoint_dir))
    original_output = (ROOT / "outputs/prophet").resolve()
    original_checkpoint = (ROOT / "checkpoints/prophet").resolve()
    if output_dir.resolve() in {original_output, original_checkpoint} or checkpoint_dir.resolve() in {
            original_output, original_checkpoint}:
        raise ValueError("Use separate 24-hour output/checkpoint directories")
    if output_dir.resolve() == checkpoint_dir.resolve():
        raise ValueError("Output and checkpoint directories must differ")
    started = time.perf_counter()
    train, val = (load_split(data_dir, split) for split in ("train", "val"))
    if val.ds.iloc[0] - train.ds.iloc[-1] != pd.Timedelta(hours=1):
        raise ValueError("Train and validation must be consecutive")
    if len(val) % 24:
        raise ValueError("Selection requires complete validation days")
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    records, best, best_predictions = [], None, None
    for regressors in (False, True):
        for prior in (0.01, 0.05):
            name = f"prophet_{'lags' if regressors else 'seasonal'}_cp{prior}"
            print(f"24h validation: fitting {name} on train only ...", flush=True)
            tick = time.perf_counter()
            np.random.seed(SEED)
            model = build_model(prior, regressors)
            model.fit(train[["ds", "y", *(REGRESSORS if regressors else [])]], seed=SEED)
            predictions = forecast_24h(model, train, val)
            predictions["seasonal_naive_168h"] = val.lag_168h.to_numpy()
            row = {"name": name, "use_regressors": regressors,
                   "changepoint_prior_scale": prior, "n_hours": len(predictions),
                   **compute_metrics(predictions.y, predictions.yhat),
                   "elapsed_seconds": time.perf_counter() - tick}
            records.append(row)
            predictions.to_csv(output_dir / f"{name}_validation_predictions.csv", index=False)
            pd.DataFrame(records).to_csv(output_dir / "validation_results.csv", index=False)
            print(f"  {len(predictions)} hours: MAE={row['MAE']:.6f}, MAPE={row['MAPE (%)']:.4f}%", flush=True)
            if best is None or row["MAE"] < best["MAE"]:
                best, best_predictions = row, predictions
                save_model(model, checkpoint_dir / "best_model.json")
    metadata = {
        "experiment": "prophet_day_ahead_24h_selection", "selected": best,
        "selection_metric": "full-precision MAE on all validation hours, horizon 24h",
        "seed": SEED, "horizon_hours": 24,
        "protocol": "Fit each candidate on train only; issue 24 forecasts at midnight; recursively update features; reveal actuals after full day. No train+validation refit.",
        "test_evaluated": False,
        "target": "MEDIC dispatch-response rows per call-received hour (legacy column: call_count)",
        "training_end": str(train.ds.iloc[-1]),
        "validation_start": str(val.ds.iloc[0]), "validation_end": str(val.ds.iloc[-1]),
        "n_validation_hours": len(val), "n_validation_days": len(val) // 24,
        "candidates": records,
        "seasonal_naive_168h": compute_metrics(val.y, val.lag_168h),
        "regressors": REGRESSORS if best["use_regressors"] else [],
        "versions": {p: version(p) for p in ("prophet", "pandas", "numpy")},
        "data_sha256": {f"{prefix}_{split}.csv": hashlib.sha256(
            (data_dir / f"{prefix}_{split}.csv").read_bytes()).hexdigest()
            for prefix in ("X", "y") for split in ("train", "val")},
        "checkpoint_sha256": hashlib.sha256((checkpoint_dir / "best_model.json").read_bytes()).hexdigest(),
        "elapsed_seconds": time.perf_counter() - started,
        "comparability": "Other models must use the same issue times, evaluation hours and agreed training/refit policy. Validation selection score is not test performance.",
    }
    content = json.dumps(metadata, indent=2, allow_nan=False)
    (checkpoint_dir / "metadata.json").write_text(content, encoding="utf-8")
    (output_dir / "selection.json").write_text(content, encoding="utf-8")
    best_predictions.to_csv(output_dir / "best_validation_predictions.csv", index=False)
    pd.DataFrame([{"lead_hour": int(lead), "n_hours": len(part),
                   **compute_metrics(part.y, part.yhat)}
                  for lead, part in best_predictions.groupby("lead_hour")]).to_csv(
                      output_dir / "best_metrics_by_lead.csv", index=False)
    print(json.dumps({"selected": best, "baseline": metadata["seasonal_naive_168h"],
                      "checkpoint_dir": str(checkpoint_dir), "test_evaluated": False}, indent=2), flush=True)
    return metadata
