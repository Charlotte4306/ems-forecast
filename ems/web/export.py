"""Prepare real test predictions for the web. No training or scaler fitting."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

from ems.data import load_split, read_split
from ems.paths import ROOT, CHECKPOINT_DIR, DATA_DIR
from ems.models.lstm.model import build_model
from ems.models.lstm.preprocess import create_sequences, load_scalers, scale_data


def export(destination=ROOT / "outputs/web/dataset.json"):
    frame = load_split(DATA_DIR, "test")
    X, y = read_split(DATA_DIR, "test")
    features, target = load_scalers()
    X_scaled, y_scaled = scale_data(X, y, features, target)
    sequences, _ = create_sequences(X_scaled, y_scaled, 24)
    torch.set_num_threads(2)
    model = build_model("vanilla").cpu()
    checkpoint_path = CHECKPOINT_DIR / "lstm/vanilla_seq24_best.pth"
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    parts = []
    with torch.inference_mode():
        for (batch,) in DataLoader(TensorDataset(torch.from_numpy(sequences)), batch_size=128):
            parts.append(model(batch).numpy())
    lstm = np.maximum(target.inverse_transform(np.concatenate(parts)).ravel(), 0)
    prophet_path = ROOT / "outputs/prophet/test_predictions.csv"
    prophet = pd.read_csv(prophet_path, parse_dates=["ds"])
    if not prophet.ds.equals(frame.ds) or not np.allclose(prophet.y, frame.y):
        raise ValueError("Prophet prediction timestamps/targets differ from the current test data")
    if not np.isfinite(prophet.yhat).all():
        raise ValueError("Non-finite Prophet predictions")
    shared = frame.iloc[24:].reset_index(drop=True)
    rows = [{"time": row.ds.strftime("%Y-%m-%dT%H:%M:%S"), "actual": int(row.y),
             "prophet": float(max(prophet.yhat.iloc[i + 24], 0)), "lstm": float(lstm[i]),
             "baseline": float(row.lag_1h)} for i, row in enumerate(shared.itertuples())]
    source_paths = [DATA_DIR / "X_test.csv", DATA_DIR / "y_test.csv", prophet_path,
                    checkpoint_path, CHECKPOINT_DIR / "lstm/feat_scaler.pkl", CHECKPOINT_DIR / "lstm/tgt_scaler.pkl"]
    value = {
        "schemaVersion": 1,
        "metadata": {
            "source": "Dữ liệu test EMS San Francisco của dự án",
            "mode": "historical-evaluation", "region": "San Francisco",
            "timeConvention": "Giờ giữ nguyên CSV nguồn; chưa gắn múi giờ.",
            "start": rows[0]["time"], "end": rows[-1]["time"], "count": len(rows),
            "trainEnd": "2024-12-31T23:00:00", "validationYear": 2025,
            "uncertaintyAvailable": False,
            "models": {
                "prophet": {"name": "Prophet", "available": True, "description": "Trend, mùa vụ ngày/tuần/năm và lag/rolling/EWM. Cấu hình chọn bằng MAE validation.", "input": "14 biến lịch sử; có quan sát t−1."},
                "lstm": {"name": "LSTM", "available": True, "description": "Vanilla LSTM, 2 lớp, hidden size 128. Cửa sổ 24 giờ, 34 features.", "input": "Cách tạo sequence gốc làm lịch sử target mới nhất trong features tới t−2."},
                "arima": {"name": "ARIMA", "available": False, "description": "Chưa có mô hình hoặc checkpoint trong dự án."},
            },
            "versions": {p: version(p) for p in ("torch", "scikit-learn", "pandas", "numpy")},
            "sourceSha256": {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        },
        "rows": rows,
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    print(f"Prepared {len(rows):,} shared test hours: {destination}")


if __name__ == "__main__":
    export()
