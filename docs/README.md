# Documentation Index

Current project documentation only. Implementation plans, working specs, and superseded design notes are never kept here — git history retains them. If a doc's subject stops existing, the doc is deleted in the same change.

**One fact, one home.** Each fact lives in exactly one authoritative doc; everywhere else links to it. CLAUDE.md holds durable rules and pointers, never current-state facts.

## Start here — find it by question

| I want to know… | Read |
|---|---|
| What Garmin data we have / how it gets in (two trees, ingest, sync, config paths) | [`reference/data-and-ingest.md`](reference/data-and-ingest.md) |
| The API + frontend route list | [`reference/routes.md`](reference/routes.md) (generated — `scripts/generate_routes_doc.py`) |
| The code map — domains, layering, where things live | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| What a domain owns / may import (its boundary contract) | `backend/app/domains/<domain>/CHARTER.md` |
| Where new code / a shared helper belongs; slice + frontend conventions | [`reference/code-conventions.md`](reference/code-conventions.md) |
| The training-system rules, v3 schema, roadmap | [`routine-pivot/`](routine-pivot/) (canon) |
| How a shipped feature works (recovery score, HRV tab) | [`reference/`](reference/) |
| What's designed but not built yet | [`future/`](future/) |
| Data-analysis findings | [`findings/`](findings/) (+ local `FINDINGS.md`) |

## The folder taxonomy

### `routine-pivot/` — CANON (read-only)

The product direction and the training system's source of truth. Everything else bends to these.

- [general_principles.md](routine-pivot/general_principles.md) — P1–P13 governing principles.
- [schema_v3_spec.md](routine-pivot/schema_v3_spec.md) — the v3 training schema the app imports.
- [pivot_roadmap.md](routine-pivot/pivot_roadmap.md) — two standing objectives, phases, shipped notes, and the import-only ingress rule.
- [block0/](routine-pivot/block0/) — the retired Block 0 artifacts; frozen as the schema-exemplar + test-fixture canon, no longer imported.
- [block1/](routine-pivot/block1/) — the authored Block 1 (threshold-development) artifacts, the active block imported verbatim by the app.

### `ARCHITECTURE.md` — the code map

Backend/frontend structure, dependency layering, and the domain index. Per-domain boundary contracts are colocated at `backend/app/domains/<domain>/CHARTER.md` (the charter is the authority; ARCHITECTURE is the map).

### `reference/` — how shipped things work and why

- [data-and-ingest.md](reference/data-and-ingest.md) — **the two Garmin data trees, ingest/sync, and config paths. Single source of truth for data topology.**
- [run-activities.md](reference/run-activities.md) — how tracked runs parse, store, and display (running only; strength still unparsed).
- [routes.md](reference/routes.md) — generated route inventory (backend OpenAPI + SvelteKit).
- [code-conventions.md](reference/code-conventions.md) — `app/utils/` promotion rule, slice boundaries, frontend conventions, doc style.
- [recovery-dashboard.md](reference/recovery-dashboard.md) — recovery score, health flags, dashboard overview (ships until the Phase 2 reframe).
- [recovery-score.md](reference/recovery-score.md) — explanation and critique of the score.
- [HRV_TAB_REFACTOR.md](reference/HRV_TAB_REFACTOR.md) — HRV tab rationale (cited by code comments).
- [analytics-approach.md](reference/analytics-approach.md) — the AI-analysis skill split.

### `future/` — specs for work not built yet

Each doc carries a status header. A partial subsystem (design here, some of it shipped) links to the shipped half in `reference/` — e.g. activity FIT *download* is shipped (`reference/data-and-ingest.md`) while parse/associate is the design below.

- [ACTIVITY_ANALYTICS_DESIGN.md](future/ACTIVITY_ANALYTICS_DESIGN.md) — activity/session ingestion design (running shipped 2026-07, see `reference/run-activities.md`; strength parsing + the generic cross-sport/experiment-day mart remain unbuilt).
- [STRENGTH_ACTIVITY_SCHEMA.md](future/STRENGTH_ACTIVITY_SCHEMA.md) — proposed parser/read-model schema; becomes Pydantic contracts (and gets deleted here) when the strength parser is built. (Its running sibling shipped and was deleted the same way — see `reference/run-activities.md`.)
- [activity-analysis/](future/activity-analysis/) — analyst question backlogs gated on that parser.
- [central-dashboard-readiness.md](future/central-dashboard-readiness.md) — Phase 2 dashboard input.
- [sleep-opportunity-regularity.md](future/sleep-opportunity-regularity.md), [health-exceptions.md](future/health-exceptions.md), [experiment-adherence.md](future/experiment-adherence.md) — pre-pivot lane requirement notes; inputs to Phase 2 design, deleted if that design supersedes them.

### `routine_bundles/` — LEGACY v2 import content

The v2 bundle format spec ([ROUTINE_ARTIFACT_BUNDLE_SPEC.md](routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md)) plus the meditation/breathwork/experiment bundle JSONs. Nothing v2 is currently imported; this corner exists so meditation content can be re-imported before Phase 3 redesigns it. The whole directory is deleted when the v2 path retires.

### `findings/` — committed findings presentation

Human-facing analysis HTML regenerated from local finding runs (the machine record, `FINDINGS.md` and raw runs, stays local-only).
