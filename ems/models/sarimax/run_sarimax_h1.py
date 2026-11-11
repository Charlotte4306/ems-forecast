"""Re-run SARIMAX at a 1-hour horizon and write results to outputs/sarimax/h1.

Same data protocol as Prophet/LSTM: fit on all of train (2019-2024), select on
validation (2025), no refit before test (2026). The model pickle goes to a
temporary folder that is removed after the run.
"""
import tempfile

from ems.models.sarimax.run_sarimax import run_experiment
from ems.paths import OUTPUT_DIR

FULL_TRAIN_HOURS = 52440  # 2019-01-08 00:00 -> 2024-12-31 23:00


def main():
    with tempfile.TemporaryDirectory() as checkpoint_dir:
        run_experiment(
            output_dir=OUTPUT_DIR / "sarimax/h1",
            checkpoint_dir=checkpoint_dir,
            window_hours=FULL_TRAIN_HOURS,
            horizon=1,
            refit=False,
        )


if __name__ == "__main__":
    main()
