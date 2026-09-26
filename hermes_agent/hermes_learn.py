"""
KEPLER — Hermes Self-Learning Engine
=====================================
Runs weekly (every Sunday) to:
  1. Read last week's swing trade outcomes from the backtest cache
  2. Send outcome data + current weights to Gemini for analysis
  3. Gemini recommends updated scoring weights
  4. Saves weights to backend/configs/hermes_weights.json
  5. The swing_probability.py engine loads these on next refresh

Usage:
  python hermes_learn.py              — Run self-learning cycle now
  python hermes_learn.py --dry-run    — Show what would be updated (no write)
  python hermes_learn.py --status     — Show current Hermes weights
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path so we can import from it
_HERMES_DIR  = Path(__file__).parent
_BACKEND_DIR = _HERMES_DIR.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

# ── Paths ──────────────────────────────────────────────────────────────────────
_WEIGHTS_PATH  = _BACKEND_DIR / "configs" / "hermes_weights.json"
_BT_CACHE      = _BACKEND_DIR / ".cache" / "strategy_backtest.json"
_PARAMS_PATH   = _BACKEND_DIR / "configs" / "strategy_params.json"
_PAPER_TRADES  = _BACKEND_DIR / ".cache" / "paper_trades.json"
_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Default weights (baseline for first run) ──────────────────────────────────
DEFAULT_WEIGHTS = {
    "alpha": 0.45,    # ML model contribution
    "beta":  0.35,    # Strategy win rate contribution
    "gamma": 0.12,    # News sentiment contribution
    "delta": 0.08,    # Fundamental quality contribution
    "fund_roe_weight":      0.30,
    "fund_pe_weight":       0.25,
    "fund_rev_weight":      0.25,
    "fund_promoter_weight": 0.20,
}


def _load_current_weights() -> Dict[str, float]:
    try:
        if _WEIGHTS_PATH.exists():
            with open(_WEIGHTS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("weights", DEFAULT_WEIGHTS)
    except Exception:
        pass
    return dict(DEFAULT_WEIGHTS)


def _load_backtest_summary() -> Optional[str]:
    """Format backtest results into a concise summary for Gemini."""
    try:
        if not _BT_CACHE.exists():
            return None
        with open(_BT_CACHE, encoding="utf-8") as f:
            bt = json.load(f)

        strategies = bt.get("strategies", {})
        lines = [f"Backtest Results (computed: {bt.get('computed_at', 'unknown')})"]
        lines.append(f"Universe: {bt.get('universe_size', 0)} stocks | {bt.get('history_years', 3)} years")
        lines.append(f"Win threshold: >{bt.get('gain_threshold', 5)}% gain = WIN\n")

        for name, data in sorted(
            strategies.items(),
            key=lambda x: -(x[1].get("win_rate_primary") or 0)
        ):
            wr  = data.get("win_rate_primary")
            ret = data.get("avg_return_primary")
            pf  = data.get("profit_factor_primary")
            dd  = data.get("max_drawdown_primary")
            sh  = data.get("sharpe_primary")
            tr  = data.get("total_trades", 0)
            act = "✅" if data.get("is_active") else "❌"
            if wr is not None:
                lines.append(
                    f"{act} {name}: WR={wr}% AvgRet={ret}% PF={pf} MaxDD={dd}% Sharpe={sh} Trades={tr}"
                )
            else:
                lines.append(f"❌ {name}: Insufficient data ({tr} trades)")

        return "\n".join(lines)
    except Exception as e:
        return f"Error loading backtest data: {e}"


def _call_gemini(prompt: str, api_key: str) -> Optional[str]:
    """Call Gemini Flash with the learning prompt."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content(prompt, generation_config={"temperature": 0.3})
        return resp.text.strip()
    except Exception as e:
        print(f"  ⚠️  Gemini call failed: {e}")
        return None


def run_self_learning(dry_run: bool = False) -> Dict[str, Any]:
    """
    Main self-learning cycle.
    Returns a dict with: new_weights, changes, reasoning, updated_at.
    """
    print("\n🧠 Hermes Self-Learning Engine")
    print("=" * 50)

    # Load API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Try loading from backend .env
        env_file = _BACKEND_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

    if not api_key:
        print("  ❌ GEMINI_API_KEY not found. Skipping Gemini-based learning.")
        return {"status": "skipped", "reason": "No API key"}

    # Load current state
    current_weights = _load_current_weights()
    backtest_summary = _load_backtest_summary()
    iteration = 1
    if _WEIGHTS_PATH.exists():
        try:
            with open(_WEIGHTS_PATH, encoding="utf-8") as f:
                stored = json.load(f)
            iteration = stored.get("iteration", 0) + 1
        except Exception:
            pass

    print(f"  📊 Backtest data: {'✅ Found' if backtest_summary else '❌ Missing'}")
    print(f"  ⚙️  Current weights: α={current_weights['alpha']} β={current_weights['beta']} "
          f"γ={current_weights['gamma']} δ={current_weights['delta']}")
    print(f"  🔄 Learning iteration: #{iteration}")

    # Build prompt
    prompt = f"""You are Hermes, a self-learning quantitative trading engine for Indian NSE stocks.
Your job: analyze swing trading strategy performance and suggest better probability scoring weights.

CURRENT SCORING FORMULA:
P(success) = α×ML_score + β×strategy_win_rate + γ×news_sentiment + δ×fundamentals

CURRENT WEIGHTS:
- α (ML model):          {current_weights['alpha']}
- β (Strategy win rate): {current_weights['beta']}
- γ (News sentiment):    {current_weights['gamma']}
- δ (Fundamentals):      {current_weights['delta']}
- ROE weight:            {current_weights['fund_roe_weight']}
- PE weight:             {current_weights['fund_pe_weight']}
- Revenue growth weight: {current_weights['fund_rev_weight']}
- Promoter holding wt:   {current_weights['fund_promoter_weight']}

CONSTRAINTS:
- α + β + γ + δ must equal exactly 1.0
- Each weight must be between 0.05 and 0.65
- fund weights must sum to 1.0
- Make SMALL adjustments (±0.05 max per weight per cycle) to avoid overfitting
- If a strategy has >65% win rate, increase β slightly
- If news sentiment shows low correlation, reduce γ slightly
- Iteration #{iteration} — be more conservative if early iterations, bolder if later

STRATEGY BACKTEST RESULTS:
{backtest_summary or 'No backtest data available — use defaults'}

TASK:
Based on these results, suggest optimal weight adjustments.
Provide reasoning for each change.

Respond ONLY in this exact JSON format (no markdown):
{{
  "weights": {{
    "alpha": <float>,
    "beta": <float>,
    "gamma": <float>,
    "delta": <float>,
    "fund_roe_weight": <float>,
    "fund_pe_weight": <float>,
    "fund_rev_weight": <float>,
    "fund_promoter_weight": <float>
  }},
  "changes": {{
    "alpha": "<increased/decreased/unchanged> by X — reason>",
    "beta":  "<increased/decreased/unchanged> by X — reason>",
    "gamma": "<increased/decreased/unchanged> by X — reason>",
    "delta": "<increased/decreased/unchanged> by X — reason>"
  }},
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "top_strategy":  "<best strategy key>",
  "worst_strategy": "<weakest strategy key>",
  "overall_assessment": "<1 sentence about the current model's strengths/weaknesses>"
}}
"""

    print("\n  🤖 Calling Gemini for weight optimization...")
    response = _call_gemini(prompt, api_key)

    if not response:
        print("  ❌ No response from Gemini. Keeping current weights.")
        return {"status": "failed", "reason": "No Gemini response"}

    # Parse response
    try:
        raw = re.sub(r"^```(?:json)?\s*", "", response)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
    except Exception as e:
        print(f"  ❌ Failed to parse Gemini response: {e}")
        print(f"  Raw response: {response[:500]}")
        return {"status": "failed", "reason": f"Parse error: {e}"}

    new_weights = data.get("weights", {})

    # Validate: α + β + γ + δ ≈ 1.0
    core_sum = sum(new_weights.get(k, 0) for k in ["alpha", "beta", "gamma", "delta"])
    if abs(core_sum - 1.0) > 0.02:
        print(f"  ⚠️  Weight sum={core_sum:.3f} ≠ 1.0 — normalising...")
        for k in ["alpha", "beta", "gamma", "delta"]:
            new_weights[k] = round(new_weights.get(k, 0.25) / core_sum, 4)

    # Clamp each weight
    for k in ["alpha", "beta", "gamma", "delta"]:
        new_weights[k] = round(max(0.05, min(0.65, new_weights.get(k, current_weights.get(k, 0.25)))), 4)

    # Fund weights sum to 1.0
    fund_keys = ["fund_roe_weight", "fund_pe_weight", "fund_rev_weight", "fund_promoter_weight"]
    fund_sum  = sum(new_weights.get(k, 0) for k in fund_keys)
    if abs(fund_sum - 1.0) > 0.02 and fund_sum > 0:
        for k in fund_keys:
            new_weights[k] = round(new_weights.get(k, 0.25) / fund_sum, 4)

    print("\n  📈 NEW WEIGHTS:")
    for k in ["alpha", "beta", "gamma", "delta"]:
        old = current_weights.get(k, "?")
        new = new_weights.get(k, "?")
        arrow = "↑" if new > old else ("↓" if new < old else "→")
        print(f"     {k:8s}: {old} → {new} {arrow}")

    print("\n  💡 Key insights:")
    for insight in data.get("key_insights", []):
        print(f"     • {insight}")

    print(f"\n  🏆 Top strategy:   {data.get('top_strategy', 'N/A')}")
    print(f"  ⚠️  Weak strategy:  {data.get('worst_strategy', 'N/A')}")
    print(f"  📝 Assessment: {data.get('overall_assessment', 'N/A')}")

    result = {
        "weights":           new_weights,
        "changes":           data.get("changes", {}),
        "key_insights":      data.get("key_insights", []),
        "top_strategy":      data.get("top_strategy"),
        "worst_strategy":    data.get("worst_strategy"),
        "overall_assessment": data.get("overall_assessment"),
        "iteration":         iteration,
        "updated_at":        datetime.utcnow().isoformat(),
        "previous_weights":  current_weights,
        "backtest_computed_at": None,
    }

    if _BT_CACHE.exists():
        try:
            with open(_BT_CACHE, encoding="utf-8") as f:
                bt_data = json.load(f)
            result["backtest_computed_at"] = bt_data.get("computed_at")
        except Exception:
            pass

    if not dry_run:
        with open(_WEIGHTS_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n  ✅ Weights saved → {_WEIGHTS_PATH}")
    else:
        print("\n  [DRY RUN] — weights NOT saved")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# HERMES L2 — Strategy Parameter Mutation
# ══════════════════════════════════════════════════════════════════════════════

def run_parameter_learning(dry_run: bool = False) -> Dict[str, Any]:
    """
    L2 Self-learning: Hermes asks Gemini to tune strategy_params.json based on
    which strategies are underperforming in the backtest.
    """
    print("\n🔧 Hermes L2 — Strategy Parameter Tuning")
    print("=" * 50)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        env_file = _BACKEND_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        return {"status": "skipped", "reason": "No API key"}

    # Load current params
    try:
        with open(_PARAMS_PATH, "r") as f:
            current_params = json.load(f)
    except Exception:
        current_params = {}

    # Load backtest to find weak strategies
    bt_summary = _load_backtest_summary()

    # Load paper trade outcomes for context
    paper_context = ""
    try:
        with open(_PAPER_TRADES, "r") as f:
            trades = json.load(f)
        recent = [t for t in trades if t.get("status") in ("WIN","LOSS")]
        if recent:
            losses = [t for t in recent if t["status"] == "LOSS"]
            wins   = [t for t in recent if t["status"] == "WIN"]
            paper_context = f"\n\nPaper Trade Outcomes (last {len(recent)} closed):\n"
            paper_context += f"  Wins: {len(wins)}, Losses: {len(losses)}, Win Rate: {len(wins)/len(recent)*100:.1f}%\n"
            if losses:
                loss_strats = [t.get('strategy','?') for t in losses]
                from collections import Counter
                strat_counts = Counter(loss_strats)
                paper_context += f"  Losing strategies: {dict(strat_counts)}\n"
    except Exception:
        pass

    prompt = f"""You are Hermes, a quantitative trading engine optimizer for Indian NSE stocks.

Your job: Analyze underperforming swing strategies and suggest updated parameter values.

CURRENT STRATEGY PARAMETERS:
{json.dumps(current_params, indent=2)}

BACKTEST PERFORMANCE:
{bt_summary or 'Not available'}
{paper_context}

TASK:
For any strategy with Win Rate below 40%, suggest new parameter values that may improve it.
For strategies with Win Rate above 60%, keep parameters stable.
Make CONSERVATIVE adjustments only (e.g., tighten RSI range, adjust volume ratio by 0.5 at most).

Respond ONLY with this JSON (no markdown):
{{
  "params": {{ <same structure as current params, with your adjustments> }},
  "changes": ["change 1 description", "change 2 description"],
  "reasoning": "Overall explanation in 2-3 sentences"
}}"""

    print("  Calling Gemini for parameter optimization...")
    response = _call_gemini(prompt, api_key)
    if not response:
        return {"status": "failed", "reason": "No Gemini response"}

    try:
        raw = re.sub(r"^```(?:json)?\s*", "", response.strip())
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        new_params = data.get("params", current_params)
        changes    = data.get("changes", [])
        reasoning  = data.get("reasoning", "")
    except Exception as e:
        print(f"  Parse error: {e}")
        return {"status": "failed", "reason": f"Parse error: {e}"}

    # Preserve the system thresholds
    new_params["system"] = current_params.get("system", new_params.get("system", {}))

    print(f"  Changes proposed: {len(changes)}")
    for c in changes:
        print(f"    - {c}")
    print(f"  Reasoning: {reasoning}")

    if not dry_run:
        with open(_PARAMS_PATH, "w") as f:
            json.dump(new_params, f, indent=2)
        print(f"  Saved updated params to {_PARAMS_PATH}")

    return {"status": "ok", "changes": changes, "reasoning": reasoning}


# ══════════════════════════════════════════════════════════════════════════════
# HERMES L3 — Paper Trade Post-Mortem
# ══════════════════════════════════════════════════════════════════════════════

def run_paper_trade_learning(dry_run: bool = False) -> Dict[str, Any]:
    """
    L3 Self-learning: Feed recent paper trade outcomes back into Gemini
    and ask what specific ML/fundamental filters would have prevented failures.
    Hermes can then adjust weights to deprioritize losing patterns.
    """
    print("\n📉 Hermes L3 — Paper Trade Post-Mortem")
    print("=" * 50)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        env_file = _BACKEND_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        return {"status": "skipped", "reason": "No API key"}

    try:
        with open(_PAPER_TRADES, "r") as f:
            trades = json.load(f)
    except Exception:
        print("  No paper trades found. Skipping L3.")
        return {"status": "skipped", "reason": "No paper trades"}

    recent = [t for t in trades if t.get("status") in ("WIN","LOSS","EXPIRED")]
    if len(recent) < 5:
        print(f"  Only {len(recent)} closed trades. Need at least 5. Skipping.")
        return {"status": "skipped", "reason": "Insufficient data"}

    wins   = [t for t in recent if t["status"] == "WIN"]
    losses = [t for t in recent if t["status"] in ("LOSS", "EXPIRED")]

    trades_summary = f"Total closed: {len(recent)} | Wins: {len(wins)} ({len(wins)/len(recent)*100:.0f}%) | Losses: {len(losses)}\n\n"
    for t in recent[-20:]:  # last 20
        trades_summary += (
            f"{t['symbol']} | Strategy: {t.get('strategy','?')} | "
            f"Entry: {t.get('entry_price','?')} | Exit: {t.get('exit_price','?')} | "
            f"P&L: {t.get('profit_pct','?')}% | Status: {t['status']}\n"
        )

    current_weights = _load_current_weights()

    prompt = f"""You are Hermes, a self-improving swing trading AI for Indian NSE stocks.

Here are the recent paper trade outcomes from the Kepler system:

{trades_summary}

CURRENT SCORING WEIGHTS:
  alpha (ML model):     {current_weights['alpha']}
  beta (strategy WR):   {current_weights['beta']}
  gamma (news):         {current_weights['gamma']}
  delta (fundamentals): {current_weights['delta']}

TASK:
1. Analyze WHY the losing trades failed (look for patterns)
2. Suggest minor weight adjustments to penalize conditions that led to losses
3. Identify common characteristics in winning trades to amplify

CONSTRAINTS:
- alpha + beta + gamma + delta must sum to 1.0
- Each weight between 0.05 and 0.65
- Max change per weight: ±0.05 per learning cycle

Respond ONLY with this JSON (no markdown):
{{
  "weights": {{
    "alpha": <float>,
    "beta":  <float>,
    "gamma": <float>,
    "delta": <float>,
    "fund_roe_weight":      {current_weights['fund_roe_weight']},
    "fund_pe_weight":       {current_weights['fund_pe_weight']},
    "fund_rev_weight":      {current_weights['fund_rev_weight']},
    "fund_promoter_weight": {current_weights['fund_promoter_weight']}
  }},
  "failure_patterns": ["pattern 1", "pattern 2"],
  "success_patterns":  ["pattern 1", "pattern 2"],
  "recommendation":    "2-sentence recommendation for improving the stock selection filter"
}}"""

    print(f"  Analyzing {len(recent)} trades ({len(wins)} wins, {len(losses)} losses)...")
    response = _call_gemini(prompt, api_key)
    if not response:
        return {"status": "failed", "reason": "No Gemini response"}

    try:
        raw = re.sub(r"^```(?:json)?\s*", "", response.strip())
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        new_weights = data.get("weights", current_weights)
    except Exception as e:
        return {"status": "failed", "reason": f"Parse error: {e}"}

    # Validate + clamp
    core_sum = sum(new_weights.get(k, 0) for k in ["alpha","beta","gamma","delta"])
    if abs(core_sum - 1.0) > 0.02:
        for k in ["alpha","beta","gamma","delta"]:
            new_weights[k] = round(new_weights.get(k, 0.25) / core_sum, 4)
    for k in ["alpha","beta","gamma","delta"]:
        new_weights[k] = round(max(0.05, min(0.65, new_weights.get(k, current_weights.get(k, 0.25)))), 4)

    print("  Failure patterns:")
    for p in data.get("failure_patterns", []):
        print(f"    - {p}")
    print("  Success patterns:")
    for p in data.get("success_patterns", []):
        print(f"    + {p}")
    print(f"  Recommendation: {data.get('recommendation','')}")

    if not dry_run:
        # Load existing weights file and update weights
        stored = {}
        if _WEIGHTS_PATH.exists():
            with open(_WEIGHTS_PATH, "r") as f:
                stored = json.load(f)
        stored["weights"] = new_weights
        stored["l3_updated_at"] = datetime.utcnow().isoformat()
        stored["l3_failure_patterns"] = data.get("failure_patterns", [])
        stored["l3_recommendation"] = data.get("recommendation", "")
        with open(_WEIGHTS_PATH, "w") as f:
            json.dump(stored, f, indent=2)
        print(f"  Saved L3-updated weights.")

    return {"status": "ok", "new_weights": new_weights, "data": data}


def show_status():
    """Print current Hermes weights and learning history."""
    print("\n🧠 Hermes Self-Learning Status")
    print("=" * 50)

    if not _WEIGHTS_PATH.exists():
        print("  No learning data yet. Run 'python hermes_learn.py' to start.")
        return

    try:
        with open(_WEIGHTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        weights = data.get("weights", {})

        print(f"  Iteration:   #{data.get('iteration', 1)}")
        print(f"  Updated:     {data.get('updated_at', 'unknown')}")
        print(f"\n  Current Weights:")
        for k, v in weights.items():
            print(f"    {k:30s}: {v}")

        print(f"\n  Top strategy:  {data.get('top_strategy', 'N/A')}")
        print(f"  Weak strategy: {data.get('worst_strategy', 'N/A')}")
        print(f"\n  Assessment: {data.get('overall_assessment', 'N/A')}")

        insights = data.get("key_insights", [])
        if insights:
            print(f"\n  Key insights from last run:")
            for ins in insights:
                print(f"    • {ins}")
    except Exception as e:
        print(f"  Error reading weights: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermes Self-Learning Engine")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
    parser.add_argument("--status",  action="store_true", help="Show current weights")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        result = run_self_learning(dry_run=args.dry_run)
        if result.get("status") in ("skipped", "failed"):
            print(f"\n  Status: {result['status']} — {result.get('reason', '')}")
        else:
            print(f"\n  ✅ Self-learning cycle #{result.get('iteration')} complete!")
