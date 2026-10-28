from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import streamlit as st

from oil360_dashboard.config import AppConfig
from oil360_dashboard.pipeline import DashboardPipeline
from oil360_dashboard.ui.sections import SECTION_OPTIONS, UIContext, render_dashboard


def _persist_uploaded_files(uploaded_files: list, config: AppConfig) -> None:
    for uploaded in uploaded_files or []:
        target = config.manual_dir / uploaded.name
        target.write_bytes(uploaded.getbuffer())


def main() -> None:
    st.set_page_config(
        page_title="Oil 360 Dashboard",
        page_icon="O",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    config = AppConfig.from_env(PROJECT_ROOT)
    config.ensure_runtime_dirs()

    st.sidebar.title("Oil 360")
    st.sidebar.caption("Analyst-first Streamlit dashboard with explicit data-quality states.")

    mode = st.sidebar.radio("Interface", ["Analyst", "Beginner"], horizontal=True)
    helper_enabled = st.sidebar.toggle("Helper / tutorial", value=True)
    timeframe = st.sidebar.selectbox("View horizon", ["Intraday", "Daily", "Weekly"], index=1)
    section = st.sidebar.selectbox("Section", SECTION_OPTIONS, index=0)

    uploaded_files = st.sidebar.file_uploader(
        "Upload CSV feeds",
        type=["csv"],
        accept_multiple_files=True,
        help="Uploads are persisted into the manual import folder and become part of the local history.",
    )
    if uploaded_files:
        _persist_uploaded_files(uploaded_files, config)
        st.sidebar.success(f"Saved {len(uploaded_files)} file(s) into {config.manual_dir}.")

    st.sidebar.caption(f"Manual CSV folder: `{config.manual_dir}`")
    st.sidebar.caption(f"Public inventory folder: `{config.public_dir}`")
    st.sidebar.caption(f"Premium pricing folder: `{config.premium_dir}`")
    st.sidebar.caption(f"Freight / AIS folder: `{config.freight_dir}`")

    pipeline = DashboardPipeline(config)
    state = pipeline.build_dashboard_state(timeframe=timeframe)

    context = UIContext(mode=mode, helper_enabled=helper_enabled, timeframe=timeframe)
    render_dashboard(state, context, section)


if __name__ == "__main__":
    main()
