---
date: 2026-08-23
severity: "high"
affected_phases: ["Phase 1"]
---

## What was wrong

The Phase 1 OOD AUC of **0.7743** (Nifty200 Extra test set, `eval_20260821_071208.json`) was initially treated as the primary evidence of model quality. This number was later found to be inflated for two reasons:

1. **The test set was not a clean holdout.** "Nifty200 Extra" is a rolling selection from the Nifty200 universe. Some of these stocks had been seen during training in earlier experimental iterations, and the split boundary was not strictly enforced at the stock level — only at the time level.

2. **Timezone and monotonic sort bugs** (see [[2026-08-23-tz-monotonic-bugs]]) caused date alignment errors that inadvertently inflated apparent AUC by misaligning forward returns with the wrong bar's features.

After locking the frozen-42 holdout (2026-08-23) and fixing the bugs, the clean holdout AUC dropped to:
- Phase C-r (pre-bug fix): **0.5608** (`bootstrap_ci_20260823_173606.json`)
- Phase C-r (post-bug fix, final): **0.6585** (`bootstrap_ci_20260824_074749.json`)

The 0.5608 result was itself a transitional number — the tz bug was partially fixed but cross-sectional rank features still had issues at that point.

## How it was caught

The frozen holdout was evaluated immediately after being locked. The AUC of 0.5608 on clean data vs 0.7743 on the "OOD" set was a clear discrepancy. Investigating the eval code revealed the test set contamination and the date alignment bugs.

## Fix applied

1. **Holdout locked** in `configs/frozen_holdout.yaml` — 42 tickers (NIFTY_500_EXTRA) permanently reserved
2. **Leakage test** added: `tests/test_no_holdout_leakage.py` — fails CI if any holdout ticker appears in any training list
3. **Bug fixes** applied (see [[2026-08-23-tz-monotonic-bugs]])
4. **Frozen holdout** is the sole source of truth for AUC reporting from Phase C-r onward

## Numbers that should no longer be quoted

- **AUC = 0.7743** (Nifty200 Extra OOD, `eval_20260821_071208.json`) — not a clean holdout, partially contaminated, pre-bug-fix
- **AUC = 0.5555** (Nifty200 Extra OOD, `eval_20260821_070620.json`) — same dataset, same contamination concern
- **AUC = 0.5608** (frozen holdout, `bootstrap_ci_20260823_173606.json`) — transitional number during bug-fix process; post-fix AUC is 0.6585
- Any precision or expectancy number from eval files dated 2026-08-21 applied to the frozen-42 set
