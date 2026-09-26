---
date: 2026-08-23
severity: "medium"
affected_phases: ["Phase 1", "Phase C-r (transitional)"]
---

## What was wrong

Two related bugs were found in the feature generation pipeline that affected date alignment between features and forward returns:

### Bug 1 — Timezone mismatch

`yfinance` returns OHLCV data with a timezone-aware `DatetimeIndex` (UTC or exchange local). The feature pipeline cast this to a naive datetime before joining with the forward-returns label. When the index was tz-aware on one side and tz-naive on the other, pandas silently dropped rows or misaligned them rather than raising an error. The result was that some bars had their features joined to the wrong forward return.

Affected code: `ml_features.py::generate_labels()` — the line converting the yfinance index to date did not strip timezone before `pd.to_datetime()`.

### Bug 2 — Non-monotonic sort after concat

When multiple ticker DataFrames were concatenated and then sorted by `(symbol, date)`, the sort was not applied with `ignore_index=True`, leaving the underlying integer index non-monotonic. Subsequent `.iloc[]` and `.shift()` operations on the non-monotonic index silently computed incorrect rolling window boundaries, causing future-bar features to leak into past-bar rows.

Affected code: `ml_features.py::generate_labels()` — the `concat` + `sort_values` block.

## How it was caught

After locking the frozen holdout and running `bootstrap_ci.py`, the AUC of 0.5608 was lower than expected for the Phase C-r model. Inspecting individual symbol DataFrames revealed date-shifted anomalies: the forward return for bar `t` was occasionally joined to bar `t-1` features, inflating apparent hit rates for some symbols.

The timezone bug was caught by adding `assert df.index.tz is None` before label join. The monotonic bug was caught by adding `assert df.index.is_monotonic_increasing` after sort.

## Fix applied

In `ml_features.py::generate_labels()`:

1. **Timezone fix**: After downloading via yfinance, the index is explicitly converted:
   ```python
   df.index = pd.to_datetime(df.index).tz_localize(None)
   ```

2. **Monotonic sort fix**: The concat block now uses:
   ```python
   df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
   assert df.index.is_monotonic_increasing, "Index is not monotonic after sort"
   ```

Both fixes were applied before the final Phase C-r holdout evaluation. The transitional `bootstrap_ci_20260823_173606.json` result (AUC = 0.5608) was produced with only the timezone fix applied; the monotonic fix was applied subsequently, yielding the final AUC of 0.6585.

## Numbers that should no longer be quoted

- **AUC = 0.5608** (`bootstrap_ci_20260823_173606.json`) — produced during the bug-fix transition; tz bug was fixed but monotonic bug was not yet fully resolved. This is a transitional artefact, not a stable result.
- Any per-symbol hit rate or precision number computed from eval files dated 2026-08-21 or from the first bootstrap CI run dated 2026-08-23T17:36.
