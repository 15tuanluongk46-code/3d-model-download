import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'download.py'
spec = importlib.util.spec_from_file_location('assets', SCRIPT)
assets = importlib.util.module_from_spec(spec)
if SCRIPT.exists():
    spec.loader.exec_module(assets)

ID = 'b8893ec3-93b8-4f6c-9c3b-810337d2587a'


class AssetsTest(unittest.TestCase):
    def test_link_recognition_and_reject_ambiguous_workspace(self):
        self.assertTrue(hasattr(assets, 'parse_link'), 'URL parser not implemented')
        self.assertEqual(assets.parse_link(f'https://hyper3d.ai/workspace/rodin/{ID}'), ('rodin', ID))
        self.assertEqual(assets.parse_link(f'https://www.meshy.ai/3d-models/cat-{ID}?x=1'), ('meshy', ID))
        self.assertEqual(assets.parse_link(f'https://www.meshy.ai/workspace?taskId={ID}'), ('meshy', ID))
        for url in ['https://www.meshy.ai/workspace?sidebar=assets', f'https://meshy.ai.evil.test/{ID}', f'https://evil.test/?link=https://meshy.ai/{ID}']:
            with self.assertRaises(assets.AssetError):
                assets.parse_link(url)

    def test_asset_envelope_prefers_textured_output(self):
        self.assertTrue(hasattr(assets, 'meshy_asset'), 'Resolver not implemented')
        task = {'status': 'SUCCEEDED', 'result': {'texture': {'modelUrl': 'https://assets.meshy.ai/a.meshy'}, 'generate': {'modelUrl': 'https://assets.meshy.ai/b.meshy'}}}
        self.assertEqual(assets.meshy_asset({'code': 'OK', 'result': task})[0], 'https://assets.meshy.ai/a.meshy')
        with self.assertRaises(assets.AssetError):
            assets.meshy_asset({'code': 'NotFound', 'result': 'Task not found'})

    def test_rejects_untrusted_download_targets(self):
        self.assertTrue(hasattr(assets, 'check_asset_url'), 'URL policy not implemented')
        for url in ['http://assets.meshy.ai/a', 'https://127.0.0.1/a', 'https://assets.meshy.ai.evil.test/a', 'https://user:pass@assets.meshy.ai/a']:
            with self.assertRaises(assets.AssetError):
                assets.check_asset_url(url)
        assets.check_asset_url('https://file.hyper3d.com/a/model.drc?signature=x')

    def test_glb_rejects_truncated_or_fake_files(self):
        self.assertTrue(hasattr(assets, 'validate_glb'), 'GLB validator not implemented')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'model.glb'
            p.write_bytes(b'<html>login</html>')
            with self.assertRaises(assets.AssetError):
                assets.validate_glb(p)
            doc = json.dumps({'asset': {'version': '2.0'}, 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}], 'accessors': [{'count': 3, 'type': 'VEC3', 'componentType': 5126}]}).encode()
            doc += b' ' * (-len(doc) % 4)
            content = struct.pack('<4sII', b'glTF', 2, 20 + len(doc)) + struct.pack('<I4s', len(doc), b'JSON') + doc
            p.write_bytes(content)
            self.assertEqual(assets.validate_glb(p)['meshes'], 1)
            p.write_bytes(content[:-1])
            with self.assertRaises(assets.AssetError):
                assets.validate_glb(p)

    def test_output_collision_does_not_overwrite(self):
        self.assertTrue(hasattr(assets, 'new_output_dir'), 'Output allocation not implemented')
        with tempfile.TemporaryDirectory() as d:
            a = assets.new_output_dir(Path(d), 'meshy', ID)
            (a / 'keep.txt').write_text('original')
            b = assets.new_output_dir(Path(d), 'meshy', ID)
            self.assertNotEqual(a, b)
            self.assertEqual((a / 'keep.txt').read_text(), 'original')


class SessionTest(unittest.IsolatedAsyncioTestCase):
    async def test_private_meshy_falls_back_after_public_404(self):
        class Page:
            async def evaluate(self, code, params):
                if '/public/' in params['url']:
                    return {'status': 404, 'data': {'code': 'NotFound', 'result': 'Task not found'}}
                return {'status': 200, 'data': {'code': 'OK', 'result': {
                    'status': 'SUCCEEDED', 'result': {'generate': {
                        'modelUrl': 'https://assets.meshy.ai/model.meshy'}}}}}
        session = assets.Session(None, 'meshy')
        session.page = Page()
        session.auth = {'authorization': 'Bearer test-only'}
        url, kind, _meta = await session.resolve(ID)
        self.assertEqual(url, 'https://assets.meshy.ai/model.meshy')
        self.assertEqual(kind, 'meshy')


if __name__ == '__main__':
    unittest.main()
