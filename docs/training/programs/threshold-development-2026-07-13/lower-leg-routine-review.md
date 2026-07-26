# Lower-Leg Routine Review — Threshold Development (2026-07-13)

**Subject:** Lower-body strength + tendon prescription in the threshold-development authored program (`strength.v3` legs cards + `support.v3` HSR cards).
**Block window:** 28 days from 2026-07-13.
**Data snapshot:** `storage/garmin_stats.db`, reviewed 2026-07-14 (block day 2).
**Status:** **Actioned in the authored program on 2026-07-15** — retained as the standing rationale for the lower-body design. §5–§6 describe the **pre-change** diagnosis (the "why"); §7 records what was applied. Edits to the routine happen in the JSON artifacts, not here.

### Applied to the authored program (2026-07-15 · re-imported through the sanctioned pipeline · all capture logs preserved)
- **Legs 2 (`str.legs_machine`) rebuilt** into a hip/posterior day: Romanian deadlift (loaded hinge, prime mover), barbell hip thrust (glute-max horizontal force), Bulgarian split squat (unilateral / frontal-plane), with pendulum squat retained for quad. **Legs 1 (`str.legs_barbell`) untouched** (already performed this block).
- **S5 rewired** — `est.e1rm.hip_hinge` is now fed by the real RDL capture (`cap.set_log.legs_rdl`), not only the seated-curl proxy.
- **Exit criterion `strength_progressing` tightened** — now requires **held-or-up vs the 28-day SWC** (`e1rm.*.dev_swc >= -1.0`) for squat / hinge / calf-soleus, replacing the "readout exists" (`> 0`) gate; three `*.dev_swc` signals + deviation estimators added.
- **Selection gating** on Legs 2 now also reduces/skips on hamstring soreness and tissue flags.

**Open follow-ups:** Legs 1's seated ham curl still co-feeds S5 (can't be removed without touching the frozen day — clean up next block); a direct hip-abduction accessory could swap in for more isolated glute-med work; the `*.dev_swc` estimators are declarative until the estimator engine materializes them (§3).

---

## 1. What the routine actually prescribes

Lower body receives **two strength sessions and two tendon sessions per week**, repeated across the 4-week block. Running (6 days/week) is the other, larger lower-body load and is out of scope for this review except as context.

| Session (card) | Exercises | Targets | Weekly hard sets |
|---|---|---|---|
| **Legs 1 — Barbell** (`str.legs_barbell`, d2/9/16/23) | Back squat 4×3–5 @ ~85% e1RM (RPE-8 top set + back-offs); seated ham curl 3×5–8, 3s eccentric | quad, glute / hamstring | 4 quad-glute, 3 hamstring |
| **Legs 2 — Machine** (`str.legs_machine`, d7/14/21/28) | Pendulum squat 4×8–12 @ RPE 9; leg extension 3×12–15 @ RPE 10, myo-reps | quad, glute / quad | 7 quad |
| **Tendon HSR A** (`sup.hsr_a`, ~2×/wk) | Standing calf raise 3×4–6 @ 85% e1RM, 3s eccentric | calf/Achilles | ~3 calf |
| **Tendon HSR B** (`sup.hsr_b`, ~2×/wk) | Seated soleus raise 3×6–10; tibialis raise 2×15–25 | soleus, tibialis | ~5 soleus/tibialis |

**Key design facts:**
- `progression_driver: load` on every leg card — the top set is prescribed off *current* e1RM at fixed RPE, so load autoregulates upward. Progression is by load on fixed movements, not by exercise rotation.
- Leg cards have **no `plus` variant** (upper-body cards do carry a +15% `plus`). Lower body is capped by design; upper body is allowed to push.
- HRV / soreness / tissue-flag gates can trim any session to 60% (`reduced`) or skip it.
- `sc.protect_long_run` forbids hamstring/adductor overload within 30h of the long run; `sc.protect_test` forbids lower-body overload within 24h of the LTHR test.

## 2. Declared goal and hierarchy

From [`../../principles.md`](../../principles.md): mission is a sub-3 marathon *"while preserving upper-body physique and lower-body strength."* The program's state vector makes the priority explicit:

- **S1 — threshold pace at LTHR** (the adaptation target for this block).
- **S2 — squat-pattern e1RM**, **S3 — calf/soleus HSR e1RM**, **S5 — hip-hinge e1RM** (qualities to hold or nudge up while running improves).
- Principle **P3**: when concurrent training forces a smaller strength dose, cut volume but keep the intensity that preserves the quality; avoid moderate-load/moderate-rep junk fatigue.

**Evaluative lens.** Written for a trained lifter, not a beginner. The program serves **two complementary goals**, and best-principles S&C achieves both with the same work rather than trading them off:

1. **Preserve and progress lower-body strength.** Recovery is a constraint; progress is the objective (P1). The state vector treats S2/S3/S5 as **progression signals** (rolling-SD SWC, k=0.5) — the block intends lower-body strength to *move up*, not merely survive. Preservation is the floor; gains are the declared intent.
2. **Build running-injury resilience.** For a runner chasing sub-3 with no deadline, tissue robustness (eccentric hamstring capacity, tendon stiffness, frontal-plane hip control) is a **performance enabler, not general-population caution** — you cannot push a block you keep breaking. This is a first-class goal, not a footnote.

These converge: heavy hinging, eccentric hamstring work, and loaded glute training raise force output *and* injury resilience simultaneously. So the routine is judged on: **does it let lower-body strength be preserved and pushed, and does it train the known running-injury risk factors — at working intensity, without junk volume?** The remedy for the gaps below is the *right high-tension movement patterns* [3][4], not more sets. This is the opposite of bodybuilding.

## 3. Data reality — progress is currently unmeasurable

- As of the snapshot, the program is on **day 2**. The only logged lower-body strength session is the **day-2 barbell squat**, marked complete but with an **empty set/rep/load capture**; the day-2 tendon session (`sup.hsr_a`) is likewise complete with no captured load.
- The e1RM and tonnage estimators (`est.e1rm.*`, `est.upper_tonnage`, `est.planned_vs_executed`) are **declared in the registry but not implemented** (per [`../../roadmap.md`](../../roadmap.md)).
- **Consequence:** the app cannot presently show leg progress even if it occurs, and the "no progress" perception is at least partly an instrumentation gap, not only a programming one. Any before/after judgement must wait for set-log capture + estimator materialization.

---

## 4. Pros (evidence-based strengths)

1. **Heavy squat + tendon HSR is the canonical runner's strength dose.** Heavy and plyometric-style strength work improves running economy and time-trial performance in distance runners [1], with high-load methods specifically effective [2]. The routine captures this via the RPE-8 heavy squat.
2. **The dose clears the evidence-based minimum for strength maintenance/gain.** Trained lifters maintain and gain 1RM on ~3–6 weekly sets/lift at >80% 1RM, RPE 7.5–9.5 [3]; strength is preserved with loads ≥80% 1RM at as little as one session/week [4]. ~11 weekly hard quad sets across three patterns sits above maintenance.
3. **Volume is correctly capped for concurrent training.** Interference concentrates in *lower-body* adaptations and scales with endurance frequency/duration — worse for running than cycling [5]. Keeping leg volume modest (and giving upper body the only `plus` variant) is the right response; the more recent compatibility meta-analysis finds max strength and hypertrophy essentially preserved under concurrent training when the dose is managed [6].
4. **Fixed exercise selection is a feature, not a bug, for a measurement block.** Exercise variety does not out-perform fixed selection for hypertrophy in trained lifters (variety mainly raised motivation) [7]; the classic pro-variety result used squat-only vs varied and the block already spans squat + pendulum squat + leg extension [8]. Fixed movements also keep the S2 e1RM trend a valid instrument (avoids neural/learning contamination from novel lifts).
5. **Tendon protocol is straight from the rehab/stiffness literature.** 3s-eccentric heavy-slow resistance is the validated protocol for patellar [9] and Achilles [10] tendon; given the 2026-07-11 check-in logging calf/Achilles soreness at 3/3, this is arguably the highest-value lower-body work in the block.
6. **The hamstring movement chosen is the better isolation option.** Seated (long-muscle-length) leg curl beats prone for hamstring hypertrophy (+14% vs +9%) [11] — so the one hamstring slot uses the more effective variant.

## 5. Cons (evidence-based weaknesses)

Against the two-goal bar in §2, the gaps below cost **both** strength progression **and** injury resilience — the same missing patterns would deliver both.

1. **The hamstring's highest-force action has no training vehicle.** In running the biarticular hamstrings produce their peak force as **eccentric hip extension at long muscle length** in terminal swing [12] — simultaneously the most trainable hamstring strength quality and the exact action that fails in a strain. Seated leg curl is knee flexion only; superimposing hip extension recruits biceps femoris far more than knee flexion alone [13]. So the capacity S5 nominally wants to progress has no route to progress — and the single best-supported hamstring-injury intervention is absent with it: eccentric hamstring work cut hamstring injuries ~51% [14] (a 2021 methods reappraisal notes the magnitude is less certain [15]). One movement, both wins forgone.
2. **Glute max horizontal-force strength has no vehicle.** Glute max is the primary hip extensor on the ground and produces the *horizontal* propulsive force of running; squats load hip extension in the *vertical* vector only. A hip-thrust vs front-squat trial found the hip thrust improved sprint performance more, precisely because it loads hip extension near hip-neutral [16]. The preceding calibration artifact carried a hip thrust (`str.lower_b`); the threshold-development draft **dropped it**, deleting the one horizontal-force glute stimulus — a progressable strength quality *and* a propulsion/resilience contributor removed outright.
3. **Unilateral / frontal-plane hip strength is entirely absent.** No single-leg or abduction work. This costs a strength quality the state vector never names (unilateral hip-extension and abductor force) **and** the frontal-plane control that is a top-tier running-injury lever: hip-abductor/glute-med weakness drives iliotibial band syndrome [17] and patellofemoral pain [18], two of the most common runner overuse injuries. For an injury-resilience goal this is arguably the most conspicuous omission.
4. **The posterior chain has no progression path — only the quads do.** S2 (squat/quad e1RM) can climb via the load-driven back squat. But the hip-extensor state (glutes as horizontal-force producers, hamstrings as hip extensors) is trained only as a squat by-product or via a knee-flexion isolation, neither of which is wired to a progressing signal. Under a push philosophy this is the core defect: half the lower body cannot be pushed because nothing measures or loads it as a prime mover.
5. **Within-block progress pressure is nominal.** The `strength_progressing` exit criterion only requires each e1RM signal `> 0` (a readout exists), not that e1RM held or improved vs SWC — one logged session satisfies it. For a program whose stated point is to see how far strength can be pushed, the exit gate applies essentially no upward pressure (contra P8).

## 6. Internal contradiction — S5 is a broken contract

The state vector declares **S5 = "e1RM hip hinge (posterior chain)"** and the exit criteria require `e1rm.hip_hinge > 0`, but:
- There is **no hip hinge anywhere in the block**, and
- S5's estimator (`est.e1rm.hip_hinge`) is fed by `cap.set_log.legs_posterior` = the **seated ham curl**, a knee-flexion isolation, not a hinge.

The block's own contract says a hinge should exist and be *progressed* (S5 is a progression signal), yet the prescription contains no hinge and feeds S5 from a knee-flexion isolation. That is the internal evidence that the posterior-chain gap is an oversight, not a deliberate choice — the block wants to push hip-hinge strength and gave it nothing to push with.

## 7. Directions — actioned 2026-07-15

Organizing principle: **every lower-body strength quality gets a high-tension, progressable vehicle, and the known running-injury risk factors are directly trained** — lean volume via minimum-effective-dose logic [3][4], not piling on sets. Each addition below earns its slot by serving *both* goals. Status markers reflect what shipped into this authored program.

- **✓ Actioned — loaded hip hinge as a prime mover.** Romanian deadlift added to Legs 2 (4×5–8 @ 75% e1RM, RPE-8 top set + back-offs, 3s eccentric): the hip-extension + long-length hamstring vehicle (§5.1), the load-driven S5 state (§6), and the eccentric hamstring stimulus behind the ~51% strain reduction [14].
- **✓ Actioned — frontal-plane / unilateral hip work.** Bulgarian split squat added to Legs 2 (2×8–12/leg): unilateral strength + the glute-med frontal-plane control tied to ITBS/PFPS [17][18] (§5.3). A direct hip-abduction accessory remains an alternative for more isolated glute-med loading.
- **✓ Actioned — hip thrust as a horizontal-force strength lift.** Barbell hip thrust added to Legs 2 (3×8–12): restores the glute-max propulsion quality present in the preceding calibration artifact and missing from the threshold-development draft (§5.2).
- **✓ Held — the real constraints.** Legs 2 raised to ~50 min; weekly strength load 302/320 min under budget; `protect_long_run` / `protect_test` windows and the interference ceiling [5][6] intact.
- **✓ Actioned — real progression predicate for S2/S3/S5.** `strength_progressing` now requires `e1rm.*.dev_swc >= -1.0` (held-or-up vs 28-day SWC) instead of `> 0` (§5.5).
- **⏳ Open — measurement prerequisite.** The e1RM / tonnage / dev-SWC estimators are declared but not yet computed; capture set/rep/load and materialize the estimator engine, or progress stays unmeasurable (§3).

---

## References

1. Blagrove RC, Howatson G, Hayes PR. *Effects of Strength Training on the Physiological Determinants of Middle- and Long-Distance Running Performance: A Systematic Review.* Sports Med, 2018. https://link.springer.com/article/10.1007/s40279-017-0835-7
2. *The Effect of Strength Training Methods on Middle-Distance and Long-Distance Runners' Athletic Performance: A Systematic Review with Meta-analysis.* Sports Med, 2024. https://link.springer.com/article/10.1007/s40279-024-02018-z
3. Androulakis-Korakakis P, et al. *The Minimum Effective Training Dose Required to Increase 1RM Strength in Resistance-Trained Men* (and the powerlifter METD paper). Front Sports Act Living / Sports Med, 2020–2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8435792/
4. Spiering BA, et al. *Maintaining Physical Performance: The Minimal Dose of Exercise Needed to Preserve Endurance and Strength Over Time.* J Strength Cond Res, 2021. https://pubmed.ncbi.nlm.nih.gov/33629972/
5. Wilson JM, et al. *Concurrent Training: A Meta-Analysis Examining Interference of Aerobic and Resistance Exercises.* J Strength Cond Res, 2012. https://journals.lww.com/nsca-jscr/fulltext/2012/08000/concurrent_training__a_meta_analysis_examining.35.aspx
6. Schumann M, et al. *Compatibility of Concurrent Aerobic and Strength Training for Skeletal Muscle Size and Function: An Updated Systematic Review and Meta-Analysis.* Sports Med, 2022. https://link.springer.com/article/10.1007/s40279-021-01587-7
7. Baz-Valle E, et al. *The effects of exercise variation in muscle thickness, maximal strength and motivation in resistance trained men.* PLoS ONE, 2019. https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0226989
8. Fonseca RM, et al. *Changes in Exercises Are More Effective Than in Loading Schemes to Improve Muscle Strength.* J Strength Cond Res, 2014. https://journals.lww.com/nsca-jscr/fulltext/2014/11000/changes_in_exercises_are_more_effective_than_in.9.aspx
9. Kongsgaard M, et al. *Corticosteroid injections, eccentric decline squat training and heavy slow resistance training in patellar tendinopathy.* Scand J Med Sci Sports, 2009. https://pubmed.ncbi.nlm.nih.gov/19793213/
10. Beyer R, et al. *Heavy Slow Resistance Versus Eccentric Training as Treatment for Achilles Tendinopathy: A Randomized Controlled Trial.* Am J Sports Med, 2015. https://pubmed.ncbi.nlm.nih.gov/26018970/
11. Maeo S, et al. *Greater Hamstrings Muscle Hypertrophy but Similar Damage Protection after Training at Long versus Short Muscle Lengths* (seated vs prone leg curl). Med Sci Sports Exerc, 2021. https://doi.org/10.1249/MSS.0000000000002523
12. *The Role of Hamstring Contraction During Running* (terminal-swing eccentric hip-extension mechanics). Liberty University honors thesis. https://digitalcommons.liberty.edu/cgi/viewcontent.cgi?article=2218&context=honors
13. *Superimposing hip extension on knee flexion evokes higher activation in biceps femoris than knee flexion alone.* J Electromyogr Kinesiol, 2021. https://www.sciencedirect.com/science/article/abs/pii/S1050641121000286
14. Al Attar WSA, et al. / van Dyk N, et al. *Including the Nordic hamstring exercise in injury prevention programmes halves the rate of hamstring injuries: a systematic review and meta-analysis of 8459 athletes.* Br J Sports Med, 2019. https://www.researchgate.net/publication/331367089_Including_the_Nordic_hamstring_exercise_in_injury_prevention_programmes_halves_the_rate_of_hamstring_injuries_A_systematic_review_and_meta-analysis_of_8459_athletes
15. Impellizzeri FM, et al. *Why methods matter in a meta-analysis: a reappraisal showed inconclusive injury preventive effect of Nordic hamstring exercise.* J Clin Epidemiol, 2021. https://pubmed.ncbi.nlm.nih.gov/34520846/
16. Contreras B, et al. *Barbell hip thrust vs front squat — sprint performance* (Hip Thrust research summary). https://bretcontreras.com/hip-thrust-wiki-page/
17. Fredericson M, et al. *Hip abductor weakness / iliotibial band syndrome in runners.* https://pubmed.ncbi.nlm.nih.gov/15896092/
18. *Gluteus medius muscle activity in patellofemoral pain syndrome: A Systematic Review.* 2024. https://www.sciencedirect.com/science/article/abs/pii/S1360859224001189
