"""Lead Browser page — searchable, filterable table of all 18 leads."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from components import render_page_title, render_temperature_pill

_TEMP_EMOJI = {"hot": "🔴 Hot", "warm": "🟡 Warm", "cold": "🔵 Cold"}
_BOT_LABEL = {"seller": "Seller Bot", "buyer": "Buyer Bot", "lead": "Lead Bot"}
_BOT_COLORS = {"seller": "#6366F1", "buyer": "#10B981", "lead": "#F59E0B"}


def render(provider) -> None:
    render_page_title("Lead browser", "Search and filter all tracked leads")

    with st.spinner("Loading leads..."):
        leads = provider.get_all_leads()

    # Filter bar
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("Search by name", placeholder="e.g. Maria", key="leads_search")
    with col2:
        temp_filter = st.selectbox("Temperature", ["All", "Hot", "Warm", "Cold"], key="leads_temp")
    with col3:
        bot_filter = st.selectbox("Bot", ["All", "Seller Bot", "Buyer Bot", "Lead Bot"], key="leads_bot")

    # Apply filters
    _bot_map = {"Seller Bot": "seller", "Buyer Bot": "buyer", "Lead Bot": "lead"}
    filtered = list(leads)
    if search.strip():
        filtered = [l for l in filtered if search.strip().lower() in l.name.lower()]
    if temp_filter != "All":
        filtered = [l for l in filtered if l.temperature == temp_filter.lower()]
    if bot_filter != "All":
        filtered = [l for l in filtered if l.bot_assigned == _bot_map[bot_filter]]

    st.markdown(
        f'<p style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;margin-bottom:0.5rem;">{len(filtered)} of {len(leads)} leads</p>',
        unsafe_allow_html=True,
    )

    if not filtered:
        st.info("No leads match your filters.")
        return

    # Table
    df = pd.DataFrame([
        {
            "Name": l.name,
            "Temperature": _TEMP_EMOJI.get(l.temperature, l.temperature.title()),
            "FRS": l.frs_score,
            "Bot": _BOT_LABEL.get(l.bot_assigned, l.bot_assigned.title()),
            "Stage": l.qualification_stage,
            "Last Contact": l.last_contact.strftime("%b %d %H:%M"),
        }
        for l in filtered
    ])

    selection = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "FRS": st.column_config.NumberColumn("FRS", format="%.1f", min_value=0, max_value=100),
        },
    )

    # CSV export
    csv = df.to_csv(index=False)
    st.download_button(
        label="Export CSV",
        data=csv,
        file_name=f"leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="leads_export_csv",
    )

    # Detail panel
    st.markdown("---")
    selected_rows = selection.selection.rows if selection.selection else []
    if selected_rows:
        idx = selected_rows[0]
        if 0 <= idx < len(filtered):
            _render_detail(filtered[idx], provider)
    else:
        st.caption("Click a row above to view lead details.")


def _render_detail(detail, provider=None) -> None:
    pill = render_temperature_pill(detail.temperature)
    bot_color = _BOT_COLORS.get(detail.bot_assigned, "#6366F1")
    bot_label = _BOT_LABEL.get(detail.bot_assigned, detail.bot_assigned.title())
    last_contact = detail.last_contact.strftime("%b %d, %Y %H:%M")
    st.markdown(
        f'<div class="lyrio-card" style="margin-top:1rem;"><div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;"><span style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;font-size:1.1rem;color:#FFFFFF;">{detail.name}</span>{pill}</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-bottom:0.75rem;"><div><div style="font-size:0.7rem;color:#8B949E;">FRS Score</div><div style="font-size:1.1rem;font-weight:700;color:#FFFFFF;">{detail.frs_score:.1f}</div></div><div><div style="font-size:0.7rem;color:#8B949E;">Conversations</div><div style="font-size:1.1rem;font-weight:700;color:#FFFFFF;">{detail.conversation_count}</div></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.85rem;"><div><span style="color:#8B949E;font-size:0.7rem;">Bot — </span><span style="color:{bot_color};">{bot_label}</span></div><div><span style="color:#8B949E;font-size:0.7rem;">Stage — </span><span style="color:#E6EDF3;">{detail.qualification_stage}</span></div><div><span style="color:#8B949E;font-size:0.7rem;">Timeline — </span><span style="color:#E6EDF3;">{detail.timeline}</span></div><div><span style="color:#8B949E;font-size:0.7rem;">Last contact — </span><span style="color:#E6EDF3;">{last_contact}</span></div><div style="grid-column:span 2;"><span style="color:#8B949E;font-size:0.7rem;">Property — </span><span style="color:#E6EDF3;">{detail.property_address}, {detail.city}</span></div><div><span style="color:#8B949E;font-size:0.7rem;">Phone — </span><span class="lyrio-mono" style="color:#E6EDF3;">{detail.phone_masked}</span></div></div></div>',
        unsafe_allow_html=True,
    )

    # Conversation transcript (if provider supports it and contact_id is available)
    if provider is not None and hasattr(provider, 'get_conversation_transcript') and detail.contact_id:
        with st.spinner("Loading Q&A transcript..."):
            transcript = provider.get_conversation_transcript(detail.contact_id)
        if transcript:
            st.markdown("**Conversation Transcript**")
            for conv in transcript:
                bot_label_t = conv.get("bot_type", "unknown").title() + " Bot"
                stage = conv.get("stage", "?")
                st.markdown(f"**{bot_label_t}** -- Stage: `{stage}`")
                history = conv.get("conversation_history", [])
                if isinstance(history, list):
                    for msg in history[-6:]:
                        role = msg.get("role", "")
                        text = msg.get("content", "")
                        if isinstance(text, str) and text:
                            prefix = "Lead" if role == "user" else "Bot"
                            st.caption(f"{prefix}: {text[:200]}")
