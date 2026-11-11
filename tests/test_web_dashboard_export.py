import unittest

from ems.web.prepare_dashboard import parse_predictions


class DashboardExportTests(unittest.TestCase):
    def test_unscored_tail_does_not_become_actual_zero(self):
        source = 'ds,y,yhat\n2026-01-01 00:00:00,0,2\n2026-01-01 01:00:00,,3\n'
        rows = parse_predictions(source, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actual'], 0)

    def test_future_observation_cutoff_is_rejected(self):
        source = ('ds,y,yhat,forecast_origin,history_cutoff,lead_hour\n'
                  '2026-01-01 00:00:00,10,11,2026-01-01 00:00:00,2026-01-01 01:00:00,1\n')
        with self.assertRaises(ValueError):
            parse_predictions(source, 24)

    def test_missing_hour_and_non_finite_prediction_are_rejected(self):
        for source in ('ds,y,yhat\n2026-01-01 00:00:00,1,nan\n',
                       'ds,y,yhat\n2026-01-01 00:00:00,1,2\n2026-01-01 02:00:00,1,2\n'):
            with self.assertRaises(ValueError):
                parse_predictions(source, 1)
