# Analytics Approach — Design Rationale

How we structure AI-assisted analysis of this dataset, and why the work is split
across three skills with the bulk of the machinery living in `finding-analyst`.

---

## The failure mode we're engineering against

A year of daily wearable metrics (resting HR, HRV, stress, body battery,
respiration, sleep scores, SpO₂, skin-temperature deviation) is small, noisy,
autocorrelated, and full of structurally-missing data. The dominant risk isn't
computation — it's **producing confident, well-formatted conclusions that are
wrong**. The specific traps recur:

- Summary statistics that hide the distribution (a mean over a bimodal or skewed
  series; a "typical" value that's actually a ceiling pile-up).
- Non-random missingness read as signal (SpO₂ is absent for the first six weeks
  of device ownership and again for a mid-series stretch — 19% of days, in two
  structural blocks).
- Autocorrelation inflating apparent significance; same-source coupling
  masquerading as a relationship (Garmin derives both daytime stress and nightly
  HRV from heart-rate variability).
- Multiple-comparison fishing — sweeping dozens of metric pairs or lags and
  reporting the one that crossed a threshold by chance.
- HARKing: forming the hypothesis after seeing the result, then presenting it as
  if predicted.

Every design choice below exists to make these failures hard to commit and easy
to catch.

---

## Why three skills, split by layer

The work decomposes into three concerns that fail differently, are reused
differently, and stack in a fixed dependency order. Collapsing them into one
playbook would blunt each.

**1. `garmin-data` — the ingest/parse contract.** Owns the device file format:
field semantics, unit handling, sensor-artifact filters (e.g. the 0-BPM
wrist-contact dropout), and the UTC→local-time shift that determines which
calendar day a reading belongs to. This layer is deterministic and mechanical —
the same files always yield the same clean daily metrics — and it is the
foundation everything else trusts. Failures here are *technical* (a mislabeled
field, a timezone off-by-one).

**2. `data-analysis` — domain-agnostic statistical and visualization discipline.**
Owns the reasoning habits: never report a mean without spread and shape; choose
median/IQR for skewed metrics; treat missingness as a measured quantity; default
to IQR bands not min/max; *always render and inspect the chart before trusting an
aggregate* (Anscombe / Datasaurus). Nothing here is watch-specific — it would
apply to any dataset. Failures here are *reasoning* errors (trusting an average,
bridging a data gap).

**3. `finding-analyst` — the study and evidence workflow.** Owns everything about
turning a question into durable, auditable, trust-tiered evidence: run structure,
snapshot pinning, pre-registration, the recipe catalog, quality gates, the
confidence ladder, and promotion into the permanent findings record. Failures
here are *discipline* errors (a fluke promoted to a fact, goalposts moved after
the reveal).

The dependency is one-directional: clean data → honest statistics → disciplined
study. An analyst run loads only the layers a task needs — a "what's a typical
night's sleep" question pulls in `data-analysis`; "why did recovery crash last
November" pulls in all three — so the right discipline arrives automatically and
nothing irrelevant is loaded. `data-analysis` is portable to other projects
untouched; `garmin-data` is specific to these files; keeping them separate lets
each evolve without disturbing the others.

(Two further skills — dashboard design and UI/UX — are deliberately *out* of the
analysis path. Determining what's true and presenting it on screen are different
jobs, and fusing them is how dashboards end up attractive and misleading.)

---

## `finding-analyst` in depth

This is where most of the engineering lives, because reproducibility and
calibrated trust don't happen by good intentions — they happen by structure.

### Run folders + snapshot pinning: reproducibility

Every investigation is a dated run folder containing the question, the frozen
data, the analysis script, the plots, the findings, and a self-review. The
dataset grows daily, so re-running an analysis next month yields different
numbers; **each run freezes an exact CSV snapshot** of the persisted daily
metrics (via the same `parse_all_days → compute_daily_metrics` path the product
uses, not a re-aggregation from raw files). The analysis declares that snapshot
as its data source in a header comment. The result: anyone can reproduce the
exact numbers a run reported, and a reviewer audits a self-contained artifact
rather than a verbal claim.

### Templates: making the contract concrete and review mechanical

Each artifact (`01-question`, `02-data-profile`, `05-findings`, `06-review`,
`07-findings-update`) has a template, copied in at run start. Templates aren't
bureaucracy — they do three things:

- **Encode the gate-passing shape.** The data-profile template has a slot for
  per-metric coverage and a null-vs-zero line; the question template has a
  pre-registration block. The structure makes omissions visible — an empty
  coverage table is an obvious gap, whereas free-form prose silently skips it.
- **Force pre-work before data.** The pre-registration block physically sits
  above the analysis and is meant to be filled in *first*; the reported-number
  check ("verify any quoted figure against the snapshot before analyzing") is a
  30-second step that, in practice, caught a dashboard value that didn't match
  the persisted data and reframed an entire run.
- **Standardize for review.** A reviewer (or the author weeks later) finds the
  same six sections in the same order every time, so review is a checklist pass,
  not an archaeology dig.

### Recipes: a vetted methodology catalog with caveats baked in

`RECIPES.md` is a catalog of named analysis techniques — *Lagged correlation*,
*Partial-correlation control*, *Anomaly window*, *Change-point*, *Distribution
shape*, *Missingness pattern*, and so on — each with its question shape, inputs,
method, **caveats**, and a validation step. Recipes exist because:

- **Methods should carry their failure modes.** "I correlated A and B" is a
  claim; "I applied *Lagged correlation*, which is a multiple-comparison sweep
  whose CIs I computed with a moving-block bootstrap because the series
  autocorrelate" is auditable methodology. The caveats encode hard-won lessons —
  contiguous calendar pairing so a "lag +1" can't secretly span a gap; "define
  recovery strictly after the last suppressed day" so a mid-regime blip isn't
  miscredited as the end; "a hand-coded known-pairs mask is brittle." These were
  learned from real runs and written down so the next run doesn't relearn them.
- **They give reviewer and author a shared vocabulary.** Declaring recipes up
  front turns "trust my analysis" into "here are the named techniques I'll apply,
  audit them."
- **Trust is earned, not assumed.** A recipe is `candidate` until a *trusted* run
  uses it, then `validated` (recording the first run). When the early
  exploratory runs were judged preliminary and set aside, every `validated` flag
  was reset to `candidate` and re-earned on a clean full-dataset baseline —
  because validation is supposed to mean "a run we rely on exercised this," not
  "this method was once typed into a file."

### Three run types: different epistemic contracts

The pre-work and promotion rules differ by run type because the *kind of claim*
differs. This is the core of the skill:

| Type | Pre-work in `01-question.md` | Promotes? |
| --- | --- | --- |
| **Question-led** | Pre-registration (prediction + decision rule) if hypothesis-testing; recipe declaration if exploratory | Yes, if it earns `confident` |
| **Manual exploratory** | Recipe declaration ("I will apply recipes A, B, C to this slice") | Yes, if it earns `confident` |
| **Scout pass** | Recipe set + breadth + ranking rule | No — feeds the question backlog only |

- **Question-led, hypothesis-testing** is the strongest contract. You write the
  prediction *and the decision rule* — what result confirms, what falsifies, and
  the exact set of comparisons — **before opening the data**. This is the
  anti-HARKing mechanism: you can't move the goalposts once you see the numbers,
  and a pre-committed comparison set defuses multiple-comparison fishing. Example:
  testing whether a high-stress day predicts suppressed HRV *the next night
  beyond the same-night relationship* required pre-committing to a partial
  correlation surviving |r| ≥ 0.10; the raw lag was nearly meaningless without
  that control, and pre-registration is what forced the control to be declared
  rather than reached for after a disappointing raw result.
- **Question-led, exploratory** and **manual-exploratory** drop the prediction (a
  descriptive "when did X end?" has no point prediction to make) but still
  require a **recipe declaration** — committing to *method* before touching data,
  even when you can't commit to an outcome. That's the weaker but still real
  discipline for open-ended questions.
- **Scout pass** is breadth-first reconnaissance: a recipe set, a defined sweep
  breadth, and a ranking rule, run across many pairs/windows. Critically, **it
  promotes nothing.** A many-comparison sweep produces candidates that are
  `tentative` *by construction* — the striking result from 66 pairs is exactly
  what you'd expect by chance — so a scout's only output is ranked candidates
  appended to the question backlog. Its best result is often a clean negative
  ("no under-documented pair exists; the off-axis metrics are weakly coupled by
  nature"). Allowing a scout to write conclusions would be the multiple-comparison
  trap institutionalized; forbidding it is the point.

Three types, because conflating them would either over-burden a quick scout with
pre-registration it can't honor, or under-discipline a hypothesis test that needs
a pre-committed rule.

### Confidence ladder + quality gates: calibrated, downgradeable trust

Findings are tiered `tentative` / `provisional` / `confident`, set by the author
and **only ever downgradeable** by the self-review — a review that could talk you
*up* isn't a check. Only `confident` findings promote as asserted claims;
`provisional` ones promote as attributed observations carrying their caveats;
`tentative` ones stay in the run folder and may seed a question. Promotion is
gated by a fixed six-point checklist (question well-posed; data sourced and
missingness measured; effect size before p-value, with spread and n; every plot
inspected and spot-checked against source; alternatives and confounders named;
only earned results recorded). Directly-measured descriptive facts (a
distribution summary, a correlation coefficient on the full snapshot) are
`confident` on sight; *inferential* claims with a standing confound — e.g. the
stress↔HRV lag, where both metrics share an HRV-based derivation — are capped at
`provisional` no matter how clean the arithmetic.

### The friction loop: the skill improves itself

Every run logs concrete friction. That log is the input to skill changes — and it
has already surfaced real contract bugs (the `confident` tier was once defined as
"provisional plus a passing review," which contradicted "review may only
downgrade"; resolved by making review confirm-or-downgrade only) and real
analysis bugs (the recovery-date relapse artifact, caught by the visual gate
mid-run). Recipes graduate from `candidate` to `validated` through use; caveats
accumulate from what actually went wrong. The skill is treated like code under
test: changes are driven by observed failure, not speculation.

---

## What the composition buys

- **Reproducibility** — pinned snapshots and self-contained run folders mean any
  number can be re-derived and any reasoning re-audited.
- **Calibrated uncertainty** — three confidence tiers, downgrade-only review, and
  promotion gates keep hunches labeled as hunches; only earned results enter the
  permanent record, and even those carry their confounds.
- **Pre-committed honesty** — pre-registration for hypothesis tests and
  promote-nothing scouts structurally block HARKing and multiple-comparison
  fishing.
- **Resilience** — when a later run shows earlier work was shaky, the old work is
  archived as superseded (not deleted, not silently overwritten) and the baseline
  is rebuilt on fresh data; disagreements between old and new are themselves
  recorded as findings.

The split isn't ceremony. It's the structure that lets a fast analyst be fast
*and* trustworthy on data that is unusually easy to misread.
