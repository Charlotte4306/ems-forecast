"""Re-run SARIMAX at a 1-hour horizon and write results to outputs/sarimax/h1.

The model pickle goes to a temporary folder that is removed after the run.
"""
import tempfile

from ems.models.sarimax.run_sarimax import run_experiment
from ems.paths import OUTPUT_DIR


def main():
    with tempfile.TemporaryDirectory() as checkpoint_dir:
        run_experiment(
            output_dir=OUTPUT_DIR / "sarimax/h1",
            checkpoint_dir=checkpoint_dir,
            horizon=1,
        )


if __name__ == "__main__":
    main()
