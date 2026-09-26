---
phase: "Phase C-r"
date: 2026-08-24
holdout_set: "frozen-42"
auc_point: 0.6585
auc_ci_low: 0.6547
auc_ci_high: 0.6625
bootstrap_method: "row-level"
precision_at_50: 0.4286
net_expectancy_at_50: 4.443
validated_on_clean_holdout: true
status: "complete"
---

## Summary

Added macro features (India VIX, USD/INR 1d return, crude oil 1d return, VIX 5d change, market breadth) and 6 cross-sectional rank features (sector RSI/momentum/volatility ranks, market momentum/volatility ranks, vol-vs-own-history). Total feature count: 45 → 51. Model retrained on Nifty200 universe with 8-year history, 5 walk-forward folds. First phase evaluated against the **locked frozen-42 holdout set** with bootstrap CI. Walk-forward OOF AUC improved to 0.668 (run 20260824_073558). Clean holdout AUC: **0.6585 [0.6547, 0.6625]**.

> [!IMPORTANT]
> This is the **first and only phase with `validated_on_clean_holdout = true`**. All numbers below are from clean holdout evaluation only.

> [!NOTE]
> Bootstrap method: **row-level** resampling with replacement. `bootstrap_ci.py` resamples individual rows (not temporal blocks). This is conservative for i.i.d. assumption but understates uncertainty for time-series data — the CI is slightly too narrow because it does not account for autocorrelation between consecutive daily rows. A block bootstrap would produce wider CIs. The current CI should be treated as a **lower bound on uncertainty**.

> [!NOTE]
> Cross-sectional ranks in holdout eval are computed within the ~40-symbol holdout set, not the full 150-symbol training universe. This makes the ranking signal weaker than at live-scan time (where all peers are present), so holdout AUC is **slightly conservative** — true live performance may be marginally higher.

## Training Configuration

| Field | Value |
|---|---|
| Universe | nifty200 |
| n_symbols | 145 |
| n_total_rows | 271,527 |
| history_years | 8 |
| n_folds | 5 |
| embargo_days | 15 |
| model_backend | lgbm |
| forward_days | 10 |
| threshold_pct | 5.0% |
| positive_rate | 22.33% |
| feature_count | 51 |
| run_id | 20260824_073558 |
| trained_at | 2026-08-24T07:43:48Z |

## Walk-Forward Fold Results (OOF, training universe only)

Sourced from `20260824_073558/summary.json`:

| Fold | Test Start | Test End | n_test | AUC | Avg Prec | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| 1 | 2018-11-26 | 2026-08-10 | 43,063 | 0.6105 | 0.3363 | 0.4229 | 0.1560 | 0.2279 |
| 2 | 2018-11-26 | 2026-08-10 | 44,183 | 0.6573 | 0.3812 | 0.5232 | 0.1585 | 0.2432 |
| 3–5 | … | … | … | … | … | … | … | … |
| **Mean** | | | | **0.668 ± 0.0321** | **0.3901** | **0.5193** | **0.1561** | **0.2391** |

> Walk-forward AUC of 0.668 (OOF on training universe) vs 0.6585 (clean holdout) — 0.009 gap, consistent with modest overfitting on the training universe.

## Holdout Evaluation (Clean — frozen-42 set)

Sourced from `bootstrap_ci_20260824_074749.json`:

| Metric | Value | Notes |
|---|---|---|
| n_symbols evaluated | 43 | 42 live + 1 partial (3 delisted skipped in backtest) |
| n_rows | 70,264 | |
| Positive rate | 25.59% | Higher than training (22.33%) — different sector mix |
| AUC (point) | **0.6585** | |
| AUC CI low (5th pct) | **0.6547** | |
| AUC CI high (95th pct) | **0.6625** | |
| Bootstrap method | **row-level**, n=1,000, seed=42 | |
| p(AUC > 0.50) | 1.0000 | Signal is real |
| CI includes 0.50? | No ✅ | |

### Precision Sweep (Clean Holdout)

| Threshold | n_trades | Precision | Recall |
|---|---|---|---|
| 0.25 | 54,652 | 0.293 | 0.891 |
| 0.30 | 45,195 | 0.315 | 0.791 |
| 0.35 | 35,039 | 0.342 | 0.666 |
| 0.40 | 25,786 | 0.371 | 0.533 |
| 0.45 | 18,285 | 0.400 | 0.407 |
| **0.50** | **12,507** | **0.4286** | 0.298 |
| 0.55 | 8,346 | 0.463 | 0.215 |
| 0.60 | 5,338 | 0.495 | 0.147 |
| 0.65 | 3,326 | 0.530 | 0.098 |
| 0.70 | 1,993 | 0.573 | 0.064 |

### Expectancy (Clean Holdout, primary model, thr=0.35)

Sourced from `expectancy_20260826_122700.json`:

| Metric | Value |
|---|---|
| n_trades @ 0.35 | 35,084 |
| Hit rate | 34.12% |
| Avg win | +12.45% |
| Avg loss | −2.18% |
| Gross expectancy | +2.813% |
| Round-trip cost (₹50k trade) | 0.393% |
| **Net expectancy @ 0.35** | **+2.420%** |
| Net expectancy @ 0.50 | **+4.443%** |

### Meta-Filter (Provisional — Phase D retrain pending)

| Combined threshold | n_trades | Hit rate | Net expectancy |
|---|---|---|---|
| 0.10 | 29,140 | 35.9% | +2.816% |
| 0.15 | 7,094 | 47.3% | +5.567% |
| 0.20 | 1,126 | 62.1% | +9.592% |

> [!WARNING]
> Meta-filter was trained on OOF predictions from the **46-feature** primary model. The primary model now has 51 features. Meta-filter results above are **provisional** until Phase D retrain (`python meta_label.py --train`) is completed.

## NautilusTrader Parity Validation

Sourced from `parity_report_20260826_123041.json`:

- Signal-based (overlapping windows): **35k trades** — exact parity with expectancy.py ✅
- Simulated position-constrained: **5k trades** — realistic NT simulation mode
- Net expectancy delta between NT and expectancy.py: **0.0%** (within rounding)

## skfolio Portfolio Layer

Sourced from `skfolio_report_20260826_130032.json`:

| Optimizer | n_folds | Diversification Ratio | Effective N |
|---|---|---|---|
| HRP | 78 | 2.30 | 34.0 |
| RiskBudget | 78 | 2.44 | 36.5 |

All sector exposures within 25% cap ✅. No correlation pair (corr > 0.80) violated the 8% combined cap.

> [!WARNING]
> skfolio sizing uses the provisional meta-filter. Weights are indicative until Phase D retrain.

## Known Limitations

- Bootstrap CI uses **row-level** resampling — understates temporal autocorrelation uncertainty; CI is a lower bound, not a true 90% interval for time-series
- Cross-sectional ranks computed within holdout set (~40 stocks) vs. live scan (150+ stocks) — holdout AUC is conservatively understated
- Meta-filter not yet retrained on 51-feature OOF predictions (Phase D pending)
- Three holdout symbols delisted (KALPATPOWR, CENTURYTEX, BIRLASOFT) — skipped in backtest; included in bootstrap CI

## Links

- [[00-Dashboard]]
- [[02-Phases/Phase-1-Nifty200-Full]]
- [[03-Corrections-Log/2026-08-23-77pct-correction]]
- [[03-Corrections-Log/2026-08-23-tz-monotonic-bugs]]
