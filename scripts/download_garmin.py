#!/usr/bin/env python3
"""Download daily wellness FIT files from Garmin Connect.

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

    # Download yesterday (default):
    cd backend && uv run python ../scripts/download_garmin.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

TOKEN_DIR = os.environ.get("GARMINTOKENS", "~/.garminconnect")
DATA_DIR = Path(os.environ.get(
    "GARMIN_DATA_DIR",
    str(Path(__file__).resolve().parent.parent / "data" / "garmin_health_stats"),
))
DOWNLOAD_SERVICE_URL = "/download-service/files"


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


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download daily wellness FIT files from Garmin Connect"
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
    args = parser.parse_args()

    # Login mode
    if args.login:
        login_interactive()
        print("Login successful! You can now download data.")
        return

    # Determine dates to download
    if args.date:
        dates = [args.date]
    elif args.from_date:
        end = args.to_date or date.today()
        if args.from_date > end:
            print("--from must be before --to", file=sys.stderr)
            sys.exit(1)
        dates = []
        current = args.from_date
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
    else:
        # Default: yesterday
        dates = [date.today() - timedelta(days=1)]

    # Remove existing if --force
    if args.force:
        for day in dates:
            zip_path = DATA_DIR / f"{day.strftime('%Y-%m-%d')}.zip"
            if zip_path.exists():
                zip_path.unlink()

    client = init_client()
    print(f"Downloading {len(dates)} day(s) to {DATA_DIR}")

    downloaded = 0
    failed = 0
    skipped = 0

    for i, day in enumerate(dates):
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
