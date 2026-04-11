"""Tests for deterministic assistant evidence retrieval and bundling."""

from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.models import (
    CardLog,
    DailyCheckIn,
    DailyMetric,
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
    Note,
    RoutineAssignment,
    RoutineSchedule,
    UserProfile,
)


class _FakeReadStore:
    def __init__(
        self,
        *,
        experiments: list[Experiment] | None = None,
        analysis_by_experiment_id: dict[str, ExperimentAnalysis] | None = None,
        exposures_by_experiment_id: dict[str, list[ExperimentExposure]] | None = None,
        routines: list[RoutineSchedule] | None = None,
        evidence_bundles: list[AssistantEvidenceBundle] | None = None,
        memory_records: list[AssistantMemoryRecord] | None = None,
    ) -> None:
        self._experiments = list(experiments or [])
        self._analysis_by_experiment_id = dict(analysis_by_experiment_id or {})
        self._exposures_by_experiment_id = {
            experiment_id: list(exposures)
            for experiment_id, exposures in (exposures_by_experiment_id or {}).items()
        }
        self._routines = list(routines or [])
        self._evidence_bundles = list(evidence_bundles or [])
        self._memory_records = list(memory_records or [])

    @classmethod
    def for_experiment_review(cls, *, experiment_id: str, routine_id: str) -> _FakeReadStore:
        experiment = Experiment(
            id=experiment_id,
            name="Meditation -> HRV",
            status="active",
            linked_routine_ids=[routine_id],
        )
        analysis = ExperimentAnalysis(
            experiment_id=experiment_id,
            analysis_date="2026-03-14",
            phase="treatment",
            days_in_baseline=14,
            days_in_treatment=14,
            adherence_rate=0.86,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="moderate",
            summary="HRV trend improved while adherence remained stable.",
        )
        exposures = [
            ExperimentExposure(
                id="exp-1",
                experiment_id=experiment_id,
                date="2026-03-13",
                exposure_score=1.0,
                adherence_state="full",
            ),
            ExperimentExposure(
                id="exp-2",
                experiment_id=experiment_id,
                date="2026-03-14",
                exposure_score=1.0,
                adherence_state="full",
            ),
        ]
        routines = [
            RoutineSchedule(
                id=routine_id,
                name="Two-week Meditation Foundation",
                status="active",
                start_date="2026-03-01",
            )
        ]
        evidence_bundles = [
            AssistantEvidenceBundle(
                id="bundle-prev-1",
                thread_id="thread-legacy",
                user_message_id="message-legacy",
                intent="experiment_review",
                entities=[],
                items=[
                    AssistantEvidenceItem(
                        kind="experiment",
                        source="experiment_table",
                        entity_id=experiment_id,
                        payload_json={"name": "Meditation -> HRV"},
                    )
                ],
                gaps=[],
                created_at="2026-03-15T10:00:00Z",
            )
        ]
        memory_records = [
            AssistantMemoryRecord(
                id="mem-1",
                kind="entity_alias",
                entity_id=experiment_id,
                alias_text="mindfulness protocol",
            )
        ]
        return cls(
            experiments=[experiment],
            analysis_by_experiment_id={experiment_id: analysis},
            exposures_by_experiment_id={experiment_id: exposures},
            routines=routines,
            evidence_bundles=evidence_bundles,
            memory_records=memory_records,
        )

    def list_experiments(
        self,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        experiments = list(self._experiments)
        if statuses is not None:
            return [experiment for experiment in experiments if experiment.status in statuses]
        if status is not None:
            return [experiment for experiment in experiments if experiment.status == status]
        return experiments

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        return self._analysis_by_experiment_id.get(experiment_id)

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        if experiment_id is None:
            return []
        exposures = list(self._exposures_by_experiment_id.get(experiment_id, []))
        if date is None:
            return exposures
        return [exposure for exposure in exposures if exposure.date == date]

    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        routines = list(self._routines)
        if status is None:
            return routines
        return [routine for routine in routines if routine.status == status]

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

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]:
        bundles = list(self._evidence_bundles)
        if thread_id is not None:
            bundles = [bundle for bundle in bundles if bundle.thread_id == thread_id]
        if last_n is None:
            return bundles
        return bundles[-last_n:]

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantMemoryRecord]:
        records = list(self._memory_records)
        if kind is not None:
            records = [record for record in records if record.kind == kind]
        if last_n is None:
            return records
        return records[-last_n:]


def test_experiment_review_retriever_returns_analysis_adherence_and_linked_routine() -> None:
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation -> HRV",
            score=0.98,
        )
    ]

    bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    kinds = [item.kind for item in bundle.items]
    assert "experiment" in kinds
    assert "analysis" in kinds
    assert "exposures" in kinds
    assert "linked_routine" in kinds


def test_experiment_review_retriever_includes_cross_thread_recall_hooks() -> None:
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation -> HRV",
            score=0.98,
        )
    ]

    bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    kinds = [item.kind for item in bundle.items]
    assert "prior_evidence" in kinds
    assert "memory" in kinds


def test_deterministic_bundle_id_uses_raw_inputs_without_lossy_collisions() -> None:
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation -> HRV",
            score=0.98,
        )
    ]

    dot_thread_bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread.1",
        user_message_id="MSG",
    )
    dash_thread_bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="MSG",
    )
    lowercase_message_bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread.1",
        user_message_id="msg",
    )

    assert dot_thread_bundle.id != dash_thread_bundle.id
    assert dot_thread_bundle.id != lowercase_message_bundle.id


def test_prior_evidence_recall_selects_other_threads_before_truncation() -> None:
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation -> HRV",
            score=0.98,
        )
    ]

    older_cross_thread = [
        AssistantEvidenceBundle(
            id="other-1",
            thread_id="thread-x",
            user_message_id="m-1",
            intent="experiment_review",
            created_at="2026-03-01T00:00:00Z",
        ),
        AssistantEvidenceBundle(
            id="other-2",
            thread_id="thread-y",
            user_message_id="m-2",
            intent="experiment_review",
            created_at="2026-03-02T00:00:00Z",
        ),
    ]
    busy_current_thread = [
        AssistantEvidenceBundle(
            id=f"current-{index}",
            thread_id="thread-1",
            user_message_id=f"current-message-{index}",
            intent="experiment_review",
            created_at=f"2026-03-{3 + index:02d}T00:00:00Z",
        )
        for index in range(1, 11)
    ]
    store._evidence_bundles = older_cross_thread + busy_current_thread

    bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    prior_bundle_ids = {
        item.payload_json["bundle_id"]
        for item in bundle.items
        if item.kind == "prior_evidence"
    }
    assert prior_bundle_ids == {"other-1", "other-2"}


def test_linked_routine_includes_non_active_status_when_routine_exists() -> None:
    routine_id = "two-week-meditation-foundation-routine"
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id=routine_id,
    )
    store._routines = [
        RoutineSchedule(
            id=routine_id,
            name="Two-week Meditation Foundation",
            status="retired",
            start_date="2026-03-01",
        )
    ]
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation -> HRV",
            score=0.98,
        )
    ]

    bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    linked_items = [item for item in bundle.items if item.kind == "linked_routine"]
    assert linked_items
    assert linked_items[0].payload_json["routines"][0]["status"] == "retired"
    assert not any(gap.startswith("linked_routine_missing:") for gap in bundle.gaps)
