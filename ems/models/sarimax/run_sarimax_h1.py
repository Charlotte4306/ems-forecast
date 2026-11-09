"""Run SARIMAX at a 1-hour horizon without overwriting the 24-hour results."""
from ems.models.sarimax.run_sarimax import run_experiment
from ems.paths import CHECKPOINT_DIR, OUTPUT_DIR


def main():
    run_experiment(
        output_dir=OUTPUT_DIR / "sarimax/h1",
        checkpoint_dir=CHECKPOINT_DIR / "sarimax_h1",
        horizon=1,
    )


if __name__ == "__main__":
    main()
