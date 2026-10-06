import contextlib
import io
import json
import struct
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import download as d


def glb_bytes(document=None):
    doc = document or {'asset': {'version': '2.0'}, 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}]}
    data = json.dumps(doc).encode()
    data += b' ' * (-len(data) % 4)
    return struct.pack('<III', 0x46546C67, 2, len(data) + 20) + struct.pack('<II', len(data), 0x4E4F534A) + data


class ReliabilityTests(unittest.TestCase):
    def test_poly_metadata_fetch_respects_requested_timeout(self):
        with patch.object(d, 'http_get', side_effect=d.AssetError('TIMEOUT')) as fetch:
            with self.assertRaises(d.AssetError):
                d.handle_poly('https://poly.pizza/m/demo', SimpleNamespace(timeout=0.25))
        self.assertEqual(fetch.call_args.kwargs.get('timeout'), 0.25)

    def test_meshy_delegate_normalizes_verified_file_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / 'model.glb'
            model.write_bytes(glb_bytes())
            record = {'ok': True, 'provider': 'meshy', 'file': str(model), 'source_url': 'https://example.com/model?token=hidden'}
            proc = SimpleNamespace(returncode=0, stdout=json.dumps(record))
            out = io.StringIO()
            with patch.object(d, 'run_process', return_value=proc), contextlib.redirect_stdout(out):
                d.run_meshy('https://meshy.ai/3d-models/demo', SimpleNamespace(output=Path(tmp), cdp='http://127.0.0.1:9222', timeout=5))
            result = json.loads(out.getvalue())
            self.assertEqual(result['file_path'], str(model))
            self.assertEqual(result['bytes'], model.stat().st_size)
            self.assertEqual(json.loads(Path(result['metadata_path']).read_text()), result)
            self.assertNotIn('hidden', out.getvalue())

    def test_direct_cli_returns_one_result_and_persisted_absolute_paths(self):
        def transfer(url, dest, **kwargs):
            Path(dest).write_bytes(glb_bytes())
            return len(glb_bytes())
        with tempfile.TemporaryDirectory() as tmp, patch.object(d, 'download_file', transfer):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = d.main(['https://example.com/test.glb?token=secret', '--output', tmp])
            self.assertEqual(rc, 0)
            lines = out.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            result = json.loads(lines[0])
            self.assertTrue(Path(result['file_path']).is_absolute())
            self.assertTrue(Path(result['file_path']).is_file())
            self.assertEqual(json.loads(Path(result['metadata_path']).read_text()), result)
            self.assertNotIn('secret', out.getvalue())

    def test_invalid_glb_is_failure_not_warning(self):
        def transfer(url, dest, **kwargs):
            Path(dest).write_bytes(b'glTF' + b'bad' * 10)
            return 34
        with tempfile.TemporaryDirectory() as tmp, patch.object(d, 'download_file', transfer):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = d.main(['https://example.com/bad.glb', '--output', tmp])
            self.assertEqual(rc, 1)
            result = json.loads(out.getvalue())
            self.assertFalse(result['ok'])
            self.assertIn('INVALID_GLB', result['error'])
            self.assertFalse([p for p in Path(tmp).rglob('*.glb') if p.is_file()])

    def test_error_redacts_userinfo_query_and_fragment(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            d.main(['https://user:password@example.com/a.glb?key=private#secret'])
        for secret in ('password', 'private', 'secret'):
            self.assertNotIn(secret, out.getvalue())

    def test_concurrent_output_directories_are_unique(self):
        with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=12) as pool:
            dirs = list(pool.map(lambda _: d.new_output_dir(tmp, 'direct', 'same'), range(30)))
            self.assertEqual(len(set(dirs)), 30)

    def test_gltf_external_dependencies_are_reported(self):
        doc = {'asset': {'version': '2.0'}, 'buffers': [{'uri': 'model.bin'}], 'images': [{'uri': 'tex.png'}]}
        def transfer(url, dest, **kwargs):
            Path(dest).write_text(json.dumps(doc))
            return Path(dest).stat().st_size
        with tempfile.TemporaryDirectory() as tmp, patch.object(d, 'download_file', transfer):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                d.main(['https://example.com/model.gltf', '--output', tmp])
            result = json.loads(out.getvalue())
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['external_dependencies'], ['model.bin', 'tex.png'])


if __name__ == '__main__':
    unittest.main()
