#!/usr/bin/env python3
"""Convert a Samsung Health export into the 5-feature CSV the model expects."""

import argparse
import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = PROJECT_ROOT / "src" / "feature_contract.json"
DEFAULT_OUT = PROJECT_ROOT / "data" / "personal" / "wearable_nights.csv"

# file name prefixes used by Samsung Health exports
FILE_PREFIXES = {
    "sleep":    "com.samsung.shealth.sleep.",
    "hr":       "com.samsung.shealth.tracker.heart_rate.",
    "stress":   "com.samsung.shealth.stress.",
    "activity": "com.samsung.shealth.activity.day_summary.",
    "steps":    "com.samsung.shealth.tracker.pedometer_day_summary.",
}


def find_csv(export_dir, prefix):
    """Find one CSV in export_dir whose name starts with prefix. None if nothing."""
    hits = sorted(export_dir.glob(f"{prefix}*.csv"))
    return hits[-1] if hits else None


def parse_dt(s):
    """Samsung timestamps are strings like '2026-10-28 06:12:27.000' (local time)."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return pd.to_datetime(s.strip())
    except Exception:
        return None


def load_sleep(path):
    """Return a DataFrame with wake_date and sleep_duration_hours.

    Samsung's sleep.csv is weird: the data row has one more field than the
    header (trailing comma), which breaks pandas's column alignment. So I
    read it with the csv module instead and index by position.
    """
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # first line is metadata, not the real header
        header = next(reader)
        duration_idx = header.index("sleep_duration")
        end_time_idx = header.index("com.samsung.health.sleep.end_time")

        for row in reader:
            if len(row) <= max(duration_idx, end_time_idx):
                continue
            end = parse_dt(row[end_time_idx])
            if end is None or not row[duration_idx]:
                continue
            try:
                duration_min = float(row[duration_idx])
            except ValueError:
                continue
            rows.append({
                "wake_date": end.date(),
                "sleep_duration_hours": duration_min / 60,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # if there's more than one sleep on the same day (nap), keep the longest
    df = df.sort_values("sleep_duration_hours", ascending=False)
    df = df.drop_duplicates(subset=["wake_date"], keep="first")
    return df.sort_values("wake_date").reset_index(drop=True)


def load_daily_mean(path, time_col, value_col, out_name):
    """Load a 'many measurements per day' CSV, average by day."""
    df = pd.read_csv(path, skiprows=1, encoding="utf-8-sig", low_memory=False)
    df["_dt"] = df[time_col].apply(parse_dt)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=["_dt", value_col])
    df["date"] = df["_dt"].apply(lambda d: d.date())
    out = df.groupby("date")[value_col].mean().reset_index()
    out.columns = ["date", out_name]
    return out


def load_activity(path):
    """activity.day_summary already has one row per day."""
    df = pd.read_csv(path, skiprows=1, encoding="utf-8-sig", low_memory=False)
    df["_dt"] = df["day_time"].apply(parse_dt)
    df = df.dropna(subset=["_dt"])
    df["date"] = df["_dt"].apply(lambda d: d.date())
    df["exercise_time"] = pd.to_numeric(df["exercise_time"], errors="coerce")
    df["step_count"] = pd.to_numeric(df["step_count"], errors="coerce")
    return df[["date", "exercise_time", "step_count"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", "-e", type=Path, required=True)
    parser.add_argument("--out", "-o", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.export_dir.is_dir():
        print(f"error: {args.export_dir} is not a directory")
        sys.exit(2)

    # find each file we need
    files = {name: find_csv(args.export_dir, p) for name, p in FILE_PREFIXES.items()}
    print("Found:")
    for name, p in files.items():
        print(f"  {name}: {p.name if p else '(not found)'}")
    if files["sleep"] is None:
        print("error: sleep file is required")
        sys.exit(2)
    print()

    sleep = load_sleep(files["sleep"])
    if sleep.empty:
        print("error: no parseable sleep sessions")
        sys.exit(2)
    print(f"{len(sleep)} sleep session(s) across "
          f"{sleep['wake_date'].min()}..{sleep['wake_date'].max()}")

    # load the daily aggregates (empty frame if the file is missing)
    hr = (load_daily_mean(files["hr"],
                          "com.samsung.health.heart_rate.start_time",
                          "com.samsung.health.heart_rate.heart_rate",
                          "hr_mean")
          if files["hr"] else pd.DataFrame(columns=["date", "hr_mean"]))

    stress = (load_daily_mean(files["stress"], "start_time", "score", "stress_raw")
              if files["stress"] else pd.DataFrame(columns=["date", "stress_raw"]))
    if not stress.empty:
        # Samsung stress is 0-100, Kaggle is 1-10 -> rescale linearly
        stress["stress_1_10"] = stress["stress_raw"] / 100 * 9 + 1
        stress = stress[["date", "stress_1_10"]]
    else:
        stress = pd.DataFrame(columns=["date", "stress_1_10"])

    activity = (load_activity(files["activity"])
                if files["activity"]
                else pd.DataFrame(columns=["date", "exercise_time", "step_count"]))

    # For each night, pull behavioural features from the day BEFORE waking up
    # (matches the "yesterday" semantics of the morning self-report)
    sleep["behaviour_date"] = sleep["wake_date"].apply(lambda d: d - timedelta(days=1))

    merged = sleep
    for other in (hr, stress, activity):
        merged = merged.merge(other, left_on="behaviour_date", right_on="date", how="left")
        merged = merged.drop(columns=["date"])

    # make sure the step_count column exists even if activity file was missing
    if "step_count" not in merged.columns:
        merged["step_count"] = pd.NA

    result = pd.DataFrame({
        "date": merged["wake_date"],
        "Sleep Duration": merged["sleep_duration_hours"],
        "Heart Rate": merged["hr_mean"],
        "Physical Activity Level": merged["exercise_time"],
        "Stress Level": merged["stress_1_10"],
        "Daily Steps": merged["step_count"],
    })

    print()
    print(result.to_string(index=False))

    # sanity check against the Kaggle feature ranges from notebook 01
    if CONTRACT_PATH.exists():
        with open(CONTRACT_PATH) as f:
            contract = json.load(f)
        print()
        print("Range check vs Kaggle:")
        for feat, spec in contract.items():
            if feat not in result.columns:
                continue
            s = result[feat].dropna()
            if s.empty:
                print(f"  {feat}: all NaN")
                continue
            flag = "ok"
            if s.min() < spec["kaggle_min"] * 0.5 or s.max() > spec["kaggle_max"] * 1.5:
                flag = "OUT OF RANGE"
            print(f"  {feat}: {s.min():.1f}..{s.max():.1f} "
                  f"(Kaggle {spec['kaggle_min']}..{spec['kaggle_max']}) {flag}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print()
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()