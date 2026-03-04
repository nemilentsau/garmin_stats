"""Tests for watcher zip extraction safety."""

import zipfile

import pytest

from app.infra.watcher import _safe_extract_all


class TestSafeExtract:
    def test_extracts_valid_archive(self, tmp_path):
        zip_path = tmp_path / "valid.zip"
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "ok")

        with zipfile.ZipFile(zip_path, "r") as zf:
            _safe_extract_all(zf, out_dir)

        assert (out_dir / "nested" / "file.fit").exists()

    def test_rejects_path_traversal_archive(self, tmp_path):
        zip_path = tmp_path / "bad.zip"
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../escape.fit", "bad")

        with zipfile.ZipFile(zip_path, "r") as zf, pytest.raises(
            ValueError, match="Unsafe path",
        ):
            _safe_extract_all(zf, out_dir)
