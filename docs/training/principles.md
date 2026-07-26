# Training System Principles

**Status:** adopted for v3 authoring and runtime decisions.

The system serves a trained runner pursuing a sub-three-hour marathon without a fixed deadline while preserving upper-body physique and lower-body strength. It uses Garmin recovery and activity data, training capture, and authored blocks to pursue measurable progress without treating recovery itself as the objective.

These principles govern authored training content and the runtime that interprets it. They are requirements, not claims that every automation described below is already implemented; current implementation status lives in [`roadmap.md`](roadmap.md).

## P1 — Progress is the objective; recovery is a constraint

Optimize change in the active block's declared state vector. HRV, resting heart rate, sleep, and tissue flags constrain training; they are not rewards to maximize. Flat performance with perfect recovery is a failure state.

## P2 — Every session declares a stimulus contract

Every card is exactly one of `overload`, `maintenance`, `measurement`, or `recovery`. The contract states what the session produces, preserves, estimates, or limits. A session without a defensible contract does not belong in a block.

## P3 — Maintenance preserves intensity before volume

When concurrent training requires a smaller strength dose, reduce volume while retaining the intensity needed to preserve the target quality. Avoid moderate-load, moderate-repetition work that creates fatigue without a clear adaptation target.

## P4 — One tissue, one owner

Each target tissue belongs to one active bundle. Compound exercises may involve tissues owned elsewhere, but only one bundle may target a tissue. Cross-bundle coordination prose is not a substitute for ownership.

## P5 — Policies, not scripts

Assignments carry explicit variants and machine-readable selection rules. The executed variant is logged. Conditional behavior must not be hidden in prose.

## P6 — Measure what must be protected

Every state component needs a capture path before the block starts. Strength uses set, repetition, and load capture; running uses tracked activity evidence plus the declared subjective fields. An unsensed quality cannot be reliably protected.

## P7 — Every collected field has a consumer

Each capture field names the estimator it feeds and the decision that estimator informs. Fields without an analysis contract are rejected.

## P8 — Measurement events and exit criteria create progress pressure

With no race deadline, blocks use required measurement events, explicit exit criteria, and bounded extensions. Races become high-quality measurement events when scheduled; taper logic does not activate without a race.

## P9 — Polarize the work

Overload sessions must be strong enough to cause the declared adaptation, and easy/recovery sessions must remain easy. Uniform medium effort is neither adequate stimulus nor adequate recovery.

## P10 — Confounds are first-class context

Protocol changes, heat season, chronic load, new equipment, illness, and similar conditions are tagged or logged. Change one material input at a time where practical; identify the confound when that is impossible.

## P11 — Validate invariants before activation

The integrated block is compiled and linted for ownership, budgets, scheduling conflicts, signal closure, state coverage, load resolvability, block identity, variant adequacy, novelty tags, and exit criteria. Errors block activation; warnings require explicit acknowledgement.

## P12 — Compute the review; ask the human for the residual

The system should compute comparisons that telemetry and capture can answer. Human prompts are reserved for mechanics, motivation, pain, and other evidence the sensors cannot observe.

## P13 — Fuse priors without anchoring to them

Older performance information may bound plausibility with appropriately wide uncertainty. It must not silently set current zones or override current-season measurement evidence.

## Surface rule

Every surface, score, card, and metric must name the objective it serves and the decision it informs. Otherwise it is demoted to supporting evidence or removed.
