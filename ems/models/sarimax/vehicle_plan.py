"""Turn hourly dispatch forecasts into the number of ambulances to schedule."""
import argparse
import math
from pathlib import Path

import pandas as pd

from ems.paths import OUTPUT_DIR

# Mean time a vehicle stays busy per dispatch (total_busy_sec in the EDA notebook).
BUSY_SECONDS = 3830.2


def erlang_c(load, vehicles):
    """Probability that a dispatch has to wait, for a stable M/M/c queue."""
    blocking = 1.0
    for count in range(1, vehicles + 1):
        blocking = load * blocking / (count + load * blocking)
    utilization = load / vehicles
    return blocking / (1 - utilization * (1 - blocking))


def vehicles_needed(dispatches, busy_seconds=BUSY_SECONDS, max_wait_probability=0.2):
    """Smallest fleet meeting the wait-probability target, with at least one vehicle."""
    load = max(float(dispatches), 0.0) * busy_seconds / 3600
    vehicles = math.floor(load) + 1
    while erlang_c(load, vehicles) > max_wait_probability:
        vehicles += 1
    return vehicles


def build_plan(predictions, max_wait_probability=0.2):
    frame = pd.read_csv(predictions, parse_dates=["timestamp"])
    return pd.DataFrame({
        "timestamp": frame["timestamp"],
        "forecast_dispatches": frame["pred"],
        "vehicles": [vehicles_needed(value, max_wait_probability=max_wait_probability)
                     for value in frame["pred"]],
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=OUTPUT_DIR / "sarimax/rerun/pred_sarimax.csv")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "sarimax/vehicle_plan/h24.csv")
    parser.add_argument("--max-wait-probability", type=float, default=0.2)
    args = parser.parse_args(argv)
    if not 0 < args.max_wait_probability < 1:
        parser.error("max-wait-probability must be between 0 and 1")
    plan = build_plan(args.predictions, args.max_wait_probability)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(args.output, index=False)
    print(f"Planned {len(plan)} hours: {args.output}", flush=True)


if __name__ == "__main__":
    main()
