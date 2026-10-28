"""Train or evaluate the original LSTM architecture through a CLI."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import torch

from ems.models.lstm.config import (
    BATCH_SIZE, DEFAULT_SEQ_LEN, DROPOUT, HIDDEN_SIZE, N_FEATURES,
    NUM_EPOCHS, NUM_LAYERS, OUTPUT_DIR, SEED,
)
from ems.models.lstm.evaluate import evaluate_all
from ems.models.lstm.model import MODEL_REGISTRY, build_model
from ems.models.lstm.preprocess import (
    build_dataloaders, create_sequences, load_data, load_scalers,
    make_dataloader, scale_data,
)
from ems.models.lstm.train import load_checkpoint, train
from ems.data import load_data as load_hourly_data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=MODEL_REGISTRY, default="vanilla")
    parser.add_argument("--seq-len", type=int, choices=(24, 168), default=DEFAULT_SEQ_LEN)
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--evaluate-only", action="store_true",
                        help="Load existing checkpoint/scalers without refitting or training")
    args = parser.parse_args(argv)
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("epochs and batch-size must be positive")
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    run_name = f"{args.architecture}_seq{args.seq_len}"
    model = build_model(args.architecture, n_features=N_FEATURES,
                        hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, dropout=DROPOUT)
    if args.evaluate_only:
        feat_scaler, tgt_scaler = load_scalers()
        *_, X_test, y_test = load_data()
        X_sc, y_sc = scale_data(X_test, y_test, feat_scaler, tgt_scaler)
        X_seq, y_seq = create_sequences(X_sc, y_sc, args.seq_len)
        test_dl = make_dataloader(X_seq, y_seq, args.batch_size)
        history = load_checkpoint(model, run_name)
    else:
        train_dl, val_dl, test_dl, _, tgt_scaler = build_dataloaders(args.seq_len, args.batch_size)
        history = train(model, train_dl, val_dl, run_name=run_name, num_epochs=args.epochs)
    y_true, y_pred, metrics = evaluate_all(model, test_dl, tgt_scaler, run_name, history)
    test = load_hourly_data()["test"].iloc[args.seq_len:]
    output_dir = Path(OUTPUT_DIR)
    pd.DataFrame({"ds": test.ds.to_numpy(), "y": y_true, "yhat": y_pred}).to_csv(
        output_dir / f"test_predictions_{run_name}.csv", index=False)
    (output_dir / f"metrics_{run_name}.json").write_text(
        json.dumps({"run_name": run_name, "seq_len": args.seq_len,
                    "n_hours": len(test), "metrics": metrics}, indent=2, allow_nan=False),
        encoding="utf-8")


if __name__ == "__main__":
    main()
