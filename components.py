"""Reusable Lyrio UI components — all pure functions."""
from __future__ import annotations
import streamlit as st
from datetime import datetime


_TEMP_COLORS = {"hot": "#ef4444", "warm": "#f59e0b", "cold": "#3b82f6"}
_BOT_COLORS = {"seller": "#6366F1", "buyer": "#10B981", "lead": "#F59E0B"}
_EVENT_COLORS = {
    "temperature_change": "#f59e0b",
    "handoff": "#8B5CF6",
    "workflow_triggered": "#EC4899",
    "tag_applied": "#EC4899",
    "message_sent": "#6366F1",
    "message_received": "#10B981",
}


def render_page_title(title: str, subtitle: str = "") -> None:
    subtitle_html = (
        f'<p style="font-family:Inter,sans-serif;font-size:0.9rem;color:#8B949E;margin:0.25rem 0 0;">{subtitle}</p>'
        if subtitle else ""
    )
    st.markdown(
        f'<div style="margin-bottom:1.5rem;"><h1 style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;font-size:1.5rem;color:#FFFFFF;margin:0;letter-spacing:-0.02em;">{title}</h1>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def render_stat(value: str, label: str, delta: str = "") -> None:
    delta_html = ""
    if delta:
        color = "#10b981" if not delta.startswith("-") else "#ef4444"
        delta_html = f'<div style="font-family:Inter,sans-serif;font-size:0.75rem;color:{color};margin-top:0.2rem;">{delta}</div>'
    st.markdown(
        f'<div class="lyrio-card" style="text-align:center;"><div class="lyrio-stat-value">{value}</div><div class="lyrio-stat-label">{label}</div>{delta_html}</div>',
        unsafe_allow_html=True,
    )


def render_bot_status_card(bot_status) -> None:
    dist = bot_status.temp_distribution
    total = sum(dist.values()) or 1
    hot_pct = dist.get("hot", 0) / total * 100
    warm_pct = dist.get("warm", 0) / total * 100
    cold_pct = dist.get("cold", 0) / total * 100
    response = f"{bot_status.avg_response_time_sec:.1f}s"
    success = f"{bot_status.success_rate*100:.0f}%"
    color = _BOT_COLORS.get(bot_status.bot_id, "#6366F1")
    dot_color = "#10b981" if bot_status.is_online else "#ef4444"
    status_hint = "Online" if bot_status.is_online else "Offline"
    st.markdown(
        f"""<div class="lyrio-card" style="border-left:3px solid {color};">
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">
            <span style="color:{dot_color};font-size:0.6rem;" title="{status_hint}">&#9679;</span>
            <span style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1rem;color:#FFFFFF;">{bot_status.bot_name}</span>
            {f'<span style="font-family:Inter,sans-serif;font-size:0.65rem;color:#ef4444;">Offline</span>' if not bot_status.is_online else ''}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:0.75rem;">
            <div><div style="font-size:1.25rem;font-weight:700;color:#FFFFFF;font-family:'Space Grotesk',sans-serif;">{bot_status.conversations_today}</div>
                 <div style="font-size:0.7rem;color:#8B949E;">today</div></div>
            <div><div style="font-size:1.25rem;font-weight:700;color:#FFFFFF;font-family:'Space Grotesk',sans-serif;">{response}</div>
                 <div style="font-size:0.7rem;color:#8B949E;">est. response</div></div>
        </div>
        <div style="font-size:0.7rem;color:#8B949E;margin-bottom:0.35rem;">Lead temperature</div>
        <div style="display:flex;height:4px;border-radius:2px;overflow:hidden;gap:1px;">
            <div style="flex:{hot_pct};background:#ef4444;"></div>
            <div style="flex:{warm_pct};background:#f59e0b;"></div>
            <div style="flex:{cold_pct};background:#3b82f6;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:0.4rem;">
            <span style="font-size:0.65rem;color:#ef4444;">{dist.get('hot',0)} hot</span>
            <span style="font-size:0.65rem;color:#f59e0b;">{dist.get('warm',0)} warm</span>
            <span style="font-size:0.65rem;color:#3b82f6;">{dist.get('cold',0)} cold</span>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_activity_item(event) -> None:
    # Determine border color
    if event.event_type == "temperature_change":
        temp = event.metadata.get("temperature", "cold")
        border = _TEMP_COLORS.get(temp, "#8B949E")
    elif event.event_type in ("message_sent", "message_received"):
        border = _BOT_COLORS.get(event.bot_id or "", "#6366F1")
    else:
        border = _EVENT_COLORS.get(event.event_type, "#8B949E")

    ts = event.timestamp.strftime("%b %d %H:%M")

    # Bot badge
    bot_badge = ""
    if event.bot_id:
        bot_color = _BOT_COLORS.get(event.bot_id, "#8B949E")
        bot_label = event.bot_id.title() + " Bot"
        bot_badge = (
            f'<span style="background:{bot_color};color:white;font-size:0.65rem;'
            f'padding:0.1rem 0.4rem;border-radius:3px;font-family:Inter,sans-serif;">'
            f'{bot_label}</span>'
        )

    # Temperature pill from metadata
    temp_meta = (event.metadata or {}).get("temperature", "")
    temp_pill = render_temperature_pill(temp_meta) if temp_meta else ""

    badges = " ".join(filter(None, [bot_badge, temp_pill]))

    # WARNING: ensure content is sanitized before rendering - potential XSS
    # event.description originates from the GHL API (external data) in Live mode
    st.markdown(
        f"""<div style="border-left:4px solid {border};padding:0.5rem 0.75rem;margin-bottom:0.5rem;
            background:rgba(13,17,23,0.5);border-radius:0 6px 6px 0;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:0.2rem;">
            <span style="font-family:Inter,sans-serif;font-size:0.85rem;color:#E6EDF3;">{event.description}</span>
            <span class="lyrio-mono" style="white-space:nowrap;margin-left:1rem;">{ts}</span>
        </div>
        {f'<div style="display:flex;gap:0.4rem;align-items:center;flex-wrap:wrap;margin-top:0.2rem;">{badges}</div>' if badges else ''}
        </div>""",
        unsafe_allow_html=True,
    )


def render_temperature_pill(temp: str) -> str:
    """Return HTML string for inline temperature pill."""
    color = _TEMP_COLORS.get(temp.lower(), "#8B949E")
    return (
        f'<span style="background:{color};color:white;font-size:0.7rem;'
        f'padding:0.15rem 0.5rem;border-radius:4px;font-family:Inter,sans-serif;">'
        f'{temp.title()}</span>'
    )


def render_conversation_item(snippet) -> None:
    temp_pill = render_temperature_pill(snippet.temperature)
    bot_color = _BOT_COLORS.get(snippet.bot_id, "#6366F1")
    bot_label = f"{snippet.bot_id.title()} Bot"
    ts = snippet.timestamp.strftime("%H:%M")
    preview = snippet.message_preview[:60] + ("\u2026" if len(snippet.message_preview) > 60 else "")
    st.markdown(
        f"""<div style="border-left:3px solid {bot_color};padding:0.5rem 0.75rem;
            margin-bottom:0.5rem;background:rgba(13,17,23,0.5);border-radius:0 6px 6px 0;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.25rem;">
            <span style="font-family:'Space Grotesk',sans-serif;font-weight:600;color:#FFFFFF;font-size:0.9rem;">{snippet.lead_name}</span>
            <span class="lyrio-mono">{ts}</span>
        </div>
        <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.25rem;">
            <span style="font-size:0.75rem;color:{bot_color};">{bot_label}</span>
            {temp_pill}
            <span style="font-size:0.75rem;color:#8B949E;">{snippet.message_count} msgs</span>
        </div>
        <div style="font-size:0.8rem;color:#8B949E;font-family:Inter,sans-serif;">{preview}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_alerts_badge(provider) -> None:
    """Show active alerts count in sidebar."""
    if not hasattr(provider, 'get_active_alerts'):
        return
    try:
        alerts = provider.get_active_alerts()
    except Exception:
        return
    if not alerts:
        return
    with st.sidebar:
        with st.expander(f"\U0001f514 {len(alerts)} Active Alert(s)", expanded=False):
            for alert in alerts:
                severity = alert.get("severity", "info")
                rule = alert.get("rule_name", "Unknown")
                icon = "\U0001f534" if severity == "critical" else "\U0001f7e1"
                st.write(f"{icon} **{rule}**")
                st.caption(alert.get("message", ""))
                if st.button("Acknowledge", key=f"ack_{alert.get('id', rule)}"):
                    if hasattr(provider, 'acknowledge_alert'):
                        provider.acknowledge_alert(alert.get('id'))


def render_sidebar_brand() -> None:
    st.markdown(
        """<div style="padding-bottom:1rem;border-bottom:1px solid rgba(255,255,255,0.06);">
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.8rem;
            color:#FFFFFF;letter-spacing:-0.03em;line-height:1.1;">Lyrio</div>
        <div style="font-family:Inter,sans-serif;font-size:0.85rem;color:#8B949E;margin-top:0.2rem;">
            Jorge's AI platform</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_sidebar_context(page: str, data) -> None:
    if page == "Bots":
        statuses = data.get_bot_statuses()
        online = sum(1 for s in statuses if s.is_online)
        qualified_today = sum(s.leads_qualified_today for s in statuses)
        text = f"{online} bots active \u2014 {qualified_today} leads qualified today"
    elif page == "Costs":
        cb = data.get_cost_breakdown()
        text = f"${cb.total_cost_usd:.2f} spent this month"
    elif page == "Activity":
        summary = data.get_lead_summary()
        text = f"{summary.total_count} leads tracked \u2014 {summary.hot_count} hot"
    elif page == "Leads":
        summary = data.get_lead_summary()
        text = f"{summary.total_count} leads \u2014 {summary.hot_count} hot · {summary.warm_count} warm"
    else:  # Chat
        summary = data.get_lead_summary()
        text = f"{summary.hot_count} hot leads need attention"

    st.markdown(
        f'<p style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;">{text}</p>',
        unsafe_allow_html=True,
    )


def render_sidebar_status(provider=None) -> None:
    try:
        if provider is not None:
            health = provider.get_platform_health()
            status = health.overall_status
        else:
            status = "healthy"
    except Exception:
        status = "unknown"

    if status == "healthy":
        color = "#10b981"
        label = "All systems operational"
    elif status == "degraded":
        color = "#f59e0b"
        label = "Degraded — GHL API issues"
    else:
        color = "#8B949E"
        label = "Status unknown"

    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:0.4rem;">
        <span style="color:{color};font-size:0.7rem;">&#9679;</span>
        <span style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;">{label}</span>
        </div>""",
        unsafe_allow_html=True,
    )
