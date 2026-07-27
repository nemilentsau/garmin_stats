# Garmin Health Coach

Garmin Health Coach is a local-first training and health application. It ingests Garmin wellness and tracked-activity FIT files, computes deterministic backend analytics, executes imported training content, and gives a local Coach bounded evidence for reviews and chat.

The active product has five centers:

1. a recovery overview and metric drill-downs;
2. tracked running activities;
3. the imported v3 training block on Today and Schedule;
4. Coach reviews/chat with durable evidence and memory;
5. explicit-date N=1 experiments with manually recorded day-grain exposures.

All experiment and training content enters through import/upload. The app does not generate, translate, seed, or derive content bundles.

## What is shipped

- Wellness FIT parsing, local-time normalization, daily metrics, period summaries, metric analysis/insights, and a validated recovery score with oxygen and thermoregulation flags.
- Garmin Connect sync for wellness archives and tracked activities.
- Running session/lap/series parsing, imperial read models, Runs list/detail pages, strap dynamics, stamina/performance condition, route display, and training-prescription association.
- Native v3 training import, strict contract validation, L1-L12 activation linting, schedule projection, strength/check-in/RPE capture, tracked-run execution evidence, LTHR measurement evaluation, authored backups, and Coach assessment composition.
- Coach queued run reviews and chat, hierarchical evidence workspaces, semantic journal/brief memory, durable jobs, and isolated Codex execution.
- Experiment preview/import, manual day-grain exposures, and cached N=1 analysis.

Strength and breathing activities download but are not parsed. The v3 registry validates and is stored, but most declared estimators/signals and automated selection rules are not yet executed. Current training work is tracked in [the training roadmap](docs/training/roadmap.md).

## Data flow

```text
Garmin wellness archives
  -> garmin_sync acquisition/persistence
  -> garmin_health FIT parsing and daily composition
  -> garmin_analytics read models
  -> FastAPI
  -> SvelteKit

Garmin tracked activities
  -> garmin_sync download and sport-specific ingest
  -> garmin_health activity parsing
  -> garmin_analytics activity read models
  -> training association/evaluation through injected ports
  -> Runs, Today, Schedule, and Coach evidence
```

The frontend is display-only for analytics. Statistical computation, aggregation, unit conversion, and derived health/training values belong in backend APIs.

Data roots, sync behavior, re-ingest commands, and runtime configuration are documented only in [docs/reference/data-and-ingest.md](docs/reference/data-and-ingest.md).

## Architecture

The FastAPI backend is organized into explicit slices:

- `bootstrap` assembles the app, storage schema, routes, lifecycle, and cross-domain adapters/reactions.
- `garmin_sync` acquires and persists Garmin data.
- `garmin_health` owns canonical FIT parsing, local-time normalization, and daily composition.
- `garmin_analytics` owns Garmin-derived read models, recovery/dashboard analytics, period summaries, and tracked-run reads.
- `training` owns v3 artifact import, activation linting, schedule/capture, run association policy, and measurement/backup evaluation.
- `coach` owns reviews, conversations, evidence packaging, memory, durable jobs, and model execution.
- `experiments` owns explicit-date experiment definitions, manual day-grain exposures, target metrics, and analysis.
- `journal` owns check-ins and notes.
- `core/profile` owns app-level profile configuration.

Per-slice dependency boundaries live in `backend/app/domains/<domain>/CHARTER.md`. The current map and generated route inventory are [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/reference/routes.md](docs/reference/routes.md).

## Content import

### v3 training

The training import at `/training/import` accepts one authored `.zip` package. The package contains the v3 program's six JSON artifacts:

- `running_v3.json`
- `strength_v3.json`
- `support_v3.json`
- the block JSON
- `registry.json`
- `exercise_library.json`

The backend opens the package in memory and ignores non-JSON documentation; it does not generate, translate, or rewrite the authored content. Import is atomic: strict wire validation, completeness checks, schedule compilation, L1-L12 linting, and warning acknowledgement all succeed before the new generation activates. The full contract is [docs/training/artifact-schema-v3.md](docs/training/artifact-schema-v3.md).

Import [`threshold-development-2026-07-13.zip`](docs/training/programs/threshold-development-2026-07-13/threshold-development-2026-07-13.zip) for the latest checked-in authored program. Do not select or package its internal JSON artifacts yourself. Repository presence does not imply runtime activation; the active imported database record is authoritative. Test-only calibration artifacts live under `backend/tests/fixtures/training/`.

### Experiments

Experiment definitions are imported through `/experiments`. Designs provide explicit baseline and treatment dates; experiment-day exposures are recorded directly rather than inferred from a separate runtime. The executable schema and day-grain semantics are owned by `backend/app/domains/experiments/contracts.py` and the experiments charter.

## Running locally

Prerequisites:

- Python 3.14
- Node.js 20+
- `uv`

Backend:

```bash
cd backend
uv sync --python 3.14
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Default URLs are `http://localhost:8000` for the API and `http://localhost:5173` for the frontend.

## Validation

Backend:

```bash
cd backend
uv run ruff check
uv run pyright app/ tests/
uv run pytest tests/ -v
```

Frontend:

```bash
cd frontend
npm run check
```

After backend API schema changes, regenerate `frontend/src/lib/api-types.ts` with `bash scripts/generate-api-types.sh`; never edit that file manually.

## Documentation

- [docs/README.md](docs/README.md) — documentation router and source-of-truth ownership.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — current code map and dependency boundaries.
- [docs/reference/data-and-ingest.md](docs/reference/data-and-ingest.md) — data trees, sync/ingest, configuration, and commands.
- [docs/reference/run-activities.md](docs/reference/run-activities.md) — tracked-run parse, storage, display, association, measurement, and backup semantics.
- [docs/reference/coach.md](docs/reference/coach.md) — Coach evidence, memory, queue, runtime, and API/UI behavior.
- [docs/reference/recovery-dashboard.md](docs/reference/recovery-dashboard.md) and [docs/reference/hrv.md](docs/reference/hrv.md) — shipped analytical surfaces.
- [docs/training/](docs/training/) — training canon, current work, and authored-program index.
- [docs/future/strength-activities.md](docs/future/strength-activities.md) — the only retained unbuilt implementation spec.
- `FINDINGS.md` — durable dataset findings and open analytical questions. Gitignored/local-only by policy (not part of this checkout); the shareable presentation is [docs/findings/](docs/findings/).
