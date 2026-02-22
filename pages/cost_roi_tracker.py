"""Cost & ROI Tracker page."""
from __future__ import annotations
from datetime import datetime
import pandas as pd
import streamlit as st
from components import render_page_title, render_stat
from charts import bar_chart


def render(provider) -> None:
    render_page_title("Cost & ROI tracker", "AI spend vs. business results")

    # Month selector
    month = st.selectbox(
        "Month",
        options=["2026-02", "2026-01", "2025-12"],
        index=0,
        key="cost_month_select",
        label_visibility="collapsed",
    )

    cb = provider.get_cost_breakdown()
    roi = cb.roi
    try:
        period_label = datetime.strptime(cb.period_label, "%Y-%m").strftime("%b %Y")
    except ValueError:
        period_label = cb.period_label  # already human-readable (e.g. "February 2026")

    # 4 metric cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat(f"${cb.total_cost_usd:.2f}", f"Total LLM spend · {period_label}")
    with c2:
        render_stat(f"${roi.cost_per_lead:.2f}", "Cost per lead")
    with c3:
        render_stat(f"${roi.cost_per_conversation:.4f}", "Cost per conversation")
    with c4:
        render_stat(f"{roi.roi_multiplier:.0f}x", "ROI estimate")

    st.markdown("<br>", unsafe_allow_html=True)

    # Cost trend bar chart
    trends = provider.get_daily_trends(28)
    # filter to selected month
    df = pd.DataFrame([
        {"date": t.date.strftime("%b %d"), "cost_usd": t.cost_usd}
        for t in trends
        if t.date.strftime("%Y-%m") == month
    ])
    if not df.empty:
        st.plotly_chart(bar_chart(df), use_container_width=True)

    st.markdown(
        '<p class="lyrio-mono" style="text-align:right;">Pricing: $3/MTok input \u00b7 $15/MTok output \u00b7 $0.30/MTok cache</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Bot breakdown table
    st.markdown(
        '<h3 style="font-family:\'Space Grotesk\',sans-serif;font-size:1rem;color:#FFFFFF;">Spend by bot</h3>',
        unsafe_allow_html=True,
    )
    if cb.per_bot:
        df_bots = pd.DataFrame([
            {
                "Bot": b.bot_id.title() + " Bot",
                "API Calls": b.api_calls,
                "Input Tokens": f"{b.input_tokens:,}",
                "Output Tokens": f"{b.output_tokens:,}",
                "Cost": f"${b.total_cost_usd:.4f}",
            }
            for b in cb.per_bot
        ])
        st.dataframe(df_bots, use_container_width=True, hide_index=True)

    # Top contacts by cost (approximate from conversation counts)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<h3 style="font-family:\'Space Grotesk\',sans-serif;font-size:1rem;color:#FFFFFF;">Top contacts by cost</h3>',
        unsafe_allow_html=True,
    )
    convs = provider.get_recent_conversations(50)
    cost_per_conv = roi.cost_per_conversation
    if convs:
        # group by lead, sum message counts as proxy for cost
        lead_costs: dict[str, dict] = {}
        for s in convs:
            if s.lead_name not in lead_costs:
                lead_costs[s.lead_name] = {"calls": 0, "cost": 0.0}
            lead_costs[s.lead_name]["calls"] += s.message_count
            lead_costs[s.lead_name]["cost"] += s.message_count * cost_per_conv

        top5 = sorted(lead_costs.items(), key=lambda x: x[1]["cost"], reverse=True)[:5]
        df_top = pd.DataFrame([
            {"Lead": name, "Est. Cost": f"${d['cost']:.4f}", "Messages": d["calls"]}
            for name, d in top5
        ])
        st.dataframe(df_top, use_container_width=True, hide_index=True)
