#!/usr/bin/env python3
"""Morning self-report CLI.

Run once each morning. Asks a short set of questions about yesterday's
behavior and this morning's subjective sleep quality. Persists two artifacts:

  data/personal/self_report/YYYY-MM-DD.json   (one file per day, structured)
  data/personal/self_report.csv               (single flat table, rebuilt
                                               from the JSON files on every
                                               run — never inconsistent)

Date = today by default (represents the night you just finished).
Override with --date YYYY-MM-DD for backfilling a missed day.

Fields collected (all optional — press Enter to skip):
  1. caffeine_cups          integer    cups of coffee/tea yesterday
  2. alcohol_drinks         integer    alcoholic drinks yesterday
  3. last_meal_time         HH:MM      time of yesterday's last meal
  4. screen_time_before_bed integer    minutes of screen time right before bed
  5. physical_activity_min  integer    minutes of exercise yesterday
  6. stress_1_5             int 1-5    perceived stress yesterday evening
  7. planned_bedtime        HH:MM      what time you planned to go to bed
  8. actual_bedtime         HH:MM      what time you actually went to bed
  9. subjective_sleep_1_5   int 1-5    how you feel about last night's sleep
                                       (this is the sanity-check reference
                                       against the model's good/poor label)
"""

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSONAL_DIR = PROJECT_ROOT / "data" / "personal"
JSON_DIR = PERSONAL_DIR / "self_report"
CSV_PATH = PERSONAL_DIR / "self_report.csv"

# Column order in the CSV
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

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _prompt(label: str, hint: str = "") -> str:
    """Prompt the user. Return the raw string (may be empty)."""
    suffix = f" [{hint}]" if hint else ""
    return input(f"  {label}{suffix}: ").strip()


def ask_int(label: str, hint: str = "", min_val: int | None = None,
            max_val: int | None = None) -> int | None:
    """Prompt for an integer. Empty = skip. Loops until valid."""
    while True:
        raw = _prompt(label, hint)
        if raw == "":
            return None
        try:
            v = int(raw)
        except ValueError:
            print("    -> not a whole number, try again (or Enter to skip)")
            continue
        if min_val is not None and v < min_val:
            print(f"    -> must be >= {min_val}")
            continue
        if max_val is not None and v > max_val:
            print(f"    -> must be <= {max_val}")
            continue
        return v


def ask_time(label: str, hint: str = "HH:MM") -> str | None:
    """Prompt for a HH:MM time. Empty = skip. Loops until valid."""
    while True:
        raw = _prompt(label, hint)
        if raw == "":
            return None
        if TIME_RE.match(raw):
            # Normalize to zero-padded HH:MM
            h, m = raw.split(":")
            return f"{int(h):02d}:{m}"
        print("    -> expected HH:MM (e.g. 23:30), try again (or Enter to skip)")


# ---------------------------------------------------------------------------
# Core report logic
# ---------------------------------------------------------------------------

def collect_answers() -> dict:
    """Walk through the 9 prompts and return the structured record."""
    print()
    print("Yesterday's behavior")
    print("-" * 40)
    caffeine = ask_int("Caffeinated drinks yesterday", "cups, integer", 0, 20)
    alcohol = ask_int("Alcoholic drinks yesterday", "drinks, integer", 0, 20)
    last_meal = ask_time("Time of yesterday's last meal")
    screen_time = ask_int("Screen time right before bed", "minutes", 0, 600)
    activity = ask_int("Physical activity yesterday", "minutes of exercise",
                       0, 600)
    stress = ask_int("Perceived stress yesterday evening",
                     "1 (very low) .. 5 (very high)", 1, 5)

    print()
    print("Bedtime")
    print("-" * 40)
    planned_bed = ask_time("Planned bedtime")
    actual_bed = ask_time("Actual bedtime")

    print()
    print("This morning")
    print("-" * 40)
    subjective = ask_int("How did you sleep?",
                         "1 (terrible) .. 5 (great)", 1, 5)

    return {
        "caffeine_cups": caffeine,
        "alcohol_drinks": alcohol,
        "last_meal_time": last_meal,
        "screen_time_before_bed_min": screen_time,
        "physical_activity_min": activity,
        "stress_1_5": stress,
        "planned_bedtime": planned_bed,
        "actual_bedtime": actual_bed,
        "subjective_sleep_1_5": subjective,
    }


def summarize(record: dict) -> None:
    """Print a review table before saving."""
    print()
    print("Summary")
    print("-" * 40)
    for key, value in record.items():
        display = value if value is not None else "(skipped)"
        print(f"  {key:30s}  {display}")
    print()


def confirm(prompt: str, default_yes: bool = True) -> bool:
    """Yes/no prompt. Empty = default."""
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
        if raw == "":
            return default_yes
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  -> please answer y or n")


def write_json(target_date: date, record: dict) -> Path:
    """Write (or overwrite) the per-day JSON file."""
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    path = JSON_DIR / f"{target_date.isoformat()}.json"
    payload = {
        "date": target_date.isoformat(),
        "filled_at": datetime.now().isoformat(timespec="seconds"),
        **record,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def rebuild_csv() -> Path:
    """Rebuild the flat CSV from all JSON files. Idempotent."""
    PERSONAL_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for json_path in sorted(JSON_DIR.glob("*.json")):
        with json_path.open(encoding="utf-8") as f:
            data = json.load(f)
        rows.append({k: data.get(k, "") for k in CSV_FIELDS})

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return CSV_PATH


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument(
        "--date", "-d",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Target date in YYYY-MM-DD format (default: today). "
             "The date represents the morning you woke up.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    target_date = args.date

    print()
    print("=" * 50)
    print(f"  Morning self-report — {target_date.isoformat()}")
    print("=" * 50)
    print("  Press Enter to skip any question.")

    # Handle "already filled today" case
    json_path = JSON_DIR / f"{target_date.isoformat()}.json"
    if json_path.exists():
        print()
        print(f"  A report for {target_date.isoformat()} already exists.")
        if not confirm("  Overwrite?", default_yes=False):
            print("  Aborted. Existing file was not touched.")
            return 0

    record = collect_answers()
    summarize(record)

    if not confirm("Save this report?", default_yes=True):
        print("Discarded. Nothing was written.")
        return 0

    json_out = write_json(target_date, record)
    csv_out = rebuild_csv()

    print()
    print(f"  Wrote {json_out.relative_to(PROJECT_ROOT)}")
    print(f"  Rebuilt {csv_out.relative_to(PROJECT_ROOT)}")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Interrupted. Nothing was saved.")
        sys.exit(130)
