"""Architecture guard rails for global shared bucket imports."""

from tests._architecture import assert_imports_from_module_match_allowlist

ALLOWLISTED_APP_STATS_IMPORTERS = {
    "backend/app/domains/garmin_analytics/application/biometrics.py",
    "backend/app/domains/garmin_analytics/application/body_battery_analysis.py",
    "backend/app/domains/garmin_analytics/application/heart_rate.py",
    "backend/app/domains/garmin_analytics/application/heart_rate_analysis.py",
    "backend/app/domains/garmin_analytics/application/hrv.py",
    "backend/app/domains/garmin_analytics/application/hrv_analysis.py",
    "backend/app/domains/garmin_analytics/application/overview.py",
    "backend/app/domains/garmin_analytics/application/period_summary.py",
    "backend/app/domains/garmin_analytics/application/sleep_analysis.py",
    "backend/app/domains/garmin_analytics/application/stress_analysis.py",
}

ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS = {
    "backend/app/domains/garmin_analytics/application/body_battery_analysis.py",
    "backend/app/domains/garmin_analytics/application/heart_rate_analysis.py",
    "backend/app/domains/garmin_analytics/application/hrv_analysis.py",
    "backend/app/domains/garmin_analytics/application/period_summary.py",
    "backend/app/domains/garmin_analytics/application/sleep_analysis.py",
    "backend/app/domains/garmin_analytics/application/stress_analysis.py",
}


def test_app_stats_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.stats",
        ALLOWLISTED_APP_STATS_IMPORTERS,
    )


def test_app_infra_cache_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.infra.cache",
        ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS,
        equivalent_imports={"app.infra"},
        required_import_name="cache",
    )
