from __future__ import annotations

from datetime import time
import html
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from ..models import AdapterResponse


OQD_SUMMARY_URL = "https://www.gulfmerc.com/gme-product-services/gme-contracts-contract-summary-oqd"
MARKER_PATTERN = re.compile(
    r"OQD Marker Price\s+([A-Za-z]+ \d{2}, \d{4})\s+is\s+([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE | re.MULTILINE,
)
USER_AGENT = "Mozilla/5.0 (compatible; Oil360Dashboard/1.0; +https://www.gulfmerc.com/)"


class GMEPublicAdapter(BaseAdapter):
    adapter_name = "gme_public"

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        request = Request(
            OQD_SUMMARY_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except URLError as exc:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id="OQD",
                            expected_source="GME public marker page",
                            actual_source="GME public marker page",
                            status="fetch_failed",
                            note=f"Could not reach the public GME Oman marker page: {exc}",
                        )
                    ]
                ),
            )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id="OQD",
                            expected_source="GME public marker page",
                            actual_source="GME public marker page",
                            status="fetch_failed",
                            note=f"GME Oman fetch failed: {exc}",
                        )
                    ]
                ),
            )

        normalized_text = self._normalize_text(html)
        match = MARKER_PATTERN.search(normalized_text)
        if not match:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id="OQD",
                            expected_source="GME public marker page",
                            actual_source="GME public marker page",
                            status="parse_failed",
                            note="Reached the public GME Oman page but could not parse the marker price.",
                        )
                    ]
                ),
            )

        trade_date = pd.to_datetime(match.group(1), format="%B %d, %Y", errors="coerce")
        marker_price = pd.to_numeric(match.group(2), errors="coerce")
        if pd.isna(trade_date) or pd.isna(marker_price):
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id="OQD",
                            expected_source="GME public marker page",
                            actual_source="GME public marker page",
                            status="parse_failed",
                            note="Parsed the GME Oman page but could not convert the marker date or price.",
                        )
                    ]
                ),
            )

        # The public contract summary page identifies the marker by trade date.
        # Use the source market timestamp from the page's published marker convention
        # rather than the local fetch time.
        marker_timestamp = pd.Timestamp.combine(trade_date.date(), time(hour=12, minute=30))

        observation = pd.DataFrame(
            [
                {
                    "series_id": "OQD",
                    "timestamp": marker_timestamp,
                    "value": float(marker_price),
                    "source": "GME public marker page",
                    "status": "daily_public",
                    "frequency": "daily",
                }
            ]
        )
        health = pd.DataFrame(
            [
                health_row(
                    series_id="OQD",
                    expected_source="GME public marker page",
                    actual_source="GME public marker page",
                    status="daily_public",
                    note="Parsed the public GME Oman marker page using the published trade date and marker price.",
                    last_update=marker_timestamp,
                )
            ]
        )
        return AdapterResponse(observation, health)

    @staticmethod
    def _normalize_text(raw_html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text)
