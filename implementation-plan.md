# Health Assistant Implementation Plan

## Goal

Implement the architecture in a sequence that ships useful value early, keeps analysis deterministic, and avoids overbuilding the AI layer before the data model is ready.

## Delivery Strategy

The build should land in three product increments:

1. **Recovery assistant foundation**: profile, routines, check-ins, notes, assistant chat.
2. **Evidence-backed experimentation**: experiment tracking, effect analysis, confidence, confounders.
3. **Execution layer**: plans, daily briefing, adherence loops, then training expansion.

## Locked Decisions

- Backend owns all metric computation, experiment analysis, confidence scoring, and safety flags.
- Frontend remains display-only.
- Claude Code is an assistant runtime, not the analytics engine.
- Claude gets curated context snapshots, not broad direct DB access by default.
- All new backend timestamped fields remain in local time.
- Backend schema changes regenerate frontend API types.

## Definition of Done For Any Phase

- Backend code changes pass:
  - `cd backend && uv run ruff check`
  - `cd backend && uv run pyright app/ tests/`
  - `cd backend && uv run pytest tests/ -v`
- Frontend code changes pass:
  - `cd frontend && npm run check`
- Backend API schema changes also pass:
  - `bash scripts/generate-api-types.sh`
  - `cd frontend && npm run check`
- User-facing routes and APIs added in the phase are documented in `README.md`.

## Phase 0: Contracts And Foundation

### Goal

Create the data contracts and storage layer that every later phase depends on.

### Backend scope

- Add Pydantic models for:
  - profile
  - goals
  - routines
  - routine entries
  - daily check-ins
  - notes
  - experiments
  - experiment exposures
  - experiment reports
  - plans
  - plan items
  - assistant threads
  - assistant messages
  - assistant runs
  - context snapshots
  - evidence cards
- Extend SQLite schema in `backend/app/infra/database.py`.
- Add CRUD functions for the new tables.
- Add a backend-owned target metric registry.
- Add tests for schema init and round-trip persistence.

### Frontend scope

- No major UI yet.
- Generate API types once new models and placeholder routes exist.

### Deliverables

- Stable backend domain model for assistant features.
- Database schema ready for user-entered data.
- Metric registry contract that experiments and plans can depend on.

### Exit criteria

- New tables exist and persist round-trip data.
- API types generate cleanly.
- The metric registry maps only to real backend fields.

## Phase 1: Manual Tracking Foundation

### Goal

Make the app useful before AI by letting the user track routines, subjective state, and experiments manually.

### Backend scope

- Add routers:
  - `/api/profile`
  - `/api/routines`
  - `/api/checkins`
  - `/api/notes`
  - `/api/experiments` basic CRUD only
- Add services for:
  - routine management
  - routine entry logging
  - daily check-in logging
  - notes
  - experiment lifecycle without analysis

### Frontend scope

- Add pages:
  - `/routines`
  - `/experiments`
- Add components:
  - routine cards
  - routine log form
  - basic experiment cards
  - experiment create/edit form
  - check-in form
- Add navigation entries for new sections.

### Deliverables

- User can define routines like meditation, abs, balance, creatine.
- User can log adherence and notes per day.
- User can create experiments and link routines to them.
- User can record subjective context that Garmin data cannot provide.

### Exit criteria

- Manual tracking works with no AI dependency.
- Logged data is queryable by date, routine, and experiment.
- The new pages pass `npm run check` and feel coherent with the existing dashboard.

## Phase 2: Assistant MVP

### Goal

Ship a trustworthy recovery assistant that can answer questions about current health state using curated backend context.

### Backend scope

- Add `/api/assistant` routes:
  - thread list/create
  - message history
  - send message
- Implement:
  - `AssistantRuntime` interface
  - `ClaudeCodeRuntime` subprocess wrapper
  - context snapshot builder
  - assistant run persistence
  - per-thread model selection
- Support two response modes:
  - streaming conversational replies
  - structured JSON jobs for weekly review and daily briefing
- Extend SSE with assistant event types.

### Assistant scope

- Build prompt templates for:
  - general chat
  - daily briefing
  - weekly review
- Use compact immediate context plus richer snapshot payloads.
- Restrict normal assistant flows to read-only curated workspace inputs.

### Frontend scope

- Add `/assistant`.
- Build:
  - thread list
  - streaming message pane
  - composer
  - model selector
  - evidence chips placeholder
- Add a dedicated assistant streaming client if the existing realtime helper is too narrow.

### Deliverables

- User can ask:
  - how recovery changed this week
  - why sleep score dropped
  - what the last few days suggest
- User can maintain persistent threads.
- Weekly review and daily briefing can be generated as saved assistant artifacts.

### Exit criteria

- Assistant responses stream reliably.
- Every assistant run stores:
  - context snapshot
  - selected model
  - session ID
  - final message
- No direct raw DB querying by Claude is required for normal user chat.

## Phase 3: Evidence And Experiment Engine

### Goal

Turn routine tracking into evidence-backed experiment analysis instead of anecdotal notes.

### Backend scope

- Implement `evidence.py` and `experiment_analysis.py`.
- Build:
  - exposure matrix
  - lag windows
  - before vs during comparisons
  - rolling baseline comparisons
  - day-of-week adjusted comparisons where possible
  - confounder detection
  - confidence labels
- Add experiment report endpoints:
  - `GET /api/experiments/{id}/report`
  - `POST /api/experiments/{id}/analyze`
- Add safety/quality checks:
  - sparse data
  - overlap warnings
  - missingness warnings

### Frontend scope

- Add `/experiments/[id]`.
- Build:
  - experiment timeline
  - adherence chart/calendar
  - evidence cards
  - effect summary table
  - confounder banner
  - assistant-written interpretation section

### Deliverables

- User can see whether a routine or experiment appears linked to next-day recovery changes.
- Reports clearly separate:
  - observed effects
  - caveats
  - confounders
  - recommended next steps

### Exit criteria

- Experiment reports are generated deterministically from backend data.
- Assistant narrative is layered on top of stored evidence, not substituted for it.
- Overlapping experiments are visible in the UI and reflected in report confidence.

## Phase 4: Plans And Adherence Loop

### Goal

Turn insights into execution with plan generation, activation, and completion tracking.

### Backend scope

- Add `/api/plans`.
- Implement:
  - plan CRUD
  - plan generation from assistant structured output
  - plan activation
  - plan item completion
  - links from plans to routines and experiments
- Add assistant prompts for:
  - plan generation
  - plan revision
  - daily adjustment

### Frontend scope

- Add `/plans`.
- Add a briefing-oriented home experience or top-level `Briefing` page.
- Build:
  - plan list
  - active plan view
  - daily checklist
  - completion states
  - quick actions from assistant message to plan draft

### Deliverables

- User can turn a conversation into a concrete weekly or block plan.
- User can activate the plan and log completion.
- The app closes the loop between recommendation and adherence.

### Exit criteria

- Plans can be created manually and by assistant.
- Plan items can be completed without custom frontend computation.
- Assistant can reference plan adherence in later chats and briefings.

## Phase 5: Daily Briefing And Product Integration

### Goal

Make the system feel like a health operating system rather than separate tools.

### Backend scope

- Add briefing aggregation service combining:
  - readiness
  - active experiments
  - active plan
  - recent adherence
  - safety flags
  - top evidence cards
- Add assistant-triggered daily briefing and weekly recap jobs.

### Frontend scope

- Add a top-level `Briefing` page or rework `/` into a briefing-first dashboard.
- Surface:
  - what changed
  - what to do today
  - what to watch
  - active experiments
  - active plan items

### Deliverables

- The app opens to an actionable summary, not only charts.
- Assistant, experiments, and plans all connect through one daily command surface.

### Exit criteria

- The user can understand today's recovery state and today's plan in one page.
- Briefing is backed by the same evidence cards used in experiments and assistant chat.

## Phase 6: Training Expansion

### Goal

Expand from recovery assistant into workout-performance assistant once the data is good enough.

### Backend scope

- Add manual workout log support first:
  - workout type
  - duration
  - RPE
  - perceived quality
  - notes
- Then extend Garmin parsing for training-relevant sources:
  - `ACTIVITY` if available
  - `METRICS` message types
  - workout summaries
  - pace/load/cadence/power where decode is reliable
- Add training outcome models and reports.

### Frontend scope

- Add workout logging UI if needed before Garmin decode is ready.
- Add training impact sections to experiments and assistant flows.

### Deliverables

- User can start asking stronger questions about running and lifting.
- The app can evaluate routines against workout outcomes instead of only recovery proxies.

### Exit criteria

- Training analysis is based on real workout outcome data, not vague recovery correlation alone.
- The assistant stops relying on weak proxy signals for performance claims.

## Recommended Release Cuts

### Release 1

Ship after Phase 2.

Outcome:

- manual routine tracking
- check-ins
- experiment setup
- recovery assistant chat

This is the first usable health assistant release.

### Release 2

Ship after Phase 3.

Outcome:

- evidence-backed experiments
- confidence and confounder reporting
- experiment detail pages

This is the first real data-driven self-experiment release.

### Release 3

Ship after Phase 5.

Outcome:

- plans
- briefing
- adherence loop
- integrated assistant workflow

This is the first complete health assistant product loop.

### Release 4

Ship after Phase 6.

Outcome:

- workout-aware assistant
- stronger running and lifting guidance

## Cross-Cutting Workstreams

### Testing

- Add persistence tests for new tables and CRUD.
- Add service tests for:
  - context snapshot generation
  - evidence generation
  - experiment effect calculations
  - plan generation parsing
- Add frontend route/component checks via `svelte-check`.

### Docs

- Update `README.md` as new routes and pages ship.
- Update `FINDINGS.md` when experiment and training analysis produce new data interpretations worth preserving.

### Safety And Privacy

- Add clear UI copy that assistant requests send health context to Claude.
- Keep assistant workspaces minimal and auditable.
- Persist enough run metadata to inspect what the assistant saw and produced.

### Observability

- Log assistant run timing, failures, and parse issues.
- Add basic counters for:
  - assistant runs
  - failed runs
  - report generation failures
  - streaming disconnects

## Immediate Next Tasks

1. Create backend models and SQLite tables for the new product domain.
2. Add the target metric registry in backend code.
3. Ship profile, routines, check-ins, notes, and experiment CRUD.
4. Build the assistant runtime wrapper and thread/message persistence.
5. Add `/assistant`, `/routines`, and `/experiments` pages.

## Delivery Goal Summary

- **Phase 0-1**: make manual health tracking real.
- **Phase 2**: make the assistant useful.
- **Phase 3**: make the assistant evidence-backed.
- **Phase 4-5**: make the assistant actionable and habit-forming.
- **Phase 6**: make the assistant performance-aware.
