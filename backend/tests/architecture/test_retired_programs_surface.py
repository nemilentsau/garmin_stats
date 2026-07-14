"""Regression guard for the retired pre-v3 Programs product surface."""

from tests._architecture import REPO_ROOT, read_repo_file


def test_programs_domain_and_frontend_route_are_absent():
    for path in [
        "backend/app/domains/programs",
        "backend/tests/domains/programs",
        "frontend/src/routes/programs",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_programs_are_absent_from_runtime_composition_and_navigation():
    sources = {
        path: read_repo_file(path)
        for path in [
            "backend/app/bootstrap/container.py",
            "backend/app/bootstrap/routing.py",
            "backend/app/bootstrap/schema.py",
            "frontend/src/routes/+layout.svelte",
        ]
    }

    assert all("domains.programs" not in source for source in sources.values())
    assert "programs_repo" not in sources["backend/app/bootstrap/container.py"]
    assert "'/programs'" not in sources["frontend/src/routes/+layout.svelte"]


def test_generated_contracts_do_not_publish_program_routes():
    assert '"/api/programs' not in read_repo_file("frontend/src/lib/api-types.ts")
    assert "`/api/programs" not in read_repo_file("docs/reference/routes.md")
