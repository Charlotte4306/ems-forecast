"""
Training loop với Early Stopping, LR Scheduler, Gradient Clipping.
"""
import os
import time
import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader
from typing import Tuple, Dict

from ems.models.lstm.config import (
    DEVICE, CKPT_DIR,
    LEARNING_RATE, WEIGHT_DECAY,
    SCHEDULER_PATIENCE, SCHEDULER_FACTOR,
    EARLY_STOP_PATIENCE, GRAD_CLIP, NUM_EPOCHS,
)


# ─────────────────────────────────────────────
# Early Stopping helper
# ─────────────────────────────────────────────

class EarlyStopping:
    def __init__(self, patience: int = 10, delta: float = 1e-5):
        self.patience  = patience
        self.delta     = delta
        self.best_loss = np.inf
        self.counter   = 0
        self.best_state: Dict = {}

    def step(self, val_loss: float, model: nn.Module) -> bool:
        """
        Returns True nếu nên dừng sớm.
        Lưu model state khi val_loss cải thiện.
        """
        if val_loss < self.best_loss - self.delta:
            self.best_loss  = val_loss
            self.counter    = 0
            # Lưu deep copy của state dict
            self.best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            self.counter += 1
        return self.counter >= self.patience

    def restore_best(self, model: nn.Module):
        """Load lại best weights."""
        model.load_state_dict(self.best_state)


# ─────────────────────────────────────────────
# One epoch train / eval
# ─────────────────────────────────────────────

def _run_epoch(model: nn.Module, loader: DataLoader,
               criterion, optimizer=None,
               grad_clip: float = GRAD_CLIP) -> float:
    """
    Chạy 1 epoch.
    - optimizer=None → eval mode (không update weights)
    - Trả về average loss trên epoch.
    """
    training = optimizer is not None
    model.train() if training else model.eval()

    total_loss = 0.0
    n_batches  = 0
    ctx = torch.no_grad() if not training else torch.enable_grad()

    with ctx:
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            y_batch = y_batch.to(DEVICE)

            preds = model(X_batch)          # (batch, 1)
            loss  = criterion(preds, y_batch)

            if training:
                optimizer.zero_grad()
                loss.backward()
                if grad_clip:
                    nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                optimizer.step()

            total_loss += loss.item()
            n_batches  += 1

    return total_loss / n_batches


# ─────────────────────────────────────────────
# Main training function
# ─────────────────────────────────────────────

def train(
    model:        nn.Module,
    train_dl:     DataLoader,
    val_dl:       DataLoader,
    run_name:     str   = "vanilla_seq24",
    num_epochs:   int   = NUM_EPOCHS,
    lr:           float = LEARNING_RATE,
    weight_decay: float = WEIGHT_DECAY,
    verbose:      bool  = True,
) -> Dict:
    """
    Full training loop.

    Returns:
        history dict: {
            "train_loss": [...],
            "val_loss":   [...],
            "best_epoch": int,
            "best_val_loss": float
        }
    """
    model = model.to(DEVICE)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(),
                                 lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        patience=SCHEDULER_PATIENCE,
        factor=SCHEDULER_FACTOR,
    )
    early_stop = EarlyStopping(patience=EARLY_STOP_PATIENCE)

    history = {"train_loss": [], "val_loss": []}
    ckpt_path = os.path.join(CKPT_DIR, f"{run_name}_best.pth")

    print(f"\n{'='*55}")
    print(f"  Training: {run_name}  |  device={DEVICE}")
    print(f"{'='*55}")
    t0 = time.time()

    for epoch in range(1, num_epochs + 1):
        train_loss = _run_epoch(model, train_dl, criterion, optimizer)
        val_loss   = _run_epoch(model, val_dl,   criterion)

        scheduler.step(val_loss)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)

        if verbose and (epoch % 5 == 0 or epoch == 1):
            elapsed = time.time() - t0
            lr_now  = optimizer.param_groups[0]["lr"]
            print(f"  Epoch {epoch:4d}/{num_epochs} | "
                  f"train={train_loss:.5f} | val={val_loss:.5f} | "
                  f"lr={lr_now:.2e} | {elapsed:.0f}s")

        stop = early_stop.step(val_loss, model)
        if stop:
            print(f"\n  ⏹ Early stopping at epoch {epoch}. "
                  f"Best val loss: {early_stop.best_loss:.5f}")
            break

    # Restore best weights & save checkpoint
    early_stop.restore_best(model)
    torch.save({
        "model_state": model.state_dict(),
        "history":     history,
        "run_name":    run_name,
        "best_val_loss": early_stop.best_loss,
    }, ckpt_path)
    print(f"  ✅ Best model saved → {ckpt_path}")

    best_epoch = int(np.argmin(history["val_loss"])) + 1
    history["best_epoch"]    = best_epoch
    history["best_val_loss"] = early_stop.best_loss

    return history


# ─────────────────────────────────────────────
# Load saved checkpoint
# ─────────────────────────────────────────────

def load_checkpoint(model: nn.Module, run_name: str) -> Dict:
    """Load model weights từ checkpoint. Trả về history."""
    ckpt_path = os.path.join(CKPT_DIR, f"{run_name}_best.pth")
    ckpt = torch.load(ckpt_path, map_location=DEVICE)
    model.load_state_dict(ckpt["model_state"])
    model.to(DEVICE)
    print(f"[Load] Loaded '{run_name}' | best_val_loss={ckpt['best_val_loss']:.5f}")
    return ckpt["history"]
