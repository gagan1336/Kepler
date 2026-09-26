---
phase: "Phase 1"
date: 2026-08-21
holdout_set: "unconfirmed"
auc_point: 0.5723
auc_ci_low: null
auc_ci_high: null
bootstrap_method: "unconfirmed"
precision_at_50: null
net_expectancy_at_50: null
validated_on_clean_holdout: false
status: "superseded"
---

## Summary

Expanded to Nifty200 universe (145 symbols), 8-year history, 5 walk-forward folds. Walk-forward mean AUC improved from 0.5159 → 0.5723. OOD AUC on `Nifty200 Extra` jumped from 0.5559 → 0.7743 — but this later turned out to be inflated because the eval test set still had non-trivial overlap with training neighbours, not a clean holdout. The frozen-42 holdout set was not yet locked at this point.

> [!WARNING]
> `validated_on_clean_holdout = false`. OOD AUC 0.7743 (Nifty200 Extra) was produced before the frozen holdout was locked and before timezone/monotonic bugs were fixed. This number **must not be cited** as a validated result. See [[03-Corrections-Log/2026-08-23-77pct-correction]].

> [!NOTE]
> `holdout_set = "unconfirmed"` — eval used "Nifty200 Extra OOD" test set from `eval_20260821_070620.json`. This is a rolling selection from the training corpus, not the frozen-42 set. The frozen holdout was created 2026-08-23.

## Training Configuration

| Field | Value |
|---|---|
| Universe | nifty200 |
| n_symbols | ~145 |
| history_years | 8 |
| n_folds | 5 |
| embargo_days | 15 |
| model_backend | lgbm |
| forward_days | 10 |
| threshold_pct | 5.0% |
| run_id | 20260821_070520 |
| model_trained_at | 2026-08-21T06:40:06Z |

## Walk-Forward Fold Results

> Sourced from `eval_20260821_071208.json` (nifty200 retrain eval)

| Fold | Test Start | Test End | n_test | AUC |
|---|---|---|---|---|
| Mean across 5 folds | | | | **0.5723** |

## OOD Evaluation Results (NOT frozen holdout)

Sourced from `eval_20260821_070620.json`:

| Test Set | n_samples | AUC | Precision @ 0.50 |
|---|---|---|---|
| Nifty50 (in-universe) | 21,535 | 0.9726 ⚠️ | 0.8433 |
| Nifty200 Extra (OOD) | 31,860 | 0.5555 | 0.2461 |
| Nifty500 Extra (small/mid) | 9,467 | 0.5773 | 0.2908 |

Sourced from `eval_20260821_071208.json` (after full nifty200 retrain):

| Test Set | n_samples | AUC |
|---|---|---|
| Nifty50 (in-universe) | 21,535 | 0.7843 |
| Nifty200 Extra (OOD) | 31,860 | 0.7743 ⚠️ inflated |
| Nifty500 Extra (small/mid) | 9,467 | 0.5805 |

> [!CAUTION]
> The 0.7743 OOD AUC was the number initially quoted in early analysis. It was subsequently corrected to ~0.56 on the clean frozen holdout after timezone and monotonic-sort bugs were fixed. See [[03-Corrections-Log/2026-08-23-77pct-correction]] and [[03-Corrections-Log/2026-08-23-tz-monotonic-bugs]].

## Known Limitations

- No macro features (VIX, crude, USD/INR) — added in Phase C-r
- No cross-sectional rank features — added in Phase C-r
- Bootstrap CI not run on this phase
- Timezone and monotonic sort bug affected date alignment; fixed before Phase C-r

## Links

- [[00-Dashboard]]
- [[02-Phases/Phase-0-Nifty50-Smoke]]
- [[02-Phases/Phase-Cr-Macro-Rank-Features]]
- [[03-Corrections-Log/2026-08-23-77pct-correction]]
- [[03-Corrections-Log/2026-08-23-tz-monotonic-bugs]]
