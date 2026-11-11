"""
Preprocessing: Scaling + Sequence Builder
"""
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import joblib
import os

from ems.models.lstm.config import (
    DATA_DIR, CKPT_DIR, FEATURE_COLS, TARGET_COL,
    BATCH_SIZE, SEED
)
from pathlib import Path
from typing import Tuple
from ems.data import read_split


# ─────────────────────────────────────────────
# 1. Load & scale data
# ─────────────────────────────────────────────

def load_data():
    """Đọc toàn bộ CSV files."""
    X_train, y_train = read_split(Path(DATA_DIR), "train")
    X_val, y_val = read_split(Path(DATA_DIR), "val")
    X_test, y_test = read_split(Path(DATA_DIR), "test")
    return X_train, y_train, X_val, y_val, X_test, y_test


def fit_scalers(X_train: pd.DataFrame, y_train: pd.DataFrame):
    """
    Fit scalers chỉ trên train set.
    - X: StandardScaler (zero mean, unit variance)
    - y: MinMaxScaler  → [0, 1]
    """
    feat_scaler = StandardScaler()
    feat_scaler.fit(X_train[FEATURE_COLS].values)

    tgt_scaler = MinMaxScaler()
    tgt_scaler.fit(y_train[[TARGET_COL]].values)

    # Lưu scalers để dùng lại khi inference
    os.makedirs(CKPT_DIR, exist_ok=True)
    joblib.dump(feat_scaler, os.path.join(CKPT_DIR, "feat_scaler.pkl"))
    joblib.dump(tgt_scaler,  os.path.join(CKPT_DIR, "tgt_scaler.pkl"))
    return feat_scaler, tgt_scaler


def load_scalers():
    """Load scalers đã lưu."""
    feat_scaler = joblib.load(os.path.join(CKPT_DIR, "feat_scaler.pkl"))
    tgt_scaler  = joblib.load(os.path.join(CKPT_DIR, "tgt_scaler.pkl"))
    return feat_scaler, tgt_scaler


def scale_data(X: pd.DataFrame, y: pd.DataFrame,
               feat_scaler, tgt_scaler):
    """Transform X và y về dạng scaled numpy arrays."""
    X_sc = feat_scaler.transform(X[FEATURE_COLS].values).astype(np.float32)
    y_sc = tgt_scaler.transform(y[[TARGET_COL]].values).astype(np.float32)
    return X_sc, y_sc


# ─────────────────────────────────────────────
# 2. Sequence builder (sliding window)
# ─────────────────────────────────────────────

def create_sequences(X: np.ndarray, y: np.ndarray, seq_len: int):
    """
    Tạo chuỗi đầu vào dạng sliding window.

    Args:
        X        : (N, n_features) scaled features
        y        : (N, 1) scaled target
        seq_len  : độ dài chuỗi (24 hoặc 168)

    Returns:
        X_seq : (N - seq_len, seq_len, n_features)  float32
        y_seq : (N - seq_len, 1)                    float32
    """
    X_list, y_list = [], []
    n = len(X)
    for i in range(seq_len, n):
        X_list.append(X[i - seq_len + 1 : i + 1])   # (seq_len, n_features)
        y_list.append(y[i])                  # (1,)
    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
    )


# ─────────────────────────────────────────────
# 3. DataLoader builder
# ─────────────────────────────────────────────

def make_dataloader(X_seq: np.ndarray, y_seq: np.ndarray,
                    batch_size: int = BATCH_SIZE,
                    shuffle: bool = False) -> DataLoader:
    """
    Chuyển numpy arrays → PyTorch DataLoader.
    shuffle=False để giữ thứ tự thời gian.
    """
    X_t = torch.from_numpy(X_seq)          # (N, seq_len, features)
    y_t = torch.from_numpy(y_seq)          # (N, 1)
    dataset = TensorDataset(X_t, y_t)
    return DataLoader(dataset, batch_size=batch_size,
                      shuffle=shuffle, pin_memory=True)


# ─────────────────────────────────────────────
# 4. Pipeline tổng hợp
# ─────────────────────────────────────────────

def build_dataloaders(seq_len: int = 24, batch_size: int = BATCH_SIZE,
                      verbose: bool = True):
    """
    Chạy toàn bộ pipeline: load → scale → sequence → dataloader

    Để test DataLoader dự báo đủ toàn bộ 6.796 giờ test (ngang bằng SARIMAX
    và Prophet), seq_len dòng cuối của Val được ghép vào đầu Test làm lookback
    window. Train và Val vẫn tạo sequence độc lập như cũ.

    Returns:
        train_dl, val_dl, test_dl, feat_scaler, tgt_scaler
    """
    # Load
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()

    # Scale (fit chỉ trên train)
    feat_scaler, tgt_scaler = fit_scalers(X_train, y_train)
    X_tr_sc, y_tr_sc = scale_data(X_train, y_train, feat_scaler, tgt_scaler)
    X_va_sc, y_va_sc = scale_data(X_val,   y_val,   feat_scaler, tgt_scaler)
    X_te_sc, y_te_sc = scale_data(X_test,  y_test,  feat_scaler, tgt_scaler)

    # Sequence
    X_tr_seq, y_tr_seq = create_sequences(X_tr_sc, y_tr_sc, seq_len)
    X_va_seq, y_va_seq = create_sequences(X_va_sc, y_va_sc, seq_len)

    # Ghép seq_len dòng cuối của Val làm lookback window cho Test,
    # giúp LSTM dự báo ngay từ giờ đầu tiên của tập Test (6.796 giờ).
    # Chỉ dùng X của Val để tạo cửa sổ; nhãn y vẫn thuộc 100% tập Test.
    X_te_with_ctx = np.concatenate([X_va_sc[-seq_len:], X_te_sc], axis=0)
    y_te_with_ctx = np.concatenate([y_va_sc[-seq_len:], y_te_sc], axis=0)
    X_te_seq, y_te_seq = create_sequences(X_te_with_ctx, y_te_with_ctx, seq_len)

    if verbose:
        print(f"[Preprocess] seq_len={seq_len}")
        print(f"  Train:  X={X_tr_seq.shape}, y={y_tr_seq.shape}")
        print(f"  Val:    X={X_va_seq.shape}, y={y_va_seq.shape}")
        print(f"  Test:   X={X_te_seq.shape}, y={y_te_seq.shape}  "
              f"(lookback từ {seq_len} dòng cuối Val → đủ toàn bộ test)")

    # DataLoader
    train_dl = make_dataloader(X_tr_seq, y_tr_seq, batch_size, shuffle=False)
    val_dl   = make_dataloader(X_va_seq, y_va_seq, batch_size, shuffle=False)
    test_dl  = make_dataloader(X_te_seq, y_te_seq, batch_size, shuffle=False)

    return train_dl, val_dl, test_dl, feat_scaler, tgt_scaler


# ─────────────────────────────────────────────
# 5. 24-Hour Block DataLoaders (Day-Ahead Planning)
# ─────────────────────────────────────────────

def create_block_sequences(X: np.ndarray, y: np.ndarray,
                           seq_len: int = 24, horizon: int = 24,
                           step: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """
    Tạo chuỗi đầu vào dạng 24-hour block:
      - Input : seq_len giờ lịch sử kết thúc tại dòng i -> (seq_len, n_features)
      - Target: horizon giờ tương lai [i+1, ..., i+horizon] -> (horizon,)

    Args:
        X       : (N, n_features) scaled features
        y       : (N, 1) scaled target
        seq_len : độ dài chuỗi lịch sử (mặc định 24)
        horizon : độ dài khối tương lai (mặc định 24)
        step    : bước trượt (1 cho train/val, 24 cho test không chồng lấn)

    Returns:
        X_seq : (n_samples, seq_len, n_features) float32
        y_seq : (n_samples, horizon) float32
    """
    X_list, y_list = [], []
    n = len(X)
    for i in range(seq_len - 1, n, step):
        if i + 1 >= n:
            break
        x_chunk = X[i - seq_len + 1 : i + 1]
        y_chunk = y[i + 1 : i + 1 + horizon].flatten()
        # Nếu khối cuối cùng của test bị thiếu giờ (< horizon), pad bằng giá trị biên
        if len(y_chunk) < horizon:
            pad_len = horizon - len(y_chunk)
            y_chunk = np.pad(y_chunk, (0, pad_len), mode="edge")
        X_list.append(x_chunk)
        y_list.append(y_chunk)
    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
    )


def build_block_dataloaders(seq_len: int = 24, horizon: int = 24,
                            batch_size: int = BATCH_SIZE,
                            verbose: bool = True):
    """
    Tạo DataLoaders cho bài toán dự báo theo khối 24 giờ (24-Hour Block).
      - Train & Val: step=1 để tối đa số mẫu học.
      - Test: step=horizon (24) để mô phỏng chính xác kịch bản xếp lịch ngày hôm sau:
        đầu ngày dự báo một lần cho cả 24 giờ tới mà không quan sát actual giữa ngày.

    Returns:
        train_dl, val_dl, test_dl, feat_scaler, tgt_scaler
    """
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()

    feat_scaler, tgt_scaler = fit_scalers(X_train, y_train)
    X_tr_sc, y_tr_sc = scale_data(X_train, y_train, feat_scaler, tgt_scaler)
    X_va_sc, y_va_sc = scale_data(X_val,   y_val,   feat_scaler, tgt_scaler)
    X_te_sc, y_te_sc = scale_data(X_test,  y_test,  feat_scaler, tgt_scaler)

    # Train & Val với step=1
    X_tr_seq, y_tr_seq = create_block_sequences(X_tr_sc, y_tr_sc, seq_len, horizon, step=1)
    X_va_seq, y_va_seq = create_block_sequences(X_va_sc, y_va_sc, seq_len, horizon, step=1)

    # Test: ghép seq_len dòng cuối Val làm lookback cho block đầu tiên, step=horizon (24)
    X_te_with_ctx = np.concatenate([X_va_sc[-seq_len:], X_te_sc], axis=0)
    y_te_with_ctx = np.concatenate([y_va_sc[-seq_len:], y_te_sc], axis=0)
    X_te_seq, y_te_seq = create_block_sequences(X_te_with_ctx, y_te_with_ctx, seq_len, horizon, step=horizon)

    if verbose:
        print(f"[Preprocess Block] seq_len={seq_len}, horizon={horizon}")
        print(f"  Train:  X={X_tr_seq.shape}, y={y_tr_seq.shape}")
        print(f"  Val:    X={X_va_seq.shape}, y={y_va_seq.shape}")
        print(f"  Test:   X={X_te_seq.shape}, y={y_te_seq.shape} ({len(X_te_seq)} blocks x {horizon}h)")

    train_dl = make_dataloader(X_tr_seq, y_tr_seq, batch_size, shuffle=False)
    val_dl   = make_dataloader(X_va_seq, y_va_seq, batch_size, shuffle=False)
    test_dl  = make_dataloader(X_te_seq, y_te_seq, batch_size, shuffle=False)

    return train_dl, val_dl, test_dl, feat_scaler, tgt_scaler
