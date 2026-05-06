# Backlog

This file tracks active parked work only. Completed implementation notes belong
in the code, tests, or current architecture docs.

## 1. Add Daily Check-In UI On `/today`

See [checkin-todo.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/checkin-todo.md).

Reason:

- backend check-in support already exists
- assistant and experiment analysis both benefit from subjective context
- there is currently no frontend entry surface

Recommended shape:

- compact `Daily Check-In` card on `/today`
- today-first entry flow
- preserve the existing `/api/checkins` contract

## Architecture Cleanup Queue

Selection rule: the next cleanup must reduce coupling, shrink a shared bucket, or
make an illegal dependency executable in tests. Package renames do not qualify by
themselves.

1. Split `app.stats` by ownership.
   - First candidate: move Garmin-only period/window helpers behind
     `domains/garmin_analytics` contracts.
   - Success signal: one fewer file imports `app.stats`, and
     `test_architecture_global_ownership.py` allowlist shrinks.

2. Split `app.models` by ownership when a touched contract clearly belongs to one
   module.
   - First candidate: move journal check-in/note contracts near `domains/journal`
     because the slice is small and already has clear API/application boundaries.
   - Next candidates: `core/profile` or `domains/programs`, whichever is touched
     first during feature work.
   - Success signal: one fewer contract family remains in `app.models`, and no
     frontend API type diff appears except stable regeneration order.

3. Split `app.infra.database` by repository ownership.
   - First candidate: move Garmin biometric read helpers behind the existing
     `SqliteBiometricRepository` boundary.
   - Success signal: domain infra adapters call smaller database primitives or
     repositories instead of unrelated global save/load helpers.

4. Revisit assistant-to-experiments coupling.
   - Current allowlist: `assistant/infra/sqlite_repository.py` reads experiment
     analysis context.
   - Success signal: assistant depends on a read-model/evidence port instead of
     importing experiment analysis internals.

Follow-up implementation plan:
- `docs/superpowers/plans/2026-05-06-domain-ownership-drain-roadmap.md`
  defines the dependency order for draining `app.models`, `app.stats`, and
  `app.infra.database` without creating new shared buckets.
