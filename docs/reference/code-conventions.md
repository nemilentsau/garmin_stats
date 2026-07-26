# Code Conventions

Cross-cutting structural and documentation conventions. CLAUDE.md links here rather than restating these. Update this file when a convention changes.

## Shared Utilities (`app/utils/`)

`app/utils/` is the only place above the domain layer where general-purpose helpers may live. It exists so two or more domains can share a primitive operation without one domain importing from another.

A helper belongs in `app/utils/` only when **all three** rules hold:

1. **Primitive-only signatures.** Inputs and outputs are language types (numbers, strings, datetimes, sequences, mappings) — never domain models like `DayData`, `DailyMetric`, or `ExperimentExposure`.
2. **No domain vocabulary in names.** Function and type names use generic terms (`safe_avg`, `safe_percentile`, `ScalarSummary`, `now_iso`). Names like `normalize_hrv_status`, `compute_hr_zones`, `classify_recovery` are domain-bound even when small, and stay in their owning domain.
3. **Two or more consumers already need it.** Don't promote on speculation. A helper used by exactly one domain stays in that domain. Promote on the second real consumer, in the same PR that introduces it.

Counter-examples (these belong in a domain, not `app/utils/`):
- `compute_daily_heart_rate(wellness: DayWellness)` — takes a domain type. → `garmin_health/domain/daily_metrics/`.
- `prior_7d_avg(...)` — encodes a period-window concept specific to analytics. → `garmin_analytics/domain/primitives/trends.py`.

Forbidden in `app/utils/`:
- Imports from `app.domains.*`, `app.infra.*`, `app.routers.*`, or `app.bootstrap.*`. Allowed dependencies are stdlib and numpy.
- Functions whose name or signature names a Garmin metric, routine concept, experiment concept, coach concept, or persistence detail.
- Re-exports from a domain (use the domain directly).

Adding a helper here is a deliberate promotion, not a default landing spot. When in doubt, keep it domain-local — promotion is cheap to do later, demotion is not.

## Slice Boundary Convention

Boundary tests guard module intent, not a mandatory folder template. Larger slices may use `api/`, `application/`, and `infra/` packages when those layers contain multiple stable concepts. Small capability slices should stay flatter when subpackages would only hold one file.

- Route modules may import FastAPI and `build_container()`, then pass container-owned dependencies into application use cases.
- `application/` modules must stay FastAPI-free, must not call `build_container()`, and must not import global storage modules, `app.services.*`, or `app.routers.*`.
- `adapters.py` modules are the SQLite or external-system boundary for small flat slices; they should own slice-specific persistence instead of wrapping a shared persistence bucket.
- Transitional slices must be called out in architecture tests and docs with their allowed boundary violations.
- Architecture tests guard route/service boundaries and prevent new imports of removed flat `app.routers.*` or `app.services.*` paths.
- Cross-domain reactions are injected capabilities composed in `bootstrap/`; a source domain such as `garmin_sync` must not import the reacting domain.
- Long-running external model calls belong behind a domain runner and durable job state, not inside request routes. Routes enqueue and return; process runtime owns execution and awaited cancellation.

Each domain's Owns / Does-not-own / May-import / Must-not-import contract lives in that domain's `CHARTER.md` (e.g. `backend/app/domains/garmin_sync/CHARTER.md`).

## Frontend conventions

- Svelte 5 runes
- typed API client in `frontend/src/lib/api.ts`
- generated API types in `frontend/src/lib/api-types.ts` (never hand-write — regenerate via `scripts/generate-api-types.sh`)
- display-only frontend for analytical values: zero statistical computation client-side
- shared chart/color/format helpers in `frontend/src/lib/`
- background operations read backend-owned status and refresh from a feature-specific SSE event; the UI does not infer queue state from local arrays

### Presentation-calibration exception

The display-only rule bars statistical computation client-side, but a narrow class of **client-side order statistics** is in-bounds when it exists purely to calibrate how already-backend-computed values are *drawn* — never to produce a value that is itself displayed as data:

- `tightScale` (`frontend/src/lib/chart-scale.ts`) — takes the min/max (an order statistic) of the chart's own already-backend-computed data points to set tight axis bounds instead of overshooting to round bounds (axes should hug the data, not round outward), then places gridline ticks at round (half-integer) values inside those bounds. The min/max themselves are never rendered; the ticks that are rendered are round grid positions chosen from the range, not a statistic *of* the underlying signal (not a mean, percentile, or smoothed value).
- Map color quantiles (`frontend/src/lib/components/RunRouteMap.svelte`) — bins a route's already-backend-computed pace values into 5 quantile bins of that run's own pace distribution to pick a line color per segment. The quantile edges are never displayed as numbers; they only decide which of 5 fixed colors a segment gets.

Both compute order statistics (min/max, quantile edges) over values the backend already produced, and neither statistic is itself surfaced as a displayed number, label, or derived metric — both are consumed only by rendering code (an SVG viewBox/gridline position, a polyline color). A helper crosses back into forbidden territory the moment its computed statistic could be read as a displayed value (e.g. an on-chart annotation of the computed percentile) rather than purely steering how existing values are drawn.

## Code Documentation Style

- Keep docs current as code moves. When adding or refactoring modules, ports, adapters, or workflow boundaries, update module/class/function docstrings in the same change.
- Match the style in `backend/app/domains/training/` and `backend/app/domains/experiments/`: short module docstring with 1-2 concrete paragraphs explaining what the module owns, what it deliberately delegates, and why that boundary exists.
- Prefer boundary and lifecycle documentation over implementation narration. Good docs explain ownership, injected dependencies, failure/idempotence expectations, and cross-domain callbacks. Avoid comments that restate obvious code.
- Add protocol/class docstrings when a type represents a port, adapter, observer, repository, workflow dependency bundle, or runtime state owner.
- Add function/method docstrings for public use cases and any helper with non-obvious policy, side effects, failure behavior, or ordering constraints. Private one-line helpers with self-evident names do not need filler docs.
- For tests, use a module docstring when the file covers a behavior slice or regression class. Test names should still carry the specific behavior under test.
