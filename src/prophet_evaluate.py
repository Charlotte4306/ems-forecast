"""Common metrics and plots on identical evaluation timestamps."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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


def plot_predictions(frame, output_dir):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    first = frame.iloc[:336]
    axes[0].plot(first.ds, first.y, label="Actual", linewidth=1)
    axes[0].plot(first.ds, first.yhat, label="Prophet", linewidth=1)
    axes[0].set(title="Prophet: first 14 days of test", ylabel="Calls/hour")
    axes[0].legend()
    axes[1].hist(frame.y - frame.yhat, bins=60)
    axes[1].set(xlabel="Actual - predicted", ylabel="Hours", title="Test residuals")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "predictions.png", dpi=150)
    plt.close(fig)
