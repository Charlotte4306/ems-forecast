"""Regression checks for time alignment and evaluation edge cases."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.prophet_data import REGRESSORS, load_data, load_split
from src.prophet_evaluate import compute_metrics
from src.prophet_model import predict


class DataTests(unittest.TestCase):
    def test_real_data_has_aligned_lags_and_separate_splits(self):
        splits = load_data()
        self.assertEqual([len(splits[s]) for s in ("train", "val", "test")],
                         [52440, 8760, 6796])
        self.assertLess(splits["train"].ds.max(), splits["val"].ds.min())
        self.assertLess(splits["val"].ds.max(), splits["test"].ds.min())

    def test_rejects_missing_hour_and_misaligned_lag(self):
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        X = pd.DataFrame({"year": dates.year, "month": dates.month,
                          "day_of_month": dates.day, "hour": dates.hour})
        for col in REGRESSORS:
            X[col] = 1.0
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            target = pd.DataFrame({"call_count": np.ones(200)})
            target.to_csv(directory / "y_train.csv", index=False)
            X.to_csv(directory / "X_train.csv", index=False)
            self.assertEqual(len(load_split(directory, "train")), 200)
            X.loc[100, "lag_1h"] = 99
            X.to_csv(directory / "X_train.csv", index=False)
            with self.assertRaisesRegex(ValueError, "misaligned"):
                load_split(directory, "train")
            X.loc[100, "lag_1h"] = 1
            X.loc[100, "hour"] += 1
            X.to_csv(directory / "X_train.csv", index=False)
            with self.assertRaisesRegex(ValueError, "hourly"):
                load_split(directory, "train")


class EvaluationTests(unittest.TestCase):
    def test_zero_targets_and_constant_series(self):
        metrics = compute_metrics([0, 0], [1, 1])
        self.assertEqual(metrics["MAE"], 1)
        self.assertIsNone(metrics["MAPE (%)"])
        self.assertIsNone(metrics["R2"])
        self.assertEqual(compute_metrics([0, 2], [1, 1])["MAPE (%)"], 50)

    def test_prediction_never_receives_target(self):
        class Model:
            extra_regressors = {"lag_1h": {}}

            def predict(self, frame):
                if list(frame.columns) != ["ds", "lag_1h"]:
                    raise AssertionError("Unexpected inference columns")
                return frame[["ds"]].assign(yhat=frame.lag_1h - 2)

        frame = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=2, freq="h"),
                              "lag_1h": [1, 3], "y": [999, 999]})
        np.testing.assert_array_equal(predict(Model(), frame).yhat, [0, 1])


if __name__ == "__main__":
    unittest.main()
