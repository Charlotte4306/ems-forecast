"""Select on validation, refit the latest year, forecast test in 24-hour blocks."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time

import pandas as pd

from ems.models.sarimax.model import GRID, baselines, load_series, make_exog, metrics, rolling_forecast
from ems.paths import CHECKPOINT_DIR, DATA_DIR, OUTPUT_DIR


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def fit_model(series, order, K, maxiter, optimizer="powell"):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    result = SARIMAX(series, exog=make_exog(series.index, K), order=order, trend="c").fit(
        method=optimizer, disp=False, maxiter=maxiter)
    # Keep warnings visible and do not silently publish a failed fit.
    if not result.mle_retvals.get("converged", False):
        raise RuntimeError(f"SARIMAX order={order}, K={K} did not converge within {maxiter} iterations")
    return result


def run_experiment(data_dir=DATA_DIR, output_dir=OUTPUT_DIR / "sarimax",
                   checkpoint_dir=CHECKPOINT_DIR / "sarimax", window_hours=8760,
                   horizon=24, maxiter=300, candidates=GRID, optimizer="powell"):
    if window_hours < 168 or not 1 <= horizon <= 168 or maxiter < 1:
        raise ValueError("window_hours >= 168, 1 <= horizon <= 168 and maxiter >= 1 required; seasonal lag-168 baseline must be available at each block origin")
    if optimizer not in ("powell", "lbfgs"):
        raise ValueError("Optimizer must be powell or lbfgs")
    from ems.models.sarimax.capacity_planning import run_capacity
    start = time.perf_counter()
    data_dir, output_dir, checkpoint_dir = map(Path, (data_dir, output_dir, checkpoint_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    splits = load_series(data_dir)
    training = splits["train"].iloc[-window_hours:]
    validation, test = splits["val"], splits["test"]
    records, best = [], None
    for order, K in candidates:
        print(f"Validation: order={order}, K={K}", flush=True)
        tick = time.perf_counter()
        row = {"order": json.dumps(order), "K": K, "optimizer": optimizer}
        try:
            fitted = fit_model(training, order, K, maxiter, optimizer)
            prediction = rolling_forecast(fitted, validation, make_exog(validation.index, K), horizon)
            row.update(status="ok", AIC=float(fitted.aic), **metrics(prediction))
            if best is None or row["MAE"] < best["MAE"]:
                best = {"order": tuple(order), "K": K, "MAE": row["MAE"]}
            print(f"  MAE={row['MAE']:.6f}", flush=True)
        except RuntimeError as error:
            row.update(status="failed", error=str(error))
            print(f"  {error}", flush=True)
        row["elapsed_seconds"] = time.perf_counter() - tick
        records.append(row)
        pd.DataFrame(records).to_csv(output_dir / "validation_results.csv", index=False)
    if best is None:
        raise RuntimeError("No converged validation candidate; inspect validation_results.csv")
    history = pd.concat([splits["train"], validation]).iloc[-window_hours:]
    print(f"Final fit: order={best['order']}, K={best['K']}", flush=True)
    fitted = fit_model(history, best["order"], best["K"], maxiter, optimizer)
    prediction = rolling_forecast(fitted, test, make_exog(test.index, best["K"]), horizon)
    prediction.rename_axis("timestamp").to_csv(output_dir / "pred_sarimax.csv")
    comparison = {name: metrics(pd.DataFrame({"actual": test, "pred": values}))
                  for name, values in baselines(history, test).items()}
    metadata = {
        "selected": best, "selection_metric": "full-precision validation MAE",
        "window_hours": window_hours, "horizon_hours": horizon, "maxiter": maxiter, "optimizer": optimizer,
        "interval_level": 0.8, "converged": bool(fitted.mle_retvals["converged"]),
        "protocol": "Fit latest train window; select on validation; refit latest train+validation window; forecast consecutive blocks, update state after observing each block, fixed parameters.",
        "time_convention": "Naive timestamps preserved from input calendar columns; no timezone conversion.",
        "comparability": "Prophet/LSTM artifacts use a different training cutoff and one-hour evaluation protocol; aligned timestamps alone do not make protocols equivalent.",
        "splits": {name: {"rows": len(values), "start": str(values.index[0]), "end": str(values.index[-1])}
                   for name, values in splits.items()},
        "final_fit": {"rows": len(history), "start": str(history.index[0]), "end": str(history.index[-1])},
        "test_metrics": {"all_test": metrics(prediction), "lstm_seq24_aligned": metrics(prediction.iloc[24:])},
        "baselines": comparison,
        "versions": {name: version(name) for name in ("statsmodels", "pandas", "numpy", "scipy")},
        "python": platform.python_version(),
        "data_sha256": {f"{prefix}_{split}.csv": hashlib.sha256(
            (data_dir / f"{prefix}_{split}.csv").read_bytes()).hexdigest()
            for prefix in ("X", "y") for split in splits},
        "elapsed_seconds": time.perf_counter() - start,
        "checkpoint_state": "Final fit before test; test observations have not been added to this checkpoint.",
    }
    fitted.save(checkpoint_dir / "best_model.pkl")
    write_json(checkpoint_dir / "metadata.json", metadata)
    write_json(output_dir / "metrics.json", metadata)
    run_capacity(data_dir, output_dir / "pred_sarimax.csv", output_dir, window_hours=window_hours)
    print(json.dumps(metadata["test_metrics"], indent=2), flush=True)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "sarimax")
    parser.add_argument("--checkpoint-dir", type=Path, default=CHECKPOINT_DIR / "sarimax")
    parser.add_argument("--window-hours", type=int, default=8760)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--maxiter", type=int, default=300)
    parser.add_argument("--optimizer", choices=("powell", "lbfgs"), default="powell",
                        help="Powell default avoids the non-converging L-BFGS fit observed on this dataset")
    parser.add_argument("--evaluate-only", action="store_true", help="Evaluate saved CSV and regenerate capacity reports without fitting")
    args = parser.parse_args(argv)
    if args.evaluate_only:
        from ems.models.sarimax.capacity_planning import run_capacity
        run_capacity(args.data_dir, args.output_dir / "pred_sarimax.csv", args.output_dir,
                     window_hours=args.window_hours)
    else:
        run_experiment(args.data_dir, args.output_dir, args.checkpoint_dir,
                       args.window_hours, args.horizon, args.maxiter, optimizer=args.optimizer)


if __name__ == "__main__":
    main()
