# Friction note — finding-analyst, 2026-06-19

From run `2026-06-18-hrv-recovery-cue-bakeoff` (D2A).

## 1. The mart snapshot lacks derived recovery quantities; analysts must re-derive them exactly
The frozen `daily.csv` carries only `hrv_nightly_avg / hrv_status / hrv_weekly_avg`. The recovery
*delta* (nightly vs prior-7-day baseline) and the *30-day drift* are computed in the product
(`_compute_recovery`, `_compute_long_baseline`) and are **not** in the snapshot. Re-deriving them
naively gets the wrong numbers: a rolling buffer of "last 7 non-null nights" reaches back across the
November gaps, whereas the product's `prior_7d_avg` averages the **7 positional rows** before the
index (`metrics[i-7:i]`, nulls skipped) and `safe_avg` **rounds to 1 decimal** before the delta is
rounded again. Using the positional window + matching the rounding reproduced the audit's 4-state mix
to the tenth and the exact flip count; the naive version was off by ~1 pp and a few nights.

**Suggested fix:** either (a) have `export_snapshot.py` optionally emit the product-derived
`recovery_delta` / `baseline_7d` / `drift` columns, or (b) add a one-paragraph "re-deriving recovery
fields" note to the skill pointing at `prior_7d_avg` + `safe_avg` semantics so each run doesn't
re-discover the positional-window + rounding requirement.

## 2. No catalogued recipe for comparing classifier/threshold rules
The run needed a "score N candidate rules on one pre-registered scorecard" pattern; nothing in
`RECIPES.md` covered it. Added **Rule/threshold bake-off** as a candidate. Its load-bearing lesson —
*always include a no-category and a smoothed-basis candidate, because discretization (not cut
placement) is the usual flicker source* — is worth surfacing wherever the skill discusses classifier
or threshold questions.

---

# Addendum — 2026-06-22, from run `2026-06-18-hrv-dow-display` (D9A)

## 3. A pre-registered statistic can be degenerate; correct it transparently before scoring
The D9A pre-registration's decision rule was "peak-to-trough bootstrap CI excludes 0." But
peak-to-trough = max−min of 7 weekday means is **≥ 0 by construction**, so its bootstrap CI can never
include 0 — the rule was unfalsifiable. Caught it before scoring, swapped to per-bin signed CIs
(which can cross 0) + a circular-shift null for the swing, and documented the swap in 05/06 rather
than silently changing the registered analysis. **Lesson for the skill:** when pre-registering a
test statistic, sanity-check that its null *can* fail; bounded-positive statistics (ranges, |effect|,
max−min) need a surrogate/null, not a CI-excludes-0 check. Now baked into the new
*Weekday / cyclic seasonality bootstrap* recipe's caveats.

## 4. The audit's "stability" check was a deterministic subsample, not a bootstrap — and overstated it
The surface audit reported split-half Spearman 0.75 and subsample p2t stability via a deterministic
2-of-3 loop. A real moving-block bootstrap + clean split-half gave Spearman 0.61 and an
autocorrelation-honest null p≈0.03 — still a real, provisional effect, but more modest. Re-derivation
on the frozen snapshot corrected the FINDINGS observation in place. **Lesson:** treat any
"stable under subsampling" claim that didn't use a real resampling null as provisional until a
bootstrap confirms it; serial autocorrelation alone manufactures a sizeable swing (~6 ms here), so
iid-flavored stability checks overstate significance.
