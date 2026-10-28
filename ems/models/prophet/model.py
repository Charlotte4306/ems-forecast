"""Prophet factories, inference and portable JSON checkpoints."""
from pathlib import Path

import numpy as np
from prophet import Prophet
from prophet.serialize import model_from_json, model_to_json

from ems.data import REGRESSORS

SEED = 42


def build_model(changepoint_prior_scale=0.05, use_regressors=False):
    model = Prophet(
        daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True,
        seasonality_mode="additive", changepoint_prior_scale=changepoint_prior_scale,
        uncertainty_samples=0,
    )
    if use_regressors:
        for col in REGRESSORS:
            model.add_regressor(col, standardize=True)
    return model


def predict(model, frame):
    # Never pass evaluation targets to Prophet's predict method.
    columns = ["ds", *model.extra_regressors]
    forecast = model.predict(frame[columns])
    return forecast[["ds", "yhat"]].assign(yhat=lambda f: np.maximum(f.yhat, 0))


def save_model(model, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model_to_json(model), encoding="utf-8")


def load_model(path: Path):
    return model_from_json(path.read_text(encoding="utf-8"))
