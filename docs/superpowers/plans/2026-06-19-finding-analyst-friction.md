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
