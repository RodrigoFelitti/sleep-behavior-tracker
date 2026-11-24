import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "data" / "personal" / "self_report"
CSV_PATH = ROOT / "data" / "personal" / "self_report.csv"

FIELDS = [
    "date", "caffeine_cups", "alcohol_drinks", "last_meal_time",
    "screen_time_before_bed_min", "physical_activity_min", "stress_1_5",
    "planned_bedtime", "actual_bedtime", "subjective_sleep_1_5", "filled_at",
]

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def ask_int(label, hint, lo=None, hi=None):
    while True:
        raw = input(f"  {label} [{hint}]: ").strip()
        if raw == "":
            return None
        try:
            n = int(raw)
        except ValueError:
            print("    not a number")
            continue
        if lo is not None and n < lo or hi is not None and n > hi:
            print(f"    must be between {lo} and {hi}")
            continue
        return n


def ask_time(label):
    while True:
        raw = input(f"  {label} [HH:MM]: ").strip()
        if raw == "":
            return None
        if TIME_RE.match(raw):
            h, m = raw.split(":")
            return f"{int(h):02d}:{m}"
        print("    expected HH:MM")


def ask_yes_no(prompt, default=True):
    raw = input(f"{prompt} {'[Y/n]' if default else '[y/N]'} ").strip().lower()
    return default if raw == "" else raw in ("y", "yes")


def rebuild_csv():
    rows = []
    for p in sorted(JSON_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        rows.append({k: data.get(k, "") for k in FIELDS})
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", "-d", default=date.today().isoformat())
    args = ap.parse_args()
    target = datetime.strptime(args.date, "%Y-%m-%d").date()

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    path = JSON_DIR / f"{target.isoformat()}.json"

    print(f"\nMorning self-report — {target}")
    print("Enter to skip any question.\n")

    if path.exists() and not ask_yes_no(f"Report for {target} exists. Overwrite?", default=False):
        print("aborted")
        return

    print("Yesterday")
    caffeine = ask_int("Caffeine", "cups", 0, 20)
    alcohol = ask_int("Alcohol", "drinks", 0, 20)
    last_meal = ask_time("Last meal")
    screen = ask_int("Screen time before bed", "minutes", 0, 600)
    activity = ask_int("Physical activity", "minutes", 0, 600)
    stress = ask_int("Stress in the evening", "1-5", 1, 5)

    print("\nBedtime")
    planned = ask_time("Planned bedtime")
    actual = ask_time("Actual bedtime")

    print("\nThis morning")
    subjective = ask_int("How did you sleep", "1-5", 1, 5)

    record = {
        "date": target.isoformat(),
        "filled_at": datetime.now().isoformat(timespec="seconds"),
        "caffeine_cups": caffeine,
        "alcohol_drinks": alcohol,
        "last_meal_time": last_meal,
        "screen_time_before_bed_min": screen,
        "physical_activity_min": activity,
        "stress_1_5": stress,
        "planned_bedtime": planned,
        "actual_bedtime": actual,
        "subjective_sleep_1_5": subjective,
    }

    print("\nSummary:")
    for k, v in record.items():
        if k not in ("date", "filled_at"):
            print(f"  {k}: {v if v is not None else '-'}")
    print()

    if not ask_yes_no("Save?"):
        print("discarded")
        return

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    rebuild_csv()
    print(f"saved {path.name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
