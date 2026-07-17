# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""Tests for backtester source='minio' integration via local_data.build_local_minio_bt_payload."""

from __future__ import annotations

import asyncio

from backtester import Backtester, local_data
from backtester.sample_data import build_sample_bt_payload


def test_backtester_source_minio_uses_local_payload_and_skips_network(monkeypatch):
    payload = build_sample_bt_payload(instruments=["AAA", "BBB"], start="2024-01-01", end="2024-03-01")
    payload["summary"]["source"] = "minio"

    calls: dict[str, object] = {}

    def fake_build(*, instruments, start, end, initial_nav):
        calls["instruments"] = instruments
        calls["start"] = start
        calls["end"] = end
        calls["initial_nav"] = initial_nav
        return payload

    monkeypatch.setattr(local_data, "build_local_minio_bt_payload", fake_build)

    bt = Backtester(
        instruments=["AAA", "BBB"],
        backtest_period={"start": "2024-01-01", "end": "2024-03-01"},
        source="minio",
        strategy_name="minio_source_smoke_test",
        show_text_reports=False,
        skip_analysis=True,
    )

    async def _get_sdk_client_should_not_be_called():
        raise AssertionError("source='minio' must not touch the SDK client / network")

    bt._get_sdk_client = _get_sdk_client_should_not_be_called  # type: ignore[method-assign]

    asyncio.run(bt._fetch_market_data())

    assert calls["instruments"] == ["AAA", "BBB"]
    assert calls["initial_nav"] == bt.initial_capital
    assert bt.session_id == "sample-session"
    assert bt.dataset_id == "sample-dataset"
    assert bt._api_response["summary"]["source"] == "minio"
