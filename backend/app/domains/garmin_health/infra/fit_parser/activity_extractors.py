"""Pure extraction of running-activity fields from decoded FIT messages.

Owns the field-level knowledge for activity FIT files (session, laps, zones,
records, run/walk splits, device info) and the unit policy: cadence is
``(value + fractional) * 2`` spm, positions are semicircles → degrees, pace is
derived from timer time and distance. Deliberately free of I/O and SDK types —
callers hand in the decoded message dict (see ``activities.py``), which keeps
every rule testable with synthetic dicts.
"""

from datetime import datetime, timedelta

from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
    RunningTimeInZones,
    RunWalkSpan,
)

_SEMICIRCLE_TO_DEG = 180 / 2**31
_SIDE_CAR_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _semicircles_to_deg(raw: int | None) -> float | None:
    return None if raw is None else round(raw * _SEMICIRCLE_TO_DEG, 7)


def _cadence_spm(value: float | None, fractional: float | None) -> float | None:
    """Cadence: (running cadence + fractional) × 2 to convert half-steps to steps per minute."""
    if value is None:
        return None
    return (value + (fractional or 0.0)) * 2


def _pace_min_per_km(timer_s: float | None, distance_m: float | None) -> float | None:
    """Pace: timer time / distance; returns min/km or None if timer or distance is zero/missing."""
    if not timer_s or not distance_m or distance_m <= 0:
        return None
    return round(timer_s / 60 / (distance_m / 1000), 2)


def _derive_utc_offset(sidecar: dict | None, messages: dict) -> float | None:
    """Per-activity UTC offset in hours; sidecar wins, FIT activity mesg is fallback."""
    if sidecar and sidecar.get("startTimeGMT") and sidecar.get("startTimeLocal"):
        gmt = datetime.strptime(sidecar["startTimeGMT"], _SIDE_CAR_TIME_FMT)
        local = datetime.strptime(sidecar["startTimeLocal"], _SIDE_CAR_TIME_FMT)
        return (local - gmt).total_seconds() / 3600
    for msg in messages.get("activity_mesgs", []):
        ts, local_ts = msg.get("timestamp"), msg.get("local_timestamp")
        if ts is not None and local_ts is not None:
            naive_ts = ts.replace(tzinfo=None)
            naive_local = local_ts.replace(tzinfo=None)
            return (naive_local - naive_ts).total_seconds() / 3600
    return None


def _detect_hr_source(messages: dict, has_hr: bool) -> tuple[str | None, str | None, str | None]:
    """Classify HR provenance: external strap beats wrist optical."""
    for msg in messages.get("device_info_mesgs", []):
        if msg.get("source_type") == "local":
            continue
        if "heart_rate" in (msg.get("ble_device_type"), msg.get("antplus_device_type")):
            serial = msg.get("serial_number")
            battery = msg.get("battery_status")
            return (
                "strap",
                str(serial) if serial is not None else None,
                str(battery) if battery is not None else None,
            )
    if has_hr:
        return ("wrist", None, None)
    return (None, None, None)


def _local_start(start_utc: datetime, offset_hours: float | None) -> datetime:
    """Convert UTC timestamp to local; if offset_hours is None, return UTC-naive timestamp."""
    naive = start_utc.replace(tzinfo=None)
    if offset_hours is None:
        return naive
    return naive + timedelta(hours=offset_hours)


def _extract_time_in_zones(messages: dict) -> RunningTimeInZones | None:
    """Extract session-scope zone data, stripping only trailing None padding.

    Garmin pads zone arrays with trailing Nones; non-trailing Nones are
    preserved to maintain zone index alignment (e.g., [316, 387, None, 483]
    means zone 2 has no high boundary but zone 3 does).
    """
    for msg in messages.get("time_in_zone_mesgs", []):
        if msg.get("reference_mesg") != "session":
            continue

        def _clean(values: list | None) -> list:
            trimmed = list(values or [])
            while trimmed and trimmed[-1] is None:
                trimmed.pop()
            return trimmed

        return RunningTimeInZones(
            time_in_hr_zone_s=_clean(msg.get("time_in_hr_zone")),
            hr_zone_high_boundary_bpm=_clean(msg.get("hr_zone_high_boundary")),
            time_in_power_zone_s=_clean(msg.get("time_in_power_zone")),
            power_zone_high_boundary_w=_clean(msg.get("power_zone_high_boundary")),
            functional_threshold_power_w=msg.get("functional_threshold_power"),
            threshold_heart_rate_bpm=msg.get("threshold_heart_rate"),
            max_heart_rate_bpm=msg.get("max_heart_rate"),
        )
    return None


def _extract_run_session(
    messages: dict, sidecar: dict | None, source_file: str
) -> RunningActivitySession:
    """Merge FIT session summary with the Connect sidecar into one contract row."""
    fit = (messages.get("session_mesgs") or [{}])[0]
    side = sidecar or {}
    offset = _derive_utc_offset(sidecar, messages)
    start_local = _local_start(fit["start_time"], offset)
    has_hr = fit.get("avg_heart_rate") is not None
    hr_source, strap_serial, strap_battery = _detect_hr_source(messages, has_hr)
    activity_id = str(side["activityId"]) if side.get("activityId") is not None else None
    stem = source_file.rsplit(".", 1)[0]
    body_battery = side.get("differenceBodyBattery")

    return RunningActivitySession(
        id=activity_id or f"file:{stem}",
        activity_id=activity_id,
        source_file=source_file,
        session_date=start_local.date().isoformat(),
        start_time_local=start_local.isoformat(),
        utc_offset_hours=offset,
        sport=fit.get("sport") or "running",
        sub_sport=fit.get("sub_sport"),
        sport_profile_name=fit.get("sport_profile_name"),
        activity_name=side.get("activityName"),
        location_name=side.get("locationName"),
        elapsed_time_s=fit.get("total_elapsed_time"),
        timer_time_s=fit.get("total_timer_time"),
        moving_time_s=side.get("movingDuration"),
        distance_m=fit.get("total_distance"),
        pace_min_per_km=_pace_min_per_km(fit.get("total_timer_time"), fit.get("total_distance")),
        avg_speed_mps=fit.get("enhanced_avg_speed"),
        max_speed_mps=fit.get("enhanced_max_speed"),
        grade_adjusted_avg_speed_mps=side.get("avgGradeAdjustedSpeed"),
        total_ascent_m=fit.get("total_ascent"),
        total_descent_m=fit.get("total_descent"),
        avg_heart_rate_bpm=fit.get("avg_heart_rate"),
        max_heart_rate_bpm=fit.get("max_heart_rate"),
        hr_source=hr_source,
        hr_strap_serial=strap_serial,
        hr_strap_battery=strap_battery,
        avg_power_w=fit.get("avg_power"),
        max_power_w=fit.get("max_power"),
        normalized_power_w=fit.get("normalized_power"),
        total_work_j=fit.get("total_work"),
        avg_cadence_spm=_cadence_spm(
            fit.get("avg_running_cadence"), fit.get("avg_fractional_cadence")
        ),
        max_cadence_spm=_cadence_spm(
            fit.get("max_running_cadence"), fit.get("max_fractional_cadence")
        ),
        avg_step_length_mm=fit.get("avg_step_length"),
        avg_vertical_oscillation_mm=fit.get("avg_vertical_oscillation"),
        avg_vertical_ratio_pct=fit.get("avg_vertical_ratio"),
        avg_ground_contact_time_ms=fit.get("avg_stance_time"),
        avg_temperature_c=fit.get("avg_temperature"),
        min_temperature_c=fit.get("min_temperature"),
        max_temperature_c=fit.get("max_temperature"),
        total_calories=fit.get("total_calories"),
        total_strides=fit.get("total_strides"),
        steps=side.get("steps"),
        aerobic_training_effect=fit.get("total_training_effect"),
        anaerobic_training_effect=fit.get("total_anaerobic_training_effect"),
        aerobic_te_message=side.get("aerobicTrainingEffectMessage"),
        anaerobic_te_message=side.get("anaerobicTrainingEffectMessage"),
        training_effect_label=side.get("trainingEffectLabel"),
        training_load=fit.get("training_load_peak"),
        vo2max=side.get("vO2MaxValue"),
        body_battery_delta=int(body_battery) if body_battery is not None else None,
        moderate_intensity_minutes=side.get("moderateIntensityMinutes"),
        vigorous_intensity_minutes=side.get("vigorousIntensityMinutes"),
        start_lat=_semicircles_to_deg(fit.get("start_position_lat")),
        start_lon=_semicircles_to_deg(fit.get("start_position_long")),
        end_lat=_semicircles_to_deg(fit.get("end_position_lat")),
        end_lon=_semicircles_to_deg(fit.get("end_position_long")),
        time_in_zones=_extract_time_in_zones(messages),
        has_heart_rate=has_hr,
        has_power=fit.get("avg_power") is not None,
        has_running_dynamics=fit.get("avg_stance_time") is not None,
    )


_RWD_SPAN_TYPES = {"rwd_run": "run", "rwd_walk": "walk", "rwd_stand": "stand"}


def _extract_run_laps(messages: dict) -> list[RunningActivityLap]:
    """Lap start_s: offset from session start_time (unlike series elapsed_s, which
    offsets from the first record); lap_index: message_index or enumerate."""
    session = (messages.get("session_mesgs") or [{}])[0]
    session_start = session.get("start_time")
    laps: list[RunningActivityLap] = []
    for i, msg in enumerate(messages.get("lap_mesgs", [])):
        start = msg.get("start_time")
        start_s = (
            (start - session_start).total_seconds()
            if start is not None and session_start is not None
            else None
        )
        avg_cadence = _cadence_spm(
            msg.get("avg_running_cadence"), msg.get("avg_fractional_cadence")
        )
        max_cadence = _cadence_spm(
            msg.get("max_running_cadence"), msg.get("max_fractional_cadence")
        )
        pace = _pace_min_per_km(
            msg.get("total_timer_time"), msg.get("total_distance")
        )
        laps.append(
            RunningActivityLap(
                lap_index=msg.get("message_index", i),
                start_s=start_s,
                timer_time_s=msg.get("total_timer_time"),
                elapsed_time_s=msg.get("total_elapsed_time"),
                distance_m=msg.get("total_distance"),
                pace_min_per_km=pace,
                avg_speed_mps=msg.get("enhanced_avg_speed"),
                max_speed_mps=msg.get("enhanced_max_speed"),
                avg_heart_rate_bpm=msg.get("avg_heart_rate"),
                max_heart_rate_bpm=msg.get("max_heart_rate"),
                avg_power_w=msg.get("avg_power"),
                max_power_w=msg.get("max_power"),
                normalized_power_w=msg.get("normalized_power"),
                avg_cadence_spm=avg_cadence,
                max_cadence_spm=max_cadence,
                avg_step_length_mm=msg.get("avg_step_length"),
                avg_vertical_oscillation_mm=msg.get("avg_vertical_oscillation"),
                avg_vertical_ratio_pct=msg.get("avg_vertical_ratio"),
                avg_ground_contact_time_ms=msg.get("avg_stance_time"),
                total_ascent_m=msg.get("total_ascent"),
                total_descent_m=msg.get("total_descent"),
                total_calories=msg.get("total_calories"),
                intensity=msg.get("intensity"),
                lap_trigger=msg.get("lap_trigger"),
            )
        )
    return laps


def _extract_run_series(messages: dict) -> RunningActivitySeries:
    """Parallel column arrays with positional nulls; spans offset from first record; rwd_* only."""
    records = messages.get("record_mesgs", [])
    series = RunningActivitySeries()
    if records:
        start_ts = records[0]["timestamp"]
        for msg in records:
            elapsed = int((msg["timestamp"] - start_ts).total_seconds())
            series.elapsed_s.append(elapsed)
            series.distance_m.append(msg.get("distance"))
            series.speed_mps.append(msg.get("enhanced_speed"))
            series.altitude_m.append(msg.get("enhanced_altitude"))
            series.heart_rate_bpm.append(msg.get("heart_rate"))
            cadence = _cadence_spm(
                msg.get("cadence"), msg.get("fractional_cadence")
            )
            series.cadence_spm.append(cadence)
            series.power_w.append(msg.get("power"))
            series.step_length_mm.append(msg.get("step_length"))
            series.vertical_oscillation_mm.append(msg.get("vertical_oscillation"))
            series.vertical_ratio_pct.append(msg.get("vertical_ratio"))
            series.stance_time_ms.append(msg.get("stance_time"))
            series.temperature_c.append(msg.get("temperature"))
            series.lat.append(_semicircles_to_deg(msg.get("position_lat")))
            series.lon.append(_semicircles_to_deg(msg.get("position_long")))
        for msg in messages.get("split_mesgs", []):
            span_type = _RWD_SPAN_TYPES.get(msg.get("split_type"))
            start_time = msg.get("start_time")
            end_time = msg.get("end_time")
            if span_type is None or start_time is None or end_time is None:
                continue
            series.run_walk_spans.append(
                RunWalkSpan(
                    span_type=span_type,
                    start_s=(start_time - start_ts).total_seconds(),
                    end_s=(end_time - start_ts).total_seconds(),
                )
            )
    return series
