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
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/application/validation.py": {
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/routes.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/artifacts/contracts.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/coach/read_gateway.py": {
        "app.domains.garmin_analytics.application",
        "app.domains.garmin_analytics.application.dependencies",
        "app.domains.garmin_analytics.contracts",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
        "app.domains.journal.dependencies",
        "app.domains.training.application",
        "app.domains.training.contracts",
        "app.domains.training.dependencies",
    },
    "backend/app/domains/coach/domain/context.py": {
        "app.domains.garmin_analytics.contracts",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.training.contracts",
    },
    "backend/app/domains/coach/infra/plots.py": {
        "app.domains.garmin_analytics.contracts",
    },
    "backend/app/domains/experiments/application/management.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/domain/analysis.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/domain/confounders.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/domain/metric_paths.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/domain/outcomes.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/experiments/domain/preview_validation.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/experiments/domain/exposures.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/experiments/dependencies.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/preview.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/application/exposure_sync.py": {
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
        "app.domains.routines.application.schedule_window",
    },
    "backend/app/domains/experiments/adapters.py": {
    },
    "backend/app/domains/experiments/read_sources.py": {
        "app.domains.garmin_analytics.application.dependencies",
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.journal.contracts",
        "app.domains.journal.dependencies",
    },
    "backend/app/domains/garmin_sync/infra/factory.py": {
        "app.core.config",
    },
    "backend/app/domains/garmin_sync/infra/sqlite_ingest.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily",
    },
    "backend/app/domains/garmin_sync/infra/activity_ingest.py": {
        "app.domains.garmin_health.infra.fit_parser",
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
    "backend/app/domains/garmin_analytics/contracts/runs.py": {
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
    "backend/app/domains/garmin_analytics/domain/analysis/hrv_patterns.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/sleep.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/analysis/stress.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/dashboard.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/recovery_score/evidence.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
    "backend/app/domains/garmin_analytics/domain/insights/heart_rate.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/insights/hrv.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/insights/hrv_rules.py": {
        GARMIN_HEALTH_CONTRACTS,
        "app.domains.garmin_health.domain.daily_metrics",
    },
    "backend/app/domains/garmin_analytics/domain/primitives/trends.py": {
        GARMIN_HEALTH_CONTRACTS,
    },
}


def test_cross_slice_imports_are_explicitly_allowlisted():
    assert_cross_slice_imports_are_allowlisted(ALLOWLISTED_CROSS_SLICE_IMPORTS)
