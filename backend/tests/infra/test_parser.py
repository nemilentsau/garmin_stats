"""Tests for parser extractor edge cases."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domains.garmin_health.contracts import (
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvValue,
    SkinTempOvernight,
    SleepLevel,
)
from app.domains.garmin_health.infra.fit_parser.days import _parse_day, parse_day
from app.domains.garmin_health.infra.fit_parser.extractors import (
    _extract_hrv,
    _extract_wellness,
)
from app.domains.garmin_health.infra.fit_parser.files import get_files_by_day
from app.domains.garmin_health.infra.fit_parser.timestamps import (
    _GARMIN_EPOCH_UNIX,
    UtcOffsetTimeline,
    _extract_utc_offset_breakpoints,
    _shift_overnight_to_local,
)


class TestExtractorZeroValues:
    def test_wellness_filters_zero_heart_rate_keeps_zero_steps_and_spo2(self):
        messages = {
            "monitoring_mesgs": [
                {"heart_rate": 0, "steps": 0},
            ],
            "spo2_data_mesgs": [
                {"reading_spo2": 0, "mode": "sleep"},
            ],
        }

        day = _extract_wellness(messages, "2026-01-15")
        assert [r.value for r in day.heart_rate] == []
        assert [r.steps for r in day.steps_summary] == [0]
        assert [r.value for r in day.spo2] == [0]

    def test_hrv_keeps_zero_value(self):
        messages = {
            "hrv_value_mesgs": [
                {"value": 0},
            ],
        }
        day = _extract_hrv(messages, "2026-01-15")
        assert [r.value for r in day.hrv_values] == [0]


class TestParseDayMerge:
    def test_extends_configured_list_fields_in_sorted_file_order(self, monkeypatch, tmp_path: Path):
        first = tmp_path / "b.fit"
        second = tmp_path / "a.fit"
        first.write_text("", encoding="ascii")
        second.write_text("", encoding="ascii")
        decoded_paths: list[Path] = []

        def decode(file_path: Path) -> dict[str, list[dict]]:
            decoded_paths.append(file_path)
            return {"source": [{"path": file_path.name}]}

        def extract(messages: dict, date: str) -> DaySleep:
            return DaySleep(
                date=date,
                sleep_levels=[
                    SleepLevel(date=date, timestamp=None, level=messages["source"][0]["path"]),
                ],
            )

        monkeypatch.setattr(
            "app.domains.garmin_health.infra.fit_parser.days.decode_fit_file",
            decode,
        )

        day = _parse_day(
            [first, second],
            "2026-01-15",
            empty=DaySleep,
            extractor=extract,
            list_fields=("sleep_levels",),
        )

        assert decoded_paths == [second, first]
        assert [level.level for level in day.sleep_levels] == ["a.fit", "b.fit"]

    def test_skips_failed_files_and_keeps_merging_later_files(self, monkeypatch, tmp_path: Path):
        bad = tmp_path / "a.fit"
        good = tmp_path / "b.fit"
        bad.write_text("", encoding="ascii")
        good.write_text("", encoding="ascii")

        def decode(file_path: Path) -> dict[str, list[dict]]:
            if file_path == bad:
                raise ValueError("corrupt")
            return {"source": [{"path": file_path.name}]}

        def extract(messages: dict, date: str) -> DayHrv:
            return DayHrv(
                date=date,
                hrv_values=[
                    HrvValue(date=date, timestamp=None, value=len(messages["source"][0]["path"])),
                ],
            )

        monkeypatch.setattr(
            "app.domains.garmin_health.infra.fit_parser.days.decode_fit_file",
            decode,
        )

        day = _parse_day(
            [bad, good],
            "2026-01-15",
            empty=DayHrv,
            extractor=extract,
            list_fields=("hrv_values",),
        )

        assert [value.value for value in day.hrv_values] == [5]


# ---------------------------------------------------------------------------
# UTC offset extraction
# ---------------------------------------------------------------------------

def _make_monitoring_info(utc_dt: datetime, offset_hours: float) -> dict:
    """Build a monitoring_info_mesgs entry with a known UTC/local pair."""
    local_unix = utc_dt.timestamp() + offset_hours * 3600
    local_garmin = int(local_unix) - _GARMIN_EPOCH_UNIX
    return {"timestamp": utc_dt, "local_timestamp": local_garmin}


class TestExtractUtcOffsetBreakpoints:
    def test_positive_offset_extracted(self):
        """NZ +13 offset is correctly extracted."""
        utc = datetime(2026, 1, 15, 3, 0, 0, tzinfo=UTC)
        messages = {"monitoring_info_mesgs": [_make_monitoring_info(utc, 13.0)]}
        assert _extract_utc_offset_breakpoints(messages) == [(utc, 13.0)]

    def test_negative_offset_extracted(self):
        """NYC -5 offset is correctly extracted."""
        utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        messages = {"monitoring_info_mesgs": [_make_monitoring_info(utc, -5.0)]}
        assert _extract_utc_offset_breakpoints(messages) == [(utc, -5.0)]

    def test_every_monitoring_info_becomes_a_breakpoint(self):
        """One file can span an offset change, so all of its infos are kept."""
        before = datetime(2026, 3, 8, 15, 6, 0, tzinfo=UTC)
        after = datetime(2026, 3, 8, 15, 49, 0, tzinfo=UTC)
        messages = {
            "monitoring_info_mesgs": [
                _make_monitoring_info(before, -5.0),
                _make_monitoring_info(after, -4.0),
            ]
        }
        assert _extract_utc_offset_breakpoints(messages) == [(before, -5.0), (after, -4.0)]

    def test_incomplete_monitoring_info_is_ignored(self):
        utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        messages = {
            "monitoring_info_mesgs": [
                {"timestamp": utc, "local_timestamp": None},
                {"timestamp": None, "local_timestamp": 1130343473},
                {"timestamp": "not-a-datetime", "local_timestamp": 1130343473},
            ]
        }
        assert _extract_utc_offset_breakpoints(messages) == []

    def test_returns_empty_when_no_monitoring_info(self):
        messages: dict[str, list[dict[str, object]]] = {"monitoring_info_mesgs": []}
        assert _extract_utc_offset_breakpoints(messages) == []

    def test_returns_empty_when_key_missing(self):
        assert _extract_utc_offset_breakpoints({}) == []


class TestUtcOffsetTimeline:
    """Offset resolution across a span that changes offset partway through."""

    EARLY = datetime(2026, 3, 8, 10, 0, 0, tzinfo=UTC)
    LATE = datetime(2026, 3, 8, 15, 49, 0, tzinfo=UTC)

    def _timeline(self) -> UtcOffsetTimeline:
        return UtcOffsetTimeline([(self.LATE, -4.0), (self.EARLY, -5.0)])

    def test_moment_before_first_breakpoint_uses_earliest_offset(self):
        assert self._timeline().offset_at(self.EARLY - timedelta(hours=1)) == -5.0

    def test_moment_between_breakpoints_uses_earlier_offset(self):
        assert self._timeline().offset_at(self.LATE - timedelta(seconds=1)) == -5.0

    def test_moment_exactly_at_breakpoint_uses_new_offset(self):
        assert self._timeline().offset_at(self.LATE) == -4.0

    def test_moment_after_last_breakpoint_uses_last_offset(self):
        assert self._timeline().offset_at(self.LATE + timedelta(hours=6)) == -4.0

    def test_final_offset_is_the_chronologically_last_offset(self):
        assert self._timeline().final_offset == -4.0

    def test_empty_timeline_resolves_to_none(self):
        empty = UtcOffsetTimeline([])
        assert empty.offset_at(self.EARLY) is None
        assert empty.final_offset is None
        assert not empty


# ---------------------------------------------------------------------------
# Timestamp shifting
# ---------------------------------------------------------------------------

def _overnight_day(ts: str | None) -> DayData:
    """A DayData whose sleep/hrv/skin-temp readings share one UTC timestamp."""
    return DayData(
        date="2026-01-15",
        wellness=DayWellness(
            date="2026-01-15",
            heart_rate=[HeartRateReading(timestamp=ts, value=70)],
        ),
        sleep=DaySleep(
            date="2026-01-15",
            sleep_levels=[SleepLevel(date="2026-01-15", timestamp=ts, level="deep")],
        ),
        hrv=DayHrv(
            date="2026-01-15",
            hrv_values=[HrvValue(date="2026-01-15", timestamp=ts, value=50.0)],
        ),
        skin_temp=DaySkinTemp(
            date="2026-01-15",
            skin_temp_overnight=[SkinTempOvernight(date="2026-01-15", timestamp=ts)],
        ),
    )


class TestShiftOvernightReadings:
    def test_shifts_sleep_hrv_and_skin_temp_but_not_wellness(self):
        """Wellness is already shifted per source file, so this pass must skip it."""
        ts = "2026-01-15T00:00:00+00:00"
        day = _overnight_day(ts)
        timeline = UtcOffsetTimeline([(datetime(2026, 1, 14, tzinfo=UTC), 13.0)])

        _shift_overnight_to_local(day, timeline)

        expected = "2026-01-15T13:00:00"
        assert day.sleep.sleep_levels[0].timestamp == expected
        assert day.hrv.hrv_values[0].timestamp == expected
        assert day.skin_temp.skin_temp_overnight[0].timestamp == expected
        assert day.wellness.heart_rate[0].timestamp == ts

    def test_negative_offset_shifts_backwards(self):
        day = _overnight_day("2026-01-15T03:00:00+00:00")
        timeline = UtcOffsetTimeline([(datetime(2026, 1, 14, tzinfo=UTC), -5.0)])

        _shift_overnight_to_local(day, timeline)

        assert day.sleep.sleep_levels[0].timestamp == "2026-01-14T22:00:00"

    def test_readings_resolve_against_their_own_instant(self):
        """An overnight reading after the change carries the post-change offset."""
        day = DayData(
            date="2026-03-08",
            wellness=DayWellness(date="2026-03-08"),
            sleep=DaySleep(
                date="2026-03-08",
                sleep_levels=[
                    SleepLevel(
                        date="2026-03-08", timestamp="2026-03-08T06:00:00+00:00", level="deep"
                    ),
                    SleepLevel(
                        date="2026-03-08", timestamp="2026-03-08T20:00:00+00:00", level="awake"
                    ),
                ],
            ),
            hrv=DayHrv(date="2026-03-08"),
            skin_temp=DaySkinTemp(date="2026-03-08"),
        )
        timeline = UtcOffsetTimeline([
            (datetime(2026, 3, 8, 5, 0, tzinfo=UTC), -5.0),
            (datetime(2026, 3, 8, 15, 49, tzinfo=UTC), -4.0),
        ])

        _shift_overnight_to_local(day, timeline)

        assert [level.timestamp for level in day.sleep.sleep_levels] == [
            "2026-03-08T01:00:00",
            "2026-03-08T16:00:00",
        ]

    def test_none_timestamps_preserved(self):
        day = _overnight_day(None)
        timeline = UtcOffsetTimeline([(datetime(2026, 1, 14, tzinfo=UTC), 5.0)])

        _shift_overnight_to_local(day, timeline)

        assert day.sleep.sleep_levels[0].timestamp is None

    def test_empty_timeline_leaves_timestamps_untouched(self):
        ts = "2026-01-15T03:00:00+00:00"
        day = _overnight_day(ts)

        _shift_overnight_to_local(day, UtcOffsetTimeline([]))

        assert day.sleep.sleep_levels[0].timestamp == ts


def _wellness_messages(
    readings: list[tuple[datetime, int]],
    infos: list[tuple[datetime, float]],
) -> dict:
    """Decoded-WELLNESS shape: HR readings plus monitoring_info offset markers."""
    return {
        "monitoring_mesgs": [
            {"timestamp": utc, "heart_rate": value} for utc, value in readings
        ],
        "monitoring_info_mesgs": [_make_monitoring_info(utc, off) for utc, off in infos],
    }


class TestWellnessDayLocalTime:
    """Each WELLNESS file is shifted with the offsets it declares itself.

    Real days do change offset partway through — DST rollover and travel — and
    a single file can straddle the change, so a day cannot be reduced to one
    offset without misplacing readings by whole hours.
    """

    DATE = "2026-03-08"

    def _parse(self, monkeypatch, tmp_path: Path, files: dict[str, dict]) -> DayData:
        paths = []
        for name in files:
            path = tmp_path / name
            path.write_text("", encoding="ascii")
            paths.append(path)
        monkeypatch.setattr(
            "app.domains.garmin_health.infra.fit_parser.days.decode_fit_file",
            lambda path: files[path.name],
        )
        return parse_day(self.DATE, {"WELLNESS": paths})

    def test_each_file_shifts_with_its_own_offset(self, monkeypatch, tmp_path: Path):
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 12, 0, tzinfo=UTC), 60)],
                [(datetime(2026, 3, 8, 5, 0, tzinfo=UTC), -5.0)],
            ),
            "b_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 23, 30, tzinfo=UTC), 61)],
                [(datetime(2026, 3, 8, 23, 6, tzinfo=UTC), -4.0)],
            ),
        })

        assert [r.timestamp for r in day.wellness.heart_rate] == [
            "2026-03-08T07:00:00",
            "2026-03-08T19:30:00",
        ]

    def test_day_offset_is_the_one_in_effect_at_the_end_of_the_day(
        self, monkeypatch, tmp_path: Path
    ):
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [], [(datetime(2026, 3, 8, 5, 0, tzinfo=UTC), -5.0)]
            ),
            "b_WELLNESS.fit": _wellness_messages(
                [], [(datetime(2026, 3, 8, 23, 6, tzinfo=UTC), -4.0)]
            ),
        })

        assert day.utc_offset_hours == -4.0

    def test_offset_change_inside_one_file_splits_that_files_readings(
        self, monkeypatch, tmp_path: Path
    ):
        """The real 2026-03-08 archive changes offset mid-file at 15:49 UTC."""
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [
                    (datetime(2026, 3, 8, 15, 10, tzinfo=UTC), 60),
                    (datetime(2026, 3, 8, 16, 0, tzinfo=UTC), 61),
                ],
                [
                    (datetime(2026, 3, 8, 15, 6, tzinfo=UTC), -5.0),
                    (datetime(2026, 3, 8, 15, 49, tzinfo=UTC), -4.0),
                ],
            ),
        })

        assert [r.timestamp for r in day.wellness.heart_rate] == [
            "2026-03-08T10:10:00",
            "2026-03-08T12:00:00",
        ]

    def test_overlapping_files_that_disagree_each_keep_their_own_offset(
        self, monkeypatch, tmp_path: Path
    ):
        """Two same-span files with different offsets must not cross-contaminate."""
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 6, 29, 23, 0, tzinfo=UTC), 60)],
                [(datetime(2026, 6, 29, 20, 25, tzinfo=UTC), -4.0)],
            ),
            "b_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 6, 29, 23, 0, tzinfo=UTC), 61)],
                [(datetime(2026, 6, 29, 22, 35, tzinfo=UTC), -5.0)],
            ),
        })

        assert [r.timestamp for r in day.wellness.heart_rate] == [
            "2026-06-29T19:00:00",
            "2026-06-29T18:00:00",
        ]

    def test_file_without_monitoring_info_falls_back_to_the_day_offset(
        self, monkeypatch, tmp_path: Path
    ):
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [], [(datetime(2026, 3, 8, 5, 0, tzinfo=UTC), -5.0)]
            ),
            "b_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 20, 0, tzinfo=UTC), 60)], []
            ),
        })

        assert [r.timestamp for r in day.wellness.heart_rate] == ["2026-03-08T15:00:00"]

    def test_uniform_day_shifts_every_reading_by_the_same_offset(
        self, monkeypatch, tmp_path: Path
    ):
        """The common case: all files agree, so nothing about the day changes."""
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 6, 0, tzinfo=UTC), 60)],
                [(datetime(2026, 3, 8, 5, 0, tzinfo=UTC), -5.0)],
            ),
            "b_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 22, 0, tzinfo=UTC), 61)],
                [(datetime(2026, 3, 8, 15, 0, tzinfo=UTC), -5.0)],
            ),
        })

        assert [r.timestamp for r in day.wellness.heart_rate] == [
            "2026-03-08T01:00:00",
            "2026-03-08T17:00:00",
        ]
        assert day.utc_offset_hours == -5.0

    def test_day_without_any_monitoring_info_keeps_utc_timestamps(
        self, monkeypatch, tmp_path: Path
    ):
        day = self._parse(monkeypatch, tmp_path, {
            "a_WELLNESS.fit": _wellness_messages(
                [(datetime(2026, 3, 8, 6, 0, tzinfo=UTC), 60)], []
            ),
        })

        assert day.utc_offset_hours is None
        assert [r.timestamp for r in day.wellness.heart_rate] == [
            "2026-03-08T06:00:00+00:00"
        ]


class TestDayDirectoryDiscovery:
    def test_files_by_day_ignores_fit_files_under_noncanonical_top_level_dirs(self, tmp_path: Path):
        canonical_fit = tmp_path / "2026-03-01" / "001_WELLNESS.fit"
        canonical_fit.parent.mkdir(parents=True)
        canonical_fit.write_text("ok", encoding="ascii")

        duplicate_fit = tmp_path / "2026-03-01 copy" / "001_WELLNESS.fit"
        duplicate_fit.parent.mkdir(parents=True)
        duplicate_fit.write_text("ignore", encoding="ascii")

        malformed_fit = tmp_path / "2026-13-01" / "001_WELLNESS.fit"
        malformed_fit.parent.mkdir(parents=True)
        malformed_fit.write_text("ignore", encoding="ascii")

        files_by_day = get_files_by_day(tmp_path)

        assert list(files_by_day) == ["2026-03-01"]
        assert files_by_day["2026-03-01"]["WELLNESS"] == [canonical_fit]
