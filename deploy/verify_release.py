"""Verify an uploaded standalone release using only Python stdlib."""
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ems.web.server import Handler


def verify():
    manifest = json.loads((ROOT / 'release-manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('File hash differs: ' + name)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(
        Handler, web_root=ROOT / 'web', dataset=ROOT / 'outputs/web/dataset.json'))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with urlopen(base + '/api/dataset') as response:
            data = json.load(response)
        assert len(data['profiles']['prophet_h1']['rows']) == 6796
        assert len(data['profiles']['prophet_h24']['rows']) == 6796
        for asset in ('index.html', 'styles.css', 'template-bindings.css', 'app.mjs',
                      'template-runtime.mjs', 'dashboard.mjs', 'analysis.mjs', 'assets/fonts.css',
                      'assets/ibm-plex-sans-400.ttf', 'assets/ibm-plex-sans-500.ttf',
                      'assets/ibm-plex-sans-600.ttf', 'zenless.css', 'zenless.mjs',
                      'routes.mjs', 'live.mjs', 'operations.css', 'operations.mjs',
                      'assets/zenless-tt-hoves-pro-compact-bold.woff2',
                      'assets/zenless-impact.ttf'):
            with urlopen(base + '/' + asset) as response:
                assert response.read() == (ROOT / 'web' / asset).read_bytes(), asset
                if asset.endswith('.ttf'):
                    assert response.headers['Content-Type'] == 'font/ttf'
        for route in ('overview', 'forecast', 'fleet-plan', 'scenario-costs',
                      'model-evaluation', 'history', 'settings', 'daily-forecast'):
            with urlopen(base + '/' + route) as response:
                assert response.read() == (ROOT / 'web/index.html').read_bytes(), route
        with urlopen(base + '/health') as response:
            assert json.load(response)['status'] == 'ok'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print('Verified release:', manifest['release'], 'forecast profiles, screen routes, assets and fonts')


if __name__ == '__main__':
    verify()
