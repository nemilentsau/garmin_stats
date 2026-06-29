#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Bundle import script — previews and imports every JSON bundle in docs/routine_bundles/.

Bundles that haven't been re-authored to the typed card_type schema (schema_version 2)
are reported as SKIP rather than crashing the import.

Usage:
    cd backend && uv run python ../scripts/import_bundles.py
"""

import json
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from pydantic import ValidationError

from app.bootstrap.schema import init_storage
from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.artifacts.application.bundles import (
    import_artifact_bundle,
    preview_artifact_bundle,
)
from app.domains.artifacts.contracts import ArtifactBundleSpec
from app.domains.routines.adapters import SqliteRoutineRepository

BUNDLES_DIR = Path(__file__).parent.parent / "docs" / "routine_bundles"
BUNDLE_GLOB = "*.json"


def main() -> int:
    init_storage()

    bundle_files = sorted(BUNDLES_DIR.glob(BUNDLE_GLOB))
    if not bundle_files:
        print(f"No bundle JSON files found in {BUNDLES_DIR}")
        return 0

    exit_code = 0

    for bundle_path in bundle_files:
        label = bundle_path.name

        # --- load raw JSON ---
        try:
            raw = json.loads(bundle_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"SKIP {label}: invalid JSON — {exc}")
            exit_code = 1
            continue

        # Skip non-bundle files (e.g. experiment specs)
        if "card_templates" not in raw and "routine_specs" not in raw:
            print(f"SKIP {label}: not a bundle spec (no card_templates or routine_specs)")
            continue

        # --- validate against ArtifactBundleSpec (requires card_type schema) ---
        try:
            bundle = ArtifactBundleSpec.model_validate(raw)
        except ValidationError as exc:
            issues = [e["msg"] for e in exc.errors()]
            print(f"SKIP {label}: schema validation failed — {'; '.join(issues[:3])}")
            continue

        # --- preview (checks slot assignments and duplicates) ---
        artifact_repo = SqliteArtifactRepository()
        routines_repo = SqliteRoutineRepository()

        try:
            preview = preview_artifact_bundle(artifact_repo, routines_repo, bundle)
        except ValidationError as exc:
            issues = [e["msg"] for e in exc.errors()]
            print(
                f"SKIP {label}: preview failed (existing DB record has old schema) "
                f"— {'; '.join(issues[:3])}"
            )
            continue

        if not preview.valid:
            blocking = [i.message for i in preview.issues if i.blocking]
            print(f"SKIP {label}: preview has blocking issues — {'; '.join(blocking[:3])}")
            continue

        # --- import ---
        try:
            result = import_artifact_bundle(artifact_repo, routines_repo, bundle)
        except ValidationError as exc:
            issues = [e["msg"] for e in exc.errors()]
            print(
                f"SKIP {label}: import failed (existing DB record has old schema) "
                f"— {'; '.join(issues[:3])}"
            )
            continue
        print(f"OK   {label}: imported {result.total_imported}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
