"""Bot Command Center page."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from components import (
    render_page_title, render_bot_status_card,
    render_stat, render_conversation_item,
)
from charts import area_chart


def render(provider) -> None:
    render_page_title("Bot command center", "Your 3 bots \u2014 live activity overview")

    # 3-column bot status cards
    statuses = provider.get_bot_statuses()
    cols = st.columns(3)
    for col, status in zip(cols, statuses):
        with col:
            render_bot_status_card(status)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs
    tab_overview, tab_convs, tab_handoffs = st.tabs(["Overview", "Conversations", "Handoffs"])

    with tab_overview:
        # Build dataframe for area chart
        trends = provider.get_daily_trends(14)
        df = pd.DataFrame([
            {
                "date": t.date,
                "seller": max(0, round(t.conversations * 0.35)),
                "buyer": max(0, round(t.conversations * 0.22)),
                "lead": max(0, round(t.conversations * 0.43)),
            }
            for t in trends
        ])
        st.plotly_chart(area_chart(df), use_container_width=True)

        # 4 stat columns
        total_convs = sum(s.conversations_total for s in statuses)
        avg_response = sum(s.avg_response_time_sec for s in statuses) / len(statuses)

        handoffs = provider.get_handoff_events(50)
        success_rate = (sum(1 for h in handoffs if h.success) / len(handoffs) * 100) if handoffs else 0
        active = sum(s.active_conversations for s in statuses)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_stat(str(total_convs), "Total conversations")
        with c2:
            render_stat(f"{avg_response:.1f}s", "Avg response time")
        with c3:
            render_stat(f"{success_rate:.0f}%", "Handoff success")
        with c4:
            render_stat(str(active), "Active conversations")

    with tab_convs:
        snippets = provider.get_recent_conversations(20)
        if snippets:
            for snippet in snippets:
                render_conversation_item(snippet)
        else:
            st.info("No recent conversations")

    with tab_handoffs:
        handoffs = provider.get_handoff_events(20)
        if handoffs:
            df_h = pd.DataFrame([
                {
                    "Source Bot": h.source_bot.title(),
                    "Target Bot": h.target_bot.title(),
                    "Lead": h.lead_name,
                    "Confidence": f"{h.confidence*100:.0f}%",
                    "Outcome": "Success" if h.success else "Failed",
                    "Time": h.timestamp.strftime("%b %d %H:%M"),
                }
                for h in handoffs
            ])
            st.dataframe(df_h, use_container_width=True, hide_index=True)
        else:
            st.info("No handoffs recorded")
