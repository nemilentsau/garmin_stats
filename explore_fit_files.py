#!/usr/bin/env python3
"""
Garmin FIT File Explorer

This script analyzes Garmin FIT files using the official Garmin FIT SDK.
Designed for Garmin Epix Gen 2 watch health data exports.

Usage:
    uv run python explore_fit_files.py [--data-dir DATA_DIR] [--summary-only] [--by-day] [--type TYPE]
"""

import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

try:
    from garmin_fit_sdk import Decoder, Stream
except ImportError:
    print("Error: garmin-fit-sdk library not installed.")
    print("Install it with: uv pip install garmin-fit-sdk")
    exit(1)


def get_fit_files_by_day(data_dir: Path) -> dict[str, dict[str, list[Path]]]:
    """Group FIT files by date directory, then by type."""
    files_by_day = defaultdict(lambda: defaultdict(list))

    for fit_file in data_dir.rglob("*.fit"):
        date_dir = fit_file.parent.name
        name_parts = fit_file.stem.split("_")
        if len(name_parts) >= 2:
            file_type = "_".join(name_parts[1:])
        else:
            file_type = "UNKNOWN"
        files_by_day[date_dir][file_type].append(fit_file)

    return {k: dict(v) for k, v in sorted(files_by_day.items())}


def decode_fit_file(file_path: Path) -> dict:
    """Decode a FIT file using the official Garmin SDK."""
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    return messages, errors


def analyze_fit_file(file_path: Path) -> dict:
    """Analyze a single FIT file and return its structure."""
    result = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "date": file_path.parent.name,
        "file_size_kb": file_path.stat().st_size / 1024,
        "message_types": {},
        "fields_by_message": {},
        "sample_data": {},
        "time_range": {"start": None, "end": None},
        "errors": [],
    }

    try:
        messages, errors = decode_fit_file(file_path)
        result["errors"] = errors

        for msg_type, records in messages.items():
            msg_name = str(msg_type)
            result["message_types"][msg_name] = len(records)

            # Collect all field names across all records of this type
            all_fields = set()
            for record in records:
                all_fields.update(str(k) for k in record.keys())

                # Track time range from timestamp fields
                for ts_field in ["timestamp", "stress_level_time"]:
                    if ts_field in record and record[ts_field]:
                        ts = record[ts_field]
                        if hasattr(ts, "timestamp"):  # datetime-like
                            if result["time_range"]["start"] is None or ts < result["time_range"]["start"]:
                                result["time_range"]["start"] = ts
                            if result["time_range"]["end"] is None or ts > result["time_range"]["end"]:
                                result["time_range"]["end"] = ts

            result["fields_by_message"][msg_name] = sorted(all_fields)

            # Sample first record
            if records:
                result["sample_data"][msg_name] = {
                    str(k): str(v)[:100] for k, v in records[0].items()
                }

    except Exception as e:
        result["errors"].append(str(e))

    return result


def print_day_summary(date: str, files_by_type: dict[str, list[Path]], analyses: list[dict]):
    """Print summary for a single day."""
    print(f"\n{'─' * 80}")
    print(f" 📅 {date}")
    print(f"{'─' * 80}")

    total_files = sum(len(files) for files in files_by_type.values())
    total_size = sum(a["file_size_kb"] for a in analyses)

    all_starts = [a["time_range"]["start"] for a in analyses if a["time_range"]["start"]]
    all_ends = [a["time_range"]["end"] for a in analyses if a["time_range"]["end"]]

    print(f"   Files: {total_files} | Size: {total_size:.1f} KB")
    if all_starts and all_ends:
        print(f"   Time Range: {min(all_starts)} to {max(all_ends)}")

    print(f"\n   File Types:")
    for file_type, files in sorted(files_by_type.items()):
        type_analyses = [a for a in analyses if a["file_name"].endswith(f"_{file_type}.fit")]
        type_size = sum(a["file_size_kb"] for a in type_analyses)
        print(f"      • {file_type}: {len(files)} file(s), {type_size:.1f} KB")


def print_analysis(file_type: str, analyses: list[dict]):
    """Print formatted analysis for a file type."""
    print("\n" + "=" * 80)
    print(f" {file_type} FILES ")
    print("=" * 80)

    for analysis in analyses:
        print(f"\n📁 File: {analysis['file_name']} ({analysis['date']})")
        print(f"   Size: {analysis['file_size_kb']:.2f} KB")

        if analysis["errors"]:
            print(f"   ⚠️  Errors: {analysis['errors']}")

        if analysis["time_range"]["start"]:
            print(f"   Time Range: {analysis['time_range']['start']} to {analysis['time_range']['end']}")

        print(f"\n   Message Types ({len(analysis['message_types'])} types):")
        for msg_type, count in sorted(analysis["message_types"].items(), key=lambda x: str(x[0])):
            print(f"      - {msg_type}: {count} records")

        print(f"\n   Fields by Message Type:")
        for msg_type, fields in sorted(analysis["fields_by_message"].items(), key=lambda x: str(x[0])):
            named_fields = [f for f in fields if not f.isdigit()]
            unknown_fields = [f for f in fields if f.isdigit()]

            print(f"      [{msg_type}]")
            if named_fields:
                print(f"         Known: {', '.join(named_fields)}")
            if unknown_fields:
                print(f"         Unknown: {', '.join(unknown_fields)}")


def generate_summary(files_by_day: dict, all_analyses: dict):
    """Generate a summary of all file types and their data."""
    print("\n" + "=" * 80)
    print(" SUMMARY: GARMIN FIT FILE ANALYSIS ")
    print("=" * 80)

    # Per-day breakdown
    print("\n📅 Data by Day:")
    for date, day_files in sorted(files_by_day.items()):
        total = sum(len(f) for f in day_files.values())
        types = ", ".join(f"{t}({len(f)})" for t, f in sorted(day_files.items()))
        print(f"   {date}: {total} files - {types}")

    # Aggregate message types across all files
    print("\n📊 Message Types (across all files):")

    all_msg_types = defaultdict(lambda: {"count": 0, "fields": set()})

    for file_type, analyses in all_analyses.items():
        for analysis in analyses:
            for msg_type, count in analysis["message_types"].items():
                all_msg_types[msg_type]["count"] += count
            for msg_type, fields in analysis["fields_by_message"].items():
                all_msg_types[msg_type]["fields"].update(fields)

    # Separate named vs unknown message types
    named_msgs = {k: v for k, v in all_msg_types.items() if not str(k).isdigit()}
    unknown_msgs = {k: v for k, v in all_msg_types.items() if str(k).isdigit()}

    print("\n   Named Message Types:")
    for msg_type, data in sorted(named_msgs.items(), key=lambda x: -x[1]["count"]):
        fields = data["fields"]
        named_fields = [f for f in fields if not str(f).isdigit()]
        print(f"      📈 {msg_type}: {data['count']} records")
        if named_fields:
            print(f"         Fields: {', '.join(sorted(named_fields)[:10])}")

    if unknown_msgs:
        print("\n   Unknown Message Types (numeric IDs):")
        for msg_type, data in sorted(unknown_msgs.items(), key=lambda x: -x[1]["count"]):
            print(f"      ❓ {msg_type}: {data['count']} records")


def main():
    parser = argparse.ArgumentParser(description="Explore Garmin FIT files")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing FIT files (default: data)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only show summary, skip detailed analysis",
    )
    parser.add_argument(
        "--by-day",
        action="store_true",
        help="Show breakdown by day",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Only analyze specific file type (e.g., WELLNESS, METRICS)",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"Error: Data directory '{args.data_dir}' not found")
        return 1

    print("🔍 Scanning for FIT files (using official Garmin SDK)...")
    files_by_day = get_fit_files_by_day(args.data_dir)

    if not files_by_day:
        print("No FIT files found!")
        return 1

    total_files = sum(sum(len(f) for f in day.values()) for day in files_by_day.values())
    total_types = len(set(t for day in files_by_day.values() for t in day.keys()))
    print(f"   Found {total_files} FIT files in {total_types} categories across {len(files_by_day)} days")

    # Filter by type if specified
    if args.type:
        args.type = args.type.upper()
        files_by_day = {
            date: {t: files for t, files in day.items() if t == args.type}
            for date, day in files_by_day.items()
        }
        files_by_day = {k: v for k, v in files_by_day.items() if v}

    print("\n🔬 Analyzing files...")
    all_analyses = defaultdict(list)

    for date, day_files in sorted(files_by_day.items()):
        for file_type, files in sorted(day_files.items()):
            for fit_file in sorted(files):
                print(f"   Processing: {fit_file.parent.name}/{fit_file.name}")
                analysis = analyze_fit_file(fit_file)
                all_analyses[file_type].append(analysis)

    # Show by-day summary if requested
    if args.by_day:
        print("\n" + "=" * 80)
        print(" PER-DAY BREAKDOWN ")
        print("=" * 80)

        for date, day_files in sorted(files_by_day.items()):
            day_analyses = []
            for file_type, files in day_files.items():
                for f in files:
                    for a in all_analyses.get(file_type, []):
                        if a["file_name"] == f.name:
                            day_analyses.append(a)
            if day_analyses:
                print_day_summary(date, day_files, day_analyses)

    # Print detailed analysis unless summary-only
    if not args.summary_only:
        for file_type, analyses in sorted(all_analyses.items()):
            print_analysis(file_type, analyses)

    # Always print summary
    generate_summary(files_by_day, dict(all_analyses))

    print("\n✅ Analysis complete!")
    return 0


if __name__ == "__main__":
    exit(main())
