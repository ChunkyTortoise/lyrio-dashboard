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
from components import render_sidebar_brand, render_sidebar_context, render_sidebar_status, render_alerts_badge
from backend.data_provider import DataProvider, create_data_provider

# Inject theme CSS
inject_css()


@st.cache_resource
def _live_creds() -> tuple[str, str]:
    """Returns (ghl_key, location_id) if configured in secrets, else ('', '')."""
    try:
        key = st.secrets.get("ghl", {}).get("api_key", "")
        loc = st.secrets.get("ghl", {}).get("location_id", "")
        return key, loc
    except Exception:
        return "", ""


@st.cache_resource
def _get_provider(mode: str) -> DataProvider:
    """Create and cache a provider per mode ('Demo' or 'Live')."""
    if mode == "Live":
        ghl_key, location_id = _live_creds()
        if ghl_key and location_id:
            from backend.ghl_client import GHLClient
            jorge_api_url = st.secrets.get("jorge_bot", {}).get("api_url", "")
            jorge_api_key = st.secrets.get("jorge_bot", {}).get("admin_api_key", "")
            ghl_client = GHLClient(ghl_key, location_id)
            if jorge_api_url and jorge_api_key:
                from backend.jorge_api_provider import JorgeApiDataProvider
                return JorgeApiDataProvider(ghl_client, jorge_api_url, jorge_api_key)
            from backend.live_data import LiveDataProvider
            return LiveDataProvider(ghl_client, jorge_api_url=jorge_api_url, jorge_api_key=jorge_api_key)
    return create_data_provider(mode="demo")


_ghl_key, _location_id = _live_creds()
_has_live_creds = bool(_ghl_key and _location_id)

# Session state defaults — auto-select Live when GHL credentials are configured
_DEFAULTS: dict = {
    "page": "Chat",
    "chat_messages": [],
    "cost_month": "2026-02",
    "activity_filters": {"event_types": ["All"], "bot": "All", "temperature": "All"},
    "activity_items_shown": 20,
    "api_key": "",
    "data_mode": "Live" if _has_live_creds else "Demo",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

provider = _get_provider(st.session_state["data_mode"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_brand()
    st.markdown("<br>", unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        options=["Chat", "Bots", "Costs", "Activity", "Leads", "Tone"],
        key="nav_page",
        label_visibility="collapsed",
    )

    st.markdown("---")
    render_sidebar_context(page, provider)
    st.markdown("<br>", unsafe_allow_html=True)
    render_sidebar_status(provider)
    render_alerts_badge(provider)
    st.markdown("---")
    if _has_live_creds:
        st.radio(
            "Data source",
            options=["Demo", "Live"],
            key="data_mode",
            horizontal=True,
        )
        if st.session_state["data_mode"] == "Live":
            _REFRESH_OPTIONS = {"Off": 0, "30s": 30, "1 min": 60, "5 min": 300}
            refresh_label = st.selectbox(
                "Auto-refresh",
                options=list(_REFRESH_OPTIONS.keys()),
                index=0,
                key="auto_refresh",
            )
            st.session_state["_refresh_interval"] = _REFRESH_OPTIONS[refresh_label]
    else:
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
elif page == "Leads":
    from pages.lead_browser import render
    render(provider)
elif page == "Tone":
    from pages.bot_tone import render
    render(provider)

# ── Auto-refresh (live mode only) ────────────────────────────────────────────
_refresh_seconds = st.session_state.get("_refresh_interval", 0)
if _refresh_seconds > 0:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=_refresh_seconds * 1000, key="autorefresh")
    except ImportError:
        pass  # streamlit-autorefresh not installed
