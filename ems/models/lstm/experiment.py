"""Run the notebook's LSTM training/evaluation workflow through a CLI."""
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
    NUM_EPOCHS, NUM_LAYERS, OUTPUT_DIR, CKPT_DIR, SEED,
)
from ems.models.lstm.evaluate import evaluate_all, predict, predict_24h_blocks
from ems.models.lstm.model import MODEL_REGISTRY, build_model
from ems.models.lstm.preprocess import (
    build_dataloaders, build_block_dataloaders,
    create_sequences, create_block_sequences,
    load_data, load_scalers, make_dataloader, scale_data,
)
from ems.models.lstm.train import load_checkpoint, train
from ems.data import load_data as load_hourly_data


def notebook_run_name(architecture, seq_len, forecast_horizon):
    """Match the two seq24 Vanilla experiments in lstm_experiment.ipynb.

    Other configurations retain their existing explicit configuration names.
    Never treat the legacy vanilla_seq24 weights as a newly trained 1h model.
    """
    if architecture == "vanilla" and seq_len == 24:
        return "vanilla_1h_rolling" if forecast_horizon == 1 else "vanilla_24h_block"
    suffix = f"_block{forecast_horizon}" if forecast_horizon > 1 else ""
    return f"{architecture}_seq{seq_len}{suffix}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=MODEL_REGISTRY, default="vanilla")
    parser.add_argument("--seq-len", type=int, choices=(24, 168), default=DEFAULT_SEQ_LEN)
    parser.add_argument("--forecast-horizon", type=int, choices=(1, 24), default=1,
                        help="1 for 1-hour rolling prediction, 24 for 24-hour block prediction")
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--evaluate-only", action="store_true",
                        help="Load existing checkpoint/scalers without refitting or training")
    args = parser.parse_args(argv)
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("epochs and batch-size must be positive")
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    run_name = notebook_run_name(args.architecture, args.seq_len, args.forecast_horizon)
    if args.evaluate_only:
        checkpoint = Path(CKPT_DIR) / f"{run_name}_best.pth"
        if not checkpoint.is_file():
            parser.error(
                f"Missing notebook checkpoint: {checkpoint}. "
                "Run the corresponding notebook training cells or run this CLI "
                "without --evaluate-only first. Legacy checkpoints are not substituted."
            )
    model = build_model(args.architecture, n_features=N_FEATURES,
                        hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, dropout=DROPOUT,
                        forecast_horizon=args.forecast_horizon)
    if args.evaluate_only:
        feat_scaler, tgt_scaler = load_scalers()
        X_train, y_train, X_val, y_val, X_test, y_test = load_data()
        X_va_sc, y_va_sc = scale_data(X_val,  y_val,  feat_scaler, tgt_scaler)
        X_te_sc, y_te_sc = scale_data(X_test, y_test, feat_scaler, tgt_scaler)
        X_te_ctx = np.concatenate([X_va_sc[-args.seq_len:], X_te_sc], axis=0)
        y_te_ctx = np.concatenate([y_va_sc[-args.seq_len:], y_te_sc], axis=0)
        if args.forecast_horizon > 1:
            X_seq, y_seq = create_block_sequences(X_te_ctx, y_te_ctx, args.seq_len,
                                                  args.forecast_horizon, step=args.forecast_horizon)
        else:
            X_seq, y_seq = create_sequences(X_te_ctx, y_te_ctx, args.seq_len)
        test_dl = make_dataloader(X_seq, y_seq, args.batch_size)
        history = load_checkpoint(model, run_name)
    else:
        if args.forecast_horizon > 1:
            train_dl, val_dl, test_dl, _, tgt_scaler = build_block_dataloaders(
                args.seq_len, args.forecast_horizon, args.batch_size
            )
        else:
            train_dl, val_dl, test_dl, _, tgt_scaler = build_dataloaders(args.seq_len, args.batch_size)
        history = train(model, train_dl, val_dl, run_name=run_name, num_epochs=args.epochs)
    
    test = load_hourly_data()["test"]  # đủ 6.796 giờ, không cắt seq_len nữa
    pred_fn = predict_24h_blocks if args.forecast_horizon > 1 else predict
    prediction_options = {"n_target_hours": len(test)} if args.forecast_horizon > 1 else {}
    y_true, y_pred, metrics = evaluate_all(
        model, test_dl, tgt_scaler, run_name, history,
        predict_fn=pred_fn, **prediction_options,
    )
    if len(y_true) != len(test) or len(y_pred) != len(test):
        raise ValueError("Predictions must cover the same test hours as the notebook")
    output_dir = Path(OUTPUT_DIR)
    pd.DataFrame({"ds": test.ds.to_numpy(), "y": y_true, "yhat": y_pred}).to_csv(
        output_dir / f"test_predictions_{run_name}.csv", index=False)
    (output_dir / f"metrics_{run_name}.json").write_text(
        json.dumps({"run_name": run_name, "seq_len": args.seq_len,
                    "forecast_horizon": args.forecast_horizon,
                    "n_hours": len(test), "metrics": metrics}, indent=2, allow_nan=False),
        encoding="utf-8")


if __name__ == "__main__":
    main()
