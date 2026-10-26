# Sleep Behavior Tracker

AI-assisted detection of poor sleep quality from consumer wearable data, with
behavioral factor tracking for personal sleep hygiene.

Course project — *Applied Computing in Healthcare* (UNISINOS, 2026/2).
Author: Rodrigo Felitti da Silva D'Ávila.

## What this does

Reads sleep and physiological data from a Samsung Galaxy Fit 3, applies a
machine learning classifier to label each night as **good** or **poor** sleep,
and asks the user to log daily behavioral factors (caffeine, alcohol, meal
timing, screen time, physical activity, perceived stress, bedtime). An
association analysis between the flagged nights and the logged behaviors
produces a per-user ranking of the most likely personal triggers for poor
sleep.

> ⚠️ Not a medical device. Does not diagnose sleep disorders. Intended as a
> self-management and prevention tool.

## Architecture

Three sequential phases:

1. **Training (offline, one-time).** Random Forest + Logistic Regression
   baseline trained on the public *Sleep Health and Lifestyle Dataset*
   (Kaggle), with 5-fold cross-validation. Output: `models/model.pkl`.
2. **Collection (1–2 weeks).** Nightly wearable data from Samsung Health
   (manual CSV export) + a morning CLI self-report (under 30 s).
3. **Analysis.** Classifier labels each night; join with self-report on date;
   behavioral association analysis (conditional frequencies + logistic
   regression). Output: ranked list of personal triggers + FHIR serialization.

## Repo layout

```
sleep-behavior-tracker/
├── src/              # Python scripts (training, self-report, alignment, inference, analysis)
├── notebooks/        # Jupyter notebooks (EDA, analysis)
├── data/
│   ├── kaggle/       # Public training dataset (gitignored)
│   └── personal/     # Personal wearable + self-report data (gitignored)
├── models/           # Trained model artifacts (gitignored)
├── reports/          # Plots + final report outputs (gitignored)
└── fhir/             # FHIR Observation / QuestionnaireResponse exports (gitignored)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Status

🚧 Work in progress. See the midterm report for the full plan.

## Privacy

All personal data stays on the local machine (LGPD-aligned). The `data/personal/`,
`models/`, `reports/` and `fhir/` folders are gitignored and must never be
committed to the public repository.
