"""
KEPLER — Swing Trade Win Probability Engine
=============================================
Computes a 0–100% probability that a swing trade will succeed
(gain ≥ 5% within the target holding window).

Formula:
    P(success) = clamp(
        α × ML_score
      + β × strategy_win_rate
      + γ × news_boost
      + δ × fundamental_bonus
    )

Default weights (overridable by Hermes via hermes_weights.json):
    α = 0.45   ML model calibrated probability
    β = 0.35   Strategy historical win rate
    γ = 0.12   News sentiment boost/penalty
    δ = 0.08   Fundamental quality bonus

Output per stock:
    win_probability       : 0–100 (overall % chance)
    probability_breakdown : {ml, strategy, news, fundamental}
    confidence_band       : "HIGH" | "MODERATE" | "LOW"
    expected_return_pct   : weighted expected return
    recommended_hold_days : optimal hold period from backtest
    best_strategy         : highest win-rate strategy that triggered
"""

import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

_BACKEND_DIR    = Path(__file__).parent
_HERMES_WEIGHTS = _BACKEND_DIR / "configs" / "hermes_weights.json"
_CACHE_DIR      = _BACKEND_DIR / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_PROB_CACHE: Dict[str, Dict] = {}
_PROB_TTL   = 30 * 60   # 30 minutes


# ── Weight loading (with Hermes override support) ──────────────────────────────

_DEFAULT_WEIGHTS = {
    "alpha": 0.45,   # ML model contribution
    "beta":  0.35,   # Strategy win rate contribution
    "gamma": 0.12,   # News sentiment contribution
    "delta": 0.08,   # Fundamental quality contribution
    # Per-feature weights for the fundamental bonus
    "fund_roe_weight":      0.30,
    "fund_pe_weight":       0.25,
    "fund_rev_weight":      0.25,
    "fund_promoter_weight": 0.20,
}


def _load_weights() -> Dict[str, float]:
    """Load weights from Hermes override file if it exists, else use defaults."""
    try:
        if _HERMES_WEIGHTS.exists():
            with open(_HERMES_WEIGHTS, encoding="utf-8") as f:
                data = json.load(f)
            weights = {**_DEFAULT_WEIGHTS, **data.get("weights", {})}
            logger.debug(f"Hermes weights loaded (updated {data.get('updated_at', 'unknown')})")
            return weights
    except Exception as e:
        logger.debug(f"Hermes weights load failed, using defaults: {e}")
    return dict(_DEFAULT_WEIGHTS)


def _sf(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


# ── Component scorers ──────────────────────────────────────────────────────────

def _ml_component(stock: Dict) -> float:
    """
    Get ML model probability for this stock.
    Tries to use the loaded Kepler model; falls back to a rule-based estimate.
    Returns 0–100.
    """
    try:
        from kepler_model import predict_probability
        prob = predict_probability(stock.get("symbol_ns") or stock.get("symbol") + ".NS")
        if prob is not None:
            return float(prob) * 100
    except Exception:
        pass

    # Rule-based fallback based on conviction score / swing score
    base = 50.0
    # RSI in sweet zone
    rsi = _sf(stock.get("rsi") or stock.get("rsi_14")) or 50
    if 50 <= rsi <= 65:
        base += 8
    elif 45 <= rsi < 50:
        base += 3
    elif rsi > 75:
        base -= 5

    # EMA structure
    if stock.get("ema_perfect"):
        base += 10
    elif stock.get("ema_above_50_200") or (
        stock.get("dma_signal") and "20>50>200" in str(stock.get("dma_signal", ""))
    ):
        base += 5

    # Volume
    vol = _sf(stock.get("vol_ratio") or stock.get("volume_ratio")) or 1.0
    if vol >= 2.5:
        base += 8
    elif vol >= 1.5:
        base += 4

    # MACD
    if stock.get("macd_above"):
        base += 5

    # RS vs Nifty
    rs = _sf(stock.get("rs_vs_nifty")) or 0
    if rs > 10:
        base += 8
    elif rs > 5:
        base += 4
    elif rs < -5:
        base -= 6

    return max(20.0, min(85.0, base))


def _strategy_component(triggered_strategies: List[str], backtest_data: Optional[Dict]) -> tuple:
    """
    Returns (score_0_to_100, best_strategy_key, best_strategy_win_rate).
    Uses backtest win rates for each triggered strategy, picks the best.
    """
    if not triggered_strategies:
        return 45.0, None, None

    if not backtest_data:
        # Rough defaults per strategy type if no backtest data
        _strategy_defaults = {
            "near_52w_high":       62.0,
            "breakout_52w":        65.0,
            "volume_surge":        58.0,
            "momentum_leaders":    67.0,
            "rsi_oversold_bounce": 58.0,
            "rsi_momentum":        63.0,
            "vcp_tight":           68.0,
            "golden_crossover":    61.0,
            "high_rs":             64.0,
            "ema_pullback_bounce": 63.0,
            "marubozu_breakout":   60.0,
            "stage2_base_breakout": 66.0,
            "accumulation_zone":   61.0,
            "news_catalyst_momentum": 59.0,
        }
        best_wr   = max((_strategy_defaults.get(s, 50.0) for s in triggered_strategies), default=50.0)
        best_strat = max(triggered_strategies, key=lambda s: _strategy_defaults.get(s, 50.0))
        return best_wr, best_strat, best_wr

    strategies_bt = backtest_data.get("strategies", {})
    best_wr    = 0.0
    best_strat = None
    for s in triggered_strategies:
        bt = strategies_bt.get(s, {})
        wr = _sf(bt.get("win_rate_primary"))
        if wr and wr > best_wr:
            best_wr    = wr
            best_strat = s

    if best_wr == 0:
        return 45.0, triggered_strategies[0] if triggered_strategies else None, None

    return best_wr, best_strat, best_wr


def _news_component(sentiment: Optional[Dict]) -> float:
    """Returns the news sentiment boost/penalty in percentage points (-10 to +8)."""
    if not sentiment:
        return 0.0
    return _sf(sentiment.get("sentiment_boost")) or 0.0


def _fundamental_component(fundamentals: Optional[Dict], weights: Dict) -> float:
    """Returns a 0–15 point fundamental quality bonus."""
    if not fundamentals:
        return 5.0   # neutral

    score = 0.0
    # ROE quality
    roe = _sf(fundamentals.get("roe"))
    if roe:
        if roe > 20:   score += weights["fund_roe_weight"] * 15
        elif roe > 12: score += weights["fund_roe_weight"] * 8

    # PE (reasonable valuation)
    pe = _sf(fundamentals.get("pe_ratio"))
    if pe and pe > 0:
        if pe < 25:    score += weights["fund_pe_weight"] * 15
        elif pe < 40:  score += weights["fund_pe_weight"] * 8
        elif pe > 80:  score -= 3   # expensive

    # Revenue growth
    rev = _sf(fundamentals.get("revenue_cagr_3y") or fundamentals.get("revenue_growth"))
    if rev:
        if rev > 15:   score += weights["fund_rev_weight"] * 15
        elif rev > 8:  score += weights["fund_rev_weight"] * 6

    # Promoter holding
    promoter = _sf(fundamentals.get("promoter_holding"))
    if promoter and promoter > 50:
        score += weights["fund_promoter_weight"] * 10

    return max(0.0, min(15.0, score))


# ── Triggered strategy detection ──────────────────────────────────────────────

def _detect_triggered_strategies(stock: Dict) -> List[str]:
    """
    Detect which strategies are currently triggered for a given stock.
    Works from the pre-computed stock fields (no re-fetch needed).
    """
    triggered = []

    pct_from_52h = _sf(stock.get("pct_from_52h")) or 100
    pct_from_52l = _sf(stock.get("pct_from_52l")) or 0
    rsi          = _sf(stock.get("rsi") or stock.get("rsi_14")) or 50
    vol_ratio    = _sf(stock.get("vol_ratio") or stock.get("volume_ratio")) or 1.0
    dma_signal   = str(stock.get("dma_signal") or "")
    ema_perfect  = bool(stock.get("ema_perfect"))
    ema_50_200   = bool(stock.get("ema_above_50_200"))
    macd_above   = bool(stock.get("macd_above"))
    vcp          = bool(stock.get("vcp_tightening"))
    golden_cross = bool(stock.get("golden_cross") or stock.get("_golden_cross_days"))
    rs           = _sf(stock.get("rs_vs_nifty")) or 0
    patterns     = stock.get("patterns") or []
    change_today = _sf(stock.get("change_pct_today") or stock.get("ret_30d_approx")) or 0

    if pct_from_52h <= 5 and rsi < 82:
        triggered.append("near_52w_high")
    if pct_from_52h <= 0.5:
        triggered.append("breakout_52w")
    if vol_ratio >= 3.0 and change_today > 0:
        triggered.append("volume_surge")
    if ema_perfect and rsi >= 50:
        triggered.append("momentum_leaders")
    if "20>50>200" in dma_signal and rsi >= 50:
        triggered.append("momentum_leaders")
    if 25 <= rsi <= 45:
        triggered.append("rsi_oversold_bounce")
    if rsi >= 65 and (ema_50_200 or ema_perfect):
        triggered.append("rsi_momentum")
    if vcp and pct_from_52h <= 12:
        triggered.append("vcp_tight")
    if golden_cross:
        triggered.append("golden_crossover")
    if pct_from_52l >= 30 and rsi >= 50:
        triggered.append("high_rs")
    if ema_perfect and 40 <= rsi <= 65 and pct_from_52h >= 3:
        triggered.append("ema_pullback_bounce")
    if change_today >= 2.5 and vol_ratio >= 2.5 and rsi < 80:
        triggered.append("marubozu_breakout")
        triggered.append("news_catalyst_momentum")

    # From patterns list (picks_engine format)
    if "VCP Setup" in str(patterns):
        triggered.append("vcp_tight")
    if "52W Breakout" in str(patterns):
        triggered.append("breakout_52w")
    if "Stage 2" in str(patterns):
        triggered.append("stage2_base_breakout")

    return list(dict.fromkeys(triggered))  # deduplicate, preserve order


# ── Recommended hold period ────────────────────────────────────────────────────

def _recommended_hold(best_strategy: Optional[str], backtest_data: Optional[Dict]) -> int:
    """Returns the recommended hold period in days."""
    if not best_strategy:
        return 20

    # Try to get from backtest data
    if backtest_data:
        meta = backtest_data.get("strategies", {}).get(best_strategy, {})
        target = meta.get("target_horizon")
        if target:
            return int(target)

    # Fallback defaults
    _hold_defaults = {
        "near_52w_high": 20, "breakout_52w": 20, "volume_surge": 10,
        "momentum_leaders": 30, "rsi_oversold_bounce": 20, "rsi_momentum": 20,
        "vcp_tight": 30, "golden_crossover": 45, "high_rs": 30,
        "ema_pullback_bounce": 20, "marubozu_breakout": 10,
        "stage2_base_breakout": 45, "accumulation_zone": 30,
        "news_catalyst_momentum": 10,
    }
    return _hold_defaults.get(best_strategy, 20)


# ── Expected return calculation ────────────────────────────────────────────────

def _expected_return(win_prob: float, best_strategy: Optional[str], backtest_data: Optional[Dict]) -> Dict:
    """Compute expected return range from backtest avg win/loss stats."""
    base_return = 0.0
    pessimistic = 0.0
    optimistic  = 0.0

    if backtest_data and best_strategy:
        strat_bt = backtest_data.get("strategies", {}).get(best_strategy, {})
        primary  = strat_bt.get("primary_stats", {})
        avg_win  = _sf(primary.get("avg_win"))  or 8.0
        avg_loss = _sf(primary.get("avg_loss")) or -4.0
        wr_frac  = (win_prob / 100)
        base_return  = round(wr_frac * avg_win + (1 - wr_frac) * avg_loss, 1)
        pessimistic  = round(avg_loss * 1.5, 1)
        optimistic   = round(avg_win * 1.2, 1)
    else:
        wr_frac     = win_prob / 100
        base_return = round(wr_frac * 9.0 + (1 - wr_frac) * -4.5, 1)
        pessimistic = -6.0
        optimistic  = 12.0

    return {
        "base":        base_return,
        "pessimistic": pessimistic,
        "optimistic":  optimistic,
    }


# ── Main probability scorer ────────────────────────────────────────────────────

def compute_win_probability(
    stock: Dict,
    fundamentals: Optional[Dict] = None,
    sentiment: Optional[Dict] = None,
    backtest_data: Optional[Dict] = None,
) -> Dict:
    """
    Compute the win probability for a single stock.

    Args:
        stock:         Stock dict from picks_engine or swing_screener
        fundamentals:  Optional fundamental data dict
        sentiment:     Optional news sentiment dict
        backtest_data: Optional full backtest results dict

    Returns:
        Dict with win_probability (0-100), breakdown, confidence, etc.
    """
    weights = _load_weights()

    # ── 1. ML component ───────────────────────────────────────────────────────
    ml_raw = _ml_component(stock)               # 0–100
    ml_contribution = weights["alpha"] * ml_raw  # weighted share

    # ── 2. Strategy component ─────────────────────────────────────────────────
    triggered = _detect_triggered_strategies(stock)
    strat_raw, best_strategy, best_wr = _strategy_component(triggered, backtest_data)
    strat_contribution = weights["beta"] * strat_raw  # weighted share

    # ── 3. News component ─────────────────────────────────────────────────────
    news_boost     = _news_component(sentiment)         # -10 to +8 pp
    news_contribution = weights["gamma"] * (50 + news_boost * 5)  # normalise

    # ── 4. Fundamental component ──────────────────────────────────────────────
    fund_raw           = _fundamental_component(fundamentals, weights)  # 0–15
    fund_contribution  = weights["delta"] * (fund_raw / 15 * 100)

    # ── Composite ─────────────────────────────────────────────────────────────
    raw_prob = (
        ml_contribution
        + strat_contribution
        + news_contribution
        + fund_contribution
    )

    # Apply news boost/penalty directly
    raw_prob += news_boost

    # Clamp to [15, 92] — never claim certainty or impossibility
    win_probability = round(max(15.0, min(92.0, raw_prob)), 1)

    # ── Confidence band ───────────────────────────────────────────────────────
    signal_count = len(triggered)
    has_news     = sentiment and sentiment.get("sentiment_score", 0) != 0
    has_fund     = fundamentals is not None

    if win_probability >= 70 and signal_count >= 2:
        confidence_band = "HIGH"
        confidence_color = "#10b981"
    elif win_probability >= 55:
        confidence_band = "MODERATE"
        confidence_color = "#f59e0b"
    else:
        confidence_band = "LOW"
        confidence_color = "#ef4444"

    # ── Supporting data ───────────────────────────────────────────────────────
    hold_days    = _recommended_hold(best_strategy, backtest_data)
    exp_return   = _expected_return(win_probability, best_strategy, backtest_data)

    return {
        "win_probability":   win_probability,
        "confidence_band":   confidence_band,
        "confidence_color":  confidence_color,
        "best_strategy":     best_strategy,
        "best_strategy_wr":  best_wr,
        "triggered_strategies": triggered,
        "recommended_hold_days": hold_days,
        "expected_return":   exp_return,
        "probability_breakdown": {
            "ml_component":         round(ml_contribution, 1),
            "strategy_component":   round(strat_contribution, 1),
            "news_component":       round(news_contribution, 1),
            "fundamental_component": round(fund_contribution, 1),
            "news_boost_pp":        news_boost,
            "ml_raw_score":         round(ml_raw, 1),
            "strategy_win_rate":    best_wr,
        },
        "news_catalyst":  sentiment.get("news_catalyst", False) if sentiment else False,
        "news_risk":      sentiment.get("news_risk", False) if sentiment else False,
        "news_headline":  sentiment.get("top_headline") if sentiment else None,
        "weights_source": "hermes" if _HERMES_WEIGHTS.exists() else "default",
    }


def batch_compute_probabilities(
    stocks: List[Dict],
    fundamentals_map: Optional[Dict] = None,
    sentiments_map: Optional[Dict] = None,
    backtest_data: Optional[Dict] = None,
) -> List[Dict]:
    """
    Attach win_probability to each stock in the list.
    Returns the list with new probability fields merged in.
    """
    fundamentals_map = fundamentals_map or {}
    sentiments_map   = sentiments_map or {}

    enriched = []
    for stock in stocks:
        sym_ns = stock.get("symbol_ns") or (stock.get("symbol", "") + ".NS")
        sym_ns = sym_ns if sym_ns.endswith(".NS") else sym_ns + ".NS"

        fund = fundamentals_map.get(sym_ns) or fundamentals_map.get(sym_ns.replace(".NS", ""))
        sent = sentiments_map.get(sym_ns) or sentiments_map.get(sym_ns.replace(".NS", ""))

        prob_data = compute_win_probability(
            stock, fundamentals=fund, sentiment=sent, backtest_data=backtest_data
        )
        enriched.append({**stock, **prob_data})

    # Sort by win_probability descending
    enriched.sort(key=lambda x: x.get("win_probability", 0), reverse=True)
    return enriched


if __name__ == "__main__":
    # Quick smoke test
    test_stock = {
        "symbol":          "RELIANCE",
        "symbol_ns":       "RELIANCE.NS",
        "rsi":             62.0,
        "ema_perfect":     True,
        "ema_above_50_200": True,
        "macd_above":      True,
        "vol_ratio":       2.1,
        "rs_vs_nifty":     8.5,
        "pct_from_52h":    3.2,
        "pct_from_52l":    42.0,
        "vcp_tightening":  True,
        "patterns":        ["VCP Setup", "EMA Stack ✅", "High RS (+8.5% vs Nifty)"],
    }
    result = compute_win_probability(test_stock)
    print(f"\nWin Probability: {result['win_probability']}%")
    print(f"Confidence:      {result['confidence_band']}")
    print(f"Best Strategy:   {result['best_strategy']} (WR: {result['best_strategy_wr']}%)")
    print(f"Hold Period:     {result['recommended_hold_days']} days")
    print(f"Expected Return: {result['expected_return']['base']}% (base)")
    print(f"Breakdown:       {result['probability_breakdown']}")
