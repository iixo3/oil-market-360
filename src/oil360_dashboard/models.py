from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SeriesDefinition:
    series_id: str
    display_name: str
    layer: str
    source_family: str
    expected_status: str
    frequency: str
    description: str
    why_it_matters: str
    fallback_proxy: str
    tooltip: str
    unit: str
    base_value: float
    volatility: float


@dataclass
class AdapterResponse:
    observations: pd.DataFrame
    source_health: pd.DataFrame


@dataclass
class DashboardState:
    observations: pd.DataFrame
    wide_frame: pd.DataFrame
    snapshot: pd.DataFrame
    source_health: pd.DataFrame
    correlation_history: pd.DataFrame
    correlation_matrix: pd.DataFrame
    divergences: pd.DataFrame
    lagged_relationships: pd.DataFrame
    composites: pd.DataFrame
    composite_components: pd.DataFrame
    interpretation_cards: list[dict[str, str]]
    narrative: str
    relationship_graph: dict[str, Any]
