"""
Garmin FIT file parser service using official Garmin SDK.
"""

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from garmin_fit_sdk import Decoder, Stream


def decode_fit_file(file_path: Path) -> dict[str, list[dict]]:
    """Decode a FIT file and return messages as dict."""
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    return messages


def parse_datetime(dt: Any) -> str | None:
    """Convert datetime to ISO string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def get_available_days(data_dir: Path) -> list[str]:
    """Get list of available date directories."""
    if not data_dir.exists():
        return []
    return sorted([d.name for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("20")])


def get_files_by_day(data_dir: Path) -> dict[str, dict[str, list[Path]]]:
    """Group FIT files by date and type."""
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


def get_day_summary(data_dir: Path, date: str) -> dict:
    """Get summary for a specific day."""
    day_dir = data_dir / date
    if not day_dir.exists():
        return {"error": f"Day {date} not found"}

    files = list(day_dir.glob("*.fit"))
    file_types = defaultdict(int)

    for f in files:
        name_parts = f.stem.split("_")
        if len(name_parts) >= 2:
            file_type = "_".join(name_parts[1:])
        else:
            file_type = "UNKNOWN"
        file_types[file_type] += 1

    return {
        "date": date,
        "total_files": len(files),
        "file_types": dict(file_types),
        "total_size_kb": round(sum(f.stat().st_size for f in files) / 1024, 1),
    }


def parse_wellness_data(data_dir: Path, date: str | None = None) -> dict:
    """Parse wellness data from WELLNESS FIT files."""
    files_by_day = get_files_by_day(data_dir)

    if date:
        if date not in files_by_day:
            return {"error": f"Day {date} not found"}
        days_to_process = {date: files_by_day[date]}
    else:
        days_to_process = files_by_day

    result = {
        "days": [],
        "heart_rate": [],
        "stress": [],
        "spo2": [],
        "respiration": [],
        "activity": [],
        "steps_summary": [],
        "resting_hr": [],
    }

    for day, day_files in sorted(days_to_process.items()):
        wellness_files = day_files.get("WELLNESS", [])

        day_hr = []
        day_stress = []
        day_spo2 = []
        day_respiration = []
        day_activity = []
        day_steps = []
        day_resting_hr = []

        for fit_file in sorted(wellness_files):
            try:
                messages = decode_fit_file(fit_file)

                # Heart rate from monitoring
                for msg in messages.get("monitoring_mesgs", []):
                    if "heart_rate" in msg and msg["heart_rate"]:
                        ts = msg.get("timestamp")
                        day_hr.append({
                            "timestamp": parse_datetime(ts),
                            "value": msg["heart_rate"],
                        })

                # Activity data
                for msg in messages.get("monitoring_mesgs", []):
                    if "activity_type" in msg:
                        ts = msg.get("timestamp")
                        day_activity.append({
                            "timestamp": parse_datetime(ts),
                            "activity_type": str(msg.get("activity_type", "unknown")),
                            "intensity": msg.get("intensity"),
                            "steps": msg.get("steps"),
                            "calories": msg.get("active_calories"),
                            "distance": msg.get("distance"),
                        })

                # Steps aggregates
                for msg in messages.get("monitoring_mesgs", []):
                    if "steps" in msg and msg["steps"]:
                        ts = msg.get("timestamp")
                        day_steps.append({
                            "timestamp": parse_datetime(ts),
                            "steps": msg["steps"],
                            "distance": msg.get("distance"),
                            "calories": msg.get("active_calories"),
                        })

                # Stress
                for msg in messages.get("stress_level_mesgs", []):
                    ts = msg.get("stress_level_time")
                    value = msg.get("stress_level_value")
                    if value is not None and value >= 0:  # -1/-2 are invalid
                        day_stress.append({
                            "timestamp": parse_datetime(ts),
                            "value": value,
                        })

                # SpO2
                for msg in messages.get("spo2_data_mesgs", []):
                    ts = msg.get("timestamp")
                    value = msg.get("reading_spo2")
                    confidence = msg.get("reading_confidence")
                    if value:
                        day_spo2.append({
                            "timestamp": parse_datetime(ts),
                            "value": value,
                            "confidence": confidence,
                            "mode": str(msg.get("mode", "unknown")),
                        })

                # Respiration
                for msg in messages.get("respiration_rate_mesgs", []):
                    ts = msg.get("timestamp")
                    value = msg.get("respiration_rate")
                    if value is not None and value > 0:  # -1 is invalid
                        day_respiration.append({
                            "timestamp": parse_datetime(ts),
                            "value": value,
                        })

                # Resting HR
                for msg in messages.get("monitoring_hr_data_mesgs", []):
                    ts = msg.get("timestamp")
                    day_resting_hr.append({
                        "timestamp": parse_datetime(ts),
                        "resting_hr": msg.get("resting_heart_rate"),
                        "current_day_resting_hr": msg.get("current_day_resting_heart_rate"),
                    })

            except Exception as e:
                print(f"Error parsing {fit_file}: {e}")

        result["days"].append(day)
        result["heart_rate"].extend(day_hr)
        result["stress"].extend(day_stress)
        result["spo2"].extend(day_spo2)
        result["respiration"].extend(day_respiration)
        result["activity"].extend(day_activity)
        result["steps_summary"].extend(day_steps)
        result["resting_hr"].extend(day_resting_hr)

    return result


def parse_sleep_data(data_dir: Path, date: str | None = None) -> dict:
    """Parse sleep data from SLEEP_DATA FIT files."""
    files_by_day = get_files_by_day(data_dir)

    if date:
        if date not in files_by_day:
            return {"error": f"Day {date} not found"}
        days_to_process = {date: files_by_day[date]}
    else:
        days_to_process = files_by_day

    result = {
        "days": [],
        "sleep_levels": [],
        "sleep_assessments": [],
    }

    for day, day_files in sorted(days_to_process.items()):
        sleep_files = day_files.get("SLEEP_DATA", [])

        for fit_file in sorted(sleep_files):
            try:
                messages = decode_fit_file(fit_file)

                # Sleep levels (stages)
                for msg in messages.get("sleep_level_mesgs", []):
                    ts = msg.get("timestamp")
                    result["sleep_levels"].append({
                        "date": day,
                        "timestamp": parse_datetime(ts),
                        "level": str(msg.get("sleep_level", "unknown")),
                    })

                # Sleep assessment
                for msg in messages.get("sleep_assessment_mesgs", []):
                    result["sleep_assessments"].append({
                        "date": day,
                        "overall_score": msg.get("overall_sleep_score"),
                        "deep_sleep_score": msg.get("deep_sleep_score"),
                        "light_sleep_score": msg.get("light_sleep_score"),
                        "rem_sleep_score": msg.get("rem_sleep_score"),
                        "awake_time_score": msg.get("awake_time_score"),
                        "awakenings_count": msg.get("awakenings_count"),
                        "average_stress": msg.get("average_stress_during_sleep"),
                    })

            except Exception as e:
                print(f"Error parsing {fit_file}: {e}")

        result["days"].append(day)

    return result


def parse_hrv_data(data_dir: Path, date: str | None = None) -> dict:
    """Parse HRV data from HRV_STATUS FIT files."""
    files_by_day = get_files_by_day(data_dir)

    if date:
        if date not in files_by_day:
            return {"error": f"Day {date} not found"}
        days_to_process = {date: files_by_day[date]}
    else:
        days_to_process = files_by_day

    result = {
        "days": [],
        "hrv_values": [],
        "hrv_summaries": [],
    }

    for day, day_files in sorted(days_to_process.items()):
        hrv_files = day_files.get("HRV_STATUS", [])

        for fit_file in sorted(hrv_files):
            try:
                messages = decode_fit_file(fit_file)

                # Raw HRV values
                for msg in messages.get("hrv_value_mesgs", []):
                    ts = msg.get("timestamp")
                    value = msg.get("value")
                    if value:
                        result["hrv_values"].append({
                            "date": day,
                            "timestamp": parse_datetime(ts),
                            "value": value,
                        })

                # HRV summary
                for msg in messages.get("hrv_status_summary_mesgs", []):
                    result["hrv_summaries"].append({
                        "date": day,
                        "weekly_average": msg.get("weekly_average"),
                        "last_night_average": msg.get("last_night_average"),
                        "last_night_5_min_high": msg.get("last_night_5_min_high"),
                        "baseline_low_upper": msg.get("baseline_low_upper"),
                        "baseline_balanced_lower": msg.get("baseline_balanced_lower"),
                        "baseline_balanced_upper": msg.get("baseline_balanced_upper"),
                        "status": str(msg.get("status", "unknown")),
                    })

            except Exception as e:
                print(f"Error parsing {fit_file}: {e}")

        result["days"].append(day)

    return result


def get_overview_stats(data_dir: Path) -> dict:
    """Get overview statistics across all data."""
    wellness = parse_wellness_data(data_dir)
    sleep = parse_sleep_data(data_dir)
    hrv = parse_hrv_data(data_dir)

    # Calculate stats
    hr_values = [d["value"] for d in wellness["heart_rate"] if d["value"]]
    stress_values = [d["value"] for d in wellness["stress"] if d["value"]]
    spo2_values = [d["value"] for d in wellness["spo2"] if d["value"]]
    resp_values = [d["value"] for d in wellness["respiration"] if d["value"]]

    # Activity distribution
    activity_counts = defaultdict(int)
    for a in wellness["activity"]:
        activity_counts[a["activity_type"]] += 1

    return {
        "days_available": wellness["days"],
        "total_days": len(wellness["days"]),
        "heart_rate": {
            "total_readings": len(hr_values),
            "min": min(hr_values) if hr_values else None,
            "max": max(hr_values) if hr_values else None,
            "avg": round(sum(hr_values) / len(hr_values), 1) if hr_values else None,
        },
        "stress": {
            "total_readings": len(stress_values),
            "min": min(stress_values) if stress_values else None,
            "max": max(stress_values) if stress_values else None,
            "avg": round(sum(stress_values) / len(stress_values), 1) if stress_values else None,
        },
        "spo2": {
            "total_readings": len(spo2_values),
            "min": min(spo2_values) if spo2_values else None,
            "max": max(spo2_values) if spo2_values else None,
            "avg": round(sum(spo2_values) / len(spo2_values), 1) if spo2_values else None,
        },
        "respiration": {
            "total_readings": len(resp_values),
            "min": round(min(resp_values), 1) if resp_values else None,
            "max": round(max(resp_values), 1) if resp_values else None,
            "avg": round(sum(resp_values) / len(resp_values), 1) if resp_values else None,
        },
        "activity_distribution": dict(activity_counts),
        "sleep_scores": [
            {"date": s["date"], "score": s["overall_score"]}
            for s in sleep["sleep_assessments"]
        ],
        "hrv_summaries": hrv["hrv_summaries"],
    }
