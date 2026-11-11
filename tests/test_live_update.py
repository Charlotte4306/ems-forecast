from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ems.live.update import atomic_json, normalize, run


class LiveUpdateTests(unittest.TestCase):
    def test_unique_hour_counts_and_explicit_zero_hours(self):
        start = datetime(2026, 11, 8)
        rows = normalize([{'day': '2026-11-08T00:00:00.000', 'hour': '1', 'dispatch_count': '12'}], start, start + timedelta(days=1))
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0]['dispatches'], 0)
        self.assertEqual(rows[1]['dispatches'], 12)
        with self.assertRaises(ValueError):
            normalize([], start, start + timedelta(days=1))
        with self.assertRaises(ValueError):
            normalize([{'day': '2026-11-08T00:00:00', 'hour': '1', 'dispatch_count': '-1'}], start, start + timedelta(days=1))

    def test_latest_partial_day_is_excluded_and_snapshot_is_published(self):
        raw = [{'day': (datetime(2026, 9, 12)+timedelta(days=i)).isoformat(), 'hour': '1', 'dispatch_count': '12'} for i in range(60)]
        with tempfile.TemporaryDirectory() as directory, patch('ems.live.update.fetch', side_effect=[[{'latest': '2026-11-11T03:00:00'}], raw]) as fetch, patch('ems.live.update.forecast', return_value=([], [], 2.5)) as forecast, patch('ems.live.update.version', return_value='test'):
            value = run(directory, datetime(2026, 11, 11, 18, tzinfo=timezone.utc), lookback=60)
            self.assertEqual(value['observedThrough'], '2026-11-10T23:00:00')
            self.assertEqual(value['trainingHours'], 1440)
            self.assertIn("dispatch_dttm < '2026-11-11T00:00:00'", fetch.call_args.args[0]['$where'])
            self.assertIn('count(distinct rowid) as dispatch_count', fetch.call_args.args[0]['$select'])
            self.assertIn('date_extract_hh(dispatch_dttm)', fetch.call_args.args[0]['$select'])
            self.assertNotIn('call_number', fetch.call_args.args[0]['$select'])
            self.assertEqual(forecast.call_args.args[1], datetime(2026, 11, 11))
            self.assertEqual(json.loads((Path(directory)/'forecast.json').read_text())['target'], 'medic-dispatches')
            self.assertEqual(value['unit'], 'dispatches')
            self.assertEqual(value['timeField'], 'dispatch_dttm')

    def test_stale_source_preserves_previous_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'forecast.json'
            atomic_json(output, {'previous': True})
            with patch('ems.live.update.fetch', return_value=[{'latest': '2026-10-01T03:00:00'}]):
                with self.assertRaises(ValueError):
                    run(directory, datetime(2026, 11, 11, 18, tzinfo=timezone.utc))
            self.assertEqual(json.loads(output.read_text()), {'previous': True})

