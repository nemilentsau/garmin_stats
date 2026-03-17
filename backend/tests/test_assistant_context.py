"""Tests for assistant context snapshots."""

import app.services.assistant_context as context_mod
from app.models import (
    DailyBodyBatteryStats,
    DailyCheckIn,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    Experiment,
    Note,
    RoutineSchedule,
    UserProfile,
)


def _make_daily_metric(date: str) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(resting=49),
        stress=DailyMetricStats(avg=21.0),
        body_battery=DailyBodyBatteryStats(min=32, max=82),
        spo2=DailyMetricStats(avg=97.0),
        respiration=DailyMetricStats(avg=13.8),
        hrv=DailyHrvStats(nightly_avg=61.0, status="balanced"),
        sleep=DailySleepStats(score=84),
        skin_temp=DailySkinTempStats(deviation=0.2),
    )


class TestBuildContextSnapshot:
    def test_includes_profile_and_recent_health_context(self, monkeypatch):
        saved_snapshots = []

        monkeypatch.setattr(
            context_mod,
            "load_daily_metrics",
            lambda: [_make_daily_metric("2026-03-10")],
        )
        monkeypatch.setattr(
            context_mod,
            "load_user_profile",
            lambda: UserProfile(name="Andrei", primary_goals=["recovery"]),
        )
        monkeypatch.setattr(
            context_mod,
            "load_routine_schedules",
            lambda status=None: [
                RoutineSchedule(
                    id="routine-1",
                    name="Meditation",
                    status="active",
                    cadence="weekly",
                    start_date="2026-03-01",
                ),
            ],
        )
        monkeypatch.setattr(
            context_mod,
            "load_experiments",
            lambda: [
                Experiment(id="exp-1", name="Meditation", status="active"),
                Experiment(id="exp-2", name="Cold shower", status="completed"),
            ],
        )
        monkeypatch.setattr(
            context_mod,
            "load_daily_checkins",
            lambda **_kw: [DailyCheckIn(id="checkin-1", date="2026-03-10", energy=4)],
        )
        monkeypatch.setattr(
            context_mod,
            "load_notes",
            lambda **_kw: [
                Note(
                    id="note-1",
                    date="2026-03-10",
                    category="reflection",
                    title="Travel",
                    content="Late dinner.",
                )
            ],
        )
        monkeypatch.setattr(context_mod, "load_dashboard_overview", lambda: None)
        monkeypatch.setattr(context_mod, "save_context_snapshot", saved_snapshots.append)

        snapshot = context_mod.build_context_snapshot()
        active_routines = snapshot.snapshot_json["active_routines"]
        active_experiments = snapshot.snapshot_json["active_experiments"]

        assert snapshot.snapshot_json["profile"] == {
            "id": "default",
            "name": "Andrei",
            "birth_year": None,
            "age_range": None,
            "sex": None,
            "height_cm": None,
            "weight_kg": None,
            "primary_goals": ["recovery"],
            "constraints": [],
            "injuries": [],
            "equipment": [],
            "default_weekly_schedule": [],
            "sleep_constraints": [],
            "nutrition_preferences": [],
            "coaching_style_preferences": [],
        }
        assert isinstance(active_routines, list)
        assert isinstance(active_experiments, list)
        assert len(active_routines) == 1
        assert active_routines[0]["cadence"] == "weekly"
        assert len(active_experiments) == 1
        assert snapshot.created_at is not None
        assert saved_snapshots[0].id == snapshot.id

    def test_falls_back_when_dashboard_overview_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(context_mod, "load_daily_metrics", lambda: [])
        monkeypatch.setattr(context_mod, "load_user_profile", lambda: None)
        monkeypatch.setattr(context_mod, "load_routine_schedules", lambda status=None: [])
        monkeypatch.setattr(context_mod, "load_experiments", lambda: [])
        monkeypatch.setattr(context_mod, "load_daily_checkins", lambda **_kw: [])
        monkeypatch.setattr(context_mod, "load_notes", lambda **_kw: [])
        monkeypatch.setattr(
            context_mod,
            "load_dashboard_overview",
            lambda: (_ for _ in ()).throw(LookupError("no overview")),
        )
        monkeypatch.setattr(context_mod, "save_context_snapshot", lambda _snapshot: None)

        snapshot = context_mod.build_context_snapshot()

        assert snapshot.snapshot_json["overview"] is None
        assert snapshot.date_window_end is None
