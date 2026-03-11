# Garmin Health Assistant — Architecture Overview

## Vision

Transform the Garmin Stats app from a passive health data dashboard into an **AI-powered health assistant** that helps the user understand their data, run self-experiments, and make data-driven health decisions.

Three new pillars extend the existing analytics platform:

1. **AI Assistant** — Conversational interface grounded in real health data
2. **Experiment Tracker** — Track routines (mindfulness, nutrition, training) and measure their effect on health metrics
3. **Health Plans** — Goal-oriented programs, AI-assisted, linked to experiments

---

## Current State

| Layer | What exists today |
|-------|------------------|
| **Data pipeline** | FIT file ingestion → SQLite (wellness, sleep, HRV, skin temp, daily metrics) |
| **Backend** | FastAPI with 12 routers, 11 services, in-memory cache, SSE event bus |
| **Frontend** | SvelteKit with 9 pages (Dashboard + 8 metric pages), Chart.js, real-time SSE |
| **Metrics** | Heart rate, HRV, sleep, stress, body battery, SpO2, respiration, skin temp |

The app is display-only today. All computation happens on the backend. The frontend renders what the API provides.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     FRONTEND (SvelteKit)                      │
│                                                               │
│  EXISTING                          NEW                        │
│  ┌────────────┐                   ┌────────────────────────┐  │
│  │ Dashboard  │                   │ AI Assistant (chat UI) │  │
│  │ HR / HRV   │                   │ Experiments hub + detail│  │
│  │ Sleep      │                   │ Plans page             │  │
│  │ Stress     │                   └──────────┬─────────────┘  │
│  │ Body Batt. │                              │                │
│  │ Resp / SpO2│                    HTTP + SSE streaming       │
│  │ Skin Temp  │                              │                │
│  └────────────┘                              │                │
└──────────────────────────────────┬───────────┘────────────────┘
                                   │
┌──────────────────────────────────▼────────────────────────────┐
│                     BACKEND (FastAPI)                          │
│                                                               │
│  EXISTING SERVICES              NEW SERVICES                  │
│  ┌──────────────────┐          ┌───────────────────────────┐  │
│  │ dashboard        │          │ ai_chat                   │  │
│  │ heart_rate_*     │          │  → spawns Claude Code CLI │  │
│  │ hrv_analysis     │          │  → manages sessions       │  │
│  │ sleep_analysis   │          │  → builds data context    │  │
│  │ stress_analysis  │          │  → streams responses      │  │
│  │ body_battery_*   │          │                           │  │
│  │ period_windows   │          │ experiments               │  │
│  └──────────────────┘          │  → CRUD + observations    │  │
│                                │  → correlation engine     │  │
│  EXISTING INFRA                │  → before/during analysis │  │
│  ┌──────────────────┐          │                           │  │
│  │ SQLite + WAL     │          │ plans                     │  │
│  │ In-memory cache  │          │  → CRUD                   │  │
│  │ SSE event bus    │          │  → AI-assisted generation │  │
│  │ File watcher     │          └───────────┬───────────────┘  │
│  └──────────────────┘                      │                  │
└────────────────────────────────────────────┼──────────────────┘
                                             │
                                    subprocess (stdin/stdout)
                                             │
┌────────────────────────────────────────────▼──────────────────┐
│                    CLAUDE CODE CLI                             │
│                                                               │
│  Invoked via: claude -p "user message"                        │
│  Session continuity: --resume <session_id>                    │
│  Data context: --append-system-prompt <health summary>        │
│  Streaming: --output-format stream-json                       │
│  Data access: --allowedTools "Read,Bash(sqlite3 *)"           │
│  Model choice: --model sonnet | opus (user picks per convo)   │
│                                                               │
│  Claude can:                                                  │
│  - Read any file in the project                               │
│  - Query SQLite directly for ad-hoc health data analysis      │
│  - Provide grounded health advice citing actual numbers        │
│  - Analyze experiment results with statistical reasoning       │
└───────────────────────────────────────────────────────────────┘
```

---

## Pillar 1: AI Assistant

### What it does
A conversational interface where the user talks with Claude about their health data. Claude has direct access to the SQLite database and can query it on the fly.

### How it works

**Data context — hybrid approach:**
- **Immediate context (system prompt):** A compact summary of the last 7 days of key vitals (resting HR, HRV, sleep score, stress, body battery), plus any active experiments. Injected via `--append-system-prompt`. This gives Claude instant awareness without any tool calls (~500 tokens).
- **Deep context (tool access):** Claude is allowed to run `sqlite3` queries against the health database. The system prompt includes the DB path and table schemas. This lets Claude do ad-hoc analysis: "Show me all days where HRV dropped below 40 and stress was above 60."

**Session management:**
- Each conversation maps to a Claude Code session via `--resume <session_id>`
- The backend stores the mapping: conversation ID → Claude session ID
- Multi-turn conversations maintain full context across messages
- Messages are also stored in our own SQLite for UI display (independent of Claude's session storage)

**Streaming:**
- Backend spawns `claude -p --output-format stream-json`
- Reads stdout line by line
- Forwards chunks as Server-Sent Events to the frontend
- Frontend renders progressively as tokens arrive

**Model selection:**
- User picks per conversation: Sonnet (fast, daily chat) or Opus (deep analysis)
- Stored on the conversation record, passed via `--model` flag

### Example interactions
- "How has my HRV trended over the last month? Any concerning patterns?"
- "I've been doing morning meditation for 2 weeks. Is it affecting my stress levels?"
- "Design a 4-week progressive running plan based on my recovery data."
- "My sleep score dropped last week. What might be causing it?"

---

## Pillar 2: Experiment Tracker

### What it does
Track self-experiments — interventions the user applies to their life — and measure how they affect health metrics over time.

### Experiment types

| Type | Examples | Typical target metrics |
|------|----------|----------------------|
| **Mindfulness** | Morning meditation, breathwork, journaling | HRV, stress, sleep score |
| **Nutrition** | High-protein diet, intermittent fasting, supplements | Body battery, recovery, resting HR |
| **Training** | Abs routine, single-leg balance, running plan, yoga | Resting HR, HRV, sleep, stress |
| **Custom** | Cold showers, blue light blocking, caffeine cutoff | User-defined |

### Data model

**Experiment** — The intervention being tested
- Identity: name, type, description, hypothesis
- Timeline: start date, end date (null = ongoing), status (active / paused / completed / abandoned)
- Target metrics: which health parameters to watch (selected from standardized metric keys that map to daily aggregate fields)

**Observation** — Daily log entry within an experiment
- Date, free-text notes, adherence score (0-100)
- Type-specific structured data (e.g., meditation duration, workout RPE, meal description)
- One observation per experiment per day

**Snapshot** — Periodic correlation analysis
- Baseline period: metric averages from the 14 days before experiment start
- During period: metric averages from experiment start to snapshot date
- Computed deltas: absolute and percentage change per target metric
- AI interpretation: Claude's analysis of the snapshot (optional, triggered on demand)

### Correlation engine

The correlation engine is deterministic backend computation (not AI-generated):

1. Define baseline window (default: 14 days before experiment start)
2. Define "during" window (experiment start to current date or end date)
3. For each target metric, compute summary statistics for both periods
4. Calculate absolute and percentage change
5. Flag overlapping experiments that might confound results

The AI layer interprets these results — it provides the narrative ("Your HRV improved by 12% since starting meditation, but you also started a new running program 5 days later which may contribute").

### The overlap problem

Real life is messy. Experiments will overlap. The system handles this by:
- Detecting concurrent experiments automatically
- Showing overlap warnings on experiment detail pages
- Providing the AI with full overlap context so it can reason about confounders
- Never claiming causation — always framing as "correlation during this period"

---

## Pillar 3: Health Plans

### What it does
Structured health programs that organize multiple experiments and goals into a coherent plan.

### Structure
- A plan has a name, description, status, and structured content
- Plans link to one or more experiments
- Plans can be created manually or generated by the AI assistant
- The AI can suggest plans based on detected patterns ("Your HRV has been declining — consider a recovery-focused plan")

### Relationship to experiments
Plans are the "why," experiments are the "what." A plan like "Improve sleep quality" might link to experiments for "No screens after 9pm," "Magnesium supplementation," and "10-min evening meditation."

---

## New Database Schema

Six new tables extend the existing SQLite database:

### conversations
Stores chat conversation metadata. Links to Claude Code sessions for continuity.
- Fields: id, title, claude_session_id, model (sonnet/opus), created_at, updated_at

### conversation_messages
Individual messages for UI display. Stored independently of Claude's session state.
- Fields: id, conversation_id, role (user/assistant), content, created_at

### experiments
The core experiment record.
- Fields: id, name, type, description, start_date, end_date, status, target_metrics (JSON array), hypothesis, created_at, updated_at

### experiment_observations
Daily logs within an experiment. One per experiment per day.
- Fields: id, experiment_id, date, notes, adherence, data (JSON), created_at
- Unique constraint on (experiment_id, date)

### experiment_snapshots
Precomputed correlation analysis results.
- Fields: id, experiment_id, snapshot_date, baseline_data (JSON), during_data (JSON), deltas (JSON), ai_interpretation, created_at

### plans
Health plan records with structured content and linked experiments.
- Fields: id, name, description, status, plan_data (JSON), linked_experiments (JSON array), created_at, updated_at

---

## New API Routes

### Chat — `/api/chat`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Send message, receive SSE stream of AI response |
| GET | `/api/chat/conversations` | List all conversations |
| GET | `/api/chat/conversations/{id}` | Get conversation with message history |
| DELETE | `/api/chat/conversations/{id}` | Delete a conversation |

The POST endpoint is unique: it returns a streaming SSE response (not a JSON body). The backend spawns Claude CLI, pipes the user message to stdin, and forwards stdout chunks as SSE events.

### Experiments — `/api/experiments`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/experiments` | List experiments (filter by status, type) |
| POST | `/api/experiments` | Create new experiment |
| GET | `/api/experiments/{id}` | Get experiment detail + observations + snapshots + health data |
| PUT | `/api/experiments/{id}` | Update experiment |
| DELETE | `/api/experiments/{id}` | Delete experiment |
| POST | `/api/experiments/{id}/observations` | Add daily observation |
| GET | `/api/experiments/{id}/observations` | List observations |
| POST | `/api/experiments/{id}/snapshot` | Trigger correlation snapshot computation |
| POST | `/api/experiments/{id}/ai-analysis` | Request AI analysis of this experiment |

### Plans — `/api/plans`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/plans` | List plans |
| POST | `/api/plans` | Create plan (optionally AI-generated) |
| GET | `/api/plans/{id}` | Get plan detail |
| PUT | `/api/plans/{id}` | Update plan |
| DELETE | `/api/plans/{id}` | Delete plan |

---

## New Frontend Pages

### Navigation structure

The header nav gets a visual separator between existing metric pages and new feature pages:

**Metric pages** (existing): Dashboard, Heart Rate, HRV, Sleep, Stress, Body Battery, Respiration, Skin Temp, Pulse Ox

**Feature pages** (new): Assistant, Experiments, Plans

### `/assistant` — AI Chat

Split-panel layout:
- **Left sidebar:** Conversation list with timestamps, model badges, search
- **Right panel:** Message thread with streaming responses, markdown rendering
- **Bottom:** Message input with model selector (Sonnet / Opus toggle)
- New conversation button in sidebar

### `/experiments` — Experiment Hub

- Card grid showing all experiments
- Each card: name, type badge (color-coded), status indicator, date range, key metric delta (if snapshot exists)
- Create experiment button → form with fields for name, type, hypothesis, target metrics, start date
- Filter controls: by type, by status

### `/experiments/[id]` — Experiment Detail

- **Header section:** Name, type badge, status, hypothesis, date range
- **Observations panel:** Chronological timeline of daily logs, adherence visualization, "add observation" form
- **Metrics panel:** Line charts for each target metric over the experiment period, with baseline reference line
- **Correlation section:** Before vs. during comparison (bar chart or table), overlapping experiment warnings
- **AI section:** Snapshot interpretations, "Ask AI about this experiment" button

### `/plans` — Health Plans

- Plan list with status indicators
- Plan detail with structured content, linked experiment cards
- Create plan form (manual or "Generate with AI" option)

---

## Target Metric Registry

Standardized metric keys that map to fields in the existing `DailyMetric` model:

| Key | Maps to | Unit |
|-----|---------|------|
| `resting_hr` | heart_rate.resting | bpm |
| `hrv_nightly` | hrv.nightly_avg | ms |
| `hrv_weekly` | hrv.weekly_avg | ms |
| `sleep_score` | sleep.score | pts |
| `deep_sleep_score` | sleep.deep_score | pts |
| `stress_avg` | stress.avg | 0-100 |
| `body_battery_min` | body_battery.min | 0-100 |
| `body_battery_max` | body_battery.max | 0-100 |
| `spo2_avg` | spo2.avg | % |
| `skin_temp_deviation` | skin_temp.deviation | C |

This registry is the contract between experiments (what to track) and the correlation engine (what to compare).

---

## Key Design Decisions

### Why Claude Code CLI (not Anthropic API)?
- No API key management in the app
- Gets all Claude Code tools for free (file reading, bash, code analysis)
- Session management via `--resume` without building our own context window manager
- Inherits project CLAUDE.md and skills automatically
- Trade-off: ~1-2s cold start per subprocess, but acceptable for chat UX with streaming

### Why hybrid data context (system prompt + tool access)?
- System prompt gives instant awareness (no tool call latency for basic questions)
- Tool access enables unbounded analytical depth (arbitrary SQL queries)
- System prompt alone hits context limits; tool access alone adds latency to every interaction

### Why store messages in our SQLite AND use Claude sessions?
- Our SQLite: fast UI rendering, conversation listing, search — no need to spawn Claude just to show history
- Claude sessions: full analytical context, accumulated reasoning, tool call results

### Why deterministic correlation engine + AI interpretation?
- Statistical comparisons must be reproducible and testable
- AI provides narrative and handles nuance (overlapping experiments, confounders)
- Separation makes the system debuggable — if the AI says something wrong, you can check the raw numbers

### Why no new Python dependencies?
- Claude CLI is a system-level tool (already installed)
- subprocess, sqlite3, json, asyncio are all stdlib
- Frontend needs `marked` for markdown rendering in chat — the only new dependency

---

## New Backend Modules

### Services (in `backend/app/services/`)

| Module | Responsibility |
|--------|---------------|
| `ai_chat.py` | Spawn Claude CLI subprocess, build system prompt with health context, manage session IDs, stream responses |
| `experiments.py` | Experiment + observation CRUD, correlation snapshot computation, overlap detection |
| `plans.py` | Plan CRUD, AI-assisted plan generation |

### Routes (in `backend/app/routers/`)

| Module | Prefix |
|--------|--------|
| `chat.py` | `/api/chat` |
| `experiments.py` | `/api/experiments` |
| `plans.py` | `/api/plans` |

### Infrastructure changes
- `database.py`: New table creation in `init_db()`, CRUD functions for all new tables, extended `_VALID_TABLES`
- `main.py`: Register three new routers

---

## New Frontend Components

| Component | Purpose |
|-----------|---------|
| `ChatMessage.svelte` | Render user/assistant message with markdown |
| `ChatInput.svelte` | Text input with send button and model selector |
| `ExperimentCard.svelte` | Summary card for experiment list |
| `ObservationForm.svelte` | Date, notes, adherence slider for daily logs |
| `MetricComparison.svelte` | Before/during bar chart for correlation display |
| `TypeBadge.svelte` | Color-coded experiment type indicator |

New utility: `chat-stream.ts` — POST-based SSE streaming (existing `sse.ts` is GET-only)

---

## Implementation Phases

| Phase | Scope | Delivers |
|-------|-------|----------|
| **1** | Database schema + experiment/plan CRUD (backend) | Data foundation, testable API |
| **2** | Experiment + plans frontend pages | Users can manually track experiments |
| **3** | Correlation engine + metric comparison UI | Quantified impact of interventions |
| **4** | AI chat integration (backend + frontend) | Full conversational health assistant |
| **5** | AI-powered experiment analysis | AI interprets experiment results |
| **6** | Polish: overlap visualization, AI suggestions, templates | Refined experience |

Each phase delivers standalone value. Phase 2 is useful without AI. Phase 4 is useful without experiments. They compound when combined.
