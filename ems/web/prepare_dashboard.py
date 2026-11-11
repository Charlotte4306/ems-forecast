"""Bundle existing Prophet CSV results for the UI, without ML dependencies.

Optional --prophet24-ref reads an explicitly chosen local Git revision. It never
checks out, trains, commits, fetches, or changes model files.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess

from ems.paths import ROOT


def parse_predictions(raw, horizon):
    rows = []
    previous = None
    from datetime import datetime, timedelta
    for row in csv.DictReader(io.StringIO(raw)):
        # Unscored tail forecasts must not become observations.
        if not row.get("y", "").strip():
            continue
        time = datetime.fromisoformat(row["ds"])
        actual, prediction = float(row["y"]), float(row["yhat"])
        if not all(math.isfinite(x) and x >= 0 for x in (actual, prediction)):
            raise ValueError("Invalid target or prediction")
        if previous is not None and time - previous != timedelta(hours=1):
            raise ValueError("Results must be hourly and contiguous")
        value = {"time": time.isoformat(), "actual": actual, "prediction": prediction}
        if horizon == 24:
            origin = datetime.fromisoformat(row["forecast_origin"])
            cutoff = datetime.fromisoformat(row["history_cutoff"])
            lead = int(row["lead_hour"])
            if not (1 <= lead <= 24 and origin.hour == 0 and
                    cutoff < origin and cutoff == origin - timedelta(hours=1) and
                    time == origin + timedelta(hours=lead - 1)):
                raise ValueError("Invalid day-ahead origin or history cutoff")
            value.update(origin=origin.isoformat(), cutoff=cutoff.isoformat(), lead=lead)
        rows.append(value)
        previous = time
    if not rows:
        raise ValueError("No scored predictions")
    return rows


def prepare(destination, prophet24_ref=None):
    destination = Path(destination)
    # Initialize from current forecast artifacts; an old LSTM export is not required.
    value = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {"schemaVersion": 1}
    path = ROOT / "outputs/prophet/test_predictions.csv"
    raw = path.read_text(encoding="utf-8")
    profiles = {"prophet_h1": {"name": "Prophet", "horizon": 1,
        "description": "Dự báo từng giờ; cập nhật đặc trưng bằng quan sát của giờ trước.",
        "source": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": hashlib.sha256(raw.encode()).hexdigest(), "rows": parse_predictions(raw, 1)}}
    if prophet24_ref:
        revision = subprocess.check_output(["git", "rev-parse", "--verify", prophet24_ref + "^{commit}"], cwd=ROOT, text=True).strip()
        artifact = "outputs/prophet/day_ahead_24h/test_selected/predictions_24h.csv"
        raw24 = subprocess.check_output(["git", "show", revision + ":" + artifact], cwd=ROOT).decode("utf-8")
        rows24 = parse_predictions(raw24, 24)
        expected = [(r["time"], r["actual"]) for r in profiles["prophet_h1"]["rows"]]
        if [(r["time"], r["actual"]) for r in rows24] != expected:
            raise ValueError("Day-ahead timestamps/actuals differ from H1 test")
        profiles["prophet_h24"] = {"name": "Prophet", "horizon": 24,
            "description": "Phát hành lúc 00:00; dự báo đệ quy 24 giờ, không cập nhật bằng số thực tế trong ngày.",
            "source": artifact, "revision": revision,
            "sha256": hashlib.sha256(raw24.encode()).hexdigest(), "rows": rows24}
    value["profiles"] = profiles
    value.pop("rows", None)  # Superseded two-model export; the UI uses profiles.
    rows = profiles["prophet_h1"]["rows"]
    value["metadata"] = {"mode": "historical-evaluation", "region": "San Francisco",
        "target": "medic-dispatches", "timeField": "received_dttm", "unit": "dispatches",
        "count": len(rows), "start": rows[0]["time"], "end": rows[-1]["time"]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    print({key: len(profile["rows"]) for key, profile in profiles.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "outputs/web/dataset.json")
    parser.add_argument("--prophet24-ref")
    args = parser.parse_args()
    prepare(args.destination, args.prophet24_ref)
