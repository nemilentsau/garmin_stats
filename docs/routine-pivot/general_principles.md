# General Principles — Training System v3

**Status:** Adopted — v2 terminated, full fresh start, no in-flight patches
**Date:** 2026-07-04 (v2 block terminated on its day 6)
**Scope:** Governing document for the Garmin-driven training app and all bundle generation. Supersedes the design assumptions embedded in the v2 three-bundle system (`four-week-running-calibration-patched`, `four-week-strength-running-calibration`, `four-week-running-support-calibration`).

---

## 0. Context

Athlete profile: trained, not developing from zero. ~49 mpw current baseline, 350 lb squat, ultra background (last year), 1:31 half (two years ago — stale, ultra-shifted, not usable as a zone anchor). Goals: sub-3:00 marathon with **no deadline** ("whenever it happens"); upper-body physique is a hard constraint to be protected; lower-body size is conceded but lower-body *function* is not. A tune-up half will serve as the primary calibration race on the way to the marathon.

System: an app that consumes Garmin data (chest-strap HR, HRV, RHR) and uses agents to generate and adapt training bundles. Stated purpose: find the load/recovery balance that produces continuous forward progress.

This document does two things: names the failure classes in the v2 system, and states the principles v3 must satisfy. The failures are systemic, not session-level — fixing individual cards without fixing the classes reproduces the same defects in new bundles.

---

## 1. Diagnosis: failure classes in v2

### 1.1 Inverted objective function

Audit the vocabulary of the three bundles: skip-if, reduce-if, "keep it deliberately underwhelming," "should improve freshness, not fitness," optional, regress, cap. It is a rich penalty vocabulary. There is not one card in the system that asserts "this session must produce X." The system knows how to avoid cost; it has no representation of benefit.

Combine that with no race date and the consequence is structural, not hypothetical: an infinite-horizon controller whose observables are recovery metrics converges on the policy that maximizes them — easy jogging and rest. HRV stays pristine, every readiness gate passes, every dashboard is green, and threshold pace quietly decays. This is under-training as reward hacking. Nothing in v2 prevents it; most of v2 actively encodes it.

### 1.2 Stimulus destroyed by multiplied hedges

The lower-body strength work illustrates a general law. Six attenuations are stacked on the same sessions: machine instead of barbell, RIR 2–3 cap, "no grinders" on top of the cap, no percentage or progression anchor, ~40% of the menu tagged optional, remaining items deferred to another bundle. Each hedge is individually defensible. Attenuations compose **multiplicatively**, so the product rounds to zero: time cost paid, adaptation not delivered — theater. The system budgeted risk per decision instead of budgeting total attenuation per session, so every reviewer-safe choice summed to a session that does nothing.

The same class recurs in the loading zone chosen where work does exist: moderate load × moderate reps (RDL 2×4–6, machine squat at RIR 3) is the maximum-soreness, sub-threshold-intensity quadrant — the most interference per unit of adaptation.

### 1.3 No ownership model

Tissues appear in multiple bundles and are coordinated by prose. Concrete failures found by integrating one week: day 12 double-books the strength Lower B and the support hamstring/adductor block with contradictory instructions in two different files; day 9 stacks the strength bundle's loaded calf work against the support bundle's bodyweight calf work, and the deference prose resolves toward the **weaker** implement. Net result across all three bundles: the calf–Achilles complex — the most-loaded tissue in a 49 mpw week and the subject of the most written anxiety ("Achilles noise" appears everywhere) — receives either zero or sub-threshold stimulus. Nobody owns it, so nobody loads it.

### 1.4 Open-loop scripts with the adaptive logic in prose

All conditional behavior ("if the steady run felt controlled, do the full version, otherwise cut one set") lives in natural-language instruction strings. It is unparseable by the agent layer, unexecutable by the scheduler, and unauditable after the fact: when the week-4 review asks whether lifting interfered, there is no record of which branches were taken. The "agent" in the current agent-designed system is the human, reading strings. The bundles are 28-day open-loop scripts wearing an adaptive costume.

### 1.5 Missing state variables

Running captures 13 post-run fields including dew point; strength captures two 1–5 subjective sliders and **no load data** — no set × rep × weight, therefore no tonnage, no e1RM trend, no strength state at all. An optimizer cannot protect a quantity it cannot see; lower-body strength was destined to be silently traded away the moment it went unmeasured. The mirror defect exists on the running side: fields are collected with no declared model consuming them (dew point feeds nothing), which is data theater — collection without an analysis contract.

### 1.6 Unvalidated invariants and incoherent block identity

The support bundle declares a 20–45 min weekly budget; its scheduled content sums to ~55–69 min. Week 4 "deloads" from a load that never exceeded the pre-block baseline (49.05 mi baseline; block peaks at 49.0). The running block progresses 46.5→48→49 — a 5% ramp too small to be stimulus and nonzero enough to dirty system identification, i.e., neither a flat measurement block nor a training block. And the single load-bearing measurement of the month, the LTHR test, is marked *optional* behind a readiness gate that three weeks of easy running trivially passes. Declared invariants are never checked against the compiled schedule; block purpose is never pinned down.

### 1.7 Unmanaged confounds

Week 1 launched a new 6-day lifting split and a new running protocol simultaneously — two baselines established at once, both contaminated by novelty. The LTHR anchor is being set in peak dew-point season, where cardiovascular drift biases a field-test estimate high and the pace↔HR mapping is seasonal, with no environment tag or correction model. The zero-rest-day structure means the HRV baseline is conditioned on chronic load and is untagged as such. None of these are necessarily wrong; all of them are invisible to the current system.

---

## 2. Principles for v3

**P1 — Progress is the objective; recovery is a constraint.** Define an explicit performance state vector *S*: threshold pace at fixed HR (or HR at fixed pace, once calibrated), e1RM on the squat pattern and one or two upper anchors, tendon-capacity proxy (loaded calf/soleus e1RM), and a physique proxy (upper tonnage trend + bodyweight). The objective is maximizing d*S*/dt subject to constraints: HRV within band, RHR within band, tissue flags clear, sleep adequate. The controller must never optimize the constraints. Green recovery dashboards with flat *S* is a failure state, not success.

**P2 — Every session declares a stimulus contract.** Each card is exactly one of: **overload** (declares the expected adaptation and its progression driver), **maintenance** (declares the preserved quantity and its minimum effective dose), **measurement** (declares the estimand and a data-quality gate), or **recovery** (declares a load ceiling). A session that cannot state its contract is deleted. This kills theater by construction: "runner durability" work either specifies the tendon-loading dose that produces durability, or it does not exist.

**P3 — Maintenance preserves intensity and cuts volume, never both.** Trained-athlete maintenance is intensity-dependent: strength holds at a fraction of volume only when load stays heavy (Bickel et al. 2011 and the reduced-training literature). Corollary for concurrent blocks: heavy low-rep work is the *running-compatible* option — lowest DOMS per unit of neural stimulus — while moderate-load moderate-rep work is banned during run blocks as the worst quadrant.

**P4 — One tissue, one owner.** The ownership map is part of the schema. A build-time validator rejects any bundle set in which a tissue tag appears in more than one active bundle. Cross-bundle coordination prose is a compile error, not documentation.

**P5 — Policies, not scripts.** Every assignment carries a variant set (full / reduced / skip / alternate) plus a selection rule over declared, machine-readable inputs: HRV deviation from baseline, RHR delta, prior-day load, soreness flags, prior-session branch outcomes. Every branch taken is logged. A natural-language conditional inside a card is a schema violation.

**P6 — Measure what you protect.** Every element of *S* has a capture mechanism before the block starts. Strength sessions log set × rep × load; the app derives tonnage and e1RM trends. Anything valued but unsensed will be traded away silently — this is not a risk, it is the observed v2 outcome.

**P7 — Every collected field has an analysis contract.** Each field names the model it feeds and the decision that model informs. Dew point exists to drive a heat-correction on the HR↔pace mapping, or it is deleted. Collection without a consumer is deleted on sight.

**P8 — Forcing functions replace the calendar.** With no race date, the architecture is infinite-horizon: continuous base with rotating emphasis blocks. Progress pressure comes from explicit forcing functions, not dates — scheduled **measurement events** (the tune-up half as primary anchor; LTHR retest every 8–12 weeks; designed step-response weeks), and block rotation triggered by **plateau detection** in *S*. Taper logic activates only when a race is actually scheduled.

**P9 — Polarize.** The system must contain sessions whose explicit purpose is overload, gated by readiness rules rather than pre-hedged into nothing, and easy sessions that are genuinely easy. v2's uniform medium-soft distribution is the worst of both: enough cumulative fatigue to matter, no session hard enough to adapt to.

**P10 — Confounds are first-class events.** Protocol changes (new split, new block, new shoes) are logged events; baselines carry condition tags (chronic-load, heat-season, dual-baseline). Change one thing at a time where feasible; tag where not.

**P11 — Invariants are validated at build time.** The app compiles the integrated cross-bundle schedule and lints it: budget sums vs. declared budgets, ownership conflicts, same-day contradiction detection, rest rules, declared vs. actual session counts, and existence of a per-day aggregate load rollup — the state variable any load/recovery controller requires and v2 lacks.

**P12 — Compute the reviews; ask the human only the residual.** "Did lifting change easy-run feel or HR" and "did support work contaminate calibration" are answered better by data (next-morning HR at fixed easy pace, HRV delta conditioned on prior-day session type) than by recall. Weekly review prompts that can be computed are computed; the human answers what sensors cannot see — mechanics feel, motivation, niggles.

**P13 — Priors are fused, not worshipped or discarded.** Stale data enters with wide variance rather than being deleted: the two-year-old 1:31 does not set zones, but it bounds plausibility and sanity-checks the LTHR test output. State estimation is Bayesian; cold starts are forbidden when informative priors exist.

---

## 3. Way forward

### 3.1 Schema v3 deltas

Stimulus contracts on every card (P2). Variant + selection-rule objects replacing prose conditionals (P5). Tissue-ownership tags plus the build-time validator (P4, P11). Measurement events as first-class scheduled objects with estimands and quality gates (P7, P8). Strength load capture: set × rep × load per exercise (P6). Event log for branches taken and protocol changes (P5, P10). Per-day aggregate load across all active bundles (P11). Baseline condition tags (P10).

### 3.2 Rebuilt ownership map

**Running bundle** owns all cardiovascular load plus strides and drills. **Strength bundle** owns upper-body physique work (v2's version is correct — ~16–18 weekly sets per major region, keep it), the heavy neural squat pattern, hip-thrust/hamstring work, and progressive plyometrics. **Support bundle** owns tendon heavy-slow-resistance (loaded calf and soleus — this becomes a *loaded* block, the single highest-value change in the whole rebuild), tibialis and foot work, core, mobility, and the stride-day micro-primer (the one v2 element worth keeping verbatim). No tissue appears twice.

### 3.3 The rebuilt lower body (the answer to "theater")

Three jobs, three short sessions, ~70 min/week total — less time than v2, real contracts:

**Lower A — neural force (overload/maintenance, ~25 min, 1×/wk, on strides day).** Squat pattern (machine acceptable — spares spine and stabilizers — but loaded like it matters): ramp to a top set of 2–3 @ RPE 7–8, two back-off doubles at ~85%. Progression driver: load; state variable: e1RM.

**Lower B — reactive + posterior chain (overload, ~25 min, 1×/wk, day after long run, never before it).** Plyometric progression, 40–60 contacts: pogos → low drop-to-stick → bounds, progressing contact quality and height across blocks — the adaptation with the strongest running-economy evidence at this training status (Rønnestad & Mujika 2014; Blagrove et al. 2018). Then hip thrust 2×5–8 or heavy hamstring curl with slow eccentric. Moderate-rep RDLs are deleted from run blocks (P3).

**Support lower-leg — tendon HSR (overload/maintenance, ~15 min, 1–2×/wk).** Loaded straight-leg calf raise 3×4–6, 3 s eccentric; loaded bent-knee soleus raise 3×6–10; tibialis 2×15–25; short-foot/balance unchanged. Bodyweight calf raises are deleted: at 49 mpw the running already exceeds that stimulus, and tendon adaptation requires strain magnitudes reached only near-maximal loads.

### 3.4 Teardown and Block 0

**Teardown.** The v2 bundles are terminated on their day 6, not patched. The salvage list is short: the micro-primer card (verbatim — the one v2 element that survives inspection), the upper-body split content (volume was correct; ported with set × rep × load logging added), and six days of strap data retained as burn-in reference only. Everything else is regenerated from scratch under the v3 schema. Days between teardown and Block 0 start are an explicit interregnum: habitual easy running and lifting, no data contracts, nothing counts.

**Build order.** Schema spec first, validator second, bundles last. No bundle is adopted until it compiles against the v3 schema and passes the linter — the system enforces its own constraints from artifact one.

**Block 0 — calibration done correctly (4 weeks, starting the first Monday after bundles pass validation).** Identity pinned as a measurement block, with every estimand declared before day 1:

- HR↔pace↔RPE mapping, with dew point now feeding an explicit heat-correction model (P7) instead of feeding nothing.
- LTHR anchor: **required** test at end of week 2 (~day 12), backup slot day 15. Mid-block placement is deliberate — the test doubles as an impulse-response probe, the only perturbation in an otherwise flat block, so the recovery trace after it is itself identification data.
- Load-response identification: mileage flat at ~48–49 through weeks 1–3. No ramp. The 5% noise progression does not return.
- Week 4: designed step-response down-week, scored as predicted vs. observed rebound in HRV, RHR, and easy-pace HR.
- Strength state initialization: first e1RM estimates on the squat pattern, loaded calf/soleus, and the upper anchors — every lift logged from day 1.
- Baseline tags: `heat-season`, `chronic-load`, `protocol-change`. Week 1 is burn-in; baselines compute from day 8.

Loading rules inside a measurement block: neural squat work and tendon HSR go heavy immediately — at this training status the novelty cost of heavy low-rep loading is small, and the sessions repeat as a stationary weekly covariate the identification model conditions on. Plyometrics are the one genuinely novel stimulus, so Block 0 holds them at the lowest tier (the pogo dose already tolerated in the primer) and the progression opens in Block 1. All sessions carry P2 contracts; ownership per §3.2; lower body per §3.3.

**Block 1 (post-calibration):** first development block, threshold-shaped, because the profile is the inverse of the typical sub-3 aspirant: the ultra background makes endurance the moat and pace at threshold the entire gap. Two quality sessions per week against freshly anchored zones; strength per §3.3; upper untouched.

**Measurement calendar:** LTHR retest every 8–12 weeks and at season change (the July anchor will read high and must be re-anchored in cool weather). Tune-up half scheduled after 2–3 development blocks or on threshold-pace plateau, formalized as a measurement event that re-derives all zones. Marathon gate: half at ~1:27–1:28 — the standard 1:26–1:27 equivalence relaxed by a durability-favorable conversion exponent (~1.04–1.05) — with marathon-specific long-run volume in place.

### 3.5 Deletions

Bodyweight calf raises. Moderate-rep RDLs during run blocks. Every "optional" tag (replaced by explicit, logged selection rules). All cross-bundle coordination prose. Every collected field without a named model. Calendar-scheduled deloads (replaced by triggered deloads plus designed step-response probes).

---

## Definition of done

v3 is done when every card states its contract, every branch is logged, every protected quantity has a sensor, every declared invariant is machine-checked against the compiled schedule, and nothing in the system exists for appearance. The test for any future session is one question: **what does this produce, and how would we know?**
