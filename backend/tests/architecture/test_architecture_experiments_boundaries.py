"""Architecture guard rails for the experiments domain slice."""

from tests._architecture import REPO_ROOT, read_repo_file


def test_experiments_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/experiments/api/experiments.py",
        "backend/app/domains/experiments/api/target_metrics.py",
    ]:
        source = read_repo_file(path)
        assert "app.infra.database" not in source
        assert "app.services." not in source
        assert "app.routers" not in source


def test_experiments_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/experiments/application/analysis.py",
        "backend/app/domains/experiments/application/experiments.py",
        "backend/app/domains/experiments/application/exposure_sync.py",
        "backend/app/domains/experiments/application/stats.py",
        "backend/app/domains/experiments/application/target_metrics.py",
    ]:
        assert "fastapi" not in read_repo_file(path)


def test_experiments_application_does_not_import_flat_services():
    for path in [
        "backend/app/domains/experiments/application/analysis.py",
        "backend/app/domains/experiments/application/experiments.py",
        "backend/app/domains/experiments/application/exposure_sync.py",
        "backend/app/domains/experiments/application/stats.py",
        "backend/app/domains/experiments/application/target_metrics.py",
    ]:
        source = read_repo_file(path)
        assert "app.services" not in source


def test_bootstrap_routing_mounts_domain_experiment_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.experiments.api.experiments" in source
    assert "domains.experiments.api.target_metrics" in source
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
    assert "domains.experiments.application.experiments" in source
    assert "load_experiment_analysis" not in source
