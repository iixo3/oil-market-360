from __future__ import annotations

import pandas as pd

from .base import BaseAdapter
from .csv_manual import load_directory_csv
from ..catalog import FREIGHT_SERIES_IDS
from ..config import AppConfig
from ..models import AdapterResponse


class FreightFlowAdapter(BaseAdapter):
    adapter_name = "freight_flow"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        return load_directory_csv(
            directory=self.config.freight_dir,
            allowed_series=FREIGHT_SERIES_IDS,
            expected_source="Baltic / AIS / logistics CSV",
            default_status="manual_csv",
        )
