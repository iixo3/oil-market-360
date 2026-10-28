from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import math

import pandas as pd

from .base import BaseAdapter, empty_health, empty_observations, health_row
from .csv_manual import load_directory_csv
from ..catalog import EXCHANGE_SERIES_IDS
from ..config import AppConfig
from ..models import AdapterResponse


@dataclass(frozen=True)
class IBKRCandidate:
    symbol: str
    exchange: str
    currency: str = "USD"


IBKR_CANDIDATES: dict[str, list[IBKRCandidate]] = {
    "CL": [IBKRCandidate("CL", "NYMEX")],
    "BRENT": [
        IBKRCandidate("COIL", "IPE"),
        IBKRCandidate("COIL", "ICEEU"),
        IBKRCandidate("BZ", "NYMEX"),
    ],
    "AUB": [IBKRCandidate("AUB", "NYMEX")],
    "OQD": [
        IBKRCandidate("OQD", "NYMEX"),
        IBKRCandidate("OQD", "GME"),
        IBKRCandidate("OQD", "DME"),
    ],
    "HTT": [IBKRCandidate("HTT", "NYMEX")],
    "WTT": [IBKRCandidate("WTT", "NYMEX")],
    "YV": [
        IBKRCandidate("AYV", "NYMEX"),
        IBKRCandidate("YV", "NYMEX"),
    ],
    "WHT": [IBKRCandidate("WHT", "NYMEX")],
    "RB": [IBKRCandidate("RB", "NYMEX")],
    "HO": [IBKRCandidate("HO", "NYMEX")],
    "G": [
        IBKRCandidate("G", "IPE"),
        IBKRCandidate("G", "ICEEU"),
    ],
}

IBKR_STATUS_MAP = {
    1: "live",
    2: "frozen",
    3: "delayed",
    4: "delayed_frozen",
}


class ExchangeBrokerAdapter(BaseAdapter):
    adapter_name = "exchange_broker"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> AdapterResponse:
        csv_response = load_directory_csv(
            directory=self.config.manual_dir,
            allowed_series=EXCHANGE_SERIES_IDS,
            expected_source="TradingView / IBKR CSV",
            default_status="delayed",
        )
        direct_response = self._fetch_direct_ibkr()

        observations = pd.concat(
            [direct_response.observations, csv_response.observations],
            ignore_index=True,
        )
        health = pd.concat(
            [direct_response.source_health, csv_response.source_health],
            ignore_index=True,
        ).drop_duplicates(subset=["series_id"], keep="first")
        return AdapterResponse(observations, health)

    def _fetch_direct_ibkr(self) -> AdapterResponse:
        if not self.config.ibkr_enabled:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id=series_id,
                            expected_source="IBKR direct or TradingView/IBKR CSV",
                            actual_source="IBKR disabled",
                            status="not_configured",
                            note="Direct IBKR is disabled. The app will use CSV imports or placeholders instead.",
                        )
                        for series_id in sorted(EXCHANGE_SERIES_IDS)
                    ]
                ),
            )

        self._ensure_event_loop()
        try:
            from ib_insync import Future, IB
        except ImportError:
            return AdapterResponse(
                empty_observations(),
                pd.DataFrame(
                    [
                        health_row(
                            series_id=series_id,
                            expected_source="IBKR direct",
                            actual_source="ib-insync missing",
                            status="dependency_missing",
                            note="Install the optional ib-insync dependency before using direct IBKR quotes.",
                        )
                        for series_id in sorted(EXCHANGE_SERIES_IDS)
                    ]
                ),
            )

        ib = IB()
        connected_port: int | None = None
        connection_errors: list[str] = []
        try:
            for port in self.config.ibkr_ports:
                try:
                    if ib.connect(
                        self.config.ibkr_host,
                        port,
                        clientId=self.config.ibkr_client_id,
                        timeout=self.config.ibkr_timeout_seconds,
                        readonly=True,
                    ):
                        connected_port = port
                        break
                except Exception as exc:  # pragma: no cover - depends on local IBKR runtime
                    connection_errors.append(f"{port}: {exc}")

            if connected_port is None:
                return AdapterResponse(
                    empty_observations(),
                    pd.DataFrame(
                        [
                            health_row(
                                series_id=series_id,
                                expected_source="IBKR direct",
                                actual_source=f"{self.config.ibkr_host}:{','.join(str(port) for port in self.config.ibkr_ports)}",
                                status="connection_failed",
                                note="Could not connect to TWS/IB Gateway on the configured ports.",
                            )
                            for series_id in sorted(EXCHANGE_SERIES_IDS)
                        ]
                    ),
                )

            ib.reqMarketDataType(3)

            observations: list[dict[str, object]] = []
            health_rows: list[dict[str, object]] = []

            for series_id in sorted(EXCHANGE_SERIES_IDS):
                contract, attempt_note = self._resolve_front_contract(ib, Future, series_id)
                if contract is None:
                    health_rows.append(
                        health_row(
                            series_id=series_id,
                            expected_source="IBKR direct",
                            actual_source=f"IBKR {self.config.ibkr_host}:{connected_port}",
                            status="contract_not_found",
                            note=self._not_found_note(series_id, attempt_note),
                        )
                    )
                    continue

                try:
                    ticker = ib.reqTickers(contract)[0]
                except Exception as exc:  # pragma: no cover - depends on local IBKR runtime
                    health_rows.append(
                        health_row(
                            series_id=series_id,
                            expected_source="IBKR direct",
                            actual_source=self._contract_label(contract),
                            status="quote_request_failed",
                            note=f"Contract resolved but quote request failed: {exc}",
                        )
                    )
                    continue

                value = self._extract_value(ticker)
                if value is None:
                    health_rows.append(
                        health_row(
                            series_id=series_id,
                            expected_source="IBKR direct",
                            actual_source=self._contract_label(contract),
                            status="no_quote",
                            note="Contract resolved but no usable market data field was returned.",
                        )
                    )
                    continue

                timestamp = self._extract_timestamp(ticker)
                market_status = self._market_status(ticker)
                source_label = self._contract_label(contract)

                observations.append(
                    {
                        "series_id": series_id,
                        "timestamp": timestamp,
                        "value": value,
                        "source": source_label,
                        "status": market_status,
                        "frequency": "intraday",
                    }
                )
                health_rows.append(
                    health_row(
                        series_id=series_id,
                        expected_source="IBKR direct",
                        actual_source=source_label,
                        status=market_status,
                        note=self._resolution_note(series_id, attempt_note),
                        last_update=timestamp,
                    )
                )

            if connection_errors:
                failed_note = " Other ports failed: " + " | ".join(connection_errors[:3])
                for row in health_rows:
                    row["note"] = f"{row['note']}{failed_note}"

            observations_frame = (
                pd.DataFrame(observations)[["series_id", "timestamp", "value", "source", "status", "frequency"]]
                if observations
                else empty_observations()
            )
            health_frame = pd.DataFrame(health_rows) if health_rows else empty_health()
            return AdapterResponse(observations_frame, health_frame)
        finally:
            if ib.isConnected():
                ib.disconnect()

    def _resolve_front_contract(self, ib, future_cls, series_id: str):
        candidates = IBKR_CANDIDATES.get(series_id, [IBKRCandidate(series_id, "NYMEX")])
        attempted: list[str] = []
        today = datetime.utcnow().strftime("%Y%m%d")

        for candidate in candidates:
            attempted.append(f"{candidate.symbol}@{candidate.exchange}")
            template = future_cls(
                symbol=candidate.symbol,
                exchange=candidate.exchange,
                currency=candidate.currency,
            )
            try:
                details = ib.reqContractDetails(template)
            except Exception:  # pragma: no cover - depends on local IBKR runtime
                continue
            if not details:
                continue

            contracts = [detail.contract for detail in details]
            active = [contract for contract in contracts if self._is_active_contract(contract, today)]
            selected = self._select_earliest_contract(active or contracts)
            if selected is not None:
                return selected, f"Resolved via {candidate.symbol}@{candidate.exchange}"

        return None, f"Tried candidates: {', '.join(attempted)}"

    @staticmethod
    def _is_active_contract(contract, today: str) -> bool:
        raw = getattr(contract, "lastTradeDateOrContractMonth", "") or ""
        digits = "".join(character for character in raw if character.isdigit())
        if len(digits) >= 8:
            return digits[:8] >= today
        if len(digits) >= 6:
            return digits[:6] >= today[:6]
        return True

    @staticmethod
    def _select_earliest_contract(contracts: list):
        if not contracts:
            return None
        return sorted(contracts, key=lambda contract: getattr(contract, "lastTradeDateOrContractMonth", "") or "99999999")[0]

    @staticmethod
    def _market_status(ticker) -> str:
        market_data_type = getattr(ticker, "marketDataType", None)
        return IBKR_STATUS_MAP.get(market_data_type, "delayed")

    @staticmethod
    def _extract_timestamp(ticker) -> pd.Timestamp:
        timestamp = getattr(ticker, "time", None)
        if timestamp is None:
            return pd.Timestamp.utcnow().tz_localize(None)
        return pd.Timestamp(timestamp).tz_localize(None) if pd.Timestamp(timestamp).tzinfo else pd.Timestamp(timestamp)

    @staticmethod
    def _extract_value(ticker) -> float | None:
        candidates = [
            ("marketPrice", getattr(ticker, "marketPrice", lambda: None)()),
            ("last", getattr(ticker, "last", None)),
            ("close", getattr(ticker, "close", None)),
            ("bid", getattr(ticker, "bid", None)),
            ("ask", getattr(ticker, "ask", None)),
        ]
        for field_name, candidate in candidates:
            if candidate is None:
                continue
            try:
                numeric = float(candidate)
            except (TypeError, ValueError):
                continue
            if field_name != "close" and numeric == -1:
                continue
            if math.isfinite(numeric):
                return numeric
        return None

    @staticmethod
    def _contract_label(contract) -> str:
        local_symbol = getattr(contract, "localSymbol", "") or getattr(contract, "symbol", "unknown")
        exchange = getattr(contract, "exchange", "unknown")
        expiry = getattr(contract, "lastTradeDateOrContractMonth", "") or ""
        return f"IBKR {local_symbol}@{exchange} {expiry}".strip()

    @staticmethod
    def _resolution_note(series_id: str, attempt_note: str) -> str:
        if series_id == "BRENT":
            return (
                "Direct IBKR quote resolved from the broker's Brent contract family "
                f"({attempt_note}). The dashboard keeps the display label as Brent (BZ) "
                "and reserves the exact broker instrument name for provenance only."
            )
        return f"Direct IBKR quote resolved from current front-month contract candidate ({attempt_note})."

    @staticmethod
    def _not_found_note(series_id: str, attempt_note: str) -> str:
        if series_id == "OQD":
            return (
                "Direct IBKR contract lookup did not resolve an Oman crude future "
                f"({attempt_note}). Current fallback path should be TradingView/CSV for Oman, "
                "with the dashboard keeping the displayed market label generic rather than feed-specific."
            )
        return attempt_note

    @staticmethod
    def _ensure_event_loop() -> None:
        try:
            asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
