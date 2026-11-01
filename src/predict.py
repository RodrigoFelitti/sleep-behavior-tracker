#!/usr/bin/env python3
"""Load the trained model and run it on wearable_nights.csv.

Last part of the pipeline:

1. 14 Days: Run morning_report.py -> Individual daily reports + self_report.csv
2. Export Samsung Health data (wearable_nights.csv) -> Run align_features.py -> feature aligned wearable_nights.csv
3. Run Predict on top of wearable_nights.csv 

"""

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FEATURES = [
    "Sleep Duration",
    "Heart Rate",
    "Physical Activity Level",
    "Stress Level",
    "Daily Steps",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", "-m", type=Path,
                        default=PROJECT_ROOT / "models" / "model.pkl")
    parser.add_argument("--wearable", "-w", type=Path,
                        default=PROJECT_ROOT / "data" / "personal" / "wearable_nights.csv")
    parser.add_argument("--kaggle", "-k", type=Path,
                        default=PROJECT_ROOT / "data" / "kaggle" / "Sleep_health_and_lifestyle_dataset.csv",
                        help="Used to compute median values for filling missing inputs")
    parser.add_argument("--out", "-o", type=Path,
                        default=PROJECT_ROOT / "data" / "personal" / "predictions.csv")
    args = parser.parse_args()

    for p in [args.model, args.wearable, args.kaggle]:
        if not p.exists():
            print(f"error: {p} not found")
            sys.exit(2)

    model = joblib.load(args.model)
    df = pd.read_csv(args.wearable)
    print(f"Loaded {len(df)} wearable night(s)")

    X = df[FEATURES].copy()
    had_nan = X.isna().any(axis=1)
    if had_nan.any():
        # fill missing values with the median from the Kaggle training set
        kaggle = pd.read_csv(args.kaggle)
        medians = {f: kaggle[f].median() for f in FEATURES}
        print(f"Filling NaN in {had_nan.sum()} row(s) with Kaggle medians")
        X = X.fillna(medians)

    labels = model.predict(X)
    probas = model.predict_proba(X)[:, 1]

    out = df.copy()
    out["predicted_label"] = labels
    out["predicted_proba_good"] = probas.round(3)
    out["filled_with_median"] = had_nan.values

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print()
    print(out[["date", "predicted_label", "predicted_proba_good",
               "filled_with_median"]].to_string(index=False))
    print()
    print(f"Wrote {args.out}")
    print(f"Summary: {int((labels == 1).sum())} good, {int((labels == 0).sum())} poor")


if __name__ == "__main__":
    main()