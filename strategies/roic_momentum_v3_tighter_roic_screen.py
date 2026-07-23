# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
ROIC + Momentum Blend v3: Tighter ROIC Screen
===============================================

Mode: weights.

Research spec: docs/research/strategies/roic-momentum-v3-tighter-roic-screen.md.
Direct follow-up to ROIC + momentum blend v2: sequential screen (Improve,
REVIEW 2026-07-23, strategies/roic_momentum_sequential_screen.py, branch
worktree-roic-momentum-v2, parked not merged). v2 replaced v1's blended
z-score with a two-step sequential screen (top-half-by-ROIC filter, then
rank survivors by ret_60d) and improved the mandatory IR gate an order of
magnitude (-0.2205 -> -0.0287) even though regime protection weakened.
v2's REVIEW read the IR improvement as better stock selection *within*
the ROIC-qualified pool, not strengthened defensiveness.

v3 tests whether that read continues to hold: same two-step sequential
screen as v2, but the first-stage ROIC filter tightens from v2's median
(top-half) split to a **top-third** split. Everything else -- data,
universe, rebalance cadence, momentum ranking on survivors, position
sizing -- is unchanged (one variable at a time, per this loop's standing
Improve-follow-up discipline).

Eligibility-count thresholds (flagged as an open design question in the
spec, decided here): v2 used MIN_ELIGIBLE_FOR_SCREEN=16 so a median split
leaves >= 8 survivors. A top-third split of the same 16-name floor would
leave only ~5 survivors, below v2's own MIN_SURVIVORS_FOR_QUARTILE=8. Per
the spec's first suggested option, MIN_ELIGIBLE_FOR_SCREEN is raised to
24 here so a top-third split still leaves >= 8 survivors;
MIN_SURVIVORS_FOR_QUARTILE stays at v2's 8 (so the top quartile of
survivors still has >= 2 names) -- keeps the second-stage logic identical
to v2 rather than compounding two threshold changes at once.

Universe: PIT S&P 500 membership (pit_sp500_ticker_universe), full
709-ticker universe -- same as v2, no delisted-name workaround needed
(shared-engine ledger bug fixed on `main`, commit a44a703).

PIT handling identical to v1/v2 (restated per the spec, not re-probed --
both datasets already live-probed and confirmed across two prior IMPLEMENT
stages):
- `roic_features`: `knowledge_time` genuinely spread 2009-2026
  (fiscal-filing-anchored) -- `roic` is forward-filled via a
  `knowledge_time`-anchored `merge_asof`.
- `technical_features.ret_60d`: `knowledge_time` bulk-clustered near "now"
  (recent-backfill artifact) -- pivoted directly on `event_time`.

Missing-value handling: unchanged from v2 -- no sentinel score needed. A
sequential screen naturally drops incomplete names at each step; the
selection decision itself is a 1.0/0.0 panel, finite by construction.

Short borrow/financing is not applicable (long/cash only, no shorting).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from backtester import Backtester, lake_api
from backtester.bt_payload import frame_payload
from backtester.local_lake import pit_sp500_ticker_universe
from backtester.portfolio.rebalance import RebalancePolicy
from backtester.portfolio.weight_cost import FixedBpsWeightCostModel

ROIC_SCREEN_QUANTILE = 2.0 / 3.0  # top third by ROIC, tightened from v2's median split
TOP_QUARTILE = 0.75  # top quartile of ROIC-screen survivors, ranked by ret_60d
MIN_ELIGIBLE_FOR_SCREEN = 24  # before the top-third ROIC split, so survivors >= 8
MIN_SURVIVORS_FOR_QUARTILE = 8  # before the momentum quartile split, so top quartile has >= 2
MAX_POSITION_SIZE = 0.10


def _decode_parameters_frame(payload: dict) -> pd.DataFrame:
    """Inverse of `backtester.bt_payload.frame_payload` for the
    "parameters" panel -- local to this file rather than reaching into
    `backtester.core`'s private `_payload_to_multiindex_df` (same helper
    as v1/v2)."""
    tuples = [(c["instrument"], c["field"]) for c in payload["columns"]]
    columns = pd.MultiIndex.from_tuples(tuples, names=["instrument", "field"])
    index = pd.DatetimeIndex(pd.to_datetime(payload["index"]), name="date")
    return pd.DataFrame(payload["data"], index=index, columns=columns)


def _roic_panel(
    roic: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex
) -> pd.DataFrame:
    """Per-ticker as-of forward-fill of `roic`, anchored on
    `knowledge_time` (not `event_time`) -- identical to v1/v2's helper of
    the same name; a trading day only sees a filing once it was actually
    known."""
    panel = pd.DataFrame(np.nan, index=dates, columns=tickers)
    if roic.empty:
        return panel
    rows = roic[roic["ticker"].isin(tickers)].dropna(subset=["roic"]).copy()
    if rows.empty:
        return panel
    # The lake's parquet reads come back as datetime64[us, UTC]; the bars-derived
    # `dates` index is datetime64[ns, UTC] -- merge_asof requires identical dtypes.
    rows["knowledge_time"] = rows["knowledge_time"].astype(dates.dtype)
    for ticker, group in rows.groupby("ticker"):
        group = group.sort_values("knowledge_time").drop_duplicates(
            subset="knowledge_time", keep="last"
        )
        merged = pd.merge_asof(
            pd.DataFrame({"date": dates}),
            group[["knowledge_time", "roic"]].rename(columns={"knowledge_time": "date"}),
            on="date",
            direction="backward",
        )
        panel[ticker] = merged["roic"].to_numpy()
    return panel


def _momentum_panel(
    technical: pd.DataFrame, tickers: list[str], dates: pd.DatetimeIndex
) -> pd.DataFrame:
    """Pivot `ret_60d` directly on `event_time` -- identical to v1/v2's
    helper of the same name (`low_volatility_anomaly.py`'s `_vol_panel`):
    this dataset's `knowledge_time` is bulk-clustered near "now", so
    `event_time` is the correct PIT anchor."""
    if technical.empty:
        return pd.DataFrame(np.nan, index=dates, columns=tickers)
    technical = technical[technical["ticker"].isin(tickers)]
    wide = technical.pivot_table(index="event_time", columns="ticker", values="ret_60d")
    return wide.reindex(index=dates, columns=tickers)


class RoicMomentumV3TighterRoicScreen(Backtester):
    """ROIC top-third screen -> 60-day-momentum rank within survivors (weight mode)."""

    async def _fetch_market_data(self) -> None:
        if self._source != "minio":
            await super()._fetch_market_data()
            return

        from backtester.local_data import build_local_minio_bt_payload

        payload = build_local_minio_bt_payload(
            instruments=self.instruments,
            start=self.backtest_period.start,
            end=self.backtest_period.end,
            initial_nav=self.initial_capital,
        )
        parameters = _decode_parameters_frame(payload["parameters"])
        tickers = list(dict.fromkeys(instrument for instrument, _ in parameters.columns))
        dates = parameters.index

        as_of = datetime.now(UTC).date()
        roic = lake_api.read_features("roic_features", tickers=tickers, as_of=as_of)
        technical = lake_api.read_features("technical_features", tickers=tickers, as_of=as_of)
        roic_panel = _roic_panel(roic, tickers, dates)
        momentum_panel = _momentum_panel(technical, tickers, dates)
        for ticker in tickers:
            parameters[(ticker, "roic")] = roic_panel[ticker]
            parameters[(ticker, "ret_60d")] = momentum_panel[ticker]
        parameters = parameters.sort_index(axis=1)

        payload["parameters"] = frame_payload(parameters)
        self._api_response = payload
        self.session_id = payload["session_id"]
        self.dataset_id = payload["dataset_id"]
        self._validate_data_completeness_response()

    def _compute_signals(self) -> pd.DataFrame:
        """Sequential screen: ROIC top-third filter, then momentum
        top-quartile of survivors. Returns the 1.0/0.0 selection decision
        itself (always finite by construction -- 0.0 covers "screened
        out" and "missing data" alike, no sentinel needed); `_compute_weights`
        only sizes the already-decided positions."""
        roic = self.instruments_data.get_feature("parameters", level="roic")
        momentum = self.instruments_data.get_feature("parameters", level="ret_60d")
        eligibility = self.instruments_data.get_feature("parameters", level="eligibility")

        selected = pd.DataFrame(0.0, index=roic.index, columns=roic.columns)
        for day in roic.index:
            eligible_mask = eligibility.loc[day] >= 1.0
            day_roic = roic.loc[day].where(eligible_mask).dropna()
            if len(day_roic) < MIN_ELIGIBLE_FOR_SCREEN:
                continue
            roic_cutoff = day_roic.quantile(ROIC_SCREEN_QUANTILE)
            survivors = day_roic[day_roic >= roic_cutoff].index

            day_momentum = momentum.loc[day, survivors].dropna()
            if len(day_momentum) < MIN_SURVIVORS_FOR_QUARTILE:
                continue
            momentum_cutoff = day_momentum.quantile(TOP_QUARTILE)
            top = day_momentum[day_momentum >= momentum_cutoff]
            if top.empty:
                continue
            selected.loc[day, top.index] = 1.0
        return selected

    def _compute_weights(self) -> pd.DataFrame:
        selected = self.signals == 1.0
        weights = pd.DataFrame(0.0, index=selected.index, columns=selected.columns)
        for day in selected.index:
            names = selected.columns[selected.loc[day]]
            if len(names) == 0:
                continue
            weight = min(1.0 / len(names), self.max_position_size)
            weights.loc[day, names] = weight
        return weights


async def main() -> None:
    as_of = datetime.now(UTC)
    start_date, end_date = date(2016, 1, 1), as_of.date()
    instruments = pit_sp500_ticker_universe(start_date, end_date, as_of=as_of)

    strategy = RoicMomentumV3TighterRoicScreen(
        strategy_name="RoicMomentumV3TighterRoicScreen",
        strategy_type="Long / Cash",
        initial_capital=100_000,
        instruments=instruments,
        backtest_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        benchmark_symbol="SPY",
        benchmark_name="SPDR S&P 500 ETF Trust",
        source="minio",
        execution_mode="weights",
        max_position_size=MAX_POSITION_SIZE,
        rebalance_policy=RebalancePolicy(frequency="BME"),
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
