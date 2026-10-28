"""Shared entry point: python main.py prophet|lstm [model-specific options]."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("prophet", "lstm"))
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv[:1])
    remaining = argv[1:]
    if args.model == "prophet":
        from ems.models.prophet.train import main as run
    else:
        from ems.models.lstm.experiment import main as run
    run(remaining)


if __name__ == "__main__":
    main()
