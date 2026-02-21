"""Lead Activity Feed page."""
from __future__ import annotations
import streamlit as st
from components import render_page_title, render_activity_item


def _save_activity_filters() -> None:
    st.session_state["activity_filters"] = {
        "event_types": st.session_state.get("feed_event_types", ["All"]),
        "bot": st.session_state.get("feed_bot", "All"),
        "temperature": st.session_state.get("feed_temperature", "All"),
    }


def render(provider) -> None:
    render_page_title("Lead activity feed", "Real-time bot interactions and qualification events")

    # Restore persisted filter values
    _saved = st.session_state.get("activity_filters", {})

    # Filter bar
    col1, col2, col3 = st.columns(3)
    with col1:
        event_types = st.multiselect(
            "Event type",
            options=["All", "message_sent", "message_received", "temperature_change",
                     "handoff", "workflow_triggered", "tag_applied"],
            default=_saved.get("event_types", ["All"]),
            key="feed_event_types",
            on_change=_save_activity_filters,
        )
    with col2:
        bot_filter = st.selectbox(
            "Bot",
            options=["All", "Seller Bot", "Buyer Bot", "Lead Bot"],
            index=["All", "Seller Bot", "Buyer Bot", "Lead Bot"].index(_saved.get("bot", "All")),
            key="feed_bot",
            on_change=_save_activity_filters,
        )
    with col3:
        temp_filter = st.selectbox(
            "Temperature",
            options=["All", "Hot", "Warm", "Cold"],
            index=["All", "Hot", "Warm", "Cold"].index(_saved.get("temperature", "All")),
            key="feed_temperature",
            on_change=_save_activity_filters,
        )

    # Fetch enough to have buffer after filtering
    shown = st.session_state.get("activity_items_shown", 20)
    events = provider.get_recent_activity(limit=shown + 20)

    # Apply filters
    filtered = []
    bot_map = {"Seller Bot": "seller", "Buyer Bot": "buyer", "Lead Bot": "lead"}

    for event in events:
        # Event type filter
        if "All" not in event_types and event.event_type not in event_types:
            continue
        # Bot filter
        if bot_filter != "All":
            if event.bot_id != bot_map.get(bot_filter):
                continue
        # Temperature filter
        if temp_filter != "All":
            event_temp = event.metadata.get("temperature", "")
            if event_temp.lower() != temp_filter.lower():
                # For non-temp-change events, check lead temperature via metadata
                lead_temp = event.metadata.get("lead_temperature", "")
                if lead_temp.lower() != temp_filter.lower():
                    continue
        filtered.append(event)

    # Show count
    st.markdown(
        f'<p style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;margin-bottom:0.5rem;">Showing {min(shown, len(filtered))} of {len(filtered)} events</p>',
        unsafe_allow_html=True,
    )

    # Render feed
    display = filtered[:shown]
    if display:
        for event in display:
            render_activity_item(event)
    else:
        st.info("No events match your filters")

    # Load more
    if len(filtered) > shown:
        if st.button("Load more"):
            st.session_state.activity_items_shown = shown + 20
            st.rerun()
