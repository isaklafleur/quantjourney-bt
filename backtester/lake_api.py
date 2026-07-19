# QuantJourney Backtester
# Copyright (c) 2026 QuantJourney.
# Licensed under the Apache License 2.0.

"""
HTTP client for IMQuantFund's external, read-only lake API
(/api/v1/lake/*), used by backtester.local_data.build_local_minio_bt_payload
for Backtester(source="minio").

Two of local_data's four MinIO-era reads move onto this HTTP transport --
equity_bars_1d_yahoo_adj (via read_bars) and sctr_features (via
read_features) -- the highest-volume reads, and the only two the API
exposes. market_ref_bars_1d_yahoo_adj and index_membership stay on
backtester.local_lake's direct MinIO reads; see
docs/superpowers/specs/2026-07-18-lake-api-client-design.md for why.

Configured via QJ_LAKE_API_URL (default http://localhost:8000) and
QJ_LAKE_API_KEY (required, sent as the X-API-Key header).
"""

from __future__ import annotations

import io
import os
from datetime import date

import httpx
import pandas as pd

DEFAULT_LAKE_API_URL = "http://localhost:8000"

__all__ = ["read_bars"]


def _headers() -> dict[str, str]:
    return {"X-API-Key": os.environ["QJ_LAKE_API_KEY"]}


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise ValueError(
            f"Lake API rejected the request (401 Unauthorized) at {response.request.url}\n"
            "  Check the QJ_LAKE_API_KEY environment variable."
        )
    if response.status_code >= 400:
        raise ValueError(
            f"Lake API request to {response.request.url} failed "
            f"({response.status_code}): {response.text}"
        )


def _get(path: str, params: dict[str, str], client: httpx.Client | None) -> httpx.Response:
    headers = _headers()
    if client is not None:
        response = client.get(path, params=params, headers=headers)
    else:
        base_url = os.environ.get("QJ_LAKE_API_URL", DEFAULT_LAKE_API_URL)
        with httpx.Client(base_url=base_url, timeout=60.0) as owned_client:
            response = owned_client.get(path, params=params, headers=headers)
    _raise_for_status(response)
    return response


def read_bars(
    dataset: str,
    *,
    tickers: list[str],
    start: date,
    end: date,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Read Yahoo-adjusted daily bars for `tickers` in [start, end] via
    GET /api/v1/lake/bars/{dataset}. PIT-resolved server-side as of `end`
    (the endpoint has no separate as_of param).

    `client` lets tests inject an httpx.Client built on an
    httpx.MockTransport instead of hitting a real server; production
    callers omit it and get a fresh client built from QJ_LAKE_API_URL.
    """
    response = _get(
        f"/api/v1/lake/bars/{dataset}",
        {"tickers": ",".join(tickers), "start": start.isoformat(), "end": end.isoformat()},
        client,
    )
    return pd.read_parquet(io.BytesIO(response.content))
