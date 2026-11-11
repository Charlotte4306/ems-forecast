"""Causal midnight shift boundaries and complete-shift scoring."""
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest

import numpy as np
import pandas as pd

from ems.paths import ROOT
from ems.queuing import SHIFT_PATTERNS, evaluate_plan, shift_plan


class CapacityShiftTests(unittest.TestCase):
    def test_configured_shifts_stay_within_the_midnight_forecast_day(self):
        times = pd.date_range('2026-01-01', periods=48, freq='h')
        for start, length in SHIFT_PATTERNS.values():
            self.assertEqual(start, 0)
            plan, origins = shift_plan(times, np.arange(48), start, length)
            self.assertFalse(plan.isna().any())
            self.assertTrue((origins.dt.normalize().to_numpy() == times.normalize().to_numpy()).all())
            for origin, values in plan.groupby(origins.values):
                self.assertEqual(len(values), length)
                self.assertEqual(origin.hour % length, 0)
                self.assertEqual(values.index[-1], origin + pd.Timedelta(hours=length - 1))

    def test_next_day_forecast_cannot_change_the_previous_evening_plan(self):
        times = pd.date_range('2026-01-01', periods=48, freq='h')
        before = np.full(48, 10)
        after = before.copy()
        after[24:] = 999
        for start, length in SHIFT_PATTERNS.values():
            old, _ = shift_plan(times, before, start, length)
            new, _ = shift_plan(times, after, start, length)
            np.testing.assert_array_equal(old.iloc[:24], new.iloc[:24])

    def test_real_hour_count_scores_6792_complete_shift_hours_only(self):
        times = pd.date_range('2026-01-01', periods=6796, freq='h')
        vehicles = np.full(6796, 10)
        for start, length in SHIFT_PATTERNS.values():
            plan, origins = shift_plan(times, vehicles, start, length)
            self.assertEqual(len(plan), 6796)
            self.assertEqual(plan.isna().sum(), 4)
            self.assertTrue(plan.iloc[-4:].isna().all())
            result = evaluate_plan(plan, vehicles, origins)
            self.assertEqual(result['Số giờ đánh giá'], 6792)
            self.assertEqual(result['Số giờ loại (ca chưa đủ)'], 4)
            self.assertEqual(result['Số ca đánh giá'], 6792 // length)
            self.assertEqual(result['Xe-giờ bố trí'], 67920)
            self.assertEqual(result['Xe-giờ thiếu'], 0)
        self.assertEqual(evaluate_plan(vehicles, vehicles)['Số giờ đánh giá'], 6796)

    def test_partial_tail_cannot_change_costs_or_complete_shift_sizes(self):
        times = pd.date_range('2026-01-01', periods=28, freq='h')
        hourly = np.full(28, 10.)
        need = np.full(28, 12.)
        plan, origins = shift_plan(times, hourly)
        baseline = evaluate_plan(plan, need, origins)
        hourly[-4:] = 99999
        need[-4:] = 99999
        changed, origins = shift_plan(times, hourly)
        self.assertEqual(evaluate_plan(changed, need, origins), baseline)

    def test_cost_formula_and_partial_first_shift(self):
        times = pd.date_range('2026-01-01', periods=16, freq='h')
        plan, origins = shift_plan(times, [1]*7 + [3] + [2]*8)
        result = evaluate_plan(plan, [4]*8 + [1]*8, origins, cost_ratios=(3,))
        self.assertEqual(result['Xe-giờ bố trí'], 40)
        self.assertEqual(result['Xe-giờ thiếu'], 8)
        self.assertEqual(result['Xe-giờ thừa'], 8)
        self.assertEqual(result['Chi phí (thiếu = 3× thừa)'], 32)
        self.assertEqual(result['% ca có giờ thiếu'], 50)
        times = pd.date_range('2026-01-01 02:00', periods=26, freq='h')
        plan, origins = shift_plan(times, np.ones(26))
        result = evaluate_plan(plan, np.ones(26), origins)
        self.assertEqual(result['Số giờ đánh giá'], 16)
        self.assertEqual(result['Số giờ loại (ca chưa đủ)'], 10)

    def test_gaps_and_duplicate_hours_do_not_count_as_complete_shifts(self):
        times = pd.date_range('2026-01-01', periods=9, freq='h')
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            shift_plan(times.delete(3), np.ones(8))
        with self.assertRaisesRegex(ValueError, 'unique'):
            shift_plan(times.insert(3, times[2]), np.ones(10))

    def test_notebook_and_generator_keep_the_same_non_optimizing_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'scripts/create_queueing_notebook.py'
            script.parent.mkdir()
            shutil.copyfile(ROOT / 'scripts/create_queueing_notebook.py', script)
            runpy.run_path(str(script), run_name='__main__')
            generated = json.loads((Path(directory) / 'notebooks/queueing_theory.ipynb').read_text(encoding='utf-8'))
        saved = json.loads((ROOT / 'notebooks/queueing_theory.ipynb').read_text(encoding='utf-8'))
        self.assertEqual([c['source'] for c in saved['cells']], [c['source'] for c in generated['cells']])
        source = '\n'.join(''.join(c['source']) for c in saved['cells'])
        self.assertNotIn('best_q', source)
        self.assertNotIn('best_quantile.csv', source)
        self.assertIn('Q_UPPER    = 0.90', source)
        self.assertIn('Khảo sát hậu kiểm', source)


if __name__ == '__main__':
    unittest.main()
