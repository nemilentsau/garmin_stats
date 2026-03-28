# AI Health Assistant Architecture Plan

## Purpose

Turn the current Garmin stats app from a metrics dashboard into a personal health assistant that can:

- answer questions about recent health and recovery patterns
- generate daily and weekly plans
- track routines such as mindfulness, nutrition protocols, mobility, balance work, and training blocks
- run messy real-life experiments with overlapping interventions
- explain recommendations using your own data instead of generic wellness advice

The assistant runtime will use Claude Code programmatically, but the app architecture should stay vendor-agnostic. The product layer should depend on an `AssistantRuntime` interface, with `ClaudeCodeRuntime` as the first implementation.

## Product Goals

1. Keep deterministic analysis in the backend.
2. Use the LLM for synthesis, conversation, prioritization, and plan writing.
3. Treat routines and experiments as first-class product objects, not free-text notes.
4. Make evidence visible: every recommendation should point back to observed data, confidence, and caveats.
5. Support messy overlap between interventions instead of assuming perfect one-variable-at-a-time experiments.

## Non-Goals For V1

- medical diagnosis
- automatic causal claims from weak observational data
- full nutrition tracking with food database and macro scanner
- frontend-side statistical computation
- giving the LLM direct write access to the repo or raw data store for normal coaching flows

## Current State

### Existing strengths

- FastAPI backend with clear service and router boundaries
- SQLite persistence already in place
- backend-generated daily aggregates and insight endpoints
- SSE event bus for realtime updates
- Svelte frontend with dashboard and metric detail pages
- strong Garmin recovery coverage already exists: HR, resting HR, stress, body battery, HRV, sleep, skin temp

### Current gaps

- no conversation model
- no routines or habit logging model
- no experiment model
- no plan storage or activation flow
- no assistant orchestration runtime
- no evidence-pack abstraction for LLM prompts
- no audit trail showing what data the assistant used
- training and workout performance data are not mature enough yet for serious running/lifting guidance

## Key Product Insight

The current app is already capable of becoming a strong recovery assistant. It is not yet a complete workout-performance assistant.

Reason:

- recovery and wellness metrics are already parsed and modeled
- workout-specific performance signals are still weak
- `WELLNESS` files expose generic activity samples, but detailed `METRICS` and activity-performance decoding is still incomplete
- user examples like "how does my abs routine affect running?" and "how does nutrition affect lifting?" require better training outcome data than the app currently stores

So the roadmap should split into:

1. recovery-first assistant now
2. workout-performance expansion after training ingestion catches up

## Architecture Principles

### 1. Backend owns truth

The backend computes all derived metrics, experiment effects, confidence levels, lag windows, and evidence cards. The assistant is never the source of truth for numeric analytics.

### 2. Frontend stays display-only

The frontend renders chat, plans, cards, timelines, and charts. It does not compute statistics, correlations, moving averages, or experiment results.

### 3. The LLM works from curated context, not raw system access

Claude Code should receive a generated evidence bundle plus a task prompt. Avoid making it infer core product data structures by crawling the whole app or database.

### 4. Free chat and structured jobs are different modes

- conversational mode: open-ended Q&A with persistent session memory
- task mode: deterministic schemas for weekly reviews, plan drafts, experiment summaries

### 5. Overlap is expected, so confidence must be explicit

The system should say:

- likely signal
- possible signal, heavy confounding
- not enough data

It should not say:

- X caused Y

unless the evidence is unusually strong.

### 6. Local-first product, cloud-aware privacy

The app remains locally hosted, but Claude Code sends prompt context to Anthropic. The architecture must make that explicit and minimize the payload.

## Target System Overview

```text
Garmin FIT + manual logs + user notes + goals
                |
                v
      Deterministic backend analysis
  daily metrics | routine adherence | experiment effects
  evidence cards | safety flags | plan inputs
                |
                v
        Assistant orchestration layer
 context snapshots | prompt templates | Claude runtime
 sessions | streaming | structured outputs | audit trail
                |
                v
              Frontend
 briefing | assistant chat | routines | experiments | plans | metrics
```

## Domain Model

### 1. User Profile

Single-user app, but still model profile explicitly.

Fields:

- name
- birth year or age range
- sex if the user wants it included
- height, weight
- primary goals
- constraints and injuries
- available equipment
- default weekly schedule
- sleep constraints
- nutrition preferences or restrictions
- coaching style preferences

### 2. Routine

A routine is a reusable behavior or protocol.

Examples:

- 10-minute meditation
- abs circuit
- single-leg balance work
- creatine daily
- high-carb pre-run breakfast
- mobility before bed

Suggested fields:

- `id`
- `name`
- `category` (`mindfulness`, `nutrition`, `strength`, `mobility`, `sleep`, `recovery`, `custom`)
- `description`
- `default_unit` (`boolean`, `minutes`, `sets`, `grams`, `rating`)
- `target_frequency`
- `default_time_of_day`
- `tags`
- `status`

### 3. Routine Entry

Concrete adherence log for a date or timestamp.

Suggested fields:

- `routine_id`
- `timestamp_local`
- `date`
- `value_numeric`
- `value_text`
- `completion_state`
- `source` (`manual`, `generated_plan`, `imported`)
- `notes`

### 4. Experiment

A time-bounded question about whether one or more interventions seem to affect one or more outcomes.

Examples:

- meditation before bed -> HRV and sleep score
- abs + balance routine -> running recovery markers
- protein target + creatine -> lifting recovery and body battery

Suggested fields:

- `id`
- `name`
- `status` (`draft`, `active`, `paused`, `completed`, `abandoned`)
- `start_date`
- `end_date`
- `goal`
- `hypothesis`
- `linked_routine_ids`
- `outcome_metrics`
- `expected_lag_days`
- `confounder_notes`
- `priority`

### 5. Experiment Exposure

Daily or timestamped record of whether the intervention actually happened.

This is separate from the experiment object because real life is messy.

Suggested fields:

- `experiment_id`
- `date`
- `exposure_score`
- `adherence_state`
- `linked_routine_entry_ids`
- `notes`

### 6. Daily Check-In

Garmin alone is not enough. Add subjective data.

Suggested fields:

- `date`
- `energy`
- `mood`
- `motivation`
- `soreness`
- `stress_subjective`
- `sleep_quality_subjective`
- `workload_subjective`
- `illness_flag`
- `travel_flag`
- `alcohol_flag`
- `notes`

### 7. Plan

A plan is a generated or manual strategy composed of routines and tasks.

Examples:

- daily recovery plan
- 7-day training adjustment plan
- 4-week mindfulness block
- nutrition experiment plan

Suggested fields:

- `id`
- `title`
- `scope` (`daily`, `weekly`, `block`)
- `status` (`draft`, `active`, `completed`, `archived`)
- `source` (`assistant`, `manual`)
- `goal`
- `markdown_body`
- `structured_outline_json`
- `linked_experiment_ids`

### 8. Plan Item

Structured actionable item inside a plan.

Suggested fields:

- `plan_id`
- `date`
- `time_block`
- `title`
- `instructions`
- `linked_routine_id`
- `completion_state`
- `completion_notes`

### 9. Assistant Thread

Conversation container.

Suggested fields:

- `id`
- `title`
- `mode` (`general`, `recovery`, `nutrition`, `training`, `experiment`)
- `model` (`sonnet`, `opus`, or future runtime label)
- `claude_session_id`
- `last_context_snapshot_id`
- `status`
- `last_message_at`

### 10. Assistant Message

Suggested fields:

- `thread_id`
- `role` (`user`, `assistant`, `system`)
- `content_markdown`
- `structured_payload_json`
- `evidence_refs_json`
- `created_at`

### 11. Assistant Run

Audit trail for each Claude invocation.

Suggested fields:

- `id`
- `thread_id`
- `task_type`
- `status`
- `context_snapshot_id`
- `claude_session_id`
- `command_json`
- `stdout_path`
- `stderr_path`
- `usage_json`
- `started_at`
- `finished_at`

### 12. Context Snapshot

Persist the exact bundle that the assistant saw.

Suggested fields:

- `id`
- `date_window_start`
- `date_window_end`
- `snapshot_json`
- `summary_markdown`
- `created_at`

### 13. Evidence Card

Deterministic backend summary object used both by UI and by Claude prompts.

Suggested fields:

- `id`
- `kind` (`trend`, `effect`, `correlation`, `warning`, `confounder`, `adherence`)
- `title`
- `summary`
- `metric`
- `window`
- `sample_count`
- `confidence`
- `caveats`
- `payload_json`

## Backend Architecture

### Persistence Strategy

Keep the current Garmin tables as they are. Add normalized tables for assistant-domain data.

### Keep existing tables

- `wellness_data`
- `sleep_data`
- `hrv_data`
- `skin_temp_data`
- `daily_metrics`
- `ingest_meta`

### Add new tables

- `user_profile`
- `goals`
- `routines`
- `routine_entries`
- `daily_checkins`
- `notes`
- `experiments`
- `experiment_exposures`
- `experiment_reports`
- `plans`
- `plan_items`
- `assistant_threads`
- `assistant_messages`
- `assistant_runs`
- `context_snapshots`
- `assistant_artifacts`

Use SQLite JSON columns where flexibility helps, but do not store everything as one giant blob. Routines, entries, plans, and threads need relational querying.

### Backend Module Plan

Suggested additions under `backend/app/`:

```text
app/
  routers/
    assistant.py
    routines.py
    experiments.py
    plans.py
    profile.py
    checkins.py
  services/
    assistant_runtime.py
    assistant_service.py
    assistant_context.py
    prompt_builder.py
    evidence.py
    experiments.py
    experiment_analysis.py
    routines.py
    plans.py
    profile.py
    checkins.py
    safety.py
  infra/
    assistant_store.py
    assistant_workspace.py
```

### `assistant_runtime.py`

Responsibility:

- wrap Claude Code CLI calls
- manage subprocess execution
- parse structured output
- parse stream output
- capture exit codes, errors, stderr, usage metadata
- persist `session_id`

This module should expose an interface like:

- `run_task(...)`
- `stream_thread_reply(...)`
- `resume_thread(...)`

Do not leak CLI details into routers.

### `assistant_context.py`

Responsibility:

- build the exact data bundle for the assistant
- choose date windows
- include only relevant routines, experiments, notes, and metrics
- emit a compact "immediate context" summary plus a richer evidence bundle
- emit both machine-readable JSON and readable Markdown summary

The context builder is the main quality lever. Bad context will produce generic answers even with a strong model.

### `evidence.py`

Responsibility:

- convert raw metrics and logs into `EvidenceCard` objects
- compute confidence and caveats
- produce reusable cards for UI and assistant prompts

Examples:

- "Nightly HRV is 8.2 ms below your 21-day baseline over the last 3 days"
- "Meditation days are associated with +5.4 HRV next-morning, but only across 6 observations"
- "Abs routine overlaps with harder run days, so effect attribution is weak"

### `experiment_analysis.py`

Responsibility:

- build exposure matrix from routine entries and experiment definitions
- compare outcome windows
- run lag-based comparisons
- score overlap/confounding
- output report objects for experiment pages and assistant use

### `safety.py`

Responsibility:

- deterministic health flags
- threshold-based escalation logic
- "talk to a clinician" or "pay attention" banners when patterns are concerning

Examples:

- repeated low SpO2 episodes
- sustained resting HR elevation
- multi-day recovery collapse

This should be rules-based, not LLM-only.

### Project-specific implementation rules

- New backend timestamped fields must stay in local time to match the current ingest model.
- New backend models and routes remain the source of truth for frontend types.
- After backend schema changes, regenerate `frontend/src/lib/api-types.ts` via `bash scripts/generate-api-types.sh`.
- New analytics logic belongs in backend services and should be covered with backend tests.

## Claude Code Runtime Design

### Why Claude Code fits

The app needs:

- multi-turn conversation
- structured outputs for plans and reports
- streaming for chat UX
- tool-based context reading

The Claude Code CLI already supports these through:

- `claude -p`
- `--resume` or `--continue`
- `--output-format json`
- `--output-format stream-json`
- `--json-schema`
- `--allowedTools`

So V1 should use the CLI through subprocess, not add a separate SDK dependency unless we later need deeper callback control.

### Runtime modes

#### 1. Conversational mode

Use for `/assistant` chat.

Behavior:

- keep one Claude session per thread
- store returned `session_id`
- resume with `--resume`
- use streaming output for responsive UI

Suggested command shape:

```bash
claude -p "<prompt>" \
  --resume "<session_id>" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages \
  --allowedTools "Read"
```

#### 2. Structured task mode

Use for:

- weekly review
- experiment summary
- plan generation
- plan revision
- routine suggestions

Behavior:

- prefer fresh runs from a canonical context snapshot
- require JSON schema output
- backend persists the result as typed objects

Suggested command shape:

```bash
claude -p "<prompt>" \
  --output-format json \
  --json-schema "<schema>" \
  --allowedTools "Read"
```

#### 3. Hybrid review mode

Use when the user wants a narrative plus saved artifact.

Pattern:

1. generate structured report with schema
2. optionally ask Claude for companion Markdown copy from the same evidence bundle

### Claude workspace isolation

Do not run assistant jobs from the repo root by default.

Instead:

1. create a per-run workspace under something like `storage/assistant/workspaces/<run_id>/`
2. write:
   - `context.json`
   - `context.md`
   - `task.md`
   - optional `schema.json`
3. set the Claude working directory to that workspace
4. only allow read-only tools for normal assistant flows

Benefits:

- smaller prompt surface
- less accidental repo crawling
- cleaner privacy boundary
- reproducible runs
- avoids inheriting repo-oriented coding prompts and skills into end-user health conversations

### Prompt architecture

Store prompt templates in code, not inline in routers.

Suggested prompt families:

- `general_chat`
- `daily_briefing`
- `weekly_review`
- `experiment_analysis`
- `plan_generation`
- `routine_recommendation`
- `safety_explanation`

Prompt rules:

- distinguish observation vs hypothesis vs recommendation
- always mention confidence and caveats
- never invent unavailable metrics
- cite evidence card IDs in major claims
- ask clarifying questions when necessary
- do not present medical diagnosis
- default to the smallest effective change, not lifestyle maximalism

### Output schemas

Define strict JSON schemas for structured jobs.

#### Example: plan generation result

- `title`
- `goal`
- `summary`
- `rationale`
- `days`
- `linked_routines`
- `linked_experiments`
- `checkpoints`
- `warnings`

#### Example: experiment review result

- `summary`
- `top_signals`
- `possible_effects`
- `confounders`
- `confidence`
- `next_best_action`
- `follow_up_questions`

#### Example: chat metadata

Even if the user sees plain text, persist structured metadata:

- `evidence_refs`
- `suggested_actions`
- `plan_candidate`
- `follow_up_questions`
- `risk_flags`

### Session and memory management

Persistent thread memory matters, but do not rely on it forever.

Strategy:

1. store full local transcript in SQLite
2. store Claude `session_id`
3. periodically create a local thread summary
4. if a thread becomes too long or the session breaks, roll to a new session using:
   - thread summary
   - latest context snapshot
   - most recent messages

This avoids silent dependency on a long-lived external session.

### Model selection

Allow model choice per thread, but treat it as a runtime preference rather than a product primitive.

Suggested rule:

- `sonnet` for daily chat, quick follow-ups, and lightweight plan revisions
- `opus` for deeper experiment interpretation or long-form plan generation

Persist the selected model on the thread and pass it through the runtime layer. Do not branch product logic on model choice.

## API Plan

### Profile and setup

- `GET /api/profile`
- `PUT /api/profile`
- `GET /api/goals`
- `POST /api/goals`

### Routines

- `GET /api/routines`
- `POST /api/routines`
- `PUT /api/routines/{id}`
- `POST /api/routines/{id}/entries`
- `GET /api/routines/{id}/entries`
- `GET /api/routines/{id}/impact`

### Check-ins and notes

- `GET /api/checkins`
- `POST /api/checkins`
- `GET /api/notes`
- `POST /api/notes`

### Experiments

- `GET /api/experiments`
- `POST /api/experiments`
- `PUT /api/experiments/{id}`
- `POST /api/experiments/{id}/start`
- `POST /api/experiments/{id}/pause`
- `POST /api/experiments/{id}/complete`
- `GET /api/experiments/{id}/report`
- `POST /api/experiments/{id}/analyze`

### Plans

- `GET /api/plans`
- `POST /api/plans`
- `GET /api/plans/{id}`
- `PUT /api/plans/{id}`
- `POST /api/plans/{id}/activate`
- `POST /api/plans/{id}/items/{item_id}/complete`

### Assistant

- `GET /api/assistant/threads`
- `POST /api/assistant/threads`
- `GET /api/assistant/threads/{id}`
- `POST /api/assistant/threads/{id}/messages`
- `GET /api/assistant/threads/{id}/messages`
- `POST /api/assistant/threads/{id}/plan`
- `POST /api/assistant/weekly-review`
- `POST /api/assistant/daily-briefing`

### Realtime events

Extend the current SSE event system with namespaced assistant events:

- `assistant_run_started`
- `assistant_stream_delta`
- `assistant_run_completed`
- `assistant_run_failed`
- `plan_updated`
- `experiment_report_updated`
- `routine_updated`

## Target Metric Registry

Experiments need a standardized metric registry so target selection, analysis, and UI labels all point at the same backend-owned fields.

Suggested initial registry:

| Key | Maps to | Unit |
|-----|---------|------|
| `resting_hr` | `heart_rate.resting` | bpm |
| `hrv_nightly` | `hrv.nightly_avg` | ms |
| `hrv_weekly` | `hrv.weekly_avg` | ms |
| `sleep_score` | `sleep.score` | pts |
| `deep_sleep_score` | `sleep.deep_score` | pts |
| `stress_avg` | `stress.avg` | 0-100 |
| `body_battery_min` | `body_battery.min` | 0-100 |
| `body_battery_max` | `body_battery.max` | 0-100 |
| `spo2_avg` | `spo2.avg` | % |
| `skin_temp_deviation` | `skin_temp.deviation` | C |

Keep this registry in backend code so experiments and plans cannot target arbitrary strings.

## Experiment Analytics Strategy

### Core problem

The user will often run overlapping routines and experiments. That means classic clean A/B attribution is unrealistic.

The system should therefore optimize for:

- useful directional evidence
- visibility into confounding
- repeatable personal learning

not for fake causal certainty.

### Proposed analytics model

#### 1. Exposure matrix

For each day, compute a matrix of routine and experiment exposures:

- completed or not
- dose or duration
- time of day
- current streak
- recent rolling exposure

#### 2. Outcome matrix

For each day, build outcome measures from backend-owned data:

- nightly HRV
- resting HR
- sleep score
- stress average
- body battery metrics
- respiration
- skin temp deviation
- subjective check-ins

Later, after workout ingestion improves:

- run duration, pace, HR drift, training load
- lifting volume and session quality
- workout completion quality

#### 3. Lag windows

For each intervention-outcome pair, compute comparisons at:

- same day
- next morning
- 2-day lag
- 3-day rolling window
- 7-day rolling window

Different interventions act on different timescales. Meditation may affect next-morning HRV. Strength blocks may affect recovery over several days.

#### 4. Comparison methods

Start simple and interpretable:

- exposure days vs non-exposure days
- before/after experiment start
- rolling baseline deltas
- day-of-week adjusted comparisons
- matched recent-window comparisons where possible

Do not start with black-box ML.

#### 5. Confidence scoring

Each reported effect should include:

- sample count
- overlap count
- missingness impact
- outcome stability
- direction consistency
- confidence label

Suggested confidence labels:

- `insufficient`
- `weak`
- `moderate`
- `strong`

#### 6. Confounder visibility

Always show potential confounders:

- other active experiments
- illness/travel/alcohol flags
- unusually hard training days
- low adherence consistency
- sparse data

### Immediate analytics focus

Given current data maturity, prioritize:

- sleep and recovery experiments
- mindfulness and stress experiments
- daily routine adherence vs next-day recovery
- plan compliance vs recovery trend

Do not over-promise running or lifting outcome analysis until training ingestion improves.

### Training Data Expansion Track

This is a separate but necessary track for serious workout advice.

#### Why it matters

User questions such as:

- "Did my abs routine improve running?"
- "Did nutrition help lifting?"

need actual workout outcome data, not only recovery proxies.

#### Planned backend expansion

Add training-oriented parsing and storage for:

- `ACTIVITY` files if available
- `METRICS` message types
- workout summaries
- pace, duration, load, power, cadence, VO2-related signals where decode is reliable

#### Stopgap before that work lands

Use manual or semi-manual workout logs:

- workout performed
- session type
- perceived quality
- RPE
- notes

That gives the assistant something useful before deep Garmin workout parsing is done.

## Frontend Architecture

### Information architecture

Keep the existing metric pages, but reposition them as the evidence layer rather than the whole product.

Suggested top-level navigation:

- `Briefing`
- `Assistant`
- `Routines`
- `Experiments`
- `Plans`
- `Metrics`

Suggested new route structure:

- `/assistant`
- `/routines`
- `/experiments`
- `/experiments/[id]`
- `/plans`

#### Briefing page

Purpose:

- daily command center
- show readiness, active routines, active experiments, top evidence cards, and a quick ask box

Key blocks:

- headline readiness and recovery summary
- "what changed recently" cards
- active experiment status
- adherence snapshot
- assistant prompt composer
- suggested next action

#### Assistant page

Purpose:

- main conversational experience
- thread list plus message view
- ability to turn a chat into a plan or experiment draft

Key blocks:

- thread rail
- streaming message pane
- evidence chips per message
- quick actions:
  - "make weekly plan"
  - "create experiment"
  - "explain this trend"
  - "compare last 14 days to baseline"

#### Routines page

Purpose:

- define reusable behaviors and log adherence

Key blocks:

- routine library cards
- streak and adherence calendar
- quick logging controls
- linked effects panel
- routine-specific notes

#### Experiments page

Purpose:

- define and inspect N-of-1 experiments

Key blocks:

- experiment board by status
- experiment detail page
- linked routines
- target outcomes
- effect cards
- confounder warnings
- assistant-written interpretation

#### Plans page

Purpose:

- generated and manual plans
- activate, edit, complete, review

Key blocks:

- plan list
- current active plan
- daily checklist
- completion history
- linked experiments and routines

#### Metrics pages

Keep current detailed metric routes and add cross-links back into:

- routine impacts
- experiment evidence
- assistant citations

The metric pages become the drill-down evidence lab.

### Frontend component plan

Suggested reusable components:

- `AssistantComposer.svelte`
- `AssistantMessage.svelte`
- `EvidenceChip.svelte`
- `EvidenceCard.svelte`
- `RoutineCard.svelte`
- `RoutineLogSheet.svelte`
- `AdherenceCalendar.svelte`
- `ExperimentCard.svelte`
- `ExperimentEffectTable.svelte`
- `ConfounderBanner.svelte`
- `PlanCard.svelte`
- `PlanChecklist.svelte`
- `QuickActionBar.svelte`
- `AssistantStreamClient.ts`

### Frontend data flow

- use backend REST endpoints for CRUD and page loads
- use SSE for assistant streaming and async job updates
- keep frontend state thin
- no statistical transforms in Svelte components

Implementation note:

- the current `sse.ts` handles GET-based event streams
- assistant chat may need a dedicated POST-then-stream helper so message submission and streamed reply stay in one flow
- keep that helper separate from the existing data-update listener

### Frontend UX direction

Follow current project rules:

- keep the strong metric color system
- preserve summary-first information hierarchy
- avoid giant headers and scroll-heavy dead space
- show evidence and caveats close to recommendations
- use equal-weight grids where cross-metric scanning matters

The new product surface should feel like:

- recovery command center
- experiment notebook
- coach conversation workspace

not like:

- generic chatbot page pasted onto a dashboard

## Backend and Frontend Integration Flow

### Chat reply flow

1. frontend sends user message
2. backend stores it
3. backend builds context snapshot
4. backend starts Claude run
5. Claude output streams through SSE
6. backend stores final assistant message and metadata
7. frontend updates thread and evidence chips

### Experiment analysis flow

1. user creates or updates experiment
2. backend recomputes exposure and outcome comparisons
3. backend stores report and evidence cards
4. optional Claude structured summary is generated
5. frontend renders report with deterministic metrics first and assistant narrative second

### Plan generation flow

1. user asks for a plan
2. backend builds structured context:
   - goals
   - active experiments
   - latest recovery state
   - schedule constraints
3. Claude returns schema-valid plan JSON
4. backend persists `plan` and `plan_items`
5. frontend shows draft for activation or edit

## Suggested Implementation Phases

### Phase 1: Foundation

Ship:

- profile
- routines
- routine entries
- daily check-ins
- notes
- basic experiments CRUD

Goal:

create the non-Garmin data model first so the assistant has something real to reason about.
Manual routine and experiment tracking should already be useful before any AI interpretation ships.

### Phase 2: Assistant runtime

Ship:

- assistant threads and messages
- Claude Code subprocess wrapper
- context snapshots
- structured weekly review
- basic assistant chat

Goal:

get conversational coaching working against current recovery metrics.

### Phase 3: Evidence and experiment engine

Ship:

- evidence cards
- experiment exposure matrix
- lag comparisons
- confidence scoring
- experiment reports

Goal:

make the assistant evidence-backed instead of generic.

### Phase 4: Plans

Ship:

- plan generation
- plan activation
- checklist completion
- assistant-to-plan conversion

Goal:

turn advice into execution.

### Phase 5: Training performance expansion

Ship:

- training and workout parsing upgrades
- run/lift outcome models
- routine-to-performance analyses

Goal:

support the user's running and lifting questions with stronger signals.

## Risks and Mitigations

### Risk: assistant becomes generic

Mitigation:

- strong context builder
- evidence cards
- structured prompts
- backend-owned analytics

### Risk: fake causality from overlapping experiments

Mitigation:

- explicit confidence labels
- confounder warnings
- overlap-aware reporting
- conservative prompt rules

### Risk: training advice outpaces actual training data

Mitigation:

- split recovery assistant from performance assistant
- add manual workout quality logs first
- treat `METRICS` decoding as a real roadmap item, not an optional polish task

### Risk: privacy concerns

Mitigation:

- opt-in assistant feature
- minimal context payloads
- snapshot auditing
- clear UX copy that Claude Code sends data to an external service

### Risk: session drift in long conversations

Mitigation:

- store local summaries
- roll sessions when needed
- prefer fresh structured runs for important artifacts

## Concrete Recommended Next Build Order

1. Add assistant-domain tables and Pydantic models.
2. Add profile, routines, routine entries, check-ins, and notes APIs.
3. Add experiment CRUD without advanced analytics first.
4. Build `AssistantRuntime` plus `ClaudeCodeRuntime`.
5. Add `ContextSnapshot` and `EvidenceCard` generation.
6. Ship `/assistant` with one-thread chat and weekly review.
7. Ship `/routines` and `/experiments` pages.
8. Add plan generation and activation.
9. Start separate `garmin-data` discovery work for workout metrics.

## Final Recommendation

Build this as a three-engine product:

1. deterministic health data engine
2. assistant orchestration engine
3. routines and experiments product layer

That separation is the key architectural decision.

If the LLM owns the analytics, the app will feel clever but unreliable.
If the backend owns the evidence and Claude owns synthesis, conversation, and plan writing, the app can become a genuinely useful personal health assistant.
