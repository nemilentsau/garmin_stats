"""Tests for deterministic assistant evidence retrieval and bundling."""

from datetime import date

import app.domains.assistant.domain.current_state as current_state_mod
from app.core.profile.contracts import UserProfile
from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)
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
    def __init__(
        self,
        *,
        experiments: list[Experiment] | None = None,
        analysis_by_experiment_id: dict[str, ExperimentAnalysis] | None = None,
        exposures_by_experiment_id: dict[str, list[ExperimentExposure]] | None = None,
        routines: list[RoutineSchedule] | None = None,
        assignments: list[RoutineAssignment] | None = None,
        card_logs: list[CardLog] | None = None,
        metrics: list[DailyMetric] | None = None,
        checkins: list[DailyCheckIn] | None = None,
        notes: list[Note] | None = None,
        profile: UserProfile | None = None,
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
        self._assignments = list(assignments or [])
        self._card_logs = list(card_logs or [])
        self._metrics = list(metrics or [])
        self._checkins = list(checkins or [])
        self._notes = list(notes or [])
        self._profile = profile
        self._evidence_bundles = list(evidence_bundles or [])
        self._memory_records = list(memory_records or [])
        self.get_experiment_calls: list[str] = []
        self.list_all_experiment_analyses_calls = 0
        self.list_experiment_exposures_calls: list[tuple[str | None, str | None]] = []
        self.get_routine_calls: list[str] = []
        self.list_assignments_calls: list[str | None] = []

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

    @classmethod
    def for_current_state(cls) -> _FakeReadStore:
        experiment = Experiment(
            id="meditation-hrv-2026-03",
            name="Meditation to HRV",
            status="active",
            linked_routine_ids=["meditation-routine"],
        )
        analysis = ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date="2026-04-11",
            phase="treatment",
            days_in_baseline=14,
            days_in_treatment=14,
            adherence_rate=0.86,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="moderate",
            summary="Recovery trends are stable with mild week-to-week noise.",
        )
        metrics = [
            DailyMetric(
                date="2026-04-11",
                utc_offset_hours=-6.0,
                heart_rate=DailyHeartRateStats(resting=48, avg=64.0),
                stress=DailyMetricStats(avg=22.0),
                body_battery=DailyBodyBatteryStats(avg=71.0),
                spo2=DailyMetricStats(avg=97.0),
                respiration=DailyMetricStats(avg=14.1),
                hrv=DailyHrvStats(nightly_avg=57.0, weekly_avg=55.0, status="balanced"),
                sleep=DailySleepStats(score=82),
                skin_temp=DailySkinTempStats(deviation=0.1),
            ),
            DailyMetric(
                date="2026-04-10",
                utc_offset_hours=-6.0,
                heart_rate=DailyHeartRateStats(resting=49, avg=65.0),
                stress=DailyMetricStats(avg=24.0),
                body_battery=DailyBodyBatteryStats(avg=68.0),
                spo2=DailyMetricStats(avg=96.8),
                respiration=DailyMetricStats(avg=14.0),
                hrv=DailyHrvStats(nightly_avg=54.0, weekly_avg=54.5, status="balanced"),
                sleep=DailySleepStats(score=79),
                skin_temp=DailySkinTempStats(deviation=0.05),
            ),
        ]
        checkins = [
            DailyCheckIn(
                id="checkin-1",
                date="2026-04-11",
                energy=6,
                mood=7,
                motivation=6,
                soreness=2,
                stress_subjective=4,
                sleep_quality_subjective=7,
                workload_subjective=5,
                illness_flag=False,
                travel_flag=False,
                alcohol_flag=False,
            )
        ]
        routines = [
            RoutineSchedule(
                id="meditation-routine",
                name="Meditation Session",
                status="active",
                start_date="2026-04-01",
            ),
            RoutineSchedule(
                id="mobility-routine",
                name="Mobility Reset",
                status="retired",
                start_date="2026-03-01",
                end_date="2026-03-31",
            ),
        ]
        assignments = [
            RoutineAssignment(
                id="assignment-1",
                routine_id="meditation-routine",
                card_template_id="meditation-card",
                date="2026-04-10",
                slot="morning",
            ),
            RoutineAssignment(
                id="assignment-2",
                routine_id="meditation-routine",
                card_template_id="meditation-card",
                date="2026-04-11",
                slot="morning",
            ),
        ]
        card_logs = [
            CardLog(
                id="card-log-1",
                date="2026-04-10",
                occurrence_key="meditation-2026-04-10-morning",
                card_template_id="meditation-card",
                assignment_id="assignment-1",
                status="completed",
                actual_json={},
            ),
            CardLog(
                id="card-log-2",
                date="2026-04-11",
                occurrence_key="meditation-2026-04-11-morning",
                card_template_id="meditation-card",
                assignment_id="assignment-2",
                status="partial",
                actual_json={},
            ),
        ]
        notes = [
            Note(
                id="note-1",
                date="2026-04-11",
                category="recovery",
                title="Travel tailwind",
                content="Sleep felt more stable after travel settled.",
                tags=["travel", "recovery"],
            )
        ]
        profile = UserProfile(
            name="Andrei",
            primary_goals=["better recovery"],
            constraints=["avoid late caffeine"],
            coaching_style_preferences=["direct"],
        )
        return cls(
            experiments=[experiment],
            analysis_by_experiment_id={experiment.id: analysis},
            exposures_by_experiment_id={
                experiment.id: [
                    ExperimentExposure(
                        id="exp-1",
                        experiment_id=experiment.id,
                        date="2026-04-10",
                        exposure_score=1.0,
                        adherence_state="full",
                    )
                ]
            },
            routines=routines,
            assignments=assignments,
            card_logs=card_logs,
            metrics=metrics,
            checkins=checkins,
            notes=notes,
            profile=profile,
        )

    @classmethod
    def for_weekly_state(cls) -> _FakeReadStore:
        experiment = Experiment(
            id="meditation-hrv-2026-03",
            name="Meditation to HRV",
            status="active",
            linked_routine_ids=["meditation-routine"],
        )
        analysis = ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date="2026-04-11",
            phase="treatment",
            days_in_baseline=14,
            days_in_treatment=14,
            adherence_rate=0.86,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="moderate",
            summary="Recovery trends are stable with mild week-to-week noise.",
        )
        metrics = [
            DailyMetric(
                date=f"2026-04-{day:02d}",
                utc_offset_hours=-6.0,
                heart_rate=DailyHeartRateStats(resting=48 + (day % 2), avg=64.0),
                stress=DailyMetricStats(avg=22.0 + (day % 3)),
                body_battery=DailyBodyBatteryStats(avg=65.0 + day),
                spo2=DailyMetricStats(avg=96.0 + (day % 2) * 0.2),
                respiration=DailyMetricStats(avg=14.0 + (day % 2) * 0.1),
                hrv=DailyHrvStats(
                    nightly_avg=52.0 + day,
                    weekly_avg=54.0 + day / 10.0,
                    status="balanced",
                ),
                sleep=DailySleepStats(score=74 + day),
                skin_temp=DailySkinTempStats(deviation=0.05),
            )
            for day in range(4, 12)
        ]
        checkins = [
            DailyCheckIn(
                id=f"checkin-{day}",
                date=f"2026-04-{day:02d}",
                energy=day % 10,
                mood=6,
                motivation=6,
                soreness=2,
                stress_subjective=4,
                sleep_quality_subjective=7,
                workload_subjective=5,
                illness_flag=False,
                travel_flag=False,
                alcohol_flag=False,
            )
            for day in range(4, 12)
        ]
        routines = [
            RoutineSchedule(
                id="meditation-routine",
                name="Meditation Session",
                status="active",
                start_date="2026-04-01",
            ),
            RoutineSchedule(
                id="mobility-routine",
                name="Mobility Reset",
                status="active",
                start_date="2026-04-03",
            ),
        ]
        assignments = [
            RoutineAssignment(
                id=f"assignment-{day}",
                routine_id="meditation-routine",
                card_template_id="meditation-card",
                date=f"2026-04-{day:02d}",
                slot="morning",
            )
            for day in range(4, 12)
        ]
        card_logs = [
            CardLog(
                id=f"card-log-{day}",
                date=f"2026-04-{day:02d}",
                occurrence_key=f"meditation-2026-04-{day:02d}-morning",
                card_template_id="meditation-card",
                assignment_id=f"assignment-{day}",
                status="completed" if day % 2 else "partial",
                actual_json={},
            )
            for day in range(4, 12)
        ]
        card_logs.append(
            CardLog(
                id="card-log-unrelated",
                date="2026-04-11",
                occurrence_key="unrelated-2026-04-11-morning",
                card_template_id="mobility-card",
                assignment_id="unrelated-assignment",
                status="skipped",
                actual_json={},
            )
        )
        notes = [
            Note(
                id="note-1",
                date="2026-04-11",
                category="recovery",
                title="Travel tailwind",
                content="Sleep felt more stable after travel settled.",
                tags=["travel", "recovery"],
            )
        ]
        profile = UserProfile(
            name="Andrei",
            primary_goals=["better recovery"],
            constraints=["avoid late caffeine"],
            coaching_style_preferences=["direct"],
        )
        return cls(
            experiments=[experiment],
            analysis_by_experiment_id={experiment.id: analysis},
            exposures_by_experiment_id={
                experiment.id: [
                    ExperimentExposure(
                        id=f"exp-{day}",
                        experiment_id=experiment.id,
                        date=f"2026-04-{day:02d}",
                        exposure_score=1.0,
                        adherence_state="full",
                    )
                    for day in range(4, 12)
                ]
            },
            routines=routines,
            assignments=assignments,
            card_logs=card_logs,
            metrics=metrics,
            checkins=checkins,
            notes=notes,
            profile=profile,
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

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        self.get_experiment_calls.append(experiment_id)
        for experiment in self._experiments:
            if experiment.id == experiment_id:
                return experiment
        return None

    def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
        self.list_all_experiment_analyses_calls += 1
        return dict(self._analysis_by_experiment_id)

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        return self._analysis_by_experiment_id.get(experiment_id)

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        self.list_experiment_exposures_calls.append((experiment_id, date))
        if experiment_id is None:
            exposures = [
                exposure
                for experiment_exposures in self._exposures_by_experiment_id.values()
                for exposure in experiment_exposures
            ]
        else:
            exposures = list(self._exposures_by_experiment_id.get(experiment_id, []))
        if date is None:
            return exposures
        return [exposure for exposure in exposures if exposure.date == date]

    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        routines = list(self._routines)
        if status is None:
            return routines
        return [routine for routine in routines if routine.status == status]

    def get_routine(self, routine_id: str) -> RoutineSchedule | None:
        self.get_routine_calls.append(routine_id)
        for routine in self._routines:
            if routine.id == routine_id:
                return routine
        return None

    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]:
        self.list_assignments_calls.append(routine_id)
        assignments = list(self._assignments)
        if routine_id is not None:
            assignments = [
                assignment
                for assignment in assignments
                if assignment.routine_id == routine_id
            ]
        return assignments

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        return [
            card_log
            for card_log in self._card_logs
            if start_date <= card_log.date <= end_date
        ]

    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        metrics = list(self._metrics)
        if last_n is None:
            return metrics
        return metrics[-last_n:]

    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        checkins = list(self._checkins)
        if last_n is None:
            return checkins
        return checkins[-last_n:]

    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]:
        notes = list(self._notes)
        if last_n is None:
            return notes
        return notes[-last_n:]

    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        _ = profile_id
        return self._profile

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
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]:
        records = list(self._memory_records)
        if kind is not None:
            records = [record for record in records if record.kind == kind]
        if alias_candidates is not None:
            candidate_set = set(alias_candidates)
            records = [
                record
                for record in records
                if record.alias_text is not None
                and " ".join(record.alias_text.lower().split()) in candidate_set
            ]
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
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    kinds = [item.kind for item in bundle.items]
    assert "experiment" in kinds
    assert "analysis" in kinds
    assert "exposures" in kinds
    assert "linked_routine" in kinds
    analysis_item = next(item for item in bundle.items if item.kind == "analysis")
    assert analysis_item.payload_json["days_in_baseline"] == 14
    assert analysis_item.payload_json["days_in_treatment"] == 14
    assert "metrics" in analysis_item.payload_json
    assert "confounders" in analysis_item.payload_json


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
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
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
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread.1",
        user_message_id="MSG",
    )
    dash_thread_bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread-1",
        user_message_id="MSG",
    )
    lowercase_message_bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
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
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
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


def test_prior_evidence_excludes_unrelated_threads_without_overlap_or_recall() -> None:
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
    store._evidence_bundles = [
        AssistantEvidenceBundle(
            id="other-1",
            thread_id="thread-x",
            user_message_id="m-1",
            intent="recovery_briefing",
            created_at="2026-03-01T00:00:00Z",
            entities=[
                AssistantResolvedEntity(
                    kind="routine",
                    entity_id="sleep-routine",
                    label="Sleep routine",
                    score=0.9,
                )
            ],
        )
    ]

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    assert not any(item.kind == "prior_evidence" for item in bundle.items)


def test_prior_evidence_includes_same_entity_across_threads() -> None:
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
    store._evidence_bundles = [
        AssistantEvidenceBundle(
            id="other-entity-match",
            thread_id="thread-x",
            user_message_id="m-1",
            intent="open_ended_coaching",
            created_at="2026-03-02T00:00:00Z",
            entities=[
                AssistantResolvedEntity(
                    kind="experiment",
                    entity_id="meditation-hrv-2026-03",
                    label="Meditation -> HRV",
                    score=0.95,
                )
            ],
        )
    ]

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    prior_items = [item for item in bundle.items if item.kind == "prior_evidence"]
    assert len(prior_items) == 1
    assert prior_items[0].payload_json["match_type"] == "entity_overlap"
    assert prior_items[0].payload_json["matched_entity_ids"] == [
        "meditation-hrv-2026-03"
    ]
    assert prior_items[0].entity_id == "meditation-hrv-2026-03"


def test_prior_evidence_includes_adjacent_family_for_recovery_briefing() -> None:
    store = _FakeReadStore.for_weekly_state()
    store._evidence_bundles = [
        AssistantEvidenceBundle(
            id="other-adjacent",
            thread_id="thread-x",
            user_message_id="m-1",
            intent="open_ended_coaching",
            created_at="2026-04-11T00:00:00Z",
        ),
        AssistantEvidenceBundle(
            id="other-unrelated",
            thread_id="thread-y",
            user_message_id="m-2",
            intent="experiment_review",
            created_at="2026-04-10T00:00:00Z",
        ),
    ]

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="recovery_briefing", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-2",
    )

    prior_items = [item for item in bundle.items if item.kind == "prior_evidence"]
    assert [item.payload_json["bundle_id"] for item in prior_items] == [
        "other-adjacent"
    ]
    assert prior_items[0].payload_json["match_type"] == "intent_family"


def test_prior_evidence_explicit_recall_override_includes_otherwise_excluded_bundle() -> None:
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    store._evidence_bundles = [
        AssistantEvidenceBundle(
            id="other-explicit",
            thread_id="thread-x",
            user_message_id="m-1",
            intent="open_ended_coaching",
            created_at="2026-03-04T00:00:00Z",
        )
    ]

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment", "explicit_recall_language"],
        ),
        entities=[
            AssistantResolvedEntity(
                kind="experiment",
                entity_id="meditation-hrv-2026-03",
                label="Meditation -> HRV",
                score=0.98,
            )
        ],
        thread_id="thread-1",
        user_message_id="message-1",
    )

    prior_items = [item for item in bundle.items if item.kind == "prior_evidence"]
    assert [item.payload_json["bundle_id"] for item in prior_items] == [
        "other-explicit"
    ]
    assert prior_items[0].payload_json["match_type"] == "explicit_recall"


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
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    linked_items = [item for item in bundle.items if item.kind == "linked_routine"]
    assert linked_items
    assert linked_items[0].payload_json["routines"][0]["status"] == "retired"
    assert not any(gap.startswith("linked_routine_missing:") for gap in bundle.gaps)


def test_experiment_review_scans_active_experiments_when_no_entity_is_resolved() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["experiment_routine_scan"],
        ),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-1",
    )

    kinds = [item.kind for item in bundle.items]
    assert "scan_overview" in kinds
    assert not bundle.gaps
    scan_item = next(item for item in bundle.items if item.kind == "scan_overview")
    assert scan_item.payload_json["active_experiments"]
    assert scan_item.payload_json["active_routines"]
    assert scan_item.payload_json["tracking_quality"]["metric_days"] == 7
    assert scan_item.payload_json["tracking_quality"]["checkin_days"] == 7
    assert scan_item.payload_json["tracking_quality"]["card_log_days"] == 7
    assert scan_item.payload_json["tracking_quality"]["routine_coverage_dates"] == 7
    assert store.list_all_experiment_analyses_calls == 1
    assert store.list_experiment_exposures_calls == [("meditation-hrv-2026-03", None)]
    assert set(store.list_assignments_calls) == {"meditation-routine", "mobility-routine"}


def test_experiment_scan_includes_all_active_items_without_hidden_truncation() -> None:
    store = _FakeReadStore.for_weekly_state()
    store._experiments.extend(
        [
            Experiment(
                id="sleep-stack-2026-04",
                name="Sleep stack",
                status="active",
            ),
            Experiment(
                id="mobility-dose-2026-04",
                name="Mobility dose",
                status="active",
            ),
            Experiment(
                id="caffeine-curfew-2026-04",
                name="Caffeine curfew",
                status="active",
            ),
        ]
    )
    store._routines.extend(
        [
            RoutineSchedule(
                id="sleep-stack-routine",
                name="Sleep stack routine",
                status="active",
                start_date="2026-04-02",
            ),
            RoutineSchedule(
                id="caffeine-curfew-routine",
                name="Caffeine curfew routine",
                status="active",
                start_date="2026-04-05",
            ),
        ]
    )

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["experiment_routine_scan"],
        ),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-1",
    )

    scan_item = next(item for item in bundle.items if item.kind == "scan_overview")
    assert scan_item.payload_json["active_experiment_count"] == 4
    assert len(scan_item.payload_json["active_experiments"]) == 4
    assert scan_item.payload_json["active_routine_count"] == 4
    assert len(scan_item.payload_json["active_routines"]) == 4
    assert store.list_all_experiment_analyses_calls == 1
    assert set(store.list_experiment_exposures_calls) == {
        ("caffeine-curfew-2026-04", None),
        ("meditation-hrv-2026-03", None),
        ("mobility-dose-2026-04", None),
        ("sleep-stack-2026-04", None),
    }
    assert set(store.list_assignments_calls) == {
        "caffeine-curfew-routine",
        "meditation-routine",
        "mobility-routine",
        "sleep-stack-routine",
    }


def test_experiment_review_without_scan_signal_keeps_missing_entity_gap() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["mentions_experiment"],
        ),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-1",
    )

    assert bundle.items == []
    assert bundle.gaps == ["experiment_entity_missing"]


def test_experiment_scan_preserves_partial_context_gaps() -> None:
    store = _FakeReadStore.for_weekly_state()
    store._checkins = []
    store._card_logs = []

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(
            intent="experiment_review",
            confidence=0.95,
            matched_signals=["experiment_routine_scan"],
        ),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-1",
    )

    assert any(item.kind == "scan_overview" for item in bundle.items)
    assert "recent_checkins_missing" in bundle.gaps
    assert "recent_card_logs_missing" in bundle.gaps


def test_recovery_briefing_returns_current_state_context() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="recovery_briefing", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-2",
    )

    kinds = [item.kind for item in bundle.items]
    assert "recovery_state" in kinds
    assert "unsupported_intent:recovery_briefing" not in bundle.gaps
    recovery_item = next(item for item in bundle.items if item.kind == "recovery_state")
    assert recovery_item.payload_json["recent_metrics"]
    assert recovery_item.payload_json["recent_checkins"]
    assert len(recovery_item.payload_json["recent_metrics"]) == 7
    assert len(recovery_item.payload_json["recent_checkins"]) == 7


def test_routine_adherence_returns_current_state_context() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="routine_adherence", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-3",
    )

    kinds = [item.kind for item in bundle.items]
    assert "routine_state" in kinds
    assert "unsupported_intent:routine_adherence" not in bundle.gaps
    routine_item = next(item for item in bundle.items if item.kind == "routine_state")
    assert routine_item.payload_json["active_routines"]
    assert routine_item.payload_json["assignment_summary"]
    assert routine_item.payload_json["card_log_window"]["status_counts"]["completed"] == 4
    assert routine_item.payload_json["card_log_window"]["status_counts"]["partial"] == 3
    assert "skipped" not in routine_item.payload_json["card_log_window"]["status_counts"]
    assert len(routine_item.payload_json["card_log_window"]["logs"]) == 5
    assert len(routine_item.payload_json["card_log_window"]["logged_dates"]) == 7


def test_routine_adherence_compacts_assignment_history_to_recent_window() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="routine_adherence", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-3",
    )

    routine_item = next(item for item in bundle.items if item.kind == "routine_state")
    summary = routine_item.payload_json["assignment_summary"][0]
    assert summary["scheduled_date_count"] == 8
    assert summary["recent_scheduled_dates"] == [
        "2026-04-05",
        "2026-04-06",
        "2026-04-07",
        "2026-04-08",
        "2026-04-09",
        "2026-04-10",
        "2026-04-11",
    ]
    assert "scheduled_dates" not in summary


def test_routine_adherence_caps_future_schedule_window_at_today(monkeypatch) -> None:
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 12)

    monkeypatch.setattr(current_state_mod, "date", _FrozenDate)

    store = _FakeReadStore.for_weekly_state()
    store._assignments.extend(
        [
            RoutineAssignment(
                id="future-assignment-1",
                routine_id="meditation-routine",
                card_template_id="meditation-card",
                date="2026-04-18",
                slot="morning",
            ),
            RoutineAssignment(
                id="future-assignment-2",
                routine_id="meditation-routine",
                card_template_id="meditation-card",
                date="2026-04-20",
                slot="morning",
            ),
        ]
    )

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="routine_adherence", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-3",
    )

    routine_item = next(item for item in bundle.items if item.kind == "routine_state")
    expected_end_date = min(date(2026, 4, 20), _FrozenDate.today()).isoformat()
    assert routine_item.payload_json["card_log_window"]["end_date"] == expected_end_date
    assert routine_item.payload_json["card_log_window"]["status_counts"]["completed"] == 3
    assert routine_item.payload_json["card_log_window"]["status_counts"]["partial"] == 3
    assert "recent_card_logs_missing" not in bundle.gaps


def test_open_ended_coaching_returns_combined_current_state_context() -> None:
    store = _FakeReadStore.for_weekly_state()

    bundle = build_evidence_bundle(
        read_store=store,
        recall_store=store,
        route=AssistantRouteDecision(intent="open_ended_coaching", confidence=0.95),
        entities=[],
        thread_id="thread-1",
        user_message_id="message-4",
    )

    kinds = [item.kind for item in bundle.items]
    assert "coaching_context" in kinds
    assert "unsupported_intent:open_ended_coaching" not in bundle.gaps
    coaching_item = next(item for item in bundle.items if item.kind == "coaching_context")
    assert coaching_item.payload_json["recovery"]["recent_metrics"]
    assert coaching_item.payload_json["routine"]["active_routines"]
    assert coaching_item.payload_json["recent_notes"]
    assert len(coaching_item.payload_json["recovery"]["recent_metrics"]) == 7
