"""
LSTM Model Architectures
  - VanillaLSTM  : baseline đơn giản
  - StackedBiLSTM: Stacked Bidirectional (Phase 2B)
  - AttentionLSTM: LSTM + Self-Attention  (Phase 2C)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


# ─────────────────────────────────────────────
# Option A — Vanilla LSTM (baseline)
# ─────────────────────────────────────────────

class VanillaLSTM(nn.Module):
    """
    Kiến trúc:
        Input  (batch, seq_len, n_features)
        → LSTM (hidden_size, num_layers, dropout)
        → lấy hidden state ở bước cuối
        → FC(hidden → fc_size) → ReLU → Dropout
        → FC(fc_size → 1)
        Output (batch, 1)
    """
    def __init__(
        self,
        n_features:  int   = 34,
        hidden_size: int   = 128,
        num_layers:  int   = 2,
        dropout:     float = 0.2,
        fc_size:     int   = 64,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, fc_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_size, 1),
        )

    def forward(self, x):
        # x: (batch, seq_len, n_features)
        out, _ = self.lstm(x)           # out: (batch, seq_len, hidden)
        last = out[:, -1, :]            # lấy timestep cuối: (batch, hidden)
        return self.fc(last)            # (batch, 1)


# ─────────────────────────────────────────────
# Option B — Stacked Bidirectional LSTM
# ─────────────────────────────────────────────

class StackedBiLSTM(nn.Module):
    """
    Bidirectional LSTM: hidden_size * 2 → FC
    """
    def __init__(
        self,
        n_features:  int   = 34,
        hidden_size: int   = 128,
        num_layers:  int   = 2,
        dropout:     float = 0.3,
        fc_size:     int   = 64,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
            bidirectional=True,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size * 2, fc_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_size, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)           # (batch, seq_len, hidden*2)
        last = out[:, -1, :]            # (batch, hidden*2)
        return self.fc(last)


# ─────────────────────────────────────────────
# Option C — LSTM + Scaled Dot-Product Attention
# ─────────────────────────────────────────────

class _Attention(nn.Module):
    """
    Scaled dot-product attention over LSTM output timesteps.
    Trả về context vector (batch, hidden_size).
    """
    def __init__(self, hidden_size: int):
        super().__init__()
        self.query = nn.Linear(hidden_size, hidden_size, bias=False)
        self.key   = nn.Linear(hidden_size, hidden_size, bias=False)
        self.value = nn.Linear(hidden_size, hidden_size, bias=False)
        self.scale = hidden_size ** 0.5

    def forward(self, lstm_out):
        # lstm_out: (batch, seq_len, hidden)
        Q = self.query(lstm_out)        # (batch, seq_len, hidden)
        K = self.key(lstm_out)
        V = self.value(lstm_out)

        scores = torch.bmm(Q, K.transpose(1, 2)) / self.scale  # (batch, seq, seq)
        weights = F.softmax(scores, dim=-1)                     # attention weights
        context = torch.bmm(weights, V)                         # (batch, seq, hidden)
        # Aggregate: mean over timesteps
        return context.mean(dim=1)                              # (batch, hidden)


class AttentionLSTM(nn.Module):
    """
    LSTM + Attention → FC
    """
    def __init__(
        self,
        n_features:  int   = 34,
        hidden_size: int   = 128,
        num_layers:  int   = 2,
        dropout:     float = 0.2,
        fc_size:     int   = 64,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.attention = _Attention(hidden_size)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, fc_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_size, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)           # (batch, seq_len, hidden)
        context = self.attention(out)   # (batch, hidden)
        return self.fc(context)         # (batch, 1)


# ─────────────────────────────────────────────
# Factory helper
# ─────────────────────────────────────────────

MODEL_REGISTRY = {
    "vanilla":    VanillaLSTM,
    "stacked_bi": StackedBiLSTM,
    "attention":  AttentionLSTM,
}

def build_model(name: str = "vanilla", **kwargs) -> nn.Module:
    """
    Khởi tạo model theo tên.
    Ví dụ: build_model("vanilla", hidden_size=128, num_layers=2)
    """
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}. Choices: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[name](**kwargs)
