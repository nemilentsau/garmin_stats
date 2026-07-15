"""Run or inspect one real coach review through production handlers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.bootstrap.container import build_container  # noqa: E402


def _last_usage(path: Path) -> dict[str, int] | None:
    if not path.is_file():
        return None
    usage = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate = event.get("usage") if isinstance(event, dict) else None
        if isinstance(candidate, dict):
            usage = {
                str(key): int(value)
                for key, value in candidate.items()
                if isinstance(value, int)
            }
    return usage


def main() -> None:
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--run-id")
    choice.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    container = build_container()
    if args.latest:
        runs = container.coach_gateway.recent_runs(evidence_date="9999-12-31", limit=1)
        if not runs:
            raise SystemExit("No runs are available")
        run_id = runs[0].id
    else:
        run_id = args.run_id

    enqueue = container.coach_jobs.enqueue_run_review(run_id)
    if enqueue.created:
        claimed = container.coach_repo.claim_next_job("9999-12-31T23:59:59Z")
        if claimed is None or claimed.id != enqueue.job.id:
            raise RuntimeError("Smoke job was not the next claimable coach job")
        asyncio.run(container.coach_handlers.execute(claimed))

    review = container.coach_repo.review(enqueue.review.id)  # type: ignore[union-attr]
    job = container.coach_repo.job(enqueue.job.id)
    if review is None or job is None:
        raise RuntimeError("Smoke review or job disappeared")
    workspace = (
        container.config.database_path.parent / "coach/workspaces/reviews" / review.id
    )
    stdout = (
        container.config.database_path.parent
        / "coach/logs"
        / f"{job.id}-attempt-{job.attempt_count}.stdout.jsonl"
    )
    print(f"run_id={run_id}")
    print(f"review_id={review.id}")
    print(f"verdict={review.verdict}")
    print(f"refs={','.join(f'{ref.kind}:{ref.value}' for ref in review.refs)}")
    print(f"follow_up_questions={','.join(review.follow_up_questions)}")
    print(f"usage={json.dumps(_last_usage(stdout), sort_keys=True)}")
    print(f"workspace={workspace}")
    print(f"job_status={job.status}")
    if review.status != "complete" or job.status != "complete":
        raise SystemExit("Coach smoke did not complete")


if __name__ == "__main__":
    main()
