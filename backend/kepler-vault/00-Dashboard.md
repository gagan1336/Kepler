---
cssclasses: [dashboard]
---

# KEPLER — Research Dashboard

> **⚠️ Meta-filter status: PROVISIONAL — Phase D retrain pending**  
> `meta_model.pkl` was trained on 46-feature OOF predictions. Primary model now has 51 features.  
> Do not cite meta-filter expectancy numbers as validated until `python meta_label.py --train` completes.

---

## ✅ Validated Results (clean holdout only)

> Phases where `validated_on_clean_holdout = true`, sorted by date descending.
> These are the only numbers safe to quote externally.

```dataview
TABLE WITHOUT ID
  file.link AS "Phase",
  date AS "Date",
  holdout_set AS "Holdout Set",
  auc_point AS "AUC",
  ("[ " + string(auc_ci_low) + " , " + string(auc_ci_high) + " ]") AS "90% CI",
  bootstrap_method AS "Bootstrap",
  precision_at_50 AS "Prec@0.50",
  net_expectancy_at_50 AS "NetExp@0.50%",
  status AS "Status"
FROM "02-Phases"
WHERE validated_on_clean_holdout = true
SORT date DESC
```

---

## 🔴 Unvalidated / Superseded Phases

> Phases where `validated_on_clean_holdout = false`. Numbers from these phases **must not** be mixed with validated results. Keep this table non-empty so unvalidated numbers are always visible.

```dataview
TABLE WITHOUT ID
  file.link AS "Phase",
  date AS "Date",
  holdout_set AS "Holdout Set",
  auc_point AS "AUC (do not cite)",
  bootstrap_method AS "Bootstrap",
  validated_on_clean_holdout AS "Clean Holdout?",
  status AS "Status"
FROM "02-Phases"
WHERE validated_on_clean_holdout = false
SORT date DESC
```

---

## 🗒 Corrections Log (newest first)

> All known corrections, measurement errors, and invalidated numbers.
> Check this before quoting any number from an older phase.

```dataview
TABLE WITHOUT ID
  file.link AS "Entry",
  date AS "Date",
  severity AS "Severity",
  affected_phases AS "Affected Phases"
FROM "03-Corrections-Log"
SORT date DESC
```

---

## Current Model Snapshot

| Field | Value | Source |
|---|---|---|
| **Phase** | Phase C-r | `kepler_meta.json` |
| **Trained at** | 2026-08-24T07:43:48Z | `kepler_meta.json` |
| **Universe** | Nifty200, 145 symbols | `kepler_meta.json` |
| **Feature count** | 51 | `kepler_meta.json` |
| **Clean holdout AUC** | **0.6585** | `bootstrap_ci_20260824_074749.json` |
| **AUC 90% CI** | [0.6547, 0.6625] | row-level bootstrap, n=1000 |
| **CI lower-bound caveat** | row-level bootstrap understates autocorr uncertainty | `bootstrap_ci.py` |
| **Net expectancy @ 0.35** | **+2.420%** (after 0.393% cost) | `expectancy_20260826_122700.json` |
| **Net expectancy @ 0.50** | **+4.443%** | same |
| **Walk-forward OOF AUC** | 0.668 ± 0.032 | `20260824_073558/summary.json` |
| **Holdout set** | frozen-42 (42 live tickers) | `configs/frozen_holdout.yaml` |
| **3 delisted** | KALPATPOWR, CENTURYTEX, BIRLASOFT | skipped in backtest |

---

## Execution Layer (NautilusTrader)

| Metric | Value | Source |
|---|---|---|
| Signal-based trades (overlapping window) | 35,084 | `parity_report_20260826_123041.json` |
| Simulated position-constrained trades | ~5,000 | same |
| NT vs expectancy.py net-exp delta | **0.0%** ✅ | parity verified |
| NSE round-trip cost model | 0.393% @ ₹50k | `expectancy.py` |
| WDAC note | pyarrow DLLs blocked; `--fallback` pure-Python runner in use | machine policy |

---

## Portfolio Layer (skfolio — PROVISIONAL)

> ⚠️ Uses provisional meta-filter. Weights are indicative only.

| Metric | HRP | RiskBudget | Source |
|---|---|---|---|
| Walk-forward folds | 78 | 78 | `skfolio_report_20260826_130032.json` |
| Diversification ratio | 2.30 | 2.44 | same |
| Effective N (1/HHI) | 34.0 | 36.5 | same |
| Sector cap violations | None ✅ | None ✅ | same |
| Correlation cap violations | None ✅ | None ✅ | same |
| Max single weight | ~3.5% | ~3.5% | same (cap: 5%) |

---

## Phase D — Outstanding Work

- [ ] Retrain meta-filter on 51-feature OOF predictions: `python meta_label.py --train`
- [ ] Re-run `portfolio_skfolio.py` after Phase D retrain
- [ ] Re-run `bootstrap_ci.py --block` to produce block-bootstrap CI (wider, more conservative)
- [ ] Run NautilusTrader without `--fallback` once WDAC policy is updated for unsigned `.pyd` files
- [ ] Create Phase D note in `02-Phases/` with updated frontmatter

---

## Quick Commands

```bash
# Full holdout bootstrap CI
python bootstrap_ci.py --holdout-yaml configs/frozen_holdout.yaml

# Expectancy table
python expectancy.py --holdout-yaml configs/frozen_holdout.yaml

# skfolio portfolio (provisional — needs Phase D retrain first)
python portfolio_skfolio.py --holdout-yaml configs/frozen_holdout.yaml --compare-expectancy

# NautilusTrader backtest (fallback runner, WDAC-compatible)
python -m nautilus_strategy.backtest_runner --fallback

# Smoke test (no data download)
python portfolio_skfolio.py --smoke-test
```
