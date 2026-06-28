# HRV Tab — Findings & What Shipped

*The investigation behind the HRV tab redesign, and the design that shipped (branch `refactor-hr`,
2026-06-27). Based on roughly one year of this user's nightly HRV data (365 nights, June 2025 –
June 2026).*

---

## The starting point

The HRV tab had grown into a dense collection of widgets — a recovery "status" pill, a histogram, an
overnight trajectory mini-bar, a 14-day status-mix bar, a grid of correlation scatter plots, Garmin
baseline zones, a day-of-week chart, and more. Each was individually plausible, but together they
answered no clear question and several actively misled.

The working hypothesis going in was simple: **the tab tries to turn a noisy, continuous signal into
discrete labels and standalone widgets, and most of those labels are displaying noise rather than
signal.** The job was to test that hypothesis widget by widget against the actual data, keep what
genuinely informs, and cut what doesn't — then build a cleaner tab around the one question a
person actually asks: *"Is my nightly HRV stable, drifting, or acutely suppressed — and how does
the latest night compare?"*

A note that shapes everything below: **a single night's HRV is genuinely noisy.** Night-to-night it
swings with a standard deviation of about 14–18 ms, which is most of the entire typical range. Any
display that reacts to one night will mostly react to noise. The useful signal lives in *level* and
*trend*, not in any single night's label.

---

## What we found

### 1. The recovery "status" pill was displaying coin-flips

The pill bucketed each night into suppressed / below-baseline / stable / elevated using fixed
millisecond cutoffs. Against this user's data those cutoffs are arbitrary: only **27%** of nights
land in "stable," **73%** read as off-baseline, and — most damning — the pill **changes its verdict
on 63% of consecutive nights**. It was flickering, not informing.

We tested four replacements head-to-head on the full year, scoring each on three things that matter:
does it still catch a real acute crash, how often does it cry wolf on a calm night, and how much does
it flicker night to night.

| Candidate | Catches acute dips | False alarms on calm nights | Night-to-night flips |
|---|---|---|---|
| Current fixed-ms pill | yes | 17% | **63%** |
| **Continuous (show the number, no label)** | yes | **0%** | none — no label to flip |
| Personal "z-score" bands | yes | 0% | **70%** (worse!) |
| **Sustained trend + acute override** | yes | 18% (as a *trend*, not a nightly claim) | **26% total; 12% drift-only** |

The decisive result: **re-bucketing doesn't help.** Personal, individually-tuned bands flickered
*even more* than the original (70%). The only things that fixed the flicker were (a) dropping the
category entirely and showing the actual number, or (b) basing the headline on a slow multi-day
trend rather than a single night. Both still caught every genuine acute dip, including the sharp
−29 ms night in February that the pill caught but Garmin's own status missed.

We also found the pill was quietly **contradicting itself**: a third of its "suppressed" verdicts
(43 nights) came purely from Garmin's status flag overriding the data — including nights where HRV
was actually 10–27 ms *above* the user's baseline but still labelled suppressed.

### 2. The histogram answered nothing the trend chart didn't

The standalone distribution histogram had two problems. First, the distribution is a plain
single-humped, symmetric shape — fully described by its median and typical range, which the trend
chart's band already shows. The histogram's shape added nothing.

Second, and worse, the one number it tried to convey — "you're in the Nth percentile" — is
**meaningless without saying percentile of *what*.** The same 50 ms night ranks at the 26th
percentile against the whole year but the 55th within its own surrounding weeks. A perfectly typical
night for the current period looked alarming against all-time history, purely because the body's
baseline drifts across seasons. On top of that, a wiring bug meant the tab showed the *latest*
night's percentile no matter which night you'd selected.

### 3. The day-of-week rhythm is real — but small, and was overstated

There is a genuine weekly rhythm in this user's HRV: Saturdays and Thursdays run low, Mondays and
Tuesdays run high, a swing of about 10 ms peak-to-trough. It survives careful checks — it's not just
an artifact of seasonal drift, and the low-Saturday pattern reappears when you split the year in
half.

But it's a **modest, group-level** effect. It explains roughly 6% of the variance, and the 10 ms
weekly swing is dwarfed by the ~18 ms a single night bounces around on its own. In plain terms:
weekday tells you something about your *average* Saturday, but almost nothing about *this* Saturday.
Our re-analysis with a proper statistical test actually found it somewhat weaker than the first pass
had suggested. It's worth keeping as a small secondary curiosity, honestly labelled — not as a
headline.

### 4. Two widgets were built on broken logic

- The **overnight "volatility" warning** could never fire (its threshold sat above the highest value
  the data ever reaches) and was backwards anyway — more overnight variability actually went with
  *better* recovery for this user, not worse.
- The **overnight trajectory** ("HRV fell through the night") flagged a direction that is mostly
  noise: overnight HRV rises on the large majority of nights, and the "falling" reading appeared on
  only 4% of nights, indistinguishable from measurement scatter.

### 5. The correlation scatter grid said one thing six times

The grid of "HRV vs respiration," "HRV vs resting heart rate," etc. showed six strong relationships
that are really the same story — these metrics all move together as one recovery axis. Six scatter
plots implying six independent insights (and hinting at causation) is better told as a single compact
"these move together" summary.

---

## What shipped

The redesigned tab is organized into two parts — **State** (recent: "what's my HRV doing lately, and
was any night off?") and **Structure** (stable patterns) — and leads with the chart that answers the
user's actual question.

**State**

- **Summary strip:** the latest night's HRV in ms (no status word) and its signed difference vs the
  recent baseline, shown in neutral text — no good/bad color verdict, since a single night is noise
  and the delta (tonight vs trailing-7d) is a different question than Garmin's multi-day status.
  Recovery state appears only as backend insight text below, not as a headline pill or a delta color.
- **Nightly trend chart (hero):** a bold 7-day moving-average line over a **moving "typical range"
  ribbon** computed from a **trailing, user-selectable baseline window** (30 / 60 / 90 days, default
  60; robust median ± 1σ via MAD × 1.4826, current night excluded). The ribbon drifts with the
  user's normal range as fitness changes; gaps in the data are shown as gaps, not bridged.
- **Extreme-night markers:** nights outside their trailing band (robust |z| > 2) are marked at the
  band edge they breached — so they flag the night *and* its direction without stretching the axis;
  the actual nightly value is in the hover.
- **Window knob:** the 30/60/90 control is URL-persisted (`?baseline=`) and governs the ribbon, the
  markers, and the headline "7-day avg vs baseline" delta — one baseline definition everywhere on the
  tab. It is visually distinct from the separate display-range picker (labelled **Baseline** vs
  **Show**).
- **History timeline + selected-night detail:** a labelled timeline (visible dates, month markers,
  keyboard nav); selecting a night shows how it ranks as a **trailing-window z** ("±X SD vs your
  N-day baseline") rather than an all-history percentile, plus that night's insights.

**Structure**

- **Day-of-week:** kept as a small secondary panel of weekday averages, computed over its own longer
  span (labelled, e.g. "last 3 months") — deliberately *not* the knob window, since a weekday needs
  many samples to be stable. Bars are colored against a backend-supplied sample-weighted reference
  mean (the frontend does no statistics of its own).
- **What moves with HRV:** the old 6-plot correlation scatter grid replaced by one compact
  co-movement summary, labelled association — not cause.

**Removed outright:** the fixed-cutoff status pill as a headline, the standalone histogram, the
overnight minute-by-minute trace, the overnight "trajectory" mini-bar, the 14-day status-mix bar, the
correlation scatter grid, the Garmin baseline zones, the weekly-average duplicate stat, the
"current streak" headline, the (already-deleted) broken volatility/trajectory warning rules, and the
generic explanatory text that just restated the UI.

---

## Design principle & the baseline divergence

Every surviving element does one of three jobs: show the **trend** honestly, flag a **genuinely
unusual night** against a fair recent baseline, or attach a **stable pattern** worth a glance.
Anything that only rendered "here's the distribution of my HRV" was cut.

One deliberate, documented decision: the HRV tab's baseline is **trailing** ("is tonight unusual
*right now*"), while the recovery score keeps an **expanding** personal baseline ("what state am I in
vs my whole history"). Trailing 30–60d windows were *validated and rejected* for the recovery score
(finding run `2026-06-11-recovery-normalization-baseline`: they absorb sustained regimes). So the
same nightly HRV can read a different z on the two surfaces — this is intentional, and any future
"one baseline everywhere" work must reconcile it rather than blindly migrate the recovery core to
trailing. See `FINDINGS.md` (Open Questions #12–#13).

---

## Under the hood

Most of the tab is presentation, but the baseline engine is real:

- A single backend primitive (`trailing_band_point` / `trailing_robust_band` in
  `domain/primitives/trends.py`) computes the per-night band + robust z from the prior N present
  nights (current night excluded). Both the `/analysis` (trend series) and `/insights` (selected-day)
  endpoints feed off the same primitive over the same reading series, so the chart and the panel
  always agree for a given night + window. The selected-day path computes just its one index rather
  than the whole series.
- **Gaps are shown as gaps.** The nightly trend is densified to a complete daily calendar; any night
  with no HRV reading — an absent day or a present row with a null reading — becomes an explicit
  all-null point, so the MA line and the ribbon break across gaps (`spanGaps: false`) instead of
  bridging a straight segment over data that was never observed. Missing nights are skipped in the
  MA/band, never interpolated.
- Degenerate (zero-spread) windows emit no z / no extreme flag rather than a garbage value. The
  baseline-dependent nightly trend is cached per window; the baseline-independent weekday patterns are
  cached once and reused across windows, so switching the knob never serves a stale window.
- Day-of-week coloring reads `HrvPatternWindow.overall_avg` (a sample-weighted mean) and its
  `total_sample_count`, both from the backend — keeping the frontend display-only.

---

## Honest caveats

This is one person's data, one device, one year. The specific thresholds and the personal scale will
drift as more data arrives, and the weekly-rhythm and recovery findings are descriptive, not medical.
The design deliberately favors showing the real number and its trend over any confident-sounding
label — because the central, repeatable finding of this whole effort is that **this signal is too
noisy night-to-night to honestly label, and most of the old tab's confidence was manufactured.**
