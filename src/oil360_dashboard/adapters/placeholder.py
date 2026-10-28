from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from ..catalog import SERIES_CATALOG
from ..models import AdapterResponse


TIMEFRAME_RULES = {
    "Intraday": ("15min", 14),
    "Daily": ("1D", 365),
    "Weekly": ("1W-FRI", 156),
}


class PlaceholderAdapter(BaseAdapter):
    adapter_name = "placeholder"

    def fetch(
        self,
        timeframe: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        series_ids: list[str] | None = None,
    ) -> AdapterResponse:
        frequency, periods = TIMEFRAME_RULES[timeframe]
        end_ts = pd.Timestamp(end).floor("15min").tz_localize(None)
        index = pd.date_range(end=end_ts, periods=periods, freq=frequency)
        factors = self._build_factor_frame(index)
        selected_series = series_ids or list(SERIES_CATALOG)

        observations: list[pd.DataFrame] = []
        health: list[dict[str, object]] = []

        for series_id in selected_series:
            definition = SERIES_CATALOG[series_id]
            values = self._generate_series_values(series_id, definition.base_value, definition.volatility, factors)
            frame = pd.DataFrame(
                {
                    "series_id": series_id,
                    "timestamp": index,
                    "value": values,
                    "source": "Synthetic placeholder scaffold",
                    "status": "placeholder",
                    "frequency": "placeholder",
                }
            )
            observations.append(frame)
            health.append(
                health_row(
                    series_id=series_id,
                    expected_source=definition.source_family,
                    actual_source="Synthetic placeholder scaffold",
                    status="placeholder",
                    note=f"No configured source available. Using placeholder; fallback is {definition.fallback_proxy}",
                    last_update=index.max(),
                )
            )

        if not observations:
            return AdapterResponse(empty_observations(), empty_health())
        return AdapterResponse(pd.concat(observations, ignore_index=True), pd.DataFrame(health))

    def _build_factor_frame(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        seconds = index.view("int64") / 1_000_000_000
        day = 86_400.0
        factors = pd.DataFrame(index=index)
        factors["market"] = np.sin(seconds / (day * 14)) + 0.7 * np.cos(seconds / (day * 43))
        factors["physical"] = 0.6 * factors["market"] + np.sin(seconds / (day * 9))
        factors["east"] = 0.3 * factors["physical"] + np.cos(seconds / (day * 6))
        factors["inland"] = -0.2 * factors["market"] + np.sin(seconds / (day * 17))
        factors["grade"] = 0.5 * factors["physical"] + np.cos(seconds / (day * 11))
        factors["product"] = 0.4 * factors["market"] + np.sin(seconds / (day * 5))
        factors["logistics"] = 0.4 * factors["physical"] + np.cos(seconds / (day * 7))
        factors["inventory"] = -0.4 * factors["physical"] + np.sin(seconds / (day * 21))
        return factors

    def _generate_series_values(
        self,
        series_id: str,
        base_value: float,
        volatility: float,
        factors: pd.DataFrame,
    ) -> pd.Series:
        exposures = {
            "CL": {"market": 1.7, "physical": 0.5, "inland": -0.3},
            "BRENT": {"market": 1.8, "physical": 0.8, "east": 0.3},
            "AUB": {"market": 1.3, "physical": 1.2, "logistics": 0.4},
            "DATED_BRENT": {"market": 1.2, "physical": 1.4, "logistics": 0.5},
            "DBI": {"market": 1.1, "physical": 0.9, "east": 1.0},
            "OQD": {"market": 1.0, "physical": 0.8, "east": 1.2},
            "ADM": {"market": 1.0, "physical": 0.8, "east": 1.1},
            "HTT": {"inland": 1.4, "physical": 0.4, "market": 0.2},
            "WTT": {"inland": 1.2, "physical": 0.5, "market": 0.2},
            "YV": {"grade": 1.6, "physical": 0.5},
            "WHT": {"grade": 1.5, "physical": 0.4},
            "RB": {"product": 1.8, "market": 0.4, "logistics": 0.3},
            "HO": {"product": 2.0, "market": 0.4, "logistics": 0.4},
            "G": {"product": 1.7, "market": 0.5, "logistics": 0.5},
            "BDTI": {"logistics": 2.1, "physical": 0.3},
            "BCTI": {"logistics": 1.9, "product": 0.5},
            "AIS_HORMUZ_TRANSITS": {"logistics": -1.6, "east": -0.5},
            "WAR_RISK_PREMIUM": {"logistics": 1.9, "east": 0.3},
            "CUSHING": {"inland": 1.6, "inventory": 1.2, "physical": -0.4},
            "FUJAIRAH": {"inventory": 1.0, "east": -0.8, "logistics": -0.3},
            "SINGAPORE": {"inventory": 1.0, "east": -0.7, "product": -0.4},
            "ARA": {"inventory": 1.1, "product": -0.8, "logistics": -0.2},
        }.get(series_id, {"market": 1.0})

        signal = np.zeros(len(factors))
        for factor_name, weight in exposures.items():
            signal += weight * factors[factor_name].to_numpy()

        hash_seed = int(hashlib.sha256(series_id.encode("utf-8")).hexdigest()[:8], 16)
        phase = (hash_seed % 360) / 57.2958
        seasonal = np.sin(np.arange(len(factors)) / 13 + phase) * volatility * 0.35
        value = base_value + signal * volatility + seasonal

        if series_id in {"AIS_HORMUZ_TRANSITS", "CUSHING", "FUJAIRAH", "SINGAPORE", "ARA", "BDTI", "BCTI"}:
            value = np.maximum(value, 1.0)
        if series_id == "WAR_RISK_PREMIUM":
            value = np.maximum(value, 0.1)
        return pd.Series(value, index=factors.index).round(3)
