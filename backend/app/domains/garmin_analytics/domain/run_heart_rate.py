"""Distribution evidence for recorded running heart-rate samples."""

import numpy as np

from app.domains.garmin_analytics.contracts.runs import (
    RunHeartRateEvidence,
    RunHeartRateHistogramBin,
    RunZoneDisplayRow,
)


def heart_rate_evidence(
    readings: list[int | None], zones: list[RunZoneDisplayRow]
) -> RunHeartRateEvidence | None:
    """Summarize present HR samples without treating nulls as zero or duration."""
    present = np.asarray([value for value in readings if value is not None], dtype=float)
    if present.size == 0:
        return None

    low = int(np.floor(present.min()))
    high = int(np.ceil(present.max()))
    counts, _ = np.histogram(present, bins=np.arange(low, high + 2))
    q1, median, q3, p90 = np.percentile(present, [25, 50, 75, 90])
    present_count = int(present.size)
    return RunHeartRateEvidence(
        total_samples=len(readings),
        present_samples=present_count,
        coverage_pct=round(100 * present_count / len(readings), 1),
        q1_bpm=round(float(q1), 2),
        median_bpm=round(float(median), 2),
        q3_bpm=round(float(q3), 2),
        p90_bpm=round(float(p90), 2),
        histogram=[
            RunHeartRateHistogramBin(
                bpm=low + index,
                sample_count=int(count),
                sample_pct=round(100 * int(count) / present_count, 2),
            )
            for index, count in enumerate(counts)
        ],
        zones=zones,
    )
