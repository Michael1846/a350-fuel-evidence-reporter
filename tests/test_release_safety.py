# SPDX-License-Identifier: AGPL-3.0-only
"""User data isolation and browser request boundaries for the release candidate."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import app
from runtime_paths import data_directory


class ReleaseSafetyTests(unittest.TestCase):
    def test_upgrade_folder_does_not_change_data_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'A350_REPORTER_DATA_DIR':folder}):
                first = data_directory()
                (first / 'case.json').write_text('{"preserve":true}')
                with patch.object(app, 'BASE', Path(folder) / 'new-version'):
                    self.assertEqual(data_directory(), first)
                self.assertTrue(json.loads((first / 'case.json').read_text())['preserve'])

    def test_browser_boundaries_and_installation_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(app,'DATA',root), patch.object(app,'FILES',root/'files'), \
                 patch.object(app,'STATE_PATH',root/'case.json'), \
                 patch.object(app,'CONFIG_PATH',root/'config.json'):
                app.ensure()
                original = json.loads((root/'config.json').read_text())['token']
                app.ensure()
                self.assertEqual(json.loads((root/'config.json').read_text())['token'], original)
                self.assertGreaterEqual(len(original), 32)
                second = root/'second.json'
                with patch.object(app,'CONFIG_PATH',second):
                    app.ensure()
                    self.assertNotEqual(json.loads(second.read_text())['token'], original)
                server = app.ReporterHTTPServer(('127.0.0.1',0),app.Handler)
                worker = threading.Thread(target=server.serve_forever,daemon=True)
                worker.start()
                url = f'http://127.0.0.1:{server.server_address[1]}'
                def check(path, headers, code, data=None):
                    request = urllib.request.Request(url+path, data=data, headers=headers)
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request,timeout=3)
                    self.assertEqual(caught.exception.code, code)
                try:
                    check('/api/config', {'Host':'attacker.example'}, 403)
                    check('/api/state', {'Origin':'https://attacker.example'}, 403)
                    check('/api/state', {'Sec-Fetch-Site':'cross-site'}, 403)
                    check('/api/snapshot', {'Content-Type':'text/plain'}, 415, b'{}')
                    check('/api/snapshot', {'Content-Type':'application/json','Origin':'null'}, 403, b'{}')
                    check('/api/waypoint', {'Content-Type':'application/json','X-Reporter-Token':'wrong'}, 403, b'{}')
                    for path in ('/api/version','/legal/license','/legal/notices','/legal/source-info'):
                        with urllib.request.urlopen(url+path,timeout=3) as response:
                            self.assertEqual(response.status,200)
                    with patch.object(app,'BASE',root):
                        check('/legal/corresponding-source.zip',{},404)
                        payload=b'PK\x03\x04'+b'synthetic source archive'*100000
                        (root/'CORRESPONDING_SOURCE.zip').write_bytes(payload)
                        with urllib.request.urlopen(url+'/legal/corresponding-source.zip',timeout=3) as response:
                            self.assertEqual(response.read(),payload)
                            self.assertEqual(int(response.headers['Content-Length']),len(payload))
                    request = urllib.request.Request(url+'/api/meta',data=b'{"notes":"local test"}',
                        headers={'Content-Type':'application/json','Origin':url})
                    with urllib.request.urlopen(request,timeout=3) as response:
                        self.assertEqual(response.status,200)
                finally:
                    server.shutdown(); server.server_close(); worker.join(timeout=3)


if __name__ == '__main__': unittest.main()
