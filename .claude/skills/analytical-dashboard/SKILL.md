# Analytical Dashboard Design System

Comprehensive reference for designing health/wellness data dashboards that prioritize readability, information hierarchy, and human comprehension over aesthetics. Synthesizes principles from Edward Tufte, Stephen Few, Cole Nussbaumer Knaflic, Nielsen Norman Group, Apple HIG, Material Design, and leading health wearable platforms (Garmin, Oura, Whoop, Apple Health).

Every rule below is actionable and directly applicable when coding a dashboard.

---

## 1. Information Hierarchy & Layout

### 1.1 Reading Patterns

**Z-pattern** is the correct model for dashboards (not F-pattern). F-pattern applies to text-heavy pages (blogs, articles). Dashboards are sparse, card-based layouts where the eye follows: top-left -> top-right -> diagonal -> bottom-left -> bottom-right.

**Rules:**
- Place the single most important metric or summary bar in the **top-left quadrant**. The eye lands here first.
- Place secondary context (date picker, filters, navigation) in the **top-right**.
- KPI summary cards go in the **top row** -- this is the "hero section" that must be visible without scrolling.
- Detailed charts and tables go below the fold. Users scroll down for depth, not breadth.
- Never force users to scroll to compare two related metrics. Related metrics must be visible simultaneously.

### 1.2 Progressive Disclosure (Three Tiers)

Structure every dashboard as three information layers:

| Tier | Content | Interaction |
|------|---------|-------------|
| **L1 -- Glance** | Summary bar: 4-6 headline numbers with sparklines and deltas | Always visible, no interaction needed |
| **L2 -- Scan** | Metric cards in a grid: chart + key stats per metric | Visible on page load, cards scannable in <5 seconds |
| **L3 -- Investigate** | Full detail: expanded chart, table of readings, filter controls | Revealed on card click/expand or drill-down navigation |

**Do:** Show the summary bar with headline values at all times. Reveal detail on demand.
**Don't:** Dump all data on one screen. Don't hide the summary behind a tab.

### 1.3 Grid Systems

- Use a **12-column grid** at desktop widths. Cards snap to 3-col (4 cards/row), 4-col (3 cards/row), or 6-col (2 cards/row) depending on content density.
- **Equal-weight cards** are mandatory for multi-metric dashboards. Inconsistent card sizes create false hierarchy -- users assume bigger cards are more important.
- Standard card aspect ratios: **16:10** for chart-heavy cards, **4:3** for stat-heavy cards. Pick one and use it consistently.
- Minimum card width: **280px** (below this, charts become unreadable).
- **Gap between cards: 16-24px.** Tighter than 12px looks cramped. Wider than 32px breaks visual grouping.

### 1.4 Above the Fold

The top ~600px of viewport (typical fold on 1080p) must contain:
1. Dashboard title (compact, 20-24px max, never dominate the space)
2. Summary bar with headline KPIs
3. At least the top row of metric cards (partially visible is fine -- it signals scrollability)

**Do:** Keep the title to one line, 20-24px. Use the saved space for data.
**Don't:** Use 48-80px hero headers. The user sees the title on every load -- it doesn't need to shout.

---

## 2. Chart Selection & Data Visualization

### 2.1 Chart Selection by Data Type

| Data question | Chart type | Why |
|---------------|-----------|-----|
| How does a metric change over time? | **Line chart** | Shows rate of change, connects data points into trends |
| How do categories compare? | **Horizontal bar chart** | Length is the most accurately perceived visual attribute (Tufte, Few) |
| What is the distribution? | **Histogram** or **box plot** | Shows spread, skew, outliers |
| What is part-to-whole? | **Stacked bar** (few segments) or **100% stacked bar** | Better than pie charts at every task |
| How do two variables relate? | **Scatter plot** | Reveals correlation, clusters, outliers |
| What patterns exist across two dimensions? | **Heatmap** | Good for time-of-day x day-of-week, or metric x metric correlation |
| What is the current value vs target? | **Bullet graph** (Few) | Replaces gauges/dials, much more space-efficient |
| What is the recent micro-trend? | **Sparkline** | Word-sized chart, no axes, shows trajectory in minimal space |

### 2.2 Tufte's Principles (Applied)

**Data-ink ratio:** Every pixel of ink on your chart should encode data. If you can erase something without losing information, erase it.

Concrete removals:
- **Remove** chart borders/boxes around the plot area
- **Remove** background fills on the plot area (white or transparent, not gray)
- **Remove** gridlines except one or two light horizontal reference lines (if needed at all)
- **Lighten** axis lines to near-invisible or remove entirely (let tick marks suffice)
- **Remove** redundant legends when color is already labeled directly on lines
- **Remove** 3D effects on everything, always, no exceptions

**Small multiples:** When comparing the same metric across segments (e.g., sleep stages across 7 days), use identically-scaled small charts side by side. Same axes, same scale, same size. The only variable is the data.

**Lie factor:** The visual size of an effect must match the numerical size. A 10% increase should look like 10%, not 50%. Always start bar chart y-axes at zero. Line charts may use a narrower range when showing variation within a metric (e.g., resting HR 55-65 bpm), but annotate the baseline clearly.

### 2.3 Few's Dashboard-Specific Rules

- **Bullet graphs over gauges.** Circular gauges waste space and are harder to read than linear bullet graphs. A gauge takes the space of 4 bullet graphs.
- **No pie charts.** The eye compares angles poorly. Use horizontal bars or simple text with percentages.
- **No 3D charts.** Perspective distortion makes values unreadable. This is absolute.
- **No donut charts.** Marginally better than pie charts but still inferior to bars.
- **No treemaps on operational dashboards.** They require time to parse and are better for exploratory analysis.
- **Sparklines for context.** Pair every headline number with a sparkline showing its recent trajectory.

### 2.4 Knaflic's Storytelling Principles (Applied)

- **Eliminate clutter before adding decoration.** Start with the data, then remove everything non-essential, then (and only then) add visual emphasis to what matters.
- **Preattentive attributes for emphasis:** Use color saturation, weight (bold), size, or position to draw attention to the one thing the user should notice first. Not everything can be emphasized.
- **Direct labeling over legends.** Label data series directly on or next to the line/bar rather than using a separate legend that forces eye-jumping.

---

## 3. Typography for Data Dashboards

### 3.1 Font Selection Rules

**Mandatory for numbers: tabular, lining figures.** This is non-negotiable for any dashboard.

- **Tabular figures** = every digit occupies the same width. Numbers align vertically in columns. Without this, values jump around when data updates.
- **Lining figures** = all digits are the same height, sitting on the baseline. Oldstyle figures (with ascenders/descenders like in Georgia) are unreadable in data contexts.
- **Multiplexed** = digits maintain the same width across font weights. This prevents layout shift when bolding a number for emphasis.

**Recommended fonts with tabular lining figures:**
- Sans-serif: Roboto, Lato, Open Sans, Source Sans Pro, Noto Sans, DM Sans
- Monospace for numbers: DM Mono, IBM Plex Mono, JetBrains Mono, Geist Mono
- High-quality options: Inter (has tabular nums via OpenType), Instrument Sans, Plus Jakarta Sans

**Enable tabular numerals in CSS:**
```css
font-variant-numeric: tabular-nums lining-nums;
/* or via OpenType features: */
font-feature-settings: 'tnum' 1, 'lnum' 1;
```

### 3.2 Sizing Hierarchy

| Element | Size | Weight | Purpose |
|---------|------|--------|---------|
| Dashboard title | 20-24px | 600 (semi-bold) | Identify the page. Compact. |
| KPI headline number | 28-36px | 700 (bold) | The primary data point. Largest text on the card. |
| KPI label | 11-13px | 400-500 | Identifies what the number represents. |
| KPI delta/change | 12-14px | 500-600 | Shows trend direction. Paired with arrow icon. |
| Card title | 14-16px | 600 | Names the metric the card shows. |
| Chart axis labels | 10-12px | 400 | Small but legible. Must not compete with data. |
| Chart axis tick values | 10-12px | 400 | Right-aligned for y-axis, centered for x-axis. |
| Tooltip values | 12-14px | 500 | Precise values on hover. Slightly larger than axis labels. |
| Secondary/context stats | 11-13px | 400 | Sub-stats on cards (resting HR, weekly avg, etc.) |

### 3.3 Number Readability Rules

- **Right-align** all numeric columns. Numbers read right-to-left (ones, tens, hundreds), so right alignment lets the eye compare magnitudes instantly.
- **Consistent decimal places** within a column. If one value shows 72.5, show 98.0, not 98.
- **Use the same number of significant digits** across related metrics. Heart rate to 0 decimals. HRV to 0 decimals. SpO2 to 1 decimal. Temperature to 1 decimal.
- **Thousands separators** for values >9999. Use commas (12,450) or locale-appropriate separators. Omit for values <10000.
- **Units next to label, not next to every number.** Write "Heart Rate (bpm)" as the card title, then just show "72" as the value. Don't repeat "72 bpm" in every cell.

### 3.4 Label Placement

- **Chart titles: top-left** of the card, flush with the card edge.
- **Y-axis labels:** rotated 90 degrees counter-clockwise, placed at the top of the axis. Or better: omit and rely on the card title.
- **X-axis labels:** below the axis, centered on tick marks. For dates, show enough context (Mon, Tue or Jan 15, not just 15).
- **Direct labels on lines:** Place value labels at the end of the line or at significant peaks/troughs. Don't label every point (clutter).
- **Annotation callouts:** Use sparingly. One or two per chart maximum, pointing to notable events (e.g., "Rest day" or "Travel").

---

## 4. Color in Analytical Dashboards

### 4.1 Semantic Color System

Color must encode meaning, never decorate. Every color in a dashboard must answer: "What does this color tell the user?"

**Status encoding (traffic light with caveats):**
- Green = good/on-target/healthy range (but see accessibility below)
- Amber/Yellow = warning/approaching threshold
- Red = alert/out-of-range/action needed
- Gray = neutral/no data/baseline

**Health metric encoding:**
Assign one distinct hue per metric. This is the single most important color decision for multi-metric dashboards:

| Metric | Suggested hue family | Rationale |
|--------|---------------------|-----------|
| Heart Rate | Red/warm coral | Universal heart association |
| HRV | Purple/violet | Distinct from HR, suggests complexity |
| Stress | Amber/orange | Warning association |
| SpO2 | Blue/cyan | Oxygen, clinical association |
| Respiration | Teal/green-blue | Breath, calm association |
| Sleep | Indigo/deep blue | Night, rest association |
| Skin Temperature | Warm amber/gold | Heat association |
| Body Battery/Energy | Green/emerald | Vitality association |

**Rule:** The metric's color carries through every representation: summary bar accent, chart line, card border/accent, icon tint.

### 4.2 Palette Types and When to Use Them

**Sequential palette** (light-to-dark of one hue):
- Use for: ordered data, low-to-high values, intensity scales
- Example: sleep depth (light blue = awake, dark blue = deep sleep)
- Lighter = lower values, darker = higher values

**Diverging palette** (two hues meeting at a neutral midpoint):
- Use for: data with a meaningful center (e.g., deviation from average, above/below baseline)
- Example: HRV deviation from personal baseline (blue = below, white = at baseline, red = above)
- Requires a legend or clear labeling -- diverging palettes are not self-explanatory

**Categorical palette** (distinct hues, no implied order):
- Use for: unordered categories (sleep stages, activity types, metric types)
- Keep to 6-8 colors maximum. Beyond 8, humans cannot reliably distinguish categories.
- Separate hues by at least 30 degrees on the color wheel

### 4.3 Accessibility (Colorblind-Safe)

~8% of men and ~0.5% of women have some form of color vision deficiency. Red-green deficiency (deuteranopia/protanopia) is most common.

**Rules:**
- **Never use red-green as the only differentiator.** Pair with a secondary cue: icon shape (checkmark vs X), text label ("Good" vs "Poor"), pattern, or position.
- **Use blue-orange** as a safe contrasting pair instead of red-green when possible.
- **Minimum contrast ratio** for graphical elements: **3:1** against background (WCAG 2.1 Level AA).
- **Minimum contrast ratio** for text: **4.5:1** for normal text, **3:1** for large text (18px+ or 14px+ bold).
- **Test every palette** under protanopia, deuteranopia, and tritanopia simulations. Tools: Viz Palette, Sim Daltonism, Chrome DevTools rendering emulation.
- **Redundant encoding is mandatory.** Color should never be the sole channel for any critical information. Always pair with: shape, pattern, label, or position.

### 4.4 Dark Mode Specifics

- **Never use pure black (#000000).** Use dark navy (#0a0f1e to #1a1f2e) or charcoal (#1e1e2e to #2a2a3a). Pure black creates harsh contrast that causes eye fatigue.
- **Never use pure white (#FFFFFF) for text.** Use off-white (#e0e0e0 to #f0f0f0). Pure white on dark backgrounds vibrates visually.
- **Desaturate colors 10-20%** compared to light mode. Highly saturated colors on dark backgrounds cause visual vibration and reduce readability.
- **Chart lines need higher luminance** on dark backgrounds. Ensure chart lines have contrast ratio >= 3:1 against the card background.
- **Test pastel card backgrounds:** Pastel backgrounds compete with chart lines. Use near-black card backgrounds with colored accents (borders, line colors), not colored card fills.

### 4.5 Color Budget

Limit the total palette to enforce discipline:
- **3-4 metric hues** for primary data series
- **1 accent color** for interactive elements (selected state, primary actions)
- **3 neutral tones** (background, card surface, text levels)
- **2-3 semantic colors** (success/warning/error) used only for status, not decoration

Total: ~10-12 colors in the full system. If you need more, you're encoding too many categories visually.

---

## 5. Density & Whitespace

### 5.1 Dashboard vs Report

| Property | Dashboard | Report |
|----------|-----------|--------|
| Purpose | Monitor, detect anomalies | Analyze, explain, document |
| Density | High (many metrics visible) | Lower (one topic in depth) |
| Interaction | Glance, scan, click to drill | Read sequentially |
| Fits on | One screen (no scrolling for overview) | Multiple pages |
| Update frequency | Live or daily | Weekly/monthly/ad-hoc |

**A dashboard must fit its overview on one screen.** If users must scroll to see the state of the system, it's a report, not a dashboard.

### 5.2 Gestalt Principles Applied

**Proximity:** Place related elements close together. A card title must be visually closer to its chart than to the neighboring card's content. Use consistent inner padding (16-20px) and larger outer gaps (20-28px) to create clear groups.

**Similarity:** Use the same card size, corner radius, shadow depth, and layout for all metric cards. Inconsistency (one card with a border, another without) implies a hierarchy that doesn't exist.

**Enclosure:** Use subtle background fills or very light borders to group related cards. A shared background groups more strongly than proximity alone.

**Connection:** Lines between elements (e.g., a breadcrumb trail, a timeline axis) create the strongest grouping. Use sparingly -- only for elements that truly form a sequence.

**Continuity:** Align card edges. Misaligned elements break the visual flow and look unintentional. Snap to grid.

### 5.3 Whitespace Rules

- **Card inner padding:** 16-20px on all sides. This is content breathing room.
- **Inter-card gap:** 16-24px. This separates cards without disconnecting them.
- **Section gaps** (between summary bar and grid, between grid and detail area): 28-40px. Larger gaps signal section boundaries.
- **Chart margin within card:** At minimum, 8px between chart edge and card border. Charts touching the card edge look cramped.
- **Whitespace is not wasted space.** It groups, separates, and provides visual rest. But whitespace on a monitoring dashboard is more expensive than on a marketing page. Every pixel not showing data must earn its place by improving comprehension.

### 5.4 When Compact Is Better

Compact density is correct when:
- Users are experts who monitor this dashboard daily (they've learned the layout)
- Cross-metric pattern recognition matters (seeing HR spike alongside stress spike)
- The dashboard is on a dedicated monitor or kiosk
- Users need to spot anomalies across many dimensions quickly

Use generous whitespace when:
- Users are infrequent visitors
- The dashboard explains rather than monitors
- The primary task is understanding a single metric in depth

---

## 6. Interaction Patterns

### 6.1 Tooltips

**Content rules:**
- Show the **exact value** (the chart shows approximate position; the tooltip provides precision)
- Include the **timestamp** or category label for the hovered point
- Add **context** the chart doesn't show: e.g., on a daily HR chart, the tooltip might show "Resting: 54, Peak: 142, Activity: Running"
- **Never duplicate** what's already visible. If the axis label says "Monday" and the bar shows "245 steps," the tooltip saying "Monday: 245 steps" adds nothing.

**Behavior rules:**
- Appear after **100-200ms** hover delay (not instant -- prevents flicker during mouse movement)
- Disappear after **200-300ms** after mouse leaves (gives user time to read)
- **Position:** Above the point by default. Flip to below if near top edge. Never obscure the data point being inspected.
- **One tooltip at a time.** Never stack or overlap tooltips.
- **Accessible via keyboard:** Tooltips must be reachable via Tab + Enter or focus states for screen reader users. Hover-only tooltips exclude keyboard users.

### 6.2 Drill-Down / Expand

- **Click a card to expand.** The card grows to full-width or opens a detail panel showing: full-resolution chart, data table, additional stats, time range controls.
- **Preserve context:** When drilling into one metric, keep the summary bar visible so users maintain orientation.
- **Clear escape:** Always show a close/back button and support Escape key to return to the overview.
- **URL-driven state:** Drill-down should update the URL (e.g., `/dashboard?metric=hrv&range=7d`) so users can bookmark or share specific views.

### 6.3 Filtering

- **Global filters** (date range, time period) go in the top bar, visible at all times.
- **Card-level filters** (e.g., sleep stage selector within the sleep card) go inside the card, near the chart they affect. Use the Gestalt proximity principle -- a filter placed far from its chart confuses users about what it controls.
- **Filter state must be visible.** Show active filters as chips/tags. Never hide the current filter state.
- **Sensible defaults.** Default to the most useful view (e.g., "Last 7 days" for daily dashboards, "Last 30 days" for trend dashboards). Never default to "All time" which is too much data for a dashboard.

### 6.4 Brushing & Linking

When multiple charts show related data (e.g., HR and stress over the same time period):
- **Hovering** one chart should highlight the corresponding time point on all other charts (crosshair synchronization).
- **Selecting** a time range on one chart should filter/zoom all other charts to that range.
- **This is the most powerful interaction pattern for health dashboards** because it lets users ask "What was my stress like when my HR spiked?" by simply hovering.

### 6.5 Time Range Controls

- Provide preset ranges: **1d, 7d, 30d, 90d, 1y**
- Support custom date range picker for power users
- **Scroll to navigate time:** On a 7-day view, allow swiping or arrow keys to move to the previous/next 7 days
- **Zoom in/out:** Scroll wheel or pinch-to-zoom on the chart to change time resolution
- Show the current date range prominently (e.g., "Feb 24 - Mar 2, 2026")

---

## 7. Common Anti-Patterns

### 7.1 Pie Charts

**Problem:** Humans perceive angle and area poorly. Comparing a 22% slice to a 27% slice is nearly impossible without labels. Pie charts fail at their primary job (comparison).

**The only acceptable pie chart:** Exactly 2 segments showing a part-to-whole relationship (e.g., 73% complete), and even then a progress bar or simple text "73%" is better.

**Replace with:** Horizontal bar chart (always), simple text with percentage, or waffle chart for part-to-whole.

### 7.2 3D Charts

**Problem:** Perspective distortion makes values unreadable. Bars at the back of a 3D bar chart appear smaller than bars at the front regardless of their actual value. 3D pie charts distort slice sizes based on viewing angle.

**Rule: Zero tolerance for 3D in any analytical context.** There is no data type that benefits from 3D rendering.

### 7.3 Rainbow Color Scales

**Problem:** Rainbow (ROYGBIV) color maps have perceptual non-uniformities. Yellow appears brighter than blue at the same data value, creating phantom patterns. The scale is not perceptually ordered -- a viewer cannot intuitively rank "orange" vs "teal."

**Replace with:** Sequential single-hue palette (light-to-dark blue), or Viridis/Magma/Inferno perceptually uniform color maps.

### 7.4 Dual-Axis Charts

**Problem:** Two y-axes with independent scales. By adjusting the scale of either axis, you can make any two trends appear correlated or anti-correlated. The viewer cannot verify the relationship because the visual encoding is manipulated by the scale choice.

**When acceptable:** Only when the two metrics share a meaningful, fixed relationship (e.g., temperature in Celsius and Fahrenheit) or when the user explicitly controls the scales.

**Replace with:** Two separate charts stacked vertically, sharing the same x-axis. This preserves time alignment without misleading scale comparison.

### 7.5 Too Many KPIs

**Problem:** Dashboards with 15-20 KPIs on the summary bar. Cognitive overload -- users can't process more than 5-7 items in working memory (Miller's Law).

**Rule:** Summary bar: **4-6 KPIs maximum.** If you have more metrics, the summary shows only the most actionable ones; the rest live in the metric grid below.

### 7.6 Vanity Metrics

**Problem:** Metrics that look impressive but don't inform decisions. "Total steps ever: 12,450,000" -- what action does this drive?

**Test every metric:** "If this number changed, would the user do something different?" If no, remove it from the dashboard and put it in a report.

### 7.7 Truncated Bar Chart Axes

**Problem:** Starting a bar chart's y-axis at a value other than zero exaggerates small differences. A bar from 95 to 100 looks 5x larger than a bar from 95 to 96 when the axis starts at 90.

**Rule:** Bar charts always start at zero. Line charts may use a narrowed range (because the slope encodes the rate of change, not the absolute magnitude), but annotate the baseline clearly.

### 7.8 Misleading Time Axes

**Problem:** Non-uniform time spacing (Jan, Feb, Mar, Jun, Dec plotted with equal spacing) distorts trends by hiding gaps.

**Rule:** Time axes must be proportionally spaced. If there's a gap in data, show the gap visually.

---

## 8. Health/Wellness Dashboard Specifics

### 8.1 Competitor Platform Analysis

**Oura Ring:**
- Structure: Three tabs -- Today (daily snapshot), Vitals (detailed metrics), My Health (long-term trends)
- Scores: Readiness (0-100), Sleep (0-100), Activity -- displayed as large ring gauges at top of Today tab
- Color hierarchy: Important information is brighter; secondary information fades back. Uses luminance, not hue, for hierarchy.
- Strengths: Clean progressive disclosure. Daily view is immediately useful. Trends tab shows long-term patterns without cluttering the daily view.
- Weakness: Relies solely on the app (no screen on device), score explanation requires multiple taps.

**Whoop:**
- Structure: Recovery score (0-100%), Strain score (0-21 Borg scale), Sleep performance
- Color encoding: Green (67-100% recovery = go), Yellow (34-66% = moderate), Red (0-33% = rest). Simple three-tier system.
- Journal: Logs 140+ behaviors, then correlates them with recovery scores to show which habits help/hurt.
- Strengths: Extremely actionable. The three-color system immediately tells users what to do today. Strain target gives a concrete daily goal.
- Weakness: Oversimplification -- the color categories collapse nuance. Subscription model locks data access.

**Garmin Connect:**
- Structure: Customizable widget-based dashboard. Body Battery (0-100), Stress (0-100), Sleep Score (0-100), HR/HRV timeline.
- Visualization: Combined Body Battery + Stress graph shows inverse relationship over time. Stacked sleep stage bars.
- Strengths: Data density is high. Power users get granular access. Customizable layout.
- Weakness: Information overload for casual users. Sleep and recovery features feel secondary to sports tracking. Lacks the "one number to rule them all" simplicity of Oura/Whoop.

**Apple Health:**
- Structure: Favorites (pinned metrics), Browse (categorical list), Trends (long-term direction)
- Activity Rings: Three concentric rings (Move, Exercise, Stand) -- iconic, immediately understood.
- Chart style: Bar histograms for daily data, horizontal bars for current-day detail. Interactive with tap-to-inspect.
- Strengths: Consistency -- every metric uses the same chart format. Trends feature automatically detects if a metric is increasing/decreasing. Accessible design.
- Weakness: Individual metric views lack cross-metric correlation. Can't see HR and sleep on the same screen.

### 8.2 Health Data Display Conventions

**Scores (0-100 or composite):**
- Display as large number + ring/arc gauge or progress bar
- Color-code by range: green/yellow/red zones
- Show contributing factors as smaller sub-metrics below the headline score
- Example: "Readiness: 78" with sub-bars for "Resting HR: Good | HRV: Fair | Sleep: Good"

**Continuous physiological data (HR, stress, SpO2):**
- Line chart is the standard for time-series physiological data
- Show the current/latest value prominently alongside the chart
- Annotate resting values, peaks, and ranges as reference bands
- Use color zones: e.g., HR zones (rest, fat burn, cardio, peak) as horizontal bands behind the line

**Sleep data:**
- Horizontal stacked bars for sleep stages (awake, REM, light, deep) -- this is the industry standard across all platforms
- Show total duration as headline, stage breakdown as percentages
- Night-by-night comparison: small multiples of sleep stage bars, one per night, aligned to the same time axis
- Sleep score as a single headline number, with contributing factors listed below

**Recovery/readiness data:**
- Single composite score with simple color coding (3 tiers: good/fair/poor)
- Pair with the 2-3 most influential contributing metrics
- Show 7-day trend sparkline next to today's score

**Temperature and respiratory rate:**
- Show deviation from personal baseline rather than absolute value ("+0.3 C from baseline" is more meaningful than "36.8 C")
- Use diverging color scale: blue for below baseline, neutral for at baseline, red for above

### 8.3 Temporal Patterns

Health data has natural temporal rhythms. Design for them:

| Time scale | What to show | Chart type |
|------------|------------|------------|
| **Intraday** (24h) | HR timeline, stress curve, activity bouts | Line chart with time-of-day x-axis |
| **Daily** | Sleep score, readiness, daily totals | KPI cards with sparklines |
| **Weekly** | 7-day trends, day-by-day comparison | Small multiples or grouped bars |
| **Monthly** | Rolling averages, habit patterns | Line chart with 7-day rolling mean overlay |
| **Long-term** (90d+) | Baseline drift, seasonal patterns | Line chart with trend line, wider date ticks |

**Rule:** Default to 7-day view for daily dashboards. It shows enough context for pattern recognition without overwhelming. Provide 1d/30d/90d as alternatives.

**Rolling means:** Use 7-day rolling averages for noisy metrics (HRV, sleep quality) to reveal trends. Show both the raw daily values (dots or thin line) and the rolling average (bold line) on the same chart.

---

## 9. Number Formatting

### 9.1 Significant Digits by Metric Type

| Metric | Precision | Example | Rationale |
|--------|-----------|---------|-----------|
| Heart rate | 0 decimals | 72 | Precision below 1 bpm is noise |
| HRV (ms) | 0 decimals | 48 | Sub-millisecond is measurement noise |
| SpO2 (%) | 0-1 decimals | 97 or 97.2 | Clinical convention varies |
| Respiration (brpm) | 0-1 decimals | 16 or 15.8 | Sub-breath precision is noise |
| Body temperature | 1 decimal | 36.8 | 0.1 C resolution is clinically relevant |
| Skin temperature deviation | 2 decimals | +0.23 | Deviations are small, precision matters |
| Sleep duration | hours:minutes | 7h 32m | Not decimal hours (7.53h is unreadable) |
| Stress score | 0 decimals | 42 | Integer score |
| Percentage change | 1 decimal + sign | +3.2% | Show sign always for deltas |

### 9.2 Delta/Change Indicators

- **Always show sign:** "+5" and "-3", never just "5" and "3"
- **Arrow icons reinforce direction:** Up arrow (green/red depending on metric -- higher HR is bad, higher HRV is good) + numeric delta
- **Percentage vs absolute:** Use percentage for metrics with different scales ("HRV +12%"), use absolute for metrics the user understands in raw units ("Resting HR -3 bpm")
- **Comparison period:** Label the comparison explicitly: "vs last week", "vs 30-day avg", "vs yesterday"
- **Semantic direction matters:** For HR, lower is better (green down arrow). For HRV, higher is better (green up arrow). For sleep, more is better (green up arrow). Hardcode the "good direction" per metric.

### 9.3 Units Placement

- **In the label, not the value:** "Heart Rate (bpm)" as the card title, then just "72" as the value
- **Exception for standalone numbers:** If a number appears in a tooltip or annotation without context, include the unit inline: "72 bpm"
- **Duration:** Use "7h 32m" format, not "7.53 hours" or "452 min"
- **Temperature:** Always include the degree symbol and scale: "36.8 C" (or "98.2 F" based on user preference)

### 9.4 Conditional Formatting

- **In-range values:** Normal text color (e.g., white on dark, black on light)
- **Out-of-range values:** Semantic color (red text or red background dot) + tooltip explaining the threshold
- **Improving trend:** Green delta text with up/down arrow (directionally correct for the metric)
- **Worsening trend:** Red delta text with appropriate arrow
- **No change:** Gray delta text, horizontal line icon

### 9.5 Sparklines

- **Width:** 60-120px. Wide enough to show a 7-day pattern but compact enough to fit next to a headline number.
- **Height:** 20-32px. Matches the height of the text it accompanies.
- **No axes, no labels.** Sparklines are visual texture showing trajectory. The headline number provides the absolute value.
- **Highlight the last point** with a dot or slightly larger end cap to show where "now" is.
- **Color:** Match the metric's assigned color, or use a neutral color if the sparkline is secondary to the number.

---

## 10. Responsive Considerations

### 10.1 Breakpoint Strategy

| Breakpoint | Width | Grid | Cards per row | Behavior |
|------------|-------|------|---------------|----------|
| Desktop large | >=1440px | 12-col | 4 | Full density, all features |
| Desktop | >=1024px | 12-col | 3-4 | Full density, may stack summary bar |
| Tablet | >=768px | 8-col | 2 | Reduce to priority metrics in summary bar |
| Mobile large | >=480px | 4-col | 1 | Cards stack vertically, summary bar becomes scrollable horizontal strip |
| Mobile | <480px | 4-col | 1 | Minimal KPI view, charts simplified or collapsed |

### 10.2 Priority-Based Show/Hide

Not all content deserves screen space at every breakpoint. Assign priority levels:

| Priority | Content | Desktop | Tablet | Mobile |
|----------|---------|---------|--------|--------|
| P0 (critical) | Summary KPIs, headline numbers | Show | Show | Show |
| P1 (important) | Metric charts, sparklines | Show | Show | Collapsed (tap to expand) |
| P2 (contextual) | Secondary stats, comparison data | Show | Show | Hidden (available via detail view) |
| P3 (supplementary) | Annotations, correlations, long-range trends | Show | Hidden | Hidden |

### 10.3 Chart Adaptations by Breakpoint

- **Desktop:** Full interactive charts with hover tooltips, brush selection, crosshair linking
- **Tablet:** Full charts but replace hover tooltips with tap-to-inspect (no hover on touch)
- **Mobile:** Replace complex charts with simplified versions:
  - Line charts: reduce to 7 data points (one per day) instead of intraday resolution
  - Heatmaps: replace with simple ranked lists
  - Multi-series charts: show one series at a time with a toggle
  - Tables: collapse rows into stacked cards

### 10.4 Touch Targets

- **Minimum touch target: 44x44px** (Apple HIG) or **48x48dp** (Material Design)
- **Chart data points** must have touch targets that extend beyond the visible dot/line. Use invisible hit areas of at least 44x44px around each interactive point.
- **Spacing between interactive elements:** At least 8px gap to prevent mis-taps.

### 10.5 Mobile-Specific Patterns

- **Horizontal scroll for summary bar:** KPI cards scroll left-right in a single row instead of wrapping.
- **Swipe between metrics:** On mobile, use horizontal swipe to navigate between metric detail views instead of showing all cards at once.
- **Bottom sheet for drill-down:** Instead of navigating to a new page, pull up a bottom sheet overlay for metric detail. This preserves context and enables quick dismissal.
- **Simplify chart interactions:** No brushing/linking on mobile. Replace with tap-to-inspect and preset time range buttons.

---

## Quick Reference: Decision Checklist

Before shipping any dashboard view, verify:

- [ ] Summary bar shows 4-6 KPIs with sparklines above the fold
- [ ] Each metric has a distinct, consistent color across all representations
- [ ] Cards are equal-sized in a clean grid (no size hierarchy without intent)
- [ ] Chart lines have >= 3:1 contrast against card background
- [ ] Numbers use tabular lining figures with `font-variant-numeric: tabular-nums`
- [ ] No pie charts, 3D charts, or rainbow color scales
- [ ] Tooltips show exact values + timestamp on hover
- [ ] Redundant encoding: color + shape/label for all status indicators
- [ ] Time axes are proportionally spaced
- [ ] Deltas show sign, arrow, and comparison period label
- [ ] Bar charts start at zero
- [ ] Mobile view has P0/P1 content only, touch targets >= 44px
- [ ] Dark mode avoids #000 background and #FFF text
- [ ] Y-axis values are right-aligned with consistent decimal places
- [ ] Filters show their current state visibly
