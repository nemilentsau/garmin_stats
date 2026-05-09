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

1. Split `app.infra.database` by repository ownership.
   - First candidate: move Garmin biometric read helpers behind the existing
     `SqliteBiometricRepository` boundary.
   - Success signal: domain infra adapters call smaller database primitives or
     repositories instead of unrelated global save/load helpers.

2. Revisit assistant-to-experiments coupling.
   - Current allowlist: `assistant/infra/sqlite_repository.py` reads experiment
     analysis context.
   - Success signal: assistant depends on a read-model/evidence port instead of
     importing experiment analysis internals.

Follow-up implementation plan:
- `docs/superpowers/plans/2026-05-06-domain-ownership-drain-roadmap.md`
  defines the original dependency order for shared-bucket ownership drain.
