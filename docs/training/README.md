# Training

This directory is the source of truth for the shipped v3 training system and
the authored programs retained in the repository.

## What is current

- [`principles.md`](principles.md) governs training decisions and authoring.
- [`artifact-schema-v3.md`](artifact-schema-v3.md) defines the shipped import
  and activation contract.
- [`roadmap.md`](roadmap.md) records the current implementation boundary and
  remaining work.
- [`threshold-development-2026-07-13.zip`](programs/threshold-development-2026-07-13/threshold-development-2026-07-13.zip)
  is the latest authored program checked into the repository and the exact file
  accepted by Training Import.

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
You must also choose **Program starts**, which becomes runtime Day 1. The app
stores that choice beside the verbatim imported block instead of rewriting the
authored date inside the ZIP.

Import
[`threshold-development-2026-07-13.zip`](programs/threshold-development-2026-07-13/threshold-development-2026-07-13.zip)
for the latest checked-in program. Do not select or package JSON files yourself.

## Authored programs

Program directories use a descriptive name plus their planned start date. Each
directory keeps one canonical authored ZIP plus any human review documentation;
it does not keep loose copies of the ZIP's JSON members. Internal filenames and
artifact IDs remain unchanged because import stores authored content without
translating it. A directory or artifact date records authoring provenance; it
does not force the runtime start selected during import. The app does not
generate ZIPs, lint reports, compiled schedules, or any other derived training
content.

## Test fixtures

The v3 calibration artifact set is not a selectable or current program. It lives
under `backend/tests/fixtures/training/v3-calibration/` because backend contract,
validator, import, and read-model tests consume it. Its expected lint report is
retained there with the input artifacts.
