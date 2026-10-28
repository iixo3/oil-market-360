from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from ..catalog import DERIVED_SERIES, SECTION_SERIES
from ..models import DashboardState
from .helpers import (
    composite_bar_chart,
    correlation_chart,
    display_name,
    format_date,
    format_timestamp,
    format_value,
    heatmap_chart,
    lag_chart,
    line_chart,
    relationship_chart,
    series_tooltip,
    show_helper,
    status_chip,
    traffic_light,
)

SECTION_OPTIONS = [
    "Executive Overview",
    "Paper vs Physical",
    "U.S. Export-Barrel / Location Stress",
    "Sour / Heavy Substitution",
    "Refined Products and Cracks",
    "Freight, Flows, and Logistics",
    "Inventories and Absorption",
    "Correlation and Transmission Map",
    "Composite Indices and Narratives",
    "Source Health and Data Quality",
    "All sections",
]


@dataclass(frozen=True)
class UIContext:
    mode: str
    helper_enabled: bool
    timeframe: str


def _layer_freshness(state: DashboardState, series_ids: list[str] | None = None) -> pd.DataFrame:
    frame = state.source_health.copy()
    if series_ids is not None:
        frame = frame[frame["series_id"].isin(series_ids)]
    if frame.empty:
        return pd.DataFrame(columns=["layer", "freshness", "status", "sort_update"])

    rows: list[dict[str, object]] = []
    for layer, layer_frame in frame.groupby("layer"):
        real_updates = layer_frame[~layer_frame["status"].isin(["missing", "placeholder"])].copy()
        fallback_updates = layer_frame[layer_frame["status"] != "missing"].copy()
        selected = real_updates if not real_updates.empty else fallback_updates

        if selected.empty or selected["last_update"].dropna().empty:
            rows.append(
                {
                    "layer": layer,
                    "freshness": "No update available",
                    "status": "missing",
                    "sort_update": pd.NaT,
                }
            )
            continue

        latest = selected.sort_values("last_update").iloc[-1]
        if latest["status"] == "placeholder":
            freshness = "No real update available"
        elif latest["status"] == "date_only_public":
            freshness = format_date(latest["last_update"])
        else:
            freshness = format_timestamp(latest["last_update"])
        rows.append(
            {
                "layer": layer,
                "freshness": freshness,
                "status": latest["status"],
                "sort_update": latest["last_update"],
            }
        )

    freshness_frame = pd.DataFrame(rows)
    if freshness_frame.empty:
        return freshness_frame
    return freshness_frame.sort_values(["sort_update", "layer"], ascending=[False, True]).reset_index(drop=True)


def _render_layer_freshness(state: DashboardState, series_ids: list[str] | None = None) -> None:
    freshness = _layer_freshness(state, series_ids)
    if freshness.empty:
        return
    st.caption("Latest market timestamps by layer")
    freshness = freshness.assign(data_status=freshness["status"].map(status_chip))
    st.dataframe(
        freshness[["layer", "freshness", "data_status"]],
        hide_index=True,
        use_container_width=True,
    )


def render_dashboard(state: DashboardState, context: UIContext, section: str) -> None:
    st.title("Oil 360 Monitoring Dashboard")
    st.caption(
        "Analyst-first oil-market dashboard with explicit placeholders, local historical storage, "
        "and a shared backend for Beginner and Analyst views."
    )

    if section == "All sections":
        for name in SECTION_OPTIONS[:-1]:
            _SECTION_RENDERERS[name](state, context)
            st.divider()
        return

    _SECTION_RENDERERS[section](state, context)


def _value(state: DashboardState, series_id: str) -> float | None:
    if state.snapshot.empty or series_id not in state.snapshot.index:
        return None
    return state.snapshot.loc[series_id, "last"]


def _metric_caption(state: DashboardState, series_id: str, row: pd.Series) -> str:
    if series_id in DERIVED_SERIES:
        return "Derived"

    status = str(row.get("status", "unknown"))
    if status == "placeholder":
        return "Placeholder"
    if status in {"unknown", "missing", "not_checked"}:
        return "Unchecked feed"

    if pd.isna(row.get("last_update")):
        return status_chip(status)

    if status == "date_only_public":
        return f"Last update: {format_date(row['last_update'])}"

    return f"Last update: {format_timestamp(row['last_update'])}"


def _render_metric_row(state: DashboardState, series_ids: list[str]) -> None:
    available = [series_id for series_id in series_ids if series_id in state.snapshot.index]
    if not available:
        st.caption("No values available.")
        return
    columns = st.columns(min(len(available), 4))
    for idx, series_id in enumerate(available):
        row = state.snapshot.loc[series_id]
        delta = row["delta_1"]
        with columns[idx % len(columns)]:
            st.metric(
                label=display_name(series_id),
                value=format_value(series_id, row["last"]),
                delta=None if pd.isna(delta) else f"{delta:+.2f}",
                help=series_tooltip(series_id),
            )
            st.caption(_metric_caption(state, series_id, row))


def _render_overview(state: DashboardState, context: UIContext) -> None:
    st.subheader("Executive Overview")
    show_helper(
        context.helper_enabled,
        "What this page does",
        "This page is the first-glance view. It helps answer whether today's stress looks more paper-driven, physical, logistical, product-led, or location-specific.",
    )
    _render_layer_freshness(state)
    st.markdown(f"> {state.narrative}")

    composite_cols = st.columns(3)
    for idx, row in state.composites.iterrows():
        with composite_cols[idx % 3]:
            st.metric(row["composite"], f"{row['score']:.1f}")
            st.caption(f"Traffic light: {row['traffic_light']}")

    _render_metric_row(
        state,
        ["CL", "BRENT", "BRENT_CL_SPREAD", "AUB", "OQD", "HTT", "RB", "HO", "G", "BDTI", "CUSHING", "FUJAIRAH"],
    )
    st.plotly_chart(
        line_chart(state.wide_frame, ["CL", "BRENT", "AUB", "OQD", "BDTI"], "Benchmarks and freight (normalized)", normalize=True),
        use_container_width=True,
    )

    cards = st.columns(3)
    for idx, card in enumerate(state.interpretation_cards):
        with cards[idx % 3]:
            st.markdown(f"**{card['title']}**")
            st.caption(card["status"])
            st.write(card["body"])


def _render_paper_physical(state: DashboardState, context: UIContext) -> None:
    st.subheader("Paper vs Physical")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel asks whether prompt physical crude is tighter than futures imply, and whether East-of-Suez stress is stronger than Atlantic Basin stress.",
    )
    _render_layer_freshness(state, SECTION_SERIES["Paper vs Physical"])
    northsea = _value(state, "NORTHSEA_PHYSICAL_PREMIUM") or 0.0
    east = _value(state, "EAST_OF_SUEZ_PREMIUM") or 0.0
    st.write(
        f"Prompt physical tightness signal: {'confirmed' if northsea > 0 else 'not clearly confirmed'}. "
        f"East-of-Suez signal: {'leading' if east > northsea else 'not leading'}."
    )
    st.plotly_chart(
        line_chart(state.wide_frame, SECTION_SERIES["Paper vs Physical"], "Paper vs physical proxies", normalize=True),
        use_container_width=True,
    )
    st.plotly_chart(
        line_chart(
            state.wide_frame,
            ["BRENT_CL_SPREAD", "NORTHSEA_PHYSICAL_PREMIUM", "EAST_OF_SUEZ_PREMIUM"],
            "Spread and differential view",
        ),
        use_container_width=True,
    )
    if context.mode == "Analyst":
        rows = [idx for idx in SECTION_SERIES["Paper vs Physical"] if idx in state.snapshot.index]
        st.dataframe(state.snapshot.loc[rows])


def _render_us_export(state: DashboardState, context: UIContext) -> None:
    st.subheader("U.S. Export-Barrel / Location Stress")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel separates inland WTI weakness from Gulf Coast or export-barrel strength.",
    )
    _render_layer_freshness(state, SECTION_SERIES["U.S. Export-Barrel / Location Stress"])
    htt = _value(state, "HTT") or 0.0
    wtt = _value(state, "WTT") or 0.0
    cushing = _value(state, "CUSHING") or 0.0
    st.write(
        f"Export-barrel signal is {'firm' if htt > 0 or wtt > 0 else 'not firm'}. "
        f"Cushing is at {format_value('CUSHING', cushing)}, which helps distinguish inland pressure from seaborne demand."
    )
    st.plotly_chart(
        line_chart(state.wide_frame, ["CL", "HTT", "WTT", "BRENT_CL_SPREAD"], "CL versus export differentials", normalize=True),
        use_container_width=True,
    )
    st.plotly_chart(line_chart(state.wide_frame, ["CUSHING"], "Cushing inventory trend"), use_container_width=True)
    if context.mode == "Analyst":
        rows = [idx for idx in ["CL", "HTT", "WTT", "CUSHING"] if idx in state.snapshot.index]
        st.dataframe(state.snapshot.loc[rows])


def _render_sour_heavy(state: DashboardState, context: UIContext) -> None:
    st.subheader("Sour / Heavy Substitution")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel checks whether refiners are short the right grade rather than short crude overall.",
    )
    _render_layer_freshness(state, SECTION_SERIES["Sour / Heavy Substitution"])
    st.write(
        "If YV or WHT strengthen while flat-price crude does not, the issue is often grade mismatch rather than aggregate crude scarcity."
    )
    st.plotly_chart(line_chart(state.wide_frame, ["YV", "WHT", "CL"], "Sour/heavy substitution view", normalize=True), use_container_width=True)
    if context.mode == "Analyst":
        rows = [idx for idx in ["YV", "WHT", "CL"] if idx in state.snapshot.index]
        st.dataframe(state.snapshot.loc[rows])


def _render_products(state: DashboardState, context: UIContext) -> None:
    st.subheader("Refined Products and Cracks")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel checks whether the binding constraint sits in crude, refining, or downstream product markets.",
    )
    _render_layer_freshness(state, SECTION_SERIES["Refined Products and Cracks"])
    st.write(
        "Higher crack proxies with stable crude usually point to downstream bottlenecks. Distillate leadership often matters most for freight and industrial demand."
    )
    st.plotly_chart(line_chart(state.wide_frame, ["RB", "HO", "G"], "Products (normalized)", normalize=True), use_container_width=True)
    st.plotly_chart(
        line_chart(
            state.wide_frame,
            ["GASOLINE_CRACK_PROXY", "DIESEL_CRACK_PROXY", "GASOIL_CRACK_PROXY", "THREE_TWO_ONE_CRACK_PROXY"],
            "Crack proxies",
        ),
        use_container_width=True,
    )
    if context.mode == "Analyst":
        rows = [
            idx
            for idx in ["RB", "HO", "G", "GASOLINE_CRACK_PROXY", "DIESEL_CRACK_PROXY", "GASOIL_CRACK_PROXY"]
            if idx in state.snapshot.index
        ]
        st.dataframe(state.snapshot.loc[rows])


def _render_freight(state: DashboardState, context: UIContext) -> None:
    st.subheader("Freight, Flows, and Logistics")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel checks whether cargoes can actually move and whether stress is broad-based, localized, or easing.",
    )
    _render_layer_freshness(state, SECTION_SERIES["Freight, Flows, and Logistics"])
    st.write("Rising freight, lower chokepoint throughput, and firmer physical premia together are stronger evidence of real logistical stress.")
    st.plotly_chart(line_chart(state.wide_frame, ["BDTI", "BCTI"], "Freight indices"), use_container_width=True)
    st.plotly_chart(
        line_chart(state.wide_frame, ["AIS_HORMUZ_TRANSITS", "WAR_RISK_PREMIUM"], "Flow and insurability proxies", normalize=True),
        use_container_width=True,
    )
    if context.mode == "Analyst":
        rows = [idx for idx in ["BDTI", "BCTI", "AIS_HORMUZ_TRANSITS", "WAR_RISK_PREMIUM"] if idx in state.snapshot.index]
        st.dataframe(state.snapshot.loc[rows])


def _render_inventories(state: DashboardState, context: UIContext) -> None:
    st.subheader("Inventories and Absorption")
    show_helper(
        context.helper_enabled,
        "Interpretation target",
        "This panel checks where the system is absorbing disruption and where stress is building rather than clearing.",
    )
    _render_layer_freshness(state, SECTION_SERIES["Inventories and Absorption"])
    st.write("Inventories are a delayed but important confirmation layer. Rising inland stocks can coexist with firm export barrels if the bottleneck is location-specific.")
    st.plotly_chart(line_chart(state.wide_frame, ["CUSHING", "FUJAIRAH", "SINGAPORE", "ARA"], "Inventory hubs"), use_container_width=True)
    if context.mode == "Analyst":
        rows = [idx for idx in ["CUSHING", "FUJAIRAH", "SINGAPORE", "ARA"] if idx in state.snapshot.index]
        st.dataframe(state.snapshot.loc[rows])


def _render_correlation_transmission(state: DashboardState, context: UIContext) -> None:
    st.subheader("Correlation and Transmission Map")
    show_helper(
        context.helper_enabled,
        "How to read this section",
        "Rolling correlations are historical co-movements. The relationship map is a designed heuristic about how stress can travel through the system. They are not the same thing.",
    )
    _render_layer_freshness(state)
    heatmap_col, graph_col = st.columns(2)
    with heatmap_col:
        st.plotly_chart(heatmap_chart(state.correlation_matrix), use_container_width=True)
    with graph_col:
        st.plotly_chart(relationship_chart(state.relationship_graph), use_container_width=True)

    st.plotly_chart(correlation_chart(state.correlation_history), use_container_width=True)

    if not state.divergences.empty:
        st.markdown("**Watch for divergence**")
        st.dataframe(state.divergences)
    else:
        st.caption("No major divergence alerts in the current sample.")

    if not state.lagged_relationships.empty:
        st.markdown("**Lead / lag heuristics**")
        st.dataframe(state.lagged_relationships)
        first = state.lagged_relationships.iloc[0]
        left, right = [part.strip() for part in first["relationship"].split("->")]
        st.plotly_chart(lag_chart(state.wide_frame, left, right, int(first["best_lag_periods"])), use_container_width=True)


def _render_composites(state: DashboardState, context: UIContext) -> None:
    st.subheader("Composite Indices and Narratives")
    show_helper(
        context.helper_enabled,
        "How to read this section",
        "These composites are heuristics, not objective truth. Each score is built from transparent component rules that you can inspect below.",
    )
    _render_layer_freshness(state)
    st.plotly_chart(composite_bar_chart(state.composites), use_container_width=True)
    st.markdown(f"> {state.narrative}")

    top_cards = st.columns(3)
    for idx, row in state.composites.iterrows():
        with top_cards[idx % 3]:
            st.metric(row["composite"], f"{row['score']:.1f}")
            st.caption(f"Traffic light: {traffic_light(row['score'])}")

    st.markdown("**Construction logic**")
    st.dataframe(state.composite_components.sort_values(["composite", "weight"], ascending=[True, False]))


def _render_source_health(state: DashboardState, context: UIContext) -> None:
    st.subheader("Source Health and Data Quality")
    show_helper(
        context.helper_enabled,
        "Why this matters",
        "This page makes data limitations visible. The dashboard never hides whether a signal is live, delayed, manual, or synthetic placeholder.",
    )
    counts = state.source_health["status"].value_counts().to_dict()
    summary_cols = st.columns(max(len(counts), 1))
    for idx, (status, count) in enumerate(counts.items()):
        with summary_cols[idx % len(summary_cols)]:
            st.metric(status_chip(status), int(count))

    _render_layer_freshness(state)

    source_health = state.source_health.sort_values(["layer", "series_id"])[
        ["series_id", "display_name", "layer", "status", "last_update", "fallback_proxy"]
    ].assign(
        status=lambda frame: frame["status"].map(status_chip),
        last_update=lambda frame: frame.apply(
            lambda row: format_date(row["last_update"]) if row["status"] == "Date Only Public" else format_timestamp(row["last_update"]),
            axis=1,
        ),
    ).rename(
        columns={"display_name": "market_label", "status": "data_status"}
    )
    st.dataframe(source_health)


_SECTION_RENDERERS = {
    "Executive Overview": _render_overview,
    "Paper vs Physical": _render_paper_physical,
    "U.S. Export-Barrel / Location Stress": _render_us_export,
    "Sour / Heavy Substitution": _render_sour_heavy,
    "Refined Products and Cracks": _render_products,
    "Freight, Flows, and Logistics": _render_freight,
    "Inventories and Absorption": _render_inventories,
    "Correlation and Transmission Map": _render_correlation_transmission,
    "Composite Indices and Narratives": _render_composites,
    "Source Health and Data Quality": _render_source_health,
}
