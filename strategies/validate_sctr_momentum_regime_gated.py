# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
Compare SCTRMomentumRegimeGated's result (run against local MinIO data)
to the original trial's already-materialized result at
analytics/sctr_momentum_regime_gated_pnl.

Manual/integration use only -- requires QJ_LOCAL_LAKE_* pointed at a
running local MinIO with the datasets described in
docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md.
Not run in CI.

Usage:
    ./strategy.sh validate_sctr_momentum_regime_gated
"""

import asyncio
from datetime import UTC, date, datetime

from backtester.local_lake import read_pit, sctr_features_ticker_universe
from backtester.local_validation import compare_return_series
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel
from strategies.sctr_momentum_regime_gated import SCTRMomentumRegimeGated


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = sctr_features_ticker_universe(start_date, end_date, as_of=as_of)

    strategy = SCTRMomentumRegimeGated(
        strategy_name="SCTRMomentumRegimeGated_validation",
        initial_capital=100_000,
        instruments=instruments,
        backtest_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        benchmark_symbol="SPY",
        source="minio",
        execution_mode="weights",
        weight_cost_model=FixedBpsWeightCostModel(total_bps=10.0),
        show_text_reports=False,
        skip_analysis=True,
    )
    await strategy.run_strategy()

    local_returns = strategy.portfolio_data.net_asset_value.pct_change().dropna()
    local_returns.index = local_returns.index.tz_localize(None)

    reference = read_pit(
        "analytics",
        "sctr_momentum_regime_gated_pnl",
        as_of=as_of,
        pit_keys=("event_time",),
    )
    reference_returns = reference.set_index("event_time")["net_return"]
    reference_returns.index = reference_returns.index.tz_localize(None)

    result = compare_return_series(local_returns, reference_returns)
    print("SCTRMomentumRegimeGated vs. original trial (analytics/sctr_momentum_regime_gated_pnl)")
    print(f"  common trading days : {result.n_common_days}")
    print(f"  return correlation  : {result.correlation:.3f}")
    print(f"  Sharpe   (qj-bt)    : {result.sharpe_a:.3f}")
    print(f"  Sharpe   (original) : {result.sharpe_b:.3f}")
    print(f"  CAGR     (qj-bt)    : {result.cagr_a:.2%}")
    print(f"  CAGR     (original) : {result.cagr_b:.2%}")
    print(f"  Max DD   (qj-bt)    : {result.max_drawdown_a:.2%}")
    print(f"  Max DD   (original) : {result.max_drawdown_b:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
