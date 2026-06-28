# Documentation Index

Current project documentation only. Completed implementation plans and superseded design notes are
not kept as a parallel source of truth (git history retains them).

## Read First

- [ARCHITECTURE.md](ARCHITECTURE.md) — backend/frontend structure, ownership boundaries, route
  inventory, and domain rules.
- [recovery-dashboard.md](recovery-dashboard.md) — the recovery score, health flags, regime
  detection, and the dashboard overview: what they are, why, and where they are computed.
- [recovery-score.md](recovery-score.md) — product-facing explanation and critique of the recovery
  score, including why it is one dashboard lane rather than the whole central model.
- [central-dashboard-readiness.md](central-dashboard-readiness.md) — current central-dashboard
  roadmap: what is shippable now, what can be added from existing data, and what is deferred until
  new ingestion exists.

## Detail Tabs

- [HRV_TAB_REFACTOR.md](HRV_TAB_REFACTOR.md) — the HRV detail tab: what the redesign investigation
  found (why the old widgets misled), what shipped (trailing baseline-window knob, moving ribbon,
  extreme-night markers, trailing-z night readout), and the deliberate baseline divergence from the
  recovery score.

## Specs & Domain Direction

- [ROUTINE_ARTIFACT_BUNDLE_SPEC.md](ROUTINE_ARTIFACT_BUNDLE_SPEC.md) — assistant-authored routine
  bundle JSON contract.
- [ACTIVITY_ANALYTICS_DESIGN.md](ACTIVITY_ANALYTICS_DESIGN.md) — future Garmin activity/session
  marts and the experiment-day joins that would unlock a load/progress axis. This is not the
  immediate implementation track while generic metric dashboards are being refactored.
- [load-data.md](load-data.md) — data requirements and validation questions for a future
  load/strain axis.
- [adaptation-progress.md](adaptation-progress.md) — data requirements and validation questions
  for sport-specific adaptation and progress metrics.
- [sleep-opportunity-regularity.md](sleep-opportunity-regularity.md) — data requirements and
  validation questions for sleep duration, timing, debt, and regularity metrics.
- [health-exceptions.md](health-exceptions.md) — data requirements and validation questions for
  health-context flags such as oxygen, thermoregulation, illness-like patterns, and data coverage.
- [experiment-adherence.md](experiment-adherence.md) — data requirements and validation questions
  for experiment-day routine exposure, protocol adherence, and analyzability gates.

## Analyst Method

- [analytics-approach.md](analytics-approach.md) — why AI-assisted analysis of this dataset is
  structured the way it is, the failure modes it guards against, and how the `finding-analyst`
  skill enforces the discipline. (The promoted evidence itself lives in the local-only
  `FINDINGS.md`.)
- [findings/index.html](findings/index.html) — the **human-facing HTML presentation** of the
  analysis behind the recovery score and HRV surfaces. A landing hub linking General / Recovery
  Score / HRV pages, each pairing the original finding-run plots with narrative takeaways and
  collapsible statistics. Generated from the analyst finding-runs and the local-only `FINDINGS.md`
  (which remains the machine-readable record for future discovery work).

## Data & Bundle Examples

- [routine_bundles/meditation_hrv_experiment.json](routine_bundles/meditation_hrv_experiment.json)
- [routine_bundles/two_week_core_bundle.json](routine_bundles/two_week_core_bundle.json)
- [routine_bundles/two_week_meditation_bundle.json](routine_bundles/two_week_meditation_bundle.json)

## Root Docs

- [../README.md](../README.md) — product overview, high-level architecture, and local setup.
- `FINDINGS.md` (repo root, local-only / gitignored) — analytical trust record for promoted
  findings from the live dataset.
