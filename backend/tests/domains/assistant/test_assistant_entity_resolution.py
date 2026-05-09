"""Tests for deterministic assistant entity resolution."""

from app.core.profile.contracts import UserProfile
from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.application.router import route_user_query
from app.domains.assistant.application.types import AssistantMemoryRecord, AssistantRouteDecision
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_analytics.contracts import DailyMetric
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.routines.contracts import (
    CardLog,
    RoutineAssignment,
    RoutineSchedule,
)


class _FakeReadStore:
    def __init__(self, *, experiments: list[Experiment] | None = None) -> None:
        self._experiments = list(experiments or [])

    def list_experiments(
        self,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        if statuses:
            return [experiment for experiment in self._experiments if experiment.status in statuses]
        if status is None:
            return list(self._experiments)
        return [experiment for experiment in self._experiments if experiment.status == status]

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        _ = experiment_id
        return None

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        _ = (experiment_id, date)
        return []

    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        _ = status
        return []

    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]:
        _ = routine_id
        return []

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        _ = (start_date, end_date)
        return []

    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        _ = last_n
        return []

    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        _ = last_n
        return []

    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]:
        _ = last_n
        return []

    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        _ = profile_id
        return None


def test_entity_resolver_matches_meditation_experiment_to_active_experiment() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(
                id="meditation-hrv-2026-03",
                name="Meditation to HRV",
                status="active",
            )
        ]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How does our meditation experiment look like so far?",
    )

    assert resolved[0].kind == "experiment"
    assert resolved[0].entity_id == "meditation-hrv-2026-03"


def test_entity_resolver_returns_no_match_when_experiment_candidates_are_ambiguous() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(id="meditation-hrv", name="Meditation to HRV", status="active"),
            Experiment(id="meditation-sleep", name="Meditation to Sleep", status="active"),
        ]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How does our meditation experiment look like so far?",
    )

    assert resolved == []


def test_entity_resolver_skips_resolution_for_non_experiment_routes() -> None:
    store = _FakeReadStore(
        experiments=[Experiment(id="meditation-hrv", name="Meditation to HRV", status="active")]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="recovery_briefing", confidence=0.95),
        query="Give me a quick recovery briefing for today",
    )

    assert resolved == []


def test_entity_resolver_prefers_exact_overlapping_experiment_id_match() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(id="sleep", name="Sleep", status="active"),
            Experiment(id="sleep-quality", name="Sleep Quality", status="active"),
        ]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="Can you review sleep-quality so far?",
    )

    assert resolved[0].entity_id == "sleep-quality"
    assert 0.0 <= resolved[0].score <= 1.0
    assert resolved[0].score == 1.0


def test_entity_resolver_handles_trial_synonym_route_for_experiment_matching() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(
                id="meditation-hrv-2026-03",
                name="Meditation to HRV",
                status="active",
            )
        ]
    )
    route = route_user_query("How is the meditation trial going?")

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=route,
        query="How is the meditation trial going?",
    )

    assert route.intent == "experiment_review"
    assert resolved[0].entity_id == "meditation-hrv-2026-03"


def test_entity_resolver_returns_no_match_when_only_generic_experiment_words_overlap() -> None:
    store = _FakeReadStore(
        experiments=[Experiment(id="cold-plunge", name="Cold Plunge", status="active")]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How is the experiment going?",
    )

    assert resolved == []


def test_entity_resolver_uses_alias_memory_for_experiment_matching() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(
                id="meditation-hrv-2026-03",
                name="Meditation to HRV",
                status="active",
            )
        ]
    )
    memory = [
        AssistantMemoryRecord(
            id="memory-1",
            kind="entity_alias",
            entity_id="meditation-hrv-2026-03",
            alias_text="mindfulness protocol",
        )
    ]

    resolved = resolve_entities(
        store=store,
        memory=memory,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How is my mindfulness protocol doing?",
    )

    assert resolved[0].entity_id == "meditation-hrv-2026-03"


def test_entity_resolver_matches_draft_experiment_when_query_names_it() -> None:
    store = _FakeReadStore(
        experiments=[
            Experiment(
                id="meditation-hrv-draft",
                name="Meditation to HRV",
                status="draft",
            )
        ]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How does our meditation experiment look like so far?",
    )

    assert resolved[0].entity_id == "meditation-hrv-draft"
