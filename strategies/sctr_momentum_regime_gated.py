# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
SCTR Momentum, Regime-Gated (Binary Trend Pause)
=================================================

Mode: weights.

Port of a strategy spec from a separate private research project, run
here against local MinIO data (source="minio") instead of that
project's own engine -- see
docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md
for the full design and known fidelity gaps versus the original.

Rules: entry at SCTR rank >= 95, hold while rank >= 85 (hysteresis),
minimum 90-trading-day hold overridable only by the trend gate, max 20
equal-weight positions with incumbent-priority slot selection. On any day
PIT-resolved SPY closes below its 200-day SMA, every held name is
force-liquidated and no new entries are taken; re-entry is immediate and
automatic the first day the trend flips back up, with no added
hysteresis on the gate itself.

Universe: every ticker with a research/sctr_features row (sctr_features_
ticker_universe), NOT a PIT S&P 500 membership reconstruction. Verified
directly against the original strategy's own asset code and real data
(comparing actual daily holdings between the two engines on
2016-03-11, the first trade day in both): the original never applies a
separate index-membership filter at runtime -- it trades whatever
sctr_features covers, which is not identical to processed/index_membership
(it includes names that had already left, or had not yet (re-)joined,
the index as of a given trade date). An earlier version of this port
gated entries on PIT S&P 500 membership, which excluded real trades the
original took and drove return correlation to ~0 against the original's
materialized result -- do not reintroduce that gate without re-checking
against real data first.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pandas as pd

from backtester import Backtester
from backtester.local_lake import sctr_features_ticker_universe
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel

ENTRY_THRESHOLD = 95.0
HOLD_THRESHOLD = 85.0
MIN_HOLDING_DAYS = 90
MAX_HOLDING_DAYS = 120
MAX_POSITIONS = 20


def _build_regime_gated_weights(
    rank: pd.DataFrame,
    eligibility: pd.DataFrame,
    trend_down: pd.Series,
    *,
    entry_threshold: float = ENTRY_THRESHOLD,
    hold_threshold: float = HOLD_THRESHOLD,
    min_holding_days: int = MIN_HOLDING_DAYS,
    max_holding_days: int = MAX_HOLDING_DAYS,
    max_positions: int = MAX_POSITIONS,
) -> pd.DataFrame:
    """Day-by-day incumbent-priority portfolio construction.

    `rank`/`eligibility`: dates x tickers panels. `trend_down`: a dates
    Series, 1.0 on days the market-trend gate is active. Returns a dates
    x tickers equal-weight panel -- NOT pre-shifted; the engine applies
    its own shift(1) before this is ever compared against returns.
    """
    dates = rank.index
    tickers = list(rank.columns)
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)

    held: dict[str, int] = {}  # ticker -> day_idx it entered
    for day_idx, day in enumerate(dates):
        if trend_down.loc[day] >= 1.0:
            held = {}
            continue

        day_rank = rank.loc[day]
        day_elig = eligibility.loc[day].fillna(0.0)
        entry_ok = (day_rank >= entry_threshold) & (day_elig >= 1.0)
        hold_ok = (day_rank >= hold_threshold) & (day_elig >= 1.0)

        held = {
            t: entry_idx
            for t, entry_idx in held.items()
            if (bool(hold_ok.get(t, False)) or (day_idx - entry_idx) < min_holding_days)
            and (day_idx - entry_idx) < max_holding_days
        }

        slots_remaining = max_positions - len(held)
        if slots_remaining > 0:
            candidates = day_rank[entry_ok]
            candidates = candidates[~candidates.index.isin(held.keys())].dropna()
            candidates = candidates.sort_values(ascending=False)
            for ticker in candidates.index[:slots_remaining]:
                held[ticker] = day_idx

        if held:
            w = 1.0 / len(held)
            for t in held:
                weights.loc[day, t] = w

    return weights


class SCTRMomentumRegimeGated(Backtester):
    """SCTR momentum with a binary SPY-trend regime gate (weight mode)."""

    entry_threshold = ENTRY_THRESHOLD
    hold_threshold = HOLD_THRESHOLD
    min_holding_days = MIN_HOLDING_DAYS
    max_holding_days = MAX_HOLDING_DAYS
    max_positions = MAX_POSITIONS

    def _compute_signals(self) -> pd.DataFrame:
        # NaN where sctr_features has no row for a (ticker, date) pair (e.g.
        # before a name's feature history starts) -- filled with 0.0 (safely
        # below both entry_threshold and hold_threshold, so it never
        # spuriously qualifies) because the engine's own signal validation
        # requires every value to be finite.
        return self.instruments_data.get_feature("parameters", level="sctr_rank").fillna(0.0)

    def _compute_weights(self) -> pd.DataFrame:
        rank = self.signals
        # No PIT S&P 500 eligibility mask here, deliberately -- see the
        # module docstring. The original strategy never gates entries on
        # index membership, so every name with an sctr_features row is
        # always eligible; _build_regime_gated_weights still accepts an
        # eligibility panel (used by its own tests), it's just all-1.0 here.
        eligibility = pd.DataFrame(1.0, index=rank.index, columns=rank.columns)
        trend_down_panel = self.instruments_data.get_feature("parameters", level="spy_trend_down")
        trend_down = trend_down_panel.iloc[:, 0]  # broadcast market-wide flag -> single Series
        return _build_regime_gated_weights(
            rank,
            eligibility,
            trend_down,
            entry_threshold=self.entry_threshold,
            hold_threshold=self.hold_threshold,
            min_holding_days=self.min_holding_days,
            max_holding_days=self.max_holding_days,
            max_positions=self.max_positions,
        )


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = sctr_features_ticker_universe(start_date, end_date, as_of=as_of)

    strategy = SCTRMomentumRegimeGated(
        strategy_name="SCTRMomentumRegimeGated",
        strategy_type="Long / Cash",
        initial_capital=100_000,
        instruments=instruments,
        backtest_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        benchmark_symbol="SPY",
        benchmark_name="SPDR S&P 500 ETF Trust",
        source="minio",
        execution_mode="weights",
        weight_cost_model=FixedBpsWeightCostModel(total_bps=10.0),
        indicators_config=[],
        show_text_reports=True,
        save_text_reports=True,
        save_portfolio_plots=True,
        show_portfolio_plots=False,
    )
    await strategy.run_strategy()
    strategy.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
