from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .adapters.csv_manual import CSVManualAdapter
from .adapters.cme_bulletin import CMEDailyBulletinAdapter
from .adapters.freight_flow import FreightFlowAdapter
from .adapters.gme_public import GMEPublicAdapter
from .adapters.ibkr import ExchangeBrokerAdapter
from .adapters.placeholder import PlaceholderAdapter
from .adapters.premium_physical import PremiumPhysicalAdapter
from .adapters.public_data import PublicMacroInventoryAdapter
from .analytics.composites import compute_composites
from .analytics.metrics import (
    build_snapshot,
    build_source_health,
    compute_correlation_history,
    compute_correlation_matrix,
    compute_lagged_relationships,
    detect_divergences,
    prepare_wide_frame,
)
from .analytics.narrative import build_daily_narrative, build_interpretation_cards
from .analytics.transmission import build_relationship_graph
from .catalog import EXCHANGE_SERIES_IDS, SERIES_CATALOG, WATCHLIST_ORDER
from .config import AppConfig
from .models import DashboardState
from .storage.history_store import HistoryStore


TIME_WINDOWS = {
    "Intraday": pd.Timedelta(days=21),
    "Daily": pd.Timedelta(days=540),
    "Weekly": pd.Timedelta(weeks=260),
}


@dataclass
class DashboardPipeline:
    config: AppConfig

    def __post_init__(self) -> None:
        self.store = HistoryStore(self.config.db_path)
        self.exchange_adapter = ExchangeBrokerAdapter(self.config)
        self.cme_bulletin_adapter = CMEDailyBulletinAdapter()
        self.gme_adapter = GMEPublicAdapter()
        self.public_adapter = PublicMacroInventoryAdapter(self.config)
        self.premium_adapter = PremiumPhysicalAdapter(self.config)
        self.freight_adapter = FreightFlowAdapter(self.config)
        self.manual_adapter = CSVManualAdapter(self.config.manual_dir, excluded_series=EXCHANGE_SERIES_IDS)
        self.placeholder_adapter = PlaceholderAdapter()

    def build_dashboard_state(self, timeframe: str) -> DashboardState:
        end = pd.Timestamp.utcnow().tz_localize(None)
        start = end - TIME_WINDOWS[timeframe]
        health_frames: list[pd.DataFrame] = []

        for adapter in [
            self.exchange_adapter,
            self.cme_bulletin_adapter,
            self.gme_adapter,
            self.public_adapter,
            self.premium_adapter,
            self.freight_adapter,
            self.manual_adapter,
        ]:
            response = adapter.fetch(timeframe=timeframe, start=start, end=end)
            self.store.upsert_observations(response.observations)
            if not response.source_health.empty:
                health_frames.append(response.source_health.assign(adapter=adapter.adapter_name))

        observed = self.store.load_observations(WATCHLIST_ORDER, start=start)
        present_series = set(observed["series_id"].unique()) if not observed.empty else set()
        missing_series = [series_id for series_id in WATCHLIST_ORDER if series_id not in present_series]
        if missing_series:
            placeholder = self.placeholder_adapter.fetch(
                timeframe=timeframe,
                start=start,
                end=end,
                series_ids=missing_series,
            )
            self.store.upsert_observations(placeholder.observations)

        observations = self.store.load_observations(WATCHLIST_ORDER, start=start)
        adapter_health = pd.concat(health_frames, ignore_index=True) if health_frames else pd.DataFrame()
        wide_frame = prepare_wide_frame(observations, timeframe)
        source_health = build_source_health(observations, SERIES_CATALOG, adapter_health)
        snapshot = build_snapshot(wide_frame, source_health, timeframe)
        correlation_history = compute_correlation_history(wide_frame, timeframe)
        correlation_matrix = compute_correlation_matrix(wide_frame)
        divergences = detect_divergences(correlation_history)
        lagged_relationships = compute_lagged_relationships(wide_frame)
        composites, composite_components = compute_composites(wide_frame)
        interpretation_cards = build_interpretation_cards(composites)
        narrative = build_daily_narrative(composites, snapshot, divergences)
        relationship_graph = build_relationship_graph()

        return DashboardState(
            observations=observations,
            wide_frame=wide_frame,
            snapshot=snapshot,
            source_health=source_health,
            correlation_history=correlation_history,
            correlation_matrix=correlation_matrix,
            divergences=divergences,
            lagged_relationships=lagged_relationships,
            composites=composites,
            composite_components=composite_components,
            interpretation_cards=interpretation_cards,
            narrative=narrative,
            relationship_graph=relationship_graph,
        )
