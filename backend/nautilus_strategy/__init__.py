"""
nautilus_strategy
=================
NautilusTrader wrapper for the Kepler ML backtest pipeline.

Sub-modules
-----------
nse_cost_model   — NSE-realistic FeeModel / FillModel / LatencyModel
data_loader      — yfinance OHLCV → NautilusTrader Bar objects
kepler_strategy  — Strategy class delegating to existing kepler_model inference
backtest_runner  — BacktestEngine wiring + CLI runner
parity_report    — Side-by-side comparison vs expectancy.py output

Scope
-----
Backtest-parity validation ONLY.  No live/paper execution wired here.
To point at a live feed, replace BacktestEngine with LiveNode and keep
KeplerStrategy unchanged — that is the explicit design goal.
"""
