# Backlog

## Assistant Follow-Ups

### Completed: Gate Cross-Thread `prior_evidence` By Relevance

Implemented on 2026-04-12.

What changed:

- cross-thread `prior_evidence` is no longer attached by recency alone
- same-thread evidence stays primary
- cross-thread recall now requires exact entity overlap, explicit recall language, or allowed intent-family fallback
- global memory remains available by default

Reference:

- [2026-04-12-assistant-cross-thread-prior-evidence-gating-design.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/superpowers/specs/2026-04-12-assistant-cross-thread-prior-evidence-gating-design.md)
- [2026-04-12-assistant-cross-thread-prior-evidence-gating.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/superpowers/plans/2026-04-12-assistant-cross-thread-prior-evidence-gating.md)

### Completed: Tighten Assistant Lead-In Wording

Implemented on 2026-04-12.

What changed:

- the fast grounded first delta no longer claims a later refinement pass
- lead-in wording now describes current evidence directly instead of implying hidden multi-stage reasoning

Reference:

- [chat.py](/Users/andreinemilentsau/Projects/garmin_stats/backend/app/domains/assistant/application/chat.py)

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
