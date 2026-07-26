# Coach

Authoritative description of the shipped local training coach: its evidence boundary,
memory model, durable queue, revision history, Codex isolation, and UI/API lifecycle.

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

Training recommendations are advisory text. Coach never changes an imported training block,
creates training content, schedules measurement retries, or computes measurement
observations and hard gates. The training-owned evidence and schedule behavior are
documented in [run-activities.md](run-activities.md#imported-block-measurement-evaluation).

## Review judgment

Coach judges the purpose of the workout rather than auditing every prescription field.
New reviews use these outcomes:

- `completed_as_intended`: the intended training stimulus was materially achieved;
- `completed_with_material_deviation`: the session was completed, but a deviation changes
  its training meaning or next decision;
- `not_completed`, `skipped`, and `unplanned`: explicit execution states.

Confidence (`low`, `moderate`, or `high`) is independent of outcome. Missing notes, RPE,
variant capture, or exact segment markers can lower confidence when they could change a
decision; they do not automatically downgrade a run. Exact values become hard validity
boundaries only when the imported contract declares a measurement quality gate or another
explicit hard gate. Thus a plausible controlled stride near a 20-second target is judged
by its neuromuscular purpose, while an LTHR measurement gate retains exact validity
semantics.

Garmin time-in-zone totals are descriptive evidence, not a continuous measure of distance
from a boundary. Boundary-sensitive intensity judgments use the attached composite HR
trace and sample distribution. A free-form authored zone label is not mapped to a Garmin
zone unless the imported contract declares that mapping; an explicit authored `hr_range`
is directly comparable. Missing RPE leaves an authored RPE ceiling unresolved rather than
establishing that it was exceeded, and visible HR drift is an observation rather than an
automatic material deviation.

The model may ask at most two athlete questions, and only when an answer could change
safety, formal measurement validity, or the next training decision. It must not request
forensic confirmation of every prescribed detail. Review output stores outcome,
confidence, direct coaching prose, up to two decision-changing `follow_up_questions`,
historical evidence used, curated refs, structured journal memory, and an explicit brief
action. The completed `CoachReview` persists those `follow_up_questions` verbatim and the
`/api/coach/reviews*` endpoints surface them so the UI can show what the model still wants
resolved. Visual evidence is recorded as bounded `plot_observations`: each entry names an
attached image basename and the concrete visible pattern that affected the judgment.
Unused attachments are omitted, and a review may legitimately record no plot observations.
The handler rejects any observation that names an image outside the current attachment
manifest. Completed rows retain only the observations; the legacy `plots_viewed` basename
list has been retired, and a startup migration strips the key from any older persisted
row so strict validation continues to accept it. A current-run plot ref and observation
must correspond in both directions;
unattached refs, attachment-inventory refs without observations, and observations without
direct refs fail the attempt. The Coach review surface loads the exact persisted PNG named
by each observation from a basename-only read route and shows it with the bounded evidence
ledger beneath the review. It never recomputes a substitute from current run data; a
missing image leaves the textual observation visible with an unavailable state. The former
`compliant`/`partial`/`non_compliant` verdict remains readable only on legacy review rows.

## Measurement assessments

`ReviewOutput` and `ChatOutput` may include one strict structured
`measurement_assessment`; completed `CoachReview` and coach `CoachMessage` records retain
the same field. It targets one `run_id` plus one runtime `occurrence_key`, classifies the
measurement as `valid`, `provisional`, or `failed`, and requires a non-blank rationale of
at most 1,000 characters. The field stays absent when the conversation does not support a
clear judgment.

Assessment validation and persistence share the review/message completion transaction:

- a run review accepts an assessment only when its run and occurrence exactly match the
  durable run-review target and queued job payload;
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

A review assessment is ordered by the instant its *current* status first appeared, held in
the `assessment_effective_at` column, not by the `updated_at` that every later revision
moves. That instant is the review's first completion for as long as the assessment's status
is unchanged since then. A revision that changes the status — adding an assessment to a
review that had none, or flipping e.g. failed to valid — moves the instant to that revision,
because the fact it dates is genuinely new; leaving it at first completion would retroactively
re-derive an already-made backup decision. A revision that only rewords the rationale, with
the status unchanged, never moves it, so already-derived backup decisions and their saved
logs stay put.

Training asks for an assessment only for the run currently associated with the exact
runtime occurrence. Detaching the run, linking a different run, or activating a different
event-qualified backup occurrence therefore leaves the old record auditable in Coach but
prevents it from being projected. Coach classifies subjective evidence only: training
computes the observations and gates, clamps any known hard-gate failure to `failed`, and
does not apply a Coach assessment when the full run series is missing. Coach can never
override those boundaries or edit imported training content.

## Hierarchical evidence workspace

Every model call gets a freshly assembled, deterministic workspace rather than a raw
database dump or one giant prompt:

1. evidence capabilities;
2. latest active policy-v2 brief;
3. active policy-v2 semantic journal plus compact archive index;
4. current training plan and seven-day target-date window;
5. current recovery overview;
6. a chronological digest of exactly the latest 20 eligible runs;
7. the question and, for chat/distillation, stored transcript.

Each of the 20 digest runs also has on-demand summary, lap, and cached plot files. Those
files are a library: the digest is a menu, and the model opens detail only when it needs
it. The journal and brief are retrieval guides, not source evidence. Before making a
historical claim, the model opens the selected run's summary and relevant laps or plot,
then records a bounded selection reason and one of `same_purpose`, `recent_clean`,
`counterexample`, or `plan_anchor`. A routine local judgment may use no comparator; a
longitudinal claim requires relevant history, and a plan change seeks both support and a
counterexample when the digest contains one. An older typed reference can be materialized
without entering the 20-run digest.
Run-review workspaces add full current-run summary/laps and plot pages; only those current
pages are initial image attachments. Current pages are also copied into the shared plot
cache so a later `plot:<filename>` reference remains resolvable.

FIT time-in-zone arrays remain canonical in the Garmin health record, including bucket
zero for time below the first configured zone. The analytics read model projects those
arrays once into numbered, high-exclusive display zones, folds overflow into the final
open-ended zone, and preserves missing duration separately from zero. The run UI and the
Coach current-run summary both consume that same projection; neither reinterprets raw FIT
bucket indexes independently. Current-run Coach attachments lead with a pace/HR/distribution
composite that labels these boundaries and reports backend Q1, median, Q3, P90, and sample
coverage; supplemental measured channels follow on later pages. Historical run panels use
the same intensity evidence.

Typed refs are `run`, `plot`, `review`, or `date`. IDs use a strict filename allowlist;
path traversal is rejected. `date` refs materialize training, daily metric, check-in, and
note context. Runtime attempt directories are never deleted during workspace refresh.
Each stored ref resolves independently: a ref that no longer resolves (a deleted run, an
evicted plot cache entry, a rejected unsafe ID) is skipped and listed in
`refs/unavailable.md` rather than failing the whole assembly, so one stale persisted
reference cannot block every future coach job.

## Digest, journal, and brief

These are different memory layers:

- **Digest:** deterministic telemetry index rebuilt from the current latest 20 runs.
- **Journal:** append-only structured interpretation: workout purpose, outcome, durable
  takeaway, decision-relevant uncertainties, follow-up/expiry triggers, comparison tags,
  and curated refs. The newest 10 are included in full; older entries remain archived
  with a compact purpose/outcome/tag/ref index. Journal entries are limited to 1,600
  characters and must not copy run tables or numeric summaries already owned by the
  digest.
- **Brief:** latest complete model of the training approach and open questions, limited to
  6,000 characters. Every review and distillation explicitly chooses `keep` or `replace`;
  routine sessions normally keep the current brief. A replacement is a complete version,
  not a patch.

Current semantic memory uses policy version 2. Legacy records default to version 1 and
remain stored and individually readable for audit, but they do not enter new workspaces or
the current journal/brief API.

Review and answer Markdown are limited to 12,000 characters. Over-length model output is
failed intact—never truncated—and changes no review, journal, or brief state.

## Durable jobs and review chronology

SQLite owns reviews, immutable review revisions, threads, messages, journal entries,
brief versions, and jobs. Enqueue, dedupe, claim, success persistence, and failure
persistence are transaction boundaries. A successful review atomically completes its
review/job, creates revision 1, and appends semantic memory; a failed runner changes no
memory. Manual retry requeues a failed durable job and preserves the original review or
user message.

Reviews are manual-only. The run page's **Review with coach** action is the sole review
trigger. Activity sync, upload, startup, watcher refresh, elapsed schedule dates, and Today
feedback persistence never enqueue Coach or infer a missed run.

Every completed review can have one reusable linked conversation inline on the review
surface. Opening or refreshing the review is read-only: the thread is created only when
the athlete sends the first message. Ordinary questions and explanations append messages
without changing the review.
Only a message beginning with `Update the review:` durably authorizes structured
`review_revision` output; prompt compliance alone is never sufficient. That output
must replace the complete review-owned snapshot: content, outcome, confidence, refs,
questions, plot observations, historical evidence, and any exact measurement assessment.
The handler validates direct and historical plot refs against the exact linked workspace;
matching a made-up ref to a made-up observation is not sufficient. It atomically appends
an immutable numbered revision and updates the current review. Prior versions expose the
complete audit snapshot in the UI. Rows written before complete snapshots were introduced
are explicitly marked as legacy partial snapshots instead of treating absent fields as
known-empty. The linked workspace includes the full persisted review as
`current-review.md`, the original run evidence, and the complete transcript so new athlete
context can be applied deliberately.

One process-local async worker claims one job at a time. Chat priority is ahead of queued
reviews; distillation is behind them. A cancellation propagates into the runner and leaves
the row `running` for startup recovery. Startup requeues every job still marked `running`
(a single-process deployment cannot have one legitimately running at boot) up to
three interruption attempts. Past that limit the job fails, and a failed distillation
carries its `closing` thread to `close_failed` the same way a worker failure does — a
thread never stays `closing` without a job to run. An explicit retry restores the whole
attempt budget. Open general threads idle for six hours queue distillation; success
closes the thread and deletes its Codex home, while failure retains both and becomes
`close_failed` with an explicit retry. Marking a thread `closing` and queueing its
distillation are separate transactions, so a failure between them also lands on
`close_failed`; retry-close then queues a fresh job. Review-linked conversations stay
available for future corrections and are not auto-distilled or closed.

Evidence dates and prescribed occurrence dates are local calendar dates. Queue,
attempt, message, review, and thread lifecycle instants are canonical UTC strings so
SQLite text ordering stays correct across DST changes. A delayed run review keeps the
original occurrence as `target_date` but uses execution-day recovery as `evidence_date`.

## Codex isolation and runtime files

Each attempt starts `codex exec` in a new process session with strict
structured-output schema, JSON events, and these isolation controls. A
read-only sandbox and a fresh workspace directory (`--sandbox read-only -C
<workspace>`) are passed only on non-resumed sessions; a resumed chat turn
reuses the already-sandboxed persistent session instead of re-declaring it:

- clean `HOME` and auth-only `CODEX_HOME`, preserving only the existing local
  `auth.json` link;
- a copied execution workspace under the system temporary root, outside the app
  repository, containing only the assembled coach evidence for that call;
- user config and exec rules ignored;
- model defaults to `gpt-5.6-sol` with `xhigh` reasoning, overridable via the
  `COACH_CODEX_MODEL` environment variable; lowering the production reasoning
  effort requires a code change rather than a user-config override;
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

The `/api/coach/*` API exposes status, review history/manual run enqueue/retry,
review-linked thread/revision history, general threads/messages/close/retry-close,
and current-policy brief. Jobs and the semantic journal
stay durable SQLite records with no standalone read route; a job's lifecycle rides along on
its owning review/message/status response instead, and no product surface reads the journal
directly. Model operations return
immediately as queued resources. `/coach` observes completion through the coach-specific
SSE event and displays written states (`queued`, `generating`, `failed`, `closing`,
`close_failed`, `closed`) rather than relying on color. It displays outcome and confidence
separately and falls back to the legacy verdict when needed. A completed review shows its
composer and any existing linked transcript inline, with readable narrative and audit
fields for every version when corrections exist. Viewing it does not create a thread;
sending the first message does.
`/runs/[id]` resolves one review
directly and shows either **Review with coach** or **Open coach review**.
On `/today`, feedback capture remains training state only and never triggers Coach.

There is no assistant chat or artifact domain, route, UI, or data model. Coach owns the
only model-backed product surface.
