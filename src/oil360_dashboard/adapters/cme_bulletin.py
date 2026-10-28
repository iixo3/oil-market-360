from __future__ import annotations

from io import BytesIO
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from ..models import AdapterResponse


CME_BULLETIN_URL = "https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf"
USER_AGENT = "Mozilla/5.0 (compatible; Oil360Dashboard/1.0)"

BULLETIN_DATE_PATTERN = re.compile(r"BULLETIN\s+#\s*\d+@\s*([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{2},\s+\d{4})")
CONTRACT_LINE_PATTERN = re.compile(r"^(?P<contract>(?:[A-Z]{3}\d{2}|\d{2}[A-Z]{3}\d{2}))\b")

TARGETS: dict[str, dict[str, object]] = {
    "AUB": {
        "aliases": ("UB FUT", "DATED BRENT (PLATTS) FINANCIAL"),
        "source_label": "CME daily bulletin (UB / Dated Brent Platts financial)",
        "expected_source": "CME daily bulletin",
        "frequency": "daily",
    },
    "HTT": {
        "aliases": ("HTT FUT", "WTI HOUSTON ARGUS V.WTI TRADE MONTH"),
        "source_label": "CME daily bulletin (HTT / WTI Houston vs WTI trade month)",
        "expected_source": "CME daily bulletin",
        "frequency": "daily",
    },
    "WTT": {
        "aliases": ("WTT FUT", "WTI MIDLAND (ARG) VS. WTI TRADE MTH"),
        "source_label": "CME daily bulletin (WTT / WTI Midland vs WTI trade month)",
        "expected_source": "CME daily bulletin",
        "frequency": "daily",
    },
    "G": {
        "aliases": ("7F FUT", "EUROPEAN GASOIL ICE FUTURE"),
        "source_label": "CME daily bulletin (7F / European gasoil ICE future)",
        "expected_source": "CME daily bulletin",
        "frequency": "daily",
    },
    "WHT": {
        "aliases": ("WHT FUT", "WCS HOUSTON (ARGUS) VS. WTI TRADE MONTH", "WCS HOUSTON"),
        "source_label": "CME daily bulletin (WHT / WCS Houston vs WTI trade month)",
        "expected_source": "CME daily bulletin",
        "frequency": "daily",
    },
}


class CMEDailyBulletinAdapter(BaseAdapter):
    adapter_name = "cme_daily_bulletin"

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        try:
            from pypdf import PdfReader
        except ImportError:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id=series_id,
                            expected_source=str(config["expected_source"]),
                            actual_source="pypdf missing",
                            status="dependency_missing",
                            note="Install the optional pypdf dependency before using official CME daily bulletin parsing.",
                        )
                        for series_id, config in TARGETS.items()
                    ]
                ),
            )

        try:
            request = Request(CME_BULLETIN_URL, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=6) as response:
                payload = response.read()
        except URLError as exc:
            return self._all_failed("fetch_failed", f"Could not reach the official CME daily bulletin PDF: {exc}")
        except Exception as exc:  # pragma: no cover - depends on live network
            return self._all_failed("fetch_failed", f"CME daily bulletin fetch failed: {exc}")

        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)
        except Exception as exc:  # pragma: no cover - depends on live PDF content
            return self._all_failed("parse_failed", f"Could not extract text from the official CME daily bulletin PDF: {exc}")

        lines = [" ".join(line.split()) for line in text.splitlines() if line and line.strip()]
        bulletin_date = self._extract_bulletin_date(text, lines)

        observations: list[dict[str, object]] = []
        health_rows: list[dict[str, object]] = []
        for series_id, config in TARGETS.items():
            row = self._extract_front_row(lines, tuple(config["aliases"]))
            if row is None or bulletin_date is None:
                health_rows.append(
                    health_row(
                        series_id=series_id,
                        expected_source=str(config["expected_source"]),
                        actual_source=str(config["source_label"]),
                        status="parse_failed",
                        note=(
                            "Reached the official CME daily bulletin, but could not locate the current front-month "
                            f"settlement row for aliases {', '.join(config['aliases'])}."
                        ),
                    )
                )
                continue

            observations.append(
                {
                    "series_id": series_id,
                    "timestamp": bulletin_date,
                    "value": row["value"],
                    "source": str(config["source_label"]),
                    "status": "date_only_public",
                    "frequency": str(config["frequency"]),
                }
            )
            health_rows.append(
                health_row(
                    series_id=series_id,
                    expected_source=str(config["expected_source"]),
                    actual_source=str(config["source_label"]),
                    status="date_only_public",
                    note=(
                        "Parsed the official CME daily bulletin front-month settlement row. "
                        f"Matched product line '{row['product_line']}' and contract '{row['contract']}'. "
                        "The bulletin exposes the trade date clearly, but not a product-level intraday timestamp, "
                        "so the dashboard shows the settlement date only."
                    ),
                    last_update=bulletin_date,
                )
            )

        return AdapterResponse(
            pd.DataFrame(observations)[["series_id", "timestamp", "value", "source", "status", "frequency"]]
            if observations
            else empty_observations(),
            pd.DataFrame(health_rows) if health_rows else empty_health(),
        )

    @staticmethod
    def _extract_bulletin_date(text: str, lines: list[str]) -> pd.Timestamp | None:
        match = BULLETIN_DATE_PATTERN.search(text)
        if match:
            parsed = pd.to_datetime(match.group(1), format="%a, %b %d, %Y", errors="coerce")
            if pd.notna(parsed):
                return pd.Timestamp(parsed).normalize()
        for line in lines:
            match = BULLETIN_DATE_PATTERN.search(line)
            if match:
                parsed = pd.to_datetime(match.group(1), format="%a, %b %d, %Y", errors="coerce")
                if pd.notna(parsed):
                    return pd.Timestamp(parsed).normalize()
        return None

    @staticmethod
    def _extract_front_row(lines: list[str], aliases: tuple[str, ...]) -> dict[str, object] | None:
        alias_hits = [alias.upper() for alias in aliases]
        for idx, line in enumerate(lines):
            upper = line.upper()
            if not any(alias in upper for alias in alias_hits):
                continue

            for candidate in lines[idx + 1 : idx + 80]:
                if candidate.startswith("TOTAL ") or "THE INFORMATION CONTAINED IN THIS REPORT" in candidate:
                    break
                contract_match = CONTRACT_LINE_PATTERN.match(candidate)
                if not contract_match:
                    continue
                value = CMEDailyBulletinAdapter._extract_first_numeric_value(candidate)
                if value is None:
                    continue
                return {
                    "contract": contract_match.group("contract"),
                    "value": value,
                    "product_line": line,
                }
        return None

    @staticmethod
    def _extract_first_numeric_value(line: str) -> float | None:
        tokens = line.split()
        if len(tokens) <= 1:
            return None
        for token in tokens[1:]:
            normalized = token.replace(",", "")
            if normalized in {"----", "--"}:
                continue
            try:
                return float(normalized)
            except ValueError:
                continue
        return None

    @staticmethod
    def _all_failed(status: str, note: str) -> AdapterResponse:
        return AdapterResponse(
            empty_observations(),
            pd.DataFrame(
                [
                    health_row(
                        series_id=series_id,
                        expected_source=str(config["expected_source"]),
                        actual_source=str(config["source_label"]),
                        status=status,
                        note=note,
                    )
                    for series_id, config in TARGETS.items()
                ]
            ),
        )
