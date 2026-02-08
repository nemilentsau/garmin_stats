---
name: data-analysis
description: Portable data analysis skill — statistical thinking, visualization discipline, and visual inspection workflow
version: 2.0.0
---

# Data Analysis Skill

You are a data analyst. Not a frontend developer who happens to display data. This skill defines how you think about data, build visualizations, and validate your work.

**This skill governs two layers:**
1. **Aggregation layer** — what statistics to compute from raw data, how to compute them, what the API exposes (`stats.py`, stat fields in `models.py`)
2. **Presentation layer** — chart types, band types, stat cards, axis rules, visual inspection (frontend chart configs, `inspect_charts.py`)

## Core Principle: Never Trust Summary Stats Alone

Anscombe's quartet — four datasets with identical means, variances, correlations, and regression lines that look completely different when plotted. The Datasaurus Dozen extends this to 13 datasets, one shaped like a dinosaur. **Always visualize before trusting any aggregate.**

---

## 1. Aggregation Layer

This section applies whenever you write or modify code that computes statistics from raw readings — `stats.py`, aggregate model fields in `models.py`, or any new summary computation.

### 1.1 Use real libraries

Never hand-roll statistical functions. Use `numpy` for percentiles, medians, means, and standard deviations. Use `pandas` for time-series aggregation, resampling, and grouped statistics. These libraries are battle-tested and handle edge cases correctly.

### 1.2 What every aggregate model must expose

When adding a new numeric metric to the daily aggregates:
- `avg` — mean (via `numpy.mean`)
- `median` — median (via `numpy.median`)
- `q1` — 25th percentile (via `numpy.percentile`)
- `q3` — 75th percentile (via `numpy.percentile`)
- `min`, `max` — extremes (keep for outlier views, but frontends default to IQR)

All fields nullable (`float | None`) — days with no readings return `None`.

### 1.3 Stat card guidance

Frontend stat cards summarize across the full date range. When choosing what to display:
- **"Overall Avg"** — mean of daily averages. Always include.
- **"Typical Low" / "Typical High"** — mean of daily Q1s / Q3s. Preferred over "Lowest Min" / "Highest Max" because min/max are dominated by outliers.
- **Keep min-based cards only when clinically meaningful** — e.g., SpO2 "Lowest Reading" matters because low SpO2 is a health flag.

---

## 2. Statistical Thinking

### 2.1 Averages are lies without context
A mean tells you nothing about the distribution shape. Before reporting any average:
- Check if the distribution is unimodal, bimodal, or skewed
- If skewed: report median + IQR instead of mean
- If bimodal: split into groups and report each separately
- Always report: mean, median, standard deviation, and sample size — never mean alone

### 2.2 Spread matters more than center
The interesting story is often in the variability, not the average. When building time series:
- **Default to IQR bands (25th-75th percentile)** not min/max bands
- Min/max bands are dominated by outliers and make the average line look flat
- Diagnostic: if band height > 3x the meaningful variation in the average, the chart has a readability problem
- Reserve min/max for separate "outlier exploration" views

### 2.3 Outlier discipline
Before any aggregation:
- Compute IQR. Flag values beyond 1.5 x IQR from Q1/Q3
- Decide: cap, remove, or investigate — but never silently include in aggregates
- Document your decision. "We capped HR at 200 bpm" is honest. Silently including 255 bpm spikes is not.

### 2.4 Missing data is information
Nulls are rarely random. Sensor dropout correlates with conditions (motion, poor contact, charging).
- Compute missingness rate per field and per time window
- If missingness > 5%, investigate whether it correlates with any variable
- Report missingness alongside results
- Distinguish null (no reading) from zero (reading of zero) — these mean different things

### 2.5 Not all readings are equally reliable
Wrist HR during vigorous movement is less reliable than resting HR during sleep. Context matters.
- Note the reliability context in your analysis
- Weight data appropriately (sleep measurements > active measurements for resting metrics)

---

## 3. Visualization Discipline

### 3.1 Chart type decision tree
| Question | Chart Type |
|----------|-----------|
| Trend over time? | Line chart |
| Comparing categories? | Bar chart (horizontal if many labels) |
| Distribution of one variable? | Histogram or box plot |
| Relationship between two variables? | Scatter plot |
| Part of whole? | Stacked bar (only if < 5 categories) |
| Range/spread over time? | Band chart (IQR shaded) or box plot series |

**Ask before every chart: "Am I showing a trend, a comparison, a distribution, or a relationship?"**

### 3.2 Min/max bands are usually wrong
When you plot min/max alongside an average, the bands are dominated by extreme outliers. The average line looks flat even when it has real trends. The visual story becomes about extremes, not the thing you're analyzing.

**Fix:** Use IQR bands (25th-75th percentile) as the primary range. Use 10th-90th percentile as a secondary lighter band if needed. Show min/max only in a separate outlier view.

### 3.3 Show raw data + smoothed trend together
- Raw daily data: light/transparent thin line or dots
- Smoothed trend: bold line (7-day or 14-day rolling average)
- Always state the smoothing window size
- Never smooth without disclosing it

### 3.4 Axis integrity
- Bar charts: must start at zero
- Line charts: non-zero baselines are OK but must be labeled
- If Y-axis range dwarfs the actual variation, zoom the axis and annotate
- Every axis must include units in parentheses

### 3.5 Series limit
Maximum 3-4 data series per chart. If you need more, use small multiples (same chart repeated per series). If a legend has > 5 entries, split the chart.

### 3.6 Gap handling in time series
Two kinds of gaps exist:
- **Within-process gaps** (sensor dropout during activity) — short gaps (< 3 points) can be interpolated
- **Between-process gaps** (no activity that day) — do NOT interpolate, show the gap (break the line)

Never connect distant points with a straight line. It implies a trend that was never observed.

### 3.7 Filtering creates bias
When you filter to "only runs > 5km" you exclude recovery runs and create survivorship bias.
- Document what every filter excludes and why
- State filter criteria in chart subtitle
- Ask: "What population does this filtered data represent?"

---

## 4. Visual Inspection

**You cannot build a chart without visually inspecting it.** Generate a static image and examine it.

### 4.1 The 5-second check
1. **Blank or flat lines?** → Data didn't load, wrong column, or all values identical
2. **Y-axis range sensible?** → HR 0-1,000,000 = scale bug. HR 74.5-75.5 = showing noise as signal
3. **Suspicious straight lines?** → Horizontal = constant/default values. Diagonal = interpolation artifact
4. **X-axis covers expected range?** → Asked for 12 months, see 3 days = query problem
5. **Labels, title, units present?** → If missing, chart is not ready

### 4.2 Pattern recognition
After the 5-second check, look for:
- **Vertical spikes to extreme values** → sensor artifacts
- **Perfectly periodic patterns** → real (weekly cycles) or timestamp aliasing
- **Abrupt data stops** → truncated query or filter issue
- **Gaps followed by level shifts** → device recalibration or firmware update
- **All values in tiny range with huge Y-axis** → chart is not informative, zoom or question the metric

### 4.3 The "so what?" test
After generating a chart: "What decision or insight does this enable?" If the answer is "none" or "it just shows the data" — redesign it. Common failures:
- Plotting raw daily values when the question is about trends → use rolling average
- Showing 12 months when the question is about last 4 weeks → zoom in
- Showing an average when the question is about variability → show distribution

### 4.4 Spot-check against source data
For every chart, validate at least 2-3 data points:
- Look up the maximum visible value in source data. Does it match?
- Pick a date, check the corresponding value in source data
- Check first and last data points match expected dataset boundaries

### 4.5 Generating inspection images

```bash
# From backend/, generate inspection images for current data
cd backend && uv run python ../.claude/skills/data-analysis/scripts/inspect_charts.py
```

This script loads the same data the frontend uses (via parser + stats), generates matplotlib charts matching the frontend layout, and saves them as PNGs. Read the PNGs with multimodal capabilities to check for issues.

**When to run:**
- After creating or modifying any chart configuration
- After changing stats logic that affects chart data
- When a user reports charts look wrong
- During EDA for a new metric

---

## 5. Analysis Workflow

### 5.1 EDA before dashboards
For every new dataset, before any visualization:
1. Check data shape — rows, columns, types
2. Compute summary stats for every numeric field
3. Plot distributions (histograms) for key metrics
4. Check for nulls, zeros, and impossible values
5. Look for correlations between variables
6. Identify time range and gaps

### 5.2 Know whether you're exploring or testing
- **Exploratory**: looking for interesting patterns. Label findings as "discovered during exploration, requires validation"
- **Hypothesis-testing**: pre-defined question with specific expected outcome
- Never present a discovered pattern as if you predicted it

---

## 6. Pipeline Trace

When adding a new metric or making significant data changes, produce a trace in `.claude/chart-inspections/<trace-dir>/`. These artifacts let the user verify each step and feed back into skill improvements.

**Trace directory naming:** Choose a descriptive, unique name that won't collide with future investigations of the same metric. Format: `<metric>-<context>`. Examples:
- `body-battery-initial` — first time adding Body Battery
- `body-battery-iqr-redesign` — revisiting BB to change band type
- `heart-rate-band-ratio-fix` — fixing a specific issue
- `sleep-score-eda` — exploratory analysis without frontend changes

### 6.1 Required artifacts

| Step | File | When | Contents |
|------|------|------|----------|
| 1. Discovery | `01-discovery-notes.md` | New FIT field/metric | Field names, types, ranges, filter rules, verification against real data |
| 2. EDA charts | `02-eda-<name>.png` | Always | Distributions, time series with IQR, min/max range — via `inspect_charts.py` or custom script |
| 3. EDA analysis | `03-eda-analysis.md` | Always | Written analysis: distribution shape, band ratio, data quality, decisions for dashboard |
| 4. Dashboard inspection | `04-dashboard-inspection.md` | Always | 5-second check, pattern recognition, "so what?" test (per section 4) |
| 5. Retrospective | `05-pipeline-retrospective.md` | Always | How each skill was used, what worked, what could improve |

### 6.2 Retrospective → skill updates

The retrospective is not just documentation. After writing it:
1. Check "what could improve" for **actionable gaps** in skills or CLAUDE.md
2. If a gap is found: update the relevant skill or CLAUDE.md in the same session
3. If no gap: note "no skill updates needed" in the retrospective

This creates a feedback loop: each new metric strengthens the skills for the next one.

### 6.3 When to trace

- **Full trace (all 5 steps)**: Adding a new metric end-to-end (parser → stats → frontend)
- **Partial trace (steps 2-5)**: Modifying chart design, changing aggregation logic, fixing a data quality issue
- **Inspection only (step 4)**: Minor chart tweaks (color, label changes)

### 6.4 Correlation check

After adding a new metric, regenerate the cross-metric correlation chart:

```bash
cd backend && uv run python ../.claude/skills/data-analysis/scripts/inspect_charts.py --chart correlations
```

Note any strong correlations (|r| > 0.5) in the EDA analysis. Cross-metric consistency validates the pipeline — if two metrics that should correlate don't, something is wrong.

---

## Anti-Pattern Quick Reference

| Anti-Pattern | Fix |
|---|---|
| Hand-rolled stats (percentile, median) | Use `numpy` / `pandas` |
| Model exposes only avg/min/max | Add median, q1, q3 |
| Stat cards show "Lowest Min"/"Highest Max" | Use "Typical Low"/"Typical High" (avg of daily Q1/Q3) |
| Average without distribution check | Show histogram first; report median + IQR |
| Min/max bands hiding signal | Use IQR bands (25th-75th percentile) |
| Not inspecting charts visually | Generate PNG, examine with multimodal |
| Wrong chart type | Use the decision tree above |
| Bar chart with non-zero baseline | Bars start at zero |
| No units on axes | Always include units in parentheses |
| Smoothing without disclosure | State window size; show raw + smooth |
| Line through data gaps | Break line at gaps > 2-3 points |
| Filter bias undisclosed | State filter in chart subtitle |
| Summary stats without scatter plot | Always plot before trusting aggregates |
| Missing data treated as zero | Distinguish null from zero; report missingness |
| New metric shipped without trace | Produce pipeline trace artifacts (section 6) |
| Retrospective without action | Check "what could improve" and update skills/CLAUDE.md |
