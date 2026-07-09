# Documentation Index

Current project documentation only. Implementation plans, working specs, and superseded design
notes are never kept here — git history retains them. If a doc's subject stops existing, the doc
is deleted in the same change.

The folder layout is the taxonomy:

## `routine-pivot/` — CANON (read-only)

The product direction and the training system's source of truth. Everything else bends to these.

- [general_principles.md](routine-pivot/general_principles.md) — P1–P13 governing principles.
- [schema_v3_spec.md](routine-pivot/schema_v3_spec.md) — the v3 training schema the app imports.
- [pivot_roadmap.md](routine-pivot/pivot_roadmap.md) — two standing objectives, phases, shipped
  notes, and the import-only ingress rule.
- [block0/](routine-pivot/block0/) — the authored Block 0 artifacts (bundles, block, registry,
  exercise library, reference linter) imported verbatim by the app.

## Top level — the code map

- [ARCHITECTURE.md](ARCHITECTURE.md) — backend/frontend structure, module charters, route
  inventory, boundary rules. Kept current with code changes (see CLAUDE.md).

## `reference/` — how shipped things work and why

- [recovery-dashboard.md](reference/recovery-dashboard.md) — recovery score, health flags, and the
  dashboard overview (ships until the Phase 2 reframe).
- [recovery-score.md](reference/recovery-score.md) — explanation and critique of the score.
- [HRV_TAB_REFACTOR.md](reference/HRV_TAB_REFACTOR.md) — HRV tab rationale (cited by code comments).
- [analytics-approach.md](reference/analytics-approach.md) — the AI-analysis skill split.

## `future/` — specs for work not built yet

- [ACTIVITY_ANALYTICS_DESIGN.md](future/ACTIVITY_ANALYTICS_DESIGN.md) — activity/session ingestion
  design (FITs download today; parsing unbuilt).
- [RUNNING_ACTIVITY_SCHEMA.md](future/RUNNING_ACTIVITY_SCHEMA.md) /
  [STRENGTH_ACTIVITY_SCHEMA.md](future/STRENGTH_ACTIVITY_SCHEMA.md) — proposed parser/read-model
  schemas from the June corpus analysis; become Pydantic contracts (and get deleted here) when the
  parser is built.
- [activity-analysis/](future/activity-analysis/) — analyst question backlogs gated on that parser.
- [central-dashboard-readiness.md](future/central-dashboard-readiness.md) — Phase 2 dashboard input.
- [sleep-opportunity-regularity.md](future/sleep-opportunity-regularity.md),
  [health-exceptions.md](future/health-exceptions.md),
  [experiment-adherence.md](future/experiment-adherence.md) — pre-pivot lane requirement notes;
  inputs to Phase 2 design, deleted if that design supersedes them.

## `routine_bundles/` — LEGACY v2 import content

The v2 bundle format spec ([ROUTINE_ARTIFACT_BUNDLE_SPEC.md](routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md))
plus the meditation/breathwork/experiment bundle JSONs. Nothing v2 is currently imported; this
corner exists so meditation content can be re-imported before Phase 3 redesigns it. The whole
directory is deleted when the v2 path retires.

## `findings/` — committed findings presentation

Human-facing analysis HTML regenerated from local finding runs (the machine record, `FINDINGS.md`
and raw runs, stays local-only).
