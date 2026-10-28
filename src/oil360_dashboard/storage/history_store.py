from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


class HistoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    series_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    value REAL NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    PRIMARY KEY (series_id, timestamp)
                )
                """
            )

    def upsert_observations(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        normalized = frame.copy()
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
        real_series_ids = (
            normalized.loc[normalized["status"] != "placeholder", "series_id"].dropna().astype(str).unique().tolist()
        )
        rows = list(
            normalized[["series_id", "timestamp", "value", "source", "status", "frequency"]].itertuples(index=False, name=None)
        )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO observations (
                    series_id, timestamp, value, source, status, frequency
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            if real_series_ids:
                placeholders = ", ".join("?" for _ in real_series_ids)
                connection.execute(
                    f"""
                    DELETE FROM observations
                    WHERE status = 'placeholder'
                      AND series_id IN ({placeholders})
                    """,
                    real_series_ids,
                )

    def load_observations(self, series_ids: list[str], start: pd.Timestamp | None = None) -> pd.DataFrame:
        if not series_ids:
            return pd.DataFrame(columns=["series_id", "timestamp", "value", "source", "status", "frequency"])

        placeholders = ", ".join("?" for _ in series_ids)
        query = f"""
            SELECT series_id, timestamp, value, source, status, frequency
            FROM observations
            WHERE series_id IN ({placeholders})
        """
        params: list[object] = list(series_ids)
        if start is not None:
            query += " AND timestamp >= ?"
            params.append(pd.Timestamp(start).strftime("%Y-%m-%d %H:%M:%S"))
        query += " ORDER BY timestamp"

        with self._connect() as connection:
            frame = pd.read_sql_query(query, connection, params=params)
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_localize(None)
        return frame
