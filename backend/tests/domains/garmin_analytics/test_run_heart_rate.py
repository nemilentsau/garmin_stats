"""Distribution evidence for per-second running heart-rate samples."""

from app.domains.garmin_analytics.contracts import RunZoneDisplayRow
from app.domains.garmin_analytics.domain.run_heart_rate import heart_rate_evidence

ZONES = [
    RunZoneDisplayRow(
        zone=1,
        label="Z1 · 94–109 bpm",
        lower_bound=94,
        upper_bound=109,
    ),
    RunZoneDisplayRow(
        zone=2,
        label="Z2 · 110–129 bpm",
        lower_bound=110,
        upper_bound=129,
    ),
    RunZoneDisplayRow(
        zone=3,
        label="Z3 · 130–147 bpm",
        lower_bound=130,
        upper_bound=147,
    ),
]


def test_complete_samples_expose_percentiles_histogram_and_zone_rows():
    result = heart_rate_evidence([129, 130, 131, 140], ZONES)

    assert result is not None
    assert result.total_samples == 4
    assert result.present_samples == 4
    assert result.coverage_pct == 100.0
    assert (result.q1_bpm, result.median_bpm, result.q3_bpm, result.p90_bpm) == (
        129.75,
        130.5,
        133.25,
        137.3,
    )
    assert result.histogram[0].model_dump() == {
        "bpm": 129,
        "sample_count": 1,
        "sample_pct": 25.0,
    }
    assert result.histogram[-1].model_dump() == {
        "bpm": 140,
        "sample_count": 1,
        "sample_pct": 25.0,
    }
    assert sum(row.sample_count for row in result.histogram) == 4
    assert result.zones == ZONES


def test_partial_samples_disclose_coverage_and_exclude_nulls():
    result = heart_rate_evidence([129, None, 131, None], ZONES)

    assert result is not None
    assert result.total_samples == 4
    assert result.present_samples == 2
    assert result.coverage_pct == 50.0
    assert [row.bpm for row in result.histogram] == [129, 130, 131]
    assert [row.sample_count for row in result.histogram] == [1, 0, 1]


def test_absent_samples_omit_evidence():
    assert heart_rate_evidence([], ZONES) is None
    assert heart_rate_evidence([None, None], ZONES) is None
