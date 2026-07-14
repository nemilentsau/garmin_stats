"""Architecture guard rails for documented module ownership.

Per-domain boundary charters are colocated with each slice at
`backend/app/<pkg>/CHARTER.md` (relocated out of `docs/ARCHITECTURE.md` in the
2026-07 docs restructure, which thinned ARCHITECTURE.md to a map + domain
index). These guards assert every charter still exists and carries the required
boundary fields, and that garmin_sync is framed as a capability.
"""

from tests._architecture import read_repo_file

# module label -> repo-relative path of its colocated charter
MODULE_CHARTERS = {
    "garmin_sync": "backend/app/domains/garmin_sync/CHARTER.md",
    "garmin_health": "backend/app/domains/garmin_health/CHARTER.md",
    "garmin_analytics": "backend/app/domains/garmin_analytics/CHARTER.md",
    "experiments": "backend/app/domains/experiments/CHARTER.md",
    "journal": "backend/app/domains/journal/CHARTER.md",
    "training": "backend/app/domains/training/CHARTER.md",
    "core/profile": "backend/app/core/profile/CHARTER.md",
}

REQUIRED_CHARTER_HEADINGS = [
    "## Owns",
    "## Does not own",
    "## May import",
    "## Must not import",
    "## Public entrypoints",
]


def test_each_module_has_a_colocated_ownership_charter():
    for module, path in MODULE_CHARTERS.items():
        source = read_repo_file(path)
        for heading in REQUIRED_CHARTER_HEADINGS:
            assert heading in source, f"{module} charter ({path}) is missing '{heading}'"


def test_architecture_index_links_every_charter():
    """ARCHITECTURE.md's domain index links to each colocated charter so the map
    remains a router to the authoritative boundary contracts."""
    source = read_repo_file("docs/ARCHITECTURE.md")
    for module, path in MODULE_CHARTERS.items():
        rel_link = path.replace("backend/", "../backend/", 1)
        assert rel_link in source, (
            f"ARCHITECTURE.md domain index is missing a link to {module} ({rel_link})"
        )


def test_garmin_sync_is_documented_as_capability_not_business_domain():
    source = read_repo_file("backend/app/domains/garmin_sync/CHARTER.md")

    assert "data-acquisition capability" in source
    assert "not a business domain" in source
    assert "FIT parsing semantics" in source
