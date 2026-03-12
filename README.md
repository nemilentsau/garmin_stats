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

A place to log behaviors that Garmin does not know about:

- meditation
- abs work
- balance drills
- supplements
- meal timing
- mobility
- sleep routines

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
- manual tracking for routines, check-ins, notes, and experiments
- assistant MVP with persisted threads and streamed replies

### Not done yet

- evidence-backed experiment engine
- plan generation and adherence loop
- strong training-performance attribution
- serious running/lifting coaching

So the app is already useful as a **personal recovery assistant**. It is not yet a complete performance coach.

## How It Works

1. Garmin exports are dropped into `data/YYYY-MM-DD/*.fit`.
2. The backend ingests those files and stores normalized data in local SQLite.
3. Backend services compute daily metrics, insights, and assistant context snapshots.
4. The assistant runtime sends a curated snapshot to Claude Code and streams the reply back.
5. Threads, messages, runs, and snapshots are stored so the assistant has memory and an audit trail.

## Main App Areas

- `/`  
  Recovery dashboard and metric exploration.

- `/assistant`  
  Chat with the recovery assistant, keep threads, ask for a daily briefing or weekly review.

- `/routines`  
  Define repeatable behaviors and log adherence, check-ins, and notes.

- `/experiments`  
  Define experiments, link routines, and choose target metrics.

The metric-specific pages still matter, but they are supporting tools. The main product direction is the assistant plus the routines/experiments loop.

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
  2026-01-14/
    *_WELLNESS.fit
    *_SKIN_TEMP.fit
    *_METRICS.fit
  2026-01-15/
    ...
```

The ingest pipeline handles the Garmin export layout and zip extraction.

## Repo Map

This is the stable mental model, not a file-by-file inventory:

- `backend/app/infra`
  Storage, ingest, watcher, SSE/event plumbing.

- `backend/app/services`
  Deterministic analytics and assistant orchestration.

- `backend/app/routers`
  FastAPI route boundaries.

- `frontend/src/routes`
  Product pages such as dashboard, assistant, routines, and experiments.

- `frontend/src/lib`
  Typed API client, streaming helpers, shared UI helpers.

- `docs/ARCHITECTURE.md`
  Current codebase architecture notes.

- `chatgpt-architecture.md`
  Product architecture for the health assistant direction.

- `implementation-plan.md`
  Delivery phases and build sequence.

- `FINDINGS.md`
  Actual observations from the Garmin dataset and open analytical questions.

## What Good Looks Like

If this project succeeds, it should help answer questions in a way that feels specific and grounded:

- "Your sleep and HRV both improved after three consistent low-stress evenings."
- "Meditation looks promising, but travel and lifting volume are confounding the signal."
- "Recovery is suppressed today; keep the plan lighter and skip adding another experiment."

That is the bar: not just charts, not just AI chat, but a system that combines both into something genuinely useful.

## Privacy

The `data/` directory is gitignored. Raw personal health data should never be committed.

Assistant features send a curated context bundle to Claude. The product direction is to keep that bundle as small, explicit, and auditable as possible.

## License

Private project. Not for distribution.
