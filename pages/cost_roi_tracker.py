"""Cost & ROI Tracker page."""
from __future__ import annotations
from datetime import datetime
import pandas as pd
import streamlit as st
from components import render_page_title, render_stat
from charts import bar_chart


def render(provider) -> None:
    render_page_title("Cost & ROI tracker", "AI spend vs. business results")

    # Fetch trend data (last 28 days) and derive available months
    trends = provider.get_daily_trends(28)
    available_months = sorted(
        {t.date.strftime("%Y-%m") for t in trends},
        reverse=True,
    )

    # Month selector — dynamic from actual data
    month = st.selectbox(
        "Month",
        options=available_months,
        index=0,
        key="cost_month_select",
        label_visibility="collapsed",
    )

    # Filter trends to selected month
    month_trends = [t for t in trends if t.date.strftime("%Y-%m") == month]
    month_cost = sum(t.cost_usd for t in month_trends)
    month_conversations = sum(t.conversations for t in month_trends)
    month_leads = sum(t.hot_leads + t.warm_leads + t.cold_leads for t in month_trends)

    cost_per_lead = month_cost / max(month_leads, 1)
    cost_per_conv = month_cost / max(month_conversations, 1)

    # ROI: use overall ROI multiplier scaled by month cost
    cb = provider.get_cost_breakdown()
    roi = cb.roi
    roi_multiplier = roi.total_commission_earned / max(month_cost, 0.01)

    try:
        period_label = datetime.strptime(month, "%Y-%m").strftime("%b %Y")
    except ValueError:
        period_label = month

    # 4 metric cards — filtered to selected month
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat(f"${month_cost:.2f}", f"Total LLM spend \u00b7 {period_label}")
    with c2:
        render_stat(f"${cost_per_lead:.2f}", "Cost per lead")
    with c3:
        render_stat(f"${cost_per_conv:.4f}", "Cost per conversation")
    with c4:
        render_stat(f"{roi_multiplier:.0f}x", "ROI (est.)")

    st.markdown(
        f'<p style="font-family:Inter,sans-serif;font-size:0.75rem;color:#8B949E;margin:0.25rem 0 0.75rem;">'
        f'Total commission: ${roi.total_commission_earned:,.0f} &middot; '
        f'Total AI spend: ${roi.total_ai_cost:.2f} &middot; '
        f'Costs estimated from token usage. Commission assumes 3% on $600K avg.</p>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Cost trend bar chart
    df = pd.DataFrame([
        {"date": t.date.strftime("%b %d"), "cost_usd": t.cost_usd}
        for t in month_trends
    ])
    if not df.empty:
        st.plotly_chart(bar_chart(df), use_container_width=True)
    else:
        st.info(f"No cost data available for {period_label}.")

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
        total_bot_cost = sum(b.total_cost_usd for b in cb.per_bot) or 1.0
        df_bots = pd.DataFrame([
            {
                "Bot": b.bot_id.title() + " Bot",
                "API Calls": b.api_calls,
                "Input Tokens": f"{b.input_tokens:,}",
                "Output Tokens": f"{b.output_tokens:,}",
                "Cost": f"${b.total_cost_usd:.4f}",
                "% of Total": f"{b.total_cost_usd / total_bot_cost * 100:.1f}%",
            }
            for b in cb.per_bot
        ])
        st.dataframe(df_bots, use_container_width=True, hide_index=True)
    else:
        st.info("No bot cost data available.")

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
    else:
        st.info("No conversation data available.")
