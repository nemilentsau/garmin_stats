"""Running-activity contracts: session, laps, zones, and record series.

Owns the shapes produced by the running-activity FIT parser
(``infra/fit_parser/activities.py``) and persisted verbatim by garmin_sync.
Deliberately separate from the day-grain wellness contracts in ``readings.py``:
activities are session-grain (zero-to-many per local date) and never feed
``DailyMetric``. All units are canonical backend units per the design spec
(m, s, m/s, bpm, W, spm, mm, ms, %, °C); the frontend receives display-ready
values and derives nothing.
"""

from app.contracts.base import DefaultsRequired


class RunningTimeInZones(DefaultsRequired):
    """Session-scope HR/power zone times and boundaries.

    Zone arrays may contain None to represent missing zone boundaries
    (preserving index alignment); only trailing Nones are stripped by the parser.
    """

    time_in_hr_zone_s: list[float | None] = []
    hr_zone_high_boundary_bpm: list[int | None] = []
    time_in_power_zone_s: list[float | None] = []
    power_zone_high_boundary_w: list[int | None] = []
    functional_threshold_power_w: int | None = None
    threshold_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None


class RunningActivitySession(DefaultsRequired):
    """One tracked run: FIT session summary merged with the Connect sidecar."""

    id: str
    activity_id: str | None = None
    source_file: str
    session_date: str
    start_time_local: str
    utc_offset_hours: float | None = None

    sport: str = "running"
    sub_sport: str | None = None
    sport_profile_name: str | None = None
    activity_name: str | None = None
    location_name: str | None = None

    elapsed_time_s: float | None = None
    timer_time_s: float | None = None
    moving_time_s: float | None = None

    distance_m: float | None = None
    pace_min_per_km: float | None = None
    avg_speed_mps: float | None = None
    max_speed_mps: float | None = None
    grade_adjusted_avg_speed_mps: float | None = None

    total_ascent_m: int | None = None
    total_descent_m: int | None = None

    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    hr_source: str | None = None  # "strap" | "wrist" | None
    hr_strap_serial: str | None = None
    hr_strap_battery: str | None = None

    avg_power_w: int | None = None
    max_power_w: int | None = None
    normalized_power_w: int | None = None
    total_work_j: int | None = None

    avg_cadence_spm: float | None = None
    max_cadence_spm: float | None = None
    avg_step_length_mm: float | None = None
    avg_vertical_oscillation_mm: float | None = None
    avg_vertical_ratio_pct: float | None = None
    avg_ground_contact_time_ms: float | None = None
    avg_ground_contact_balance_pct: float | None = None
    avg_stance_time_pct: float | None = None
    avg_respiration_rate_brpm: float | None = None
    max_respiration_rate_brpm: float | None = None
    min_respiration_rate_brpm: float | None = None

    # Firstbeat stamina (Connect Stats-panel "Stamina" group): begin/end read off
    # stamina-potential (the ceiling), min reads off stamina itself (the dip). Derived
    # at parse time from the record series — see parse_running_activity's post-fill.
    stamina_beginning_potential_pct: int | None = None
    stamina_ending_potential_pct: int | None = None
    stamina_min_pct: int | None = None

    avg_temperature_c: float | None = None
    min_temperature_c: float | None = None
    max_temperature_c: float | None = None

    total_calories: int | None = None
    total_strides: int | None = None
    steps: int | None = None
    aerobic_training_effect: float | None = None
    anaerobic_training_effect: float | None = None
    aerobic_te_message: str | None = None
    anaerobic_te_message: str | None = None
    training_effect_label: str | None = None
    training_load: float | None = None
    vo2max: float | None = None
    body_battery_delta: int | None = None
    moderate_intensity_minutes: int | None = None
    vigorous_intensity_minutes: int | None = None

    start_lat: float | None = None
    start_lon: float | None = None
    end_lat: float | None = None
    end_lon: float | None = None

    time_in_zones: RunningTimeInZones | None = None

    lap_count: int = 0
    record_count: int = 0
    has_heart_rate: bool = False
    has_power: bool = False
    has_running_dynamics: bool = False
    has_strap_dynamics: bool = False
    has_gps_trace: bool = False


class RunningActivityLap(DefaultsRequired):
    """One lap of a run; ``start_s`` is the offset from session start."""

    lap_index: int
    start_s: float | None = None
    timer_time_s: float | None = None
    elapsed_time_s: float | None = None
    distance_m: float | None = None
    pace_min_per_km: float | None = None
    avg_speed_mps: float | None = None
    max_speed_mps: float | None = None
    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    avg_power_w: int | None = None
    max_power_w: int | None = None
    normalized_power_w: int | None = None
    avg_cadence_spm: float | None = None
    max_cadence_spm: float | None = None
    avg_step_length_mm: float | None = None
    avg_vertical_oscillation_mm: float | None = None
    avg_vertical_ratio_pct: float | None = None
    avg_ground_contact_time_ms: float | None = None
    avg_ground_contact_balance_pct: float | None = None
    avg_stance_time_pct: float | None = None
    avg_respiration_rate_brpm: float | None = None
    max_respiration_rate_brpm: float | None = None
    total_ascent_m: int | None = None
    total_descent_m: int | None = None
    total_calories: int | None = None
    intensity: str | None = None
    lap_trigger: str | None = None


class RunWalkSpan(DefaultsRequired):
    """Run/walk/stand detection span, offsets from session start."""

    span_type: str  # "run" | "walk" | "stand"
    start_s: float
    end_s: float


class RunningActivitySeries(DefaultsRequired):
    """Per-second record stream as parallel column arrays (nulls positional)."""

    elapsed_s: list[int] = []
    distance_m: list[float | None] = []
    speed_mps: list[float | None] = []
    altitude_m: list[float | None] = []
    heart_rate_bpm: list[int | None] = []
    cadence_spm: list[float | None] = []
    power_w: list[int | None] = []
    step_length_mm: list[float | None] = []
    vertical_oscillation_mm: list[float | None] = []
    vertical_ratio_pct: list[float | None] = []
    stance_time_ms: list[float | None] = []
    stance_time_balance_pct: list[float | None] = []
    respiration_rate_brpm: list[float | None] = []
    stance_time_pct: list[float | None] = []
    stamina_pct: list[int | None] = []
    stamina_potential_pct: list[int | None] = []
    performance_condition: list[int | None] = []
    temperature_c: list[float | None] = []
    lat: list[float | None] = []
    lon: list[float | None] = []
    run_walk_spans: list[RunWalkSpan] = []


class RunningActivityData(DefaultsRequired):
    """Full parse result for one running FIT file."""

    session: RunningActivitySession
    laps: list[RunningActivityLap] = []
    series: RunningActivitySeries
