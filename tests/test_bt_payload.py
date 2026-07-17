# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

from __future__ import annotations

import pandas as pd

from backtester.bt_payload import frame_payload, series_payload


def test_frame_payload_round_trips_columns_index_and_data():
    dates = pd.bdate_range("2024-01-01", periods=3, tz="UTC")
    df = pd.DataFrame(
        {("AAA", "close"): [1.0, 2.0, None], ("AAA", "volume"): [10.0, 20.0, 30.0]},
        index=dates,
    )
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["instrument", "field"])

    payload = frame_payload(df)

    assert payload["columns"] == [
        {"instrument": "AAA", "field": "close"},
        {"instrument": "AAA", "field": "volume"},
    ]
    assert payload["index"] == [d.isoformat() for d in dates]
    assert payload["data"][0] == [1.0, 10.0]
    assert payload["data"][2] == [None, 30.0]


def test_series_payload_round_trips_index_and_data():
    dates = pd.bdate_range("2024-01-01", periods=2, tz="UTC")
    series = pd.Series([100.0, None], index=dates)

    payload = series_payload(series)

    assert payload["index"] == [d.isoformat() for d in dates]
    assert payload["data"] == [100.0, None]
