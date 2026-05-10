"""Architecture guard rails for canonical Garmin health data ownership."""

from tests._architecture import REPO_ROOT, assert_no_text_in_files, read_repo_file


def test_garmin_health_owns_canonical_contracts_and_daily_metric_composer():
    base = REPO_ROOT / "backend/app/domains/garmin_health"

    for path in [
        base / "__init__.py",
        base / "contracts/__init__.py",
        base / "contracts/readings.py",
        base / "contracts/daily.py",
        base / "domain/__init__.py",
        base / "domain/daily.py",
        base / "domain/daily_metrics/__init__.py",
        base / "domain/daily_metrics/heart_rate.py",
        base / "domain/daily_metrics/stress.py",
        base / "domain/daily_metrics/body_battery.py",
        base / "domain/daily_metrics/spo2.py",
        base / "domain/daily_metrics/respiration.py",
        base / "domain/daily_metrics/hrv.py",
        base / "domain/daily_metrics/sleep.py",
        base / "domain/daily_metrics/skin_temp.py",
    ]:
        assert path.exists()

    assert not (base / "domain/numeric.py").exists()
    assert (REPO_ROOT / "backend/app/utils/numeric.py").exists()

    daily_source = read_repo_file("backend/app/domains/garmin_health/domain/daily.py")
    assert "def compute_daily_metric" in daily_source
    assert "def compute_daily_metrics" in daily_source
    assert "DailyAggregatesResponse" not in daily_source

    utils_numeric_source = read_repo_file("backend/app/utils/numeric.py")
    for forbidden in ("hrv", "body_battery", "garmin", "DayData", "DailyMetric"):
        assert forbidden.lower() not in utils_numeric_source.lower(), (
            f"app/utils/numeric.py must not contain Garmin vocabulary ({forbidden!r})"
        )


def test_garmin_sync_ingest_adapter_uses_garmin_health_not_garmin_analytics_behavior():
    source = read_repo_file("backend/app/domains/garmin_sync/sqlite_ingest.py")

    assert "domains.garmin_health.domain.daily import" in source
    assert "domains.garmin_analytics.domain" not in source
    assert "domains.garmin_analytics.utils" not in source
    assert "compute_daily_aggregates" not in source
    assert "DailyAggregatesResponse" not in source


def test_garmin_health_does_not_import_feature_domains():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/garmin_health").rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert_no_text_in_files(
        paths,
        [
            "app.domains.garmin_analytics",
            "app.domains.experiments",
            "app.domains.assistant",
            "app.infra.database",
        ],
    )
