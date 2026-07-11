# assistant — Charter

**Status:** shipped (backend + `/assistant` frontend route for threads and chat)
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Assistant chat and retrieval-first evidence context. This slice uses a flat
small-capability layout: `routes.py` owns `/api/assistant` HTTP and streaming
endpoints; `application/` owns thread catalog, intent classification, entity
resolution, read-model interaction, evidence assembly, retrieval, and chat
orchestration; `domain/` owns pure assistant evidence payload policy;
`dependencies.py` owns conversation/read-model/runtime dependencies;
`adapters.py` owns assistant SQLite persistence; `read_gateway.py` owns the
cross-domain read-model wiring for evidence assembly; `runtime.py` owns Claude
Code subprocess execution; and `contracts.py` owns assistant API and
persistence shapes.

## Owns
- Assistant threads, messages, and thread activity ordering.
- Evidence bundle assembly and persistence.
- Retrieval routing (intent classification, entity resolution, retrieval).
- Assistant memory records.
- Runtime interaction (streaming chat via the Claude Code subprocess).

## Does not own
- Garmin parsing.
- Garmin ingest.
- Routine scheduling writes.
- Experiment exposure derivation.
- Artifact activation.

## May import
- Its own contracts, application helpers, and dependencies.
- Explicitly allowlisted read dependencies needed to build evidence context,
  including canonical Garmin health contracts.

## Must not import
- Garmin sync.
- Garmin analytics application internals.
- Routine activation internals.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints
- `/api/assistant` routes (thread list/create/detail, message list, and the
  NDJSON streaming reply endpoint) and the assistant application use cases
  those routes call.
- Note: `/api/assistant/artifacts` and `/api/assistant/artifact-bundles` are
  owned by the `artifacts` domain, not this slice, despite the shared URL
  prefix.

## Key files
- `routes.py` — FastAPI + NDJSON streaming boundary under `/api/assistant`.
- `application/` — `threads.py`, `chat.py`, `intent_routing.py`,
  `entity_resolution.py`, `retrieval.py`, `evidence.py`, `turn_context.py`,
  `runtime_stream.py`, `memory_aliases.py`.
- `domain/` — pure evidence payload policy (`payloads.py`,
  `current_state.py`, `experiment_evidence.py`, `text.py`).
- `dependencies.py` — conversation store, read-model store, and runtime ports.
- `adapters.py` — SQLite assistant repository (`SqliteAssistantRepository`).
- `read_gateway.py` — allowlisted cross-domain read wiring for evidence.
- `runtime.py` — Claude Code subprocess execution.
- `contracts.py` — assistant API + persistence shapes.
- `schema.py` — SQLite table schema for assistant storage.

## Verified against code (2026-07-10)
- Owns, does-not-own, and public entrypoints match the code.
- `routes.py` mounts prefix `/api/assistant`; all endpoints are under
  `/threads` (list/create/detail, `/threads/{id}/messages`, and the streaming
  POST). The central "Assistant" route-inventory block also lists
  `/api/assistant/artifacts` and `/api/assistant/artifact-bundles`, but those
  are the `artifacts` domain's routes — assistant does not mount them.
- Import boundary nuance (by design, not a violation): the allowlisted evidence
  seam lives in `read_gateway.py`, which imports
  `experiments.application.analysis_cache` and
  `garmin_analytics.application.dependencies.BiometricReadRepository` (a read
  port), plus `routines`/`journal`/`experiments` contracts and dependency
  protocols. This is the "allowlisted read dependencies … to build evidence
  context" clause. The narrower "Must not import Garmin analytics application
  internals" wording applies to application use cases/logic, not this read
  port; the seam is confined to `read_gateway.py`, and application modules do
  not import FastAPI or SQLite helpers.
- `adapters.py` imports `app.infra.sqlite` / `app.infra.jsonstore` (adapter
  layer, allowed); application modules do not.
