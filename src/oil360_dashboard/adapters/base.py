from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from ..models import AdapterResponse


OBSERVATION_COLUMNS = ["series_id", "timestamp", "value", "source", "status", "frequency"]
HEALTH_COLUMNS = [
    "series_id",
    "expected_source",
    "actual_source",
    "status",
    "last_update",
    "note",
]


def empty_observations() -> pd.DataFrame:
    return pd.DataFrame(columns=OBSERVATION_COLUMNS)


def empty_health() -> pd.DataFrame:
    return pd.DataFrame(columns=HEALTH_COLUMNS)


def health_row(
    series_id: str,
    expected_source: str,
    actual_source: str,
    status: str,
    note: str,
    last_update: datetime | pd.Timestamp | None = None,
) -> dict[str, object]:
    ts = pd.Timestamp(last_update or datetime.utcnow()).tz_localize(None)
    return {
        "series_id": series_id,
        "expected_source": expected_source,
        "actual_source": actual_source,
        "status": status,
        "last_update": ts,
        "note": note,
    }


class BaseAdapter(ABC):
    adapter_name = "base"

    @abstractmethod
    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        raise NotImplementedError
