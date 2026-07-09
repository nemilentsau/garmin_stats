"""Single-shot v3 artifact import and activation policy.

Consumes an uploaded set of v3 training artifacts (content bundles, one
block, the signal registry, the exercise library) and either activates the
whole set atomically or activates nothing. There is no partial import: every
file must be independently contract-valid, the set must be complete relative
to the block's own `bundle_ids`, the ported L1-L12 linter
(`application.validation`) must report zero errors, and every lint warning
must appear in the caller's `warning_acks`. Any single failure returns a full
per-file diagnosis with `activated=False` and leaves the repository
untouched — this module never raises for a user-supplied validation failure;
the diagnosis rides the result instead (a route layer turns it into a 200
response, not an HTTP error).

Stored artifacts are the raw uploaded dicts, never a re-serialized round trip
through the typed `V3Block`/`V3Bundle`/`SignalRegistry`/`ExerciseLibrary`
models — those models exist here only to validate and to feed the
compiler/linter, not to become the persisted record.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.contracts.base import DefaultsRequired, StrictDefaultsRequired
from app.domains.training.application.validation import lint
from app.domains.training.contracts import (
    ExerciseLibrary,
    LintReport,
    SignalRegistry,
    StoredBlock,
    StoredBundle,
    StoredLibrary,
    StoredRegistry,
    V3Block,
    V3Bundle,
)
from app.domains.training.dependencies import TrainingRepository
from app.utils.timeutil import now_iso

ArtifactKind = Literal["bundle", "block", "registry", "library"]

_REGISTRY_RECORD_ID = "registry"
_LIBRARY_RECORD_ID = "library"


class ImportFile(StrictDefaultsRequired):
    """One uploaded artifact file: its name plus parsed JSON content."""

    filename: str
    content: dict[str, Any]


class ImportRequest(StrictDefaultsRequired):
    """An upload batch plus any lint warnings the caller has already accepted."""

    files: list[ImportFile]
    warning_acks: list[str] = []


class FileValidation(DefaultsRequired):
    """Per-file diagnosis: detected kind, contract validity, and any errors."""

    filename: str
    kind: ArtifactKind | None = None
    valid: bool
    errors: list[str] = []


class ImportResult(DefaultsRequired):
    """Full diagnosis of one import attempt, including whether it activated."""

    files: list[FileValidation] = []
    lint_report: LintReport | None = None
    missing_kinds: list[str] = []
    activated: bool = False


def _detect_kind(content: dict[str, Any]) -> ArtifactKind | None:
    """Classify one artifact by its distinguishing top-level key.

    `cards` only appears on bundles, `identity` only on the block, `signals`
    only on the registry, `exercises` only on the library — the four content
    shapes never overlap, so first-match-wins needs no priority ordering.
    """
    if "cards" in content:
        return "bundle"
    if "identity" in content:
        return "block"
    if "signals" in content:
        return "registry"
    if "exercises" in content:
        return "library"
    return None


def _format_errors(exc: ValidationError) -> list[str]:
    formatted: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"])
        formatted.append(f"{loc}: {error['msg']}" if loc else error["msg"])
    return formatted


def _validate[ModelT: BaseModel](
    model_cls: type[ModelT], content: dict[str, Any]
) -> tuple[ModelT | None, list[str]]:
    try:
        return model_cls.model_validate(content), []
    except ValidationError as exc:
        return None, _format_errors(exc)


def import_artifacts(repo: TrainingRepository, request: ImportRequest) -> ImportResult:
    """Validate, lint, and single-shot activate an uploaded v3 artifact set.

    Every file is classified and contract-validated independently; a second
    file of a singleton kind (block/registry/library), or a second bundle
    sharing an already-seen id, is kept as a per-file error rather than
    silently replacing the first. Completeness is checked in both
    directions: every block-declared `bundle_ids` entry must have a matching
    uploaded bundle (`missing_kinds`), and every uploaded bundle must be
    referenced by the block's `bundle_ids` (a per-file error on the stray
    bundle) — an uploaded bundle the block doesn't reference would otherwise
    validate and then silently vanish from lint/storage while the rest of
    the set activates, which breaks the all-or-nothing contract. Activation
    additionally requires zero lint errors and every lint warning
    acknowledged. On any gap this returns the full diagnosis with
    `activated=False` and never calls `repo.save_import`.
    """
    file_results: list[FileValidation] = []

    block: V3Block | None = None
    block_file: ImportFile | None = None
    block_count = 0
    bundles: dict[str, V3Bundle] = {}
    bundle_files: dict[str, ImportFile] = {}
    bundle_result_index: dict[str, int] = {}
    registry: SignalRegistry | None = None
    registry_file: ImportFile | None = None
    registry_count = 0
    library: ExerciseLibrary | None = None
    library_file: ImportFile | None = None
    library_count = 0
    all_files_valid = True

    for file in request.files:
        kind = _detect_kind(file.content)
        if kind is None:
            file_results.append(
                FileValidation(
                    filename=file.filename,
                    kind=None,
                    valid=False,
                    errors=[
                        "unrecognized artifact: expected one of 'cards', 'identity', "
                        "'signals', 'exercises'"
                    ],
                )
            )
            all_files_valid = False
            continue

        errors: list[str]
        if kind == "block":
            block_model, errors = _validate(V3Block, file.content)
            if block_model is not None:
                block_count += 1
                if block_count == 1:
                    block, block_file = block_model, file
                else:
                    errors = ["duplicate block artifact; only one block is allowed per import"]
        elif kind == "bundle":
            bundle_model, errors = _validate(V3Bundle, file.content)
            if bundle_model is not None:
                if bundle_model.id in bundles:
                    errors = [f"duplicate bundle id '{bundle_model.id}'"]
                else:
                    bundles[bundle_model.id] = bundle_model
                    bundle_files[bundle_model.id] = file
                    bundle_result_index[bundle_model.id] = len(file_results)
        elif kind == "registry":
            registry_model, errors = _validate(SignalRegistry, file.content)
            if registry_model is not None:
                registry_count += 1
                if registry_count == 1:
                    registry, registry_file = registry_model, file
                else:
                    errors = ["duplicate registry artifact; only one registry is allowed"]
        else:
            library_model, errors = _validate(ExerciseLibrary, file.content)
            if library_model is not None:
                library_count += 1
                if library_count == 1:
                    library, library_file = library_model, file
                else:
                    errors = ["duplicate exercise library artifact; only one library is allowed"]

        valid = not errors
        if not valid:
            all_files_valid = False
        file_results.append(
            FileValidation(filename=file.filename, kind=kind, valid=valid, errors=errors)
        )

    missing_kinds: list[str] = []
    if block is None:
        missing_kinds.append("block")
    if registry is None:
        missing_kinds.append("registry")
    if library is None:
        missing_kinds.append("library")
    if block is not None:
        missing_kinds.extend(
            bundle_id for bundle_id in block.bundle_ids if bundle_id not in bundles
        )
        for bundle_id, index in bundle_result_index.items():
            if bundle_id in block.bundle_ids:
                continue
            result = file_results[index]
            result.errors = [
                *result.errors,
                f"bundle '{bundle_id}' is not referenced by block '{block.id}' (bundle_ids)",
            ]
            result.valid = False
            all_files_valid = False

    lint_report: LintReport | None = None
    activated = False

    if (
        all_files_valid
        and not missing_kinds
        and block is not None
        and registry is not None
        and library is not None
    ):
        ordered_bundles = [bundles[bundle_id] for bundle_id in block.bundle_ids]
        lint_report = lint(block, ordered_bundles, registry, library)
        if not lint_report.errors and all(
            warning in request.warning_acks for warning in lint_report.warnings
        ):
            activated = True
            assert block_file is not None
            assert registry_file is not None
            assert library_file is not None
            stored_block = StoredBlock(
                id=block.id,
                status="active",
                artifact=block_file.content,
                lint_report=lint_report,
                warning_acks=list(request.warning_acks),
                activated_at=now_iso(),
            )
            stored_bundles = [
                StoredBundle(
                    id=bundle_id, status="active", artifact=bundle_files[bundle_id].content
                )
                for bundle_id in block.bundle_ids
            ]
            stored_registry = StoredRegistry(id=_REGISTRY_RECORD_ID, artifact=registry_file.content)
            stored_library = StoredLibrary(id=_LIBRARY_RECORD_ID, artifact=library_file.content)
            repo.save_import(
                block=stored_block,
                bundles=stored_bundles,
                registry=stored_registry,
                library=stored_library,
            )

    return ImportResult(
        files=file_results,
        lint_report=lint_report,
        missing_kinds=missing_kinds,
        activated=activated,
    )
