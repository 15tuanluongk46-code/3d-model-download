import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download.py"
spec = importlib.util.spec_from_file_location("assets", SCRIPT)
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "poly_page.html"


class ClassifyTests(unittest.TestCase):
    def test_meshy_page(self):
        url = "https://www.meshy.ai/3d-models/Stag-v2-019ca926-5c23-7ebd-840b-3849dab0dcbb"
        self.assertEqual(assets.classify(url)[0], "meshy")

    def test_meshy_root_host(self):
        self.assertEqual(assets.classify("https://meshy.ai/3d-models/x")[0], "meshy")

    def test_rodin_host(self):
        self.assertEqual(assets.classify("https://hyper3d.ai/workspace/rodin/abc")[0], "meshy")

    def test_poly_page(self):
        self.assertEqual(assets.classify("https://poly.pizza/m/nIItLV9nxS")[0], "poly")

    def test_poly_static(self):
        url = "https://static.poly.pizza/b9f5d6a2-8c3e-4a7b-9d1f-2e6a4c8b0d3f.glb"
        self.assertEqual(assets.classify(url)[0], "poly-static")

    def test_direct_glb(self):
        self.assertEqual(assets.classify("https://example.com/a/model.glb")[0], "direct")

    def test_reject_http(self):
        with self.assertRaises(assets.AssetError):
            assets.classify("http://poly.pizza/m/x")

    def test_reject_credentials(self):
        with self.assertRaises(assets.AssetError):
            assets.classify("https://user:pass@poly.pizza/m/x")

    def test_reject_unknown_host(self):
        with self.assertRaises(assets.AssetError):
            assets.classify("https://cults3d.com/en/3d-model/foo")

    def test_reject_lookalike_host(self):
        with self.assertRaises(assets.AssetError):
            assets.classify("https://poly.pizza.evil.test/m/x")

    def test_reject_unknown_extension(self):
        with self.assertRaises(assets.AssetError):
            assets.classify("https://example.com/page.html")

    def test_sketchfab_page(self):
        url = "https://sketchfab.com/3d-models/blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4"
        self.assertEqual(assets.classify(url)[0], "sketchfab")

    def test_sketchfab_www_host(self):
        url = "https://www.sketchfab.com/3d-models/x-c75ab6b43e1e49da952361ee6b36f0a4"
        self.assertEqual(assets.classify(url)[0], "sketchfab")

    def test_sketchfab_embed(self):
        url = "https://sketchfab.com/models/c75ab6b43e1e49da952361ee6b36f0a4/embed"
        self.assertEqual(assets.classify(url)[0], "sketchfab")


class SketchfabParseTests(unittest.TestCase):
    URL = "https://sketchfab.com/3d-models/blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4"

    def test_uid_regex(self):
        self.assertEqual(
            assets.SKETCHFAB_UID_RE.search(self.URL).group(0),
            "c75ab6b43e1e49da952361ee6b36f0a4",
        )

    def test_slug_regex(self):
        self.assertEqual(
            assets.SKETCHFAB_SLUG_RE.search(self.URL).group(1),
            "blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4",
        )


class PolyParseTests(unittest.TestCase):
    def test_parse_fixture(self):
        info = assets.parse_poly_page(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(info["resource_id"], "b9f5d6a2-8c3e-4a7b-9d1f-2e6a4c8b0d3f")
        self.assertEqual(info["name"], "Hoodie Character")
        self.assertEqual(info["likes"], 35)
        self.assertEqual(info["downloads"], "2.4k")
        self.assertEqual(info["views"], "9.1k")
        self.assertEqual(info["creator"], "Quaternius")
        self.assertEqual(info["license"], "CC0")


class OutputDirTests(unittest.TestCase):
    def test_numbering(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = assets.new_output_dir(tmp, "poly-pizza", "slug")
            second = assets.new_output_dir(tmp, "poly-pizza", "slug")
            self.assertEqual(first.name, "slug")
            self.assertEqual(second.name, "slug-1")
            self.assertTrue(first.is_dir() and second.is_dir())

    def test_sanitize_direct_name(self):
        import re

        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", "my model (final).glb")
        self.assertEqual(stem, "my_model_final_.glb")


if __name__ == "__main__":
    unittest.main()
