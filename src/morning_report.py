#!/usr/bin/env python3
"""Morning self-report. Run every morning, answer the questions, save to disk."""

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = PROJECT_ROOT / "data" / "personal" / "self_report"
CSV_PATH = PROJECT_ROOT / "data" / "personal" / "self_report.csv"

# field order used in the output CSV
CSV_FIELDS = [
    "date",
    "caffeine_cups",
    "alcohol_drinks",
    "last_meal_time",
    "screen_time_before_bed_min",
    "physical_activity_min",
    "stress_1_5",
    "planned_bedtime",
    "actual_bedtime",
    "subjective_sleep_1_5",
    "filled_at",
]

TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def ask_int(label, hint, lo=None, hi=None):
    """Ask for an integer. Blank = skip (returns None). Loops until valid."""
    while True:
        raw = input(f"  {label} [{hint}]: ").strip()
        if raw == "":
            return None
        try:
            n = int(raw)
        except ValueError:
            print("    not a number, try again")
            continue
        if lo is not None and n < lo:
            print(f"    must be >= {lo}")
            continue
        if hi is not None and n > hi:
            print(f"    must be <= {hi}")
            continue
        return n


def ask_time(label):
    """Ask for a HH:MM time. Blank = skip."""
    while True:
        raw = input(f"  {label} [HH:MM]: ").strip()
        if raw == "":
            return None
        if TIME_PATTERN.match(raw):
            h, m = raw.split(":")
            return f"{int(h):02d}:{m}"  # pad hour so sort order works later
        print("    expected format HH:MM")


def ask_yes_no(prompt, default_yes=True):
    suffix = "[Y/n]" if default_yes else "[y/N]"
    raw = input(f"{prompt} {suffix} ").strip().lower()
    if raw == "":
        return default_yes
    return raw in ("y", "yes")


def rebuild_csv():
    """Rebuild the CSV from every JSON file. Simpler than appending."""
    rows = []
    for p in sorted(JSON_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        rows.append({field: data.get(field, "") for field in CSV_FIELDS})
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Morning self-report")
    parser.add_argument("--date", "-d", default=date.today().isoformat(),
                        help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    json_path = JSON_DIR / f"{target_date.isoformat()}.json"

    print()
    print(f"Morning self-report — {target_date}")
    print("Press Enter to skip any question.")
    print()

    if json_path.exists():
        if not ask_yes_no(f"A report for {target_date} already exists. Overwrite?",
                          default_yes=False):
            print("Aborted.")
            return

    # yesterday's behaviour
    print("Yesterday")
    caffeine = ask_int("Caffeine", "cups", 0, 20)
    alcohol = ask_int("Alcohol", "drinks", 0, 20)
    last_meal = ask_time("Time of last meal")
    screen = ask_int("Screen time before bed", "minutes", 0, 600)
    activity = ask_int("Physical activity", "minutes", 0, 600)
    stress = ask_int("Stress yesterday evening", "1=low .. 5=high", 1, 5)

    # bedtime
    print()
    print("Bedtime")
    planned = ask_time("Planned bedtime")
    actual = ask_time("Actual bedtime")

    # this morning
    print()
    print("This morning")
    subj = ask_int("How did you sleep?", "1=terrible .. 5=great", 1, 5)

    record = {
        "date": target_date.isoformat(),
        "filled_at": datetime.now().isoformat(timespec="seconds"),
        "caffeine_cups": caffeine,
        "alcohol_drinks": alcohol,
        "last_meal_time": last_meal,
        "screen_time_before_bed_min": screen,
        "physical_activity_min": activity,
        "stress_1_5": stress,
        "planned_bedtime": planned,
        "actual_bedtime": actual,
        "subjective_sleep_1_5": subj,
    }

    # review before saving
    print()
    print("Summary:")
    for k, v in record.items():
        if k in ("date", "filled_at"):
            continue
        print(f"  {k}: {v if v is not None else '(skipped)'}")
    print()

    if not ask_yes_no("Save?"):
        print("Discarded.")
        return

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    rebuild_csv()
    print(f"Saved {json_path.name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)