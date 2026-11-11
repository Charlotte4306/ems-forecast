"""Bootstrap a current web snapshot without legacy weights or a prior export."""
import json
from pathlib import Path
import tempfile
import unittest

from ems.web.prepare_dashboard import prepare
from ems.web.server import read_dataset


class WebPreparationTests(unittest.TestCase):
    def test_bootstrap_from_committed_forecasts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/dataset.json"
            prepare(path)
            data = json.loads(read_dataset(path))
        self.assertEqual(data["metadata"]["target"], "medic-dispatches")
        self.assertEqual(data["metadata"]["timeField"], "received_dttm")
        self.assertEqual(len(data["profiles"]["prophet_h1"]["rows"]), 6796)
        self.assertNotIn("rows", data)
