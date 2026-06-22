# D12 — Contract Consumer Audit (HRV tab field removals)

**Status:** Audit complete. Engineering deliverable for D12 of
`2026-06-17-hrv-tab-design-decisions.md` — *not* a finding run (no statistical content). Gates the
"stop rendering vs delete from contract" decision for the three fields D5/D6 retire:
`baseline_bands`, `trajectory`, `status_mix`.

**Method:** grep every layer for each field/type/constructor — backend `app/` (constructors,
readers, OpenAPI), generated `frontend/src/lib/api-types.ts`, frontend `src/` components, and
`backend/tests/`. A field is **delete-safe** only if, after the HRV tab stops rendering it, no other
consumer remains.

**Headline result:** all three are **delete-safe**. Each is consumed by exactly **one** frontend
file — the HRV tab `src/routes/hrv/+page.svelte` — and by **no** cross-domain backend code (only the
analytics contracts + `analysis`/`insights` layers that produce them). Two name-collision traps below
must be respected so the deletion does not over-reach.

---

## Field 1 — `baseline_bands` (D5: drop Garmin baseline zones)

| Layer | Site | Action |
| --- | --- | --- |
| Contract (type) | `contracts/analysis.py:83` `HrvBaselineBands`; exported `contracts/__init__.py:17,136` | delete |
| Contract (field) | `contracts/insights.py:11,147` `baseline_bands: HrvBaselineBands \| None` | delete |
| Producer | `domain/analysis/hrv_patterns.py:35` `extract_baseline_bands` | delete |
| Composer | `domain/insights/hrv.py:220,246` (`extract_baseline_bands(day_rows)` → response) | delete the call + the response kwarg |
| Frontend (only consumer) | `src/routes/hrv/+page.svelte:262` `baselineBands`; `332–365` `annotationPlugin` drawing the zones on the trend chart | stop rendering (remove the annotation plugin block) |
| Tests | `test_hrv_service.py` `TestBaselineBands` (547–592, 3 cases) | delete the class |

> ⚠ **Name-collision trap — do NOT delete the source readings.** The field *names*
> `baseline_low_upper` / `baseline_balanced_lower` / `baseline_balanced_upper` / `five_min_high`
> also live on the **raw `HrvSummary` reading** (`contracts/readings.py:107–109`) and are populated
> by the **FIT extractor** (`infra/fit_parser/extractors.py:179–181`). Those are upstream Garmin
> source data feeding `compute_daily_hrv` and the persisted mart — **keep them.** Only the analytics
> `HrvBaselineBands` projection is retired.

**Verdict:** delete-safe. One consumer (the HRV tab annotation plugin).

---

## Field 2 — `trajectory` (D6: drop overnight trajectory mini-bar)

| Layer | Site | Action |
| --- | --- | --- |
| Contract (type) | `contracts/analysis.py:109` `HrvTrajectory`; exported `contracts/__init__.py:22,152` | delete |
| Contract (field) | `contracts/insights.py:14,149` `trajectory: HrvTrajectory \| None` | delete |
| Producer | `domain/analysis/hrv_patterns.py:84` `compute_trajectory` (+ the module docstring line 3 mention) | delete fn; update docstring |
| Composer | `domain/insights/hrv.py:224,248` | delete the call + the response kwarg |
| Frontend (only consumer) | `src/routes/hrv/+page.svelte:139` `historicalTrajectory`; render `850–864`; helpers `trajectoryColor` (620) / `trajectoryArrow`; CSS `.trajectory-*` (1322–1356) | stop rendering (remove the mini-bar block + dead helpers/CSS) |
| Tests | `test_hrv_service.py` `TestTrajectory` (~674–744, the structural/direction cases) | delete those cases |

> ⚠ **Name-collision trap — `HrvTrajectory` ≠ the recovery-score trajectory.** The grep for
> "trajectory" also hits `domain/dashboard.py`, `domain/recovery_score/evidence.py` & `regimes.py`,
> `contracts/dashboard.py`, and `primitives/trends.py` — these are the **recovery-score time
> series** ("score trajectory", hover-brushing window), an unrelated concept. They do **not**
> reference `HrvTrajectory` and must be left untouched. Confirmed: no file outside
> `contracts/ analysis/ insights/` imports `HrvTrajectory`.

> 🔗 **Sequencing coupling with D12-#3.** The already-landed cleanup test
> `test_falling_trajectory_no_longer_emits_insight` (`test_hrv_service.py:745–767`) asserts
> `result.trajectory is not None` while proving the deleted rule emits nothing. When the
> `trajectory` field is removed, **drop the two `result.trajectory*` assertions from that test**
> (keep the non-emission assertion — that is the test's real point). This is the one place the two
> changes interact.

**Verdict:** delete-safe. One consumer (the HRV tab mini-bar).

---

## Field 3 — `status_mix` (D6: drop 14-day status-mix bar)

| Layer | Site | Action |
| --- | --- | --- |
| Contract (type) | `contracts/insights.py:98` `HrvStatusBucket`; exported `contracts/__init__.py:66,150` | delete |
| Contract (field) | `contracts/insights.py:150` `status_mix: list[HrvStatusBucket]` | delete |
| Producer/Composer | `domain/insights/hrv.py:13,112,225,249` `_compute_status_mix` | delete fn + call + response kwarg |
| Frontend (only consumer) | `src/routes/hrv/+page.svelte:140` `historicalStatusMix`; render `871–886` | stop rendering |
| Tests | `test_hrv_service.py:158` (`sum(bucket.count …) == 2`, inside `test_adds_stable_signal_when_metrics_look_good`) | drop that one assertion (keep the rest of the test) |

**Verdict:** delete-safe. One consumer (the HRV tab status-mix bar).

---

## Cross-cutting findings

- **No API consumer outside the HRV tab.** Nothing in `src/routes/` other than `hrv/+page.svelte`
  reads any of the three. No backend route, serializer, or other domain references the three types
  (only the contracts + `analysis`/`insights` that build them).
- **`HrvInsightsResponse` shrinks by three fields.** All three are emitted solely on the HRV insights
  response; removing them is a pure contract reduction with a single-surface frontend impact.
- **Schema change ⇒ regenerate types.** Any of these deletions changes the OpenAPI schema, so the
  flow is mandatory: edit backend → `scripts/generate-api-types.sh` → commit regenerated
  `api-types.ts` → `npm run check`.

## Recommended sequence (when D12 is approved for implementation)

1. **Frontend stop-render first** (no contract change yet): remove the annotation plugin, the
   trajectory mini-bar + dead helpers/CSS, and the status-mix bar from `hrv/+page.svelte`;
   `npm run check`; visually verify the tab via browser MCP (per CLAUDE.md). This is independently
   shippable and reversible.
2. **Backend contract deletion:** remove the three types, the `baseline_bands`/`trajectory`/
   `status_mix` response fields, `extract_baseline_bands` / `compute_trajectory` /
   `_compute_status_mix`, and their composer wiring in `insights/hrv.py`. **Preserve** the raw
   `HrvSummary` baseline fields + FIT extractor and the recovery-score trajectory code.
3. **Tests:** delete `TestBaselineBands` and the structural `TestTrajectory` cases; drop the
   `result.trajectory*` assertions from `test_falling_trajectory_no_longer_emits_insight` and the
   `status_mix` assertion from `test_adds_stable_signal_when_metrics_look_good`.
4. **Regenerate + validate:** `scripts/generate-api-types.sh`, then ruff + pyright + pytest +
   `npm run check`; commit the regenerated `api-types.ts` in the same change.

This audit is the "consumer audit, not more statistical analysis" that D12 requires; with it, the
three removals are unblocked for the Gate-3 implementation step.
