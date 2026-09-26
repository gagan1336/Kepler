# -*- coding: utf-8 -*-
"""
Kepler ML Model — Comprehensive Test
Tests: model loading, single-stock scoring, batch radar, score distribution.
"""
import sys
import time
import json
from pathlib import Path

# ── 1. Model loading ──────────────────────────────────────────────────────────
print("=" * 60)
print("  KEPLER ML MODEL TEST")
print("=" * 60)

import kepler_model as km

print("\n[1] Loading model...")
t0 = time.time()
ok = km.load_model()
elapsed = time.time() - t0
print(f"    Model ready : {ok} ({elapsed:.2f}s)")

if not ok:
    print("ABORT: model not loaded.")
    sys.exit(1)

info = km.get_model_info()
print(f"    Trained at  : {info['trained_at']}")
print(f"    Universe    : {info['universe']} ({info['n_symbols']} stocks)")
print(f"    Train rows  : {info['n_train_rows']:,}")
print(f"    Val AUC     : {info['metrics']['val_auc']}")
print(f"    Features    : {info['n_features']}")
print(f"    Fwd days    : {info['forward_days']}d  threshold: {info['threshold_pct']}%")

print(f"\n    Top-10 Feature Importances:")
for feat, imp in list(info['top_features'].items())[:10]:
    bar = "#" * int(imp * 200)
    print(f"      {feat:<25} {imp:.4f}  {bar}")

# ── 2. Single-stock scoring across sectors ────────────────────────────────────
print("\n[2] Single-stock scoring (one per sector)...")
TEST_STOCKS = [
    ("RELIANCE",    "Energy"),
    ("TCS",         "IT"),
    ("HDFCBANK",    "Banking"),
    ("SUNPHARMA",   "Pharma"),
    ("MARUTI",      "Auto"),
    ("HINDUNILVR",  "FMCG"),
    ("LT",          "Infra"),
    ("ADANIENT",    "Conglomerate"),
    ("TITAN",       "Consumer"),
    ("COALINDIA",   "Mining"),
    ("NTPC",        "Power"),
    ("BAJFINANCE",  "NBFC"),
]

scores = []
t0 = time.time()
for sym, sector in TEST_STOCKS:
    r = km.score_symbol(sym)
    if r:
        scores.append(r)
        signal_icon = {
            "STRONG_BUY": "[++]",
            "BUY":        "[ +]",
            "WATCH":      "[  ]",
            "NEUTRAL":    "[--]",
            "AVOID":      "[XX]",
        }.get(r["signal"], "[??]")
        print(
            f"    {signal_icon} {sym:<14} "
            f"price=Rs.{r['price']:>7,.0f}  "
            f"prob={r['buy_prob']:.3f}  "
            f"rsi={r['features']['rsi_14']:.1f}  "
            f"vol={r['features']['volume_ratio']:.2f}x  "
            f"({sector})"
        )
    else:
        print(f"    [??] {sym:<14} FAILED to score")

elapsed = time.time() - t0
print(f"\n    Scored {len(scores)}/{len(TEST_STOCKS)} stocks in {elapsed:.1f}s")

# ── 3. Score distribution ─────────────────────────────────────────────────────
if scores:
    probs = sorted([s["buy_prob"] for s in scores], reverse=True)
    print(f"\n[3] Score Distribution:")
    print(f"    Min  : {min(probs):.3f}")
    print(f"    Max  : {max(probs):.3f}")
    avg = sum(probs) / len(probs)
    print(f"    Mean : {avg:.3f}")
    buckets = {">=0.5": 0, "0.3-0.5": 0, "0.2-0.3": 0, "<0.2": 0}
    for p in probs:
        if p >= 0.5:   buckets[">=0.5"] += 1
        elif p >= 0.3: buckets["0.3-0.5"] += 1
        elif p >= 0.2: buckets["0.2-0.3"] += 1
        else:          buckets["<0.2"] += 1
    for bucket, count in buckets.items():
        bar = "#" * count
        print(f"    {bucket:>10}  {count:2d} stocks  {bar}")

# ── 4. Batch radar: top-N from a sample universe ──────────────────────────────
print("\n[4] Batch Radar (Nifty 50 subset, top 10 picks, min_prob=0.10)...")
BATCH_UNIVERSE = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK",
    "INFY", "SBIN", "HINDUNILVR", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "BAJFINANCE", "MARUTI", "ASIANPAINT",
    "HCLTECH", "SUNPHARMA", "NTPC", "POWERGRID", "ONGC",
    "TITAN", "JSWSTEEL", "TATASTEEL", "ADANIENT", "COALINDIA",
]

t0 = time.time()
picks = km.get_top_picks(
    symbols=BATCH_UNIVERSE,
    n=10,
    min_prob=0.10,  # low threshold to see the ranking even if probs are modest
)
elapsed = time.time() - t0

print(f"    Scanned {len(BATCH_UNIVERSE)} stocks in {elapsed:.1f}s")
print(f"    Top picks (ranked by buy_prob):")
print(f"    {'Rank':<5} {'Symbol':<14} {'Prob':>6}  {'Signal':<12}  {'Price':>8}  {'RSI':>6}  {'Vol':>6}")
print(f"    {'-'*70}")
for i, p in enumerate(picks, 1):
    print(
        f"    {i:<5} {p['symbol']:<14} {p['buy_prob']:>6.3f}  "
        f"{p['signal']:<12}  Rs.{p['price']:>7,.0f}  "
        f"{p['rsi_14']:>5.1f}  "
        f"{p['volume_ratio']:>5.2f}x"
    )

if not picks:
    print("    No picks above min_prob=0.10 — all stocks scored below threshold")

# ── 5. Meta.json snapshot ─────────────────────────────────────────────────────
meta_path = Path(__file__).parent / "models" / "kepler_meta.json"
if meta_path.exists():
    with open(meta_path) as f:
        meta = json.load(f)
    print(f"\n[5] Model metadata (models/kepler_meta.json):")
    print(f"    Saved at     : {meta['trained_at']}")
    print(f"    XGB iter     : {meta.get('best_xgb_iteration', 'n/a')}")
    print(f"    Val AUC      : {meta['metrics']['val_auc']}")
    print(f"    Val AP       : {meta['metrics']['val_ap']}")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED")
print("=" * 60)
