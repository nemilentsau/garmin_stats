# Coach Domain Charter

## Owns

- Durable coach reviews, conversations, semantic journal entries, briefs, and jobs.
- Hierarchical evidence workspaces assembled from existing read models.
- Codex execution, output validation, and coach-specific runtime lifecycle.

## Does not own

- Garmin parsing, analytical calculations, training prescriptions, or artifact import.
- Authoritative run, recovery, routine, experiment, check-in, or note storage.
- Training-content creation or activation.

## May import

- Shared contracts and SQLite primitives.
- Existing domain application read models through `read_gateway.py` only.
- Bootstrap composition only at route/container boundaries.

## Must not import

- Retired assistant modules.
- FIT parser internals.
- Other domains' persistence adapters outside the bootstrap-injected gateway.

## Public entrypoints

- `routes.py` for `/api/coach` HTTP operations.
- `application/jobs.py` for enqueue/reconciliation behavior.
- `application/worker.py` for process-owned queued execution.
