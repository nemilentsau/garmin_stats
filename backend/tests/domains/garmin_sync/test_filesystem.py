"""Tests for Garmin sync filesystem adapter behavior."""

import os
import zipfile

import pytest

from app.domains.garmin_sync.filesystem import (
    _ARCHIVE_STAMP_NAME,
    _safe_extract_all,
    compute_data_fingerprint,
    ensure_data_dir,
    extract_existing_archives,
)


class TestFingerprint:
    def test_detects_file_content_change(self, tmp_path):
        data_dir = tmp_path / "data"
        day_dir = data_dir / "2026-01-15"
        day_dir.mkdir(parents=True)
        fit_file = day_dir / "001_WELLNESS.fit"
        fit_file.write_bytes(b"AAAA")
        fp1 = compute_data_fingerprint(data_dir)

        fit_file.write_bytes(b"BBBB")
        stat = fit_file.stat()
        os.utime(fit_file, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 1))
        fp2 = compute_data_fingerprint(data_dir)

        assert fp1 != fp2

    def test_returns_stable_hash_for_nonexistent_dir(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        fp = compute_data_fingerprint(missing)
        assert isinstance(fp, str)
        assert len(fp) == 64


class TestSafeExtract:
    def test_creates_missing_data_directory_before_watching(self, tmp_path):
        data_dir = tmp_path / "missing-data"

        ensure_data_dir(data_dir)

        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_extracts_valid_archive(self, tmp_path):
        zip_path = tmp_path / "valid.zip"
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "ok")

        with zipfile.ZipFile(zip_path, "r") as zf:
            _safe_extract_all(zf, out_dir)

        assert (out_dir / "nested" / "file.fit").exists()

    def test_extract_existing_archives_reads_top_level_day_archives(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        zip_path = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "ok")

        extracted = extract_existing_archives(data_dir)

        assert extracted == 1
        assert (data_dir / "2026-01-15" / "nested" / "file.fit").exists()
        assert (data_dir / "2026-01-15" / _ARCHIVE_STAMP_NAME).exists()

        extracted_again = extract_existing_archives(data_dir)

        assert extracted_again == 0

    def test_existing_matching_output_bootstraps_archive_stamp_without_reextracting(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        zip_path = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "ok")

        out_dir = data_dir / "2026-01-15" / "nested"
        out_dir.mkdir(parents=True)
        (out_dir / "file.fit").write_text("ok", encoding="ascii")

        extracted = extract_existing_archives(data_dir)

        assert extracted == 0
        assert (data_dir / "2026-01-15" / _ARCHIVE_STAMP_NAME).exists()

    def test_changed_archive_reextracts_when_existing_output_does_not_match(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        zip_path = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "updated")

        out_dir = data_dir / "2026-01-15" / "nested"
        out_dir.mkdir(parents=True)
        (out_dir / "old.fit").write_text("stale", encoding="ascii")

        extracted = extract_existing_archives(data_dir)

        assert extracted == 1
        assert (
            data_dir / "2026-01-15" / "nested" / "file.fit"
        ).read_text(encoding="ascii") == "updated"
        assert not (data_dir / "2026-01-15" / "nested" / "old.fit").exists()

    def test_changed_archive_reextracts_when_legacy_output_has_same_file_sizes(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        zip_path = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nested/file.fit", "BBBBBBBBBB")

        out_dir = data_dir / "2026-01-15" / "nested"
        out_dir.mkdir(parents=True)
        (out_dir / "file.fit").write_text("AAAAAAAAAA", encoding="ascii")

        extracted = extract_existing_archives(data_dir)

        assert extracted == 1
        assert (
            data_dir / "2026-01-15" / "nested" / "file.fit"
        ).read_text(encoding="ascii") == "BBBBBBBBBB"
        assert (data_dir / "2026-01-15" / _ARCHIVE_STAMP_NAME).exists()

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
