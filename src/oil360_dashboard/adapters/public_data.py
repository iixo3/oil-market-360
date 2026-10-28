from __future__ import annotations

import html
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from .csv_manual import load_directory_csv
from ..catalog import PUBLIC_SERIES_IDS
from ..config import AppConfig
from ..models import AdapterResponse


EIA_CUSHING_URL = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=W_EPC0_SAX_YCUOK_MBBL"
FOIZ_FUJAIRAH_URL = "https://foiz.gov.ae/statistics/"
USER_AGENT = "Mozilla/5.0 (compatible; Oil360Dashboard/1.0)"

CUSHING_RELEASE_PATTERN = re.compile(r"Release Date:\s*([0-9/]+)", re.IGNORECASE)
CUSHING_MONTH_LINE_PATTERN = re.compile(r"^\s*(\d{4})-([A-Za-z]{3})\s+(.*)$")
CUSHING_WEEK_VALUE_PATTERN = re.compile(r"(\d{2}/\d{2})\s+([0-9,]+)")
CUSHING_MONTH_BLOCK_PATTERN = re.compile(r"(\d{4})-([A-Za-z]{3})\s+((?:(?:\d{2}/\d{2})\s+[0-9,]+\s*)+)", re.IGNORECASE)
FUJAIRAH_DATE_PATTERN = re.compile(r"INVENTORIES As of date\s+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
FUJAIRAH_BLOCK_PATTERN = re.compile(r"INVENTORIES As of date\s+(\d{2}/\d{2}/\d{4})(.*?)(?:BUNKER SALES As of date|$)", re.IGNORECASE | re.DOTALL)
FUJAIRAH_COMPONENT_PATTERN = re.compile(
    r"INVENTORIES As of date\s+(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<light>[0-9,]+)\s+LIGHT DISTILLATES\s+THOUSAND BARRELS\s+"
    r"(?P<middle>[0-9,]+)\s+MEDIUM DISTILLATES\s+THOUSAND BARRELS\s+"
    r"(?P<heavy>[0-9,]+)\s+HEAVY DISTILLATES\s*&\s*RESIDUE",
    re.IGNORECASE,
)


def _fetch_url(url: str, timeout_seconds: float = 8.0) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="ignore")


def _normalize_html_text(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def _html_to_lines(raw_html: str) -> list[str]:
    text = re.sub(r"<[^>]+>", "\n", raw_html)
    text = html.unescape(text)
    return [" ".join(line.split()) for line in text.splitlines() if line and line.strip()]


def _fetch_cushing_eia() -> AdapterResponse:
    try:
        raw_html = _fetch_url(EIA_CUSHING_URL, timeout_seconds=10.0)
    except URLError as exc:
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="CUSHING",
                        expected_source="EIA weekly stocks page",
                        actual_source="EIA weekly stocks page",
                        status="fetch_failed",
                        note=f"Could not reach the official EIA Cushing weekly history page: {exc}",
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
                        series_id="CUSHING",
                        expected_source="EIA weekly stocks page",
                        actual_source="EIA weekly stocks page",
                        status="fetch_failed",
                        note=f"EIA Cushing weekly history fetch failed: {exc}",
                    )
                ]
            ),
        )

    lines = _html_to_lines(raw_html)
    normalized_text = _normalize_html_text(raw_html)
    release_match = (
        CUSHING_RELEASE_PATTERN.search(raw_html)
        or CUSHING_RELEASE_PATTERN.search("\n".join(lines))
        or CUSHING_RELEASE_PATTERN.search(normalized_text)
    )
    month_blocks = CUSHING_MONTH_BLOCK_PATTERN.findall(normalized_text)
    if month_blocks:
        year, month, month_block = month_blocks[-1]
        week_matches = CUSHING_WEEK_VALUE_PATTERN.findall(month_block)
    else:
        month_lines = [line for line in lines if CUSHING_MONTH_LINE_PATTERN.match(line)]
        latest_line = month_lines[-1] if month_lines else ""
        month_match = CUSHING_MONTH_LINE_PATTERN.match(latest_line)
        year = month_match.group(1) if month_match else ""
        month = month_match.group(2) if month_match else ""
        week_matches = CUSHING_WEEK_VALUE_PATTERN.findall(latest_line) if latest_line else []
    if not year or not month or not week_matches or not release_match:
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="CUSHING",
                        expected_source="EIA weekly stocks page",
                        actual_source="EIA weekly stocks page",
                        status="parse_failed",
                        note="Reached the official EIA Cushing weekly history page but could not parse the latest weekly value or release date.",
                    )
                ]
            ),
        )

    latest_week, latest_value = week_matches[-1]
    latest_end_date = pd.to_datetime(f"{year}-{month}-{latest_week}", format="%Y-%b-%m/%d", errors="coerce")
    value_kbbl = pd.to_numeric(latest_value.replace(",", ""), errors="coerce")
    release_date = pd.to_datetime(release_match.group(1), format="%m/%d/%Y", errors="coerce")
    if pd.isna(value_kbbl) or pd.isna(release_date) or pd.isna(latest_end_date):
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="CUSHING",
                        expected_source="EIA weekly stocks page",
                        actual_source="EIA weekly stocks page",
                        status="parse_failed",
                        note="Parsed the EIA Cushing weekly history page but could not convert the latest week, latest value, or release date.",
                    )
                ]
            ),
        )

    release_timestamp = pd.Timestamp(release_date).normalize()
    observation = pd.DataFrame(
        [
            {
                "series_id": "CUSHING",
                "timestamp": release_timestamp,
                "value": float(value_kbbl) / 1000.0,
                "source": "EIA weekly stocks page",
                "status": "date_only_public",
                "frequency": "weekly",
            }
        ]
    )
    health = pd.DataFrame(
        [
            health_row(
                series_id="CUSHING",
                expected_source="EIA weekly stocks page",
                actual_source="EIA weekly stocks page",
                status="date_only_public",
                note=(
                    "Parsed the official EIA weekly Cushing history page. "
                    f"Latest reported stock week ends on {latest_end_date.strftime('%Y-%m-%d')}, and the EIA page lists "
                    f"a release date of {release_date.strftime('%Y-%m-%d')}. The source page exposes dates but not an exact publication time, "
                    "so the dashboard shows the release date only."
                ),
                last_update=release_timestamp,
            )
        ]
    )
    return AdapterResponse(observation, health)


def _fetch_fujairah_foiz() -> AdapterResponse:
    try:
        raw_html = _fetch_url(FOIZ_FUJAIRAH_URL, timeout_seconds=15.0)
    except URLError as exc:
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="FUJAIRAH",
                        expected_source="FOIZ statistics page",
                        actual_source="FOIZ statistics page",
                        status="fetch_failed",
                        note=f"Could not reach the official FOIZ statistics page: {exc}",
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
                        series_id="FUJAIRAH",
                        expected_source="FOIZ statistics page",
                        actual_source="FOIZ statistics page",
                        status="fetch_failed",
                        note=f"FOIZ Fujairah fetch failed: {exc}",
                    )
                ]
            ),
        )

    normalized_text = _normalize_html_text(raw_html)
    component_match = FUJAIRAH_COMPONENT_PATTERN.search(normalized_text)
    if component_match:
        as_of_date = pd.to_datetime(component_match.group("date"), format="%d/%m/%Y", errors="coerce")
        light = pd.to_numeric(component_match.group("light").replace(",", ""), errors="coerce")
        middle = pd.to_numeric(component_match.group("middle").replace(",", ""), errors="coerce")
        heavy = pd.to_numeric(component_match.group("heavy").replace(",", ""), errors="coerce")
    else:
        block_match = FUJAIRAH_BLOCK_PATTERN.search(normalized_text)
        if not block_match:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id="FUJAIRAH",
                            expected_source="FOIZ statistics page",
                            actual_source="FOIZ statistics page",
                            status="parse_failed",
                            note="Reached the official FOIZ statistics page but could not parse the latest Fujairah inventory totals.",
                        )
                    ]
                ),
            )

        as_of_date = pd.to_datetime(block_match.group(1), format="%d/%m/%Y", errors="coerce")
        inventory_block = block_match.group(2)
        light_label = re.search(r"LIGHT DISTILLATES", inventory_block, re.IGNORECASE)
        middle_label = re.search(r"MEDIUM DISTILLATES", inventory_block, re.IGNORECASE)
        heavy_label = re.search(r"HEAVY DISTILLATES\s*&\s*RESIDUE", inventory_block, re.IGNORECASE)

        def _strongest_numeric(segment: str) -> float | pd._libs.missing.NAType:
            values = [
                int(token.replace(",", ""))
                for token in re.findall(r"\b\d[\d,]*\b", segment)
            ]
            return max(values) if values else pd.NA

        light = (
            _strongest_numeric(inventory_block[: light_label.start()])
            if light_label
            else pd.NA
        )
        middle = (
            _strongest_numeric(inventory_block[light_label.end() : middle_label.start()])
            if light_label and middle_label
            else pd.NA
        )
        heavy = (
            _strongest_numeric(inventory_block[middle_label.end() : heavy_label.start()])
            if middle_label and heavy_label
            else pd.NA
        )
    if pd.isna(as_of_date) or any(pd.isna(value) for value in [light, middle, heavy]):
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="FUJAIRAH",
                        expected_source="FOIZ statistics page",
                        actual_source="FOIZ statistics page",
                        status="parse_failed",
                        note="Parsed the FOIZ page but could not convert the Fujairah inventory date or values.",
                    )
                ]
            ),
        )

    total_mb = float(light + middle + heavy) / 1000.0
    if total_mb <= 0:
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id="FUJAIRAH",
                        expected_source="FOIZ statistics page",
                        actual_source="FOIZ statistics page",
                        status="parse_failed",
                        note="Reached the official FOIZ statistics page, but the extracted inventory total was non-positive. The parser is failing closed rather than publishing a false zero.",
                    )
                ]
            ),
        )
    as_of_timestamp = pd.Timestamp(as_of_date).normalize()
    observation = pd.DataFrame(
        [
            {
                "series_id": "FUJAIRAH",
                "timestamp": as_of_timestamp,
                "value": total_mb,
                "source": "FOIZ statistics page",
                "status": "date_only_public",
                "frequency": "weekly",
            }
        ]
    )
    health = pd.DataFrame(
        [
            health_row(
                series_id="FUJAIRAH",
                expected_source="FOIZ statistics page",
                actual_source="FOIZ statistics page",
                status="date_only_public",
                note="Parsed the official FOIZ page. Total Fujairah inventories are computed from published light, middle, and heavy/residue components. The source page provides an as-of date but no explicit publication time.",
                last_update=as_of_timestamp,
            )
        ]
    )
    return AdapterResponse(observation, health)


class PublicMacroInventoryAdapter(BaseAdapter):
    adapter_name = "public_inventory"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        csv_response = load_directory_csv(
            directory=self.config.public_dir,
            allowed_series=PUBLIC_SERIES_IDS,
            expected_source="Public inventory CSV",
            default_status="delayed_public",
        )
        official_responses = [_fetch_cushing_eia(), _fetch_fujairah_foiz()]

        observations = [csv_response.observations] + [response.observations for response in official_responses]
        health = [csv_response.source_health] + [response.source_health for response in official_responses]

        observations_frame = pd.concat(observations, ignore_index=True) if any(not frame.empty for frame in observations) else empty_observations()
        health_frame = pd.concat(health, ignore_index=True) if any(not frame.empty for frame in health) else empty_health()
        if not health_frame.empty:
            health_frame = health_frame.drop_duplicates(subset=["series_id"], keep="last")
        return AdapterResponse(observations_frame, health_frame)
