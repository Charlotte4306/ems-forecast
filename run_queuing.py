"""Run the same 24h fleet-planning workflow as queueing_theory.ipynb.

    python run_queuing.py
    python run_queuing.py --output-dir outputs/queuing_cli

Uses the notebook's saved forecasts/checkpoint, busy-time carryover, shifts,
quantile analysis, and cost scenarios. No model training or Jupyter server.
The notebook's existing methodological limitations remain unchanged.
"""
import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Override the report folder; default is the notebook OUT_DIR')
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    from ems.capacity_notebook import run_capacity_notebook
    run_capacity_notebook(output_dir=args.output_dir)


if __name__ == '__main__':
    main()
