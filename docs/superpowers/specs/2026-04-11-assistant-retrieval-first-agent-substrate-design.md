# Assistant Retrieval-First Agent Substrate Design

Date: 2026-04-11
Status: Proposed

## Summary

Replace the current assistant internals with a retrieval-first analyst layer that keeps the existing `/api/assistant` HTTP contract stable while making backend state the source of truth for continuity, grounding, and memory.

This is not a compatibility-wrapper migration like the routines slice. For assistant, the backend should preserve only the external API and stream contract used by the frontend. The current internal assistant implementation is replaceable.

The new assistant should optimize for three things at the same time:

1. Follow-up reliability
2. Better experiment and routine answer quality
3. Lower first-response latency

The design targets a production path that is retrieval-first today, while being explicitly shaped so a future planner/action layer can be added without another architectural rewrite.

## Current Problems

The current assistant stack is too thin and too brittle:

- `backend/app/services/assistant.py` saves the user message, builds a generic snapshot, shells out to Claude Code, and relies on streamed deltas plus a final done event to persist the assistant reply.
- `backend/app/services/assistant_context.py` builds one generic snapshot for every question from profile, dashboard overview, a 14-day metric digest, active routines, active experiments, recent check-ins, and recent notes.
- `backend/app/services/assistant_runtime.py` writes `context.json`, `context.md`, and `task.md`, then calls `claude -p ... --resume <session_id>`.
- Follow-up continuity depends on external Claude session state rather than state the backend owns.

Observed failure:

- The first experiment question succeeded, but took about 85 seconds end to end.
- The follow-up failed immediately with `No conversation found with session ID ...`.
- This shows that continuity is currently owned by Claude session resume, not by the backend.

Grounding quality is also structurally weak:

- The assistant sees a broad generic snapshot rather than a question-specific evidence bundle.
- The snapshot includes experiment specs, but not the canonical persisted experiment analysis that the experiments UI uses.
- The assistant does not explicitly retrieve prior thread content, resolved entities, or prior evidence used in the conversation.

## Goals

- Make backend persistence the source of truth for continuity.
- Replace generic snapshotting with question-specific retrieval and evidence bundling.
- Keep the current assistant frontend UX and API contract stable.
- Support cross-thread memory by default.
- Allow clarifying questions when intent or entity resolution is ambiguous.
- Improve latency by retrieving only what a question needs.
- Shape the assistant substrate so future routine/experiment authoring can be added as a planner/action layer instead of a rewrite.

## Non-Goals

- No frontend UX redesign in this slice.
- No change to `/api/assistant` route paths or request/response contracts consumed by the frontend.
- No long-lived compatibility layer for old assistant internals.
- No knowledge-graph-first implementation in this slice.
- No fully agentic planner as the default production path in this slice.

## Hard Constraints And Decisions

- Preserve the assistant HTTP contract and NDJSON stream shape used by the current frontend.
- Preserve nothing else internally unless it directly protects that contract.
- Claude session resume is an optimization only, never a dependency.
- Threads are not the true memory boundary. Global user memory is the primary memory model.
- The assistant is a data-grounded analyst and coach for this system's state, not a general health chatbot.
- The production path is retrieval-first and deterministic-first.
- The design must keep explicit hooks for a future planner and action executor.

## External Contract To Preserve

These are the only required compatibility surfaces:

- `/api/assistant/threads`
- `/api/assistant/threads/{thread_id}`
- `/api/assistant/threads/{thread_id}/messages`
- the streamed NDJSON contract consumed by `frontend/src/lib/assistant-stream.ts`

Everything else in the current assistant internals is replaceable.

## Target Architecture

The assistant becomes a retrieval-first agent substrate:

```text
assistant request
  -> query router
  -> entity resolver
  -> retriever registry
  -> evidence bundle builder
  -> answer generator
  -> persistence of run/message/evidence/memory
```

Core subsystems:

- `api`
  Owns the stable `/api/assistant` HTTP boundary and NDJSON stream contract.

- `application/router`
  Classifies the user request into known assistant intents and returns confidence.

- `application/entity_resolution`
  Resolves phrases like "meditation experiment" into canonical IDs using current domain state, recent thread context, and global memory aliases.

- `application/retrieval`
  Coordinates deterministic domain retrievers based on the routed intent and resolved entities.

- `application/evidence`
  Produces a compact, structured evidence bundle with provenance and freshness metadata.

- `application/generation`
  Calls the model with the evidence bundle and instructions for grounded answering.

- `application/memory`
  Maintains global and thread-local memory records owned by the backend.

- `infra`
  Provides persistence, model runtime invocation, and optional event publishing.

## Assistant Positioning

The assistant should primarily behave as:

- a grounded interpreter of the user's routines, experiments, recovery state, and logs
- a coach that explains what the data supports and where uncertainty remains
- a system-aware analyst that can later propose experiments and routines once planning and action layers are added

It should not behave as:

- a generic health chatbot
- a system that invents answers when evidence is weak
- a conversation engine whose continuity depends on model-side memory

## Memory Model

Memory is global-first.

### 1. Thread history

Thread history stores exact conversation turns and remains useful for:

- local phrasing
- immediate follow-up context
- UI presentation

But thread history is not the system's primary continuity mechanism.

### 2. Global user memory

Global memory is available by default to every thread. It stores reusable, assistant-owned context such as:

- resolved entity aliases
- durable preferences
- recurring confounders
- prior assistant conclusions worth resurfacing
- short factual summaries that help routing or retrieval

Examples:

- `"meditation experiment"` usually resolves to `meditation-hrv-2026-03`
- the user cares about causal interpretation and confounders
- alcohol and travel are recurring HRV confounders worth checking

### 3. Canonical domain state

Canonical domain state is not assistant-authored memory. It is backend truth:

- experiments
- persisted experiment analyses
- exposures
- routines
- card logs
- notes
- check-ins
- metrics
- profile

Rule:

- canonical domain state always outranks assistant-authored memory when they conflict

## Retrieval Model

The assistant should not receive one giant snapshot for every question. It should receive a question-specific evidence bundle.

### Query router

The first version should be deterministic-first, with confidence scoring.

Example intent families:

- experiment review
- routine adherence / today
- recovery briefing
- coaching interpretation
- open-ended system-state analysis
- future authoring intents such as experiment proposal or routine proposal

Routing does not need a full generative planner on day one. It can begin with rules, weighted matching, and explicit fallbacks.

### Entity resolver

Entity resolution should:

- extract likely entity phrases from the request
- rank candidate matches against active experiments, linked routines, prior thread entities, and global aliases
- ask a clarifying question when ambiguity remains

This makes a query like `How does our meditation experiment look so far?` tractable without a full planner.

### Retriever registry

Retrievers should be deterministic domain read-model fetchers. Initial retrievers should include:

- `experiment_retriever`
- `experiment_analysis_retriever`
- `experiment_adherence_retriever`
- `routine_retriever`
- `routine_log_retriever`
- `recovery_retriever`
- `confounder_retriever`
- `conversation_memory_retriever`

Each retriever returns structured evidence, not prose.

### Evidence bundle builder

The evidence bundle is the model-facing payload. It should include:

- routed intent
- resolved entities
- canonical facts
- provenance
- freshness
- missing or unresolved gaps
- optional supporting excerpts from thread/global memory

The evidence bundle should be persisted per run so answers can be audited and reused.

## Generation Model

The model should answer from the evidence bundle, not from an oversized generic snapshot.

Rules for generation:

- use evidence bundle facts as the basis for the answer
- explicitly call out uncertainty and missing evidence
- do not silently invent continuity from prior model-side conversation
- prefer canonical analysis outputs when they exist
- ask a clarifying question when the bundle is ambiguous

Prompting becomes thinner and more disciplined:

- instruct the model to answer from the supplied evidence bundle
- instruct it to distinguish facts, inference, and uncertainty
- instruct it to ask a short clarification when entity resolution is ambiguous

The prompt should stop carrying the burden of retrieval design.

## Continuity Model

Backend persistence becomes the continuity owner.

Continuity should come from:

- stored thread messages
- global memory
- prior resolved entities
- prior evidence bundles
- canonical backend state

Optional Claude session resume may still be attempted, but:

- a lost session must not break follow-ups
- continuity must still work without it
- the system should degrade to backend-owned continuity automatically

This directly addresses the observed follow-up failure mode.

## Latency Strategy

Latency needs explicit design, not prompt tweaking.

The assistant should use a two-stage reply path:

1. fast grounded first answer
2. optional deeper synthesis when the question needs more work

Implications:

- retrieve only what the routed intent needs
- stop building the same large generic snapshot for every question
- cache or memoize stable read models where practical
- keep evidence bundles compact
- treat any optional model-side resume as a speed optimization only

The first version does not need full multi-stage UX changes. The important part is that the backend architecture supports fast initial grounding instead of always paying for broad retrieval plus fragile session resume.

## Failure Handling

Failure behavior should be explicit and controlled:

- If intent confidence is low, route to a safe fallback or ask a clarifying question.
- If entity resolution is ambiguous, ask a clarifying question.
- If a retriever fails, record the gap and continue if a minimal answer is still possible.
- If evidence is insufficient, say so clearly instead of bluffing.
- If Claude session resume fails, continue with backend-owned continuity.
- If generation fails after retrieval succeeds, keep the retrieved evidence and run record for debugging and retry.

## Future Planner And Action Hooks

This design is retrieval-first today but planned for a future agentic layer.

Stable extension points should exist now:

- `query_router`
- `entity_resolver`
- `retriever_registry`
- `memory_store`
- `evidence_bundle_builder`
- `generator`
- `planner`
- `action_executor`

In this slice:

- `planner` exists only as a designed extension point
- `action_executor` exists only as a designed extension point

Later, `planner` becomes necessary when:

- routing confidence is often low
- deterministic retrieval cannot handle common real questions
- the assistant needs multi-step retrieval planning
- the assistant needs to author or mutate routines, experiments, or artifacts as part of normal behavior

This design intentionally separates:

- grounded answering
- planning
- action execution

That separation is what avoids another rewrite when the assistant eventually starts proposing or authoring experiments and routines.

## Knowledge Graph Assessment

A knowledge graph is not the right first move.

Why not now:

- the important entities are already strongly structured in SQLite
- the current failures are continuity, retrieval design, and grounding, not graph traversal
- a graph-first system would increase implementation and debugging complexity before the assistant substrate is stable

When a graph may become useful later:

- if cross-entity memory becomes rich enough that aliasing and relationship traversal are hard to model in relational retrieval alone
- if the planner starts needing broader multi-hop relationship search across many domains

For this slice, SQLite-backed deterministic retrieval is the correct base.

## Migration Strategy

The assistant slice should be treated as an API-stable internal rewrite.

Implementation implications:

- `domains/assistant/` becomes the real owner immediately
- old flat assistant internals should not be preserved as long-lived compatibility seams
- old internals may be deleted aggressively once imports and tests are moved
- only the frontend API contract and stream event shape need to remain stable

This differs from the routines slice on purpose.

## Testing Strategy

The assistant rewrite should add or preserve tests for:

- intent routing
- entity resolution
- retriever correctness per domain
- evidence bundle construction
- generation orchestration
- follow-up continuity without Claude session resume
- degraded-mode behavior when a retriever fails
- explicit regression coverage for:
  - initial experiment question succeeds
  - follow-up still works when external session resume is unavailable

Verification remains:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

## Implementation Shape

The next implementation plan should replace the current assistant internals with a domain-owned stack that includes:

- assistant API boundary
- router
- entity resolver
- retriever registry
- evidence bundle builder
- backend-owned memory store
- generation orchestrator
- runtime adapter

This should land as the next backend refactor slice after routines, and it should supersede the older assistant migration plan that assumed a more compatibility-oriented move.
