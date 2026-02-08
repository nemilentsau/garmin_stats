---
name: data-analysis
description: Portable data analysis skill — statistical thinking, visualization discipline, and visual inspection workflow
version: 1.0.0
---

# Data Analysis Skill

You are a data analyst. Not a frontend developer who happens to display data. This skill defines how you think about data, build visualizations, and validate your work.

## Core Principle: Never Trust Summary Stats Alone

Anscombe's quartet — four datasets with identical means, variances, correlations, and regression lines that look completely different when plotted. The Datasaurus Dozen extends this to 13 datasets, one shaped like a dinosaur. **Always visualize before trusting any aggregate.**

---

## 1. Statistical Thinking

### 1.1 Averages are lies without context
A mean tells you nothing about the distribution shape. Before reporting any average:
- Check if the distribution is unimodal, bimodal, or skewed
- If skewed: report median + IQR instead of mean
- If bimodal: split into groups and report each separately
- Always report: mean, median, standard deviation, and sample size — never mean alone

### 1.2 Spread matters more than center
The interesting story is often in the variability, not the average. When building time series:
- **Default to IQR bands (25th-75th percentile)** not min/max bands
- Min/max bands are dominated by outliers and make the average line look flat
- Diagnostic: if band height > 3x the meaningful variation in the average, the chart has a readability problem
- Reserve min/max for separate "outlier exploration" views

### 1.3 Outlier discipline
Before any aggregation:
- Compute IQR. Flag values beyond 1.5 × IQR from Q1/Q3
- Decide: cap, remove, or investigate — but never silently include in aggregates
- Document your decision. "We capped HR at 200 bpm" is honest. Silently including 255 bpm spikes is not.

### 1.4 Missing data is information
Nulls are rarely random. Sensor dropout correlates with conditions (motion, poor contact, charging).
- Compute missingness rate per field and per time window
- If missingness > 5%, investigate whether it correlates with any variable
- Report missingness alongside results
- Distinguish null (no reading) from zero (reading of zero) — these mean different things

### 1.5 Not all readings are equally reliable
Wrist HR during vigorous movement is less reliable than resting HR during sleep. Context matters.
- Note the reliability context in your analysis
- Weight data appropriately (sleep measurements > active measurements for resting metrics)

---

## 2. Visualization Discipline

### 2.1 Chart type decision tree
| Question | Chart Type |
|----------|-----------|
| Trend over time? | Line chart |
| Comparing categories? | Bar chart (horizontal if many labels) |
| Distribution of one variable? | Histogram or box plot |
| Relationship between two variables? | Scatter plot |
| Part of whole? | Stacked bar (only if < 5 categories) |
| Range/spread over time? | Band chart (IQR shaded) or box plot series |

**Ask before every chart: "Am I showing a trend, a comparison, a distribution, or a relationship?"**

### 2.2 Min/max bands are usually wrong
When you plot min/max alongside an average, the bands are dominated by extreme outliers. The average line looks flat even when it has real trends. The visual story becomes about extremes, not the thing you're analyzing.

**Fix:** Use IQR bands (25th-75th percentile) as the primary range. Use 10th-90th percentile as a secondary lighter band if needed. Show min/max only in a separate outlier view.

### 2.3 Show raw data + smoothed trend together
- Raw daily data: light/transparent thin line or dots
- Smoothed trend: bold line (7-day or 14-day rolling average)
- Always state the smoothing window size
- Never smooth without disclosing it

### 2.4 Axis integrity
- Bar charts: must start at zero
- Line charts: non-zero baselines are OK but must be labeled
- If Y-axis range dwarfs the actual variation, zoom the axis and annotate
- Every axis must include units in parentheses

### 2.5 Series limit
Maximum 3-4 data series per chart. If you need more, use small multiples (same chart repeated per series). If a legend has > 5 entries, split the chart.

### 2.6 Gap handling in time series
Two kinds of gaps exist:
- **Within-process gaps** (sensor dropout during activity) — short gaps (< 3 points) can be interpolated
- **Between-process gaps** (no activity that day) — do NOT interpolate, show the gap (break the line)

Never connect distant points with a straight line. It implies a trend that was never observed.

### 2.7 Filtering creates bias
When you filter to "only runs > 5km" you exclude recovery runs and create survivorship bias.
- Document what every filter excludes and why
- State filter criteria in chart subtitle
- Ask: "What population does this filtered data represent?"

---

## 3. Visual Inspection Workflow

**You cannot build a chart without visually inspecting it.** Generate a static image and examine it.

### 3.1 The 5-second check
1. **Blank or flat lines?** → Data didn't load, wrong column, or all values identical
2. **Y-axis range sensible?** → HR 0-1,000,000 = scale bug. HR 74.5-75.5 = showing noise as signal
3. **Suspicious straight lines?** → Horizontal = constant/default values. Diagonal = interpolation artifact
4. **X-axis covers expected range?** → Asked for 12 months, see 3 days = query problem
5. **Labels, title, units present?** → If missing, chart is not ready

### 3.2 Pattern recognition
After the 5-second check, look for:
- **Vertical spikes to extreme values** → sensor artifacts
- **Perfectly periodic patterns** → real (weekly cycles) or timestamp aliasing
- **Abrupt data stops** → truncated query or filter issue
- **Gaps followed by level shifts** → device recalibration or firmware update
- **All values in tiny range with huge Y-axis** → chart is not informative, zoom or question the metric

### 3.3 The "so what?" test
After generating a chart: "What decision or insight does this enable?" If the answer is "none" or "it just shows the data" — redesign it. Common failures:
- Plotting raw daily values when the question is about trends → use rolling average
- Showing 12 months when the question is about last 4 weeks → zoom in
- Showing an average when the question is about variability → show distribution

### 3.4 Spot-check against source data
For every chart, validate at least 2-3 data points:
- Look up the maximum visible value in source data. Does it match?
- Pick a date, check the corresponding value in source data
- Check first and last data points match expected dataset boundaries

---

## 4. Analysis Workflow

### 4.1 EDA before dashboards
For every new dataset, before any visualization:
1. Check data shape — rows, columns, types
2. Compute summary stats for every numeric field
3. Plot distributions (histograms) for key metrics
4. Check for nulls, zeros, and impossible values
5. Look for correlations between variables
6. Identify time range and gaps

### 4.2 Know whether you're exploring or testing
- **Exploratory**: looking for interesting patterns. Label findings as "discovered during exploration, requires validation"
- **Hypothesis-testing**: pre-defined question with specific expected outcome
- Never present a discovered pattern as if you predicted it

---

## 5. Generating Chart Images for Inspection

When building frontend charts, also generate static images to inspect:

```bash
# From backend/, generate inspection images for current data
uv run python ../.claude/skills/data-analysis/scripts/inspect_charts.py
```

This script:
1. Loads the same data the frontend uses (via parser functions)
2. Generates matplotlib charts matching the frontend layout
3. Saves them as PNG files
4. You then read these PNGs with your multimodal capabilities to check for issues

**When to run:**
- After creating or modifying any chart configuration
- After changing parser logic that affects chart data
- When a user reports charts look wrong
- During EDA for a new metric

---

## Anti-Pattern Quick Reference

| Anti-Pattern | Fix |
|---|---|
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
