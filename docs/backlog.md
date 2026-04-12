# Backlog

## Assistant Follow-Ups

### 1. Add Daily Check-In UI On `/today`

See [checkin-todo.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/checkin-todo.md).

Reason:

- backend check-in support already exists
- assistant and experiment analysis both benefit from subjective context
- there is currently no frontend entry surface

Recommended shape:

- compact `Daily Check-In` card on `/today`
- today-first entry flow
- preserve the existing `/api/checkins` contract

### 2. Gate Cross-Thread `prior_evidence` By Relevance

Current state:

- global continuity is enabled by default
- new threads can still receive `prior_evidence` items from unrelated recent threads
- this did not break the current smoke test, but it is broader than necessary

Why it matters:

- broad recall will eventually cause answer bleed across topics or threads
- daily briefings should not automatically carry recent experiment-review bundles unless they are actually relevant

Recommended follow-up:

- keep global memory default
- tighten `prior_evidence` selection by intent and entity relevance
- continue allowing explicit cross-thread recall where it adds value

### 3. Tighten Assistant Lead-In Wording

Current state:

- the assistant can still imply hidden multi-stage reasoning or later refinement in some lead sentences

Why it matters:

- wording should describe the actual runtime behavior
- the current assistant is a single-pass grounded generation path over `evidence.json`, `memory.json`, and `thread_messages.json`

Recommended follow-up:

- replace any misleading “refine later” phrasing with factual source-aware wording
- preferred framing: grounded from current evidence plus prior thread context when present
