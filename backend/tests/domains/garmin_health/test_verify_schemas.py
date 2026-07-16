"""Tests for the real-data Garmin schema verification utility."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def verifier() -> ModuleType:
    project_root = Path(__file__).resolve().parents[4]
    script_path = (
        project_root
        / ".claude"
        / "skills"
        / "garmin-data"
        / "scripts"
        / "verify_schemas.py"
    )
    spec = spec_from_file_location("test_verify_schemas_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_files_include_all_chunks_from_spread_representative_days(
    verifier: ModuleType,
) -> None:
    files_by_day = {
        f"2026-01-0{day}": {
            "WELLNESS": [
                Path(f"day-{day}-first.fit"),
                Path(f"day-{day}-second.fit"),
            ]
        }
        for day in range(1, 6)
    }

    sample_files = verifier.get_sample_files(
        files_by_day, "WELLNESS", sample_day_count=3
    )

    assert sample_files == [
        Path("day-1-first.fit"),
        Path("day-1-second.fit"),
        Path("day-3-first.fit"),
        Path("day-3-second.fit"),
        Path("day-5-first.fit"),
        Path("day-5-second.fit"),
    ]


def test_verifier_aggregates_all_files_within_a_sampled_day(
    verifier: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_file = Path("first.fit")
    second_file = Path("second.fit")
    schema = {
        "monitoring_mesgs": {
            "fields": {"steps": {"type": "int", "nullable": False}}
        }
    }
    decoded = {
        first_file: {"monitoring_mesgs": [{}]},
        second_file: {"monitoring_mesgs": [{"steps": 123}]},
    }
    monkeypatch.setattr(verifier, "load_schema", lambda _file: schema)
    monkeypatch.setattr(verifier, "decode_fit_file", decoded.__getitem__)

    findings = verifier.verify_file_type(
        "WELLNESS",
        {"file": "unused.json", "messages": ["monitoring_mesgs"]},
        {"2026-01-01": {"WELLNESS": [first_file, second_file]}},
    )

    assert not [finding for finding in findings if finding["level"] == "DRIFT"]
    assert any(finding["detail"] == "Field 'steps' verified" for finding in findings)


def test_nullable_field_absent_across_samples_is_not_drift(
    verifier: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_file = Path("sleep-disruptions.fit")
    schema = {
        "sleep_disruption_severity_period_mesgs": {
            "fields": {"severity": {"type": "int", "nullable": True}}
        }
    }
    monkeypatch.setattr(verifier, "load_schema", lambda _file: schema)
    monkeypatch.setattr(
        verifier,
        "decode_fit_file",
        lambda _path: {"sleep_disruption_severity_period_mesgs": [{}]},
    )

    findings = verifier.verify_file_type(
        "SLEEP_DISRUPTIONS",
        {
            "file": "unused.json",
            "messages": ["sleep_disruption_severity_period_mesgs"],
        },
        {"2026-01-01": {"SLEEP_DISRUPTIONS": [sample_file]}},
    )

    assert not [finding for finding in findings if finding["level"] == "DRIFT"]
    assert any(
        finding["level"] == "OK" and "nullable" in finding["detail"]
        for finding in findings
    )


def test_required_field_absent_across_samples_remains_drift(
    verifier: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_file = Path("wellness.fit")
    schema = {
        "monitoring_mesgs": {
            "fields": {"steps": {"type": "int", "nullable": False}}
        }
    }
    monkeypatch.setattr(verifier, "load_schema", lambda _file: schema)
    monkeypatch.setattr(
        verifier,
        "decode_fit_file",
        lambda _path: {"monitoring_mesgs": [{}]},
    )

    findings = verifier.verify_file_type(
        "WELLNESS",
        {"file": "unused.json", "messages": ["monitoring_mesgs"]},
        {"2026-01-01": {"WELLNESS": [sample_file]}},
    )

    drift = [finding for finding in findings if finding["level"] == "DRIFT"]
    assert [finding["detail"] for finding in drift] == [
        "Field 'steps' documented but NOT found in data"
    ]
