"""Display-only projections for recorded running-activity series.

Canonical FIT values remain unchanged in ``garmin_health`` contracts and storage.
This module only decides which values are meaningful on analytical charts and
derives corrected display elevation in the ``garmin_analytics`` read layer.
"""

import math
from collections.abc import Sequence
from typing import Protocol

import numpy as np

RESUME_SETTLE_SECONDS = 10
ELEVATION_WINDOW_M = 150.0
ELEVATION_HYSTERESIS_M = 3.0
CLOSED_LOOP_MAX_ENDPOINT_DISTANCE_M = 100.0
EARTH_RADIUS_M = 6_371_000.0


class RunWalkSpanView(Protocol):
    """Minimal span shape consumed by the analytics display policy."""

    @property
    def span_type(self) -> str: ...

    @property
    def start_s(self) -> float: ...

    @property
    def end_s(self) -> float: ...


def active_running_display_mask(
    elapsed_s: list[int], spans: Sequence[RunWalkSpanView]
) -> list[bool]:
    """Return chart-valid running positions, excluding start/resume transitions.

    FIT recording gaps represent paused time. Running-dynamics sensors need a
    short settling interval after recording starts or resumes; explicit walk and
    stand spans are also outside the meaning of a steady-running metric.
    """
    if not elapsed_s:
        return []

    transition_starts = [elapsed_s[0]]
    transition_starts.extend(
        current
        for previous, current in zip(elapsed_s, elapsed_s[1:], strict=False)
        if current - previous > 1
    )
    non_run_spans = [span for span in spans if span.span_type != "run"]

    return [
        not any(
            start <= elapsed < start + RESUME_SETTLE_SECONDS
            for start in transition_starts
        )
        and not any(
            span.start_s <= elapsed <= span.end_s for span in non_run_spans
        )
        for elapsed in elapsed_s
    ]


def apply_display_mask[T](
    values: list[T | None], mask: list[bool]
) -> list[T | None]:
    """Apply a positional chart mask without mutating the canonical source array."""
    if not values:
        return []
    if len(values) != len(mask):
        return [None] * len(mask)
    return [value if keep else None for value, keep in zip(values, mask, strict=True)]


def _elevation_segments(
    distance_m: list[float | None], altitude_m: list[float | None]
) -> list[list[int]]:
    segments: list[list[int]] = []
    current: list[int] = []
    previous_distance: float | None = None
    for index, (distance, altitude) in enumerate(
        zip(distance_m, altitude_m, strict=True)
    ):
        if (
            distance is not None
            and altitude is not None
            and math.isfinite(distance)
            and math.isfinite(altitude)
        ):
            if previous_distance is not None and distance < previous_distance:
                if current:
                    segments.append(current)
                current = []
            current.append(index)
            previous_distance = distance
        else:
            if current:
                segments.append(current)
                current = []
            previous_distance = None
    if current:
        segments.append(current)
    return segments


def smooth_elevation_by_distance(
    distance_m: list[float | None], altitude_m: list[float | None]
) -> list[float | None] | None:
    """Median-smooth altitude in a centered 150 m window without crossing gaps."""
    if not distance_m or len(distance_m) != len(altitude_m):
        return None

    result: list[float | None] = [None] * len(distance_m)
    half_window = ELEVATION_WINDOW_M / 2
    for segment in _elevation_segments(distance_m, altitude_m):
        distances = np.array([distance_m[index] for index in segment], dtype=float)
        altitudes = np.array([altitude_m[index] for index in segment], dtype=float)
        left = 0
        right = 0
        for position, index in enumerate(segment):
            center = distances[position]
            while left < position and distances[left] < center - half_window:
                left += 1
            if right < position:
                right = position
            while (
                right + 1 < len(segment)
                and distances[right + 1] <= center + half_window
            ):
                right += 1
            result[index] = float(np.median(altitudes[left : right + 1]))
    return result


def _segment_gain_loss(
    values: list[float], threshold_m: float
) -> tuple[float, float]:
    anchor = values[0]
    extreme = anchor
    direction = 0
    gain = 0.0
    loss = 0.0

    for value in values[1:]:
        if direction == 0:
            if value - anchor >= threshold_m:
                direction = 1
                extreme = value
            elif anchor - value >= threshold_m:
                direction = -1
                extreme = value
            continue
        if direction > 0:
            if value > extreme:
                extreme = value
            elif extreme - value >= threshold_m:
                gain += extreme - anchor
                anchor = extreme
                extreme = value
                direction = -1
            continue
        if value < extreme:
            extreme = value
        elif value - extreme >= threshold_m:
            loss += anchor - extreme
            anchor = extreme
            extreme = value
            direction = 1

    if direction > 0:
        gain += extreme - anchor
    elif direction < 0:
        loss += anchor - extreme
    return gain, loss


def elevation_gain_loss_m(
    altitude_m: list[float | None], threshold_m: float = ELEVATION_HYSTERESIS_M
) -> tuple[float, float]:
    """Accumulate only excursions meeting the threshold, independently per gap."""
    gain = 0.0
    loss = 0.0
    segment: list[float] = []
    for altitude in [*altitude_m, None]:
        if altitude is not None and math.isfinite(altitude):
            segment.append(altitude)
            continue
        if segment:
            segment_gain, segment_loss = _segment_gain_loss(segment, threshold_m)
            gain += segment_gain
            loss += segment_loss
            segment = []
    return gain, loss


def _endpoint_distance_m(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> float:
    start_lat_rad = math.radians(start_lat)
    end_lat_rad = math.radians(end_lat)
    lat_delta = math.radians(end_lat - start_lat)
    lon_delta = math.radians(end_lon - start_lon)
    haversine = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(start_lat_rad)
        * math.cos(end_lat_rad)
        * math.sin(lon_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(haversine))


def detrend_closed_loop_elevation(
    distance_m: list[float | None],
    altitude_m: list[float | None],
    *,
    start_lat: float | None,
    start_lon: float | None,
    end_lat: float | None,
    end_lon: float | None,
) -> list[float | None]:
    """Remove linear barometric drift only when GPS identifies a closed loop."""
    coordinates = (start_lat, start_lon, end_lat, end_lon)
    if (
        not distance_m
        or len(distance_m) != len(altitude_m)
        or any(value is None or not math.isfinite(value) for value in coordinates)
    ):
        return altitude_m.copy()
    assert start_lat is not None
    assert start_lon is not None
    assert end_lat is not None
    assert end_lon is not None
    if (
        _endpoint_distance_m(start_lat, start_lon, end_lat, end_lon)
        > CLOSED_LOOP_MAX_ENDPOINT_DISTANCE_M
    ):
        return altitude_m.copy()

    valid = [
        index
        for index, (distance, altitude) in enumerate(
            zip(distance_m, altitude_m, strict=True)
        )
        if distance is not None
        and altitude is not None
        and math.isfinite(distance)
        and math.isfinite(altitude)
    ]
    if len(valid) < 2:
        return altitude_m.copy()
    first = valid[0]
    last = valid[-1]
    first_distance = distance_m[first]
    last_distance = distance_m[last]
    first_altitude = altitude_m[first]
    last_altitude = altitude_m[last]
    assert first_distance is not None
    assert last_distance is not None
    assert first_altitude is not None
    assert last_altitude is not None
    distance_span = last_distance - first_distance
    if distance_span <= 0:
        return altitude_m.copy()
    drift = last_altitude - first_altitude

    return [
        None
        if distance is None or altitude is None
        else altitude - drift * (distance - first_distance) / distance_span
        for distance, altitude in zip(distance_m, altitude_m, strict=True)
    ]
