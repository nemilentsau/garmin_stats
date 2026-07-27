"""Tests for Garmin sync filesystem adapter behavior."""

import os
import zipfile
from datetime import date
from pathlib import Path

import pytest

from app.domains.garmin_sync.infra.filesystem import (
    _ARCHIVE_STAMP_NAME,
    FilesystemSyncFileStore,
    _extract_zip,
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

    def test_file_that_vanishes_between_listing_and_stat_is_skipped(
        self, tmp_path, monkeypatch
    ):
        """Extraction replaces whole day directories under the watcher, so a
        listed FIT file can be gone by the time it is stat'd."""
        data_dir = tmp_path / "data"
        day_dir = data_dir / "2026-01-15"
        day_dir.mkdir(parents=True)
        (day_dir / "001_WELLNESS.fit").write_bytes(b"AAAA")
        doomed = day_dir / "002_WELLNESS.fit"
        doomed.write_bytes(b"BBBB")

        real_stat = Path.stat

        def vanishing_stat(self, *args, **kwargs):
            if self.name == "002_WELLNESS.fit":
                raise FileNotFoundError(str(self))
            return real_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", vanishing_stat)
        fp_during_race = compute_data_fingerprint(data_dir)
        monkeypatch.undo()

        doomed.unlink()
        assert fp_during_race == compute_data_fingerprint(data_dir)


class TestSafeExtract:
    def test_reextract_restores_existing_day_when_staged_directory_install_fails(
        self, tmp_path, monkeypatch
    ):
        data_dir = tmp_path / "data"
        old_day = data_dir / "2026-01-15"
        old_day.mkdir(parents=True)
        (old_day / "old.fit").write_text("old", encoding="ascii")
        zip_path = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("new.fit", "new")

        real_rename = Path.rename

        def fail_staged_install(self: Path, target: Path):
            if self.name == ".2026-01-15.tmp" and Path(target) == old_day:
                raise OSError("simulated directory install failure")
            return real_rename(self, target)

        monkeypatch.setattr(Path, "rename", fail_staged_install)

        with pytest.raises(OSError, match="simulated directory install failure"):
            _extract_zip(zip_path)

        assert (old_day / "old.fit").read_text(encoding="ascii") == "old"
        assert not (old_day / "new.fit").exists()
        assert not (data_dir / ".2026-01-15.extract.backup").exists()
        assert not (data_dir / ".2026-01-15.tmp").exists()

    def test_install_archive_replaces_zip_and_extracted_day_only_after_validation(
        self, tmp_path
    ):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        old_zip = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(old_zip, "w") as zf:
            zf.writestr("nested/old.fit", "old")
        extract_existing_archives(data_dir)

        replacement = tmp_path / "replacement.zip"
        with zipfile.ZipFile(replacement, "w") as zf:
            zf.writestr("nested/new.fit", "new")

        FilesystemSyncFileStore().install_archive(
            data_dir,
            date(2026, 1, 15),
            replacement.read_bytes(),
        )

        assert not (data_dir / "2026-01-15" / "nested" / "old.fit").exists()
        assert (data_dir / "2026-01-15" / "nested" / "new.fit").read_text() == "new"
        with zipfile.ZipFile(old_zip) as zf:
            assert zf.namelist() == ["nested/new.fit"]

    def test_install_archive_preserves_existing_day_when_replacement_is_invalid(
        self, tmp_path
    ):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        old_zip = data_dir / "2026-01-15.zip"
        with zipfile.ZipFile(old_zip, "w") as zf:
            zf.writestr("nested/old.fit", "old")
        extract_existing_archives(data_dir)
        old_bytes = old_zip.read_bytes()

        with pytest.raises(zipfile.BadZipFile):
            FilesystemSyncFileStore().install_archive(
                data_dir,
                date(2026, 1, 15),
                b"not-a-zip",
            )

        assert old_zip.read_bytes() == old_bytes
        assert (data_dir / "2026-01-15" / "nested" / "old.fit").read_text() == "old"

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

        assert extracted == ["2026-01-15"]
        assert (data_dir / "2026-01-15" / "nested" / "file.fit").exists()
        assert (data_dir / "2026-01-15" / _ARCHIVE_STAMP_NAME).exists()

        extracted_again = extract_existing_archives(data_dir)

        assert extracted_again == []

    def test_extract_existing_archives_omits_dates_it_could_not_extract(self, tmp_path):
        """A corrupt archive must not be reported as extracted; sync would then
        stamp a whole-tree fingerprint over a date it never re-ingested."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "2026-01-15.zip").write_bytes(b"not-a-zip")
        good_zip = data_dir / "2026-01-16.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr("nested/file.fit", "ok")

        extracted = extract_existing_archives(data_dir)

        assert extracted == ["2026-01-16"]

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

        assert extracted == []
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

        assert extracted == ["2026-01-15"]
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

        assert extracted == ["2026-01-15"]
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
