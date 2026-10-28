from __future__ import annotations

import pandas as pd

from .base import BaseAdapter
from .csv_manual import load_directory_csv
from ..catalog import PREMIUM_SERIES_IDS
from ..config import AppConfig
from ..models import AdapterResponse


class PremiumPhysicalAdapter(BaseAdapter):
    adapter_name = "premium_physical"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        return load_directory_csv(
            directory=self.config.premium_dir,
            allowed_series=PREMIUM_SERIES_IDS,
            expected_source="Platts / Argus / OPIS CSV",
            default_status="manual_csv",
        )
