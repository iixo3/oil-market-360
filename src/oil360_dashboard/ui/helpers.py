from __future__ import annotations

import calendar
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..catalog import DERIVED_SERIES, SERIES_CATALOG


def display_name(series_id: str) -> str:
    if series_id in SERIES_CATALOG:
        return SERIES_CATALOG[series_id].display_name
    if series_id in DERIVED_SERIES:
        return series_id.replace("_", " ").title()
    return series_id


def series_tooltip(series_id: str) -> str:
    if series_id in SERIES_CATALOG:
        return SERIES_CATALOG[series_id].tooltip
    return DERIVED_SERIES.get(series_id, "Derived metric.")


def series_unit(series_id: str) -> str:
    if series_id in SERIES_CATALOG:
        return SERIES_CATALOG[series_id].unit
    return ""


def format_value(series_id: str, value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if abs(value) >= 100:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def format_timestamp(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    timestamp = pd.Timestamp(value)
    return f"{format_date(value)}, {timestamp.strftime('%H:%M')}"


def format_date(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    timestamp = pd.Timestamp(value)
    day = timestamp.day
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    month = calendar.month_name[timestamp.month]
    return f"{day}{suffix} {month}"


def show_helper(enabled: bool, title: str, body: str) -> None:
    if enabled:
        st.info(f"**{title}**  \n{body}")


def status_chip(status: str) -> str:
    return status.replace("_", " ").title()


def traffic_light(score: float) -> str:
    if score >= 67:
        return "Red"
    if score >= 45:
        return "Amber"
    return "Green"


def line_chart(
    wide: pd.DataFrame,
    series_ids: Iterable[str],
    title: str,
    normalize: bool = False,
) -> go.Figure:
    fig = go.Figure()
    for series_id in series_ids:
        if series_id not in wide.columns:
            continue
        series = wide[series_id].dropna()
        if series.empty:
            continue
        plotted = (series / series.iloc[0] * 100.0) if normalize else series
        unit = "base=100" if normalize else series_unit(series_id)
        fig.add_trace(
            go.Scatter(
                x=plotted.index,
                y=plotted.values,
                mode="lines",
                name=display_name(series_id),
                hovertemplate=(
                    f"{display_name(series_id)}<br>%{{x|%Y-%m-%d}}<br>"
                    f"%{{y:.2f}} {unit}<br>{series_tooltip(series_id)}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title=title,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h"),
        height=360,
    )
    return fig


def correlation_chart(correlation_history: pd.DataFrame, pairs: list[str] | None = None) -> go.Figure:
    fig = go.Figure()
    if correlation_history.empty:
        return fig
    frame = correlation_history.copy()
    if pairs:
        frame = frame[frame["pair"].isin(pairs)]
    for pair in frame["pair"].unique():
        pair_frame = frame[frame["pair"] == pair]
        fig.add_trace(go.Scatter(x=pair_frame["timestamp"], y=pair_frame["short_corr"], mode="lines", name=f"{pair} short"))
        fig.add_trace(
            go.Scatter(
                x=pair_frame["timestamp"],
                y=pair_frame["medium_corr"],
                mode="lines",
                name=f"{pair} medium",
                line=dict(dash="dash"),
            )
        )
    fig.update_layout(
        title="Rolling correlations",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h"),
        yaxis=dict(range=[-1, 1]),
        height=380,
    )
    return fig


def heatmap_chart(matrix: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            colorbar=dict(title="Corr"),
        )
    )
    fig.update_layout(title="Correlation heatmap", height=420, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def composite_bar_chart(composites: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        data=go.Bar(
            x=composites["score"],
            y=composites["composite"],
            orientation="h",
            marker_color=composites["score"].apply(
                lambda score: "#b22222" if score >= 67 else "#d89b00" if score >= 45 else "#2f7d32"
            ),
        )
    )
    fig.update_layout(
        title="Composite stress heuristics",
        xaxis=dict(range=[0, 100]),
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def relationship_chart(graph: dict) -> go.Figure:
    nodes = {node["id"]: node for node in graph["nodes"]}
    fig = go.Figure()
    for edge in graph["edges"]:
        source = nodes[edge["source"]]
        target = nodes[edge["target"]]
        fig.add_trace(
            go.Scatter(
                x=[source["x"], target["x"]],
                y=[source["y"], target["y"]],
                mode="lines",
                line=dict(width=2, color="#6c7a89"),
                hoverinfo="text",
                text=f"{edge['label']}: {edge['explanation']}",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[node["x"] for node in graph["nodes"]],
            y=[node["y"] for node in graph["nodes"]],
            mode="markers+text",
            text=[node["label"] for node in graph["nodes"]],
            textposition="bottom center",
            marker=dict(size=18, color="#264653"),
            hoverinfo="text",
            hovertext=[node["label"] for node in graph["nodes"]],
            showlegend=False,
        )
    )
    fig.update_layout(
        title="Relationship map",
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1]),
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def lag_chart(wide: pd.DataFrame, left: str, right: str, lag: int) -> go.Figure:
    fig = go.Figure()
    if left not in wide.columns or right not in wide.columns:
        return fig
    frame = wide[[left, right]].dropna().copy()
    if frame.empty:
        return fig
    shifted = frame[right].shift(-lag)
    fig.add_trace(go.Scatter(x=frame.index, y=frame[left], mode="lines", name=display_name(left)))
    fig.add_trace(
        go.Scatter(
            x=frame.index,
            y=shifted,
            mode="lines",
            name=f"{display_name(right)} shifted {-lag}",
            line=dict(dash="dash"),
        )
    )
    fig.update_layout(
        title=f"Lagged comparison: {display_name(left)} vs {display_name(right)}",
        height=340,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h"),
    )
    return fig
