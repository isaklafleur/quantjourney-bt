# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester.lake_api."""

from __future__ import annotations

import io
from datetime import date

import httpx
import pandas as pd
import pytest

from backtester import lake_api


def _parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf)
    return buf.getvalue()


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")


def test_read_bars_parses_parquet_and_sends_expected_request(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")
    expected = pd.DataFrame({"ticker": ["AAPL"], "close": [123.45]})
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers["x-api-key"]
        return httpx.Response(200, content=_parquet_bytes(expected))

    result = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=["AAPL"],
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        client=_mock_client(handler),
    )

    pd.testing.assert_frame_equal(result, expected)
    assert "/api/v1/lake/bars/equity_bars_1d_yahoo_adj" in captured["url"]
    assert "tickers=AAPL" in captured["url"]
    assert "start=2024-01-01" in captured["url"]
    assert "end=2024-01-31" in captured["url"]
    assert captured["api_key"] == "test-key"


def test_read_bars_401_raises_value_error_mentioning_api_key(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "wrong-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(ValueError, match="QJ_LAKE_API_KEY"):
        lake_api.read_bars(
            "equity_bars_1d_yahoo_adj",
            tickers=["AAPL"],
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            client=_mock_client(handler),
        )


def test_read_bars_404_includes_response_body(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            text="unknown bars dataset 'foo' -- valid datasets: ['equity_bars_1d_yahoo_adj']",
        )

    with pytest.raises(ValueError, match="unknown bars dataset"):
        lake_api.read_bars(
            "foo",
            tickers=["AAPL"],
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            client=_mock_client(handler),
        )


def test_read_bars_empty_result_returns_empty_dataframe(monkeypatch):
    monkeypatch.setenv("QJ_LAKE_API_KEY", "test-key")
    empty = pd.DataFrame(
        {"ticker": pd.Series(dtype="object"), "close": pd.Series(dtype="float64")}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_parquet_bytes(empty))

    result = lake_api.read_bars(
        "equity_bars_1d_yahoo_adj",
        tickers=["AAPL"],
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        client=_mock_client(handler),
    )
    assert result.empty
    assert list(result.columns) == ["ticker", "close"]
