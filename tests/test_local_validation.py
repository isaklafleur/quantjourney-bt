# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtester.local_validation import compare_return_series


def test_compare_return_series_identical_series_gives_correlation_one():
    dates = pd.bdate_range("2024-01-01", periods=100)
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0005, 0.01, size=100), index=dates)

    result = compare_return_series(returns, returns.copy())

    assert result.correlation == pytest.approx(1.0)
    assert result.sharpe_a == pytest.approx(result.sharpe_b)
    assert result.n_common_days == 100


def test_compare_return_series_aligns_on_common_dates_only():
    dates_a = pd.bdate_range("2024-01-01", periods=10)
    dates_b = pd.bdate_range("2024-01-05", periods=10)
    a = pd.Series(0.001, index=dates_a)
    b = pd.Series(0.001, index=dates_b)

    result = compare_return_series(a, b)

    assert result.n_common_days == len(set(dates_a) & set(dates_b))


def test_compare_return_series_raises_on_no_overlap():
    a = pd.Series(0.001, index=pd.bdate_range("2024-01-01", periods=5))
    b = pd.Series(0.001, index=pd.bdate_range("2025-01-01", periods=5))

    with pytest.raises(ValueError, match="no overlapping dates"):
        compare_return_series(a, b)


def test_compare_return_series_max_drawdown_is_negative_for_a_losing_series():
    dates = pd.bdate_range("2024-01-01", periods=5)
    losing = pd.Series([-0.01, -0.01, -0.01, -0.01, -0.01], index=dates)
    flat = pd.Series([0.0, 0.0, 0.0, 0.0, 0.0], index=dates)

    result = compare_return_series(losing, flat)

    assert result.max_drawdown_a < 0.0
    assert result.max_drawdown_b == 0.0
