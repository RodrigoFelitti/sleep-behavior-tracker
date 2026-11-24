import argparse
import csv
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "src" / "feature_contract.json"
DEFAULT_OUT = ROOT / "data" / "personal" / "wearable_nights.csv"
DEFAULT_SELF_REPORT = ROOT / "data" / "personal" / "self_report.csv"

PREFIXES = {
    "sleep":    "com.samsung.shealth.sleep.",
    "hr":       "com.samsung.shealth.tracker.heart_rate.",
    "stress":   "com.samsung.shealth.stress.",
    "activity": "com.samsung.shealth.activity.day_summary.",
    "steps":    "com.samsung.shealth.tracker.pedometer_day_summary.",
}


def find_csv(export_dir, prefix):
    hits = sorted(export_dir.glob(f"{prefix}*.csv"))
    return hits[-1] if hits else None


def parse_dt(s):
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return pd.to_datetime(s.strip())
    except Exception:
        return None


#samsung CSVs have a metadata line first and one extra trailing value per
#row, which throws off pandas. Reading by column index with csv avoids it.
def read_samsung(path, cols):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        header = next(reader)
        idx = {c: header.index(c) for c in cols}
        for row in reader:
            if len(row) > max(idx.values()):
                rows.append({c: row[i] for c, i in idx.items()})
    return rows


def load_sleep(path):
    rows = read_samsung(path, ["sleep_duration", "com.samsung.health.sleep.end_time"])
    out = []
    for r in rows:
        end = parse_dt(r["com.samsung.health.sleep.end_time"])
        if end is None or not r["sleep_duration"]:
            continue
        try:
            out.append({"wake_date": end.date(),
                        "sleep_duration_hours": float(r["sleep_duration"]) / 60})
        except ValueError:
            pass
    df = pd.DataFrame(out)
    if df.empty:
        return df
    df = df.sort_values("sleep_duration_hours", ascending=False)
    df = df.drop_duplicates("wake_date", keep="first")
    return df.sort_values("wake_date").reset_index(drop=True)


def load_daily_mean(path, time_col, value_col, name):
    rows = read_samsung(path, [time_col, value_col])
    by_date = {}
    for r in rows:
        dt = parse_dt(r[time_col])
        if dt is None:
            continue
        try:
            by_date.setdefault(dt.date(), []).append(float(r[value_col]))
        except ValueError:
            pass
    data = [{"date": d, name: sum(v) / len(v)} for d, v in sorted(by_date.items())]
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["date", name])


def load_activity(path):
    rows = read_samsung(path, ["day_time", "exercise_time", "step_count"])
    out = []
    for r in rows:
        dt = parse_dt(r["day_time"])
        if dt is None:
            continue
        ex = float(r["exercise_time"]) if r["exercise_time"] else None
        sc = float(r["step_count"]) if r["step_count"] else None
        out.append({"date": dt.date(), "exercise_time": ex, "step_count": sc})
    return pd.DataFrame(out) if out else pd.DataFrame(columns=["date", "exercise_time", "step_count"])


def load_steps(path):
    rows = read_samsung(path, ["day_time", "step_count"])
    out = []
    for r in rows:
        dt = parse_dt(r["day_time"])
        if dt and r["step_count"]:
            out.append({"date": dt.date(), "pedometer_steps": float(r["step_count"])})
    if not out:
        return pd.DataFrame(columns=["date", "pedometer_steps"])
    return pd.DataFrame(out).groupby("date")["pedometer_steps"].max().reset_index()


def load_self_report(path):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["stress_from_self"] = (df["stress_1_5"] - 1) / 4 * 9 + 1
    return df[["date", "stress_from_self", "physical_activity_min"]].rename(
        columns={"physical_activity_min": "activity_from_self"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-dir", "-e", type=Path, required=True)
    ap.add_argument("--out", "-o", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--self-report", "-s", type=Path, default=DEFAULT_SELF_REPORT)
    args = ap.parse_args()

    if not args.export_dir.is_dir():
        raise SystemExit(f"not a directory: {args.export_dir}")

    files = {k: find_csv(args.export_dir, p) for k, p in PREFIXES.items()}
    for k, p in files.items():
        print(f"  {k}: {p.name if p else '(missing)'}")
    if files["sleep"] is None:
        raise SystemExit("sleep file required")

    sleep = load_sleep(files["sleep"])
    if sleep.empty:
        raise SystemExit("no sleep sessions")
    print(f"\n{len(sleep)} nights, {sleep['wake_date'].min()}..{sleep['wake_date'].max()}")

    hr = load_daily_mean(files["hr"], "com.samsung.health.heart_rate.start_time",
                         "com.samsung.health.heart_rate.heart_rate", "hr_mean") \
        if files["hr"] else pd.DataFrame(columns=["date", "hr_mean"])

    stress = load_daily_mean(files["stress"], "start_time", "score", "stress_raw") \
        if files["stress"] else pd.DataFrame(columns=["date", "stress_raw"])
    if not stress.empty:
        stress["stress_from_samsung"] = stress["stress_raw"] / 100 * 9 + 1
        stress = stress[["date", "stress_from_samsung"]]
    else:
        stress = pd.DataFrame(columns=["date", "stress_from_samsung"])

    activity = load_activity(files["activity"]) if files["activity"] \
        else pd.DataFrame(columns=["date", "exercise_time", "step_count"])
    pedometer = load_steps(files["steps"]) if files["steps"] \
        else pd.DataFrame(columns=["date", "pedometer_steps"])

    self_report = pd.DataFrame(columns=["date", "stress_from_self", "activity_from_self"])
    if args.self_report.exists():
        self_report = load_self_report(args.self_report)
        print(f"self-report: {len(self_report)} days")

    sleep["behaviour_date"] = sleep["wake_date"] - timedelta(days=1)

    m = sleep
    for other in (hr, stress, activity, pedometer):
        m = m.merge(other, left_on="behaviour_date", right_on="date", how="left").drop(columns=["date"])
    m = m.merge(self_report, left_on="wake_date", right_on="date", how="left").drop(columns=["date"])

    for col in ["step_count", "exercise_time", "pedometer_steps",
                "stress_from_samsung", "stress_from_self", "activity_from_self"]:
        if col not in m.columns:
            m[col] = pd.NA

    #self-report wins for stress and activity since the Fit 3 barely tracks them
    m["stress"] = m["stress_from_self"].combine_first(m["stress_from_samsung"])
    m["activity"] = m["activity_from_self"].combine_first(m["exercise_time"])
    m["steps"] = m["step_count"].combine_first(m["pedometer_steps"])

    result = pd.DataFrame({
        "date": m["wake_date"],
        "Sleep Duration": m["sleep_duration_hours"],
        "Heart Rate": m["hr_mean"],
        "Physical Activity Level": m["activity"],
        "Stress Level": m["stress"],
        "Daily Steps": m["steps"],
    })

    print()
    print(result.to_string(index=False))

    if CONTRACT_PATH.exists():
        contract = json.load(open(CONTRACT_PATH))
        print("\nRange vs Kaggle:")
        for feat, spec in contract.items():
            s = result[feat].dropna()
            if s.empty:
                print(f"  {feat}: all NaN")
                continue
            flag = "OUT OF RANGE" if s.min() < spec["kaggle_min"] * 0.5 or s.max() > spec["kaggle_max"] * 1.5 else "ok"
            print(f"  {feat}: {s.min():.1f}..{s.max():.1f} (kaggle {spec['kaggle_min']}..{spec['kaggle_max']}) {flag}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
