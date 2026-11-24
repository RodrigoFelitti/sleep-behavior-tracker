import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

BEHAVIOURS = [
    "caffeine_cups",
    "screen_time_before_bed_min",
    "stress_1_5",
    "meal_time_min",
    "bedtime_lateness_min",
    "bedtime_delay_min",
]


def to_minutes_after_6pm(hhmm):
    #anchor at 18:00 so late-night times sort after evening ones
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return np.nan
    h, m = map(int, hhmm.split(":"))
    if h < 18:
        h += 24
    return (h - 18) * 60 + m


def to_minutes(hhmm):
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return np.nan
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", "-p", type=Path, default=ROOT / "data" / "personal" / "predictions.csv")
    ap.add_argument("--self-report", "-s", type=Path, default=ROOT / "data" / "personal" / "self_report.csv")
    args = ap.parse_args()

    pred = pd.read_csv(args.predictions)
    self_report = pd.read_csv(args.self_report)
    df = pred.merge(self_report, on="date", how="inner")
    print(f"{len(df)} nights with both prediction and self-report\n")

    df["meal_time_min"] = df["last_meal_time"].apply(to_minutes)
    df["bedtime_lateness_min"] = df["actual_bedtime"].apply(to_minutes_after_6pm)
    df["bedtime_delay_min"] = (df["actual_bedtime"].apply(to_minutes_after_6pm)
                               - df["planned_bedtime"].apply(to_minutes_after_6pm))

    df["model_poor"] = (df["predicted_label"] == 0).astype(int)
    df["subjective_poor"] = (df["subjective_sleep_1_5"] <= 3).astype(int)

    #agreement between the model and how the user actually rated the night
    agree = (df["model_poor"] == df["subjective_poor"]).mean()
    both_poor = ((df["model_poor"] == 1) & (df["subjective_poor"] == 1)).sum()
    print("Model vs subjective rating")
    print(pd.crosstab(df["model_poor"], df["subjective_poor"],
                      rownames=["model poor"], colnames=["subjective poor"]))
    print(f"agreement: {agree:.0%}  (both flag poor on {both_poor} night(s))\n")

    #average of each behaviour on nights the model called good vs poor
    print("Behaviour averages by model label")
    by_model = df.groupby("model_poor")[BEHAVIOURS].mean().T
    by_model.columns = ["model good", "model poor"]
    print(by_model.round(1), "\n")

    #average by the user own rating
    print("Behaviour averages by subjective rating")
    by_subj = df.groupby("subjective_poor")[BEHAVIOURS].mean().T
    by_subj.columns = ["felt good", "felt poor"]
    print(by_subj.round(1), "\n")

    #which behaviours track worse sleep (correlation with the continuous outcomes)
    rows = []
    for b in BEHAVIOURS:
        rows.append({
            "behaviour": b,
            "corr_with_subjective": df[b].corr(df["subjective_sleep_1_5"]),
            "corr_with_model_proba": df[b].corr(df["predicted_proba_good"]),
        })
    corr = pd.DataFrame(rows)
    corr["abs_subj"] = corr["corr_with_subjective"].abs()
    corr = corr.sort_values("abs_subj", ascending=False).drop(columns="abs_subj")
    print("Behaviour correlation with sleep quality")
    print("(negative corr_with_subjective = behaviour goes with worse self-rated sleep)")
    print(corr.round(2).to_string(index=False), "\n")

    REPORTS.mkdir(exist_ok=True)
    df.to_csv(REPORTS / "analysis_merged.csv", index=False)
    corr.to_csv(REPORTS / "behaviour_correlations.csv", index=False)

    with open(REPORTS / "analysis_summary.md", "w", encoding="utf-8") as f:
        f.write("# Analysis summary\n\n")
        f.write(f"- Nights analysed: {len(df)}\n")
        f.write(f"- Model flagged poor: {int(df['model_poor'].sum())}\n")
        f.write(f"- Self-rated poor (<=3): {int(df['subjective_poor'].sum())}\n")
        f.write(f"- Model vs subjective agreement: {agree:.0%}\n")
        f.write(f"- Both flag poor on the same night: {both_poor}\n\n")
        f.write("## Behaviour correlation with self-rated sleep\n\n")
        f.write("```\n")
        f.write(corr.round(2).to_string(index=False))
        f.write("\n```\n")
    print(f"wrote {REPORTS/'analysis_merged.csv'}")
    print(f"wrote {REPORTS/'behaviour_correlations.csv'}")
    print(f"wrote {REPORTS/'analysis_summary.md'}")


if __name__ == "__main__":
    main()
