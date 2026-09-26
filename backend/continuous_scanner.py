"""
KEPLER — Continuous Swing Scanner
==================================
Runs every 2 hours during market hours to:
  1. Download TODAY's price data for all 200 NSE stocks
  2. Apply ALL 14 active strategies to current market conditions
  3. Score each hit using swing_probability.py (Hermes-weighted)
  4. For the TOP 5 high-probability picks, generate a full
     AI-powered Swing Trade Thesis using Gemini
  5. Save results to .cache/swing_picks.json

The frontend SwingStrategiesHub reads this file to display live picks.
This is the "analyst engine" — it finds stocks continuously.
"""

import json
import os
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

_BACKEND_DIR = Path(__file__).parent
_CACHE_DIR   = _BACKEND_DIR / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_PICKS_FILE       = _CACHE_DIR / "swing_picks.json"
_BT_CACHE_FILE    = _CACHE_DIR / "strategy_backtest.json"
_PARAMS_FILE      = _BACKEND_DIR / "configs" / "strategy_params.json"

# ── Universe ───────────────────────────────────────────────────────────────────
SCAN_UNIVERSE = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","BHARTIARTL.NS",
    "ICICIBANK.NS","KOTAKBANK.NS","HINDUNILVR.NS","ITC.NS","LT.NS",
    "SBIN.NS","BAJFINANCE.NS","ASIANPAINT.NS","MARUTI.NS","AXISBANK.NS",
    "SUNPHARMA.NS","TITAN.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS",
    "POWERGRID.NS","NTPC.NS","ONGC.NS","COALINDIA.NS","TECHM.NS",
    "HCLTECH.NS","DRREDDY.NS","BAJAJFINSV.NS","GRASIM.NS","ADANIENT.NS",
    "JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS","CIPLA.NS","EICHERMOT.NS",
    "TATACONSUM.NS","DIVISLAB.NS","APOLLOHOSP.NS","BPCL.NS","HEROMOTOCO.NS",
    "BRITANNIA.NS","INDUSINDBK.NS","SBILIFE.NS","HDFCLIFE.NS","ICICIGI.NS",
    "ADANIPORTS.NS","BAJAJ-AUTO.NS","DMART.NS","PIDILITIND.NS","SIEMENS.NS",
    "HAVELLS.NS","MUTHOOTFIN.NS","CHOLAFIN.NS","IDFCFIRSTB.NS","FEDERALBNK.NS",
    "TATAPOWER.NS","IRCTC.NS","HAL.NS","BEL.NS","DLF.NS","GODREJPROP.NS",
    "PRESTIGE.NS","OBEROIRLTY.NS","LUPIN.NS","AUROPHARMA.NS","ALKEM.NS",
    "TORNTPHARM.NS","ZYDUSLIFE.NS","MAXHEALTH.NS","FORTIS.NS",
    "OFSS.NS","MPHASIS.NS","PERSISTENT.NS","COFORGE.NS","LTTS.NS",
    "POLYCAB.NS","KEI.NS","ASTRAL.NS","DIXON.NS","AMBER.NS","KAYNES.NS",
    "ANGELONE.NS","TVSMOTORS.NS","PAGEIND.NS","TRENT.NS","NMDC.NS",
    "IRFC.NS","RECLTD.NS","JKCEMENT.NS","SHREECEM.NS","AMBUJACEM.NS",
    "ACC.NS","DEEPAKNTR.NS","SRF.NS","PIIND.NS","SOLARINDS.NS",
    "LALPATHLAB.NS","METROPOLIS.NS","BIOCON.NS","NHPC.NS","SJVN.NS",
    "TATACOMM.NS","JUBLFOOD.NS","DEVYANI.NS","KALYANKJIL.NS","MOTHERSON.NS",
    "TATACHEM.NS","IOC.NS","HINDPETRO.NS","IGL.NS","GAIL.NS","PETRONET.NS",
    "CONCOR.NS","ADANIGREEN.NS","MARICO.NS","DABUR.NS","COLPAL.NS",
    "GODREJCP.NS","VOLTAS.NS","CROMPTON.NS","APOLLOTYRE.NS","MRF.NS",
    "BALKRISIND.NS","MANAPPURAM.NS","HDFCAMC.NS","ABB.NS","CUMMINSIND.NS",
    "THERMAX.NS","BHEL.NS","PFC.NS","IREDA.NS","TATAELXSI.NS","CYIENT.NS",
    "KPITTECH.NS","AFFLE.NS","INDIAMART.NS","NAUKRI.NS","ESCORTS.NS",
    "SONACOMS.NS","HINDZINC.NS","M&M.NS","TIINDIA.NS","AUBANK.NS",
    "CDSL.NS","BSE.NS","MCX.NS","SHRIRAMFIN.NS","RAYMOND.NS",
    "COCHINSHIP.NS","INDUSTOWER.NS",
]
SCAN_UNIVERSE = list(dict.fromkeys(SCAN_UNIVERSE))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sf(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return None if (f != f or f == float("inf") or f == float("-inf")) else f
    except Exception:
        return None

def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def _compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _load_backtest_results() -> Dict[str, Any]:
    try:
        with open(_BT_CACHE_FILE, "r") as f:
            return json.load(f).get("strategies", {})
    except Exception:
        return {}

def _load_params() -> Dict:
    try:
        with open(_PARAMS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ── Signal detection (TODAY's data) ───────────────────────────────────────────

def _check_signals_today(df: pd.DataFrame, params: Dict) -> List[str]:
    """Return list of strategy IDs that fire TODAY (last row) for a stock."""
    if df is None or len(df) < 252:
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close", "Volume", "High", "Low", "Open"])
    if len(df) < 252:
        return []

    close  = df["Close"]
    volume = df["Volume"]
    high   = df["High"]
    low    = df["Low"]
    opens  = df["Open"]

    ema20  = _ema(close, 20)
    ema50  = _ema(close, 50)
    ema200 = _ema(close, 200)
    rsi    = _compute_rsi(close, 14)
    vol_avg10 = volume.rolling(10).mean().shift(1)
    vol_ratio  = volume / vol_avg10.replace(0, float("nan"))
    high_52w  = close.rolling(252).max().shift(1)
    low_52w   = close.rolling(252).min().shift(1)
    pct_from_52h = (high_52w - close) / high_52w * 100
    pct_from_52l = (close - low_52w) / low_52w * 100
    body = (close - opens).abs()
    candle_range = (high - low).replace(0, float("nan"))
    body_pct = body / candle_range

    # Get TODAY's values (last row)
    idx = -1

    def v(series):
        try:
            val = _sf(series.iloc[idx])
            return val if val is not None else 0.0
        except Exception:
            return 0.0

    triggered = []

    try:
        p_near52 = params.get("near_52w_high", {})
        if v(pct_from_52h) <= p_near52.get("pct_threshold", 5.0) and v(rsi) < 82 and v(close) > v(ema50):
            triggered.append("near_52w_high")
    except Exception: pass

    try:
        prev_52h = close.rolling(252).max().shift(2)
        p_bk = params.get("breakout_52w", {})
        if v(close) >= v(prev_52h) and v(vol_ratio) >= p_bk.get("min_volume_ratio", 1.2):
            triggered.append("breakout_52w")
    except Exception: pass

    try:
        p_vs = params.get("volume_surge", {})
        if v(vol_ratio) >= p_vs.get("vol_ratio", 3.0) and v(close) > v(opens) and v(close) > v(ema50):
            triggered.append("volume_surge")
    except Exception: pass

    try:
        if v(close) > v(ema20) > 0 and v(ema20) > v(ema50) > 0 and v(ema50) > v(ema200) > 0 and v(rsi) >= 50:
            triggered.append("momentum_leaders")
    except Exception: pass

    try:
        p_rsi_ob = params.get("rsi_oversold_bounce", {})
        if p_rsi_ob.get("rsi_min", 25) <= v(rsi) <= p_rsi_ob.get("rsi_max", 45) and v(close) > v(ema200):
            triggered.append("rsi_oversold_bounce")
    except Exception: pass

    try:
        p_rsimom = params.get("rsi_momentum", {})
        if v(rsi) >= p_rsimom.get("rsi_threshold", 65) and v(close) > v(ema50) and v(close) > v(ema200):
            triggered.append("rsi_momentum")
    except Exception: pass

    try:
        std_10   = close.rolling(10).std()
        std_prev = close.rolling(10).std().shift(15)
        if v(std_10) < v(std_prev) * 0.6 and v(pct_from_52h) <= 12 and v(close) > v(ema50):
            triggered.append("vcp_tight")
    except Exception: pass

    try:
        if v(ema50) > v(ema200) and v(close) > v(ema200):
            # Only trigger if golden cross happened within 45 days
            cross_mask = (ema50 > ema200) & (ema50.shift(1) <= ema200.shift(1))
            if cross_mask.any():
                last_cross = cross_mask[cross_mask].index[-1]
                days_since = (df.index[-1] - last_cross).days
                if days_since <= 45:
                    triggered.append("golden_crossover")
    except Exception: pass

    try:
        p_hrs = params.get("high_rs", {})
        if v(pct_from_52l) >= p_hrs.get("rs_threshold", 30) and v(close) > v(ema50) and v(rsi) >= 50:
            triggered.append("high_rs")
    except Exception: pass

    try:
        in_uptrend = v(ema20) > v(ema50) > 0 and v(ema50) > v(ema200) > 0
        near_ema20 = abs(v(close) - v(ema20)) / max(v(ema20), 1) * 100 <= 2.0
        if in_uptrend and near_ema20 and 40 <= v(rsi) <= 65:
            triggered.append("ema_pullback_bounce")
    except Exception: pass

    try:
        p_mb = params.get("marubozu_breakout", {})
        if v(body_pct) >= p_mb.get("body_pct_threshold", 0.75) and v(close) > v(opens) and v(vol_ratio) >= p_mb.get("vol_ratio", 2.0) and v(close) > v(ema20):
            triggered.append("marubozu_breakout")
    except Exception: pass

    try:
        sma30w = close.rolling(150).mean()
        range_high = close.rolling(30).max().shift(1)
        range_width = (close.rolling(30).max() - close.rolling(30).min()) / close.rolling(30).mean() * 100
        tight_base = _sf(range_width.iloc[-2]) is not None and range_width.iloc[-2] <= 15
        if v(close) > v(sma30w) and tight_base and v(close) >= v(range_high) and v(vol_ratio) >= 1.5:
            triggered.append("stage2_base_breakout")
    except Exception: pass

    try:
        mid_point  = (high + low) / 2
        upper_close = close > mid_point
        high_vol    = vol_ratio >= params.get("accumulation_zone", {}).get("vol_ratio", 2.0)
        accum_day   = (upper_close & high_vol).astype(int)
        accum_count = accum_day.rolling(10).sum()
        if v(accum_count) >= 4 and v(pct_from_52h) <= 15 and v(close) > v(ema50):
            triggered.append("accumulation_zone")
    except Exception: pass

    try:
        p_nc = params.get("news_catalyst_momentum", {})
        day_ret = _sf(close.pct_change().iloc[-1])
        if day_ret and day_ret * 100 >= p_nc.get("price_move_pct", 2.5) and v(vol_ratio) >= p_nc.get("vol_ratio", 2.5) and v(close) > v(ema50) and v(rsi) < 80:
            triggered.append("news_catalyst_momentum")
    except Exception: pass

    return triggered


# ── Fundamental Score ──────────────────────────────────────────────────────────

def _get_fundamental_score(symbol: str) -> Dict:
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}
        score = 0.0
        data = {}

        roe = _sf(info.get("returnOnEquity"))
        if roe and roe > 0.12: score += 25
        data["roe"] = round(roe * 100, 1) if roe else None

        pe = _sf(info.get("trailingPE"))
        if pe and 5 < pe < 40: score += 20
        data["pe"] = round(pe, 1) if pe else None

        rev_growth = _sf(info.get("revenueGrowth"))
        if rev_growth and rev_growth > 0.08: score += 25
        data["rev_growth"] = round(rev_growth * 100, 1) if rev_growth else None

        promoter_pct = _sf(info.get("heldPercentInsiders"))
        if promoter_pct and promoter_pct > 0.35: score += 30
        data["promoter_pct"] = round(promoter_pct * 100, 1) if promoter_pct else None

        market_cap = _sf(info.get("marketCap"))
        data["market_cap"] = market_cap
        data["sector"]     = info.get("sector", "")
        data["industry"]   = info.get("industry", "")

        return {"score": round(score, 1), **data}
    except Exception:
        return {"score": 0.0}


# ── Gemini Deep Research Thesis ────────────────────────────────────────────────

def _generate_thesis(symbol: str, strategies: List[str], technicals: Dict, fundamentals: Dict, probability: float) -> Dict:
    """Call Gemini to write a structured swing trade thesis for the stock."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"thesis": "Gemini API key not configured.", "success": False}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        ticker_name = symbol.replace(".NS", "")
        strat_labels = ", ".join(strategies)

        prompt = f"""You are Kepler, an elite swing trading AI analyst specialized in Indian stock markets (NSE/BSE).

Analyze {ticker_name} ({symbol}) as a swing trade candidate and produce a concise, actionable research thesis.

## Technical Data
- Triggered Strategies: {strat_labels}
- Win Probability (Kepler AI): {probability:.0f}%
- RSI: {technicals.get('rsi', 'N/A')}
- Price vs 52W High: {technicals.get('pct_from_52h', 'N/A')}%
- Price vs 20 EMA: {technicals.get('pct_from_ema20', 'N/A')}%
- Volume Ratio (vs 10d avg): {technicals.get('vol_ratio', 'N/A')}x
- EMA Stack (20>50>200): {technicals.get('ema_aligned', 'N/A')}

## Fundamental Data
- ROE: {fundamentals.get('roe', 'N/A')}%
- P/E Ratio: {fundamentals.get('pe', 'N/A')}
- Revenue Growth: {fundamentals.get('rev_growth', 'N/A')}%
- Promoter Holding: {fundamentals.get('promoter_pct', 'N/A')}%
- Sector: {fundamentals.get('sector', 'N/A')}
- Industry: {fundamentals.get('industry', 'N/A')}

## Current Date: {datetime.now().strftime('%d %B %Y')}

Produce ONLY this JSON format (no markdown, no code blocks, just raw JSON):
{{
  "summary": "2-3 sentence summary of the trade setup",
  "entry_zone": "price range as string e.g. '2450-2480'",
  "target_1": "first target price as number",
  "target_2": "second/extended target price as number",
  "stop_loss": "stop loss price as number",
  "holding_period": "e.g. '2-4 weeks'",
  "catalyst": "key catalyst or trigger for this trade",
  "risk_factors": ["risk 1", "risk 2"],
  "confidence": "HIGH or MODERATE or LOW",
  "trade_type": "MOMENTUM or REVERSAL or BREAKOUT or ACCUMULATION"
}}"""

        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            data = json.loads(json_match.group())
            data["success"] = True
            data["generated_at"] = datetime.now().isoformat()
            return data
        else:
            return {"thesis": raw, "success": True, "generated_at": datetime.now().isoformat()}

    except Exception as e:
        logger.warning(f"Gemini thesis generation failed for {symbol}: {e}")
        return {
            "summary": f"AI thesis generation unavailable: {e}",
            "confidence": "LOW",
            "success": False
        }


# ── Per-stock scoring ──────────────────────────────────────────────────────────

def _score_stock(symbol: str, df: pd.DataFrame, backtest_results: Dict, params: Dict) -> Optional[Dict]:
    """Score a single stock. Returns a pick dict or None if no strategies fire."""
    try:
        if df is None or len(df) < 252:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna(subset=["Close", "Volume", "High", "Low", "Open"])
        if len(df) < 252:
            return None

        triggered = _check_signals_today(df, params)
        if not triggered:
            return None

        close  = df["Close"]
        volume = df["Volume"]
        high   = df["High"]
        low    = df["Low"]
        opens  = df["Open"]
        ema20  = _ema(close, 20)
        ema50  = _ema(close, 50)
        ema200 = _ema(close, 200)
        rsi    = _compute_rsi(close, 14)
        vol_avg10  = volume.rolling(10).mean().shift(1)
        vol_ratio  = volume / vol_avg10.replace(0, float("nan"))
        high_52w   = close.rolling(252).max().shift(1)
        pct_from_52h = (high_52w - close) / high_52w * 100

        curr_price  = _sf(close.iloc[-1]) or 0
        curr_rsi    = _sf(rsi.iloc[-1]) or 0
        curr_vr     = _sf(vol_ratio.iloc[-1]) or 1.0
        curr_ema20  = _sf(ema20.iloc[-1]) or curr_price
        curr_ema50  = _sf(ema50.iloc[-1]) or curr_price
        curr_ema200 = _sf(ema200.iloc[-1]) or curr_price
        pct52h      = _sf(pct_from_52h.iloc[-1]) or 0

        technicals = {
            "price":           round(curr_price, 2),
            "rsi":             round(curr_rsi, 1),
            "vol_ratio":       round(curr_vr, 2),
            "pct_from_52h":    round(pct52h, 2),
            "pct_from_ema20":  round((curr_price - curr_ema20) / max(curr_ema20, 1) * 100, 2),
            "ema20":           round(curr_ema20, 2),
            "ema50":           round(curr_ema50, 2),
            "ema200":          round(curr_ema200, 2),
            "ema_aligned":     curr_price > curr_ema20 > curr_ema50 > curr_ema200,
            "52w_high":        round(_sf(close.rolling(252).max().iloc[-1]) or curr_price, 2),
            "52w_low":         round(_sf(close.rolling(252).min().iloc[-1]) or curr_price, 2),
        }

        # ── Score: strategy win rates (Hermes β) ──────────────────────────────
        strategy_scores = []
        best_strategy   = None
        best_wr         = 0
        for strat in triggered:
            bt = backtest_results.get(strat, {})
            wr = bt.get("primary_stats", {}).get("win_rate") or bt.get("win_rate_primary", 0) or 0
            strategy_scores.append(wr)
            if wr > best_wr:
                best_wr       = wr
                best_strategy = strat

        avg_wr = sum(strategy_scores) / len(strategy_scores) if strategy_scores else 30.0

        # ── ML score proxy (RSI + EMA alignment + vol) ────────────────────────
        ml_components = []
        if curr_rsi > 50:   ml_components.append(min((curr_rsi - 50) / 50 * 100, 100))
        if curr_ema20 > 0 and curr_ema50 > 0 and curr_price > curr_ema50: ml_components.append(60)
        if curr_vr > 1.5:   ml_components.append(min(curr_vr / 3.0 * 80, 80))
        ml_score = sum(ml_components) / max(len(ml_components), 1)

        # ── Fundamentals ──────────────────────────────────────────────────────
        fund = _get_fundamental_score(symbol)
        fund_score = fund.get("score", 0)

        # ── Hermes-weighted composite probability ─────────────────────────────
        # Load current weights from hermes_weights.json
        hermes_path = _BACKEND_DIR / "configs" / "hermes_weights.json"
        try:
            with open(hermes_path, "r") as f:
                w = json.load(f).get("weights", {})
        except Exception:
            w = {}

        alpha = w.get("alpha", 0.40)
        beta  = w.get("beta",  0.35)
        gamma = w.get("gamma", 0.12)
        delta = w.get("delta", 0.08)

        raw_prob = (
            alpha * ml_score
          + beta  * avg_wr
          + delta * fund_score
        )
        prob = max(10.0, min(95.0, raw_prob))

        confidence = "HIGH" if prob >= 68 else "MODERATE" if prob >= 48 else "LOW"

        # ── Expected return / hold days ────────────────────────────────────────
        best_bt = backtest_results.get(best_strategy or triggered[0], {})
        expected_return = _sf(best_bt.get("primary_stats", {}).get("avg_return")) or 6.5
        hold_days       = best_bt.get("target_horizon_days", 20)

        return {
            "symbol":           symbol,
            "ticker":           symbol.replace(".NS", ""),
            "price":            curr_price,
            "win_probability":  round(prob, 1),
            "confidence":       confidence,
            "strategies":       triggered,
            "best_strategy":    best_strategy or triggered[0],
            "strategy_count":   len(triggered),
            "expected_return":  round(expected_return, 1),
            "hold_days":        hold_days,
            "technicals":       technicals,
            "fundamentals":     {k: v for k, v in fund.items() if k != "score"},
            "fund_score":       fund_score,
            "scanned_at":       datetime.now().isoformat(),
        }

    except Exception as e:
        logger.debug(f"Error scoring {symbol}: {e}")
        return None


# ── Main scanner ───────────────────────────────────────────────────────────────

def run_scan(generate_thesis: bool = True) -> Dict:
    """
    Full scan: download data → apply strategies → score → generate theses.
    Returns the full results dict (also saved to cache).
    """
    t0 = time.time()
    logger.info(f"Swing Scanner starting: {len(SCAN_UNIVERSE)} stocks")

    backtest_results = _load_backtest_results()
    params           = _load_params()

    if not backtest_results:
        logger.warning("No backtest results found. Run strategy_backtester.py first.")

    # ── Download historical data for all stocks ────────────────────────────────
    logger.info("Downloading 6-month price history...")
    try:
        raw_data = yf.download(
            SCAN_UNIVERSE,
            period="13mo",      # need 252+ days for indicators
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception as e:
        logger.error(f"Data download failed: {e}")
        return {"error": str(e), "picks": [], "scanned_at": datetime.now().isoformat()}

    # ── Score each stock ───────────────────────────────────────────────────────
    picks = []
    for symbol in SCAN_UNIVERSE:
        try:
            if isinstance(raw_data.columns, pd.MultiIndex):
                df = raw_data[symbol].copy() if symbol in raw_data.columns.get_level_values(0) else None
            else:
                df = raw_data.copy()

            if df is None or df.empty:
                continue

            pick = _score_stock(symbol, df, backtest_results, params)
            if pick:
                picks.append(pick)
                logger.info(f"  HIT: {symbol} | strategies={pick['strategy_count']} | prob={pick['win_probability']}%")

        except Exception as e:
            logger.debug(f"Skipping {symbol}: {e}")
            continue

    # ── Sort by probability ────────────────────────────────────────────────────
    picks.sort(key=lambda x: (-x["win_probability"], -x["strategy_count"]))
    logger.info(f"Found {len(picks)} swing trade candidates in {time.time()-t0:.1f}s")

    # ── Generate AI thesis for top 5 ──────────────────────────────────────────
    top_picks = picks[:8]
    if generate_thesis and top_picks:
        logger.info(f"Generating Gemini thesis for top {len(top_picks)} picks...")
        for pick in top_picks[:5]:
            pick["thesis"] = _generate_thesis(
                symbol      = pick["symbol"],
                strategies  = pick["strategies"],
                technicals  = pick["technicals"],
                fundamentals= pick["fundamentals"],
                probability = pick["win_probability"],
            )
            time.sleep(1.5)  # rate limit

    # ── Save to cache ──────────────────────────────────────────────────────────
    result = {
        "picks":            picks[:20],          # top 20 stored
        "total_hits":       len(picks),
        "strategies_active": len(backtest_results),
        "scanned_at":       datetime.now().isoformat(),
        "scan_duration_s":  round(time.time() - t0, 1),
    }

    with open(_PICKS_FILE, "w") as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"Saved {len(picks[:20])} picks to {_PICKS_FILE}")
    return result


def load_cached_picks() -> Dict:
    """Read cached picks from disk (used by the API)."""
    try:
        with open(_PICKS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"picks": [], "total_hits": 0, "scanned_at": None, "error": "No scan data yet. Scanner runs every 2 hours."}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-thesis", action="store_true", help="Skip Gemini thesis generation")
    args = parser.parse_args()

    result = run_scan(generate_thesis=not args.no_thesis)
    print(f"\nScan complete: {result['total_hits']} hits found")
    for p in result.get("picks", [])[:10]:
        print(f"  {p['ticker']:15s} prob={p['win_probability']}% conf={p['confidence']} strats={','.join(p['strategies'])}")
