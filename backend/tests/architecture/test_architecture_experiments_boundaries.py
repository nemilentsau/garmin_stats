"""Architecture guard rails for the experiments domain slice."""

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_text_in_files,
    read_repo_file,
)


def test_experiments_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/experiments/routes.py",
    ])


def test_experiments_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/experiments/application/analysis_cache.py",
        "backend/app/domains/experiments/application/analysis.py",
        "backend/app/domains/experiments/application/exposures.py",
        "backend/app/domains/experiments/application/exposure_sync.py",
        "backend/app/domains/experiments/application/management.py",
        "backend/app/domains/experiments/application/preview.py",
        "backend/app/domains/experiments/application/target_metrics.py",
    ])


def test_experiments_application_files_are_named_by_responsibility():
    for path in [
        "backend/app/domains/experiments/application/experiments.py",
        "backend/app/domains/experiments/application/analysis_math.py",
        "backend/app/domains/experiments/application/ports.py",
        "backend/app/domains/experiments/application/stats.py",
        "backend/app/domains/experiments/domain/analysis_math.py",
        "backend/app/domains/experiments/api/__init__.py",
        "backend/app/domains/experiments/api/experiments.py",
        "backend/app/domains/experiments/api/target_metrics.py",
        "backend/app/domains/experiments/infra/__init__.py",
        "backend/app/domains/experiments/infra/sqlite_repository.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/experiments/routes.py",
        "backend/app/domains/experiments/adapters.py",
        "backend/app/domains/experiments/dependencies.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_experiment_pure_rules_live_in_domain_layer():
    domain_root = REPO_ROOT / "backend/app/domains/experiments/domain"
    expected = {
        domain_root / "__init__.py",
        domain_root / "adherence.py",
        domain_root / "analysis.py",
        domain_root / "confounders.py",
        domain_root / "exposures.py",
        domain_root / "metric_paths.py",
        domain_root / "outcomes.py",
        domain_root / "reporting.py",
        domain_root / "statistics.py",
        domain_root / "windows.py",
    }
    assert expected.issubset(set(domain_root.rglob("*.py")))


def test_experiment_analysis_module_stays_as_pipeline_assembler():
    source = read_repo_file("backend/app/domains/experiments/domain/analysis.py")
    assert "import numpy" not in source

    extracted_concerns = [
        "def _extract_metric_values(",
        "def _analyse_metric_lag(",
        "def _analyse_metric(",
        "def _extract_confounder(",
        "def _check_confounders(",
        "def _compute_adherence(",
        "def _classify_confidence(",
        "def _generate_summary(",
    ]
    assert [name for name in extracted_concerns if name in source] == []


def test_experiment_domain_modules_do_not_import_application_or_infra():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/experiments/domain").rglob("*.py")
    ]
    assert_no_text_in_files(
        paths,
        [
            "app.domains.experiments.application",
            "app.domains.experiments.infra",
            "app.bootstrap",
            "app.infra.database",
            "fastapi",
            "build_container",
        ],
    )


def test_infra_database_does_not_own_experiment_persistence_contracts():
    source = read_repo_file("backend/app/infra/database.py")
    assert "domains.experiments.contracts" not in source

    experiment_persistence_functions = [
        "def experiment_exists(",
        "def load_experiment(",
        "def save_experiment(",
        "def delete_experiment(",
        "def load_experiments(",
        "def save_experiment_exposure(",
        "def replace_experiment_exposure_for_date(",
        "def load_experiment_exposures(",
        "def save_experiment_report(",
        "def load_experiment_reports(",
        "def save_experiment_analysis(",
        "def delete_experiment_analysis(",
        "def load_experiment_analysis(",
        "def load_all_experiment_analyses(",
    ]
    assert [name for name in experiment_persistence_functions if name in source] == []


def test_bootstrap_routing_mounts_domain_experiment_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.experiments.routes" in source
    assert "domains.experiments.api.experiments" not in source
    assert "domains.experiments.api.target_metrics" not in source
    assert "from ..routers.experiments import router as experiments_router" not in source
    assert "from ..routers.target_metrics import router as target_metrics_router" not in source
    assert "include_router(experiments_router)" in source
    assert "include_router(target_metrics_router)" in source


def test_migrated_experiment_service_shims_are_removed():
    for path in [
        "backend/app/services/experiment_analysis.py",
        "backend/app/services/experiment_exposure_sync.py",
        "backend/app/services/experiment_stats.py",
        "backend/app/services/experiments.py",
        "backend/app/services/target_metrics.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_migrated_experiment_router_shims_are_removed():
    for path in [
        "backend/app/routers/experiments.py",
        "backend/app/routers/target_metrics.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_assistant_reads_experiment_analysis_through_domain_service():
    source = read_repo_file("backend/app/domains/assistant/infra/sqlite_repository.py")
    assert "domains.experiments.application.analysis_cache" in source
    assert "load_experiment_analysis" not in source
