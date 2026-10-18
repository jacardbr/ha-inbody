"""Tests for the silhouette storage helpers (standard library only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

_path = Path(__file__).resolve().parents[1] / "custom_components" / "ha_inbody" / "silhouette.py"
_spec = importlib.util.spec_from_file_location("ha_inbody_silhouette", _path)
sil = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sil)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"0" * 20
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 20
GIF = b"GIF89a" + b"0" * 20


class SniffTests(unittest.TestCase):
    def test_accepts_raster_formats(self):
        self.assertEqual(sil.sniff_image(PNG), "png")
        self.assertEqual(sil.sniff_image(JPG), "jpg")
        self.assertEqual(sil.sniff_image(WEBP), "webp")
        self.assertEqual(sil.sniff_image(GIF), "gif")

    def test_rejects_svg_html_and_junk(self):
        self.assertIsNone(sil.sniff_image(b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>"))
        self.assertIsNone(sil.sniff_image(b"<html></html>"))
        self.assertIsNone(sil.sniff_image(b""))
        self.assertIsNone(sil.sniff_image(b"RIFF\x00\x00\x00\x00WAVE"))


class NameTests(unittest.TestCase):
    def test_valid_and_invalid_names(self):
        self.assertTrue(sil.is_valid_name("silhouette-0123456789ab.png"))
        for bad in ("../x.png", "silhouette-0123456789ab.svg", "silhouette-xyz.png",
                    "silhouette-0123456789ab.png/../../etc", "other.png", "", "/etc/passwd"):
            self.assertFalse(sil.is_valid_name(bad), bad)


class StoreTests(unittest.TestCase):
    def test_store_keeps_only_the_latest_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = sil.store(root, PNG, "png")
            second = sil.store(root, JPG, "jpg")
            files = sorted(p.name for p in (root / sil.SUBDIR).iterdir())
            self.assertEqual(files, [second])
            self.assertNotEqual(first, second)
            self.assertEqual((root / sil.SUBDIR / second).read_bytes(), JPG)

    def test_store_leaves_unrelated_files_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / sil.SUBDIR).mkdir()
            (root / sil.SUBDIR / "keep.txt").write_text("x")
            sil.store(root, PNG, "png")
            self.assertTrue((root / sil.SUBDIR / "keep.txt").exists())

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = sil.store(root, PNG, "png")
            self.assertTrue(sil.delete(root, name))
            self.assertFalse((root / sil.SUBDIR / name).exists())
            self.assertTrue(sil.delete(root, name))  # idempotent

    def test_delete_refuses_paths_outside_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / "secret.png"
            secret.write_bytes(PNG)
            self.assertFalse(sil.delete(root, "../secret.png"))
            self.assertTrue(secret.exists())


if __name__ == "__main__":
    unittest.main()
