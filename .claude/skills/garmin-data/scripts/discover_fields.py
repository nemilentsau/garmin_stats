#!/usr/bin/env python3
"""
Discover undocumented FIT message types and fields.

Scans all FIT files (or a specific type/day) and dumps full field schemas
for any message type. Use this when:
  - Adding a new metric and need to know what fields exist
  - A new FIT file type appears (e.g., new firmware)
  - The verify script reports DRIFT and you need to investigate
  - You want to explore what's inside an undocumented message type

Output is JSON-formatted, ready to paste into reference schema files.

Usage:
    cd backend && uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py [options]

Examples:
    # Discover ALL message types in WELLNESS files
    uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type WELLNESS

    # Discover a specific unknown message type
    uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type WELLNESS --message 233

    # Discover everything in METRICS files (entirely undocumented)
    uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type METRICS

    # Discover from a specific day
    uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type WELLNESS --day 2026-01-15

    # Scan ALL file types and dump summary
    uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --all
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.parser import decode_fit_file, get_files_by_day


def analyze_field(values: list) -> dict:
    """Analyze a list of field values and produce a schema description."""
    non_null = [v for v in values if v is not None]
    null_count = len(values) - len(non_null)

    if not non_null:
        return {
            "type": "unknown",
            "description": "All values null",
            "nullable": True,
            "total": len(values),
        }

    sample = non_null[0]
    python_type = type(sample).__name__

    # Map Python types to FIT-style types
    type_map = {
        "int": "int",
        "float": "float",
        "str": "string",
        "datetime": "datetime",
        "bool": "bool",
        "bytes": "bytes",
    }

    fit_type = type_map.get(python_type, python_type)

    result = {
        "type": fit_type,
        "total": len(values),
        "non_null": len(non_null),
    }

    if null_count > 0:
        result["nullable"] = True
        result["null_pct"] = round(null_count / len(values) * 100, 1)

    # Numeric stats
    if python_type in ("int", "float"):
        # Filter to only numeric values (some fields have mixed types)
        nums = [v for v in non_null if isinstance(v, (int, float))]
        if nums:
            result["min"] = min(nums)
            result["max"] = max(nums)
            if len(nums) > 1:
                result["mean"] = round(sum(nums) / len(nums), 2)
            unique = set(nums)
            if len(unique) <= 10:
                result["unique_values"] = sorted(unique)
        # Note mixed types
        non_nums = [v for v in non_null if not isinstance(v, (int, float))]
        if non_nums:
            result["mixed_types"] = True
            result["other_type_sample"] = repr(non_nums[0])[:60]

    # String/enum stats
    elif python_type == "str":
        unique = set(non_null)
        if len(unique) <= 20:
            result["unique_values"] = sorted(unique, key=str)
        else:
            result["unique_count"] = len(unique)
            result["sample_values"] = sorted(list(unique), key=str)[:5]

    # Datetime — show range
    elif hasattr(sample, "isoformat"):
        sorted_vals = sorted(non_null)
        result["earliest"] = sorted_vals[0].isoformat()
        result["latest"] = sorted_vals[-1].isoformat()

    # Always include a sample
    if hasattr(sample, "isoformat"):
        result["sample"] = sample.isoformat()
    elif isinstance(sample, bytes):
        result["sample"] = sample.hex()[:40]
    else:
        s = repr(sample)
        result["sample"] = s[:80] if len(s) > 80 else s

    return result


def discover_messages(
    files: list[Path],
    target_message: str | None = None,
) -> dict:
    """Discover all message types and fields in a list of FIT files."""
    # Collect values per message_type per field
    msg_fields: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    msg_counts: dict[str, int] = defaultdict(int)
    files_scanned = 0

    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            files_scanned += 1

            for msg_type, records in messages.items():
                if target_message and str(msg_type) != str(target_message):
                    continue
                msg_counts[str(msg_type)] += len(records)
                for record in records:
                    for field, value in record.items():
                        msg_fields[str(msg_type)][str(field)].append(value)
        except Exception as e:
            print(f"  WARN: Failed to decode {fit_file.name}: {e}", file=sys.stderr)

    # Build schema output
    result = {"_meta": {"files_scanned": files_scanned}}

    for msg_type in sorted(msg_fields.keys(), key=str):
        fields = msg_fields[msg_type]
        field_schemas = {}
        for field_name in sorted(fields.keys(), key=str):
            field_schemas[field_name] = analyze_field(fields[field_name])

        result[msg_type] = {
            "total_records": msg_counts[msg_type],
            "fields": field_schemas,
        }

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Discover FIT message types and fields"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Path to data directory",
    )
    parser.add_argument(
        "--file-type",
        help="FIT file type to scan (e.g., WELLNESS, METRICS, SLEEP_DATA)",
    )
    parser.add_argument(
        "--message",
        help="Specific message type to discover (e.g., 233, monitoring_mesgs)",
    )
    parser.add_argument("--day", help="Specific day to scan (YYYY-MM-DD)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all file types and dump summary",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=3,
        help="Max files to scan per type (default 3 for speed)",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"ERROR: Data directory not found: {args.data_dir}", file=sys.stderr)
        sys.exit(1)

    files_by_day = get_files_by_day(args.data_dir)

    if not args.file_type and not args.all:
        print("ERROR: Specify --file-type or --all", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if args.all:
        # Discover all file types
        all_types = set()
        for day_files in files_by_day.values():
            all_types.update(day_files.keys())

        print(f"Found file types: {sorted(all_types)}", file=sys.stderr)

        for file_type in sorted(all_types):
            files = []
            days = sorted(files_by_day.keys())
            mid = len(days) // 2
            for day in [days[0], days[mid], days[-1]]:
                files.extend(files_by_day[day].get(file_type, []))

            if not files:
                continue

            files = files[: args.max_files]
            print(f"\n--- {file_type} ({len(files)} files) ---", file=sys.stderr)
            result = discover_messages(files, args.message)
            # Print just the summary (message types and record counts)
            for msg_type, info in result.items():
                if msg_type == "_meta":
                    continue
                field_count = len(info["fields"])
                print(
                    f"  {msg_type}: {info['total_records']} records, {field_count} fields",
                    file=sys.stderr,
                )

        print("\nTo get full field details, re-run with --file-type <TYPE>", file=sys.stderr)
        return

    # Collect files for the specified type
    files = []
    if args.day:
        if args.day not in files_by_day:
            print(f"ERROR: Day {args.day} not found", file=sys.stderr)
            sys.exit(1)
        files = files_by_day[args.day].get(args.file_type, [])
    else:
        days = sorted(files_by_day.keys())
        # Sample from start, middle, end for representative coverage
        sample_days = [days[0], days[len(days) // 2], days[-1]]
        for day in sample_days:
            files.extend(files_by_day[day].get(args.file_type, []))

    files = files[: args.max_files]

    if not files:
        print(f"ERROR: No {args.file_type} files found", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {len(files)} {args.file_type} files...", file=sys.stderr)
    result = discover_messages(files, args.message)

    # Output as JSON to stdout (machine-readable, pasteable into schemas)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
