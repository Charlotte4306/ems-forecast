"""Vehicle busy-time preparation: exclusions, overlap union, and historical cutoff."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from ems.capacity.prepare_busy_time import audit_records, hourly_workload, prepare, union_intervals


def record(call, unit, dispatch, available, received=None, source_record=1, unit_type="MEDIC"):
    return {"call_number": str(call), "incident_number": str(call), "unit_id": unit,
            "unit_type": unit_type, "received_dttm": received or dispatch,
            "dispatch_dttm": dispatch, "available_dttm": available,
            "source_file": "fixture.csv", "source_record": source_record}


class BusyTimeTests(unittest.TestCase):
    def test_same_call_two_units_are_two_assignments_and_overlaps_are_unioned(self):
        raw = pd.DataFrame([
            record(1, "A", "2025-01-01T08:40:00", "2025-01-01T10:10:00"),
            record(1, "B", "2025-01-01T09:00:00", "2025-01-01T09:30:00", source_record=2),
            record(2, "A", "2025-01-01T09:50:00", "2025-01-01T10:30:00", source_record=3),
        ])
        records = audit_records(raw)
        self.assertEqual(records.usable_busy_interval.sum(), 3)
        self.assertEqual(records.call_number.nunique(), 2)
        intervals, overlaps = union_intervals(records)
        self.assertEqual(len(intervals), 2)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps.overlap_minutes.iloc[0], 20)
        hourly = hourly_workload(records, intervals).set_index("hour")
        np.testing.assert_allclose(hourly.observed_busy_vehicle_hours, [1 / 3, 1.5, 0.5])
        self.assertEqual(hourly.peak_simultaneously_busy_units.max(), 2)
        self.assertAlmostEqual(hourly.observed_busy_vehicle_hours.sum(), 140 / 60)

    def test_invalid_duration_flags_and_long_interval_policy(self):
        raw = pd.DataFrame([
            record(1, "A", "2025-01-01T08:00:00", ""),
            record(2, "A", "2025-01-01T08:00:00", "2025-01-01T07:00:00"),
            record(3, "A", "2025-01-01T08:00:00", "2025-01-01T08:00:00"),
            record(4, "A", "2025-01-01T08:00:00", "2025-01-03T08:00:00"),
            record(5, "B", "bad", "2025-01-01T09:00:00"),
            record(6, "C", "2025-01-01T08:00:00", "2025-01-01T09:00:00",
                   received="2025-01-01T08:05:00"),
            record(7, "ENGINE1", "2025-01-01T08:00:00", "2025-01-01T09:00:00", unit_type="ENGINE"),
        ])
        result = audit_records(raw)
        self.assertEqual(len(result), 6)
        for col in ("missing_available_dttm", "negative_busy_time", "zero_busy_time", "long_busy_time",
                    "invalid_dispatch_dttm", "negative_dispatch_delay"):
            self.assertEqual(result[col].sum(), 1, col)
        self.assertEqual(result.usable_busy_interval.sum(), 2)
        self.assertEqual(result.eligible_busy_calibration.sum(), 1)
        self.assertEqual(result.busy_minutes.iloc[1], -60)

    def test_exact_repeats_and_conflicting_versions_do_not_double_count(self):
        first = record(1, "A", "2025-01-01T08:00:00", "2025-01-01T09:00:00")
        duplicate = {**first, "source_record": 2}
        result = audit_records(pd.DataFrame([first, duplicate]))
        self.assertEqual(result.duplicate_record.sum(), 1)
        self.assertEqual(result.conflicting_assignment_key.sum(), 0)
        self.assertEqual(result.usable_busy_interval.sum(), 1)
        conflict = {**first, "available_dttm": "2025-01-01T10:00:00"}
        result = audit_records(pd.DataFrame([first, conflict]))
        self.assertEqual(result.conflicting_assignment_key.sum(), 2)
        self.assertEqual(result.usable_busy_interval.sum(), 0)

    def test_interval_end_is_exclusive_at_same_time_as_another_start(self):
        records = audit_records(pd.DataFrame([
            record(1, "A", "2025-01-01T08:00:00", "2025-01-01T09:00:00"),
            record(2, "B", "2025-01-01T09:00:00", "2025-01-01T10:00:00"),
        ]))
        intervals, _ = union_intervals(records)
        result = hourly_workload(records, intervals)
        self.assertEqual(result.peak_simultaneously_busy_units.max(), 1)
        self.assertEqual(result.observed_busy_vehicle_hours.sum(), 2)

    def test_calibration_uses_only_durations_known_by_historical_cutoff(self):
        raw = pd.DataFrame([
            record(1, "A", "2025-06-01T08:00:00", "2025-06-01T09:00:00"),
            record(2, "B", "2025-12-31T23:30:00", "2026-01-01T00:30:00"),
            record(3, "C", "2026-01-02T08:00:00", "2026-01-02T10:00:00"),
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.csv"
            raw.to_csv(source, index=False)
            source_before = source.read_bytes()
            result = prepare([source], root / "output")
            self.assertEqual(result["calibration"]["busy_time"]["count"], 1)
            self.assertEqual(result["calibration"]["busy_time"]["mean_minutes"], 60)
            self.assertFalse(result["calibration"]["on_duty_roster_available"])
            self.assertEqual(source.read_bytes(), source_before)
            saved = pd.read_csv(root / "output/medic_busy_records.csv")
            self.assertEqual(saved.in_busy_calibration.tolist(), [True, False, False])


if __name__ == "__main__":
    unittest.main()
