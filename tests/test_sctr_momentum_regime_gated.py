# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

from __future__ import annotations

import pandas as pd

from strategies.sctr_momentum_regime_gated import _build_regime_gated_weights


def _panel(dates: pd.DatetimeIndex, columns: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=dates)


def test_hold_hysteresis_and_min_holding_days_override():
    dates = pd.bdate_range("2024-01-01", periods=4)
    rank = _panel(dates, {"AAA": [96.0, 40.0, 40.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0, 1.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0, 0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=2, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 1.0  # entry: rank 96 >= 95
    assert weights.loc[dates[1], "AAA"] == 1.0  # rank 40 fails hold(85), but held < 2 days -> min-hold protects
    assert weights.loc[dates[2], "AAA"] == 0.0  # held 2 days now -> min-hold no longer protects -> evicted
    assert weights.loc[dates[3], "AAA"] == 1.0  # rank back to 96 -> fresh re-entry


def test_gate_liquidates_and_allows_immediate_reentry():
    dates = pd.bdate_range("2024-01-01", periods=4)
    rank = _panel(dates, {"AAA": [96.0, 96.0, 96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0, 1.0, 1.0]})
    trend_down = pd.Series([0.0, 1.0, 0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 1.0
    assert weights.loc[dates[1], "AAA"] == 0.0  # gated day: force-liquidated, no new entries evaluated
    assert weights.loc[dates[2], "AAA"] == 1.0  # trend flips back up -> immediate re-entry, no hysteresis buffer
    assert weights.loc[dates[3], "AAA"] == 1.0


def test_max_positions_cap_prioritizes_by_rank():
    dates = pd.bdate_range("2024-01-01", periods=2)
    rank = _panel(dates, {"AAA": [99.0, 99.0], "BBB": [97.0, 97.0], "CCC": [96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [1.0, 1.0], "BBB": [1.0, 1.0], "CCC": [1.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=2,
    )

    assert weights.loc[dates[0], "AAA"] == 0.5
    assert weights.loc[dates[0], "BBB"] == 0.5
    assert weights.loc[dates[0], "CCC"] == 0.0
    # incumbents keep their slots on day 2 even though CCC's rank alone would also qualify
    assert weights.loc[dates[1], "AAA"] == 0.5
    assert weights.loc[dates[1], "BBB"] == 0.5
    assert weights.loc[dates[1], "CCC"] == 0.0


def test_ineligible_name_never_enters_even_with_qualifying_rank():
    dates = pd.bdate_range("2024-01-01", periods=2)
    rank = _panel(dates, {"AAA": [96.0, 96.0]})
    eligibility = _panel(dates, {"AAA": [0.0, 1.0]})
    trend_down = pd.Series([0.0, 0.0], index=dates)

    weights = _build_regime_gated_weights(
        rank, eligibility, trend_down,
        entry_threshold=95.0, hold_threshold=85.0, min_holding_days=90, max_positions=20,
    )

    assert weights.loc[dates[0], "AAA"] == 0.0  # ineligible on day 1 despite qualifying rank
    assert weights.loc[dates[1], "AAA"] == 1.0  # eligible from day 2 -> enters
