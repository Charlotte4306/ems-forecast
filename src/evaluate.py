"""
Evaluation: Metrics + Visualizations
"""
import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from typing import Tuple, Dict

from src.config import DEVICE, OUTPUT_DIR


# ─────────────────────────────────────────────
# 1. Prediction helper
# ─────────────────────────────────────────────

def predict(model: nn.Module, loader: DataLoader,
            tgt_scaler) -> Tuple[np.ndarray, np.ndarray]:
    """
    Chạy inference trên toàn bộ loader.

    Returns:
        y_true: (N,) actual call_count (inverse-transformed)
        y_pred: (N,) predicted call_count (inverse-transformed)
    """
    model.eval()
    preds_list, true_list = [], []

    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            p = model(X_batch).cpu().numpy()
            preds_list.append(p)
            true_list.append(y_batch.numpy())

    y_pred_sc = np.concatenate(preds_list, axis=0)   # (N, 1) scaled
    y_true_sc = np.concatenate(true_list,  axis=0)   # (N, 1) scaled

    # Inverse transform → giá trị thực
    y_pred = tgt_scaler.inverse_transform(y_pred_sc).flatten()
    y_true = tgt_scaler.inverse_transform(y_true_sc).flatten()

    # Clip về 0 (call_count không âm)
    y_pred = np.clip(y_pred, 0, None)
    return y_true, y_pred


# ─────────────────────────────────────────────
# 2. Metrics
# ─────────────────────────────────────────────

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)

    # MAPE — bỏ qua các điểm y_true == 0
    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

    metrics = {"MAE": mae, "RMSE": rmse, "MAPE (%)": mape, "R²": r2}
    return metrics


def print_metrics(metrics: Dict, run_name: str = ""):
    header = f"  Evaluation Metrics — {run_name}" if run_name else "  Evaluation Metrics"
    print(f"\n{'─'*50}")
    print(header)
    print(f"{'─'*50}")
    for k, v in metrics.items():
        print(f"  {k:<12}: {v:.4f}")
    print(f"{'─'*50}\n")


# ─────────────────────────────────────────────
# 3. Visualizations
# ─────────────────────────────────────────────

def _setup_style():
    plt.rcParams.update({
        "figure.facecolor": "#0f1117",
        "axes.facecolor":   "#1a1d27",
        "axes.edgecolor":   "#3a3d4d",
        "axes.labelcolor":  "#c9d1d9",
        "xtick.color":      "#8b949e",
        "ytick.color":      "#8b949e",
        "text.color":       "#c9d1d9",
        "grid.color":       "#2d3047",
        "grid.linewidth":   0.6,
        "font.family":      "DejaVu Sans",
        "font.size":        11,
    })


def plot_loss_curve(history: Dict, run_name: str = "model",
                    save: bool = True):
    """Plot train/val loss curves theo epoch."""
    _setup_style()
    train_loss = history["train_loss"]
    val_loss   = history["val_loss"]
    best_epoch = history.get("best_epoch", np.argmin(val_loss) + 1)

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#0f1117")

    epochs = range(1, len(train_loss) + 1)
    ax.plot(epochs, train_loss, color="#58a6ff", lw=1.8, label="Train Loss")
    ax.plot(epochs, val_loss,   color="#f78166", lw=1.8, label="Val Loss")
    ax.axvline(best_epoch, color="#3fb950", ls="--", lw=1.2,
               label=f"Best epoch = {best_epoch}")

    ax.set_title(f"Loss Curve — {run_name}", fontsize=13, pad=10)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE Loss")
    ax.legend(framealpha=0.3)
    ax.grid(True, alpha=0.4)
    fig.tight_layout()

    if save:
        path = os.path.join(OUTPUT_DIR, f"loss_{run_name}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  [Plot] Saved → {path}")
    return fig


def plot_predictions(y_true: np.ndarray, y_pred: np.ndarray,
                     run_name: str = "model",
                     n_hours: int = 24 * 14,
                     save: bool = True):
    """
    Plot Predicted vs Actual cho n_hours giờ đầu tiên của test set.
    + Scatter plot + Residual distribution
    """
    _setup_style()
    n = min(n_hours, len(y_true))
    residuals = y_true - y_pred

    fig = plt.figure(figsize=(14, 9))
    fig.patch.set_facecolor("#0f1117")
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, :])   # time series: full width
    ax2 = fig.add_subplot(gs[1, 0])   # scatter
    ax3 = fig.add_subplot(gs[1, 1])   # residual hist

    # ── Time series ──
    t = np.arange(n)
    ax1.plot(t, y_true[:n],  color="#58a6ff", lw=1.2, alpha=0.9, label="Actual")
    ax1.plot(t, y_pred[:n],  color="#f78166", lw=1.2, alpha=0.85, label="Predicted")
    ax1.fill_between(t, y_true[:n], y_pred[:n],
                     alpha=0.15, color="#bc8cff")
    ax1.set_title(f"Predicted vs Actual — {run_name} (first {n} hours)",
                  fontsize=12, pad=8)
    ax1.set_xlabel("Hour index")
    ax1.set_ylabel("call_count")
    ax1.legend(framealpha=0.3)
    ax1.grid(True, alpha=0.4)

    # ── Scatter ──
    lim = max(y_true.max(), y_pred.max()) + 2
    ax2.scatter(y_true, y_pred, alpha=0.25, s=8, color="#58a6ff", rasterized=True)
    ax2.plot([0, lim], [0, lim], "r--", lw=1.2, label="Perfect")
    ax2.set_xlim(0, lim); ax2.set_ylim(0, lim)
    ax2.set_xlabel("Actual"); ax2.set_ylabel("Predicted")
    ax2.set_title("Scatter: Actual vs Predicted")
    ax2.legend(framealpha=0.3)
    ax2.grid(True, alpha=0.4)

    # ── Residual distribution ──
    ax3.hist(residuals, bins=60, color="#3fb950", alpha=0.75, edgecolor="none")
    ax3.axvline(0, color="#f78166", lw=1.5, ls="--")
    ax3.set_xlabel("Residual (Actual − Predicted)")
    ax3.set_ylabel("Count")
    ax3.set_title("Residual Distribution")
    ax3.grid(True, alpha=0.4)

    fig.suptitle(f"Model Evaluation — {run_name}", fontsize=14, y=1.01,
                 color="#e6edf3", fontweight="bold")

    if save:
        path = os.path.join(OUTPUT_DIR, f"preds_{run_name}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  [Plot] Saved → {path}")
    return fig


def plot_comparison(results: Dict[str, Dict],
                    save: bool = True):
    """
    So sánh các model theo MAE, RMSE, R².
    results = {"vanilla_seq24": {"MAE": ..., "RMSE": ..., "R²": ..., "MAPE (%)": ...}, ...}
    """
    _setup_style()
    models  = list(results.keys())
    metrics = ["MAE", "RMSE", "R²", "MAPE (%)"]
    colors  = ["#58a6ff", "#f78166", "#3fb950", "#bc8cff"]

    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    fig.patch.set_facecolor("#0f1117")

    for ax, metric, color in zip(axes, metrics, colors):
        vals = [results[m][metric] for m in models]
        bars = ax.bar(models, vals, color=color, alpha=0.8, width=0.5)
        ax.set_title(metric, fontsize=12)
        ax.set_ylabel(metric)
        ax.tick_params(axis="x", rotation=20)
        ax.grid(True, axis="y", alpha=0.4)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.02,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle("Model Comparison", fontsize=14, color="#e6edf3",
                 fontweight="bold")
    fig.tight_layout()

    if save:
        path = os.path.join(OUTPUT_DIR, "model_comparison.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  [Plot] Saved → {path}")
    return fig


# ─────────────────────────────────────────────
# 4. Baseline (Naive)
# ─────────────────────────────────────────────

def naive_baseline(y_true: np.ndarray) -> Dict:
    """
    Baseline: dự đoán = giá trị giờ trước (lag-1).
    """
    y_pred_naive = np.roll(y_true, 1)
    y_pred_naive[0] = y_true[0]
    metrics = compute_metrics(y_true[1:], y_pred_naive[1:])
    return metrics


def evaluate_all(model: nn.Module, test_dl: DataLoader,
                 tgt_scaler, run_name: str, history: Dict):
    """
    Convenience wrapper: predict → metrics → plots.
    """
    y_true, y_pred = predict(model, test_dl, tgt_scaler)
    metrics = compute_metrics(y_true, y_pred)
    print_metrics(metrics, run_name)
    plot_loss_curve(history, run_name)
    plot_predictions(y_true, y_pred, run_name)
    return y_true, y_pred, metrics
