from __future__ import annotations

import numpy as np
import pandas as pd

from ..catalog import CORRELATION_MATRIX_SERIES, CORRELATION_PAIRS, LAG_RELATIONSHIPS


VIEW_RULES = {
    "Intraday": {"resample": "4H", "change_lookback": 6, "window_short": 12, "window_medium": 36},
    "Daily": {"resample": "1D", "change_lookback": 5, "window_short": 20, "window_medium": 60},
    "Weekly": {"resample": "1W-FRI", "change_lookback": 4, "window_short": 12, "window_medium": 26},
}


def prepare_wide_frame(observations: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if observations.empty:
        return pd.DataFrame()

    frame = observations.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_localize(None)
    frame = frame.sort_values(["timestamp", "series_id"]).drop_duplicates(["series_id", "timestamp"], keep="last")
    wide = frame.pivot(index="timestamp", columns="series_id", values="value").sort_index()
    wide = wide.resample(VIEW_RULES[timeframe]["resample"]).last().ffill()
    return add_derived_series(wide)


def add_derived_series(wide: pd.DataFrame) -> pd.DataFrame:
    result = wide.copy()
    if {"BRENT", "CL"}.issubset(result.columns):
        result["BRENT_CL_SPREAD"] = result["BRENT"] - result["CL"]
    if "AUB" in result.columns and "BRENT" in result.columns:
        result["NORTHSEA_PHYSICAL_PREMIUM"] = result["AUB"] - result["BRENT"]
    elif "DATED_BRENT" in result.columns and "BRENT" in result.columns:
        result["NORTHSEA_PHYSICAL_PREMIUM"] = result["DATED_BRENT"] - result["BRENT"]

    east_components = [column for column in ["OQD", "DBI", "ADM"] if column in result.columns]
    if east_components and "BRENT" in result.columns:
        result["EAST_OF_SUEZ_PREMIUM"] = result[east_components].mean(axis=1) - result["BRENT"]

    if {"RB", "CL"}.issubset(result.columns):
        result["GASOLINE_CRACK_PROXY"] = result["RB"] * 42 - result["CL"]
    if {"HO", "CL"}.issubset(result.columns):
        result["DIESEL_CRACK_PROXY"] = result["HO"] * 42 - result["CL"]
    if {"G", "BRENT"}.issubset(result.columns):
        result["GASOIL_CRACK_PROXY"] = result["G"] / 7.45 - result["BRENT"]
    if {"RB", "HO", "CL"}.issubset(result.columns):
        result["THREE_TWO_ONE_CRACK_PROXY"] = (((result["RB"] * 2) + result["HO"]) * 42 / 3) - result["CL"]
    return result


def build_source_health(
    observations: pd.DataFrame,
    catalog: dict,
    adapter_health: pd.DataFrame | None = None,
) -> pd.DataFrame:
    latest = (
        observations.sort_values("timestamp").groupby("series_id").tail(1).set_index("series_id")
        if not observations.empty
        else pd.DataFrame()
    )
    feed_health = (
        adapter_health.sort_values("last_update").groupby("series_id").tail(1).set_index("series_id")
        if adapter_health is not None and not adapter_health.empty
        else pd.DataFrame()
    )
    rows = []
    for series_id, definition in catalog.items():
        feed_row = feed_health.loc[series_id] if series_id in feed_health.index else None
        if series_id in latest.index:
            row = latest.loc[series_id]
            rows.append(
                {
                    "series_id": series_id,
                    "display_name": definition.display_name,
                    "layer": definition.layer,
                    "expected_source": definition.source_family,
                    "actual_source": row["source"],
                    "status": row["status"],
                    "last_update": row["timestamp"],
                    "fallback_proxy": definition.fallback_proxy,
                    "why_it_matters": definition.why_it_matters,
                    "feed_source": feed_row["actual_source"] if feed_row is not None else row["source"],
                    "feed_status": feed_row["status"] if feed_row is not None else row["status"],
                    "feed_last_update": feed_row["last_update"] if feed_row is not None else row["timestamp"],
                    "feed_note": feed_row["note"] if feed_row is not None else "",
                }
            )
        else:
            rows.append(
                {
                    "series_id": series_id,
                    "display_name": definition.display_name,
                    "layer": definition.layer,
                    "expected_source": definition.source_family,
                    "actual_source": "missing",
                    "status": "missing",
                    "last_update": pd.NaT,
                    "fallback_proxy": definition.fallback_proxy,
                    "why_it_matters": definition.why_it_matters,
                    "feed_source": feed_row["actual_source"] if feed_row is not None else definition.source_family,
                    "feed_status": feed_row["status"] if feed_row is not None else "not_checked",
                    "feed_last_update": feed_row["last_update"] if feed_row is not None else pd.NaT,
                    "feed_note": feed_row["note"] if feed_row is not None else "",
                }
            )
    return pd.DataFrame(rows)


def _latest_zscore(series: pd.Series, window: int = 60) -> float:
    cleaned = series.dropna()
    if cleaned.empty:
        return np.nan
    sample = cleaned.tail(window)
    std = sample.std(ddof=0)
    if std == 0 or np.isnan(std):
        return 0.0
    return float((sample.iloc[-1] - sample.mean()) / std)


def _latest_percentile(series: pd.Series, window: int = 120) -> float:
    cleaned = series.dropna()
    if cleaned.empty:
        return np.nan
    sample = cleaned.tail(window)
    return float((sample.rank(pct=True).iloc[-1]) * 100)


def build_snapshot(wide: pd.DataFrame, source_health: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame()

    lookback = VIEW_RULES[timeframe]["change_lookback"]
    latest = wide.ffill().iloc[-1]
    previous = wide.ffill().shift(1).iloc[-1]
    anchor = wide.ffill().shift(lookback).iloc[-1]

    rows = []
    for series_id in wide.columns:
        series = wide[series_id]
        metadata = source_health[source_health["series_id"] == series_id]
        source = metadata.iloc[0]["actual_source"] if not metadata.empty else "unknown"
        status = metadata.iloc[0]["status"] if not metadata.empty else "unknown"
        metadata_last_update = metadata.iloc[0]["last_update"] if not metadata.empty else pd.NaT
        series_last_update = series.dropna().index.max() if not series.dropna().empty else pd.NaT
        rows.append(
            {
                "series_id": series_id,
                "last": latest.get(series_id, np.nan),
                "delta_1": latest.get(series_id, np.nan) - previous.get(series_id, np.nan),
                "delta_window": latest.get(series_id, np.nan) - anchor.get(series_id, np.nan),
                "zscore_60": _latest_zscore(series, 60),
                "percentile_120": _latest_percentile(series, 120),
                "source": source,
                "status": status,
                "last_update": metadata_last_update if pd.notna(metadata_last_update) else series_last_update,
            }
        )
    return pd.DataFrame(rows).set_index("series_id")


def compute_correlation_history(wide: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame()

    short_window = VIEW_RULES[timeframe]["window_short"]
    medium_window = VIEW_RULES[timeframe]["window_medium"]
    frames = []
    for left, right, label in CORRELATION_PAIRS:
        if left not in wide.columns or right not in wide.columns:
            continue
        pair = wide[[left, right]].dropna()
        if len(pair) < medium_window:
            continue
        short = pair[left].rolling(short_window).corr(pair[right])
        medium = pair[left].rolling(medium_window).corr(pair[right])
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": pair.index,
                    "pair": label,
                    "left": left,
                    "right": right,
                    "short_corr": short,
                    "medium_corr": medium,
                }
            ).dropna()
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def compute_correlation_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    available = [series_id for series_id in CORRELATION_MATRIX_SERIES if series_id in wide.columns]
    if not available:
        return pd.DataFrame()
    frame = wide[available].tail(90).corr().round(2)
    return frame


def detect_divergences(correlation_history: pd.DataFrame) -> pd.DataFrame:
    if correlation_history.empty:
        return pd.DataFrame(columns=["pair", "short_corr", "medium_corr", "message"])

    latest = correlation_history.sort_values("timestamp").groupby("pair").tail(1).copy()
    latest["message"] = ""
    mask = (latest["medium_corr"].abs() >= 0.45) & (
        (latest["short_corr"].abs() <= 0.20) | ((latest["medium_corr"] * latest["short_corr"]) < 0)
    )
    latest = latest[mask]
    latest["message"] = latest.apply(
        lambda row: (
            f"Historically linked pair is decoupling: medium-term corr {row['medium_corr']:.2f}, "
            f"short-term corr {row['short_corr']:.2f}."
        ),
        axis=1,
    )
    return latest[["pair", "short_corr", "medium_corr", "message"]].sort_values("pair")


def compute_lagged_relationships(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for left, right, explanation in LAG_RELATIONSHIPS:
        if left not in wide.columns or right not in wide.columns:
            continue
        pair = wide[[left, right]].dropna()
        if len(pair) < 25:
            continue
        best_lag = 0
        best_corr = None
        for lag in range(0, 6):
            shifted = pair[right].shift(-lag)
            corr = pair[left].corr(shifted)
            if pd.notna(corr) and (best_corr is None or abs(corr) > abs(best_corr)):
                best_corr = corr
                best_lag = lag
        rows.append(
            {
                "relationship": f"{left} -> {right}",
                "best_lag_periods": best_lag,
                "lagged_corr": best_corr if best_corr is not None else np.nan,
                "explanation": explanation,
            }
        )
    return pd.DataFrame(rows)
