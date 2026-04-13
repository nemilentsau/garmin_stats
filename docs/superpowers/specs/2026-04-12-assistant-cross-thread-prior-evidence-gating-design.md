# Assistant Cross-Thread Prior Evidence Gating Design

Date: 2026-04-12

## Problem

The retrieval-first assistant currently attaches recent `prior_evidence` bundles from other threads by recency alone. This is too eager:

- fresh threads can inherit irrelevant analytical context from unrelated threads
- experiment-focused evidence can bleed into recovery briefings
- continuity becomes opaque because cross-thread recall is ambient instead of relevance-triggered

Global memory should remain available by default, but cross-thread prior evidence should not.

## Scope

This change tightens only cross-thread `prior_evidence` recall in the assistant retrieval layer.

Out of scope:

- HTTP/API contract changes
- NDJSON stream shape changes
- assistant runtime changes
- broader memory model redesign
- frontend changes

## Target Rule

- Thread-local evidence is primary.
- Global memory stays available by default.
- Cross-thread `prior_evidence` is attached only when a relevance trigger is present.

Phase-1 relevance triggers:

- exact resolved-entity overlap
- explicit recall language from the user
- same intent family

## Matching Rules

### Exact entity overlap

Use exact canonical `entity_id` overlap only. Do not use fuzzy text similarity or embeddings for this follow-up.

### Explicit recall language

Allow cross-thread prior evidence when the user explicitly asks to compare or recall earlier discussion, including phrases such as:

- `compare`
- `earlier`
- `before`
- `last thread`
- `what did we say`

### Intent-family fallback

Intent-family recall is allowed only through this bounded adjacency map:

- `recovery_briefing` -> `recovery_briefing`, `open_ended_coaching`
- `open_ended_coaching` -> `open_ended_coaching`, `recovery_briefing`, `routine_adherence`
- `routine_adherence` -> `routine_adherence`, `open_ended_coaching`
- `experiment_review` -> `experiment_review` only, unless explicit recall language or exact entity overlap is present

Hard exclusions:

- no unrelated-family recall by recency alone
- no ambient cross-thread recall in a fresh thread without a trigger
- no fuzzy matching against prior assistant prose

## Implementation Direction

Localize the change to assistant retrieval:

- `backend/app/domains/assistant/application/evidence.py`
- small routing signal support in `backend/app/domains/assistant/application/router.py` if needed

Keep persistence shape stable. Prior-bundle relevance should be derived from:

- bundle intent
- bundle entities
- current resolved entities
- current route signals

Do not redesign runtime or conversation persistence for this slice.

## Verification

Add regression coverage for:

- recovery briefings excluding unrelated experiment prior evidence
- same-entity experiment recall across threads
- bounded adjacent-family recall
- explicit recall language enabling cross-thread recall
- thread-local behavior remaining unchanged
