"""Tests for process-owned task startup, disablement, and awaited shutdown."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import app.bootstrap.process_runtime as runtime_module
from app.bootstrap.container import AppContainer
from app.bootstrap.process_runtime import ProcessRuntime


class BlockingLoop:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()

    async def run(self) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()


class FakeWatcher:
    def __init__(self) -> None:
        self.loop = BlockingLoop()
        self.refresh = None

    async def watch(self, *, refresh_after_ingest=None) -> None:
        self.refresh = refresh_after_ingest
        await self.loop.run()


def _container(*, enabled: bool, after_data_change=None):
    worker = BlockingLoop()
    watcher = FakeWatcher()
    recovered: list[tuple[str, int]] = []
    container = SimpleNamespace(
        config=SimpleNamespace(coach_worker_enabled=enabled),
        garmin_sync=SimpleNamespace(after_data_change=after_data_change or (lambda: 0)),
        garmin_sync_watcher=watcher,
        coach_worker=worker,
        coach_repo=SimpleNamespace(
            recover_stale_jobs=lambda **kwargs: recovered.append(
                (kwargs["cutoff"], kwargs["max_attempts"])
            )
        ),
        coach_jobs=SimpleNamespace(),
        experiments_repo=object(),
        experiments_read_source=object(),
    )
    return cast(AppContainer, container), worker, watcher, recovered


def test_enabled_runtime_recovers_starts_and_awaits_all_tasks(monkeypatch):
    container, worker, watcher, recovered = _container(enabled=True)
    heartbeat = BlockingLoop()
    monkeypatch.setattr(runtime_module, "run_startup_ingest_if_needed", lambda deps: None)
    monkeypatch.setattr(runtime_module, "heartbeat_loop", heartbeat.run)

    async def exercise():
        cutoff_time_before_start = datetime.now(UTC)
        runtime = ProcessRuntime(container)
        runtime.start()
        await worker.started.wait()
        await watcher.loop.started.wait()
        await heartbeat.started.wait()
        await runtime.stop()
        return cutoff_time_before_start

    cutoff_time = asyncio.run(exercise())

    assert len(recovered) == 1
    assert recovered[0][1] == 3
    # The cutoff passed should be >= the instant just before start() was called.
    # ISO format with "Z" suffix: "2026-07-15T12:34:56.789012Z"
    cutoff_str = recovered[0][0]
    cutoff_dt = datetime.fromisoformat(cutoff_str.replace("Z", "+00:00"))
    assert cutoff_dt >= cutoff_time, (
        f"Cutoff {cutoff_str} should be >= time before start {cutoff_time.isoformat()}; "
        "recovery window must cover jobs claimed immediately before restart"
    )
    assert worker.stopped.is_set()
    assert watcher.loop.stopped.is_set()
    assert heartbeat.stopped.is_set()


def test_disabled_runtime_skips_coach_recovery_and_worker(monkeypatch):
    container, worker, watcher, recovered = _container(enabled=False)
    heartbeat = BlockingLoop()
    monkeypatch.setattr(runtime_module, "run_startup_ingest_if_needed", lambda deps: None)
    monkeypatch.setattr(runtime_module, "heartbeat_loop", heartbeat.run)

    async def exercise():
        runtime = ProcessRuntime(container)
        runtime.start()
        await watcher.loop.started.wait()
        await heartbeat.started.wait()
        await runtime.stop()

    asyncio.run(exercise())

    assert recovered == []
    assert not worker.started.is_set()
    assert watcher.refresh is not None


def test_watcher_refresh_uses_the_generic_data_change_callback(monkeypatch):
    refreshes: list[str] = []
    container, _worker, _watcher, _recovered = _container(
        enabled=False,
        after_data_change=lambda: refreshes.append("experiments") or 1,
    )

    def obsolete_direct_refresh(*_args, **_kwargs):
        raise AssertionError("runtime must use the composed data-change callback")

    monkeypatch.setattr(
        runtime_module,
        "refresh_active_experiments",
        obsolete_direct_refresh,
        raising=False,
    )

    refreshed = ProcessRuntime(container)._refresh_after_ingest()

    assert refreshed == 1
    assert refreshes == ["experiments"]


def test_coach_startup_recovery_failure_does_not_block_process_tasks(monkeypatch):
    container, worker, watcher, _recovered = _container(enabled=True)
    heartbeat = BlockingLoop()
    monkeypatch.setattr(runtime_module, "run_startup_ingest_if_needed", lambda deps: None)
    monkeypatch.setattr(runtime_module, "heartbeat_loop", heartbeat.run)

    def fail(*_args, **_kwargs):
        raise RuntimeError("recovery unavailable")

    container.coach_repo.recover_stale_jobs = fail

    async def exercise():
        runtime = ProcessRuntime(container)
        runtime.start()
        await worker.started.wait()
        await watcher.loop.started.wait()
        await heartbeat.started.wait()
        await runtime.stop()

    asyncio.run(exercise())

    assert worker.stopped.is_set()
    assert watcher.loop.stopped.is_set()
    assert heartbeat.stopped.is_set()
