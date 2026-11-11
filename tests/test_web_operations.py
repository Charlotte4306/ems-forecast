import unittest

from ems.web.prepare_operations import capacity_rows


class CapacityWebExportTests(unittest.TestCase):
    def test_misaligned_capacity_is_rejected(self):
        raw = 'timestamp,actual_dispatches\n2026-01-01 01:00:00,12\n'
        with self.assertRaisesRegex(ValueError, 'timestamps/actuals'):
            capacity_rows(raw, [('2026-01-01T00:00:00', 12)])

    def test_missing_observations_are_rejected(self):
        with self.assertRaises(ValueError):
            capacity_rows('timestamp,actual_dispatches\n', [('2026-01-01T00:00:00', 12)])
