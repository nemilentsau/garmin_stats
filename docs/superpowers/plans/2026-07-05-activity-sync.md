# Activity Download on Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dashboard Sync button (`POST /api/ingest/sync`) also downloads new tracked-activity FIT files from Garmin Connect into `data/garmin_activities/YYYY-MM-DD/`, reporting workout counts alongside wellness counts. Download only — no DB ingest of activities.

**Architecture:** Salvage the uncommitted `--activities` work from the `.worktrees/garmin-activity-download` worktree, then move its file-layout logic into `garmin_sync` infra so both the CLI script and a new `ActivityFileStore` port share one implementation. Extend the existing hexagonal sync ports (`GarminDownloadClient`, new `ActivityFileStore`) and add an activity sweep to the `sync_garmin` workflow that runs after the watcher-guarded wellness block (the activities tree is not watched and not ingested). Failures in the activity sweep are counted, never abort wellness sync.

**Tech Stack:** FastAPI + Pydantic backend (Python 3.14, `uv`), `garminconnect` + `garmin-fit-sdk`, SvelteKit 5 frontend, generated API types via `scripts/generate-api-types.sh`.

## Global Constraints

- Python: `uv` only, never bare `pip`. All backend commands run from `backend/`.
- Python changes: `cd backend && uv run ruff check` + `uv run pyright app/ tests/` + `uv run pytest tests/ -v` must all pass with 0 errors before each commit.
- Backend API schema changed (SyncResult): regenerate types with `bash scripts/generate-api-types.sh`, commit `frontend/src/lib/api-types.ts`; never hand-edit it.
- Frontend changes: `cd frontend && npm run check` must pass; visually verify changed pages with browser MCP at desktop viewport.
- Sync/watcher/startup house rule: tests must cover missing / already-in-sync / stale states including an idempotent second run that does no work, plus a real local smoke check against the actual data tree before done.
- Do NOT modify anything inside `.worktrees/garmin-activity-download/` — read/copy from it only. Leave its unrelated uncommitted work (observability, finding-verifier, `running_effort_report.py`, CLAUDE.md edits) untouched.
- Work happens on branch `activity-sync` cut from `main` (NOT from `refactor-routines`).
- Frontend is display-only: no stats computation in Svelte.

**Paths:** `ROOT = /Users/andreinemilentsau/Projects/garmin_stats`, `WT = $ROOT/.worktrees/garmin-activity-download`. All file paths below are relative to `ROOT`.

---

### Task 1: Branch + salvage the worktree's activity-download work verbatim

The worktree branch has zero commits; everything lives in its working tree. This task snapshots the activity-related subset into a clean branch so we have a green checkpoint before refactoring. `scripts/download_garmin.py` and `docs/ACTIVITY_ANALYTICS_DESIGN.md` have NOT drifted between the worktree base and main (verified) — direct copy/apply is safe. `README.md` HAS drifted — use 3-way apply.

**Files:**
- Create branch: `activity-sync` from `main`
- Copy from worktree: `scripts/download_garmin.py`, `backend/tests/scripts/test_download_garmin_script.py`, `docs/RUNNING_ACTIVITY_SCHEMA.md`, `docs/STRENGTH_ACTIVITY_SCHEMA.md`, `docs/activity-analysis/` (3 files)
- Patch: `README.md`, `docs/ACTIVITY_ANALYTICS_DESIGN.md`
- Commit (also include this plan file `docs/superpowers/plans/2026-07-05-activity-sync.md`)

**Interfaces:**
- Produces: working `--activities` CLI mode; script helpers `existing`-behavior tests passing; the salvaged script still contains ALL helpers inline (extraction happens in Task 3).

- [ ] **Step 1: Create the branch**

```bash
cd /Users/andreinemilentsau/Projects/garmin_stats
git checkout -b activity-sync main
```

- [ ] **Step 2: Copy activity files from the worktree**

```bash
WT=.worktrees/garmin-activity-download
cp "$WT/scripts/download_garmin.py" scripts/download_garmin.py
cp "$WT/backend/tests/scripts/test_download_garmin_script.py" backend/tests/scripts/
cp "$WT/docs/RUNNING_ACTIVITY_SCHEMA.md" "$WT/docs/STRENGTH_ACTIVITY_SCHEMA.md" docs/
mkdir -p docs/activity-analysis
cp "$WT"/docs/activity-analysis/*.md docs/activity-analysis/
```

- [ ] **Step 3: Apply the README + design-doc edits (3-way for README drift)**

```bash
git -C "$WT" diff -- README.md docs/ACTIVITY_ANALYTICS_DESIGN.md > /private/tmp/claude-501/-Users-andreinemilentsau-Projects-garmin-stats/4b8c2008-40fd-4353-8a1d-e46a39124bb1/scratchpad/activity-docs.patch
git apply -3 /private/tmp/claude-501/-Users-andreinemilentsau-Projects-garmin-stats/4b8c2008-40fd-4353-8a1d-e46a39124bb1/scratchpad/activity-docs.patch
```

If the README hunk conflicts: the intent is (a) replace the two-line "Garmin Connect download support…" paragraph in the Data download section with the worktree's paragraph describing `--activities`, the `data/garmin_activities/YYYY-MM-DD/` layout, local-time+sport naming, and the JSON sidecar; (b) add the two `--activities` usage code blocks; (c) add `GARMIN_ACTIVITY_DATA_DIR` to the runtime path overrides list. Read `$WT/README.md` around the "Data download" section and port it by hand.

- [ ] **Step 4: Run the salvaged tests and validation**

```bash
cd backend
uv run pytest tests/scripts/test_download_garmin_script.py -v
uv run ruff check && uv run pyright app/ tests/
```

Expected: 4 passed; ruff and pyright 0 errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/andreinemilentsau/Projects/garmin_stats
git add scripts/download_garmin.py backend/tests/scripts/test_download_garmin_script.py \
  docs/RUNNING_ACTIVITY_SCHEMA.md docs/STRENGTH_ACTIVITY_SCHEMA.md docs/activity-analysis \
  README.md docs/ACTIVITY_ANALYTICS_DESIGN.md docs/superpowers/plans/2026-07-05-activity-sync.md
git commit -m "feat(activities): salvage activity download script, schemas, and analyses from worktree

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Add `activities_dir` to backend app config

**Files:**
- Modify: `backend/app/core/config.py` (AppConfig + get_app_config)
- Test: `backend/tests/core/test_config.py` (match existing test style in that file)

**Interfaces:**
- Produces: `AppConfig.activities_dir: Path`, env override `GARMIN_ACTIVITY_DATA_DIR`, default `<project>/data/garmin_activities`. Task 6's factory consumes `app_config.activities_dir`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/core/test_config.py`, aligning imports/naming with the file's existing tests)

```python
def test_activities_dir_defaults_under_project_data_tree():
    config = get_app_config(environ={})
    assert config.activities_dir.name == "garmin_activities"
    assert config.activities_dir.parent.name == "data"
    assert config.activities_dir.parent == config.data_dir.parent


def test_activities_dir_reads_env_override():
    config = get_app_config(environ={"GARMIN_ACTIVITY_DATA_DIR": "/tmp/custom-activities"})
    assert config.activities_dir == Path("/tmp/custom-activities")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/test_config.py -v`
Expected: FAIL — `AppConfig` has no attribute `activities_dir`.

- [ ] **Step 3: Implement** — in `backend/app/core/config.py`, add the field and resolution:

```python
@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    data_dir: Path
    activities_dir: Path
    garmin_token_dir: Path
```

and inside `get_app_config`:

```python
    default_activities_dir = _PROJECT_ROOT / "data" / "garmin_activities"
```

```python
        activities_dir=Path(
            env.get("GARMIN_ACTIVITY_DATA_DIR", str(default_activities_dir))
        ).expanduser(),
```

- [ ] **Step 4: Run tests + validation**

Run: `cd backend && uv run pytest tests/core/ -v && uv run ruff check && uv run pyright app/ tests/`
Expected: all pass, 0 errors. If any other code constructs `AppConfig(...)` directly (search `AppConfig(` in `app/` and `tests/`), add the new field there.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/core/test_config.py
git commit -m "feat(config): GARMIN_ACTIVITY_DATA_DIR / activities_dir app config

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Extract activity file layout into `garmin_sync` infra; script delegates

One implementation of the `garmin_activities` tree layout, owned by the domain. The script keeps CLI-only concerns (login, date args, `--health-range`, `--force`, printing) and imports the layout functions, following the `scripts/reingest.py` import pattern.

**Files:**
- Create: `backend/app/domains/garmin_sync/infra/activity_files.py`
- Modify: `scripts/download_garmin.py` (delete moved helpers, import from infra)
- Test: create `backend/tests/domains/garmin_sync/test_activity_files.py`; rewrite `backend/tests/scripts/test_download_garmin_script.py` (keep only the CLI-only `health_data_date_range` test)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces (used by Tasks 4–6):
  - `existing_activity_stem(day_dir: Path, activity_id: str) -> str | None`
  - `store_activity_payload(day_dir: Path, activity_id: str, metadata: dict[str, Any], payload: bytes) -> list[Path]` (raises `ValueError` on unusable payloads; cleans up partial files)
  - `remove_activity_outputs(day_dir: Path, file_stem: str) -> None`
  - `class FilesystemActivityStore` with `has_activity(activities_dir: Path, day: date, activity_id: str) -> bool` and `store_activity(activities_dir: Path, day: date, activity_id: str, metadata: dict[str, Any], payload: bytes) -> None`

- [ ] **Step 1: Write the failing tests** — `backend/tests/domains/garmin_sync/test_activity_files.py`:

```python
"""Tests for the garmin_activities filesystem layout and store adapter.

Covers payload-extraction equivalence classes (bare FIT, ZIP of FITs, junk),
stem naming from local start time plus decoded sport, sidecar-based
idempotence lookups, and stem-collision handling.
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from app.domains.garmin_sync.infra import activity_files
from app.domains.garmin_sync.infra.activity_files import (
    FilesystemActivityStore,
    existing_activity_stem,
    store_activity_payload,
)

METADATA = {"activityId": 23398049297, "startTimeLocal": "2026-06-27 10:40:56"}


@pytest.fixture(autouse=True)
def _fixed_fit_kind(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        activity_files, "_activity_kind_from_fit", lambda _path: "running_generic"
    )


def _zip_payload(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_store_bare_fit_payload_names_by_local_time_and_sport(tmp_path: Path):
    paths = store_activity_payload(tmp_path, "23398049297", METADATA, b"\x0eFITDATA")

    assert [p.name for p in paths] == ["104056_running_generic.fit"]
    sidecar = json.loads((tmp_path / "104056_running_generic.json").read_text())
    assert sidecar["activityId"] == 23398049297


def test_store_zip_payload_extracts_only_fit_members(tmp_path: Path):
    payload = _zip_payload({"a.fit": b"one", "b.fit": b"two", "notes.txt": b"skip"})

    paths = store_activity_payload(tmp_path, "1", METADATA, payload)

    assert [p.name for p in paths] == [
        "104056_running_generic.fit",
        "104056_running_generic_part2.fit",
    ]


def test_store_zip_without_fit_members_raises_and_leaves_no_files(tmp_path: Path):
    payload = _zip_payload({"readme.txt": b"no fits"})

    with pytest.raises(ValueError):
        store_activity_payload(tmp_path, "1", METADATA, payload)
    assert list(tmp_path.iterdir()) == []


def test_store_corrupt_zip_payload_raises_value_error(tmp_path: Path):
    with pytest.raises(ValueError):
        store_activity_payload(tmp_path, "1", METADATA, b"PK\x03\x04garbage")


def test_stem_appends_activity_id_only_on_sidecar_collision(tmp_path: Path):
    (tmp_path / "104056_running_generic.json").write_text(json.dumps({"activityId": 111}))

    paths = store_activity_payload(tmp_path, "23398049297", METADATA, b"\x0eFIT")

    assert paths[0].name == "104056_running_generic_23398049297.fit"


def test_stem_falls_back_when_metadata_lacks_start_time(tmp_path: Path):
    paths = store_activity_payload(tmp_path, "5", {"activityId": 5}, b"\x0eFIT")

    assert paths[0].name == "unknown-time_running_generic.fit"


def test_existing_activity_stem_matches_sidecar_activity_id(tmp_path: Path):
    (tmp_path / "104056_running_generic.json").write_text(
        json.dumps({"activityId": 23398049297})
    )

    assert existing_activity_stem(tmp_path, "23398049297") == "104056_running_generic"
    assert existing_activity_stem(tmp_path, "999") is None


def test_store_adapter_round_trips_day_directories(tmp_path: Path):
    store = FilesystemActivityStore()
    day = date(2026, 6, 27)

    assert store.has_activity(tmp_path, day, "23398049297") is False
    store.store_activity(tmp_path, day, "23398049297", METADATA, b"\x0eFIT")

    assert store.has_activity(tmp_path, day, "23398049297") is True
    assert (tmp_path / "2026-06-27" / "104056_running_generic.fit").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_activity_files.py -v`
Expected: FAIL — `No module named 'app.domains.garmin_sync.infra.activity_files'`.

- [ ] **Step 3: Create `backend/app/domains/garmin_sync/infra/activity_files.py`** — port the helpers from the salvaged script (they are currently inline there; move, don't reinvent):

```python
"""Filesystem layout for downloaded Garmin activity FIT files.

Owns the ``data/garmin_activities/YYYY-MM-DD`` tree: extracting Garmin's
original activity payloads (bare FIT or ZIP of FITs), deriving readable
filename stems from local start time plus decoded FIT sport/sub_sport,
writing JSON metadata sidecars, and answering activity-id idempotence
lookups from those sidecars. Consumed by sync workflows through the
``ActivityFileStore`` port and by ``scripts/download_garmin.py`` backfills.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from garmin_fit_sdk import Decoder, Stream

_SAFE_FILENAME_PATTERN = re.compile(r"[^a-z0-9_-]+")


def existing_activity_stem(day_dir: Path, activity_id: str) -> str | None:
    """Find an already-downloaded activity's file stem by Garmin activity id."""
    if not day_dir.exists():
        return None
    for metadata_path in sorted(day_dir.glob("*.json")):
        if _metadata_matches_activity(metadata_path, activity_id):
            return metadata_path.stem
    return None


def store_activity_payload(
    day_dir: Path,
    activity_id: str,
    metadata: dict[str, Any],
    payload: bytes,
) -> list[Path]:
    """Extract one activity payload into ``day_dir`` and write its sidecar.

    Raises ``ValueError`` when the payload is not a usable FIT/ZIP-of-FITs or
    the first FIT cannot be decoded for naming; extracted files are removed on
    failure so a bad payload leaves no partial state behind.
    """
    day_dir.mkdir(parents=True, exist_ok=True)
    download_stem = f"download-{activity_id}"
    extracted = _extract_activity_payload(payload, download_stem, day_dir)
    try:
        final_stem = _activity_file_stem_from_fit(day_dir, activity_id, metadata, extracted)
    except ValueError:
        for path in extracted:
            path.unlink(missing_ok=True)
        raise
    extracted = _rename_activity_outputs(day_dir, download_stem, final_stem, extracted)
    metadata_path = day_dir / f"{final_stem}.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return extracted


def remove_activity_outputs(day_dir: Path, file_stem: str) -> None:
    """Delete the FIT files and sidecar for one stored activity stem."""
    for path in day_dir.glob(f"{file_stem}*.fit"):
        path.unlink(missing_ok=True)
    (day_dir / f"{file_stem}.json").unlink(missing_ok=True)


class FilesystemActivityStore:
    """ActivityFileStore adapter over the garmin_activities day-directory tree."""

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool:
        return existing_activity_stem(activities_dir / day.isoformat(), activity_id) is not None

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict[str, Any],
        payload: bytes,
    ) -> None:
        store_activity_payload(activities_dir / day.isoformat(), activity_id, metadata, payload)


def _activity_file_stem_from_fit(
    day_dir: Path,
    activity_id: str,
    metadata: dict[str, Any],
    fit_paths: list[Path],
) -> str:
    base_stem = _activity_base_stem(metadata, _activity_kind_from_fit(fit_paths[0]))
    metadata_path = day_dir / f"{base_stem}.json"
    if not metadata_path.exists() or _metadata_matches_activity(metadata_path, activity_id):
        return base_stem
    return f"{base_stem}_{activity_id}"


def _activity_base_stem(metadata: dict[str, Any], activity_kind: str) -> str:
    started_at = _activity_start_time(metadata)
    time_part = started_at.strftime("%H%M%S") if started_at else "unknown-time"
    return f"{time_part}_{_safe_filename_part(activity_kind)}"


def _activity_kind_from_fit(fit_path: Path) -> str:
    messages, errors = Decoder(Stream.from_file(str(fit_path))).read()
    if errors:
        raise ValueError(f"{fit_path.name} decoded with errors: {errors}")

    session = (messages.get("session_mesgs") or [{}])[0]
    sport = _safe_filename_part(str(session.get("sport") or "activity"))
    sub_sport = _safe_filename_part(str(session.get("sub_sport") or "generic"))
    return f"{sport}_{sub_sport}"


def _activity_start_time(metadata: dict[str, Any]) -> datetime | None:
    for key in ("startTimeLocal", "startTimeGMT"):
        raw = metadata.get(key)
        if not raw:
            continue
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _safe_filename_part(value: str) -> str:
    safe = _SAFE_FILENAME_PATTERN.sub("-", value.strip().lower()).strip("-_")
    return safe or "activity"


def _metadata_matches_activity(metadata_path: Path, activity_id: str) -> bool:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(metadata.get("activityId")) == activity_id


def _rename_activity_outputs(
    day_dir: Path,
    source_stem: str,
    target_stem: str,
    fit_paths: list[Path],
) -> list[Path]:
    if source_stem == target_stem:
        return fit_paths

    renamed: list[Path] = []
    for index, fit_path in enumerate(fit_paths):
        suffix = "" if index == 0 else f"_part{index + 1}"
        target_path = day_dir / f"{target_stem}{suffix}.fit"
        fit_path.replace(target_path)
        renamed.append(target_path)
    return renamed


def _extract_activity_payload(payload: bytes, file_stem: str, day_dir: Path) -> list[Path]:
    """Extract Garmin's original activity payload into activity FIT files."""
    if not payload.startswith(b"PK"):
        fit_path = day_dir / f"{file_stem}.fit"
        fit_path.write_bytes(payload)
        return [fit_path]

    try:
        with ZipFile(BytesIO(payload)) as archive:
            fit_members = [
                member for member in archive.namelist() if member.lower().endswith(".fit")
            ]
            if not fit_members:
                raise ValueError("activity ZIP contained no FIT files")

            extracted: list[Path] = []
            for index, member in enumerate(fit_members):
                suffix = "" if index == 0 else f"_part{index + 1}"
                target_path = day_dir / f"{file_stem}{suffix}.fit"
                target_path.write_bytes(archive.read(member))
                extracted.append(target_path)
            return extracted
    except BadZipFile as e:
        raise ValueError("activity payload was not a valid ZIP") from e
```

Note the two deliberate behavior deltas vs the script (both invisible to callers): extraction uses a `download-<id>` temp stem instead of a metadata-derived interim stem, and the sidecar is written only after the final rename (so `_rename_activity_outputs` no longer unlinks a stale sidecar).

- [ ] **Step 4: Run the new tests**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_activity_files.py -v`
Expected: 8 passed.

- [ ] **Step 5: Rewire `scripts/download_garmin.py`** to import the layout functions. Add the backend path insert immediately after the stdlib imports (mirror `scripts/reingest.py`, including its `# ruff: noqa: E402, I001` header comment placement):

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.domains.garmin_sync.infra.activity_files import (
    existing_activity_stem,
    remove_activity_outputs,
    store_activity_payload,
)
```

Then in the script: delete the now-duplicated helpers (`_existing_activity_stem`, `_activity_file_stem_from_fit`, `_activity_base_stem`, `_activity_kind_from_fit`, `_activity_start_time`, `_safe_filename_part`, `_metadata_matches_activity`, `_remove_activity_outputs`, `_rename_activity_outputs`, `_extract_activity_payload`, `SAFE_FILENAME_PATTERN`, and the now-unused `garmin_fit_sdk` / `BytesIO` / `ZipFile` imports), and rewrite the per-activity body of `download_activity_files` to:

```python
        activity_id_str = str(activity_id)
        name = activity.get("activityName") or "(unnamed)"
        existing_stem = existing_activity_stem(day_dir, activity_id_str)

        if existing_stem and not force:
            print(f"    {existing_stem}: already exists ({name})")
            skipped += 1
            continue

        print(f"    {activity_id_str}: downloading ({name})...", end=" ", flush=True)
        try:
            payload = client.download_activity(
                activity_id_str,
                Garmin.ActivityDownloadFormat.ORIGINAL,
            )
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1
            continue

        if not payload or len(payload) < MINIMUM_ACTIVITY_BYTES:
            print("no activity payload")
            failed += 1
            continue

        if force and existing_stem:
            remove_activity_outputs(day_dir, existing_stem)

        try:
            extracted = store_activity_payload(day_dir, activity_id_str, activity, payload)
        except ValueError as e:
            print(f"FAILED ({e})")
            failed += 1
            continue

        print(f"OK ({len(payload):,} bytes, {len(extracted)} FIT)")
        downloaded += 1
```

- [ ] **Step 6: Trim `backend/tests/scripts/test_download_garmin_script.py`** to only the CLI-owned helper (the three naming/sidecar tests are superseded by `test_activity_files.py`). Full new file content:

```python
"""Regression tests for Garmin download script CLI policy."""

from __future__ import annotations

import runpy
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "download_garmin.py"


def _script_namespace() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="__not_main__")


def test_health_data_date_range_uses_zip_and_extracted_day_entries(tmp_path: Path):
    ns = _script_namespace()
    (tmp_path / "2026-06-03.zip").write_bytes(b"zip")
    (tmp_path / "2026-06-01").mkdir()
    (tmp_path / "not-a-date.zip").write_bytes(b"ignored")

    start, end = ns["health_data_date_range"](tmp_path)

    assert (start, end) == (date(2026, 6, 1), date(2026, 6, 3))
```

- [ ] **Step 7: Smoke the script end-to-end against a real, already-downloaded date** (idempotence path — must skip everything, no network writes):

```bash
cd backend && uv run python ../scripts/download_garmin.py --activities --date 2026-06-27
```

Expected: lists the day's activities, each line ends `already exists (…)`, summary shows 0 downloaded / N skipped / 0 failed.

- [ ] **Step 8: Full validation + commit**

```bash
cd backend && uv run pytest tests/ -v && uv run ruff check && uv run pyright app/ tests/
cd .. && git add backend/app/domains/garmin_sync/infra/activity_files.py \
  backend/tests/domains/garmin_sync/test_activity_files.py \
  backend/tests/scripts/test_download_garmin_script.py scripts/download_garmin.py
git commit -m "refactor(garmin-sync): activity file layout owned by infra, script delegates

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Note: `backend/tests/architecture/test_architecture_garmin_sync_boundaries.py` runs in the full suite — if it enumerates infra modules explicitly, register `activity_files` per that file's pattern.

---

### Task 4: Activity ports + Garmin Connect client methods

**Files:**
- Modify: `backend/app/domains/garmin_sync/dependencies.py` (ActivityRef, protocol methods, ActivityFileStore port)
- Modify: `backend/app/domains/garmin_sync/infra/garmin_connect.py` (client rename + two methods)
- Test: `backend/tests/domains/garmin_sync/test_garmin_connect.py` (extend; update for rename)

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Task 5/6):
  - `@dataclass(frozen=True) ActivityRef { activity_id: str; metadata: dict[str, Any] }` in `dependencies.py`
  - `GarminDownloadClient` protocol gains `list_activities(day: date) -> list[ActivityRef]` and `download_activity_original(activity_id: str) -> bytes | None`
  - `ActivityFileStore` protocol with `has_activity(activities_dir: Path, day: date, activity_id: str) -> bool` / `store_activity(activities_dir: Path, day: date, activity_id: str, metadata: dict[str, Any], payload: bytes) -> None`
  - `GarminConnectWellnessClient` renamed to `GarminConnectDownloadClient` (factory docstring updated to match)

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/domains/garmin_sync/test_garmin_connect.py`, reusing that file's existing fake-raw-client/sleep-recorder conventions (read the file first; adapt fake construction to match). New cases:

```python
def test_list_activities_maps_ids_and_skips_entries_without_id():
    raw = FakeRawGarminClient(
        activities=[
            {"activityId": 23398049297, "activityName": "Morning Run"},
            {"activityName": "ghost entry"},
        ]
    )
    client = GarminConnectDownloadClient(raw, sleep=lambda _s: None)

    refs = client.list_activities(date(2026, 6, 27))

    assert [r.activity_id for r in refs] == ["23398049297"]
    assert refs[0].metadata["activityName"] == "Morning Run"
    assert raw.activity_queries == [("2026-06-27", "2026-06-27")]


def test_download_activity_original_returns_none_for_short_payload():
    raw = FakeRawGarminClient(activity_payload=b"x")
    client = GarminConnectDownloadClient(raw, sleep=lambda _s: None)

    assert client.download_activity_original("123") is None


def test_download_activity_original_returns_bytes_for_real_payload():
    raw = FakeRawGarminClient(activity_payload=b"P" * 200)
    client = GarminConnectDownloadClient(raw, sleep=lambda _s: None)

    assert client.download_activity_original("123") == b"P" * 200


def test_activity_and_wellness_requests_share_request_spacing():
    sleeps: list[float] = []
    raw = FakeRawGarminClient(activities=[], activity_payload=b"P" * 200)
    client = GarminConnectDownloadClient(raw, sleep=sleeps.append)

    client.list_activities(date(2026, 6, 27))
    client.download_activity_original("123")

    assert sleeps == [1.0]
```

If the file's existing fake cannot express activities, extend it with `activities`, `activity_payload`, and an `activity_queries` recorder rather than adding a second fake class.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_garmin_connect.py -v`
Expected: FAIL — `GarminConnectDownloadClient` not defined.

- [ ] **Step 3: Implement ports in `dependencies.py`** — add near the existing protocols:

```python
@dataclass(frozen=True)
class ActivityRef:
    """One Garmin Connect activity listed for a date, with its raw metadata."""

    activity_id: str
    metadata: dict[str, Any]


class GarminDownloadClient(Protocol):
    """Logged-in Garmin client for wellness archives and activity payloads."""

    def download_wellness_archive(self, day: date) -> bytes | None: ...

    def list_activities(self, day: date) -> list[ActivityRef]: ...

    def download_activity_original(self, activity_id: str) -> bytes | None: ...


class ActivityFileStore(Protocol):
    """Filesystem port for the data/garmin_activities day-directory tree."""

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool: ...

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict[str, Any],
        payload: bytes,
    ) -> None: ...
```

(add `from typing import Any` to that module's imports).

- [ ] **Step 4: Implement the client in `infra/garmin_connect.py`** — rename the class and add the methods; extract the spacing logic:

```python
_MINIMUM_ACTIVITY_BYTES = 100


class _RawGarminClient(Protocol):
    def download(self, path: str) -> bytes | bytearray | None: ...

    def get_activities_by_date(
        self,
        startdate: str,
        enddate: str,
        activitytype: str | None = None,
        sortorder: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def download_activity(
        self, activity_id: str, dl_fmt: Any
    ) -> bytes | bytearray | None: ...


class GarminConnectDownloadClient:
    """Download wellness archives and original activity payloads via Garmin Connect."""

    # __init__ unchanged from GarminConnectWellnessClient

    def download_wellness_archive(self, day: date) -> bytes | None:
        self._space_requests()
        data = self._client.download(f"{_WELLNESS_ARCHIVE_PATH_PREFIX}/{day.isoformat()}")
        if not data or len(data) < _MINIMUM_ARCHIVE_BYTES:
            return None
        return bytes(data)

    def list_activities(self, day: date) -> list[ActivityRef]:
        self._space_requests()
        date_str = day.isoformat()
        activities = self._client.get_activities_by_date(date_str, date_str, sortorder="asc")
        refs: list[ActivityRef] = []
        for activity in activities:
            activity_id = activity.get("activityId")
            if activity_id is None:
                continue
            refs.append(ActivityRef(activity_id=str(activity_id), metadata=activity))
        return refs

    def download_activity_original(self, activity_id: str) -> bytes | None:
        self._space_requests()
        data = self._client.download_activity(
            activity_id, Garmin.ActivityDownloadFormat.ORIGINAL
        )
        if not data or len(data) < _MINIMUM_ACTIVITY_BYTES:
            return None
        return bytes(data)

    def _space_requests(self) -> None:
        if self._has_requested:
            self._sleep(self._request_spacing_seconds)
        self._has_requested = True
```

Update `GarminConnectClientFactory.create` to return `GarminConnectDownloadClient(...)` and fix all references to the old class name (`grep -rn GarminConnectWellnessClient backend/`).

- [ ] **Step 5: Run tests + validation**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/ -v && uv run ruff check && uv run pyright app/ tests/`
Expected: all pass, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domains/garmin_sync/dependencies.py \
  backend/app/domains/garmin_sync/infra/garmin_connect.py \
  backend/tests/domains/garmin_sync/test_garmin_connect.py
git commit -m "feat(garmin-sync): activity list/download client methods + ActivityFileStore port

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Activity sweep in the sync workflow + SyncResult counters

**Files:**
- Modify: `backend/app/domains/garmin_sync/contracts.py` (SyncResult)
- Modify: `backend/app/domains/garmin_sync/dependencies.py` (GarminSyncDependencies fields)
- Modify: `backend/app/domains/garmin_sync/workflows.py` (sweep + planning)
- Test: `backend/tests/domains/garmin_sync/test_ingest_application.py`

**Interfaces:**
- Consumes: `ActivityRef`, `ActivityFileStore`, client methods from Task 4.
- Produces: `SyncResult` gains required int fields `activities_downloaded`, `activities_skipped`, `activities_failed`. `GarminSyncDependencies` gains `activities_dir: Path` and `activity_files: ActivityFileStore`. Internal helpers `_plan_activity_dates(*, wellness_start: date, today: date) -> list[date]` and `_sync_activities(deps, client, days) -> tuple[int, int, int]`; module constant `_ACTIVITY_LOOKBACK_DAYS = 3`.

- [ ] **Step 1: Write the failing tests** — in `test_ingest_application.py`:

(a) Extend `FakeGarminClient` (same class, don't add a parallel fake):

```python
class FakeGarminClient:
    def __init__(
        self,
        responses: dict[str, bytes | None],
        *,
        activities: dict[str, list[ActivityRef]] | None = None,
        activity_payloads: dict[str, bytes | None] | None = None,
        listing_errors: set[str] | None = None,
    ) -> None:
        self.responses = responses
        self.days: list[date] = []
        self.activities = activities or {}
        self.activity_payloads = activity_payloads or {}
        self.listing_errors = listing_errors or set()
        self.listed_days: list[str] = []
        self.downloaded_activities: list[str] = []

    def download_wellness_archive(self, day: date) -> bytes | None:
        self.days.append(day)
        return self.responses[day.isoformat()]

    def list_activities(self, day: date) -> list[ActivityRef]:
        date_str = day.isoformat()
        self.listed_days.append(date_str)
        if date_str in self.listing_errors:
            raise RuntimeError("listing failed")
        return self.activities.get(date_str, [])

    def download_activity_original(self, activity_id: str) -> bytes | None:
        self.downloaded_activities.append(activity_id)
        return self.activity_payloads.get(activity_id)
```

(b) Add `FakeActivityFileStore`:

```python
class FakeActivityFileStore:
    def __init__(self, *, existing: set[tuple[str, str]] | None = None) -> None:
        self.existing = existing if existing is not None else set()
        self.stored: list[tuple[Path, str, str]] = []
        self.store_error: ValueError | None = None

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool:
        return (day.isoformat(), activity_id) in self.existing

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict,
        payload: bytes,
    ) -> None:
        if self.store_error is not None:
            raise self.store_error
        self.stored.append((activities_dir, day.isoformat(), activity_id))
        self.existing.add((day.isoformat(), activity_id))
```

(c) Extend `_deps` with pass-through kwargs `activities`, `activity_payloads`, `listing_errors`, `existing_activities`, construct `store = FakeActivityFileStore(existing=existing_activities)`, add `activities_dir=tmp_path / "garmin_activities"` and `activity_files=store` to `GarminSyncDependencies(...)`, and append `store` to the returned tuple. Update every existing full-tuple unpack in the file to absorb the extra element.

(d) New tests (fixture default: `latest=2026-03-14`, `today=2026-03-15`, so the wellness window is 03-14..03-15 and the activity window with 3-day lookback is 03-12..03-15):

```python
def _ref(activity_id: str) -> ActivityRef:
    return ActivityRef(activity_id=activity_id, metadata={"activityId": activity_id})


def test_sync_sweeps_activity_window_with_lookback_and_stores_new(tmp_path: Path):
    deps, _ingest, _archives, _watcher, client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-12": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )

    result = sync_garmin(deps)

    assert client.listed_days == ["2026-03-12", "2026-03-13", "2026-03-14", "2026-03-15"]
    assert [entry[2] for entry in store.stored] == ["a1"]
    assert (result.activities_downloaded, result.activities_skipped, result.activities_failed) == (1, 0, 0)


def test_sync_second_run_skips_already_stored_activities(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-13": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )

    first = sync_garmin(deps)
    second = sync_garmin(deps)

    assert first.activities_downloaded == 1
    assert second.activities_downloaded == 0
    assert second.activities_skipped == 1
    assert [entry[2] for entry in store.stored] == ["a1"]


def test_sync_activity_listing_failure_is_counted_and_isolated(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, _store = _deps(
        tmp_path,
        activities={"2026-03-15": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
        listing_errors={"2026-03-12"},
    )

    result = sync_garmin(deps)

    assert result.activities_failed == 1
    assert result.activities_downloaded == 1
    assert result.days_ingested == 1  # wellness ingest unaffected


def test_sync_counts_activity_without_payload_as_failed(tmp_path: Path):
    deps, *_rest, _files, _store = _deps(
        tmp_path,
        activities={"2026-03-14": [_ref("a1")]},
    )

    result = sync_garmin(deps)

    assert (result.activities_downloaded, result.activities_failed) == (0, 1)


def test_sync_counts_unusable_activity_payload_as_failed(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-14": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )
    store.store_error = ValueError("activity ZIP contained no FIT files")

    result = sync_garmin(deps)

    assert (result.activities_downloaded, result.activities_failed) == (0, 1)


def test_plan_activity_dates_applies_lookback_beyond_wellness_start():
    days = _plan_activity_dates(wellness_start=date(2026, 3, 14), today=date(2026, 3, 15))

    assert days == [date(2026, 3, 12), date(2026, 3, 13), date(2026, 3, 14), date(2026, 3, 15)]


def test_plan_activity_dates_keeps_older_wellness_start():
    days = _plan_activity_dates(wellness_start=date(2026, 3, 10), today=date(2026, 3, 15))

    assert days[0] == date(2026, 3, 10)
    assert days[-1] == date(2026, 3, 15)
```

Import `ActivityRef` and `_plan_activity_dates` at the top of the test module.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py -v`
Expected: new tests FAIL (`_plan_activity_dates` undefined, `GarminSyncDependencies` missing fields).

- [ ] **Step 3: Implement.**

`contracts.py` — extend `SyncResult`:

```python
class SyncResult(DefaultsRequired):
    downloaded: int
    skipped: int
    failed: int
    deleted_latest: str | None = None
    days_ingested: int
    duration_ms: int
    activities_downloaded: int
    activities_skipped: int
    activities_failed: int
```

`dependencies.py` — extend the bundle (fields grouped with the existing filesystem ones):

```python
@dataclass(frozen=True)
class GarminSyncDependencies:
    ...
    data_dir: Path
    activities_dir: Path
    ...
    files: SyncFileStore
    activity_files: ActivityFileStore
    ...
```

`workflows.py` — add after the wellness helpers:

```python
_ACTIVITY_LOOKBACK_DAYS = 3


def _plan_activity_dates(*, wellness_start: date, today: date) -> list[date]:
    """Sweep the wellness window plus a short lookback for late activity uploads."""
    start = min(wellness_start, today - timedelta(days=_ACTIVITY_LOOKBACK_DAYS))
    days: list[date] = []
    current = start
    while current <= today:
        days.append(current)
        current += timedelta(days=1)
    return days


def _sync_activities(
    deps: GarminSyncDependencies,
    client: GarminDownloadClient,
    days: list[date],
) -> tuple[int, int, int]:
    """Download missing activity payloads; per-item failures never abort the sweep."""
    downloaded = 0
    skipped = 0
    failed = 0
    for day in days:
        date_str = day.isoformat()
        try:
            refs = client.list_activities(day)
        except Exception:
            log.exception("  %s: activity listing failed", date_str)
            failed += 1
            continue
        for ref in refs:
            if deps.activity_files.has_activity(deps.activities_dir, day, ref.activity_id):
                skipped += 1
                continue
            try:
                payload = client.download_activity_original(ref.activity_id)
            except Exception:
                log.exception("  %s: activity %s download failed", date_str, ref.activity_id)
                failed += 1
                continue
            if payload is None:
                log.info("  %s: activity %s had no payload", date_str, ref.activity_id)
                failed += 1
                continue
            try:
                deps.activity_files.store_activity(
                    deps.activities_dir, day, ref.activity_id, ref.metadata, payload
                )
            except ValueError:
                log.exception("  %s: activity %s payload unusable", date_str, ref.activity_id)
                failed += 1
                continue
            downloaded += 1
    return downloaded, skipped, failed
```

In `sync_garmin`: hoist `today = deps.today()` above the plan call (reuse it), and after the existing `finally: deps.resume_watcher()` block insert:

```python
    activity_days = _plan_activity_dates(wellness_start=plan.dates[0], today=today)
    activities_downloaded, activities_skipped, activities_failed = _sync_activities(
        deps, client, activity_days
    )
```

then extend the returned `SyncResult(...)` with the three new fields. Update the module + `sync_garmin` docstrings: the activity sweep runs outside watcher suspension because the activities tree is neither watched nor ingested.

- [ ] **Step 4: Run tests + validation**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/ -v && uv run pytest tests/ -v && uv run ruff check && uv run pyright app/ tests/`
Expected: all pass. If any other test constructs `SyncResult` or `GarminSyncDependencies` directly (e.g. `test_ingest_api.py`), add the new fields there.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/garmin_sync/contracts.py \
  backend/app/domains/garmin_sync/dependencies.py \
  backend/app/domains/garmin_sync/workflows.py \
  backend/tests/domains/garmin_sync/test_ingest_application.py
git commit -m "feat(garmin-sync): sync workflow downloads new activity FIT files

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Wire factory + regenerate API types

**Files:**
- Modify: `backend/app/domains/garmin_sync/infra/factory.py`
- Regenerate: `frontend/src/lib/api-types.ts` (+ `frontend/openapi.json` if tracked)

**Interfaces:**
- Consumes: `AppConfig.activities_dir` (Task 2), `FilesystemActivityStore` (Task 3), dependency fields (Task 5).
- Produces: production wiring; generated `SyncResult` TS type with the three new fields for Task 7.

- [ ] **Step 1: Wire the factory** — in `build_garmin_sync_infra`, import `FilesystemActivityStore` from `app.domains.garmin_sync.infra.activity_files` and add to the bundle construction:

```python
        activities_dir=app_config.activities_dir,
        activity_files=FilesystemActivityStore(),
```

- [ ] **Step 2: Full backend validation**

Run: `cd backend && uv run pytest tests/ -v && uv run ruff check && uv run pyright app/ tests/`
Expected: all pass, 0 errors.

- [ ] **Step 3: Regenerate API types**

```bash
bash scripts/generate-api-types.sh
git diff --stat frontend/src/lib/api-types.ts
```

Expected: `SyncResult` in `api-types.ts` gains `activities_downloaded`, `activities_skipped`, `activities_failed`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/domains/garmin_sync/infra/factory.py frontend/src/lib/api-types.ts
git status --short frontend/openapi.json && git add frontend/openapi.json || true
git commit -m "feat(garmin-sync): wire activity store into sync factory, regen API types

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Sync button shows workout counts + real smoke check + docs

**Files:**
- Modify: `frontend/src/routes/+page.svelte` (two `syncResult` render sites, lines ~179 and ~186)
- Modify: `README.md` (sync behavior note)

**Interfaces:**
- Consumes: generated `SyncResult` TS type (Task 6).

- [ ] **Step 1: Update both sync-result lines** in `frontend/src/routes/+page.svelte`. Both currently read:

```svelte
{syncResult.downloaded} downloaded, {syncResult.days_ingested} days ingested
```

Change both to:

```svelte
{syncResult.downloaded} archives, {syncResult.activities_downloaded} workouts, {syncResult.days_ingested} days ingested
```

- [ ] **Step 2: Frontend check**

Run: `cd frontend && npm run check`
Expected: 0 errors.

- [ ] **Step 3: Real smoke check (mandatory house rule for sync changes).** Start both servers (`cd backend && uv run uvicorn app.main:app --reload` and `cd frontend && npm run dev`), open the dashboard with browser MCP tools, then:
  1. Click **Sync**. Wait for completion (this hits real Garmin Connect; tokens already exist in `~/.garminconnect`).
  2. Verify the result line shows non-zero workouts (local `data/garmin_activities/` was last downloaded through 2026-06-28, so roughly a week of activities should arrive) and check on disk: `ls data/garmin_activities/ | tail -8` should now include dates after 2026-06-28, each new day dir containing `HHMMSS_<sport>.fit` + `.json` pairs.
  3. Click **Sync again**: workouts downloaded must be 0 (all skipped) and no new files may appear — the idempotent no-op run, observed for real.
  4. Screenshot the dashboard sync area for the record (desktop viewport).

- [ ] **Step 4: README** — in the sync/dashboard section, note that the Sync button also downloads new tracked-activity FIT files into `data/garmin_activities/` (wellness window + 3-day lookback), download-only (activities are not yet ingested into the database).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/+page.svelte README.md
git commit -m "feat(dashboard): sync button downloads and reports new workouts

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-plan notes

- **Out of scope (explicitly):** parsing/ingesting activity FITs into the DB, activity analytics endpoints, frontend activity surfaces. The salvaged `RUNNING_ACTIVITY_SCHEMA.md` / `STRENGTH_ACTIVITY_SCHEMA.md` are the specs for that follow-up.
- **Left in the worktree deliberately:** observability experiments, Langfuse/Opik importers + tests, finding-verifier harness, `running_effort_report.py`, CLAUDE.md observability edits, `four_weeks_meditation.json`.
- The `testing` skill (`.claude/skills/testing/SKILL.md`) governs test style — executors should read it before writing the test files above and adjust naming/structure if it conflicts.
