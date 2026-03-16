# Garmin Health Assistant

This project is not trying to be another Garmin dashboard.

It is trying to become a personal health assistant that uses Garmin data, manual logs, and an AI assistant to help answer questions like:

- Why did recovery dip this week?
- Did meditation help HRV, or did it just coincide with easier days?
- Is this routine worth keeping?
- What should tomorrow's recovery plan look like?

The long-term goal is a data-driven system that can track routines, run messy real-life experiments, and turn all of that into grounded advice instead of generic wellness talk.

## Vision

Garmin already gives raw numbers. This app is meant to turn those numbers into a usable coaching loop:

- ingest health and recovery data from Garmin FIT exports
- let you track routines such as mindfulness, nutrition, mobility, balance work, supplements, or training blocks
- let you run overlapping experiments even when life is messy
- let you talk to an assistant that can explain patterns, caveats, and next steps
- generate plans and recommendations from your own context, not from generic templates

The important distinction is this:

- the backend owns the analytics
- the AI owns synthesis, conversation, prioritization, and writing

That means the app should eventually behave less like a chart collection and more like a personal operating system for health and training decisions.

## Product Direction

Right now the product is **recovery-first**.

That is the correct scope for the current data quality. We already have strong recovery signals such as sleep, HRV, resting heart rate, stress, body battery, respiration, and skin temperature. Those are enough to build a useful health assistant.

We are **not** yet at full workout-performance coaching. Questions like "how does my abs routine affect running?" or "how does nutrition affect lifting?" need better training outcome data than the app currently stores. That expansion is planned, but it should follow the same rule: evidence first, AI interpretation second.

## What We Are Building

### 1. Recovery assistant

A chat-based assistant that can look at recent health context and answer practical questions:

- what changed in the last few days
- why recovery looks worse or better
- what signals matter most today
- what confounders might explain a pattern

### 2. Routine tracking

A place to define and log behaviors that Garmin does not know about:

- meditation
- abs work
- balance drills
- supplements
- meal timing
- mobility
- sleep routines

The current routine runtime is assistant-spec first:

- an assistant or user produces one structured artifact bundle JSON payload
- the backend previews that bundle without writing live runtime data
- the user imports the clean bundle as inert assistant-artifact drafts
- the user explicitly activates valid drafts
- the app compiles them into live cards, schedules, and today-board entries

That boundary is deliberate. New routine content should usually be data, not code. Only a new renderer family should require infrastructure work.

### 3. Experiment tracking

A way to test whether routines appear linked to outcomes over time, even when multiple things overlap.

The system should not pretend life is a clean one-variable lab. It should surface:

- likely signal
- possible signal with heavy confounding
- not enough data

### 4. Plans and adherence

The assistant should eventually move beyond analysis and help with execution:

- daily recovery plan
- weekly plan
- experiment plan
- adherence tracking

## Core Principles

- **Deterministic backend:** metrics, comparisons, confidence, and experiment analysis live in the backend.
- **Display-only frontend:** the UI renders results; it does not compute statistics.
- **Curated AI context:** the assistant works from backend-built snapshots, not broad direct database access.
- **Explicit uncertainty:** overlapping routines and confounders are normal, so confidence must be visible.
- **Local-first by default:** data stays local, while assistant requests send a minimized context bundle to Claude.

## Current Status

### Working today

- Garmin FIT ingest and local SQLite storage
- daily aggregates and metric detail views
- dashboard for recovery signals
- assistant-authored routine drafts with validation and explicit activation
- compiled live card templates, recurring schedules, and a Today board
- assistant MVP with persisted threads and streamed replies

### Not done yet

- evidence-backed experiment engine
- plan generation and adherence loop
- strong training-performance attribution
- serious running/lifting coaching
- reintroducing programs and experiments on top of the new routine runtime

So the app is already useful as a **personal recovery assistant**. It is not yet a complete performance coach.

## How It Works

1. Garmin exports are dropped into `data/garmin_health_stats/YYYY-MM-DD/*.fit`.
2. The backend ingests those files and stores normalized data in local SQLite.
3. Backend services compute daily metrics, insights, and assistant context snapshots.
4. The assistant runtime sends a curated snapshot to Claude Code and streams the reply back.
5. Threads, messages, runs, and snapshots are stored so the assistant has memory and an audit trail.

## Routine Runtime

The routine system now has two layers:

1. **Assistant artifacts**  
   Structured drafts authored by the health assistant. Supported kinds are `card_template`, `routine_spec`, and `capability_request`.
2. **Live runtime records**  
   Activated cards, routines, assignments, and logs that drive `/today`. Persisted date-specific overrides are still read for backward compatibility, but Today no longer authors them.

The app enforces a strict renderer boundary. v1 supports:

- `timer_session`
- `checklist_block`
- `exercise_block`

If a draft asks for an unsupported renderer family, validation rejects it and records a `capability_request` instead of mutating the schema.

The canonical import unit is now a proper artifact bundle:

- `card_templates[]`
- `routine_specs[]`

The app accepts deterministic bundle JSON only. It does not convert arbitrary markdown in-app. The external conversion target for an LLM is documented in [`docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md`](/Users/andreinemilentsau/Projects/garmin_stats/docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md), and the checked-in examples are [`docs/two_week_meditation_bundle.json`](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_meditation_bundle.json) and [`docs/two_week_core_bundle.json`](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_core_bundle.json).

## Main App Areas

- `/`  
  Recovery dashboard and metric exploration.

- `/assistant`  
  Chat with the recovery assistant, keep threads, ask for a daily briefing or weekly review.

- `/today`  
  Render the active day from compiled live schedules and log what actually happened. If the schedule is wrong, fix it through routines creation instead of patching Today.

- `/routines/schedule`  
  Review a 14-day resolved schedule through two lenses: by day for agenda review, and by routine for upcoming dated occurrences.

- `/routines/creation`  
  Paste real bundle JSON, preview create/update deltas without DB writes, import inert drafts, and activate them into the live runtime. Placeholder/demo starter content is rejected at preview/import time.

- `/routines`  
  Redirects to `/routines/schedule`.

- `/experiments`  
  Placeholder. Experiments are intentionally parked until they can consume the new routine runtime cleanly.

- `/programs`  
  Placeholder. The old program-import surface is intentionally offline while routines use the artifact-bundle pipeline.

The metric-specific pages still matter, but they are supporting tools. The main product direction is the assistant plus the draft -> validate -> activate -> execute routine loop.

## Running Locally

### Prerequisites

- Python 3.12+
- Node.js 20+
- `uv`

### Backend

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`.

### Manual smoke runs

Automated backend tests already isolate the database with pytest fixtures.

Ad hoc `python`, `uv run python`, and `uvicorn` commands do not. If you run them without overrides, they will use the default local runtime DB at `storage/garmin_stats.db`.

For any manual repro or smoke run, use the isolated helper:

```bash
bash scripts/run_isolated_backend.sh
```

That script creates a temporary workspace, exports `GARMIN_DB_PATH` and `GARMIN_DATA_DIR`, prints the temp paths on startup, and removes them on exit. Set `KEEP_TMP=1` if you want to inspect the temp DB after the run.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

### Data layout

```text
data/
  garmin_health_stats/
    2026-01-14/
      *_WELLNESS.fit
      *_SKIN_TEMP.fit
      *_METRICS.fit
    2026-01-15/
      ...
```

The ingest pipeline handles the Garmin export layout and zip extraction.
Top-level `YYYY-MM-DD.zip` archives already present in `data/garmin_health_stats/` are reconciled on startup and before manual re-ingest, so days copied while the backend was down are picked up on the next boot.
Calendar-driven pages use the laptop's local date as "today". The dashboard overview surfaces a stale-data warning if Garmin data lags behind that date instead of silently treating the latest ingested day as current.
If `data/garmin_health_stats/` is missing, the backend recreates it on startup and the dashboard stays in an empty upload/ingest state until the first files arrive.

## Repo Map

This is the stable mental model, not a file-by-file inventory:

- `backend/app/infra`
  Storage, ingest, watcher, SSE/event plumbing.

- `backend/app/services`
  Deterministic analytics and assistant orchestration.

- `backend/app/routers`
  FastAPI route boundaries.

- `frontend/src/routes`
  Product pages such as dashboard, assistant, today, routines, and the parked programs/experiments placeholders.

- `frontend/src/lib`
  Typed API client, streaming helpers, shared UI helpers.

- `docs/ARCHITECTURE.md`
  Current codebase architecture notes.

- `docs/DATA_SCHEMA_DESIGN.md`
  Routine runtime design notes: assistant artifacts, cards, schedules, Today projection, and core assumptions.

- `chatgpt-architecture.md`
  Product architecture for the health assistant direction.

- `implementation-plan.md`
  Delivery phases and build sequence.

- `FINDINGS.md`
  Actual observations from the Garmin dataset and open analytical questions.

## API Surface

Key API groups exposed by the backend:

- `GET /api/cards`  
  List live card templates that can be scheduled in live routines.

- `GET /api/routines`  
  List live compiled routines.

- `GET /api/routines/{routine_id}`  
  Fetch one live routine.

- `GET /api/routines/{routine_id}/assignments`  
  Fetch recurring card placements for a live routine.

- `GET /api/routines/schedule-window?start_date=YYYY-MM-DD`  
  Resolve the next 14 days of dated schedule occurrences for schedule review.

- `GET /api/today?date=YYYY-MM-DD`  
  Build the day view from active routines, assignments, persisted date-specific overrides, and logs.

- `PUT /api/today/{date}/cards/{occurrence_key}`  
  Upsert one-tap or detailed logging for a card occurrence.

- `GET /api/assistant/artifacts`  
  List assistant-authored drafts and capability requests.

- `POST /api/assistant/artifacts`  
  Create one low-level assistant artifact draft directly.

- `POST /api/assistant/artifacts/{artifact_id}/activate`  
  Validate and compile a draft into the live runtime.

- `POST /api/assistant/artifact-bundles/preview`  
  Validate one proper bundle, report blocking issues and create/update deltas, and perform no DB writes.

- `POST /api/assistant/artifact-bundles/import`  
  Persist a valid proper bundle as validated draft artifacts only. This does not compile live runtime records.

## What Good Looks Like

If this project succeeds, it should help answer questions in a way that feels specific and grounded:

- "Your sleep and HRV both improved after three consistent low-stress evenings."
- "Meditation looks promising, but travel and lifting volume are confounding the signal."
- "Recovery is suppressed today; keep the plan lighter and skip adding another experiment."

That is the bar: not just charts, not just AI chat, but a system that combines both into something genuinely useful.

## Privacy

The `data/` directory is gitignored. Raw personal health data under `data/garmin_health_stats/` should never be committed.

Assistant features send a curated context bundle to Claude. The product direction is to keep that bundle as small, explicit, and auditable as possible.

## License

Private project. Not for distribution.
