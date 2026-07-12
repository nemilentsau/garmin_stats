# Coach Run Panels — EDA Analysis

## Sample

- `23490523365` (2026-07-05): 12.02 mi chest-strap run, 13 laps, 6,065 records, all 16 configured channels.
- `23563889771` (2026-07-11): 6.02 mi wrist run, 7 laps, 3,192 records, 13 channels. Ground-contact balance, respiration, and stance-time percentage are correctly absent.
- `23211503506` (2026-06-11): 12.21 mi wrist/lap-rich run, 13 laps, 6,262 records, 12 channels and a 571-second record gap.

The sample covers the intended quality classes: full strap dynamics, ordinary wrist data with missing strap-only channels, and a lap-rich session with a large structural gap.

## Observations

- The compact three-strip panel answers its triage question: pace discontinuities line up vertically with HR/cadence changes and lap boundaries, making stops, recoveries, and late-run drift visible without opening the full channel stack.
- The wrist run omits unavailable strap-only panels rather than drawing empty or zero-valued strips.
- Cadence zeros and extreme pace values coincide with stops/dropouts; they remain visible as source observations rather than being silently filtered.
- Stamina and performance-condition series are stepwise by source design. They are not smoothed or interpolated.
- A first render connected observations across elapsed-time jumps. The Antibes 571-second gap produced a false diagonal in pace, HR, and cadence. `break_elapsed_gaps()` now inserts a NaN separator whenever adjacent records differ by more than three seconds, and panel spec v2 invalidates the stale cache.

## Decision

Keep the three-strip historical panel and four-strip current-run pages. They use shared elapsed-time axes, direct unit labels, sparse horizontal grids, and no dual axes. No statistical or compliance inference is added.
