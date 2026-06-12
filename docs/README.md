# Documentation Index

Current project documentation only. Completed implementation plans and superseded design notes are
not kept as a parallel source of truth (git history retains them).

## Read First

- [ARCHITECTURE.md](ARCHITECTURE.md) — backend/frontend structure, ownership boundaries, route
  inventory, and domain rules.
- [recovery-dashboard.md](recovery-dashboard.md) — the recovery score, health flags, regime
  detection, and the dashboard overview: what they are, why, and where they are computed.

## Specs & Domain Direction

- [ROUTINE_ARTIFACT_BUNDLE_SPEC.md](ROUTINE_ARTIFACT_BUNDLE_SPEC.md) — assistant-authored routine
  bundle JSON contract.
- [ACTIVITY_ANALYTICS_DESIGN.md](ACTIVITY_ANALYTICS_DESIGN.md) — future Garmin activity/session
  marts and the experiment-day joins that would unlock a load/progress axis.

## Analyst Method (research record)

- [analytics-approach.md](analytics-approach.md) — why AI-assisted analysis of this dataset is
  structured the way it is, and the failure modes it guards against.
- [analyst-data-discovery.md](analyst-data-discovery.md) — the (now-complete) stress/recovery
  research agenda: rationale, operating principles, and method constraints. Retained as the
  operating manual for future analyst runs.

## Data & Bundle Examples

- [meditation_hrv_experiment.json](meditation_hrv_experiment.json)
- [two_week_core_bundle.json](two_week_core_bundle.json)
- [two_week_meditation_bundle.json](two_week_meditation_bundle.json)

## Root Docs

- [../README.md](../README.md) — product overview, high-level architecture, and local setup.
- `FINDINGS.md` (repo root, local-only / gitignored) — analytical trust record for promoted
  findings from the live dataset.
