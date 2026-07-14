# Training System — Current State and Next Work

**Status:** current implementation boundary and remaining objectives.

This file contains only current state and work that still changes the product. Git history records how the pivot arrived here. [`general_principles.md`](general_principles.md) governs training decisions; [`schema_v3_spec.md`](schema_v3_spec.md) describes the shipped artifact contract.

## Current state

- **Block 1 is the active authored block.** `block1/` contains the six import artifacts for a 28-day threshold-development block beginning 2026-07-13. `block0/` is retired and retained only as the frozen schema exemplar and validator/import test fixture.
- **v3 import and execution are shipped.** A six-file upload is strictly parsed, compiled, linted L1-L12, and activated atomically. The Today and schedule-window reads project the active block; logs capture status, variant, notes, set/rep/load, run RPE, and tissue check-ins.
- **Running activity evidence is shipped.** Running FIT files parse into session/lap/series storage, display in Runs, associate with `running.v3` cards, and can establish effective execution.
- **Imported-block measurement handling is shipped.** Training evaluates the authored LTHR protocol from tracked run evidence, applies hard quality gates, composes the exact Coach assessment, activates authored backup opportunities at read time, and exposes estimator eligibility without mutating the imported schedule.
- **Coach v1 is shipped.** Coach owns queued reviews/chat, bounded evidence workspaces, semantic memory, and subjective measurement assessments. It does not create or edit training content and does not replace the general estimator engine.
- **Selection is still human-driven.** The app displays authored variants and rules and records the chosen branch, but it does not yet evaluate the registry's morning selection rules.
- **The signal registry is declarative only.** The active `block1/registry.json` validates and is stored verbatim; most estimators and materialized training-state signals it declares are not yet computed.
- **Strength and breathing activity files remain download-only.** Strength set/rep/load capture exists in training logs, but Garmin strength FIT sessions are not parsed or associated.

## Remaining implementation objectives

### 1. Materialize the active registry

Implement the estimators and signals declared by `block1/registry.json`, starting with the inputs already captured or ingested: HRV/RHR baselines, LTHR evidence, set-log e1RM and tonnage, planned-versus-executed work, tissue check-ins, and daily load. Persist outputs so weekly reviews and selection rules consume one auditable source.

This engine is separate from Coach. Coach may explain its outputs, but deterministic estimators own the values.

### 2. Parse and associate strength activities

Implement the session-first parser and read model in [`../future/strength-activities.md`](../future/strength-activities.md). Join a tracked strength session to its prescribed training occurrence without using Garmin's unreliable inferred exercise/set labels as the source of set, rep, load, or tonnage truth; the training capture log remains authoritative for those fields.

### 3. Evaluate selection rules

Once required signals are materialized, evaluate the authored decision list with staleness handling, expose the selected variant and evidence snapshot, preserve manual override, and log the executed branch. Missing inputs must follow each assignment's explicit `on_missing_signal` policy.

### 4. Reframe the overview around training state

After the state signals exist, add progress lanes for the active state vector and a compact constraint strip. The existing recovery dashboard remains the shipped recovery view; do not imply that it already measures load, adaptation, or workout readiness.

### 5. Calmness remains gated

Do not add meditation/breathwork content or make response claims until a morning-after calmness capture with an analysis contract exists. Any future implementation must enter through the current authored import contracts rather than reviving a parallel runtime.

## Standing rules

- Import/upload is the only content ingress. Do not add generators, translators, seeders, or derived bundle artifacts.
- Store uploaded artifacts verbatim. Runtime views may overlay evidence and authored backup behavior but never rewrite content.
- Capture ships before analysis when data cannot be recovered later; analysis may backfill from stored capture.
- The frontend formats and renders backend-owned values; it does not compute training or health statistics.
- Baselines and measurements preserve local-date and condition-tag semantics.
