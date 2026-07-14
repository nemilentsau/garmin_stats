# Coach

Authoritative description of the shipped local training coach: its evidence boundary,
memory model, durable queue, Codex isolation, and UI/API lifecycle.

## Product boundary

Coach is the app's full assistant surface. It starts from analytics and training data the
app already computes; it does not wait for, own, or recreate a general signal/estimator
engine. The single `CoachReadGateway` delegates to the existing run, recovery, training,
daily-metric, check-in, and note read models. Frontend code displays these results and job
states but computes no analytical values.

Evidence has three explicit levels:

- **Authoritative existing evidence:** run/session/lap/series fields and imperial
  projections, training association and captured status/variant/notes/RPE, recovery
  overview evidence, daily metrics, check-ins, and notes.
- **Descriptive coach transformations:** bounded formatting, whole-session
  distance/duration comparison, source/missingness labels, and static plots.
- **Unavailable in v1:** heat correction, pace-at-fixed-HR adaptation, causal lifting
  interference, plateau detection, predicted recovery, segment-matched compliance, and
  any undeclared estimator. The model must label apparent patterns as observations or
  hypotheses rather than facts.

Plan adjustments are advisory text. Coach never changes an imported training block,
creates training content, schedules measurement retries, or computes measurement
observations and hard gates. The training-owned evidence and schedule behavior are
documented in [run-activities.md](run-activities.md#imported-block-measurement-evaluation).

## Measurement assessments

`ReviewOutput` and `ChatOutput` may include one strict structured
`measurement_assessment`; completed `CoachReview` and coach `CoachMessage` records retain
the same field. It targets one `run_id` plus one runtime `occurrence_key`, classifies the
measurement as `valid`, `provisional`, or `failed`, and requires a non-blank rationale of
at most 1,000 characters. The field stays absent when the conversation does not support a
clear judgment.

Assessment validation and persistence share the review/message completion transaction:

- a run review accepts an assessment only when its run and occurrence exactly match the
  durable run-review target and queued job payload; skip reviews cannot carry one;
- chat accepts an assessment only when the output cites exactly one `run` reference and
  that reference matches `assessment.run_id`. Chat refs do not encode an occurrence, so
  this check cannot independently prove the supplied `occurrence_key`; training's later
  exact-target lookup is the occurrence safety boundary;
- an invalid target rejects the whole model completion. No assessment, completed coach
  review/message, semantic journal entry, or brief is committed. The worker records the
  job as failed; chat writes only its normal failure system message.

Coach persistence returns the newest successful assessment matching the exact
`(run_id, occurrence_key)` pair across completed reviews and completed coach messages.
The read ignores failed jobs and unrelated or assessment-free newer outputs. At bootstrap,
a read-only adapter translates that coach-owned record into training's local
`status`/`rationale`/`source_id` contract; neither domain imports the other's persistence
adapter. The same exact read accepts an optional exclusive cutoff: a local calendar date
is normalized to that day's start in canonical UTC before comparison with stored lifecycle
instants. Training uses this historical view only to freeze authored backup decisions;
ordinary card display still reads the current latest exact assessment.

Training asks for an assessment only for the run currently associated with the exact
runtime occurrence. Detaching the run, linking a different run, or activating a different
event-qualified backup occurrence therefore leaves the old record auditable in Coach but
prevents it from being projected. Coach classifies subjective evidence only: training
computes the observations and gates, clamps any known hard-gate failure to `failed`, and
does not apply a Coach verdict when the full run series is missing. Coach can never
override those boundaries or edit imported training content.

## Hierarchical evidence workspace

Every model call gets a freshly assembled, deterministic workspace rather than a raw
database dump or one giant prompt:

1. evidence capabilities;
2. latest complete brief;
3. recent semantic journal plus compact archive index;
4. current training plan and seven-day target-date window;
5. current recovery overview;
6. a chronological digest of exactly the latest 20 eligible runs;
7. the question and, for chat/distillation, stored transcript.

Each of the 20 digest runs also has on-demand summary, lap, and cached plot files. Those
files are a library: the digest is a menu, and the model opens detail only when it needs
it. An older typed reference can be materialized without entering the 20-run digest.
Run-review workspaces add full current-run summary/laps and plot pages; only those current
pages are initial image attachments. Current pages are also copied into the shared plot
cache so a later `plot:<filename>` reference remains resolvable.

Typed refs are `run`, `plot`, `review`, or `date`. IDs use a strict filename allowlist;
path traversal is rejected. `date` refs materialize training, daily metric, check-in, and
note context. Runtime attempt directories are never deleted during workspace refresh.

## Digest, journal, and brief

These are different memory layers:

- **Digest:** deterministic telemetry index rebuilt from the current latest 20 runs.
- **Journal:** append-only semantic decisions, conclusions, unresolved hypotheses, and
  what to compare next. The newest 10 are included in full; older entries remain archived
  with a compact index. Journal entries are limited to 1,600 characters and must not copy
  run tables or numeric summaries already owned by the digest.
- **Brief:** latest complete model of the training approach and open questions, limited to
  6,000 characters. A new version replaces the prior brief as a whole; it is not patched.

Review and answer Markdown are limited to 12,000 characters. Over-length model output is
failed intact—never truncated—and changes no review, journal, or brief state.

## Durable jobs and review chronology

SQLite owns reviews, threads, messages, journal entries, brief versions, jobs, and one
reconciliation marker. Enqueue, dedupe, claim, success persistence, and failure
persistence are transaction boundaries. A successful review atomically completes its
review/job and appends semantic memory; a failed runner changes no memory. Manual retry
requeues the same durable job and preserves the original review or user message.

One process-local async worker claims one job at a time. Chat priority is ahead of queued
reviews; distillation is behind them. A cancellation propagates into the runner and leaves
the row `running` for startup recovery. Startup requeues work older than 20 minutes up to
three interruption attempts. Open threads idle for six hours queue distillation; success
closes the thread and deletes its Codex home, while failure retains both and becomes
`close_failed` with an explicit retry.

The first enabled reconciliation inspects the inclusive local-date window from today
minus 14 days through today, selects at most the three most recent eligible run/skip
items, then enqueues those selected items oldest-to-newest so journal chronology is
readable. The remaining pre-activation history is manual-only. Later reconciliation
considers only target dates strictly after the saved activation date. Unresolved run
association candidates are not treated as skips.

Evidence dates and prescribed occurrence dates are local calendar dates. Queue,
attempt, message, review, and thread lifecycle instants are canonical UTC strings so
SQLite text ordering stays correct across DST changes. A delayed run review keeps the
original occurrence as `target_date` but uses execution-day recovery as `evidence_date`.

## Codex isolation and runtime files

Each attempt starts `codex exec` in a new process session with a read-only sandbox,
strict structured-output schema, JSON events, and these isolation controls:

- clean `HOME` and auth-only `CODEX_HOME`, preserving only the existing local
  `auth.json` link;
- a copied execution workspace under the system temporary root, outside the app
  repository, containing only the assembled coach evidence for that call;
- user config and exec rules ignored;
- project documentation budget set to zero, preventing repo `AGENTS.md` and unrelated
  analytical skills from inflating or redirecting the coach call;
- no fallback schema guessing or automatic model retry.

Review and distillation use ephemeral Codex sessions. A chat thread uses one persistent
clean home and the probe-confirmed resume session ID; every turn still receives a fresh
outside-repository copy of the refreshed canonical workspace, and the prompt requires
rereading it. On timeout or cancellation the runner sends `SIGTERM` to the whole process
group, waits up to five seconds, then sends `SIGKILL`; process shutdown awaits that
cleanup.

Runtime files live beside the configured database under `coach/`: workspaces, shared
plot cache, thread Codex homes, and attempt logs. Attempts are keyed by job ID and attempt
number, so stale output from another attempt cannot be accepted. Temporary execution
workspace copies are removed after each call. Plot filenames include a source-content
fingerprint and rendering-spec version.

`GARMIN_COACH_WORKER_ENABLED` accepts exactly `true` or `false` and defaults to `true`.
Set it to `false` during reload-heavy development to prevent automatic model spend;
history and manual enqueue APIs remain readable, and `/api/coach/status` reports the
paused state.

## API and UI

The `/api/coach/*` API exposes status, review history/manual run enqueue/retry, durable
jobs, threads/messages/close/retry-close, journal, and brief. Model operations return
immediately as queued resources. `/coach` observes completion through the coach-specific
SSE event and displays written states (`queued`, `generating`, `failed`, `closing`,
`close_failed`, `closed`) rather than relying on color. `/runs/[id]` resolves one review
directly and shows either **Review with coach** or **Open coach review**.

The `/api/assistant/artifacts*` prefix remains for compatibility, but those routes belong
to the independent `artifacts` domain. There is no assistant chat domain, route, UI, or
data model.
