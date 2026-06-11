# Analytical Dashboard Ideas

**Status:** idea backlog, not an implementation plan. **Created:** 2026-05-27.

This document captures dashboard concepts for the future stress/recovery copilot while the
current dashboard remains unchanged. Ideas here are deliberately non-binding: they become
implementation work only after `docs/analyst-data-discovery.md` produces findings and score
contracts that justify them.

## Product stance

The dashboard should behave like an analytical instrument, not a decorative score page. Its
job is to answer three questions quickly:

1. What state am I in today?
2. What evidence supports that state?
3. What changed enough to deserve attention?

The frontend stays display-only. All scores, baselines, smoothing, meaningful-change
thresholds, state labels, confidence flags, and narrative explanations must come from backend
analytics contracts.

## Principles to preserve

- **State before score.** Lead with the physiological state or pattern, then show the numeric
  score as supporting detail. "Suppressed recovery with high confidence" is more useful than
  "41/100".
- **Evidence stack over mystery composite.** Every headline state should expose the few inputs
  that moved it: value, baseline, delta, coverage, and meaningful-change flag.
- **Axis cards, not metric tiles.** Once axes are discovered, the overview should organize by
  analytical axis such as autonomic balance, sleep, oxygen/respiratory flag, and
  thermoregulation flag. Individual Garmin metrics belong inside those cards or drill-downs.
- **Uncertainty is first-class.** Missingness, stale data, short baselines, Garmin-derived
  coupling, and provisional findings should be visible in compact badges.
- **Raw plus trend.** Trend views should show raw daily points or thin lines with the smoothed
  backend trend. Smoothing windows and lead-in behavior should be disclosed.
- **Meaningful deltas only.** The dashboard should not dramatize normal noise. Deltas should
  use the score-specific threshold from the finding, not generic up/down coloring.
- **Flags are not pillars.** Oxygenation and skin temperature may be important health-context
  flags without becoming daily gauges.
- **No fake progress axis.** Load, strain, and progress stay absent until source-native activity
  or training-load data is ingested.

## Candidate overview shape

Recommended direction for later design work:

1. **State banner**
   - Current state label.
   - Confidence or coverage badge.
   - One sentence explaining the main driver.
   - Latest date and freshness warning when needed.

2. **Axis summary row**
   - 3-5 equal-weight axis cards.
   - Each card shows current score/state, baseline comparison, meaningful delta, and a compact
     sparkline or bullet-style range.
   - Cards should use direct labels and avoid circular gauges as the primary analytical form.

3. **Evidence stack**
   - "Why this changed" panel showing top contributing signals.
   - Each signal row: latest value, personal baseline, delta, confidence, and source type.
   - This should make double-counting visible when multiple inputs come from Garmin-derived HRV
     summaries.

4. **Drill-down tabs**
   - One tab per confirmed axis, not one route per raw metric.
   - Default comparison: current window vs personal baseline.
   - Include raw + smoothed trend, distribution position, event markers, and coverage.

5. **Event context**
   - Known event windows such as November suppression, February recovery peak, and acute dips
     can be shown as annotations only after they are promoted to the active findings record.

## Idea backlog

| Idea | Why it may help | Requires |
|---|---|---|
| Autonomic balance axis card | Avoids separate stress/recovery gauges that double-count one state | Phase 1 axis result + Phase 2 score contract |
| Confidence/coverage badge | Prevents high-certainty display when data is missing or stale | Missing-data rule per score |
| Meaningful-change labels | Separates real movement from daily noise | Phase 3 smallest-worthwhile-change finding |
| Lead/lag expectation card | Frames low HRV after high-stress days as expected context, not surprise | Validated Phase 4 lead/lag finding |
| Oxygen flag | Keeps SpO2 visible without pretending it drives recovery | SpO2 min/avg decision + missingness rule |
| Thermoregulation flag | Surfaces acute illness/context outliers without making temperature a daily gauge | Skin-temp threshold finding |
| Derived-metric badge | Shows when evidence is Garmin-derived rather than source-native | Source-type metadata in score contract |
| Event markers | Helps users connect score shifts to known regimes | Promoted event findings |
| "Why this changed" panel | Turns the dashboard from reporting into explanation | Backend explanation contract |
| Load placeholder omitted | Avoids a fake progress story | Activity/session mart or training-load ingest |

## Anti-ideas to avoid

- A new 0-100 score with different arbitrary weights.
- Separate stress and recovery headline gauges if Phase 1 confirms they are mirror views of one
  autonomic axis.
- A progress, strain, or training-readiness claim before activity data exists.
- Frontend-computed baselines, smoothing, correlations, or derived status text.
- Pie, donut, dual-axis, or decorative chart forms.
- UI language that implies diagnosis, causality, or prescribed training action.

## Open design questions

- Should the overview keep any single headline number, or should it lead with a state label and
  use scores only inside axis cards?
- What confidence vocabulary is compact enough for daily use: high/medium/low, measured/limited,
  or a coverage percentage?
- Should event annotations live on the overview, only in drill-downs, or both?
- How much raw data belongs in the overview before it becomes a report rather than a dashboard?
- Should metric-specific routes remain as reference pages after axis-based drill-downs exist, or
  should they become secondary "source metric" views?
