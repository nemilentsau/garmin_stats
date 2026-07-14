# Coach Run Panels — Visual Inspection

## Five-second check

- No panel is blank when its source channel is present.
- Pace is oriented faster-up and labeled `min/mi`; elevation is feet; temperature is °F; stride length is meters; vertical oscillation is centimeters; GCT is milliseconds.
- Shared elapsed-time axes cover the full recorded sessions: approximately 6,200 s, 3,300 s, and 7,300 s for the three samples.
- Run/walk shading is subdued and lap markers remain distinguishable without overpowering the series.
- Long record gaps are white breaks, not straight interpolated lines.

## Source spot checks

1. `23490523365`: manifest reports 12.02 mi, 8.4 min/mi, average HR 140, and 13 laps. The compact panel is centered near 8–9 min/mi and roughly 140 bpm, with 13 lap divisions and late HR rising into the 150s.
2. `23563889771`: manifest reports 6.02 mi, 8.8 min/mi, average HR 135, and wrist HR. The historical panel sits near those values; the current stack has 13 channels and correctly excludes balance/respiration/stance-time strips.
3. `23211503506`: source inspection found a 571-second elapsed gap between 2,452 s and 3,023 s. The final panel shows a visible break over that interval in all three aligned series.

## Readability

- Direct labels fit at the normal rendered width; no legend lookup is required.
- Pages contain at most four strips, so dense strap data remains readable.
- Y-scales hug observed line-series ranges. Large real spikes remain visible rather than being clipped.
- No chart uses decorative fills, 3D, gauges, or unrelated color. Color distinguishes metric identity and position provides the primary comparison.

Result: visual gate passed after the elapsed-gap correction and spec-version bump.
