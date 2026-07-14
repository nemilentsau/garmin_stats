# experiments — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Experiment CRUD, design preview/import, target metric registry, manual
day-grain exposure recording, and N=1 analysis. Experiment analysis is a cached read model that
refreshes after exposure changes and on stale date-sensitive reads. The slice
uses a flat route/adapter/dependency layout with a pure `domain/` core.

## Owns

- Experiment definitions.
- Design preview/import.
- Target metric registry.
- Experiment-day exposures.
- Cached N=1 analysis and active-analysis refresh.

## Does not own

- Today log storage.
- Training execution and Today logs.
- Garmin ingest.
- Coach runtime.

## May import

- Experiment repository dependencies.
- Experiment-owned contracts.
- Canonical Garmin health contracts.
- Journal check-in contracts and the injected journal read source used for
  confounders.
- The Garmin Analytics biometric read-repository port through `read_sources.py`.
- Experiment-owned domain analysis helpers.

## Must not import

- Garmin sync.
- Garmin analytics application internals except through analytics read adapters.
- Coach runtime.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints

- `/api/experiments`
- `/api/target-metrics`
- Experiment management use cases.
- Exposure use cases.
- Analysis refresh/read use cases.

## Key files

- `routes.py` — experiment and target-metric HTTP routes (`experiments_router`,
  `target_metrics_router`).
- `application/` — named use cases: `management`, `preview`, `exposures`,
  `analysis_cache`, `analysis`, `target_metrics`.
- `dependencies.py` — repository/read-source ports (`ExperimentRepository`,
  `ExperimentPreviewReadSource`, `ExperimentAnalysisReadSource`).
- `read_sources.py` — cross-domain read-source wiring for preview/analysis inputs.
- `domain/` — pure experiment analysis, experiment-local statistical primitives,
  metric path resolution, and exposure scoring
  (`adherence`, `analysis`, `confounders`, `design_dates`,
  `metric_paths`, `outcomes`, `preview_validation`, `reporting`, `statistics`,
  `windows`).
- `adapters.py` — SQLite repository adapter.
- `contracts.py` — experiment API and persistence shapes.

## Domain semantics

Experiment adherence is protocol-defined and day-grain.

- One `ExperimentExposure` represents one experiment-day for one
  `experiment_id + date`.
- Exposure is recorded explicitly after considering whether the planned
  intervention dose for that day was satisfied across every required session
  or component.
- Multiple intervention sessions or components on one day are summarized into
  the single day-grain exposure record.
- Do not collapse an experiment day to a "best card status" and do not treat
  multiple same-day linked cards as ambiguity. The correct question is whether
  the prescribed daily dose was met, partially met, missed, or is still
  unresolved.
- Experiment analysis is not a permanent snapshot for active windows.
  It is recomputed after exposure changes and refreshed on read when its
  `analysis_date` is stale.
