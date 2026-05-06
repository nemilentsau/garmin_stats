"""Architecture guard rails for documented module ownership."""

from tests._architecture import read_repo_file

REQUIRED_MODULE_CHARTERS = [
    "assistant",
    "routines",
    "garmin_sync",
    "garmin_analytics",
    "experiments",
    "artifacts",
    "journal",
    "programs",
    "core/profile",
]

REQUIRED_CHARTER_FIELDS = [
    "Owns:",
    "Does not own:",
    "May import:",
    "Must not import:",
    "Public entrypoints:",
]


def test_architecture_documents_module_ownership_charters():
    source = read_repo_file("docs/ARCHITECTURE.md")

    for module in REQUIRED_MODULE_CHARTERS:
        heading = f"#### `{module}`"
        assert heading in source

        section_start = source.index(heading)
        next_heading = source.find("\n#### `", section_start + len(heading))
        section = source[section_start:] if next_heading == -1 else source[
            section_start:next_heading
        ]

        for field in REQUIRED_CHARTER_FIELDS:
            assert field in section, f"{module} is missing {field}"


def test_garmin_sync_is_documented_as_capability_not_business_domain():
    source = read_repo_file("docs/ARCHITECTURE.md")

    section_start = source.index("#### `garmin_sync`")
    next_heading = source.find("\n#### `", section_start + 1)
    section = source[section_start:] if next_heading == -1 else source[
        section_start:next_heading
    ]

    assert "data acquisition capability" in section
    assert "not a business domain" in section
    assert "FIT parsing semantics" in section
