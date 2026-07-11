# Code Conventions

Cross-cutting structural and documentation conventions. CLAUDE.md links here rather than restating these. Update this file when a convention changes.

## Shared Utilities (`app/utils/`)

`app/utils/` is the only place above the domain layer where general-purpose helpers may live. It exists so two or more domains can share a primitive operation without one domain importing from another.

A helper belongs in `app/utils/` only when **all three** rules hold:

1. **Primitive-only signatures.** Inputs and outputs are language types (numbers, strings, datetimes, sequences, mappings) — never domain models like `DayData`, `DailyMetric`, `RoutineCard`, or `ExperimentExposure`.
2. **No domain vocabulary in names.** Function and type names use generic terms (`safe_avg`, `percentile_rank`, `ScalarSummary`, `now_utc`). Names like `normalize_hrv_status`, `compute_hr_zones`, `classify_recovery` are domain-bound even when small, and stay in their owning domain.
3. **Two or more consumers already need it.** Don't promote on speculation. A helper used by exactly one domain stays in that domain. Promote on the second real consumer, in the same PR that introduces it.

Counter-examples (these belong in a domain, not `app/utils/`):
- `compute_daily_heart_rate(wellness: DayWellness)` — takes a domain type. → `garmin_health/domain/daily_metrics/`.
- `prior_7d_avg(...)` — encodes a period-window concept specific to analytics. → `garmin_analytics/domain/primitives/trends.py`.
- `format_routine_card_label(card)` — single consumer + domain type. → `routines/`.

Forbidden in `app/utils/`:
- Imports from `app.domains.*`, `app.infra.*`, `app.routers.*`, or `app.bootstrap.*`. Allowed dependencies are stdlib and numpy.
- Functions whose name or signature names a Garmin metric, routine concept, experiment concept, assistant concept, or persistence detail.
- Re-exports from a domain (use the domain directly).

Adding a helper here is a deliberate promotion, not a default landing spot. When in doubt, keep it domain-local — promotion is cheap to do later, demotion is not.

## Slice Boundary Convention

Boundary tests guard module intent, not a mandatory folder template. Larger slices may use `api/`, `application/`, and `infra/` packages when those layers contain multiple stable concepts. Small capability slices should stay flatter when subpackages would only hold one file.

- Route modules may import FastAPI and `build_container()`, then pass container-owned dependencies into application use cases.
- `application/` modules must stay FastAPI-free, must not call `build_container()`, and must not import global storage modules, `app.services.*`, or `app.routers.*`.
- `adapters.py` modules are the SQLite or external-system boundary for small flat slices; they should own slice-specific persistence instead of wrapping a shared persistence bucket.
- Transitional slices must be called out in architecture tests and docs with their allowed boundary violations.
- Architecture tests guard route/service boundaries and prevent new imports of removed flat `app.routers.*` or `app.services.*` paths.

Each domain's Owns / Does-not-own / May-import / Must-not-import contract lives in that domain's `CHARTER.md` (e.g. `backend/app/domains/garmin_sync/CHARTER.md`).

## Frontend conventions

- Svelte 5 runes
- typed API client in `frontend/src/lib/api.ts`
- generated API types in `frontend/src/lib/api-types.ts` (never hand-write — regenerate via `scripts/generate-api-types.sh`)
- display-only frontend for analytical values: zero statistical computation client-side
- shared chart/color/format helpers in `frontend/src/lib/`

## Code Documentation Style

- Keep docs current as code moves. When adding or refactoring modules, ports, adapters, or workflow boundaries, update module/class/function docstrings in the same change.
- Match the style in `backend/app/domains/routines/` and `backend/app/domains/experiments/`: short module docstring with 1-2 concrete paragraphs explaining what the module owns, what it deliberately delegates, and why that boundary exists.
- Prefer boundary and lifecycle documentation over implementation narration. Good docs explain ownership, injected dependencies, failure/idempotence expectations, and cross-domain callbacks. Avoid comments that restate obvious code.
- Add protocol/class docstrings when a type represents a port, adapter, observer, repository, workflow dependency bundle, or runtime state owner.
- Add function/method docstrings for public use cases and any helper with non-obvious policy, side effects, failure behavior, or ordering constraints. Private one-line helpers with self-evident names do not need filler docs.
- For tests, use a module docstring when the file covers a behavior slice or regression class. Test names should still carry the specific behavior under test.
