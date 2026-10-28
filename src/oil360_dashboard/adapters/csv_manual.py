from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from ..models import AdapterResponse

TIMESTAMP_COLUMNS = ["timestamp", "datetime", "date", "time"]
VALUE_COLUMNS = ["value", "close", "price", "last", "settle", "index_value"]
SERIES_COLUMNS = ["series_id", "series", "symbol", "ticker"]
FREQUENCY_COLUMNS = ["frequency", "granularity"]
SERIES_ALIASES = {
    "CL": "CL",
    "CL1": "CL",
    "CL2": "CL",
    "WTI": "CL",
    "BRENT": "BRENT",
    "BZ": "BRENT",
    "BZ1": "BRENT",
    "BZ2": "BRENT",
    "COIL": "BRENT",
    "COIL1": "BRENT",
    "COIL2": "BRENT",
    "OQD": "OQD",
    "OMOIL": "OQD",
    "OMOIL1": "OQD",
    "OMOIL2": "OQD",
    "OMAN": "OQD",
}


def _canonicalise_series_id(value: str) -> str:
    raw = str(value).strip().upper()
    key = "".join(character for character in raw if character.isalnum())
    return SERIES_ALIASES.get(key, raw)


def _infer_frequency(frame: pd.DataFrame) -> str:
    if len(frame) < 2:
        return "manual"
    diffs = frame["timestamp"].sort_values().diff().dropna()
    if diffs.empty:
        return "manual"
    median_diff = diffs.median()
    if median_diff <= pd.Timedelta(hours=1):
        return "intraday"
    if median_diff <= pd.Timedelta(days=2):
        return "daily"
    return "weekly"


def normalise_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        return empty_observations()

    lowered = {column.lower().strip(): column for column in frame.columns}
    timestamp_column = next((lowered[name] for name in TIMESTAMP_COLUMNS if name in lowered), None)
    value_column = next((lowered[name] for name in VALUE_COLUMNS if name in lowered), None)
    series_column = next((lowered[name] for name in SERIES_COLUMNS if name in lowered), None)
    frequency_column = next((lowered[name] for name in FREQUENCY_COLUMNS if name in lowered), None)

    if timestamp_column is None or value_column is None:
        return empty_observations()

    normalized = pd.DataFrame()
    normalized["timestamp"] = pd.to_datetime(frame[timestamp_column], errors="coerce", utc=True).dt.tz_localize(None)
    normalized["value"] = pd.to_numeric(frame[value_column], errors="coerce")
    if series_column:
        normalized["series_id"] = frame[series_column].astype(str).map(_canonicalise_series_id)
    else:
        normalized["series_id"] = _canonicalise_series_id(path.stem)
    if frequency_column:
        normalized["frequency"] = frame[frequency_column].astype(str).str.strip().str.lower()
    else:
        normalized["frequency"] = ""

    normalized["source"] = path.name
    normalized["status"] = "manual_csv"
    normalized = normalized.dropna(subset=["timestamp", "value"])
    if normalized.empty:
        return empty_observations()
    normalized["frequency"] = normalized["frequency"].replace("", _infer_frequency(normalized))
    return normalized[["series_id", "timestamp", "value", "source", "status", "frequency"]]


def load_directory_csv(
    directory: Path,
    allowed_series: set[str] | None,
    expected_source: str,
    default_status: str,
) -> AdapterResponse:
    if not directory.exists():
        return AdapterResponse(empty_observations(), empty_health())

    observations: list[pd.DataFrame] = []
    health: list[dict[str, object]] = []

    for path in sorted(directory.glob("*.csv")):
        frame = normalise_csv(path)
        if frame.empty:
            continue
        if allowed_series is not None:
            frame = frame[frame["series_id"].isin(allowed_series)]
        if frame.empty:
            continue

        frame["status"] = default_status
        observations.append(frame)

        for series_id in frame["series_id"].unique():
            latest_ts = frame.loc[frame["series_id"] == series_id, "timestamp"].max()
            health.append(
                health_row(
                    series_id=series_id,
                    expected_source=expected_source,
                    actual_source=path.name,
                    status=default_status,
                    note=f"Loaded from {path.name}.",
                    last_update=latest_ts,
                )
            )

    if not observations:
        return AdapterResponse(empty_observations(), empty_health())

    return AdapterResponse(pd.concat(observations, ignore_index=True), pd.DataFrame(health))


class CSVManualAdapter(BaseAdapter):
    adapter_name = "csv_manual"

    def __init__(self, directory: Path, excluded_series: set[str] | None = None) -> None:
        self.directory = directory
        self.excluded_series = excluded_series or set()

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        response = load_directory_csv(
            directory=self.directory,
            allowed_series=None,
            expected_source="Manual CSV import",
            default_status="manual_csv",
        )
        if response.observations.empty:
            return response

        frame = response.observations[~response.observations["series_id"].isin(self.excluded_series)].copy()
        health = response.source_health[~response.source_health["series_id"].isin(self.excluded_series)].copy()
        if frame.empty:
            return AdapterResponse(empty_observations(), empty_health())
        return AdapterResponse(frame, health)
