# Coach Run Panels — Pipeline Retrospective

## What worked

- Reusing `RunDetailResponse` and `RunSeriesResponse` kept Garmin parsing and analytical ownership outside coach.
- Adding display-ready `step_length_m` and `vertical_oscillation_cm` to the analytics read contract preserved the frontend/consumer display-only rule.
- Content fingerprints plus an explicit panel-spec version made cache behavior testable and made the visual gap fix invalidate existing files deterministically.
- Real-data inspection exposed a gap-bridging defect that fixture-only image existence tests could not reveal.

## What could improve

- The first auto-sampler allowed the lap-rich choice to duplicate another category, yielding only two runs. It now selects the lap-rich run from the remaining IDs, keeping the sample deterministic and distinct.
- Image tests verify cache and channel branches, but visual QA remains necessary for line semantics and label fit.

## Skill updates

No skill update is needed. The existing data-analysis rule to break between-process gaps directly identified the defect, and the analytical-dashboard guidance correctly favored aligned small multiples with direct labels.
