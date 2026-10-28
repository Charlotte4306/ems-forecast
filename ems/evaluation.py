"""Shared forecast metrics; model-specific plots stay in each model package."""
import numpy as np


def compute_metrics(y_true, y_pred):
    actual, predicted = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    if actual.ndim != 1 or actual.shape != predicted.shape or not actual.size:
        raise ValueError("Expected non-empty, equally sized 1-D arrays")
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise ValueError("Metrics require finite values")
    error = actual - predicted
    nonzero = actual != 0
    denominator = np.square(actual - actual.mean()).sum()
    return {
        "MAE": float(np.abs(error).mean()),
        "RMSE": float(np.sqrt(np.square(error).mean())),
        "MAPE (%)": float((np.abs(error[nonzero] / actual[nonzero])).mean() * 100) if nonzero.any() else None,
        "R2": float(1 - np.square(error).sum() / denominator) if denominator else None,
    }
