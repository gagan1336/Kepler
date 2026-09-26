"""
KEPLER — Paper Trade Tracker
==============================
Logs deep research swing picks as "paper trades" to evaluate outcome accuracy.
Hermes L3 will read these outcomes to learn from its mistakes.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import yfinance as yf
import pandas as pd
from loguru import logger

_BACKEND_DIR = Path(__file__).parent
_CACHE_DIR   = _BACKEND_DIR / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_TRADE_LOG_FILE = _CACHE_DIR / "paper_trades.json"

def _load_trades() -> List[Dict]:
    if _TRADE_LOG_FILE.exists():
        try:
            with open(_TRADE_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading paper trades: {e}")
    return []

def _save_trades(trades: List[Dict]):
    with open(_TRADE_LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def record_trade(symbol: str, entry_price: float, target_price: float, stop_loss: float, strategy: str, thesis: str):
    """Record a new swing pick as an open paper trade."""
    trades = _load_trades()
    
    # Avoid duplicate active trades for the same stock
    for t in trades:
        if t["symbol"] == symbol and t["status"] == "OPEN":
            return
            
    new_trade = {
        "id": f"{symbol}_{datetime.now().strftime('%Y%m%d')}",
        "symbol": symbol,
        "entry_date": datetime.now().isoformat(),
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "strategy": strategy,
        "thesis": thesis,
        "status": "OPEN",
        "exit_date": None,
        "exit_price": None,
        "profit_pct": None
    }
    trades.append(new_trade)
    _save_trades(trades)
    logger.info(f"Recorded new paper trade for {symbol} at {entry_price}")

def evaluate_open_trades():
    """Check all OPEN trades against current market prices to see if Target/SL was hit."""
    trades = _load_trades()
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    
    if not open_trades:
        logger.info("No open paper trades to evaluate.")
        return
        
    symbols = list(set([t["symbol"] for t in open_trades]))
    logger.info(f"Evaluating {len(symbols)} open paper trades...")
    
    try:
        data = yf.download(symbols, period="5d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            # multi-symbol
            highs = data["High"].iloc[-1]
            lows  = data["Low"].iloc[-1]
            closes = data["Close"].iloc[-1]
        else:
            # single symbol
            highs = pd.Series({symbols[0]: data["High"].iloc[-1]})
            lows  = pd.Series({symbols[0]: data["Low"].iloc[-1]})
            closes = pd.Series({symbols[0]: data["Close"].iloc[-1]})
            
        updated_count = 0
        for t in trades:
            if t["status"] == "OPEN":
                sym = t["symbol"]
                if sym in highs:
                    high = float(highs[sym])
                    low  = float(lows[sym])
                    close = float(closes[sym])
                    
                    if high >= t["target_price"]:
                        t["status"] = "WIN"
                        t["exit_date"] = datetime.now().isoformat()
                        t["exit_price"] = t["target_price"]
                        t["profit_pct"] = round((t["target_price"] - t["entry_price"]) / t["entry_price"] * 100, 2)
                        updated_count += 1
                        logger.success(f"Trade WIN: {sym} hit target {t['target_price']}")
                        
                    elif low <= t["stop_loss"]:
                        t["status"] = "LOSS"
                        t["exit_date"] = datetime.now().isoformat()
                        t["exit_price"] = t["stop_loss"]
                        t["profit_pct"] = round((t["stop_loss"] - t["entry_price"]) / t["entry_price"] * 100, 2)
                        updated_count += 1
                        logger.warning(f"Trade LOSS: {sym} hit stop loss {t['stop_loss']}")
                        
                    else:
                        # Check if trade has been open too long (e.g., 30 days)
                        entry_dt = datetime.fromisoformat(t["entry_date"])
                        if (datetime.now() - entry_dt).days > 30:
                            t["status"] = "EXPIRED"
                            t["exit_date"] = datetime.now().isoformat()
                            t["exit_price"] = close
                            t["profit_pct"] = round((close - t["entry_price"]) / t["entry_price"] * 100, 2)
                            updated_count += 1
                            logger.info(f"Trade EXPIRED: {sym} closed at time limit.")
                            
        if updated_count > 0:
            _save_trades(trades)
            
    except Exception as e:
        logger.error(f"Error evaluating paper trades: {e}")

if __name__ == "__main__":
    evaluate_open_trades()
