# Coach Domain Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes it.**

## Owns

- Durable coach reviews, conversations, semantic journal entries, briefs, and jobs.
- Hierarchical evidence workspaces assembled from existing read models.
- Codex execution, output validation, and coach-specific runtime lifecycle.
- Strict optional measurement-assessment validation and atomic persistence
  with the successful review or coach message that produced it.
- Idempotent run-review enqueue after explicit Today feedback submission,
  durable recovery of a failed immediate enqueue from that manual completion,
  and bounded automatic skipped-run reconciliation. Tracked-run discovery alone
  never queues a review.
- Newest-successful assessment reads for one exact
  `(run_id, occurrence_key)` target, optionally before an exclusive cutoff.

## Does not own

- Garmin parsing, measurement observations/gates, deterministic estimators,
  training scheduling/prescriptions, or artifact import.
- Authoritative run, recovery, routine, experiment, check-in, or note storage.
- Training-content creation, editing, activation, backup substitution, or
  estimator eligibility. Coach classifies evidence; it does not change the
  imported training content.

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
`latest_measurement_assessment(run_id, occurrence_key, *, before=None)` into
training's read-only assessment contract (`status`, `rationale`, `source_id`)
and injects that port into training reads. Coach owns cutoff normalization;
it does not perform training's hard-gate clamp, missing-series policy, or
schedule overlay; see
`docs/reference/run-activities.md`.

## Public entrypoints

- `routes.py` for `/api/coach` HTTP operations.
- `application/jobs.py` for explicit feedback/manual enqueue, submitted-feedback
  recovery, and skipped-run reconciliation behavior.
- `application/worker.py` for process-owned queued execution.
