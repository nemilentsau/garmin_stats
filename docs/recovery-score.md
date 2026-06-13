# Recovery Score

A guide to the recovery score on your dashboard: what the number means, how the underlying signals
are combined into it, and why it's done that way. The exact inputs, weights, and thresholds are in
[`recovery-dashboard.md`](recovery-dashboard.md); the evidence behind every choice is in
`FINDINGS.md`.

---

## What it is

The recovery score is **one daily estimate of your physiological recovery state, measured against
your own normal** — a summary of overnight and resting signals that tend to move together when your
system is fresh or suppressed.

That wording is deliberately narrower than "how recovered you are." For a health-training app,
recovery is only one product axis. The score does not measure training load, adaptation, sleep
opportunity, workout readiness, or why the state changed.

## The seven signals

It's built from seven daily signals that mostly move with the same underlying recovery state:

- **Up when you're well recovered:** nightly HRV, body battery, sleep score.
- **Up when you're run down:** resting heart rate, heart-rate average, stress, respiration.

These are not seven independent product concepts. Within this selected recovery bundle they rise
and fall together strongly enough that a single factor explains about three-quarters of their
movement. That supports a compact physiological-state indicator.

There is an important caveat: **body battery and sleep score are Garmin-derived composites, not raw
physiology.** Garmin does not publish their exact formulas, and they likely already encode some of
the same ingredients used elsewhere here, such as HRV, heart rate, stress, sleep, or activity
context. They are useful as vendor context, but they should not be treated as independent
measurements. If the score is revised, a rawer version should be tested with Garmin composites
demoted to supporting evidence rather than primary inputs.

## How the signals are combined

The signals are in completely different units — heart rate in bpm, HRV in milliseconds, stress and
body battery as 0–100 scores, respiration in breaths per minute. You can't just add them; "60 bpm +
50 ms" is meaningless. So combining them takes four steps:

**1. Put each signal on a common personal scale.** For each one, we look at your own past values
and express today as *how far it is from your typical, in robust standard deviations* — a personal
z-score, using your median and a robust measure of spread. After this step every signal speaks the
same language: roughly −3 to +3, where **0 is normal for you**, no matter its original units.

> *Why:* you can't average bpm with milliseconds, and you can't tell whether a value is high or low
> for you without comparing it to your own history. The z-score solves both at once. We use the
> **median and a robust spread** (rather than the average and standard deviation) so a single odd
> night doesn't distort the scale — these metrics are skewed and prone to outliers.

**2. Point all seven the same way.** Some signals are good when high (HRV, body battery, sleep) and
some are bad when high (resting HR, HR average, stress, respiration). We flip the sign of the "bad"
ones so that, afterwards, **higher always means better recovery** for all seven.

> *Why:* if we didn't, a high-heart-rate bad day and a high-HRV good day would partly cancel each
> other out, and the combined number would be mush. Flipping the signs makes the signals reinforce
> instead of fight.

**3. Average them into one number.** We take a (roughly equal) weighted average of the seven signed,
scaled values. Because they're all on the same scale and all point the same direction, the result is
a single recovery z-score: **0 = a typical day, positive = stronger physiological recovery state,
negative = suppressed physiological recovery state.**

> *Why roughly equal weights:* we tested equal weighting, a redundancy-adjusted weighting, and a
> data-driven weighting — they give essentially the same score, because the signals carry so much
> overlapping information that *how* you weight them barely matters. So we don't pretend a clever
> weighting is doing real work; a near-equal average is the honest choice.
>
> The value of the average is therefore **not** that it discovers a clever hidden formula. The value
> is compression and noise reduction: several co-moving signals become one cleaner state estimate,
> while the evidence table still shows which inputs moved. If the dashboard needs several meaningful
> training-health axes, those axes must come from other constructs, not from re-weighting these same
> redundant recovery inputs.

**4. Smooth for the trend.** The main line on the dashboard is a 7-day average of that daily score.

> *Why:* day-to-day recovery is genuinely noisy; the 7-day average is the trend you can actually act
> on. The raw daily values are still shown underneath.

## How to read the number

It's a **personal scale centred on you**, roughly −3 to +3. **0 is a typical day.** Positive means
a stronger-than-usual physiological recovery state; negative means more suppression than usual.
Read it as a **level** (where you are versus your own baseline) and a **trend** (which way it's
heading) — "+0.5 and rising" is a bit above normal and improving; "−1.2 and falling" is
meaningfully suppressed and getting worse.

## When a change matters, and the state label

We measured how much the score normally bounces around, and the dashboard flags a week-over-week
move only when it's bigger than that noise — smaller wiggles are left alone. Because recovery is a
smooth continuum and not a set of fixed categories, the headline pairs a simple band (suppressed /
typical / strong) with a direction (improving / steady / declining), e.g. "Typical recovery,
improving."

## Why you can trust it

We checked, on your own year of data, that the combined score tracks reality:

- It carries **real signal**, not random noise — it has genuine momentum from day to day.
- It **catches the real episodes** — even with its baseline locked to *before* an event, it drops
  through your November low-recovery stretch and rises through your strong February–March period.
- It **holds up on fresh data** it was never tuned against.

The honest caveat: your year holds one severe low stretch and one strong plateau, so the evidence is
solid for your data while being upfront that there were only a couple of big events to test against.

## Product critique

The recovery score is defensible as a compressed physiological-state indicator, but it is not a
complete central model for a health-training app.

The risk is that a statistically tidy score becomes a product placeholder for several different
questions:

- **Can I train hard today?** This needs recent load, planned load, and recovery together.
- **Am I adapting?** This needs performance, workload, and long-term trend, not just low stress.
- **Did I create enough recovery opportunity?** This needs sleep duration, timing, and consistency,
  not just Garmin's sleep score.
- **Is something abnormal happening?** This needs health flags such as oxygen and temperature,
  which are deliberately outside the score.
- **What changed?** This needs behavior, experiment, illness, travel, and training context.

So the score should be read as one lane on the dashboard, not the dashboard's whole answer. A better
top-level product model is **training state**: recovery state + recent load + sleep opportunity +
health exceptions + behavior context.

## Axes to study next

The next analyst work should look for product axes, not "another recovery axis." Suggested
priorities:

1. **Training load / strain.** Use source-native activity fields first: `training_load_peak`,
   training effect, activity duration, distance, sport, and previous-day run load. Do not infer load
   from recovery outputs like HRV, resting HR, body battery, or sleep score.
2. **Adaptation / progress.** Study whether a stable performance or capacity trend can be built
   from activity sessions: pace/power at comparable effort, run duration, distance, training effect,
   and longer-term workload. This is separate from feeling recovered.
3. **Sleep opportunity / regularity.** Add sleep duration, bedtime, wake time, midpoint, and
   midpoint consistency. These answer whether recovery had enough time and regularity, which
   Garmin's sleep score may partially obscure.
4. **Health exceptions.** Keep oxygen and thermoregulation as flags, not recovery-score inputs.
   They answer "is something unusual happening?" rather than "how ready am I?"
5. **Behavior and experiment context.** Join routines, experiments, alcohol, illness, travel,
   meditation, and training days to explain state changes. This should explain the recovery score;
   it should not be blended into it.

The practical next step is to build and validate the load and sleep-opportunity axes before
redesigning the central dashboard. If those axes carry real signal, the overview should become a
multi-lane training-state dashboard instead of a single recovery-score dashboard.

---

*Every number and threshold behind the score was established from your own data and recorded in
`FINDINGS.md`, not picked by guesswork.*
