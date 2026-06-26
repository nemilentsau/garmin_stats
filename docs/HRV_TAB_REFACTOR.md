# HRV Tab Refactor — Findings & Design Proposal

*A summary of the investigation behind the HRV tab redesign. Based on roughly one year of this
user's nightly HRV data (365 nights, June 2025 – June 2026).*

---

## The starting point

The HRV tab had grown into a dense collection of widgets — a recovery "status" pill, a histogram, an
overnight trajectory mini-bar, a 14-day status-mix bar, a grid of correlation scatter plots, Garmin
baseline zones, a day-of-week chart, and more. Each was individually plausible, but together they
answered no clear question and several actively misled.

The working hypothesis going in was simple: **the tab tries to turn a noisy, continuous signal into
discrete labels and standalone widgets, and most of those labels are displaying noise rather than
signal.** The job was to test that hypothesis widget by widget against the actual data, keep what
genuinely informs, and cut what doesn't — then propose a cleaner tab built around the one question a
person actually asks: *"Is my nightly HRV stable, drifting, or acutely suppressed — and how does
last night compare?"*

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
| **Sustained trend + acute override** | yes | 18% (as a *trend*, not a nightly claim) | **12%** |

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

Both have already been removed.

### 5. The correlation scatter grid said one thing six times

The grid of "HRV vs respiration," "HRV vs resting heart rate," etc. showed six strong relationships
that are really the same story — these metrics all move together as one recovery axis. Six scatter
plots implying six independent insights (and hinting at causation) is better told as a single compact
"these move together" summary.

---

## The design proposal

The redesigned tab is organized top-to-bottom around level → trend → context, and leads with the
chart that actually answers the user's question.

**1. A compact summary strip (top)**
- Last night's HRV, in milliseconds, as the number — no status word.
- How it compares to the recent baseline, shown as a signed difference ("+6 ms vs your 7-day
  average") with a personal scale, so the reader sees magnitude, not a verdict.
- A short trend cue — whether the multi-day direction is steady, drifting down, or recovering — based
  on the 7-day-vs-30-day movement, which is stable enough not to flip every night.
- A coverage note when last night's data is thin, shown *before* any interpretation.
- Garmin's own status, if shown at all, as its own separate chip — never silently merged into the
  app's reading.

**2. The nightly trend chart — the hero (promoted above the fold)**
- Raw nightly dots (light) plus a bold 7-day average line, both kept — the raw dots are what make a
  sudden dip visible instead of smoothed away.
- One honest "your typical range" band based on the full history.
- Gaps in the data shown as gaps, not bridged with a misleading line.
- The Garmin baseline zones removed.

This chart, not a single noisy overnight trace, is what belongs in the prime spot.

**3. A labelled history timeline**
- Replaces the current hover-only strip of unlabelled cells with a readable timeline: each night
  shaded by how it compares to baseline, with visible dates, month markers, and keyboard navigation.

**4. A trimmed selected-night detail (on demand)**
- When you pick a night: its overnight HRV line (shown only when coverage is adequate), its
  difference from baseline, and — if kept at all — a single, clearly-labelled "this night was around
  the Nth percentile of your last 90 days" readout instead of the standalone histogram.

**5. A small relationships summary**
- The scatter grid replaced by one compact "what moves with HRV" summary, labelled as co-movement,
  not cause.

**6. Day-of-week, demoted and honest**
- Kept as a small secondary panel showing the average weekday pattern with its uncertainty and a
  plain-language note that it describes long-run averages, not any single night. Shown as a deviation
  from typical, never as raw bars on a zero baseline that would exaggerate it.

### What's removed outright

The fixed-cutoff status pill as a headline, the standalone histogram, the overnight trajectory
mini-bar, the 14-day status-mix bar, the correlation scatter grid, the Garmin baseline zones, the
weekly-average duplicate stat, the "current streak" headline, the broken volatility and trajectory
warnings (already gone), and the generic explanatory text that just restated the UI.

---

## What this means under the hood

Most of the proposal is presentation. A few backend touch-points:

- **Already done:** the two broken warning rules have been removed, with tests confirming they no
  longer fire.
- **Small, additive:** expose the personal-scaled difference number so the front end can show
  magnitude without inventing a new label. The existing recovery status is no longer used as a
  headline, but its meaning is left unchanged for now.
- **Likely no change needed:** the percentile fix is mostly wiring the correct (already-computed)
  value to the selected night and naming its window.
- **If day-of-week stays:** the back end should serve the *adjusted* weekday pattern with its effect
  size, not the raw averages it currently sends.
- **Cleanup, verified safe:** the three retired widgets' data fields are used only by this one tab
  and nothing else, so they can be removed cleanly once the front end stops drawing them.

---

## Honest caveats

This is one person's data, one device, one year. The specific thresholds and the personal scale will
drift as more data arrives, and the weekly-rhythm and recovery findings are descriptive, not medical.
The design deliberately favors showing the real number and its trend over any confident-sounding
label — because the central, repeatable finding of this whole effort is that **this signal is too
noisy night-to-night to honestly label, and most of the old tab's confidence was manufactured.**
