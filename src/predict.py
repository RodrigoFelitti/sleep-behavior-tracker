import argparse
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

FEATURES = [
    "Sleep Duration",
    "Heart Rate",
    "Physical Activity Level",
    "Stress Level",
    "Daily Steps",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", "-m", type=Path, default=ROOT / "models" / "model.pkl")
    ap.add_argument("--wearable", "-w", type=Path, default=ROOT / "data" / "personal" / "wearable_nights.csv")
    ap.add_argument("--kaggle", "-k", type=Path, default=ROOT / "data" / "kaggle" / "Sleep_health_and_lifestyle_dataset.csv")
    ap.add_argument("--out", "-o", type=Path, default=ROOT / "data" / "personal" / "predictions.csv")
    args = ap.parse_args()

    for p in (args.model, args.wearable, args.kaggle):
        if not p.exists():
            raise SystemExit(f"not found: {p}")

    model = joblib.load(args.model)
    df = pd.read_csv(args.wearable)

    X = df[FEATURES].copy()
    missing = X.isna().any(axis=1)
    if missing.any():
        kaggle = pd.read_csv(args.kaggle)
        medians = {f: kaggle[f].median() for f in FEATURES}
        X = X.fillna(medians)
        print(f"filled {missing.sum()} row(s) with kaggle medians")

    df["predicted_label"] = model.predict(X)
    df["predicted_proba_good"] = model.predict_proba(X)[:, 1].round(3)
    df["filled_with_median"] = missing.values

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    print()
    print(df[["date", "predicted_label", "predicted_proba_good", "filled_with_median"]].to_string(index=False))
    print()
    good = int((df["predicted_label"] == 1).sum())
    print(f"{good} good, {len(df) - good} poor  ->  {args.out}")


if __name__ == "__main__":
    main()
