"""
Shared JSON-table serialization for /bt/prepare-compatible payloads.

Used by every Backtester data source that builds its own `_api_response`
locally instead of fetching one from the API -- today `sample_data.py`
(deterministic demo data) and `local_data.py` (local MinIO lake reads).
Kept in one place so both stay byte-for-byte consistent with what
`backtester.core._payload_to_multiindex_df` / `_payload_to_series` expect.

Copyright (c) 2026 QuantJourney.
Licensed under the Apache License 2.0.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    columns = [
        {"instrument": str(instrument), "field": str(field)}
        for instrument, field in df.columns.to_list()
    ]
    safe = df.astype(object).where(pd.notna(df), None)
    return {
        "columns": columns,
        "index": [idx.isoformat() for idx in df.index],
        "data": safe.values.tolist(),
    }


def series_payload(series: pd.Series) -> dict[str, Any]:
    safe = series.astype(object).where(pd.notna(series), None)
    return {
        "index": [idx.isoformat() for idx in series.index],
        "data": safe.tolist(),
    }
