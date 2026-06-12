---
name: finding-analyst
description: Use when investigating a question about the Garmin health dataset, running an exploratory review of a metric area, running a scout pass for candidate signals, or proposing a FINDINGS.md update. Triggers on "why did metric X change", anomaly/regime-shift questions, lagged-correlation questions, and any analyst run that produces durable evidence.
---

# Finding Analyst

You are running a **finding** — an evidence-backed observation about the local Garmin dataset, captured in a durable run folder and (only if it earns it) promoted to `FINDINGS.md`.

**REQUIRED BACKGROUND:** Use `data-analysis` for all statistical and chart discipline (distribution checks, IQR bands, missingness, visual inspection, spot-checks). This skill does **not** re-explain those — it owns the *workflow and evidence contract* on top of them.

**Vocabulary:** A **finding** is analyst-authored. An **insight** is the rule-based per-day dashboard card from `domains/garmin_analytics/domain/insights/` — different thing, don't conflate.

## Source of truth, never recompute

- Consume **persisted daily metrics**, not raw FIT files, unless the question genuinely needs raw readings. Snapshot the mart with `scripts/export_snapshot.py` (reuses `parse_all_days → compute_daily_metrics`).
- Reusable stats live in `backend/app/domains/garmin_analytics/domain/analysis/`. You may import from there; you do not extend those modules inside an analyst run.
- The frontend stays display-only. Findings never write to product surfaces.
- **Verify reported numbers against the snapshot before analyzing.** If the question quotes a value seen somewhere (a dashboard reading, a remembered figure), confirm it against the snapshot *first*. A mismatch is itself a finding and often reframes the run — don't analyze a number the data doesn't contain.
- **Presentation-layer questions are a distinct class.** "Why does the dashboard show X" may not be answerable from the mart at all — the answer can live in API responses (`/api/dashboard`) or frontend chart code (smoothing, windowing, axis derivation). For these, trace the product source and treat the **live render as valid evidence**: capture annotated screenshots into `04-plots/` alongside computed plots. You still never write to product surfaces — you diagnose, and route any fix to an Open Question.

## Run types

| Type | Pre-work in `01-question.md` | Promotes? |
| --- | --- | --- |
| **Question-led** | Pre-registration (prediction + decision rule) if hypothesis-testing; recipe declaration if exploratory | Yes, if it earns `confident` |
| **Manual exploratory** | Recipe declaration ("I will apply recipes A, B, C to this slice") | Yes, if it earns `confident` |
| **Scout pass** | Recipe set + breadth + ranking rule | No — feeds the question backlog only |

## Run folder

```
.claude/finding-runs/YYYY-MM-DD-<topic>-<slug>/
```
`<topic>` ∈ `hrv sleep recovery spo2 stress multi scout` (grepable).

**Minimal run** (scout passes, and question-led runs ending in "no signal"):
```
01-question.md  03-analysis.py  04-plots/  05-findings.md
```
**Extended run** (required to propose a `FINDINGS.md` edit) adds:
```
02-data-profile.md  06-review.md  07-findings-update.md  08-snapshot/ (gitignored)
```
Ceremony is proportional to claim weight. Don't write extended files for a scout pass.

Templates for each artifact live in `templates/`. Copy them at run start so the gate-passing shape is concrete.

`03-analysis.py` must declare its data source in a header comment:
```python
# DATA: snapshot at .claude/finding-runs/<run>/08-snapshot/daily.csv
```
Every plot in `04-plots/` has a title, axis units, date range, and smoothing window if any. An unannotated plot is not evidence — name files for content (`hrv-drop-feb-context.png`, not `figure_3.png`).

## Confidence

Set the confidence in `05-findings.md`. The `06-review.md` self-review can only **confirm or downgrade** it — never upgrade. A self-review that could talk you *up* is not a check. So claim the level your evidence supports in 05, and let the review try to knock it down.

- `tentative` — single recipe, no replication, exploratory. **A single eye-catching result from a many-comparison sweep is tentative, not more.**
- `provisional` — multiple recipes converge, or a pre-registered hypothesis test passed its decisive rule. The evidence is sound but a real interpretive ceiling remains (an uncontrolled confound, a shared-derivation coupling, a single non-replicable point).
- `confident` — `provisional`-grade evidence that you judge to clear *every* quality gate with no standing interpretive ceiling, claimed in 05 and **left standing by the 06 review**. For an extended run you may claim `confident` directly in 05; if the review finds any gate weak, it downgrades.

**Promotion by tier:**
- `confident` → promotes as an asserted **Analytical Takeaway** / claim.
- `provisional` → promotes as an **attributed observation** in a Temporal / Cross-Metric subsection, carrying its caveats and a `provisional` marker — never as an unqualified claim.
- `tentative` → stays in the run folder; may seed an Open Question; does not promote.

## Quality gates (all must pass before promotion)

1. **Question** — concrete question, explicit date range + metrics, run type declared, pre-registration present for hypothesis tests; any number quoted in the question is confirmed against the snapshot before analysis (record the confirmed-or-mismatched value).
2. **Data** — source named + snapshot pinned; coverage and missingness measured for every metric in a claim; nulls/zeros/impossible values addressed; filters state what they exclude.
3. **Statistical** — sample size + spread always (not just means); median/IQR for skewed metrics; outliers handled with documented reason; correlation ≠ causation; compare against a real baseline window, not an anecdotal neighbor; **effect size before any p-value**; for N-comparison sweeps, state N and the multiple-comparisons posture.
4. **Visual** — every evidence plot opened and inspected; units + sensible ranges; gaps not bridged in ways implying unobserved trend; 2–3 plotted values spot-checked against source; review records whether each plot supports / weakens / complicates the claim.
5. **Interpretation** — clear "so what"; alternatives and confounders named; exploratory labeled exploratory; descriptive only, no medical advice.
6. **Findings** — confidence is set in 05 and only confirmed or downgraded in review, never upgraded; promotion follows the tier rule (`confident` → Takeaway, `provisional` → attributed observation, `tentative` → run folder only); every promotion records snapshot date, date range, sample size, caveats; any resolved open question moves in the same patch.

## FINDINGS.md update semantics

- **Snapshot sections** (Distribution Snapshot, Temporal Observations, Cross-Metric Relationships) — full rebuild when the snapshot date bumps; latest supersedes.
- **Analytical Takeaways** — append-only with attribution (snapshot date + run folder). Retract with strikethrough + one-line note pointing to the invalidating run; never delete. Correct numbers in place, noting the snapshot bump.
- **Open / Resolved / Parked Questions** — append-only with state transitions. A resolved question moves to `Resolved Questions` with a back-reference; a question that resists two attempts moves to `Parked Questions` with a one-line why.

Conflict between a rebuilt section and a standing takeaway is itself a finding to investigate, not a bug to hide.

## Recipes

`RECIPES.md` is the catalog of named techniques. A recipe is **validated** only after a real run uses it; until then it is a **candidate**. Declare which recipes a run uses; record mid-run additions as they happen.

## Friction

Log concrete pain points to a dated friction note under `docs/superpowers/plans/` as you hit them, so future planning starts from real use rather than speculation.
