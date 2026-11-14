# SPDX-License-Identifier: AGPL-3.0-only
"""Release-level regression tests for v0.7.10 UI and backend routing."""
import json
import contextlib
import io
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from telemetry_store import TelemetryStore


class V0710ReleaseTests(unittest.TestCase):
    def test_single_source_version_constant_and_removed_benchmark(self):
        self.assertEqual(app.APP_VERSION, '0.7.11-rc2')
        web = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')
        script = (Path(__file__).resolve().parents[1] / 'static' / 'v07.js').read_text(encoding='utf-8')
        self.assertIn('{{APP_VERSION}}', web)
        self.assertIn("fetch('/api/version'", web)
        self.assertNotIn('data-tab="benchmark"', web)
        self.assertNotIn('tab-benchmark', web)
        self.assertNotIn('loadBenchmark', script)
        self.assertNotIn('archiveBenchmarkFlight', script)
        self.assertFalse((Path(__file__).resolve().parents[1] / 'benchmark.py').exists())

    def test_port_conflict_reports_existing_process_before_arming(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'files').mkdir()
            (base / 'case.json').write_text(json.dumps(app.DEF), encoding='utf-8')
            existing = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            try:
                out = io.StringIO()
                with patch.object(app, 'DATA', base), patch.object(app, 'FILES', base / 'files'), \
                     patch.object(app, 'STATE_PATH', base / 'case.json'), \
                     patch.object(app, 'CONFIG_PATH', base / 'config.json'), \
                     patch.object(app, 'PORT', existing.server_address[1]), \
                     patch.object(app.HOTKEY, 'start') as start_hotkey, contextlib.redirect_stdout(out):
                    app.main()
                    start_hotkey.assert_not_called()
                self.assertIn('already in use', out.getvalue())
                self.assertIn('/api/version', out.getvalue())
            finally:
                existing.server_close()

    def test_live_http_routes_are_separate_and_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'case.json').write_text(json.dumps(app.DEF), encoding='utf-8')
            (base / 'files').mkdir()
            with patch.object(app, 'DATA', base), patch.object(app, 'FILES', base / 'files'), \
                 patch.object(app, 'STATE_PATH', base / 'case.json'), \
                 patch.object(app, 'CONFIG_PATH', base / 'config.json'), \
                 patch.object(app, 'TELEM_STORE', TelemetryStore(base / 't.csv')):
                server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base_url = 'http://127.0.0.1:' + str(server.server_address[1])
                def get(path):
                    with urllib.request.urlopen(base_url + path, timeout=5) as response:
                        return response.status, response.headers, response.read()
                try:
                    status, headers, body = get('/api/version')
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body)['version'], app.APP_VERSION)
                    self.assertEqual(headers['Cache-Control'], 'no-store')
                    status, headers, html = get('/')
                    self.assertEqual(status, 200)
                    page = html.decode('utf-8')
                    self.assertIn('Version ' + app.APP_VERSION, page)
                    self.assertNotIn('{{APP_VERSION}}', page)
                    self.assertNotIn('Real-World Benchmark', page)
                    self.assertEqual(headers['Cache-Control'], 'no-store')
                    _, _, script = get('/static/v07.js')
                    self.assertIn(b'refreshRouteData', script)
                    for path in ('/api/benchmark', '/api/benchmark-report.pdf'):
                        with self.assertRaises(urllib.error.HTTPError) as response:
                            get(path)
                        self.assertEqual(response.exception.code, 404)
                    with urllib.request.urlopen(base_url + '/api/state', timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn('groups', json.load(response))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
