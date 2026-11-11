"""Run with: python -m ems.models.prophet.train"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

from ems.data import ROOT, REGRESSORS, load_data
from ems.evaluation import compute_metrics
from ems.models.prophet.evaluate import plot_predictions
from ems.models.prophet.model import SEED, build_model, predict, save_model


def run_experiment(data_dir=ROOT / "data", output_dir=ROOT / "outputs/prophet",
                   checkpoint_dir=ROOT / "checkpoints/prophet"):
    output_dir, checkpoint_dir = Path(output_dir), Path(checkpoint_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(SEED)
    splits = load_data(Path(data_dir))
    train, val, test = (splits[s] for s in ("train", "val", "test"))
    candidates, best, best_model = [], None, None
    start = time.perf_counter()
    # All candidates fit train only. Validation selects configuration by MAE.
    for regressors in (False, True):
        for prior in (0.01, 0.05):
            name = f"prophet_{'lags' if regressors else 'seasonal'}_cp{prior}"
            print(f"Training {name} ...", flush=True)
            model = build_model(prior, regressors)
            cols = ["ds", "y", *(REGRESSORS if regressors else [])]
            model.fit(train[cols], seed=SEED)
            forecast = predict(model, val)
            result = {"name": name, "use_regressors": regressors,
                      "changepoint_prior_scale": prior,
                      **compute_metrics(val.y, forecast.yhat)}
            candidates.append(result)
            print(f"  Validation MAE={result['MAE']:.4f}", flush=True)
            if best is None or result["MAE"] < best["MAE"]:
                best, best_model = result, model

    # Keep training cutoff unchanged, matching the LSTM experiment.
    forecast = predict(best_model, test)
    predictions = test[["ds", "y"]].copy()
    predictions["yhat"] = forecast.yhat.to_numpy()
    results = {}
    for label, offset in (("all_test", 0), ("lstm_seq24_aligned", 24), ("seq168_aligned", 168)):
        subset = test.iloc[offset:]
        if subset.empty:
            continue
        results[label] = {"n_hours": len(subset), "start": str(subset.ds.iloc[0]),
                          "end": str(subset.ds.iloc[-1]),
                          "prophet": compute_metrics(subset.y, predictions.yhat.iloc[offset:])}
        for lag in (1, 24, 168):
            results[label][f"naive_lag{lag}"] = compute_metrics(subset.y, subset[f"lag_{lag}h"])

    metadata = {
        "selected": best, "selection_metric": "validation MAE", "seed": SEED,
        "regressors": REGRESSORS if best["use_regressors"] else [],
        "protocol": "Fit train only; select on validation; evaluate test once. Lag features use observed history at each forecast hour.",
        "splits": {s: {"rows": len(f), "start": str(f.ds.iloc[0]), "end": str(f.ds.iloc[-1])} for s, f in splits.items()},
        "versions": {p: version(p) for p in ("prophet", "pandas", "numpy", "matplotlib")},
        "data_sha256": {f"{prefix}_{split}.csv": hashlib.sha256(
            (Path(data_dir) / f"{prefix}_{split}.csv").read_bytes()).hexdigest()
            for prefix in ("X", "y") for split in splits},
        "python": platform.python_version(), "elapsed_seconds": time.perf_counter() - start,
        "test_metrics": results,
    }
    save_model(best_model, checkpoint_dir / "best_model.json")
    (checkpoint_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(candidates).to_csv(output_dir / "validation_results.csv", index=False)
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    plot_predictions(predictions, output_dir)
    figure = best_model.plot_components(best_model.predict(test[["ds", *best_model.extra_regressors]]))
    figure.savefig(output_dir / "components.png", dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(figure)
    print(json.dumps(results, indent=2), flush=True)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--forecast-24h", action="store_true",
                        help="Evaluate saved checkpoint in 24h blocks, scoring all available hours; no training")
    mode.add_argument("--select-24h", action="store_true",
                      help="Fit four configurations on train, select on full 24h validation, no test")
    parser.add_argument("--forecast-split", choices=("val", "test"), default="test")
    parser.add_argument("--max-days", type=int, help="Limit the 24-hour backtest for a quick trial")
    args = parser.parse_args(argv)
    if args.select_24h:
        if args.max_days is not None or args.forecast_split != "test":
            parser.error("--select-24h always uses full validation; no --max-days/--forecast-split")
        from ems.models.prophet.select_24h import select_day_ahead
        select_day_ahead(args.data_dir,
                        args.output_dir or ROOT / "outputs/prophet/day_ahead_24h/selection",
                        args.checkpoint_dir or ROOT / "checkpoints/prophet/day_ahead_24h")
    elif args.forecast_24h:
        from ems.models.prophet.forecast import run_day_ahead
        output = args.output_dir or ROOT / "outputs/prophet/day_ahead_24h" / args.forecast_split
        run_day_ahead(args.data_dir, args.checkpoint_dir or ROOT / "checkpoints/prophet", output,
                     args.forecast_split, args.max_days)
    else:
        if args.max_days is not None or args.forecast_split != "test":
            parser.error("--max-days and --forecast-split require --forecast-24h")
        run_experiment(args.data_dir, args.output_dir or ROOT / "outputs/prophet",
                       args.checkpoint_dir or ROOT / "checkpoints/prophet")


if __name__ == "__main__":
    main()
