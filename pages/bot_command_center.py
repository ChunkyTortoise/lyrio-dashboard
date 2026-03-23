"""Bot Command Center page."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from components import (
    render_page_title, render_bot_status_card,
    render_stat, render_conversation_item,
)
from charts import area_chart


@st.cache_data(ttl=300)
def _get_bot_statuses(_provider):
    return _provider.get_bot_statuses()


@st.cache_data(ttl=300)
def _get_all_leads(_provider):
    return _provider.get_all_leads()


@st.cache_data(ttl=300)
def _get_trends(_provider, days: int):
    return _provider.get_daily_trends(days)


@st.cache_data(ttl=300)
def _get_handoffs(_provider, limit: int):
    return _provider.get_handoff_events(limit)


@st.cache_data(ttl=300)
def _get_conversations(_provider, limit: int):
    return _provider.get_recent_conversations(limit)


def render(provider) -> None:
    render_page_title("Bot command center", "Your 3 bots \u2014 live activity overview")

    # 3-column bot status cards
    statuses = _get_bot_statuses(provider)
    cols = st.columns(3)
    for col, status in zip(cols, statuses):
        with col:
            render_bot_status_card(status)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs
    tab_overview, tab_convs, tab_handoffs = st.tabs(["Overview", "Conversations", "Handoffs"])

    with tab_overview:
        # Hot leads requiring action
        hot_leads = [l for l in _get_all_leads(provider) if l.temperature == "hot"]
        if hot_leads:
            st.markdown(
                '<h3 style="font-family:\'Space Grotesk\',sans-serif;font-size:0.95rem;color:#ef4444;margin-bottom:0.5rem;">Hot leads requiring action</h3>',
                unsafe_allow_html=True,
            )
            for lead in hot_leads[:5]:
                last_contact = lead.last_contact.strftime("%b %d %H:%M")
                st.markdown(
                    f'<div class="lyrio-card" style="border-left:3px solid #ef4444;padding:0.5rem 0.75rem;margin-bottom:0.4rem;">'
                    f'<span style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;color:#FFFFFF;">{lead.name}</span>'
                    f'<span style="color:#8B949E;font-size:0.75rem;margin-left:0.5rem;">FRS {lead.frs_score:.0f} · last contact {last_contact}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("<br>", unsafe_allow_html=True)

        # 4 stat columns — above the chart so they're visible without scrolling
        total_convs = sum(s.conversations_total for s in statuses)
        avg_response = sum(s.avg_response_time_sec for s in statuses) / len(statuses)

        handoffs = _get_handoffs(provider, 50)
        success_rate = (sum(1 for h in handoffs if h.success) / len(handoffs) * 100) if handoffs else 0
        active = sum(s.active_conversations for s in statuses)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_stat(str(total_convs), "Total conversations")
        with c2:
            render_stat(f"{avg_response:.1f}s", "Avg response time")
        with c3:
            render_stat(f"{success_rate:.0f}%", "Qualification rate")
        with c4:
            render_stat(str(active), "Active conversations")

        # P95 / 5-min compliance / cache hit rate (if provider supports it)
        if hasattr(provider, 'get_performance_metrics'):
            perf = provider.get_performance_metrics()
            if perf:
                p95 = perf.get("ai_p95_ms", 0)
                compliance = perf.get("five_minute_rule_compliance", 0)
                cache_rate = perf.get("cache_hit_rate", 0)
                pc1, pc2, pc3 = st.columns(3)
                pc1.metric("P95 Response", f"{p95:.0f}ms")
                pc2.metric("5-Min Compliance", f"{compliance:.0%}")
                pc3.metric("Cache Hit Rate", f"{cache_rate:.0%}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Build dataframe for area chart — proportions from actual bot data
        trends = _get_trends(provider, 14)
        total_all = sum(s.conversations_total for s in statuses) or 1
        bot_pcts = {s.bot_id: s.conversations_total / total_all for s in statuses}
        df = pd.DataFrame([
            {
                "date": t.date,
                "seller": max(0, round(t.conversations * bot_pcts.get("seller", 0.35))),
                "buyer": max(0, round(t.conversations * bot_pcts.get("buyer", 0.22))),
                "lead": max(0, round(t.conversations * bot_pcts.get("lead", 0.43))),
            }
            for t in trends
        ])
        st.plotly_chart(area_chart(df), use_container_width=True)

        # Q-stage distribution funnel (only if provider supports it)
        if hasattr(provider, 'get_q_stage_distribution'):
            q_stages = provider.get_q_stage_distribution()
            if q_stages:
                import plotly.graph_objects as go
                stage_order = ["Q0", "Q1", "Q2", "Q3", "Q4", "QUALIFIED", "STALLED"]
                labels = [s for s in stage_order if s in q_stages]
                values = [q_stages[s] for s in labels]
                fig = go.Figure(go.Funnel(
                    y=labels,
                    x=values,
                    textinfo="value+percent initial",
                    marker_color=["#6366F1", "#8B5CF6", "#A78BFA", "#C4B5FD", "#10B981", "#22C55E", "#EF4444"][:len(labels)],
                ))
                fig.update_layout(
                    title={"text": "Qualification funnel", "font": {"family": "Space Grotesk", "size": 14, "color": "#E6EDF3"}},
                    paper_bgcolor="#0D1117",
                    plot_bgcolor="#0D1117",
                    font={"color": "#E6EDF3"},
                    margin={"t": 40, "b": 20, "l": 0, "r": 0},
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)

        # SMS Health metrics (if provider supports it)
        if hasattr(provider, 'get_sms_metrics'):
            sms = provider.get_sms_metrics()
            st.subheader("SMS Health")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Delivery Rate", f"{sms.get('delivery_rate', 0):.1%}")
            sc2.metric("Failed", str(sms.get("failed", 0)))
            sc3.metric("Read", str(sms.get("read", 0)))

        # Funnel visualization (if provider supports it)
        if hasattr(provider, 'get_funnel_data'):
            funnel = provider.get_funnel_data()
            if funnel:
                import plotly.graph_objects as go
                stage_order = ["AWARENESS", "INTEREST", "CONSIDERATION", "INTENT", "CONVERSION"]
                stages = funnel.get("stages", {})
                labels = [s for s in stage_order if s in stages]
                values = [stages[s] for s in labels]
                if labels:
                    # Compute conversion rates between adjacent stages
                    conv_text = []
                    for i, lbl in enumerate(labels):
                        if i > 0 and values[i - 1] > 0:
                            rate = values[i] / values[i - 1] * 100
                            conv_text.append(f"{values[i]} ({rate:.0f}%)")
                        else:
                            conv_text.append(str(values[i]))
                    fig = go.Figure(go.Bar(
                        y=labels,
                        x=values,
                        orientation="h",
                        text=conv_text,
                        textposition="auto",
                        marker_color=["#6366F1", "#8B5CF6", "#A78BFA", "#10B981", "#22C55E"][:len(labels)],
                    ))
                    fig.update_layout(
                        title={"text": "Lead funnel", "font": {"family": "Space Grotesk", "size": 14, "color": "#E6EDF3"}},
                        paper_bgcolor="#0D1117",
                        plot_bgcolor="#0D1117",
                        font={"color": "#E6EDF3"},
                        margin={"t": 40, "b": 20, "l": 120, "r": 20},
                        height=300,
                        xaxis={"showgrid": False},
                        yaxis={"autorange": "reversed"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

        # Stall Recovery section (if provider supports it)
        if hasattr(provider, 'get_stall_stats'):
            stall = provider.get_stall_stats()
            if stall:
                st.subheader("Stall Recovery")
                stc1, stc2 = st.columns(2)
                stc1.metric("Stalled Leads", str(stall.get("stalled_count", 0)))
                reply_rate = stall.get("reply_rate", 0)
                stc2.metric("Reply Rate", f"{reply_rate:.0%}" if isinstance(reply_rate, float) else str(reply_rate))
                by_stage = stall.get("by_stage", {})
                if by_stage:
                    st.markdown("**Stage breakdown**")
                    df_stall = pd.DataFrame(
                        [{"Stage": k, "Count": v} for k, v in by_stage.items()]
                    )
                    st.dataframe(df_stall, use_container_width=True, hide_index=True)

    with tab_convs:
        snippets = _get_conversations(provider, 20)
        if snippets:
            for snippet in snippets:
                render_conversation_item(snippet)
        else:
            st.info("No recent conversations")

    with tab_handoffs:
        handoffs = _get_handoffs(provider, 20)
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
            st.info("No handoffs in the last 7 days")
