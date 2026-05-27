# Finding Analyst Phase 1

This document defines the first phase of the Garmin Stats analyst workflow. It
is a workflow and quality plan, not an implementation plan. Two goals run in
parallel: make analyst runs produce durable, reviewed evidence, *and* actively
help the analyst find new things in the data. Headless runners and frontend
promotion stay deferred until the manual contract has survived real use.

> **Naming.** "Insight" is already used by `backend/app/domains/garmin_analytics/domain/insights/` for rule-based per-day dashboard cards. To avoid collision, analyst-discovered observations are called **findings**. The skill, run directory, and file names follow the same convention. The original draft of this plan used "insight"; this revision renames it.

## Vocabulary

- **Finding** — an analyst-authored, evidence-backed observation about the dataset. Findings live in run folders until promoted; promoted findings live in `FINDINGS.md`.
- **Insight** — a computed, rule-based per-day callout produced by `backend/app/domains/garmin_analytics/domain/insights/` and surfaced in the frontend. Not authored by an analyst.
- **Analyst run** — one investigation, scoped to a question and a date window, that produces one run folder under `.claude/finding-runs/`.
- **Recipe** — a named analytical technique with declared inputs and outputs. Recipes give analysts a vocabulary for *how* they investigated, separate from *what* they investigated.
- **Scout pass** — a lightweight multi-recipe scan that proposes candidate questions without trying to settle any of them. Seeds the question backlog.

## Goals

The plan has two halves.

**Discovery half** (the new emphasis):

- Maintain an open question backlog as the analyst's prompt source.
- Provide a recipe catalog so analysts apply known-good techniques instead of reinventing.
- Run scout passes that propose candidate findings before any deep dive.
- Make broad-review passes structurally easy so anomalies, regime shifts, and unmodeled relationships get surfaced.

**Documentation half** (the original plan's scope):

- Each analyst run produces a structured run folder.
- `FINDINGS.md` is the curated, reviewed analytical memory.
- Quality gates enforce statistical, visual, and interpretation discipline before promotion.

## Non-Goals

- No frontend finding cards or promoted finding records in this phase.
- No backend API schema changes for finding storage in this phase.
- No headless recurring scan runner yet.
- No generic machine-learning harness or benchmark-style orchestration.
- No model-building unless a specific question requires it and the run explains why simpler descriptive or statistical tests are insufficient.

## Relationship to Existing Code

Phase 1 runs alongside existing analytics code without modifying it:

- `backend/app/domains/garmin_analytics/domain/insights/` (HRV, heart rate rule-based per-day cards) — untouched. Those are dashboard "insights" in the rule-based sense.
- `backend/app/domains/garmin_analytics/domain/analysis/` (hrv_patterns, stress, body_battery, sleep, hrv) — reusable statistical building blocks. Analyst scripts may import from here; analyst runs do not extend these modules.
- `backend/app/domains/garmin_analytics/domain/aggregates/` and `domains/garmin_health/domain/daily_metrics/` — source of statistical truth for per-day metric values. Analyst scripts should consume persisted daily metrics (via the API or directly via the repository) rather than re-aggregating from raw FIT files unless the question requires raw readings.

When an analyst run repeatedly reaches for a calculation that doesn't exist in `domain/analysis/`, that is a signal to add it there — but only after the second time the same code is rewritten, and never as part of the same analyst run that needs it.

## Analyst Run Types

### Question-Led Investigation

User (or backlog) supplies a concrete question. The run is scoped to the question, declares whether it is exploratory or hypothesis-testing, and either ends with a candidate finding or with a documented "no signal." Hypothesis-testing runs pre-register their prediction and decision rule before opening any data (see Quality Gates).

Examples:

- What changed around the November 2025 suppression window?
- Does respiration on day D predict HRV on day D+1?
- Is the late-April SpO2 cluster a sensor issue or a real cluster?

### Manual Exploratory Review

User asks for a broader review of a dataset area — HRV, sleep, stress, recovery windows, SpO2. The run uses one or more recipes from the catalog. Every candidate finding is labeled exploratory and goes through the same gates, but pre-registration is replaced by recipe declaration ("I will apply recipes A, B, C to this slice").

### Scout Pass

A lightweight scan across multiple recipes on the current dataset that produces a ranked list of candidate signals worth investigating. A scout pass does not promote findings — its job is to feed the question backlog. Scout passes are the primary discovery mechanism; a healthy Phase 1 runs them periodically.

### Future Recurring Scan

Recurring scans remain deferred. When the artifact contract is stable, a headless runner can reuse this phase's contract to run scout passes on a schedule.

## Analytical Recipes

The recipe catalog is the lever that turns "well-documented analysis" into "more analysis happening." It lives at `.claude/skills/finding-analyst/RECIPES.md` as a living document.

Each recipe specifies:

- **Name** and one-line description.
- **Question shape** it answers.
- **Inputs** — metrics, date window, baseline reference.
- **Outputs** — what kind of finding it can produce, with quantitative shape.
- **Method** — short paragraph citing `numpy` / `pandas` / `scipy.stats` / `statsmodels` / `ruptures` (or equivalent).
- **Caveats** — known failure modes; when not to use it.
- **Validation** — visual or numeric sanity check the analyst runs before trusting output.

Phase 1 seeds the catalog with eight recipes:

| Recipe | Question shape |
| --- | --- |
| **Anomaly window** | Which date windows had simultaneous deviation across N metrics versus baseline? |
| **Change-point** | When did the baseline of metric X shift? |
| **Lagged correlation** | Does metric A on day D predict metric B on day D+k for k in 1..7? |
| **Period comparison** | What separates the best 14-day window from the worst, by effect size? |
| **Missingness pattern** | When does metric X drop out, and does dropout covary with other state? |
| **Distribution shape** | Is metric X unimodal, bimodal, or skewed? Does the shape change by month? |
| **Day-type clustering** | What recovery-day archetypes exist across the dataset? |
| **Trigger search** | Within a known bad window, which metrics shifted first and by how much? |

Recipes are vocabulary, not procedures. They give the analyst names for what they are doing and give reviewers something to audit. A recipe is added to the catalog only after it has been used in at least one real run — speculation does not earn an entry.

## Question Backlog

`FINDINGS.md` already has an `Open Questions` section. Phase 1 formalizes it:

- Open questions live in `FINDINGS.md` § `Open Questions`. Each is one line, optionally tagged with a metric area.
- When an analyst run resolves a question, its `07-findings-update.md` moves the question from `Open Questions` to a new `Resolved Questions` subsection with a back-reference to the run folder.
- Anyone can add questions at any time. Scout passes are the primary feeder.
- Questions that resist investigation across two attempts move to a `Parked Questions` subsection with a one-line note on why.

## Required Run Artifacts

Every run lives at:

```
.claude/finding-runs/YYYY-MM-DD-<topic>-<slug>/
```

`<topic>` is a one-word metric area (`hrv`, `sleep`, `recovery`, `spo2`, `multi`, `scout`) so the directory is grepable.

### Minimal Run (all run types)

```
01-question.md
03-analysis.py            (or 03-analysis.ipynb with exported .py)
04-plots/
05-findings.md
```

### Extended Run (required for `FINDINGS.md` promotion)

Adds:

```
02-data-profile.md
06-review.md
07-findings-update.md
08-snapshot/              (gitignored; pinned data the finding rests on)
```

Scout passes stay minimal. Question-led runs that end with "no signal" stay minimal. Only runs that propose a `FINDINGS.md` edit must include the extended files. This tiering keeps ceremony proportional to claim weight.

### `01-question.md`

User question, date window, metrics in scope, context sources in scope, explicit exclusions, declared run type.

**For hypothesis-test runs** — pre-registration block: the specific prediction, the decision rule (what evidence would falsify), the pre-registered set of comparisons. Written before any data is opened.

**For exploratory runs** — recipe declaration: which recipes from the catalog will be applied to this slice. Recipe choices may change mid-run, but additions must be recorded as they happen.

**For scout passes** — recipe set and breadth: which recipes will sweep across which metrics, and how candidate signals will be ranked.

### `02-data-profile.md` *(extended runs only)*

Data source (live API, sqlite snapshot, parquet export), snapshot timestamp, row counts, date boundaries per metric, coverage and missingness per metric, units, known sensor/parser caveats, filters applied.

### `03-analysis.py` or `03-analysis.ipynb`

Reproducible analysis. Notebooks are allowed; if used, an exported `.py` companion with cleared outputs must be committed alongside. The script header declares its data source explicitly:

```python
# DATA: live backend at 2026-05-22T14:30Z
# or
# DATA: snapshot at .claude/finding-runs/<run>/08-snapshot/daily.parquet
```

All figures save under `04-plots/` with content-bearing filenames (`hrv-vs-stress-lag.png`, not `figure_3.png`).

### `04-plots/`

Plots used as evidence. Every plot has a title, units on every axis, the date range, and the smoothing window (if any). An unannotated plot is not evidence.

### `05-findings.md`

For each finding (a single run may produce zero, one, or several):

- **Claim** — one sentence.
- **Evidence** — concrete numbers (effect size + spread + sample size), chart references.
- **Method** — which recipe(s) produced it.
- **Interpretation** — what it means; "so what."
- **Caveats** — alternative explanations, confounders, missingness, multiple-comparisons posture.
- **Confidence** — `tentative` / `provisional` / `confident`.
- **Promotion recommendation** — `keep in run folder` or `propose FINDINGS.md update`.

**Confidence levels:**

- `tentative` — single recipe, no replication, exploratory context. Stays in run folder.
- `provisional` — multiple recipes converge, or a hypothesis-test passes its pre-registered rule. Stays in run folder pending review.
- `confident` — provisional plus a passing extended-run review. Eligible for `FINDINGS.md`.

### `06-review.md` *(extended runs only)*

Self-review pass. Walks the six gates explicitly and concludes with `promote` or `do not promote`. Confidence levels may be downgraded here; they may not be upgraded.

### `07-findings-update.md` *(extended runs only)*

The exact proposed `FINDINGS.md` patch as a diff or quoted before/after. Includes:

- The new or updated takeaway.
- Any `Open Questions` → `Resolved Questions` move triggered by this run.
- Any retraction of a prior takeaway invalidated by this run.

### `08-snapshot/` *(extended runs only, gitignored)*

A frozen copy of the daily metric mart (parquet or csv) the finding was made against. Lets a future reviewer reproduce the numbers even after the underlying dataset grows. Gitignored because of size; referenced by filename in `02-data-profile.md`.

## Reproducibility & Snapshots

Findings are claims about specific data. Two rules keep them reproducible:

1. Every `03-analysis.py` declares its data source in its header (see above).
2. Promoted findings carry a snapshot in `08-snapshot/`. Re-running a script six months later may produce different numbers because data grew; the snapshot lets a reviewer verify the original numbers against the original dataset.

## Quality Gates

A run targeting `FINDINGS.md` is not complete until all gates pass.

### Question Gate

- Question stated in concrete terms.
- Date range and metrics explicit.
- Run type declared (exploratory / hypothesis-test / scout).
- Hypothesis-test runs include pre-registration in `01-question.md`.

### Data Gate

- Data source named and snapshot pinned.
- Coverage and missingness measured for every metric used in a claim.
- Nulls, zeros, impossible values, and parser caveats addressed.
- Filtering rules state what population they exclude.

### Statistical Gate

- Summary stats include sample size and spread, not just averages.
- Skewed distributions use median and IQR.
- Outliers investigated, capped, excluded, or retained with documented reason.
- Correlations are not described as causal.
- Claims about change compare against a relevant baseline window, not only a nearby anecdotal window.
- **Effect size before p-value.** Quantify the magnitude of the effect (mean diff, r, Cohen's d, etc.) before invoking any significance language.
- **Multiple-comparisons posture.** For exploratory runs that scanned N comparisons (correlation sweeps, recipe scans across metric pairs), the finding states N and acknowledges that some "significant" results are expected by chance. A single eye-catching result from a many-comparison sweep is `tentative`, not `provisional`. Replicating the finding on a held-out window or via a different recipe can raise it to `provisional`.

### Visual Gate

- Every plot used in a finding is opened and visually inspected.
- Axes have units and sensible ranges.
- Gaps not connected in ways that imply unobserved trends.
- At least two or three plotted values spot-checked against source data.
- Review records whether the plot supports, weakens, or complicates the written finding.

### Interpretation Gate

- Each finding has a clear "so what."
- Caveats and plausible alternative explanations named.
- Exploratory discoveries labeled exploratory.
- Health interpretations stay descriptive; no medical advice.

### Findings Gate

- Only `confident` findings promote to `FINDINGS.md`.
- Tentative and provisional findings stay in the run folder.
- Promotion includes snapshot date, date range, sample size, and caveats.
- If the run resolves an open question, that move is part of the same patch.

## FINDINGS.md Update Semantics

`FINDINGS.md` is a living document with three sections that update on different cadences:

1. **Distribution Snapshot, Temporal Observations, Cross-Metric Relationships** — periodic full rebuild. When the snapshot date is bumped (currently roughly monthly), these sections are regenerated against the current dataset. Prior snapshots are not retained inline; the most recent supersedes.

2. **Analytical Takeaways** — append-only with attribution. Each takeaway carries the snapshot date it was added and, when promoted from an analyst run, the run folder name. Takeaways stay until explicitly retracted.

3. **Open Questions, Resolved Questions, Parked Questions** — append-only with state transitions. Questions never disappear; they move between subsections.

**Retraction.** When a new run invalidates a previously promoted takeaway, the takeaway gets a strikethrough line plus a one-sentence retraction note pointing to the invalidating run. Retracted takeaways are not deleted — the audit trail matters.

**Correction.** When a takeaway needs updated numbers (e.g., baseline drift), edit in place and note the snapshot-date bump that produced the new values.

**Conflict between full-rebuild sections and append-only takeaways** is not a bug to suppress. The rebuild describes the dataset *as of* the snapshot; takeaways describe observations *across time*. A conflict between them is itself a finding worth investigating.

## Skill Direction

Phase 1 splits the skill, up front:

- **`data-analysis`** — keeps its current scope: portable statistical hygiene, chart discipline, visual inspection, aggregation and presentation guidance. No Garmin finding-workflow content.
- **`finding-analyst`** — new skill. Garmin-specific finding workflow, run-folder contract, recipe catalog, FINDINGS.md update policy, question backlog handling. References `data-analysis` for stat/chart discipline rather than re-explaining it.

`finding-analyst` directory shape:

```
.claude/skills/finding-analyst/
  SKILL.md
  RECIPES.md
  templates/
    01-question.md
    02-data-profile.md
    05-findings.md
    06-review.md
    07-findings-update.md
```

Templates make the gate-passing shape concrete at run time so the analyst is not guessing the structure.

The split happens before run #2, not at the end of Phase 1. Migration cost grows linearly with run count.

## Headless CLI Direction

Headless scans wait until the manual workflow has produced a stable contract.

The future runner should:

- Create the same `finding-runs/` directory structure.
- Invoke Codex with the `finding-analyst` skill and a scout-pass prompt.
- Compare current data against the last reviewed snapshot.
- Require the same artifacts and gates as a manual scout pass.
- Optionally run a second visual-review pass.
- Leave `FINDINGS.md` changes as proposed edits unless explicitly approved.

The runner must not:

- Write directly to frontend insight records or any product-facing surface.
- Bypass review gates.
- Run broad model searches by default.
- Invent a separate artifact format.

## General Implementation Details

- Skill files under `.claude/skills/`, concise.
- Analyst artifacts under `.claude/finding-runs/`.
- Snapshots under `.claude/finding-runs/<run>/08-snapshot/` are gitignored. The `08-snapshot/` path stays in version control via a `.gitkeep` so the directory shape is preserved.
- Shared analysis helpers live in `.claude/skills/finding-analyst/scripts/` only after repeated manual runs prove the same code is being rewritten. First-use code stays inline in `03-analysis.py`.
- `FINDINGS.md` remains the reviewed report surface for the current local dataset.
- Backend analytics remains the source of statistical truth for product-facing data. The frontend stays display-only.
- A future headless runner can use a script under `scripts/` once the run contract is stable.

## Completion Criteria for Phase 1

Phase 1 is ready to move toward implementation planning when all of these hold:

- The artifact contract has been used by **three separate analyst runs**, one of each type (question-led, manual exploratory, scout pass), in **separate sessions** so the contract is exercised without author-of-contract bias.
- At least **one run produced a promoted `FINDINGS.md` update** going through the full extended-artifact path, including snapshot, review, and patch.
- At least **one run produced "no signal"** and stayed minimal, demonstrating the contract does not force findings.
- At least **two scout passes** populated the question backlog with new open questions.
- The recipe catalog contains at least **four named recipes that were actually used** (not merely seeded).
- A friction log at `docs/superpowers/plans/2026-05-21-finding-analyst-friction.md` captures concrete pain points from real use. Phase 2 planning starts from that log, not from speculation.
