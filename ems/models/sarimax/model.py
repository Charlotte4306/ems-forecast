"""Hourly calendar regressors and forecasts issued in consecutive 24-hour blocks."""
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from ems.data import load_data
from ems.evaluation import compute_metrics
from ems.paths import DATA_DIR

GRID = (((1, 0, 1), 3), ((1, 0, 1), 4), ((2, 0, 1), 4),
        ((1, 0, 2), 4), ((2, 0, 2), 4))


def load_series(data_dir=DATA_DIR):
    """Reuse shared split, timestamp, target and lag-alignment validation."""
    return {name: frame.set_index("ds")["y"].asfreq("h")
            for name, frame in load_data(data_dir).items()}


def make_exog(index, K=4):
    if K < 1:
        raise ValueError("Fourier order K must be positive")
    index = pd.DatetimeIndex(index)
    if index.empty:
        raise ValueError("Calendar index must not be empty")
    hour, dow = index.hour.to_numpy(), index.day_of_week.to_numpy()
    weekend = (dow >= 5).astype(float)
    features = pd.DataFrame(index=index)
    for k in range(1, K + 1):
        sine, cosine = np.sin(2 * np.pi * k * hour / 24), np.cos(2 * np.pi * k * hour / 24)
        features[f"s{k}"], features[f"c{k}"] = sine, cosine
        features[f"s{k}_we"], features[f"c{k}_we"] = sine * weekend, cosine * weekend
    for day in range(1, 7):
        features[f"dow{day}"] = (dow == day).astype(float)
    holidays = USFederalHolidayCalendar().holidays(index.min().normalize(), index.max().normalize())
    features["holiday"] = index.normalize().isin(holidays).astype(float)
    return features


def metrics(frame):
    result = compute_metrics(frame.actual.to_numpy(), frame.pred.to_numpy())
    total = float(frame.actual.abs().sum())
    result["WAPE (%)"] = float(100 * (frame.actual - frame.pred).abs().sum() / total) if total else None
    if {"lo", "hi"}.issubset(frame.columns):
        result["coverage_80 (%)"] = float(frame.actual.between(frame.lo, frame.hi).mean() * 100)
        result["mean_interval_width"] = float((frame.hi - frame.lo).mean())
    return result


def rolling_forecast(result, actual, exog, horizon=24):
    """Observe a block only AFTER forecasting it, without refitting parameters.

    extend filters only new observations using the previous final state, avoiding
    append's repeated filtering of the entire historical series.
    """
    if horizon < 1 or actual.empty or not actual.index.equals(exog.index):
        raise ValueError("Expected aligned non-empty data and a positive horizon")
    current, blocks = result, []
    for start in range(0, len(actual), horizon):
        observed = actual.iloc[start:start + horizon]
        features = exog.iloc[start:start + horizon]
        forecast = current.get_forecast(steps=len(observed), exog=features)
        interval = np.asarray(forecast.conf_int(alpha=0.2))
        blocks.append(pd.DataFrame({
            "actual": observed.to_numpy(), "pred": np.asarray(forecast.predicted_mean),
            "lo": interval[:, 0], "hi": interval[:, 1],
        }, index=observed.index))
        # A day-of-week dummy can be all ones within a single 24h block. The
        # complete design was validated at fit time; avoid reinterpreting that
        # temporary block as a duplicate constant alongside the model intercept.
        current = current.extend(observed, exog=features, validate_specification=False)
    predictions = pd.concat(blocks)
    predictions[["pred", "lo", "hi"]] = predictions[["pred", "lo", "hi"]].clip(lower=0)
    return predictions


def baselines(history, actual):
    """Fixed historical calendar profile; seasonal naive uses observed lag 168h."""
    if history.empty or actual.empty or history.index[-1] + pd.Timedelta(hours=1) != actual.index[0]:
        raise ValueError("History must end one hour before predictions start")
    profile = history.groupby([history.index.hour, history.index.day_of_week]).mean()
    lookup = list(zip(actual.index.hour, actual.index.day_of_week))
    profile_prediction = pd.Series([profile.get(key, history.mean()) for key in lookup], index=actual.index)
    seasonal = pd.concat([history, actual]).shift(168).loc[actual.index]
    # fillna requires an indexed Series, not the original NumPy array.
    return {"Seasonal Naive (168h)": seasonal.fillna(profile_prediction),
            "Lịch sử Giờ x Thứ": profile_prediction}
