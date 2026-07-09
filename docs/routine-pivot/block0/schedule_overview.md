# Block 0 — Schedule Overview

**Window:** Mon 2026-07-06 → Sun 2026-08-02 (28 days) · **Identity:** measurement · **Lint:** 0 errors, 0 warnings
**Tags:** heat-season · chronic-load · protocol-change · **Week 1 is burn-in; baselines compute from day 8.**

## The week (weeks 1–3, identical — flat ~49 mi)

| Day | Morning | Midday |
|---|---|---|
| Mon | Easy 7 | **Push A** |
| Tue | Easy 6.4 + primer + strides 6×20s | **Lower A** (neural squat) + **HSR-A** (calf) |
| Wed | Recovery 5 | **Pull A** |
| Thu | Easy 7 | **Push B** |
| Fri | Easy 6.1 + drills *(wk 2: LTHR test)* | **Pull B** |
| Sat | **Long 12** (key session) | — |
| Sun | Recovery 4.5 | **Lower B** (posterior) + **HSR-B** (soleus/tib) |

Daily, every morning: check-in (soreness 0–3 per tissue, flags) + your habitual core/mobility, ≤15 min ceiling. That card is also where the selection rules get their inputs — skip the check-in and every rule falls back to its conservative branch.

**Week 4 (step-response):** run volume only drops to ~67% — 5 / 4.5+strides / 3.5 / 5 / 4 / **long 8** / 3 ≈ 33 mi. **All lifting and HSR continue at full, unchanged.** One variable steps; the rebound in HRV/RHR/easy-pace-HR is the measurement.

## LTHR test logic

- **Day 12 (Fri wk 2):** outdoor 30-min field test — 15 min warmup, 30 min max sustainable, LTHR = mean HR of final 20 min, 10 min cooldown (~7 mi total, so flat weeks stay flat). Deferred automatically if dew point > 22 °C or HRV is > 1 SWC below baseline.
- **Day 16 (Tue wk 3):** single backup slot. Outdoor if dew point passes; **treadmill in AC (1% grade) if not** — the anchor cannot be lost to weather. If day 12 already completed, day 16 reverts to a normal strides day via a logged `alternate_strides` branch.
- Day 15 (Mon) was rejected as a backup: the linter's L5 check flagged Sunday's Lower B landing inside the 24 h pre-test window. Day 16 works because the test is done in the morning *before* the midday lift.

## Strength cards (intensity unlocked)

**Push A (~58′):** bench 4×5–8 top-set/back-offs @ RPE 8 · incline DB 3×8–12 @ 9 · machine shoulder press 2×8–10 → failure · cable fly 2×12–15 → failure · laterals 4×12–20, final set myo-reps · pushdown 3×10–15, final set rest-pause
**Push B (~55′):** incline press 4×6–10 top/back-offs · flat machine/DB 3×8–12 · OHP/DB press 3×5–8 · laterals 4 (myo-reps) · overhead extension 3×10–15
**Pull A (~55′):** weighted pull-up 4×6–10 top/back-offs · chest-supported row 3×8–12 · 1-arm cable row 2×10–12 → failure · rear delts 3×12–20 (myo-reps) · EZ curl 3×8–12 · hammer curl 2×10–15
**Pull B (~52′):** machine/BB row 4×6–10 · pulldown 3×8–12 · rear delts 3 · EZ curl 3 (rest-pause) · farmer carry 3×30–40 m
**Lower A (~25′):** pendulum *or* hack squat (pick one day 1, keep it all block): ramp → top set 2–3 @ RPE 8 (~87%), 2 back-off doubles @ 85%
**Lower B (~25′):** hip thrust 3×5–8 @ RPE 8 · seated ham curl 3×5–8, 3 s eccentric
**HSR-A (~12′, after Lower A):** standing calf raise 3×4–6 @ ~85%, 3 s eccentric, pause at stretch
**HSR-B (~14′, after Lower B):** seated soleus raise 3×6–10 heavy, 3 s ecc · tibialis 2×15–25
**HSR week 1 ramp:** RPE 6–7 loads, same sets/reps; contract endpoint (3×4–6 @ 85%) from week 2. Declared endpoint — a ramp, not a hedge.

~18–20 hard sets/week per upper region. Every lift logs set × rep × load — that's where e1RM and the planned-vs-executed diagnostic come from.

## Adaptive rules (plain-English rendering of what's in the JSON)

- **Lower/HSR overloads:** skip if any target-tissue flag or HRV < −1.5 SWC; reduced (−1 set, −2–3% load) if HRV < −0.75 or target soreness ≥ 2. No plus variant — overshoot protection where it costs you.
- **Upper:** skip below −2.0, reduced below −1.25 — deliberately more lenient. **Plus variant (+2 isolation sets)** exists on every upper card, selectable only by you as a logged override; rules can never pick it. Weekly planned-vs-executed tonnage is a computed review diagnostic; sustained >1.25× flags the review that either raises the card or shows you why not.
- **Runs:** full unless a lower-limb tissue flag or HRV < −2.0, then shortened. Sleep < 50 or RHR +5 pushes the whole next day conservative via block constraints.
- **Missing data** (strap died, no sync): overloads default conservative, recovery cards default full.

## Exit criteria (block ends when true, day 28 target)

LTHR anchored · ≥2 clean flat cycles · e1RM initialized for squat pattern, hip hinge, calf/soleus · heat-correction model first-fit. Each failure extends by exactly 7 days, capped at +14. Week 4's rebound scores the recovery-dynamics prediction.

## What the linter verified (and caught)

All 12 rules pass on the final build. During authoring it caught, in order: the test session contributing zero miles to the flatness check (L9), the day-16 backup double-booked on top of the strides run — breaking both flatness and the running time budget (L9+L3), a day-15 backup slot violating the pre-test protection window (L5), and seven registry signals nothing consumed, including `sleep.score` (L6) — which is now a real constraint. The system rejected its own author four times before shipping. That is the design working.

## Day-1 inputs from you

1. Pendulum or hack for the squat pattern (then locked for the block).
2. First HSR loads: start ~RPE 6–7 and log — week 1 *is* the e1RM discovery.
3. Optional: LTHR prior (your guess ± wide band) into the estimator config; it bounds the test, never replaces it.
