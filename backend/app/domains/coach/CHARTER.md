# Coach Domain Charter

## Owns

- Durable coach reviews, conversations, semantic journal entries, briefs, and jobs.
- Hierarchical evidence workspaces assembled from existing read models.
- Codex execution, output validation, and coach-specific runtime lifecycle.
- Strict optional measurement-assessment validation and atomic persistence
  with the successful review or coach message that produced it.
- Newest-successful assessment reads for one exact
  `(run_id, occurrence_key)` target.

## Does not own

- Garmin parsing, measurement observations/gates, analytical calculations,
  program scheduling, training prescriptions, or artifact import.
- Authoritative run, recovery, routine, experiment, check-in, or note storage.
- Training-content creation, editing, activation, backup substitution, or
  estimator eligibility. Coach classifies evidence; it does not change the
  imported program.

## May import

- Shared contracts and SQLite primitives.
- Existing domain application read models through `read_gateway.py` only.
- Bootstrap composition only at route/container boundaries.

## Must not import

- Retired assistant modules.
- FIT parser internals.
- Other domains' persistence adapters outside the bootstrap-injected gateway.

## Bootstrap boundary

Training never imports Coach persistence. Bootstrap adapts
`latest_measurement_assessment(run_id, occurrence_key)` into training's
read-only assessment contract (`status`, `rationale`, `source_id`) and injects
that port into training reads. Coach does not perform training's hard-gate
clamp, missing-series policy, or schedule overlay; see
`docs/reference/run-activities.md`.

## Public entrypoints

- `routes.py` for `/api/coach` HTTP operations.
- `application/jobs.py` for enqueue/reconciliation behavior.
- `application/worker.py` for process-owned queued execution.
