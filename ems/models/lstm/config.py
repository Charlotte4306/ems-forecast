"""
Hyperparameters & paths config cho EMS LSTM Forecasting
"""
import os

# ── Paths ──────────────────────────────────────────────────────────────────
from ems.paths import ROOT, DATA_DIR as SHARED_DATA_DIR, CHECKPOINT_DIR, OUTPUT_DIR as SHARED_OUTPUT_DIR

ROOT_DIR   = str(ROOT)
DATA_DIR   = str(SHARED_DATA_DIR)
CKPT_DIR   = str(CHECKPOINT_DIR / "lstm")
OUTPUT_DIR = str(SHARED_OUTPUT_DIR / "lstm")

# ── Data ───────────────────────────────────────────────────────────────────
FEATURE_COLS = [
    "hour", "day_of_week", "month", "year", "day_of_month",
    "week_of_year", "quarter", "is_weekend",
    "sin_hour", "cos_hour", "sin_dow", "cos_dow", "sin_month", "cos_month",
    "rolling_mean_6h", "rolling_std_6h",
    "rolling_mean_12h", "rolling_std_12h",
    "rolling_mean_24h", "rolling_std_24h",
    "rolling_mean_48h", "rolling_std_48h",
    "rolling_mean_168h", "rolling_std_168h",
    "ewm_24h", "ewm_168h",
    "lag_1h", "lag_2h", "lag_3h", "lag_6h",
    "lag_12h", "lag_24h", "lag_48h", "lag_168h",
]
TARGET_COL = "call_count"
N_FEATURES = len(FEATURE_COLS)   # 34

# ── Sequence ────────────────────────────────────────────────────────────────
SEQ_LENGTHS = [24, 168]           # thử cả hai để so sánh
DEFAULT_SEQ_LEN = 24

# ── Model ───────────────────────────────────────────────────────────────────
HIDDEN_SIZE  = 128
NUM_LAYERS   = 2
DROPOUT      = 0.2
BIDIRECTIONAL = False            # True → Bidirectional

# ── Training ────────────────────────────────────────────────────────────────
BATCH_SIZE       = 64
NUM_EPOCHS       = 30
LEARNING_RATE    = 1e-3
WEIGHT_DECAY     = 1e-5
SCHEDULER_PATIENCE = 5
SCHEDULER_FACTOR   = 0.5
EARLY_STOP_PATIENCE = 10
GRAD_CLIP        = 1.0           # gradient clipping

# ── Device ──────────────────────────────────────────────────────────────────
import torch
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ── Random seed ─────────────────────────────────────────────────────────────
SEED = 42

# ── Tạo thư mục nếu chưa có ──────────────────────────────────────────────
for d in [CKPT_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)
