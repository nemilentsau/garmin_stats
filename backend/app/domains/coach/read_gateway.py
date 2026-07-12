"""Single cross-domain read seam for existing coach evidence.

This adapter delegates to shipped application read models. It does not
recompute analytics, unit conversions, association policy, or journal policy.
"""

from __future__ import annotations

from app.domains.garmin_analytics.application import dashboard as dashboard_uc
from app.domains.garmin_analytics.application import runs as runs_uc
from app.domains.garmin_analytics.application.dependencies import (
    BiometricReadRepository,
    RunsReadRepository,
)
from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse,
    RunDetailResponse,
    RunListItem,
    RunSeriesResponse,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn, Note
from app.domains.journal.dependencies import JournalRepository
from app.domains.training.application import read_models as training_uc
from app.domains.training.contracts import (
    TrainingBlockStatus,
    TrainingScheduleWindow,
    TrainingTodayResponse,
)
from app.domains.training.dependencies import RunActivityReadPort, TrainingRepository


class CoachReadGateway:
    """Adapt authoritative application read models into coach evidence access."""

    def __init__(
        self,
        *,
        runs_repo: RunsReadRepository,
        biometrics_repo: BiometricReadRepository,
        training_repo: TrainingRepository,
        run_activity_port: RunActivityReadPort,
        journal_repo: JournalRepository,
    ) -> None:
        self._runs_repo = runs_repo
        self._biometrics_repo = biometrics_repo
        self._training_repo = training_repo
        self._run_activity_port = run_activity_port
        self._journal_repo = journal_repo

    def recent_runs(self, *, evidence_date: str, limit: int = 20) -> list[RunListItem]:
        response = runs_uc.list_runs(self._runs_repo, to_date=evidence_date)
        return response.runs[:limit]

    def run_detail(self, run_id: str) -> RunDetailResponse:
        return runs_uc.get_run(self._runs_repo, run_id)

    def run_series(self, run_id: str) -> RunSeriesResponse:
        return runs_uc.get_run_series(self._runs_repo, run_id)

    def recovery_overview(self) -> DashboardOverviewResponse | None:
        try:
            return dashboard_uc.get_dashboard_overview(self._biometrics_repo)
        except LookupError:
            return None

    def daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        return self._biometrics_repo.load_daily_metrics(last_n=last_n)

    def training_today(self, date: str) -> TrainingTodayResponse:
        return training_uc.get_training_today(
            self._training_repo,
            date=date,
            run_activity_port=self._run_activity_port,
        )

    def training_window(self, start: str, days: int) -> TrainingScheduleWindow:
        return training_uc.get_training_schedule_window(
            self._training_repo,
            start_date=start,
            duration_days=days,
        )

    def block_status(self) -> TrainingBlockStatus | None:
        return training_uc.get_block_status(self._training_repo)

    def checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        return self._journal_repo.list_checkins(last_n=last_n)

    def notes(self, *, last_n: int | None = None) -> list[Note]:
        return self._journal_repo.list_notes(last_n=last_n)
