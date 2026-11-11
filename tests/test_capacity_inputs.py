import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from ems.capacity_inputs import load_sarimax_day_ahead
from ems.data import load_data
from ems.paths import ROOT


class CapacityInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.predictions = Path(self.directory.name) / 'predictions.csv'
        self.metadata = Path(self.directory.name) / 'metrics.json'
        self.index = pd.date_range('2026-01-01', periods=3, freq='h', name='timestamp')
        self.actual = pd.Series([5., 0., 10.], index=self.index)
        self.frame = pd.DataFrame({'actual': self.actual, 'pred': [6., 1., 9.],
                                   'lo': [4., 0., 8.], 'hi': [8., 2., 12.]})
        self.frame.to_csv(self.predictions)
        self.details = {'refit': False, 'horizon_hours': 24,
                        'final_fit': {'end': '2024-12-31 23:00:00'},
                        'test_metrics': {'all_test': {'MAE': 1.}}}
        self.write_metadata()

    def write_metadata(self):
        self.metadata.write_text(json.dumps(self.details), encoding='utf-8')

    def load(self):
        return load_sarimax_day_ahead(self.predictions, self.metadata, self.actual,
                                     training_end='2024-12-31 23:00:00')

    def test_valid_frozen_24h_input_is_loaded(self):
        result = self.load()
        self.assertEqual(result.index.tolist(), self.index.tolist())
        self.assertEqual(result.pred.tolist(), [6., 1., 9.])

    def test_refit_and_wrong_horizon_are_rejected(self):
        for field, value in [('refit', True), ('horizon_hours', 1)]:
            with self.subTest(field=field):
                original = self.details[field]
                self.details[field] = value
                self.write_metadata()
                with self.assertRaisesRegex(ValueError, 'refit=false'):
                    self.load()
                self.details[field] = original

    def test_future_fit_cutoff_is_rejected(self):
        self.details['final_fit']['end'] = '2025-12-31 23:00:00'
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, 'training cutoff'):
            self.load()

    def test_an_old_csv_cannot_be_paired_with_new_metadata(self):
        self.frame['pred'] += .2
        self.frame.to_csv(self.predictions)
        with self.assertRaisesRegex(ValueError, 'metadata MAE'):
            self.load()

    def test_wrong_actuals_and_invalid_bounds_are_rejected(self):
        self.frame.loc[self.index[0], 'actual'] = 99
        self.frame.to_csv(self.predictions)
        with self.assertRaisesRegex(ValueError, 'shared test hours'):
            self.load()
        self.frame['actual'] = self.actual
        self.frame.loc[self.index[0], 'lo'] = 100
        self.frame.to_csv(self.predictions)
        with self.assertRaisesRegex(ValueError, 'interval bounds'):
            self.load()

    def test_real_imported_run_covers_all_shared_test_hours(self):
        splits = load_data()
        actual = splits['test'].set_index('ds').y.astype(float)
        folder = ROOT / 'outputs/sarimax/norefit'
        result = load_sarimax_day_ahead(folder / 'pred_sarimax.csv', folder / 'metrics.json',
                                      actual, splits['train'].ds.iloc[-1])
        self.assertEqual(len(result), 6796)
        self.assertAlmostEqual((result.actual - result.pred).abs().mean(), 3.012486314823568)


if __name__ == '__main__':
    unittest.main()
