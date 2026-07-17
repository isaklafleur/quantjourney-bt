# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
Compare SCTRMomentumRegimeGated's result (run against local MinIO data)
to the original trial's already-materialized result at
analytics/sctr_momentum_regime_gated_pnl.

Builds the SAME PIT S&P 500 instrument universe SCTRMomentumRegimeGated's
own main() uses -- this validates what actually runs in production, not
a loosened stand-in. Expect a real, deliberate gap against the original:
this engine enforces point-in-time index membership (a name is only ever
a candidate on days it was an actual index member) and the original does
not (confirmed directly against real data -- see
strategies/sctr_momentum_regime_gated.py's module docstring). With the
eligibility gate temporarily disabled during development, the lag-
corrected correlation against the original was 0.988, confirming the
port's mechanics are correct; with the gate back on (as below), a lower
number here reflects that intentional methodological choice, not a bug.

Manual/integration use only -- requires QJ_LOCAL_LAKE_* pointed at a
running local MinIO with the datasets described in
docs/superpowers/specs/2026-07-16-minio-local-data-sctr-backtest-design.md.
Not run in CI.

Usage:
    ./strategy.sh validate_sctr_momentum_regime_gated
"""

import asyncio
from datetime import UTC, date, datetime

from backtester.local_lake import pit_sp500_ticker_universe, read_pit
from backtester.local_validation import compare_return_series
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel
from strategies.sctr_momentum_regime_gated import SCTRMomentumRegimeGated


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = pit_sp500_ticker_universe(start_date, end_date, as_of=as_of)

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

    # The two engines book the same T -> T+1 price move under different
    # calendar labels: the original's run_backtest joins the forward
    # return back onto the DECISION day (event_time=T, see its own "weight[T]
    # instead earns ret_1d[T+1]" comment), while this engine's
    # target_weights.shift(1) shifts the WEIGHT forward instead, booking the
    # same move under the REALIZATION day (T+1). Same economics, one
    # calendar day apart -- shift local_returns back by one day before
    # comparing so this doesn't read as "no relationship" between two
    # strategies making nearly identical decisions. Both the same-day and
    # lag-corrected correlation are reported so this convention difference
    # stays visible rather than silently invisible.
    same_day_result = compare_return_series(local_returns, reference_returns)
    lag_corrected_result = compare_return_series(local_returns.shift(-1), reference_returns)

    print("SCTRMomentumRegimeGated vs. original trial (analytics/sctr_momentum_regime_gated_pnl)")
    print(f"  common trading days          : {lag_corrected_result.n_common_days}")
    print(f"  return correlation (same-day): {same_day_result.correlation:.3f}  <- misleading, see comment above")
    print(f"  return correlation (T-1 lag) : {lag_corrected_result.correlation:.3f}  <- the real comparison")
    print(f"  Sharpe   (qj-bt)    : {lag_corrected_result.sharpe_a:.3f}")
    print(f"  Sharpe   (original) : {lag_corrected_result.sharpe_b:.3f}")
    print(f"  CAGR     (qj-bt)    : {lag_corrected_result.cagr_a:.2%}")
    print(f"  CAGR     (original) : {lag_corrected_result.cagr_b:.2%}")
    print(f"  Max DD   (qj-bt)    : {lag_corrected_result.max_drawdown_a:.2%}")
    print(f"  Max DD   (original) : {lag_corrected_result.max_drawdown_b:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
