---
phase: "Phase 0"
date: 2026-08-21
holdout_set: "unconfirmed"
auc_point: 0.5159
auc_ci_low: null
auc_ci_high: null
bootstrap_method: "unconfirmed"
precision_at_50: null
net_expectancy_at_50: null
validated_on_clean_holdout: false
status: "superseded"
---

## Summary

Proof-of-concept smoke test. Nifty50 universe only, 3-year history, 3 walk-forward folds. Confirmed the pipeline wired end-to-end: data fetch → feature generation → SMOTE → LightGBM → fold evaluation. Numbers are **not** holdout-validated and should not be cited.

> [!WARNING]
> `validated_on_clean_holdout = false`. The OOD eval in this phase ran against `Nifty200 Extra` and `Nifty500 Extra` — these were **not** the frozen-42 holdout set. The frozen holdout did not exist yet. Do not quote OOD AUC from this phase as a holdout number.

> [!NOTE]
> `holdout_set = "unconfirmed"` — the Phase 0 eval file (`eval_20260821_065104.json`) scores against three test sets ("Nifty50 in-universe", "Nifty200 Extra OOD", "Nifty500 Extra OOD"). None of these is the frozen-42 set. Froze holdout was created 2026-08-23.

## Training Configuration

| Field | Value |
|---|---|
| Universe | nifty50 |
| n_symbols | 50 |
| history_years | 3 |
| n_folds | 3 |
| embargo_days | 15 |
| model_backend | lgbm |
| forward_days | 10 |
| threshold_pct | 5.0% |
| run_id | 20260821_063901 |

## Walk-Forward Fold Results

| Fold | Test Start | Test End | n_test | AUC | Avg Prec |
|---|---|---|---|---|---|
| 1 | 2024-08-08 | 2025-03-27 | 8,000 | 0.5191 | 0.1511 |
| 2 | 2025-04-11 | 2025-12-02 | 8,000 | 0.4751 | 0.1149 |
| 3 | 2025-12-15 | 2026-08-04 | 7,999 | 0.5534 | 0.1853 |
| **Mean** | | | | **0.5159 ± 0.032** | 0.1504 |

## OOD Evaluation Results (NOT frozen holdout)

Sourced from `eval_20260821_065104.json` (first eval run, same model):

| Test Set | n_samples | AUC | Precision @ 0.50 |
|---|---|---|---|
| Nifty50 (in-universe) | 21,535 | 0.9726 | 0.8433 |
| Nifty200 Extra (OOD) | 31,429 | 0.5559 | 0.2463 |
| Nifty500 Extra (small/mid) | 8,177 | 0.5724 | 0.2880 |

> [!CAUTION]
> The in-universe AUC of **0.9726** is a contamination flag — the model was evaluated on the same data it was trained on for the Nifty50 set. This was caught and documented in [[03-Corrections-Log/2026-08-21-contamination-catch]].

## Known Limitations

- 3-year history too short; rolling features (EMA-200, ATR-14) have insufficient warm-up for early years
- Nifty50 universe is too small and too liquid to generalise
- No macro features, no cross-sectional rank features (added in Phase C-r)
- No frozen holdout yet — holdout set was locked on 2026-08-23
- Bootstrap CI not run on this phase

## Links

- [[00-Dashboard]]
- [[02-Phases/Phase-1-Nifty200-Full]]
- [[03-Corrections-Log/2026-08-21-contamination-catch]]
