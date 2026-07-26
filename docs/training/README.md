# Training

This directory is the source of truth for the shipped v3 training system and
the authored programs retained in the repository.

## What is current

- [`principles.md`](principles.md) governs training decisions and authoring.
- [`artifact-schema-v3.md`](artifact-schema-v3.md) defines the shipped import
  and activation contract.
- [`roadmap.md`](roadmap.md) records the current implementation boundary and
  remaining work.
- [`programs/threshold-development-2026-07-13/`](programs/threshold-development-2026-07-13/)
  is the latest authored program checked into the repository.

"Latest authored" is not the same as "active." A checked-in program becomes
active only after the complete artifact set passes import validation and is
activated in SQLite. The active `training_blocks` record is the runtime source
of truth; this directory does not claim that any checked-in program is currently
imported.

## What to import

Import **one `.zip` file** on the Training Import page. That ZIP represents one
authored program and contains its block, running, strength, support, registry,
and exercise-library JSON artifacts. The backend shows and validates those six
artifacts after you submit the package; you do not select them individually.

The latest checked-in source is
[`programs/threshold-development-2026-07-13/`](programs/threshold-development-2026-07-13/).
When packaging that source, include its six JSON files. The Markdown review may
be present in the ZIP because the importer ignores non-JSON documentation.

## Authored programs

Program directories use a descriptive name plus their planned start date. The
JSON filenames and internal artifact IDs remain unchanged because import stores
authored content without translating it. Packages are authored outside the app;
the app does not generate ZIPs, lint reports, compiled schedules, or any other
derived training content.

## Test fixtures

The v3 calibration artifact set is not a selectable or current program. It lives
under `backend/tests/fixtures/training/v3-calibration/` because backend contract,
validator, import, and read-model tests consume it. Its expected lint report is
retained there with the input artifacts.
