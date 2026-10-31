# Notes for the Final Report

Running collection of observations made during development that need to be
addressed in the final 4-8 page report. Written in plain language — formalize
later when drafting the actual report.

---

## On the training results (notebook 02)

The classifier reaches very high scores on the Kaggle dataset:

- **CV (5-fold on 299 training rows):** F1 = 0.993, ROC-AUC = 0.999
- **Held-out test set (75 rows):** accuracy 0.97, F1 0.98, ROC-AUC 0.998, recall 1.00
- **Confusion matrix:** 2 false positives, 0 false negatives (out of 75)
- **Best Random Forest params:** `n_estimators=300, max_depth=None, min_samples_split=5, class_weight=None`

**These numbers should NOT be presented as evidence that the system works well
in the real world.** They almost certainly reflect two properties of the
Kaggle dataset that will not hold for personal Samsung Health data:

1. **The dataset is likely synthetic or aggregated by occupation profile.**
   EDA showed strong discreteness — Daily Steps peak at exactly 5000, 6000,
   7000, 8000; Physical Activity Level peaks at 30, 45, 60, 75, 90; Stress
   Level has no 1, 2, 9, or 10 values despite being advertised as Likert 1-10.
   Real wearable data is continuous (e.g. 7342 steps, HR 68.4 bpm).
2. **No ambiguous cases.** The model is essentially memorizing clean clusters.
   The 2 misclassifications came from the boundary.

**Feature importances confirmed the EDA findings:**

- Sleep Duration: 0.39
- Stress Level: 0.38
- Heart Rate: 0.18
- Physical Activity Level: 0.03
- Daily Steps: 0.02 (essentially ignored, as predicted by r = 0.01 with target)

**Framing for the report:** present the training results honestly, note the
limitation, and position the validation that matters as the comparison between
classifier predictions and the subjective 1-5 self-rating on personal nights.
Something like:

> The classifier achieves F1 = 0.98 on the Kaggle test set, but this likely
> reflects the synthetic character of the dataset (visible as discrete clumping
> in the feature distributions) rather than genuine clinical-grade accuracy on
> continuous wearable data. The relevant validation is the Phase 3 agreement
> between model labels and the user's subjective sleep rating, discussed in
> Section X.

This is the "exploratory framing" mitigation already written into the midterm.

---

## On the Kaggle dataset itself

- 374 rows, 13 columns, no missing values, 0 duplicates
- Class balance after thresholding Quality of Sleep >= 7: 68.7% good / 31.3% poor
- Raw Quality of Sleep only takes values 4-9 (never 1-3 or 10)
- Strong multicollinearity: Sleep Duration ↔ Stress r = -0.81, Physical Activity ↔ Daily Steps r = +0.77, Heart Rate ↔ Stress r = +0.67

---

## On feature alignment risks (anticipated)

From the `feature_contract.json` built in notebook 01:

- **HIGH risk — Stress Level.** Samsung's HRV-derived 0-100 score and Kaggle's
  subjective 1-10 Likert measure different constructs. Linear rescale is a
  rough workaround. This is also the strongest predictor in the trained model,
  so the mismatch directly impacts inference quality.
- **MEDIUM risk — Heart Rate.** Kaggle doesn't document whether it's resting
  HR or daily average. Decision: use daily mean of all `tracker.heart_rate`
  measurements. Document the choice.
- **LOW risk — Sleep Duration.** Just divide minutes by 60.
- **LOW risk — Daily Steps.** Direct match in units; also carries essentially
  no signal in training, so imperfect alignment is tolerable.
- **Unfixable — the shape mismatch.** StandardScaler neutralizes location and
  scale differences but not discreteness vs. continuity.

---

## Add here as development progresses

(Keep adding bullet points for anything that will matter in the final writeup —
unexpected behavior, decisions made, mitigations applied.)
