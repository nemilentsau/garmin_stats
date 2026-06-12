# Dashboard Recovery Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ONLY the dashboard **overview** scaffold (the readiness ring + four sparkline cards + four hardcoded 0–25 readiness components) with the validated recovery score, presented as one shared-axis trajectory + an aligned evidence table + an inline flag strip. The nine per-metric detail tabs are **kept exactly as-is** (they carry intraday curves, distributions, sleep stages, HR zones, circadian profiles that a daily score cannot encode); the overview's evidence rows and flags **link into** those existing tabs. Behavior-preserving code de-duplication of the metric pages is allowed but optional.

**Explicit non-goals (corrected scope):** Do NOT remove, collapse, or change the information shown by `/heart-rate`, `/hrv`, `/sleep`, `/stress`, `/body-battery`, `/respiration`, `/skin-temp`, `/pulse-ox`. Do NOT touch `/today`, `/routines`, `/experiments`, `/programs`, `/assistant`. Do NOT add an experiment-response number (R10: blocked on data). **Keep the recovery score on its robust-z scale — do NOT invent a 0–100 mapping yet** (deferred UX decision). **Phase E (detail-tab code de-duplication) is DEFERRED for this iteration** — implement Phases A–D only.

**Architecture:** A new backend `recovery_score` domain computes the validated score + two flags; `compute_dashboard_overview` assembles a new `DashboardOverviewResponse`. The contract flows OpenAPI → generated TS types. The frontend rebuilds ONLY `/+page.svelte` around three non-card components; the evidence rows and flag chips are links to the existing detail tabs.

**Tech Stack:** Backend FastAPI + Pydantic + numpy (Python 3.14, `uv`); frontend SvelteKit 2 / Svelte 5 runes / Tailwind 4 / Chart.js 4 / TS.

**Source of truth for every number/weight/threshold:** `FINDINGS.md`, `docs/dashboard-metrics-plan.md` (the VALIDATED score contract), `docs/dashboard-drilldown-spec.md` (R8), and the `.claude/finding-runs/2026-06-11-*` runs. Nothing here is invented.

---

## PART 0 — WHAT THE SCORE IS, AND WHY THE OVERVIEW CHANGES (read first)

### The recovery score (the central object — stated plainly)

**A single daily index of overall autonomic recovery state, on the user's personal scale.**

- **Inputs (7 daily aggregates already in the mart):** resting HR, HR avg, stress, respiration (stress-pole → recovery-negative); body battery, nightly HRV, sleep score (recovery-pole → recovery-positive).
- **Construction:** (1) normalize each metric to a robust z vs the user's OWN expanding history (median/MAD×1.4826, current day excluded, ≥30 prior present days); (2) sign each so higher = better recovery; (3) weighted mean with correlation-deflated weights (≈ equal, ~0.135–0.159) over ≥5 of 7 present inputs; (4) seeded 7-day MA for the displayed trend.
- **Output:** a robust-z, ~[−3, +3]. 0 = the user's typical recovery; negative = suppressed; positive = strong. Read as **level-vs-baseline + trend**, never as a raw number.
- **What it is / isn't:** a recovery/autonomic-state summary, validated out-of-sample (R6) to track real regimes (Nov suppression, Feb plateau). NOT a training/performance score (no activity data). It deliberately collapses seven correlated metrics into one because R4 proved they are **one axis** — and that collapse is exactly why the detail tabs stay: the score answers "what is my overall state and trend," the tabs answer "what is each system actually doing."

### Why the OVERVIEW (and only the overview) changes

The overview today (`+page.svelte`) is a readiness ring gauge (`457-512`) + a 2-column grid of four sparkline "metric cards" (`514-559`). That presentation is wrong for this data, for reasons that do not apply to the detail tabs:

1. **It isolates co-moving signals.** The four metrics are one axis (|r| 0.5–0.84). Four cards with four independent y-axes hide that resting-HR↑ + HRV↓ + stress↑ is ONE event. A shared-axis trajectory shows the autonomic state moving as a whole.
2. **It foregrounds a meaningless number.** A robust-z has meaning only relationally (vs baseline) and temporally (trend). The ring/card format enlarges the number and shrinks the trend. A gauge is never right for a value whose meaning is its trajectory (Few).
3. **The four readiness components are arbitrary** (hardcoded 0–25 each) — the literal thing the refactor exists to delete.

The forcing rule (Task A1, also added to the ux-design skill): *before any card grid, ask — does this data need to be COMPARED across items or read as a TREND? If yes, cards are wrong.* The overview's metrics need both → trajectory + aligned table. The **detail tabs are exempt**: each shows ONE system's intraday/distribution/architecture detail, which is genuinely card/panel-shaped and stays untouched.

### The approved overview shape (the evidence rows LINK to the existing tabs)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Typical recovery, improving        score −0.2 z          synced 2h ago        │  ← state line (a sentence, not a ring)
├─────────────────────────────────────────────────────────────────────────────┤
│   recovery (robust z, vs personal baseline)            ┌── 7d / 30d / 90d ─┐  │
│  +2 ┤                          ╱▔▔╲                                           │  ← HERO: one shared-axis trajectory,
│   0 ┤·······█baseline band█···╱······╲····················█·······            │     raw (thin) + MA7 (bold, seeded),
│  -2 ┤   ╲___╱              ╲_╱          ╲___╱▔▔                                │     baseline band, event annotations
│     └──Nov regime──┴──plateau──┴───softening───┴──now→                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ WHAT MOVED IT (today vs your baseline)                         sorted by |Δz| │
│ metric →tab    latest    baseline    Δz       ····7d····    src   coverage    │  ← EVIDENCE TABLE (not cards):
│ HRV →/hrv      42 ms     53 ms     −1.8 ▼    ╲╱╲▁▁╲         der    ●          │     aligned rows, tabular figures;
│ Resting HR →   58 bpm    50 bpm    +1.6 ▲    ▁▁╱╱╲╱        dev    ●          │     each row LINKS to its detail tab.
│ Stress →       47        32        +1.4 ▲    ▁▁╱▔▔╲        der    ●          │     Scan the Δz column to SEE the
│ Body Battery → 18        31        −1.2 ▼    ▔╲╲▁▁▁        der    ●          │     co-movement cards hide.
│ Respiration →  14.1      13.0      +0.9 ▲    ▁▁▁╱╱╲        nat    ●          │
│ Sleep →/sleep  41        62        −0.8 ▼    ▔▔╲╲▁╱        der    ○ degraded │
├─────────────────────────────────────────────────────────────────────────────┤
│ ○ Oxygen: clear →/pulse-ox     ▲ Thermo: clear →/skin-temp   (no SpO₂ 2d)     │  ← FLAG STRIP: links to the tabs
└─────────────────────────────────────────────────────────────────────────────┘
```

The overview becomes the **synthesis + hub**: it states the overall recovery state and trend, shows what drove it, and links each driver into the existing detailed tab. The tabs are the depth; the overview is the entry point — not a replacement for them.

---

## PART 1 — THE THREE QUESTIONS

### Q1 — Frontend: what changes, and what does not

**Changes:** ONLY `frontend/src/routes/+page.svelte` (the overview) and `+layout.svelte` is left alone (the nav and all nine tabs stay).

| Area | Change |
|---|---|
| Overview readiness ring (`457-512`) | **Delete.** Replaced by `StateLine` + `RecoveryTrajectory`. |
| Overview four-card `metric-grid` (`514-559`) | **Delete.** Replaced by `EvidenceTable` (rows link to tabs) + `FlagStrip`. |
| Overview JS (`metricConfigs`, `componentOrder`, `componentInfo`, `deltaColor`, `readinessColor`, sparkline canvases) | **Delete** (now dead). |
| Freshness/sync banner, empty/loading/error branches | **Keep.** |
| Nine detail tabs + nav | **Keep exactly as-is.** Evidence rows + flag chips link to them. |

**New non-card components** (`frontend/src/lib/components/recovery/`): `StateLine`, `RecoveryTrajectory`, `EvidenceTable`, `EvidenceSparkline`, `FlagStrip`. **Keep** `ChartCanvas.svelte`. The overview stops using `StatCard`/`ChartCard`; the detail tabs keep using them unchanged.

**Optional, separable (Phase E):** behavior-preserving de-duplication of the metric pages' chart-builder boilerplate — extract a `buildLineConfig()` factory and a `<StatBar>` component, consolidate ad-hoc CSS tokens. **No chart, stat, or feature removed; each refactor verified screenshot-identical.** This is the only thing that touches the detail tabs, and it changes their *code*, never their *output*.

### Q2 — API contract: what changes from removing the four overview plots

The four plots are `DashboardSparklines` (`contracts/dashboard.py:68-74`), part of the overview response only. Swap the overview response (this does NOT affect any per-metric endpoint, which the detail tabs use):

- **Remove** (old overview scaffold): `ReadinessScore`, `DashboardSparklines` + `SparklineSeries`/`SparklinePoint`/`SparklineSummary`, `MetricCorrelation` + `CorrelationPoint` (the overview's HRV-vs-X scatter; the `/hrv` tab's own correlations come from a *different* endpoint — confirmed by grep in Task B-contract Step 5), most of `TodayVitals`.
- **Add:** `RecoveryScorePoint{date, raw, ma7, baseline_lo, baseline_hi}`; `RecoveryState{band, trend, score_z, label}`; `MeaningfulChange{delta7_z, is_meaningful, direction, comparison_label, delta1_z, is_acute}`; `EvidenceRow{metric, label, tab_href, source_type, latest_value, unit, baseline, delta_z, delta_raw, meaningful, coverage_ok, degraded, sparkline}`; `HealthFlag{kind, state, value, threshold, direction, recent, tab_href}`; `StructuralGap{start, end}`; new `DashboardOverviewResponse{date, state, score, change, evidence, flags, spo2_gaps}`.

Then `bash scripts/generate-api-types.sh`, commit the regenerated `api-types.ts`, `cd frontend && npm run check`.

### Q3 — Backend: what changes

New `backend/app/domains/garmin_analytics/domain/recovery_score/` (closest domain, per CLAUDE.md). Pure testable units porting validated analyst logic:

| Module | Responsibility | Source |
|---|---|---|
| `normalization.py` | expanding robust-z (median/MAD, current day excluded, ≥30 prior, else None) | R3 |
| `weighting.py` | recovery-signed deflated weights (RHR .142 / HRavg .148 / stress .139 / resp .137 / BB .135 / HRV .140 / sleep .159), per-day renorm over ≥5/7 | R1 |
| `smoothing.py` | seeded trailing-7 MA | R5 |
| `thresholds.py` | Δ7/Δ1 (≥0.97 / ≥1.86 z), band (±0.5 z), trend | R2 + Q4.1 |
| `flags.py` | oxygen spo2_avg < median−2.5·MAD; thermo skin-temp outside median±2.5·MAD; "unknown" on missing; structural gaps | R9 |
| `evidence.py` | assemble 7 evidence rows + per-input sparkline window + source-type + `tab_href` | R8 |

Rewrite `domain/dashboard.py::compute_dashboard_overview` to assemble from these; delete `_compute_readiness`, `_compute_sparklines`, `_compute_correlations`, `_compute_vitals`, `_recovery_status`, `_format_delta_magnitude`. The per-metric API endpoints (used by the detail tabs) are **not touched**.

**Perf:** expanding-z is O(n²); n≈373, computed once over the loaded metrics per request — fine. Cap at a trailing 365-day window only past ~2 years (R3 noted it's indistinguishable now); leave a comment, out of scope.

---

## PART 2 — FILE STRUCTURE

**Backend — create:** `domain/recovery_score/{__init__,normalization,weighting,smoothing,thresholds,flags,evidence}.py`; `tests/domains/garmin_analytics/recovery_score/test_*.py` (one per module).
**Backend — modify:** `contracts/dashboard.py` (swap models); `domain/dashboard.py` (rewrite `compute_dashboard_overview`, delete the four `_compute_*` + two helpers).
**Frontend — create:** `lib/components/recovery/{StateLine,RecoveryTrajectory,EvidenceTable,EvidenceSparkline,FlagStrip}.svelte`; `lib/recovery-format.ts` (display-only).
**Frontend — modify:** `routes/+page.svelte` (overview only); `lib/api-types.ts` (regenerated).
**Frontend — UNCHANGED:** all nine detail `+page.svelte`, `+layout.svelte` nav. (Phase E may de-dup their internals, behavior-preserving.)
**Skill/docs — modify:** `.claude/skills/ux-design/SKILL.md` + `CLAUDE.md` (the rule); `docs/dashboard-drilldown-spec.md` (correct the "replaces the tabs" error → "links to the tabs").

---

## PART 3 — PHASED TASKS

> Frontend tasks specify responsibility + typed props + structure + browser-MCP verification, not frozen Svelte (visual-iteration + display-only; pre-writing unverified UI is the garbage to avoid). Backend/contract tasks give complete TDD code.

### Phase A — Encode the anti-card rule + fix the spec doc

#### Task A1: Add the forcing rule to ux-design + CLAUDE.md
**Files:** Modify `.claude/skills/ux-design/SKILL.md`, `CLAUDE.md`.
- [ ] **Step 1: Add to `ux-design/SKILL.md`** (under "Visual System"):

```markdown
## Cards Are a Last Resort (forcing rule)

Before rendering any card/tile/grid-of-boxes, answer out loud:
> **Does this data need to be COMPARED across items, or read as a TREND over time?**
> If yes, a card grid is the wrong container — it isolates what should be aligned.

- Comparison across items → an aligned table or small multiples (shared axis/scale).
- Trend over time → one shared-axis time series (raw + smoothed).
- A self-contained independent entity (one routine, one experiment, one detail-metric page) → a card/panel is fine.

Cards are correct for independent objects and for a single metric's own detail surface; they are
wrong for facets of one signal shown together. The dashboard OVERVIEW's recovery metrics are one
axis (they co-move) → aligned evidence table + shared trajectory, never a per-metric card grid.
The per-metric DETAIL tabs each show one system and are exempt. Erase any pixel that is not data
(Tufte); a ring/gauge is never right for a value whose meaning is its trend (Few).
```

- [ ] **Step 2: Append to the `ux-design` bullet in `CLAUDE.md`:** `Includes the "Cards Are a Last Resort" forcing rule — apply before any card/grid; the per-metric detail tabs are exempt.`
- [ ] **Step 3: Commit** — `git commit -m "ux-design: add 'Cards Are a Last Resort' forcing rule"`

#### Task A2: Correct the drill-down spec's tab-scope error
**Files:** Modify `docs/dashboard-drilldown-spec.md`.
- [ ] **Step 1:** Replace every claim that the per-metric tabs are "replaced/removed/collapsed" with: the overview's evidence rows and flags **link into** the existing detail tabs, which are kept as-is. Remove the L3 "per-input small multiples" and "sleep-architecture sub-section" recreations (those duplicate what `/hrv`, `/sleep`, etc. already show) — the L3 drill-down IS the existing tabs, reached via the evidence-row links.
- [ ] **Step 2: Commit** — `git commit -m "drilldown-spec: correct scope — overview links to detail tabs, does not replace them"`

### Phase B — Backend recovery-score domain (TDD, complete code)

*(Unchanged from the validated math; the detail-tab endpoints are untouched.)*

#### Task B1: Normalization (expanding robust-z)
**Files:** Create `domain/recovery_score/normalization.py`; Test `…/test_normalization.py`.
- [ ] **Step 1: Failing tests**

```python
# test_normalization.py
"""Expanding robust-z — warm-up boundary, current-day exclusion, MAD-degenerate fallback."""
import math
from app.domains.garmin_analytics.domain.recovery_score.normalization import expanding_robust_z

def test_warmup_returns_none_before_30_prior_present_days():
    assert expanding_robust_z([1.0] * 29 + [5.0])[29] is None

def test_value_defined_at_exactly_30_prior_days():
    assert expanding_robust_z(list(range(30)) + [100.0])[30] is not None

def test_current_day_excluded_from_its_own_baseline():
    assert expanding_robust_z([10.0] * 30 + [10.0])[30] == 0.0

def test_nan_inputs_skipped_not_counted():
    out = expanding_robust_z([1.0] * 20 + [None] * 5 + [1.0] * 10 + [9.0])
    assert out[35] is not None and out[22] is None

def test_degenerate_spread_falls_back_to_std():
    out = expanding_robust_z([5.0] * 30 + [6.0])
    assert out[30] is not None and math.isfinite(out[30])
```

- [ ] **Step 2: Run → FAIL** (`cd backend && uv run pytest tests/domains/garmin_analytics/recovery_score/test_normalization.py -v`).
- [ ] **Step 3: Implement**

```python
# normalization.py
"""Per-metric expanding robust-z for the recovery score.

Each day is z-scored vs the median/MAD of the user's own PRIOR present days
(expanding, current day excluded), requiring >= 30 priors. Validated in run
2026-06-11-recovery-normalization-baseline (trailing windows absorb regimes;
expanding is the shippable baseline)."""
from __future__ import annotations
import numpy as np

MIN_PRIOR_DAYS = 30
_MAD_SCALE = 1.4826

def expanding_robust_z(values: list[float | None]) -> list[float | None]:
    out: list[float | None] = []
    arr = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            out.append(None); continue
        prior = arr[:i][~np.isnan(arr[:i])]
        if len(prior) < MIN_PRIOR_DAYS:
            out.append(None); continue
        med = float(np.median(prior))
        mad = float(np.median(np.abs(prior - med))) * _MAD_SCALE
        scale = mad if mad > 1e-9 else (float(np.std(prior)) or 1e-9)
        out.append((float(arr[i]) - med) / scale)
    return out
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: expanding robust-z (R3)"`

#### Task B2: Weighting
**Files:** Create `…/weighting.py`; Test `…/test_weighting.py`.
- [ ] **Step 1: Failing tests**

```python
# test_weighting.py
"""Recovery-signed correlation-deflated weighting, per-day renormalization, >=5/7 gate."""
import math
from app.domains.garmin_analytics.domain.recovery_score.weighting import (
    RECOVERY_SIGNS, DEFLATED_WEIGHTS, weighted_recovery_score)

def test_keys_and_weight_sum():
    keys = {"heart_rate_resting","heart_rate_avg","stress_avg","respiration_avg",
            "body_battery_avg","hrv_nightly_avg","sleep_score"}
    assert set(RECOVERY_SIGNS) == keys == set(DEFLATED_WEIGHTS)
    assert math.isclose(sum(DEFLATED_WEIGHTS.values()), 1.0, abs_tol=1e-6)

def test_all_present_recovery_positive():
    # recovery-positive z for every metric -> positive score
    z = {"hrv_nightly_avg":1.0,"body_battery_avg":1.0,"sleep_score":1.0,
         "heart_rate_resting":-1.0,"heart_rate_avg":-1.0,"stress_avg":-1.0,"respiration_avg":-1.0}
    score, n = weighted_recovery_score(z)
    assert score > 0 and n == 7

def test_missing_inputs_renormalize():
    score, n = weighted_recovery_score({"hrv_nightly_avg": 2.0, "body_battery_avg": 2.0})
    assert math.isclose(score, 2.0, abs_tol=1e-9) and n == 2

def test_below_five_inputs_none():
    score, n = weighted_recovery_score({"hrv_nightly_avg":1.0,"sleep_score":1.0,
                                        "body_battery_avg":1.0,"stress_avg":-1.0})
    assert score is None and n == 4
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# weighting.py
"""Correlation-deflated, recovery-signed weighting of the seven axis metrics.

Weighting is practically immaterial (run 2026-06-11-recovery-score-weighting:
equal/deflated/PC1 agree at r>=0.9996); deflated adopted for its double-count
defense. Caller passes RAW per-metric z; signs are applied here. >=5/7 present."""
from __future__ import annotations

MIN_INPUTS = 5
RECOVERY_SIGNS: dict[str, int] = {
    "heart_rate_resting": -1, "heart_rate_avg": -1, "stress_avg": -1,
    "respiration_avg": -1, "body_battery_avg": +1, "hrv_nightly_avg": +1, "sleep_score": +1}
DEFLATED_WEIGHTS: dict[str, float] = {
    "heart_rate_resting": 0.142, "heart_rate_avg": 0.148, "stress_avg": 0.139,
    "respiration_avg": 0.137, "body_battery_avg": 0.135, "hrv_nightly_avg": 0.140, "sleep_score": 0.159}

def weighted_recovery_score(raw_z: dict[str, float]) -> tuple[float | None, int]:
    present = {k: v for k, v in raw_z.items() if v is not None and k in DEFLATED_WEIGHTS}
    if len(present) < MIN_INPUTS:
        return None, len(present)
    num = sum(RECOVERY_SIGNS[k] * v * DEFLATED_WEIGHTS[k] for k, v in present.items())
    den = sum(DEFLATED_WEIGHTS[k] for k in present)
    return num / den, len(present)
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: deflated weighting (R1)"`

#### Task B3: Smoothing (seeded MA7)
**Files:** Create `…/smoothing.py`; Test `…/test_smoothing.py`.
- [ ] **Step 1: Failing tests**

```python
# test_smoothing.py
"""Seeded trailing-7 MA — the seed fills the left edge so the display window does not ramp."""
from app.domains.garmin_analytics.domain.recovery_score.smoothing import seeded_ma7

def test_seeded_left_edge_differs_from_naive():
    seeded = seeded_ma7([0.0]*6, [3.0, 3.0, 3.0])
    assert seeded[0] < 3.0 and len(seeded) == 3

def test_no_seed_equals_plain_trailing_ma():
    assert seeded_ma7([], [1.0, 2.0, 3.0])[0] == 1.0

def test_none_values_skipped():
    assert seeded_ma7([], [2.0, None, 4.0])[2] == 3.0
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement** (mirrors `domain/primitives/trends.py:50`):

```python
# smoothing.py
"""Seeded trailing-7-day MA for the displayed recovery trend.

Compute the MA over seed + display then drop the seed, so the first displayed
points use the 6 prior days instead of ramping from one point. Validated window
in run 2026-06-11-recovery-score-smoothing-spec (MA7: 86% plateau-noise cut, 0
onset lag, sustained depth preserved)."""
from __future__ import annotations
from app.utils.numeric import safe_avg

WINDOW = 7
SEED_DAYS = WINDOW - 1

def seeded_ma7(seed: list[float | None], display: list[float | None]) -> list[float | None]:
    combined = list(seed) + list(display)
    out: list[float | None] = []
    for i in range(len(combined)):
        out.append(safe_avg([v for v in combined[max(0, i - SEED_DAYS): i + 1] if v is not None]))
    return out[len(seed):]
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: seeded MA7 (R5)"`

#### Task B4: Thresholds, band, trend
**Files:** Create `…/thresholds.py`; Test `…/test_thresholds.py`.
- [ ] **Step 1: Failing tests**

```python
# test_thresholds.py
"""Δ7/Δ1 meaningful-change, score band, trend direction (R2 + Q4.1)."""
from app.domains.garmin_analytics.domain.recovery_score.thresholds import (
    T7, T1, is_meaningful_delta7, is_acute_delta1, score_band, trend_direction)

def test_validated_thresholds(): assert T7 == 0.97 and T1 == 1.86
def test_delta7_boundary():
    assert is_meaningful_delta7(0.97) and is_meaningful_delta7(-0.97) and not is_meaningful_delta7(0.96)
def test_acute_boundary():
    assert is_acute_delta1(-1.86) and not is_acute_delta1(-1.85)
def test_band_cuts():
    assert score_band(-1.2)=="suppressed" and score_band(0.0)=="typical" and score_band(1.2)=="strong"
def test_trend():
    assert trend_direction(0.97)=="improving" and trend_direction(-0.97)=="declining" and trend_direction(0.5)=="steady"
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# thresholds.py
"""Meaningful-change thresholds, score band, trend direction.

T7/T1 from run 2026-06-11-recovery-score-meaningful-change (default comparison:
7-day mean vs prior 7-day mean). Band cuts at +-0.5 z realize the Q4.1 continuum
-> band x trend banner; no discrete archetypes."""
from __future__ import annotations

T7, T1, _BAND = 0.97, 1.86, 0.5

def is_meaningful_delta7(d: float) -> bool: return abs(d) >= T7
def is_acute_delta1(d: float) -> bool: return abs(d) >= T1
def score_band(z: float) -> str:
    return "suppressed" if z <= -_BAND else "strong" if z >= _BAND else "typical"
def trend_direction(d7: float) -> str:
    return "improving" if d7 >= T7 else "declining" if d7 <= -T7 else "steady"
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: thresholds, band, trend (R2 + Q4.1)"`

#### Task B5: Health flags + structural gaps
**Files:** Create `…/flags.py`; Test `…/test_flags.py`.
- [ ] **Step 1: Failing tests**

```python
# test_flags.py
"""Personal robust health-flag thresholds, the 'unknown' state, structural gaps (R9)."""
from app.domains.garmin_analytics.domain.recovery_score.flags import (
    oxygen_flag_state, thermo_flag_state, structural_gaps)

def test_oxygen_unknown_when_missing():
    assert oxygen_flag_state(None, history=[93.0]*40)[0] == "unknown"
def test_oxygen_flag_below_threshold():
    assert oxygen_flag_state(82.0, history=[93.0,92.0,94.0]*14)[0] == "flag"
def test_oxygen_clear_typical():
    assert oxygen_flag_state(93.0, history=[93.0,92.0,94.0]*14)[0] == "clear"
def test_thermo_two_sided():
    h = [0.1,-0.1,0.2,-0.2]*10
    assert thermo_flag_state(1.5, history=h)[0]=="flag" and thermo_flag_state(-1.5, history=h)[0]=="flag"
    assert thermo_flag_state(0.05, history=h)[0]=="clear"
def test_structural_gaps_blocks_only():
    dates=[f"2025-06-{d:02d}" for d in range(1,11)]
    present=[True,False,False,False,True,True,False,True,True,True]
    assert structural_gaps(dates, present, min_len=3)==[("2025-06-02","2025-06-04")]
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# flags.py
"""Health flags: low-oxygen (spo2_avg) and thermoregulation (skin-temp deviation).

Personal robust thresholds (median +- 2.5*MAD); oxygen one-sided low, thermo
two-sided. Missing reading => 'unknown' (never 'clear'; the SpO2 gaps are
structural). Validated in run 2026-06-11-spo2-skintemp-flag-thresholds
(spo2_avg beats spo2_min; ~90.5% personal threshold ~ conventional 90%)."""
from __future__ import annotations
import numpy as np

K, _MAD_SCALE, _MIN_HISTORY = 2.5, 1.4826, 30

def _scale(history: list[float]) -> tuple[float, float] | None:
    vals = np.array([h for h in history if h is not None], dtype=float)
    if len(vals) < _MIN_HISTORY: return None
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) * _MAD_SCALE
    return med, (mad if mad > 1e-9 else (float(np.std(vals)) or 1e-9))

def oxygen_flag_state(value: float | None, *, history: list[float]) -> tuple[str, float | None]:
    sc = _scale(history)
    if value is None: return "unknown", (sc[0]-K*sc[1] if sc else None)
    if sc is None: return "clear", None
    thr = sc[0] - K*sc[1]
    return ("flag" if value < thr else "clear"), thr

def thermo_flag_state(value: float | None, *, history: list[float]) -> tuple[str, tuple[float,float] | None]:
    sc = _scale(history)
    band = (sc[0]-K*sc[1], sc[0]+K*sc[1]) if sc else None
    if value is None: return "unknown", band
    if band is None: return "clear", None
    return ("flag" if (value < band[0] or value > band[1]) else "clear"), band

def structural_gaps(dates: list[str], present: list[bool], *, min_len: int = 3) -> list[tuple[str, str]]:
    gaps: list[tuple[str, str]] = []
    start: int | None = None
    for i, ok in enumerate(present):
        if not ok and start is None: start = i
        elif ok and start is not None:
            if i - start >= min_len: gaps.append((dates[start], dates[i-1]))
            start = None
    if start is not None and len(present) - start >= min_len:
        gaps.append((dates[start], dates[-1]))
    return gaps
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: health flags + structural gaps (R9)"`

#### Task B6: Evidence + score-series assembly
**Files:** Create `…/evidence.py`; Test `…/test_evidence.py`.
- [ ] **Step 1: Failing tests** — assert from a synthetic ≥40-day `list[DailyMetric]` (real `app.domains.garmin_health.contracts.DailyMetric`): seven evidence rows; `source_type` from the fixed map (`respiration_avg`→native, `heart_rate_resting`/`heart_rate_avg`→device, the four Garmin composites→derived); `tab_href` per metric (`hrv_nightly_avg`→`/hrv`, `heart_rate_resting`→`/heart-rate`, `stress_avg`→`/stress`, `body_battery_avg`→`/body-battery`, `respiration_avg`→`/respiration`, `sleep_score`→`/sleep`); `degraded` true when a day had <7 present inputs; score-series length == display window with `ma7` seeded.
- [ ] **Step 2: Run → FAIL. Step 3: Implement** `evidence.py` composing B1–B5 into plain dataclasses (Pydantic mapping happens in `dashboard.py`); source-type + `tab_href` maps as module constants.
- [ ] **Step 4: Run → PASS. Step 5: Commit** — `"recovery_score: evidence + score series with tab links (R8)"`

### Phase C — API contract swap

#### Task B-contract: Replace the overview contract
**Files:** Modify `contracts/dashboard.py`, `domain/dashboard.py`; Test `tests/domains/garmin_analytics/test_dashboard_overview.py`.
- [ ] **Step 1: Failing contract test** — `compute_dashboard_overview(metrics)` returns `DashboardOverviewResponse` with `.state.band in {"suppressed","typical","strong"}`, 7 `.evidence` rows each with a `tab_href`, 2 `.flags` (oxygen+thermoregulation, each with a `tab_href`), non-empty `.score` with `ma7` populated. Fixture: ≥40 synthetic `DailyMetric`s.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Replace `contracts/dashboard.py`** with the Q2 models (full Pydantic, `DefaultsRequired` style). Delete `ReadinessScore`, `TodayVitals`, `Sparkline*`, `DashboardSparklines`, `MetricCorrelation`, `CorrelationPoint`.
- [ ] **Step 4: Rewrite `domain/dashboard.py::compute_dashboard_overview`** to assemble from Phase B; delete the four `_compute_*` helpers + `_recovery_status` + `_format_delta_magnitude`.
- [ ] **Step 5: Grep consumers** — `cd backend && grep -rn "ReadinessScore\|DashboardSparklines\|MetricCorrelation\|TodayVitals\|\.correlations\|\.sparklines" app/` → confirm ONLY the overview route consumes them (NOT the per-metric endpoints, which the detail tabs use); fix the overview route. Record that the `/hrv` correlations endpoint is separate.
- [ ] **Step 6: Validate** — `uv run pytest tests/ -v`, `uv run ruff check`, `uv run pyright app/ tests/` → 0 errors.
- [ ] **Step 7: Regenerate + commit** —

```bash
bash scripts/generate-api-types.sh
cd frontend && npm run check    # the OLD overview +page.svelte will break here — expected; Phase D fixes it
git add backend/ frontend/src/lib/api-types.ts && git commit -m "contract: swap dashboard OVERVIEW to recovery score + flags (Q2)"
```

### Phase D — Frontend: Overview tab only

> Build each component, then verify with a browser-MCP screenshot. Props typed against the regenerated `api-types.ts`. Detail tabs untouched.

#### Task D1: `recovery-format.ts` (display-only)
- [ ] Create `lib/recovery-format.ts`: `bandLabel`, `trendLabel`, `stateSentence` ("Typical recovery, improving"), `zToColor` (diverging, from `colors.ts`), `sourceGlyph`, `flagLabel`. No statistics. Vitest unit test for `stateSentence` over all band×trend combos. Commit.

#### Task D2: `StateLine.svelte`
- [ ] One flex row: state sentence + score z (small, tabular) + freshness. Props `state: RecoveryState`, `date`, `pending`. No card, no ring. Verify: screenshot in `/`, reads as a sentence, fits mobile+desktop. Commit.

#### Task D3: `RecoveryTrajectory.svelte` (hero)
- [ ] Chart.js line via `ChartCanvas`: raw (thin, low-alpha) + MA7 (bold) + shaded baseline band + event annotations (Nov regime/plateau/softening via `chartjs-plugin-annotation`) + 7d/30d/90d picker (reuse `TrendRangePicker`). Props `score: RecoveryScorePoint[]`, `change: MeaningfulChange`. Owns full width, no card. Z-axis with labeled zero; MA window in subtitle. Verify: screenshot at 7d/30d/90d; band behind line; annotations align with FINDINGS dates; ≥3:1 contrast. Commit.

#### Task D4: `EvidenceSparkline.svelte` + `EvidenceTable.svelte`
- [ ] `EvidenceSparkline`: tiny axis-less line, ~24px, **shared y-domain** across rows (passed in), last point emphasized. Props `points`, `domain`.
- [ ] `EvidenceTable`: a real `<table>`, columns metric(→link `tab_href`) / latest+unit / baseline / Δz (signed, arrow, `zToColor`) / sparkline / source glyph / coverage glyph. **Rows sorted by |Δz| desc** (display-only). Right-aligned `tabular-nums`. `degraded` → muted coverage glyph + tooltip. **Each metric cell is an `<a href={row.tab_href}>`** — the bridge to the detail tab. Props `evidence: EvidenceRow[]`. No cards. Verify: screenshot; scan Δz column to see co-movement; click a row → lands on the matching detail tab (unchanged); mobile reflow hides the sparkline column (P2). Commit.

#### Task D5: `FlagStrip.svelte`
- [ ] One line, two ternary chips (clear/flag/unknown), redundant encoding (lucide icon + text + color), `recent` marker, "no SpO₂ reading Nd" when unknown; **each chip links to its `tab_href`** (`/pulse-ox`, `/skin-temp`). Props `flags: HealthFlag[]`. Verify: screenshot all three states via fixture; chips link to the existing tabs. Commit.

#### Task D6: Rewrite `/+page.svelte` (overview only)
- [ ] Delete the readiness-hero (`457-512`), the `metric-grid` (`514-559`), and dead JS (`metricConfigs`, `componentOrder`, `componentInfo`, `deltaColor`, `readinessColor`, `sparkCanvases`, Chart.js sparkline mounting). Keep the freshness/sync banner + empty/loading/error branches. Compose `StateLine` → `RecoveryTrajectory` → `EvidenceTable` → `FlagStrip` against the new `overview` contract. Verify: `npm run check` passes; screenshot the full overview vs the Part-0 mockup; confirm NO card grid remains and every evidence row + flag links to its existing tab. Commit.

### Phase E — Behavior-preserving code de-duplication (DEFERRED — not this iteration)

> **DEFERRED per the 2026-06-12 direction — do NOT implement now.** Kept here as the documented future option. Allowed when taken up: clean up duplicated code WITHOUT removing any functionality. Hard constraint: every detail tab renders **identically** before and after — verify by before/after screenshot of each touched page. No chart, stat, or feature removed. One page per commit.

#### Task E1: Extract `buildLineConfig()` chart factory
- [ ] Create `lib/chart-factory.ts` with `buildLineConfig(series, {color, title, range, yLabel, annotations?})` returning the `ChartConfiguration<'line'>` that the metric pages currently inline (the repeated `$derived.by` blocks, e.g. `heart-rate/+page.svelte:362-467`). Replace the inline builders in ONE page (`/stress`, smallest) first. Verify screenshot-identical. Commit. Then roll to the other pages one commit each, screenshot-identical each time.

#### Task E2: Extract `<StatBar>` component
- [ ] Create `lib/components/StatBar.svelte` taking `stats: {label, value, unit?, delta?}[]`, rendering the repeated `.stat-item` markup. Replace per-page stat-bar HTML one page at a time, screenshot-identical. Commit per page.

#### Task E3: Consolidate ad-hoc CSS tokens (cosmetic, behavior-preserving)
- [ ] Add CSS custom properties for the scattered border/radius/gap/spacing values (the Explore report found `8px`/`10px`/`14px` radii, two border alphas) into the global stylesheet; replace literals where it does not change rendering. Verify screenshot-identical. Commit.

*(E1–E3 are independent; skip any without affecting Phases A–D.)*

---

## SELF-REVIEW

**Spec coverage:** Q1 (frontend) → overview-only refactor (Phase D) + tabs kept + optional cleanup (Phase E); the corrected scope is the Part-1 Q1 table and the Goal's explicit non-goals. Q2 (contract) → Task B-contract. Q3 (backend) → Phase B. The score definition → Part 0 (the gap the user flagged, now stated). Anti-card rule → Task A1; tab-scope error → Task A2.

**Placeholder scan:** Backend (B1–B5, B-contract) carry full test+impl. B6/D2–D6/E* specify structure + verification, not frozen Svelte — deliberate (visual-iteration, display-only, behavior-preservation). Stated.

**Type consistency:** `RecoveryState/RecoveryScorePoint/MeaningfulChange/EvidenceRow/HealthFlag/StructuralGap` identical across Q2, B-contract, D2–D6. `expanding_robust_z/weighted_recovery_score/seeded_ma7/oxygen_flag_state/thermo_flag_state/structural_gaps/score_band/trend_direction` consistent across Phase B and tests. `tab_href` added on `EvidenceRow` + `HealthFlag` (the tab-link bridge) and asserted in B6 + B-contract.

**Scope guard (the prior failure):** no task removes, collapses, or alters any detail tab's information. The only tab-touching phase (E) is behavior-preserving and verified screenshot-identical. The nine tabs and the nav are in the "UNCHANGED" file list.

---

## EXECUTION HANDOFF

One coupled feature (backend → contract → overview share the contract seam); Phase E is independent cleanup. **Recommended order:** Phase A (rule + spec fix) → Phase B (TDD, no UI) → Phase C (contract seam; frontend breaks here, expected) → Phase D (overview, screenshot-reviewed) → Phase E only if wanted. Do not start a Phase-D component before its contract fields exist and `api-types.ts` is regenerated.

**Two execution options:** (1) **Subagent-driven (recommended)** — fresh subagent per task, review between. (2) **Inline** — execute here with checkpoints. Which?
