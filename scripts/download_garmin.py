#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Download Garmin wellness archives or activity FIT files from Garmin Connect.

Usage:
    # Prepare backend-managed env once:
    #   cd backend && uv sync --python 3.14
    # Then run this script from backend so dependencies come from backend/pyproject.toml:
    #   cd backend && uv run python ../scripts/download_garmin.py [options]
    #
    # First-time login (saves tokens to ~/.garminconnect):
    cd backend && uv run python ../scripts/download_garmin.py --login

    # Download a specific date:
    cd backend && uv run python ../scripts/download_garmin.py --date 2026-02-08

    # Download a date range:
    cd backend && uv run python ../scripts/download_garmin.py --from 2026-02-08 --to 2026-02-15

    # Download yesterday's wellness archive (default):
    cd backend && uv run python ../scripts/download_garmin.py

    # Download tracked activity FIT files for a specific date:
    cd backend && uv run python ../scripts/download_garmin.py --activities --date 2026-06-27

    # Download tracked activity FIT files across the existing health-data range:
    cd backend && uv run python ../scripts/download_garmin.py --activities --health-range
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.domains.garmin_sync.infra.activity_files import (
    existing_activity_stem,
    remove_activity_outputs,
    store_activity_payload,
)
from garminconnect import Garmin

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

TOKEN_DIR = os.environ.get("GARMINTOKENS", "~/.garminconnect")
DOWNLOAD_SERVICE_URL = "/download-service/files"
MINIMUM_ACTIVITY_BYTES = 100
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\.zip)?$")


def _derive_shared_checkout_root(repo_root: Path) -> Path | None:
    """Derive the shared checkout root from git metadata when running in a worktree."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    common_dir_raw = proc.stdout.strip()
    if not common_dir_raw:
        return None

    common_dir = Path(common_dir_raw).resolve()
    if common_dir.name == ".git":
        return common_dir.parent

    for parent in [common_dir, *common_dir.parents]:
        if parent.name == ".git":
            return parent.parent

    return None


def _default_data_dir(name: str) -> Path:
    """Resolve default data paths for normal checkouts and linked worktrees."""
    local_data_root = REPO_ROOT / "data"
    if local_data_root.exists():
        return local_data_root / name

    shared_root = _derive_shared_checkout_root(REPO_ROOT)
    if shared_root and shared_root != REPO_ROOT and (shared_root / "data").exists():
        return shared_root / "data" / name

    return local_data_root / name


DATA_DIR = Path(os.environ.get("GARMIN_DATA_DIR", str(_default_data_dir("garmin_health_stats"))))
ACTIVITY_DATA_DIR = Path(os.environ.get(
    "GARMIN_ACTIVITY_DATA_DIR",
    str(_default_data_dir("garmin_activities")),
))


def init_client() -> Garmin:
    """Create a Garmin client using saved tokens."""
    token_path = os.path.expanduser(TOKEN_DIR)
    if not os.path.isdir(token_path):
        print(
            f"No tokens found at {token_path}. Run with --login first.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = Garmin()
    client.login(token_path)
    return client


def login_interactive() -> Garmin:
    """Perform interactive login and save tokens."""
    import shutil

    email = os.environ.get("GARMIN_EMAIL") or input("Garmin email: ")
    password = os.environ.get("GARMIN_PASSWORD") or input("Garmin password: ")
    token_path = os.path.expanduser(TOKEN_DIR)

    # Clear stale tokens that may cause OAuth refresh errors
    if os.path.isdir(token_path):
        shutil.rmtree(token_path)
        print(f"Cleared stale tokens at {token_path}")

    client = Garmin(email, password, prompt_mfa=_prompt_mfa)
    client.login()

    os.makedirs(token_path, exist_ok=True)
    client.garth.dump(token_path)
    os.chmod(token_path, 0o700)
    print(f"Tokens saved to {token_path}")
    return client


def _prompt_mfa() -> str:
    """Prompt user for MFA code."""
    return input("Enter MFA/2FA code: ")


def download_day(client: Garmin, day: date) -> Path | None:
    """Download wellness FIT files for a single day.

    Returns the path to the saved zip, or None if no data.
    """
    date_str = day.strftime("%Y-%m-%d")
    zip_path = DATA_DIR / f"{date_str}.zip"

    if zip_path.exists():
        print(f"  {date_str}: already exists, skipping")
        return zip_path

    url = f"{DOWNLOAD_SERVICE_URL}/wellness/{date_str}"
    print(f"  {date_str}: downloading...", end=" ", flush=True)

    try:
        data = client.download(url)
    except Exception as e:
        print(f"FAILED ({e})")
        return None

    if not data or len(data) < 100:
        print("no data available")
        return None

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(data)
    print(f"OK ({len(data):,} bytes)")
    return zip_path


def download_activity_files(
    client: Garmin,
    day: date,
    *,
    activity_type: str | None,
    force: bool,
) -> tuple[int, int, int]:
    """Download original activity FIT payloads for one Garmin Connect activity date."""
    date_str = day.strftime("%Y-%m-%d")
    day_dir = ACTIVITY_DATA_DIR / date_str
    print(f"  {date_str}: listing activities...", end=" ", flush=True)

    try:
        activities = client.get_activities_by_date(
            date_str,
            date_str,
            activitytype=activity_type,
            sortorder="asc",
        )
    except Exception as e:
        print(f"FAILED ({e})")
        return 0, 0, 1

    if not activities:
        print("none")
        return 0, 0, 0

    print(f"{len(activities)} found")
    downloaded = 0
    skipped = 0
    failed = 0

    for index, activity in enumerate(activities):
        activity_id = activity.get("activityId")
        if not activity_id:
            print("    missing activityId, skipping")
            failed += 1
            continue

        activity_id_str = str(activity_id)
        name = activity.get("activityName") or "(unnamed)"
        existing_stem = existing_activity_stem(day_dir, activity_id_str)

        if existing_stem and not force:
            print(f"    {existing_stem}: already exists ({name})")
            skipped += 1
            continue

        print(f"    {activity_id_str}: downloading ({name})...", end=" ", flush=True)
        try:
            payload = client.download_activity(
                activity_id_str,
                Garmin.ActivityDownloadFormat.ORIGINAL,
            )
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1
            continue

        if not payload or len(payload) < MINIMUM_ACTIVITY_BYTES:
            print("no activity payload")
            failed += 1
            continue

        if force and existing_stem:
            remove_activity_outputs(day_dir, existing_stem)

        try:
            extracted = store_activity_payload(day_dir, activity_id_str, activity, payload)
        except ValueError as e:
            print(f"FAILED ({e})")
            failed += 1
            continue

        print(f"OK ({len(payload):,} bytes, {len(extracted)} FIT)")
        downloaded += 1

        if index < len(activities) - 1:
            time.sleep(1)

    return downloaded, skipped, failed


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def health_data_date_range(data_dir: Path) -> tuple[date, date]:
    """Return the inclusive min/max date range represented by health archives."""
    dates: set[date] = set()
    if not data_dir.exists():
        raise ValueError(f"health data directory does not exist: {data_dir}")

    for entry in data_dir.iterdir():
        if not DATE_PATTERN.match(entry.name):
            continue
        date_text = entry.name.removesuffix(".zip")
        try:
            dates.add(parse_date(date_text))
        except ValueError:
            continue

    if not dates:
        raise ValueError(f"no health data dates found in {data_dir}")

    return min(dates), max(dates)


def date_range(start: date, end: date) -> list[date]:
    """Build an inclusive list of dates."""
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Garmin wellness archives or activity FIT files"
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Perform interactive login and save tokens",
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        help="Download a specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=parse_date,
        help="Start of date range (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=parse_date,
        help="End of date range (YYYY-MM-DD), inclusive",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if zip already exists",
    )
    parser.add_argument(
        "--activities",
        action="store_true",
        help="Download tracked activity FIT files instead of wellness archives",
    )
    parser.add_argument(
        "--activity-type",
        help=(
            "Optional Garmin activity type filter for --activities "
            "(for example running, cycling, walking, other)"
        ),
    )
    parser.add_argument(
        "--health-range",
        action="store_true",
        help=(
            "With --activities, download the inclusive date range represented by "
            "existing health data archives"
        ),
    )
    args = parser.parse_args()

    # Login mode
    if args.login:
        login_interactive()
        print("Login successful! You can now download data.")
        return

    if args.health_range and not args.activities:
        print("--health-range requires --activities", file=sys.stderr)
        sys.exit(1)
    if args.health_range and (args.date or args.from_date or args.to_date):
        print("--health-range cannot be combined with --date, --from, or --to", file=sys.stderr)
        sys.exit(1)

    # Determine dates to download
    if args.health_range:
        try:
            start, end = health_data_date_range(DATA_DIR)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        dates = date_range(start, end)
        print(f"Resolved health data range from {DATA_DIR}: {start} through {end}")
    elif args.date:
        dates = [args.date]
    elif args.from_date:
        end = args.to_date or date.today()
        if args.from_date > end:
            print("--from must be before --to", file=sys.stderr)
            sys.exit(1)
        dates = date_range(args.from_date, end)
    else:
        # Default: yesterday
        dates = [date.today() - timedelta(days=1)]

    if args.activity_type and not args.activities:
        print("--activity-type requires --activities", file=sys.stderr)
        sys.exit(1)

    # Remove existing wellness archives if --force. Activity files are removed per activity.
    if args.force and not args.activities:
        for day in dates:
            zip_path = DATA_DIR / f"{day.strftime('%Y-%m-%d')}.zip"
            if zip_path.exists():
                zip_path.unlink()

    client = init_client()
    if args.activities:
        print(f"Downloading activity FIT files for {len(dates)} day(s) to {ACTIVITY_DATA_DIR}")
    else:
        print(f"Downloading {len(dates)} wellness day(s) to {DATA_DIR}")

    downloaded = 0
    failed = 0
    skipped = 0

    for i, day in enumerate(dates):
        if args.activities:
            day_downloaded, day_skipped, day_failed = download_activity_files(
                client,
                day,
                activity_type=args.activity_type,
                force=args.force,
            )
            downloaded += day_downloaded
            skipped += day_skipped
            failed += day_failed
        else:
            result = download_day(client, day)
            if result and result.exists():
                downloaded += 1
            elif result is None:
                failed += 1
            else:
                skipped += 1

        # Be nice to Garmin servers
        if i < len(dates) - 1:
            time.sleep(1)

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
