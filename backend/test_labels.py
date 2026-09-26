from ml_features import generate_labels
import time

print("Testing vectorised generate_labels on RELIANCE...")
t0 = time.time()
df = generate_labels("RELIANCE", forward_days=10, threshold_pct=5.0)
elapsed = time.time() - t0

if df is not None:
    pos_rate = df["label"].mean() * 100
    print(f"OK: {len(df)} rows in {elapsed:.2f}s | pos rate: {pos_rate:.1f}%")
    print(df[["rsi_14", "macd_hist", "adx_14", "bb_pct_b", "label"]].tail(3).to_string())
else:
    print("FAILED: returned None")
