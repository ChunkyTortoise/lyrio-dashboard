"""Lyrio Dashboard — Jorge's AI Platform.

Run with: streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

# Page config must be the first Streamlit call
st.set_page_config(
    page_title="Lyrio — Jorge's AI Platform",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

from theme import inject_css
from components import render_sidebar_brand, render_sidebar_context, render_sidebar_status
from backend.data_provider import DataProvider, create_data_provider

# Inject theme CSS
inject_css()

# Session state defaults
_DEFAULTS: dict = {
    "page": "Chat",
    "chat_messages": [],
    "cost_month": "2026-02",
    "activity_filters": {"event_types": ["All"], "bot": "All", "temperature": "All"},
    "activity_items_shown": 20,
    "api_key": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Create data provider (demo mode — no live API calls)
@st.cache_resource
def _get_provider() -> DataProvider:
    return create_data_provider(mode="demo")

provider = _get_provider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_brand()
    st.markdown("<br>", unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        options=["Chat", "Bots", "Costs", "Activity"],
        key="nav_page",
        label_visibility="collapsed",
    )

    st.markdown("---")
    render_sidebar_context(page, provider)
    st.markdown("<br>", unsafe_allow_html=True)
    render_sidebar_status()
    st.markdown("---")
    st.markdown(
        '<p style="font-family:Inter,sans-serif;font-size:0.75rem;color:#8B949E;margin:0;">Demo mode — data is illustrative</p>',
        unsafe_allow_html=True,
    )

# ── Page routing ──────────────────────────────────────────────────────────────
if page == "Chat":
    from pages.concierge_chat import render
    render(provider)
elif page == "Bots":
    from pages.bot_command_center import render
    render(provider)
elif page == "Costs":
    from pages.cost_roi_tracker import render
    render(provider)
elif page == "Activity":
    from pages.lead_activity_feed import render
    render(provider)
