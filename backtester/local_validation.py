"""
Compare a locally-produced daily net-return series against a reference
return series (e.g. an already-materialized backtest result read from
the lake) -- used to sanity-check the SCTR momentum regime-gated port
against the original trial's result.

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

__all__ = ["ReturnSeriesComparison", "compare_return_series"]


@dataclass(frozen=True)
class ReturnSeriesComparison:
    correlation: float
    n_common_days: int
    sharpe_a: float
    sharpe_b: float
    cagr_a: float
    cagr_b: float
    max_drawdown_a: float
    max_drawdown_b: float


def _sharpe(returns: pd.Series) -> float:
    if returns.empty or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _cagr(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns).cumprod()
    years = len(returns) / TRADING_DAYS_PER_YEAR
    if years <= 0 or nav.iloc[-1] <= 0:
        return 0.0
    return float(nav.iloc[-1] ** (1.0 / years) - 1.0)


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return float(drawdown.min())


def compare_return_series(a: pd.Series, b: pd.Series) -> ReturnSeriesComparison:
    """`a`/`b`: daily net-return series indexed by date. Aligns on their
    common index before computing correlation and per-series risk
    metrics -- days present in only one series are dropped, not
    zero-filled (a missing observation is not a zero return)."""
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if joined.empty:
        raise ValueError("compare_return_series: no overlapping dates between the two series")

    correlation = float(joined["a"].corr(joined["b"])) if len(joined) > 1 else 0.0
    return ReturnSeriesComparison(
        correlation=correlation,
        n_common_days=len(joined),
        sharpe_a=_sharpe(joined["a"]),
        sharpe_b=_sharpe(joined["b"]),
        cagr_a=_cagr(joined["a"]),
        cagr_b=_cagr(joined["b"]),
        max_drawdown_a=_max_drawdown(joined["a"]),
        max_drawdown_b=_max_drawdown(joined["b"]),
    )
