---
phase: ""
date: 
holdout_set: ""        # e.g. "frozen-42" — must always be explicit, never assumed
auc_point: 
auc_ci_low: 
auc_ci_high: 
bootstrap_method: ""   # "row-level" | "block" | "unconfirmed" — never leave implicit
precision_at_50: 
net_expectancy_at_50: 
validated_on_clean_holdout: 
status: ""             # "complete" | "superseded" | "in-progress"
---

## Summary

> One paragraph describing what this phase added and what its key output numbers mean.

## Training Configuration

| Field | Value |
|---|---|
| Universe | |
| n_symbols | |
| history_years | |
| n_folds | |
| embargo_days | |
| model_backend | |
| forward_days | |
| threshold_pct | |

## Walk-Forward Fold Results

| Fold | Test Start | Test End | n_test | AUC | Avg Prec |
|---|---|---|---|---|---|

## Holdout Evaluation

| Metric | Value | Notes |
|---|---|---|
| AUC (point) | | |
| AUC CI low (5th pct) | | |
| AUC CI high (95th pct) | | |
| Bootstrap method | | |
| Bootstrap n_iter | | |
| Precision @ 0.50 | | |
| Net expectancy @ thr=0.35 | | |

## Known Limitations

- 

## Links

- [[00-Dashboard]]
- [[03-Corrections-Log/]]
