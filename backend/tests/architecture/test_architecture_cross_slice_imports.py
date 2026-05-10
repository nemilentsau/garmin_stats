"""Architecture guard rails for cross-slice imports."""

from tests._architecture import assert_cross_slice_imports_are_allowlisted

GARMIN_HEALTH_CONTRACTS = "app.domains.garmin_health.contracts"

ALLOWLISTED_CROSS_SLICE_IMPORTS = {
    "backend/app/domains/artifacts/application/activation.py": {
        "app.domains.routines.application.activation",
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/application/bundles.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/application/staging.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/application/validation.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/routes.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/artifacts/contracts.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/experiments/application/management.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/domain/analysis.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/domain/analysis_math.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/ports.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/preview.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/application/exposure_sync.py": {
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
        "app.domains.routines.application.schedule_window",
    },
    "backend/app/domains/experiments/infra/sqlite_repository.py": {
        "app.domains.garmin_analytics.adapters",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/assistant/application/ports.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.contracts",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/assistant/application/entity_resolution.py": {
        "app.domains.experiments.contracts",
    },
    "backend/app/domains/assistant/application/retrieval.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.contracts",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/assistant/infra/sqlite_repository.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.application.analysis_cache",
        "app.domains.experiments.application.ports",
        "app.domains.experiments.contracts",
        "app.domains.garmin_analytics.adapters",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
        "app.domains.routines.adapters",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/garmin_sync/adapters.py": {
        "app.core.config",
    },
    "backend/app/domains/garmin_analytics/adapters.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/application/daily_aggregates.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/application/dependencies.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/application/raw_biometrics.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/contracts/insights.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/contracts/period.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/contracts/raw.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/body_battery.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/heart_rate.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics.heart_rate",
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/hrv.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics.hrv",
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/respiration.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/skin_temp.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/sleep.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/spo2.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/stress.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/body_battery.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/heart_rate.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/hrv.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics.hrv",
    },
    "backend/app/domains/garmin_analytics/domain/analysis/sleep.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/stress.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/dashboard.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/insights/heart_rate.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/insights/hrv.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/primitives/trends.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
}


def test_cross_slice_imports_are_explicitly_allowlisted():
    assert_cross_slice_imports_are_allowlisted(ALLOWLISTED_CROSS_SLICE_IMPORTS)
