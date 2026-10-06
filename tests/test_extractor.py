import hashlib
import http.client
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/sketchfab'))
import extract_public_model as cli
import serve_public_extractor as server
from asset_io import AssetError, copy_bounded, run_process
from test_reliability import glb_bytes


class IOTests(unittest.TestCase):
    def test_transfer_limits_and_truncation(self):
        for body, expected, limit in [(b'abc', 4, 10), (b'abcdef', None, 5), (b'', 0, 5)]:
            with self.subTest(body=body), self.assertRaises(AssetError):
                copy_bounded(io.BytesIO(body), io.BytesIO(), expected=expected, limit=limit)

    def test_process_deadline(self):
        start = time.monotonic()
        with self.assertRaisesRegex(AssetError, 'TIMEOUT'):
            run_process([sys.executable, '-c', 'import time;time.sleep(30)'], .15)
        self.assertLess(time.monotonic() - start, 5)

    def test_unknown_license_and_reused_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'model.glb'
            output.write_bytes(glb_bytes())
            attr = cli.attribution_for('a' * 32, output, metadata={'name': 'Example'})
            self.assertEqual(attr['license'], 'unknown')
            self.assertEqual(attr['name'], 'Example')

    def test_proxy_checks_credentials_ports_and_hosts(self):
        for url in ['https://evil.test/x', 'https://user:pass@sketchfab.com/x', 'https://sketchfab.com:8443/x', 'http://sketchfab.com/x']:
            with self.subTest(url=url), self.assertRaises(AssetError):
                server.validate_target(url)


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / 'model.glb'
        self.server = server.ExtractionServer('a' * 32, self.output, timeout=10)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def post(self, path, body, authenticated=True, **headers):
        if authenticated:
            headers['X-Extractor-Token'] = self.server.token
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request('POST', path, body=body, headers=headers)
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def test_rejects_unauthenticated_and_foreign_origin(self):
        self.assertEqual(self.post('/save', glb_bytes(), False), 403)
        self.assertEqual(self.post('/save', glb_bytes(), Origin='https://evil.test'), 403)
        self.assertFalse(self.output.exists())

    def test_bounded_metadata_and_invalid_container(self):
        self.assertEqual(self.post('/metadata', b'x' * ((1 << 20) + 1)), 413)
        self.assertEqual(self.post('/save', b'glTFbroken'), 422)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(Path(self.tmp.name).glob('*.part')))

    def test_raw_glb_atomic_save_with_diagnostics(self):
        metadata = {'metadata': {'name': 'Example'}, 'diagnostics': {'skipped_geometries': [{'name': 'bad'}]}, 'warnings': ['SKIPPED_GEOMETRIES']}
        self.assertEqual(self.post('/metadata', json.dumps(metadata)), 204)
        body = glb_bytes()
        self.assertEqual(self.post('/save', body), 204)
        self.assertEqual(self.output.read_bytes(), body)
        self.assertEqual(self.server.result['sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(self.server.result['warnings'], ['SKIPPED_GEOMETRIES'])
        attr = json.loads(self.output.with_suffix('.glb.attribution.json').read_text())
        self.assertEqual(attr['license'], 'unknown')
        self.assertEqual(self.post('/save', body), 409)

    def test_ephemeral_ports_do_not_conflict(self):
        other = server.ExtractionServer('b' * 32, Path(self.tmp.name) / 'b.glb', timeout=10)
        try:
            self.assertNotEqual(self.server.server_port, other.server_port)
        finally:
            other.server_close()
