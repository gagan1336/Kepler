---
date: 2026-08-21
severity: "high"
affected_phases: ["Phase 0", "Phase 1"]
---

## What was wrong

During Phase 0 and Phase 1 evaluation, the "in-universe" test set (Nifty50 stocks) was scored using the same model that was **trained on those exact stocks**. The eval script (`evaluate_model.py`) passed the full Nifty50 list as a test set without excluding it from the training corpus.

Result: AUC of **0.9726** was reported for the in-universe Nifty50 set. This is a memorisation artifact, not generalisation.

## How it was caught

The 0.9726 AUC was immediately suspicious on inspection — a well-calibrated binary classifier on financial data rarely exceeds 0.75 on genuinely unseen data. Cross-referencing the training ticker list against the eval ticker list showed 100% overlap for the Nifty50 in-universe test set.

The OOD sets ("Nifty200 Extra", "Nifty500 Extra") were genuinely held out and showed AUC of 0.55–0.58, consistent with reasonable but modest generalisation.

## Fix applied

The eval report structure was revised to clearly label test sets as "in-universe" vs "OOD". The frozen holdout set was created on 2026-08-23 with a hard rule: holdout tickers must never appear in any training file. The `tests/test_no_holdout_leakage.py` test suite enforces this at CI time.

The inflated in-universe AUC of 0.9726 was never used in any downstream analysis — it was flagged immediately as contaminated.

## Numbers that should no longer be quoted

- **AUC = 0.9726** (Nifty50 in-universe, Phase 0/1 eval) — contaminated by training overlap
- **AUC = 0.7843** (Nifty50 in-universe, Phase 1 retrain eval, `eval_20260821_071208.json`) — same contamination
- Any precision/recall figure from the "Nifty50 (in-universe)" test set row in any eval JSON from 2026-08-21
