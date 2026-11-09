"""Behavioral checks for recursive features and day-ahead information boundaries."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from ems.data import REGRESSORS, load_data
from ems.models.prophet.forecast import _History, forecast_24h
from ems.models.prophet.model import load_model
from ems.paths import CHECKPOINT_DIR
from ems.models.prophet.select_24h import select_day_ahead


def make_frame(start, values):
    frame = pd.DataFrame({"ds": pd.date_range(start, periods=len(values), freq="h"),
                          "y": np.asarray(values, dtype=float)})
    for span in (24, 168):
        frame[f"ewm_{span}h"] = frame.y.shift(1).ewm(span=span, adjust=False).mean()
    return frame


class LagModel:
    extra_regressors = {name: {} for name in REGRESSORS}

    def predict(self, frame):
        if "y" in frame:
            raise AssertionError("Target leaked into inference")
        return frame[["ds"]].assign(yhat=frame.lag_1h + 1)


class DayAheadTests(unittest.TestCase):
    def setUp(self):
        frame = make_frame("2024-12-25", np.arange(216) % 20 + 1)
        self.history, self.evaluation = frame.iloc[:168], frame.iloc[168:]

    def test_recursive_predictions_and_day_boundary_updates(self):
        result = forecast_24h(LagModel(), self.history, self.evaluation)
        last = self.history.y.iloc[-1]
        np.testing.assert_allclose(result.yhat.iloc[:24], last + np.arange(1, 25))
        self.assertEqual(result.yhat.iloc[24], self.evaluation.y.iloc[23] + 1)
        self.assertEqual(result.lead_hour.tolist(), list(range(1, 25)) * 2)
        self.assertEqual(result.forecast_origin.iloc[0], pd.Timestamp("2025-01-01"))
        self.assertEqual(result.history_cutoff.iloc[0], self.history.ds.iloc[-1])

    def test_future_actuals_and_precomputed_features_cannot_affect_same_day(self):
        first = forecast_24h(LagModel(), self.history, self.evaluation)
        changed = self.evaluation.copy()
        changed.loc[:, "y"] = 999.0
        for name in REGRESSORS:
            changed[name] = 123456.0
        second = forecast_24h(LagModel(), self.history, changed)
        np.testing.assert_array_equal(first.yhat.iloc[:24], second.yhat.iloc[:24])
        self.assertNotEqual(first.yhat.iloc[24], second.yhat.iloc[24])

    def test_features_match_shifted_pandas_calculations(self):
        frame = make_frame("2024-12-01", np.arange(250) % 17 + 2)
        state = _History(frame.iloc[:180])
        for end in range(180, 200):
            actual = state.features(frame.ds.iloc[end]).iloc[0]
            past = frame.y.iloc[:end]
            for lag in (1, 2, 3, 6, 12, 24, 48, 168):
                self.assertEqual(actual[f"lag_{lag}h"], past.iloc[-lag])
            for window in (24, 168):
                self.assertAlmostEqual(actual[f"rolling_mean_{window}h"], past.iloc[-window:].mean())
                self.assertAlmostEqual(actual[f"rolling_std_{window}h"], past.iloc[-window:].std())
                self.assertAlmostEqual(actual[f"ewm_{window}h"], past.ewm(span=window, adjust=False).mean().iloc[-1])
            state.observe(frame.y.iloc[end])

    def test_real_origin_features_match_exported_csv(self):
        splits = load_data()
        history = pd.concat([splits["train"], splits["val"]], ignore_index=True)
        state = _History(history)
        for row in splits["test"].iloc[:25].itertuples():
            actual = state.features(row.ds)
            for name in REGRESSORS:
                self.assertAlmostEqual(actual[name].iloc[0], getattr(row, name), places=8)
            state.observe(row.y)

    def test_fast_additive_path_matches_public_predict_on_real_checkpoint(self):
        splits = load_data()
        model = load_model(CHECKPOINT_DIR / "prophet/best_model.json")
        val = splits["val"].iloc[:48]
        fast = forecast_24h(model, splits["train"], val)
        reference = forecast_24h(model, splits["train"], val, fast=False)
        np.testing.assert_allclose(fast.yhat, reference.yhat, rtol=0, atol=1e-10)

    def test_partial_last_day_is_excluded_and_limit_is_respected(self):
        result = forecast_24h(LagModel(), self.history, self.evaluation.iloc[:28])
        self.assertEqual(len(result), 24)
        self.assertEqual(len(forecast_24h(LagModel(), self.history, self.evaluation, max_days=1)), 24)
        with self.assertRaises(ValueError):
            forecast_24h(LagModel(), self.history, self.evaluation.iloc[:23])
        with self.assertRaises(ValueError):
            forecast_24h(LagModel(), self.history, self.evaluation, max_days=0)

    def test_rejects_future_fitted_checkpoint_and_time_gap(self):
        model = LagModel()
        model.history = self.evaluation[["ds"]]
        with self.assertRaisesRegex(ValueError, "Checkpoint"):
            forecast_24h(model, self.history, self.evaluation)
        shifted = self.evaluation.copy()
        shifted["ds"] += pd.Timedelta(hours=1)
        with self.assertRaisesRegex(ValueError, "continuous"):
            forecast_24h(LagModel(), self.history, shifted)


class SelectionTests(unittest.TestCase):
    def test_selects_by_full_validation_mae_without_loading_test(self):
        history = make_frame("2024-12-25", np.full(168, 3.0))
        val = make_frame("2025-01-01", np.full(48, 3.0))
        for name in REGRESSORS:
            if name not in history:
                history[name] = 3.0
            if name not in val:
                val[name] = 3.0

        class ConstantModel:
            def __init__(self, value, regressors):
                self.value = value
                self.extra_regressors = {name: {} for name in REGRESSORS} if regressors else {}

            def fit(self, frame, seed):
                self.history = frame[["ds"]]

            def predict(self, frame):
                return frame[["ds"]].assign(yhat=self.value)

        def build(prior, regressors):
            return ConstantModel((3 if regressors else 1) + (prior == 0.05), regressors)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for prefix in ("X", "y"):
                for split in ("train", "val"):
                    (root / f"{prefix}_{split}.csv").write_text("fixture", encoding="utf-8")
            with patch("ems.models.prophet.select_24h.load_split",
                       side_effect=lambda _, split: {"train": history, "val": val}[split]) as load, \
                 patch("ems.models.prophet.select_24h.build_model", side_effect=build), \
                 patch("ems.models.prophet.select_24h.save_model",
                       side_effect=lambda model, path: path.write_text(str(model.value))):
                metadata = select_day_ahead(root, root / "out", root / "checkpoint")
            self.assertEqual([call.args[1] for call in load.call_args_list], ["train", "val"])
            self.assertEqual(metadata["selected"]["name"], "prophet_lags_cp0.01")
            self.assertEqual(metadata["selected"]["MAE"], 0)
            self.assertFalse(metadata["test_evaluated"])
            self.assertEqual(metadata["n_validation_hours"], 48)
            self.assertEqual((root / "checkpoint/best_model.json").read_text(), "3")


if __name__ == "__main__":
    unittest.main()
