"""The demo server needs only Python stdlib and exposes no repository sources."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ems.web.server import Handler, read_dataset


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "web").mkdir()
        (self.root / "web/index.html").write_text("<h1>EMS</h1>", encoding="utf-8")
        (self.root / "secret.txt").write_text("private", encoding="utf-8")
        self.dataset = self.root / "dataset.json"
        self.dataset.write_text(json.dumps({"schemaVersion": 1, "rows": [{"actual": 1}]}), encoding="utf-8")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, web_root=self.root / "web", dataset=self.dataset))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_api_and_health_and_head(self):
        with urlopen(self.base + "/api/dataset") as response:
            self.assertEqual(json.load(response)["schemaVersion"], 1)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        with urlopen(self.base + "/health") as response:
            self.assertEqual(response.status, 200)
        with urlopen(Request(self.base + "/", method="HEAD")) as response:
            self.assertEqual(response.read(), b"")
            self.assertGreater(int(response.headers["Content-Length"]), 0)

    def test_no_source_or_traversal_access(self):
        for route in ("/../secret.txt", "/%2e%2e/secret.txt", "/ems/models/lstm/train.py"):
            with self.assertRaises(HTTPError) as result:
                urlopen(self.base + route)
            self.assertEqual(result.exception.code, 404)
            result.exception.close()

    def test_missing_dataset_has_actionable_error(self):
        self.dataset.unlink()
        with self.assertRaises(HTTPError) as result:
            urlopen(self.base + "/api/dataset")
        self.assertEqual(result.exception.code, 503)
        self.assertIn(b"ems.web.export", result.exception.read())
        result.exception.close()
        with self.assertRaises(HTTPError) as health:
            urlopen(self.base + "/health")
        self.assertEqual(health.exception.code, 503)
        health.exception.close()

    def test_invalid_dataset_is_rejected(self):
        self.dataset.write_text('{"schemaVersion":9,"rows":[]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_dataset(self.dataset)


if __name__ == "__main__":
    unittest.main()
