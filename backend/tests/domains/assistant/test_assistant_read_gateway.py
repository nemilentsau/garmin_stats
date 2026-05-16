"""Assistant read gateway tests for cross-domain evidence dependencies."""

from typing import Any, cast

from app.domains.assistant.read_gateway import AssistantReadModelGateway


class TestAssistantReadModelGateway:
    def test_list_recent_metrics_pushes_limit_to_biometric_repository(self):
        class _TrackingBiometricRepo:
            def __init__(self):
                self.last_n_calls: list[int | None] = []

            def load_daily_metrics(self, *, last_n: int | None = None) -> list[object]:
                self.last_n_calls.append(last_n)
                return []

        biometric_repo = _TrackingBiometricRepo()
        gateway = AssistantReadModelGateway(
            experiment_repo=cast(Any, object()),
            experiment_read_source=cast(Any, object()),
            profile_repo=cast(Any, object()),
            routine_repo=cast(Any, object()),
            journal_repo=cast(Any, object()),
            biometric_repo=cast(Any, biometric_repo),
        )

        assert gateway.list_recent_metrics(last_n=7) == []
        assert biometric_repo.last_n_calls == [7]

    def test_get_experiment_analysis_converts_missing_snapshot_to_none(self, monkeypatch):
        class _ExperimentRepo:
            pass

        experiment_repo = _ExperimentRepo()
        experiment_read_source = object()
        gateway = AssistantReadModelGateway(
            experiment_repo=cast(Any, experiment_repo),
            experiment_read_source=cast(Any, experiment_read_source),
            profile_repo=cast(Any, object()),
            routine_repo=cast(Any, object()),
            journal_repo=cast(Any, object()),
            biometric_repo=cast(Any, object()),
        )

        def raise_missing(
            candidate_repo: Any,
            candidate_read_source: Any,
            experiment_id: str,
        ):
            assert candidate_repo is experiment_repo
            assert candidate_read_source is experiment_read_source
            assert experiment_id == "experiment-1"
            raise LookupError("missing analysis")

        monkeypatch.setattr(
            "app.domains.assistant.read_gateway.get_current_experiment_analysis",
            raise_missing,
        )

        assert gateway.get_experiment_analysis("experiment-1") is None
