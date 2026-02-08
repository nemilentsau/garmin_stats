#!/usr/bin/env python3
"""
Verify reference schemas against real FIT file data.

Decodes one sample file per FIT type and compares the actual message
structures against the documented schemas in references/.

Reports:
  - DRIFT: field documented but not found in data (SDK change? firmware update?)
  - NEW:   field found in data but not in schema (undocumented, needs investigation)
  - OK:    field matches between schema and data

Usage:
    cd backend && uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py [--data-dir ../data]
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.parser import decode_fit_file, get_files_by_day


REFERENCES_DIR = SKILL_DIR / "references"

# Map FIT file type -> reference file -> message types to check
SCHEMA_MAP = {
    "WELLNESS": {
        "file": "wellness-messages.json",
        "messages": [
            "monitoring_mesgs",
            "stress_level_mesgs",
            "respiration_rate_mesgs",
            "spo2_data_mesgs",
            "monitoring_hr_data_mesgs",
        ],
    },
    "SLEEP_DATA": {
        "file": "sleep-messages.json",
        "messages": ["sleep_level_mesgs", "sleep_assessment_mesgs"],
    },
    "HRV_STATUS": {
        "file": "hrv-messages.json",
        "messages": ["hrv_value_mesgs", "hrv_status_summary_mesgs"],
    },
    "SKIN_TEMP": {
        "file": "skin-temp-messages.json",
        "messages": ["skin_temp_overnight_mesgs"],
    },
    "SLEEP_DISRUPTIONS": {
        "file": "sleep-disruptions-messages.json",
        "messages": [
            "sleep_disruption_overnight_severity_mesgs",
            "sleep_disruption_severity_period_mesgs",
        ],
    },
}


def load_schema(ref_file: str) -> dict:
    path = REFERENCES_DIR / ref_file
    with open(path) as f:
        return json.load(f)


def get_documented_fields(schema: dict, msg_type: str) -> tuple[set[str], set[str], set[str]]:
    """Extract documented field names from a schema entry.
    Returns (all_fields, rare_fields, acknowledged_unknown_fields)."""
    if msg_type not in schema:
        return set(), set(), set()
    entry = schema[msg_type]
    fields_dict = entry.get("fields", {})
    all_fields = set(fields_dict.keys())
    rare_fields = {k for k, v in fields_dict.items() if isinstance(v, dict) and v.get("rare")}
    # Parse acknowledged undocumented fields like "35 (int)" -> "35"
    acknowledged = set()
    for item in entry.get("fields_undocumented", []):
        field_name = item.split(" ")[0] if isinstance(item, str) else str(item)
        # Try int conversion since FIT SDK uses int keys for unknown fields
        try:
            acknowledged.add(int(field_name))
        except ValueError:
            acknowledged.add(field_name)
    # Also acknowledge fields in fields_discovered (discovered-but-unnamed SDK fields)
    for key in entry.get("fields_discovered", {}):
        try:
            acknowledged.add(int(key))
        except ValueError:
            acknowledged.add(key)
    return all_fields, rare_fields, acknowledged


# FIT metadata message types that exist in every file but aren't health data
FIT_METADATA_MESSAGES = {
    "file_id_mesgs",
    "file_creator_mesgs",
    "device_info_mesgs",
    "software_mesgs",
    "timestamp_correlation_mesgs",
}


def get_sample_file(files_by_day: dict, file_type: str) -> Path | None:
    """Find a sample file of the given type from the middle of the date range."""
    all_days = sorted(files_by_day.keys())
    if not all_days:
        return None
    # Pick from the middle of the range for a representative sample
    mid = len(all_days) // 2
    for offset in range(len(all_days)):
        for direction in [0, 1]:
            idx = mid + offset if direction == 0 else mid - offset
            if 0 <= idx < len(all_days):
                day = all_days[idx]
                files = files_by_day[day].get(file_type, [])
                if files:
                    return sorted(files)[0]
    return None


def extract_actual_fields(messages: list[dict]) -> dict[str, dict]:
    """Extract field names, sample values, and types from actual message data."""
    field_info = {}
    for msg in messages:
        for key, value in msg.items():
            if key not in field_info:
                field_info[key] = {
                    "type": type(value).__name__ if value is not None else "NoneType",
                    "sample": value,
                    "null_count": 0,
                    "total_count": 0,
                }
            field_info[key]["total_count"] += 1
            if value is None:
                field_info[key]["null_count"] += 1
            elif field_info[key]["type"] == "NoneType":
                # Update type if we previously only saw None
                field_info[key]["type"] = type(value).__name__
                field_info[key]["sample"] = value
    return field_info


def verify_file_type(
    file_type: str, schema_config: dict, files_by_day: dict
) -> list[dict]:
    """Verify all message types for a FIT file type. Returns list of findings."""
    findings = []
    schema = load_schema(schema_config["file"])

    sample_file = get_sample_file(files_by_day, file_type)
    if not sample_file:
        findings.append(
            {
                "level": "WARN",
                "file_type": file_type,
                "msg_type": "-",
                "detail": f"No {file_type} files found in data directory",
            }
        )
        return findings

    try:
        messages = decode_fit_file(sample_file)
    except Exception as e:
        findings.append(
            {
                "level": "ERROR",
                "file_type": file_type,
                "msg_type": "-",
                "detail": f"Failed to decode {sample_file.name}: {e}",
            }
        )
        return findings

    # Check each documented message type
    for msg_type in schema_config["messages"]:
        actual_msgs = messages.get(msg_type, [])
        documented_fields, rare_fields, acknowledged_unknown = get_documented_fields(schema, msg_type)

        if not actual_msgs:
            findings.append(
                {
                    "level": "WARN",
                    "file_type": file_type,
                    "msg_type": msg_type,
                    "detail": f"No messages found in sample file {sample_file.name}",
                }
            )
            continue

        actual_fields = extract_actual_fields(actual_msgs)
        actual_field_names = set(actual_fields.keys())

        # Fields in schema but not in data (DRIFT vs RARE)
        for field in sorted(documented_fields - actual_field_names, key=str):
            if field in rare_fields:
                findings.append(
                    {
                        "level": "OK",
                        "file_type": file_type,
                        "msg_type": msg_type,
                        "detail": f"Field '{field}' not in sample (marked rare — expected)",
                    }
                )
            else:
                findings.append(
                    {
                        "level": "DRIFT",
                        "file_type": file_type,
                        "msg_type": msg_type,
                        "detail": f"Field '{field}' documented but NOT found in data",
                    }
                )

        # Fields in data but not in schema (NEW)
        for field in sorted(actual_field_names - documented_fields, key=str):
            # Skip fields acknowledged as undocumented in the schema
            if field in acknowledged_unknown:
                continue
            info = actual_fields[field]
            sample_repr = repr(info["sample"])
            if len(sample_repr) > 60:
                sample_repr = sample_repr[:57] + "..."
            findings.append(
                {
                    "level": "NEW",
                    "file_type": file_type,
                    "msg_type": msg_type,
                    "detail": f"Field '{field}' in data but NOT in schema (type={info['type']}, sample={sample_repr}, null={info['null_count']}/{info['total_count']})",
                }
            )

        # Fields that match (OK)
        for field in sorted(documented_fields & actual_field_names, key=str):
            findings.append(
                {
                    "level": "OK",
                    "file_type": file_type,
                    "msg_type": msg_type,
                    "detail": f"Field '{field}' verified",
                }
            )

    # Check for message types in file but not in schema
    # Build set of acknowledged types (tracked messages + not_parsed + metadata)
    acknowledged_msg_types = set()
    for k, v in schema.items():
        if not isinstance(v, dict):
            continue
        if v.get("status") == "not_parsed" or k.startswith("$"):
            acknowledged_msg_types.add(k)
            # Also add the numeric ID for unknown_NNN entries (as both str and int)
            if k.startswith("unknown_"):
                num_str = k.split("_", 1)[1]
                acknowledged_msg_types.add(num_str)  # SDK returns string keys
                try:
                    acknowledged_msg_types.add(int(num_str))
                except ValueError:
                    pass
    for msg_type in messages:
        if msg_type not in schema_config["messages"] and messages[msg_type]:
            # Skip FIT metadata messages and acknowledged untracked types
            if msg_type in FIT_METADATA_MESSAGES or msg_type in acknowledged_msg_types:
                continue
            count = len(messages[msg_type])
            findings.append(
                {
                    "level": "NEW",
                    "file_type": file_type,
                    "msg_type": msg_type,
                    "detail": f"Message type exists in data ({count} records) but not tracked in schema",
                }
            )

    return findings


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Verify FIT schemas against real data")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Path to data directory",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show OK fields too"
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"ERROR: Data directory not found: {args.data_dir}")
        sys.exit(1)

    files_by_day = get_files_by_day(args.data_dir)
    print(f"Scanning {len(files_by_day)} days of data...\n")

    all_findings = []
    for file_type, schema_config in SCHEMA_MAP.items():
        findings = verify_file_type(file_type, schema_config, files_by_day)
        all_findings.extend(findings)

    # Print results grouped by level
    drift = [f for f in all_findings if f["level"] == "DRIFT"]
    new = [f for f in all_findings if f["level"] == "NEW"]
    warns = [f for f in all_findings if f["level"] == "WARN"]
    errors = [f for f in all_findings if f["level"] == "ERROR"]
    ok = [f for f in all_findings if f["level"] == "OK"]

    if errors:
        print("=== ERRORS (decode failures) ===")
        for f in errors:
            print(f"  [{f['file_type']}] {f['detail']}")
        print()

    if drift:
        print("=== DRIFT (schema says exists, data says no) ===")
        for f in drift:
            print(f"  [{f['file_type']}/{f['msg_type']}] {f['detail']}")
        print()

    if new:
        print("=== NEW (in data, not in schema) ===")
        for f in new:
            print(f"  [{f['file_type']}/{f['msg_type']}] {f['detail']}")
        print()

    if warns:
        print("=== WARNINGS ===")
        for f in warns:
            print(f"  [{f['file_type']}] {f['detail']}")
        print()

    if args.verbose and ok:
        print(f"=== OK ({len(ok)} fields verified) ===")
        for f in ok:
            print(f"  [{f['file_type']}/{f['msg_type']}] {f['detail']}")
        print()

    # Summary
    print("--- Summary ---")
    print(f"  Verified: {len(ok)} fields OK")
    print(f"  Drift:    {len(drift)} fields documented but missing from data")
    print(f"  New:      {len(new)} fields/messages in data but not in schema")
    print(f"  Warnings: {len(warns)}")
    print(f"  Errors:   {len(errors)}")

    if drift or errors:
        print("\nAction needed: DRIFT or ERRORS detected. Schemas may be out of date.")
        print("Run the discover script to get full field dumps for affected message types.")
        sys.exit(1)
    elif new:
        print("\nInfo: NEW undocumented fields found. Consider running discover script")
        print("and updating reference schemas if these fields are useful.")
        sys.exit(0)
    else:
        print("\nAll schemas verified against real data.")
        sys.exit(0)


if __name__ == "__main__":
    main()
