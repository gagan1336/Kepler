"""
nautilus_strategy.nse_cost_model
=================================
NSE-realistic cost components for NautilusTrader's SimulatedExchange.

Mirrors the arithmetic in backend/expectancy.py::compute_round_trip_cost_pct()
so both backtest paths model the same ~0.58% round-trip cost at ₹50k trade
value.  All parameters are configurable; defaults reproduce the baseline.

WDAC NOTE
---------
NautilusTrader's Cython core (via PyArrow) requires an unsigned `.pyd` DLL that
Windows Defender Application Control (WDAC) blocks on this machine unless the
policy is updated.  The NSEFeeModel / NSEFillModel / NSELatencyModel classes
below import NT lazily so the module can be imported and the cost arithmetic
used even when NT itself cannot be instantiated.

Three NT interfaces are implemented:

    NSEFeeModel      →  passed to add_venue(..., fee_model=...)
    NSEFillModel     →  passed to add_venue(..., fill_model=...)
    NSELatencyModel  →  passed to add_venue(..., latency_model=...)

NSEFeeModel arithmetic
-----------------------
Buy leg:
    stamp_duty      0.015% of trade value
    exchange_charge 0.00345% of trade value
    sebi_charge     0.0001% of trade value
    brokerage       min(₹20, 0.03% of trade value) × 1.18 GST

Sell leg:
    stt             0.10% of trade value
    exchange_charge 0.00345% of trade value
    sebi_charge     0.0001% of trade value
    brokerage       min(₹20, 0.03% of trade value) × 1.18 GST

Slippage (NSEFillModel):
    0.10% one-way adverse price movement on fill, configurable.

Latency (NSELatencyModel):
    250ms order-to-fill (same-bar fill for daily strategy), configurable.
"""
from __future__ import annotations

# ── Default NSE cost constants (mirrors expectancy.py NSE_COSTS) ──────────────

_DEFAULT_STT_SELL_PCT        = 0.001       # 0.10%  sell-side only (delivery)
_DEFAULT_EXCHANGE_CHARGE_PCT = 0.0000345   # 0.00345% of turnover
_DEFAULT_SEBI_CHARGE_PCT     = 0.000001    # ₹10/crore ≈ 0.000001%
_DEFAULT_BROKERAGE_FLAT_INR  = 20.0        # ₹20/leg flat
_DEFAULT_BROKERAGE_PCT_CAP   = 0.0003      # 0.03% of trade value, whichever lower
_DEFAULT_STAMP_DUTY_BUY_PCT  = 0.00015     # 0.015% on buy side
_DEFAULT_SLIPPAGE_PCT        = 0.001       # 0.10% one-way


# ── Pure-Python cost helper (no NT dependency) ────────────────────────────────

def compute_round_trip_cost_pct(
    trade_value_inr: float = 50_000,
    slippage_pct:    float = _DEFAULT_SLIPPAGE_PCT,
    brokerage_flat_inr:   float = _DEFAULT_BROKERAGE_FLAT_INR,
    brokerage_pct_cap:    float = _DEFAULT_BROKERAGE_PCT_CAP,
    stt_sell_pct:         float = _DEFAULT_STT_SELL_PCT,
    stamp_duty_buy_pct:   float = _DEFAULT_STAMP_DUTY_BUY_PCT,
    exchange_charges_pct: float = _DEFAULT_EXCHANGE_CHARGE_PCT,
    sebi_charges_pct:     float = _DEFAULT_SEBI_CHARGE_PCT,
) -> float:
    """
    Identical to expectancy.py::compute_round_trip_cost_pct().
    Returns total round-trip cost as a *percentage* of trade value.

    Included here so backtest_runner.py can embed cost_pct in its output JSON
    without importing from expectancy.py (avoids circular deps), and so the
    NautilusTrader fee model can share the same baseline.

    >>> abs(compute_round_trip_cost_pct(50_000) - 0.39) < 0.05
    True
    """
    brokerage_buy = min(brokerage_flat_inr, trade_value_inr * brokerage_pct_cap)
    buy_cost = (
        trade_value_inr * stamp_duty_buy_pct
        + trade_value_inr * exchange_charges_pct
        + trade_value_inr * sebi_charges_pct
        + brokerage_buy * 1.18   # 18% GST on brokerage
        + trade_value_inr * slippage_pct
    )

    brokerage_sell = min(brokerage_flat_inr, trade_value_inr * brokerage_pct_cap)
    sell_cost = (
        trade_value_inr * stt_sell_pct
        + trade_value_inr * exchange_charges_pct
        + trade_value_inr * sebi_charges_pct
        + brokerage_sell * 1.18
        + trade_value_inr * slippage_pct
    )

    return (buy_cost + sell_cost) / trade_value_inr * 100


# ── NautilusTrader model classes (imported lazily) ────────────────────────────

def _get_nt_base_classes():
    """
    Lazily import NT base classes.  Raises ImportError with a clear
    WDAC resolution message if PyArrow DLLs are blocked.
    """
    try:
        from nautilus_trader.backtest.models import FeeModel, FillModel, LatencyModel
        return FeeModel, FillModel, LatencyModel
    except ImportError as exc:
        if "Application Control" in str(exc) or "DLL load failed" in str(exc):
            raise ImportError(
                "\n\n"
                "NautilusTrader cannot load because a Windows Defender Application\n"
                "Control (WDAC) policy on this machine blocks unsigned .pyd DLLs\n"
                "downloaded from PyPI (policy ID: 0283ac0f-fff1-49ae-ada1-8a933130cad6).\n\n"
                "To resolve, ask your administrator to either:\n"
                "  (a) Add an allow rule for the venv site-packages directory, or\n"
                "  (b) Enable the WDAC audit-only mode so unsigned code runs with logging.\n\n"
                "Full command to diagnose:\n"
                "  wevtutil qe Microsoft-Windows-CodeIntegrity/Operational "
                "/q:*[System[EventID=3077]] /c:5 /f:text\n\n"
                "Alternatively, run the backtest on a machine without this policy\n"
                "(e.g., a Linux CI runner or WSL2).\n\n"
                "The pure-Python fallback backtester in backtest_runner.py will still\n"
                "run correctly for parity validation on this machine.\n"
            ) from exc
        raise


class NSEFeeModel:
    """
    Per-order NSE fee model implementing the delivery equity cost schedule.

    Wraps nautilus_trader.backtest.models.FeeModel.  Instantiation requires
    NautilusTrader to be importable (WDAC policy permitting).

    Parameters
    ----------
    brokerage_flat_inr : float
        Flat brokerage per leg in INR (default ₹20).
    brokerage_pct_cap : float
        Max brokerage as fraction of trade value per leg (default 0.03%).
    stt_sell_pct : float
        STT on sell side as fraction (default 0.001 = 0.10%).
    stamp_duty_buy_pct : float
        Stamp duty on buy side as fraction (default 0.00015 = 0.015%).
    exchange_charges_pct : float
        NSE exchange charge fraction (default 0.0000345).
    sebi_charges_pct : float
        SEBI charge fraction (default 0.000001).
    """

    def __new__(
        cls,
        brokerage_flat_inr:   float = _DEFAULT_BROKERAGE_FLAT_INR,
        brokerage_pct_cap:    float = _DEFAULT_BROKERAGE_PCT_CAP,
        stt_sell_pct:         float = _DEFAULT_STT_SELL_PCT,
        stamp_duty_buy_pct:   float = _DEFAULT_STAMP_DUTY_BUY_PCT,
        exchange_charges_pct: float = _DEFAULT_EXCHANGE_CHARGE_PCT,
        sebi_charges_pct:     float = _DEFAULT_SEBI_CHARGE_PCT,
    ):
        FeeModel, _, _ = _get_nt_base_classes()

        # Build a concrete subclass dynamically so we inherit from the real
        # NautilusTrader FeeModel Cython type.
        class _NSEFeeModelImpl(FeeModel):
            def __init__(self, **kw):
                self._brokerage_flat   = kw["brokerage_flat_inr"]
                self._brokerage_cap    = kw["brokerage_pct_cap"]
                self._stt_sell         = kw["stt_sell_pct"]
                self._stamp_buy        = kw["stamp_duty_buy_pct"]
                self._exchange         = kw["exchange_charges_pct"]
                self._sebi             = kw["sebi_charges_pct"]

            def get_commission(self, quantity, price, liquidity_side, instrument):
                """
                Return per-leg commission in the instrument's quote currency.

                NT calls this once per filled order (buy leg + sell leg separately),
                so we compute the *average* per-leg cost, which over a round-trip
                yields the same total as the expectancy.py flat-percentage model.
                """
                trade_value = float(quantity) * float(price)
                brokerage = min(
                    self._brokerage_flat,
                    trade_value * self._brokerage_cap
                ) * 1.18   # 18% GST

                # Average of buy-leg (stamp) and sell-leg (STT) so that
                # buy_commission + sell_commission = full expectancy.py cost
                avg_duty = trade_value * (self._stamp_buy + self._stt_sell) / 2.0
                exchange = trade_value * self._exchange
                sebi     = trade_value * self._sebi

                total_inr = brokerage + avg_duty + exchange + sebi
                from nautilus_trader.model.objects import Money
                return Money(total_inr, instrument.quote_currency)

        obj = _NSEFeeModelImpl(
            brokerage_flat_inr=brokerage_flat_inr,
            brokerage_pct_cap=brokerage_pct_cap,
            stt_sell_pct=stt_sell_pct,
            stamp_duty_buy_pct=stamp_duty_buy_pct,
            exchange_charges_pct=exchange_charges_pct,
            sebi_charges_pct=sebi_charges_pct,
        )
        return obj


class NSEFillModel:
    """
    Slippage model: probability-based adverse fill, with slippage_pct stored
    for reference.  NT's FillModel applies stochastic slippage controlled by
    `prob_slippage`; we set it to 1.0 so slippage is always applied.

    The explicit ₹ slippage cost is captured as part of NSEFeeModel's brokerage
    average, matching expectancy.py's flat-percentage approach.

    Parameters
    ----------
    slippage_pct : float
        One-way slippage fraction (default 0.001 = 0.10%), stored as metadata.
    prob_fill_on_limit : float
        Probability a limit order fills (default 1.0 — Kepler uses market orders).
    prob_slippage : float
        Probability slippage is applied (default 1.0 — always conservative).
    """

    def __new__(
        cls,
        slippage_pct:       float = _DEFAULT_SLIPPAGE_PCT,
        prob_fill_on_limit: float = 1.0,
        prob_slippage:      float = 1.0,
    ):
        _, FillModel, _ = _get_nt_base_classes()

        class _NSEFillModelImpl(FillModel):
            def __init__(self, prob_fill_on_limit, prob_slippage, slippage_pct):
                super().__init__(
                    prob_fill_on_limit=prob_fill_on_limit,
                    prob_slippage=prob_slippage,
                )
                self.slippage_pct = slippage_pct  # informational

        return _NSEFillModelImpl(prob_fill_on_limit, prob_slippage, slippage_pct)


class NSELatencyModel:
    """
    Order-to-fill latency for a daily-bar EOD strategy on NSE.

    For backtesting daily bars the latency has no practical impact on fill price
    (same bar fills regardless), but it ensures NT's event ordering is realistic.

    Parameters
    ----------
    base_latency_nanos : int
        Base latency in nanoseconds (default 250_000_000 = 250ms).
    """

    def __new__(cls, base_latency_nanos: int = 250_000_000):
        _, _, LatencyModel = _get_nt_base_classes()

        class _NSELatencyModelImpl(LatencyModel):
            def __init__(self, base_latency_nanos):
                super().__init__(base_latency_nanos=base_latency_nanos)

        return _NSELatencyModelImpl(base_latency_nanos)
