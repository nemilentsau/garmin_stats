"""Tests for Garmin analytics period aggregate helper policies."""

from app.domains.garmin_analytics.contracts import (
    BodyBatteryReading,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SpO2Reading,
    StressReading,
)
from app.domains.garmin_analytics.domain.aggregates.period import (
    compute_period_body_battery,
    compute_period_heart_rate,
    compute_period_hrv,
    compute_period_respiration,
    compute_period_skin_temp,
    compute_period_sleep,
    compute_period_spo2,
    compute_period_stress,
)


def _day(
    date: str = "2026-01-15",
    *,
    heart_rate: list[int] | None = None,
    resting_hr: list[RestingHRReading] | None = None,
    stress: list[int] | None = None,
    respiration: list[float] | None = None,
    spo2: list[int] | None = None,
    body_battery: list[int] | None = None,
    hrv_summaries: list[HrvSummary] | None = None,
    skin_temp: list[SkinTempOvernight] | None = None,
    sleep: list[SleepAssessment] | None = None,
) -> DayData:
    return DayData(
        date=date,
        wellness=DayWellness(
            date=date,
            heart_rate=[
                HeartRateReading(timestamp=f"{date}T00:{i:02d}:00", value=value)
                for i, value in enumerate(heart_rate or [])
            ],
            resting_hr=resting_hr or [],
            stress=[
                StressReading(timestamp=f"{date}T01:{i:02d}:00", value=value)
                for i, value in enumerate(stress or [])
            ],
            respiration=[
                RespirationReading(timestamp=f"{date}T02:{i:02d}:00", value=value)
                for i, value in enumerate(respiration or [])
            ],
            spo2=[
                SpO2Reading(
                    timestamp=f"{date}T03:{i:02d}:00",
                    value=value,
                    mode="sleep",
                )
                for i, value in enumerate(spo2 or [])
            ],
            body_battery=[
                BodyBatteryReading(timestamp=f"{date}T04:{i:02d}:00", value=value)
                for i, value in enumerate(body_battery or [])
            ],
        ),
        hrv=DayHrv(date=date, hrv_summaries=hrv_summaries or []),
        skin_temp=DaySkinTemp(date=date, skin_temp_overnight=skin_temp or []),
        sleep=DaySleep(date=date, sleep_assessments=sleep or []),
    )


def test_period_heart_rate_empty_days_return_nulls_and_empty_zones():
    result = compute_period_heart_rate([])
    assert result.avg is None
    assert result.avg_resting is None
    assert result.typical_low is None
    assert result.typical_high is None
    assert result.zones == []


def test_period_heart_rate_uses_raw_reading_weighted_average_and_resting_last_value():
    day1 = _day(
        "2026-01-01",
        heart_rate=[60, 60, 60, 60, 60],
        resting_hr=[
            RestingHRReading(timestamp="2026-01-01T05:00:00", resting_hr=52),
            RestingHRReading(timestamp="2026-01-01T06:00:00", resting_hr=48),
        ],
    )
    day2 = _day(
        "2026-01-02",
        heart_rate=[100],
        resting_hr=[
            RestingHRReading(
                timestamp="2026-01-02T06:00:00",
                resting_hr=51,
                current_day_resting_hr=46,
            )
        ],
    )

    result = compute_period_heart_rate([day1, day2])

    assert result.avg == 66.7
    assert result.avg_resting == 47.0
    assert result.zones


def test_period_stress_empty_days_return_nulls():
    result = compute_period_stress([])
    assert result.avg is None
    assert result.typical_low is None
    assert result.typical_high is None


def test_period_stress_uses_raw_values_for_average_and_percentiles():
    result = compute_period_stress([_day(stress=[10, 20, 30, 40])])
    assert result.avg == 25.0
    assert result.typical_low == 17.5
    assert result.typical_high == 32.5


def test_period_respiration_empty_days_return_nulls():
    result = compute_period_respiration([])
    assert result.avg is None
    assert result.typical_low is None
    assert result.typical_high is None


def test_period_respiration_uses_raw_values_for_average_and_percentiles():
    result = compute_period_respiration([_day(respiration=[12.0, 14.0, 16.0, 18.0])])
    assert result.avg == 15.0
    assert result.typical_low == 13.5
    assert result.typical_high == 16.5


def test_period_hrv_empty_summaries_return_nulls_and_zero_days():
    result = compute_period_hrv([_day()])
    assert result.avg_nightly is None
    assert result.avg_weekly is None
    assert result.balanced_pct is None
    assert result.total_days == 0


def test_period_hrv_excludes_null_values_and_rounds_balanced_status_percentage():
    result = compute_period_hrv([
        _day(
            "2026-01-01",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-01",
                    last_night_average=50.0,
                    weekly_average=None,
                    status="balanced",
                )
            ],
        ),
        _day(
            "2026-01-02",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-02",
                    last_night_average=None,
                    weekly_average=60.0,
                    status="low",
                )
            ],
        ),
        _day(
            "2026-01-03",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-03",
                    last_night_average=70.0,
                    weekly_average=80.0,
                    status="balanced",
                )
            ],
        ),
    ])
    assert result.avg_nightly == 60.0
    assert result.avg_weekly == 70.0
    assert result.balanced_pct == 67
    assert result.total_days == 3


def test_period_hrv_does_not_count_unbalanced_status_as_balanced():
    result = compute_period_hrv([
        _day(
            "2026-01-01",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-01",
                    last_night_average=50.0,
                    weekly_average=55.0,
                    status="balanced",
                )
            ],
        ),
        _day(
            "2026-01-02",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-02",
                    last_night_average=45.0,
                    weekly_average=50.0,
                    status="unbalanced",
                )
            ],
        ),
        _day(
            "2026-01-03",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-03",
                    last_night_average=40.0,
                    weekly_average=45.0,
                    status="low",
                )
            ],
        ),
    ])

    assert result.balanced_pct == 33
    assert result.total_days == 3


def test_period_spo2_empty_readings_return_nulls_and_zero_counts():
    result = compute_period_spo2([])
    assert result.avg is None
    assert result.lowest_min is None
    assert result.low_days == 0
    assert result.total_days == 0


def test_period_spo2_low_threshold_and_lowest_min_use_daily_mins():
    result = compute_period_spo2([
        _day("2026-01-01", spo2=[95, 89]),
        _day("2026-01-02", spo2=[90, 92]),
    ])
    assert result.avg == 91.5
    assert result.lowest_min == 89.0
    assert result.low_days == 1
    assert result.total_days == 2


def test_period_skin_temp_empty_records_return_nulls_and_zero_days():
    result = compute_period_skin_temp([])
    assert result.avg_deviation is None
    assert result.max_deviation is None
    assert result.min_deviation is None
    assert result.avg_nightly is None
    assert result.days_tracked == 0


def test_period_skin_temp_excludes_null_deviations_and_averages_nightly_values():
    result = compute_period_skin_temp([
        _day(
            "2026-01-01",
            skin_temp=[
                SkinTempOvernight(
                    date="2026-01-01",
                    average_deviation=-0.234,
                    nightly_value=36.4,
                ),
            ],
        ),
        _day(
            "2026-01-02",
            skin_temp=[
                SkinTempOvernight(
                    date="2026-01-02",
                    average_deviation=None,
                    nightly_value=36.8,
                ),
            ],
        ),
    ])
    assert result.avg_deviation == -0.2
    assert result.min_deviation == -0.23
    assert result.max_deviation == -0.23
    assert result.avg_nightly == 36.6
    assert result.days_tracked == 1


def test_period_sleep_empty_assessments_return_nulls_and_zero_days():
    result = compute_period_sleep([])
    assert result.avg_score is None
    assert result.avg_deep_score is None
    assert result.days_tracked == 0


def test_period_sleep_excludes_null_overall_and_deep_scores_independently():
    result = compute_period_sleep([
        _day(
            "2026-01-01",
            sleep=[
                SleepAssessment(
                    date="2026-01-01",
                    overall_score=80,
                    deep_sleep_score=None,
                ),
            ],
        ),
        _day(
            "2026-01-02",
            sleep=[
                SleepAssessment(
                    date="2026-01-02",
                    overall_score=None,
                    deep_sleep_score=70,
                ),
            ],
        ),
    ])
    assert result.avg_score == 80.0
    assert result.avg_deep_score == 70.0
    assert result.days_tracked == 1


def test_period_body_battery_empty_readings_return_nulls_and_zero_days():
    result = compute_period_body_battery([])
    assert result.avg_min is None
    assert result.avg_max is None
    assert result.days_tracked == 0


def test_period_body_battery_averages_each_days_min_and_max():
    result = compute_period_body_battery([
        _day("2026-01-01", body_battery=[20, 80]),
        _day("2026-01-02", body_battery=[40, 60]),
    ])
    assert result.avg_min == 30.0
    assert result.avg_max == 70.0
    assert result.days_tracked == 2
