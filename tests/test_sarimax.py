"""Regression coverage for SARIMAX state updates, artifacts and capacity costs."""
import importlib
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
import json
from unittest.mock import patch

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX, SARIMAXResults

from ems.models.sarimax.model import baselines, make_exog, metrics, rolling_forecast
from ems.models.sarimax.capacity_planning import capacity_summary, read_predictions, run_capacity
from ems.paths import CHECKPOINT_DIR, OUTPUT_DIR


class SarimaxTests(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2025-01-01", periods=245, freq="h")
        rng = np.random.default_rng(7)
        self.series = pd.Series(12 + 3 * np.sin(np.arange(245) * 2 * np.pi / 24)
                                + rng.normal(size=245), index=index)
        self.history, self.actual = self.series.iloc[:192], self.series.iloc[192:]

    def test_import_does_not_execute_experiment(self):
        with patch("pandas.read_csv", side_effect=AssertionError("import read data")):
            with redirect_stdout(io.StringIO()) as output:
                importlib.reload(importlib.import_module("ems.models.sarimax.run_sarimax"))
                importlib.reload(importlib.import_module("ems.models.sarimax.capacity_planning"))
        self.assertEqual(output.getvalue(), "")

    def test_calendar_schema_and_holidays_outside_original_year_range(self):
        index = pd.date_range("2027-01-01", periods=72, freq="h")
        features = make_exog(index)
        self.assertEqual(features.shape, (72, 23))
        self.assertEqual(features.iloc[0].holiday, 1)
        self.assertEqual(features.loc["2027-01-02 00:00:00", "c1_we"], 1)
        self.assertTrue(np.isfinite(features.to_numpy()).all())

    def test_rolling_extend_matches_append_and_does_not_peek_inside_block(self):
        features = make_exog(self.history.index, 1)
        model = SARIMAX(self.history, exog=features, order=(1, 0, 0), trend="c")
        params = np.zeros(len(model.param_names))
        params[0], params[-2], params[-1] = 6, .5, 1
        fitted = model.filter(params)
        future = make_exog(self.actual.index, 1)
        result = rolling_forecast(fitted, self.actual, future)
        expected, current = [], fitted
        for start in range(0, len(self.actual), 24):
            observed, exog = self.actual.iloc[start:start + 24], future.iloc[start:start + 24]
            forecast = current.get_forecast(len(observed), exog=exog)
            expected.extend(forecast.predicted_mean)
            current = current.append(observed, exog=exog, refit=False)
        np.testing.assert_allclose(result.pred, np.maximum(0, expected), rtol=1e-10, atol=1e-10)
        changed = self.actual.copy()
        changed.iloc[:24] += 20
        alternate = rolling_forecast(fitted, changed, future)
        np.testing.assert_allclose(result.pred.iloc[:24], alternate.pred.iloc[:24])
        self.assertGreater(abs(result.pred.iloc[24] - alternate.pred.iloc[24]), 1)

    def test_failed_convergence_is_not_silently_accepted(self):
        from types import SimpleNamespace
        from ems.models.sarimax.run_sarimax import fit_model
        with patch("statsmodels.tsa.statespace.sarimax.SARIMAX") as constructor:
            constructor.return_value.fit.return_value = SimpleNamespace(mle_retvals={"converged": False})
            with self.assertRaisesRegex(RuntimeError, "did not converge"):
                fit_model(self.history, (1, 0, 0), 1, 1)

    def test_seasonal_naive_fallback_is_an_aligned_series(self):
        # Short history deliberately exercises the previously broken fillna path.
        history = self.history.iloc[-24:]
        result = baselines(history, self.actual)
        self.assertFalse(result["Seasonal Naive (168h)"].isna().any())
        pd.testing.assert_series_equal(result["Seasonal Naive (168h)"], result["Lịch sử Giờ x Thứ"])

    def test_wape_includes_zero_target_error(self):
        frame = pd.DataFrame({"actual": [0., 10.], "pred": [2., 8.]})
        self.assertEqual(metrics(frame)["WAPE (%)"], 40)
        self.assertIsNone(metrics(frame.assign(actual=0))["WAPE (%)"])

    def test_original_capacity_costs_and_invalid_inputs(self):
        # Evaluate the committed artifact using independently calculated costs.
        from ems.models.sarimax.model import load_series
        splits = load_series()
        frame = read_predictions(OUTPUT_DIR / "sarimax/pred_sarimax.csv", splits["test"])
        history = pd.concat([splits["train"], splits["val"]]).iloc[-8760:]
        baseline = baselines(history, frame.actual)
        summary, _ = capacity_summary(frame, baseline)
        # Compute from committed predictions instead of hardcoding a fitted model's metrics.
        assigned = np.ceil(frame.pred / 3)
        needed = np.ceil(frame.actual / 3)
        expected = ((assigned - needed).clip(lower=0) * 30 + (needed - assigned).clip(lower=0) * 75).sum()
        self.assertEqual(summary.iloc[2]["TỔNG CHI PHÍ ($)"], expected)
        with self.assertRaises(ValueError):
            capacity_summary(frame, baseline, mu=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            frame.assign(hi=frame.lo - 1).to_csv(path)
            with self.assertRaises(ValueError):
                read_predictions(path, splits["test"])

    def test_reports_from_other_working_directory(self):
        import os
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with redirect_stdout(io.StringIO()):
                    run_capacity(output_dir=Path(directory) / "reports")
            finally:
                os.chdir(previous)
            for name in ["capacity_metadata.json", "staffing_schedule.csv", "capacity_cost_evaluation.csv",
                         "figures/hourly_mae.png", "figures/cost_comparison.png"]:
                self.assertTrue((Path(directory) / "reports" / name).is_file())

    def test_saved_checkpoint_forecasts_the_next_unseen_block(self):
        from ems.models.sarimax.model import load_series
        checkpoint = CHECKPOINT_DIR / "sarimax/best_model.pkl"
        if not checkpoint.exists():
            self.skipTest("Run SARIMAX to create its checkpoint before checking serialization")
        metadata = json.loads((checkpoint.parent / "metadata.json").read_text(encoding="utf-8"))
        test = load_series()["test"].iloc[:24]
        fitted = SARIMAXResults.load(checkpoint)
        forecast = fitted.get_forecast(len(test), exog=make_exog(test.index, metadata["selected"]["K"]))
        self.assertEqual(pd.Timestamp(metadata["final_fit"]["end"]) + pd.Timedelta(hours=1), test.index[0])
        self.assertEqual(fitted.nobs, metadata["final_fit"]["rows"])
        self.assertTrue(forecast.predicted_mean.index.equals(test.index))
        self.assertTrue(np.isfinite(forecast.predicted_mean).all())
        self.assertTrue(metadata["converged"])


if __name__ == "__main__":
    unittest.main()
