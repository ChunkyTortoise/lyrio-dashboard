"""Concierge Chat page — AI assistant for Jorge's real estate business."""
from __future__ import annotations

import anthropic
import streamlit as st

from backend.concierge import ConciergeChat
from components import render_page_title


def _get_model() -> str:
    """Get concierge model from secrets, with default."""
    try:
        return st.secrets.get("anthropic", {}).get("model", "") or "claude-sonnet-4-20250514"
    except Exception:
        return "claude-sonnet-4-20250514"


@st.cache_resource
def _get_concierge(_provider, api_key: str, model: str) -> ConciergeChat:
    """Cache the ConciergeChat instance so the Anthropic client is created once."""
    return ConciergeChat(_provider, api_key=api_key, model=model)

_SUGGESTIONS = [
    "How many hot leads this week?",
    "What's my cost per qualified lead?",
    "Should I follow up with Maria Gonzalez?",
    "Show me seller bot performance",
]


def _fallback_response(prompt: str, provider) -> str:
    """Deterministic backup response when the LLM is unavailable."""
    text = prompt.lower()

    if "follow up with" in text:
        name = prompt.split("with", 1)[-1].strip(" ?.!")
        detail = provider.get_lead_detail(name) if name else None
        if detail is None:
            return "I couldn't find that lead in the dashboard data. Try the full name."
        if detail.temperature == "hot":
            recommendation = "Yes — prioritize this follow-up now."
        elif detail.temperature == "warm":
            recommendation = "Yes — follow up soon, ideally within 24 hours."
        else:
            recommendation = "Not urgent yet. Keep them in nurture unless new activity appears."
        return (
            f"{detail.name} is {detail.temperature.upper()} (FRS {detail.frs_score:.1f}). "
            f"Stage: {detail.qualification_stage}. Last contact: {detail.last_contact.strftime('%b %d %H:%M')}. "
            f"{recommendation}"
        )

    if "seller bot" in text and ("performance" in text or "status" in text):
        seller = next((s for s in provider.get_bot_statuses() if s.bot_id == "seller"), None)
        if seller:
            t = seller.temp_distribution
            return (
                f"Seller Bot is online with {seller.conversations_today} conversations today, "
                f"{seller.avg_response_time_sec:.1f}s average response, and {seller.success_rate * 100:.0f}% success. "
                f"Lead mix: {t.get('hot', 0)} hot, {t.get('warm', 0)} warm, {t.get('cold', 0)} cold."
            )

    if "cost" in text or "roi" in text:
        cb = provider.get_cost_breakdown()
        roi = cb.roi
        return (
            f"{cb.period_label}: total AI spend is ${cb.total_cost_usd:.2f}. "
            f"Cost per qualified lead is ${roi.cost_per_lead:.2f}, cost per conversation is ${roi.cost_per_conversation:.4f}, "
            f"and estimated ROI is {roi.roi_multiplier:.0f}x."
        )

    ls = provider.get_lead_summary()
    return (
        f"Current lead summary: {ls.hot_count} hot, {ls.warm_count} warm, {ls.cold_count} cold "
        f"({ls.total_count} total). Qualified today: {ls.qualified_today}. New today: {ls.new_today}."
    )


def _get_api_key() -> str:
    """Get API key from secrets or session state."""
    try:
        key = st.secrets.get("anthropic", {}).get("api_key", "")
        if key:
            return key
    except Exception:
        pass
    return st.session_state.get("api_key", "")


def render(provider) -> None:
    render_page_title("Concierge", "Ask about your leads, costs, or strategy")

    # API key input in sidebar if not in secrets
    api_key = _get_api_key()
    if not api_key:
        with st.sidebar:
            with st.expander("API key", expanded=True):
                entered = st.text_input(
                    "Anthropic API key",
                    type="password",
                    key="api_key_input",
                    placeholder="sk-ant-...",
                )
                if entered:
                    st.session_state["api_key"] = entered
                    api_key = entered

    # Init chat history
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    messages = st.session_state.chat_messages

    # Clear chat button (only shown when history exists)
    if messages:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()

    # Empty state — suggestion chips + daily digest
    if not messages:
        # Daily digest card
        try:
            summary = provider.get_lead_summary()
            trends = provider.get_daily_trends(1)
            today_cost = trends[0].cost_usd if trends else 0.0
            st.markdown(
                f'<div class="lyrio-card" style="margin-bottom:1rem;">'
                f'<span style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;">Today: </span>'
                f'<span style="color:#ef4444;font-weight:700;">{summary.new_today} new</span>'
                f'<span style="color:#8B949E;"> &middot; </span>'
                f'<span style="color:#10b981;font-weight:700;">{summary.hot_count} hot</span>'
                f'<span style="color:#8B949E;"> &middot; </span>'
                f'<span style="color:#E6EDF3;">{summary.qualified_today} qualified</span>'
                f'<span style="color:#8B949E;"> &middot; ${today_cost:.4f} AI spend</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

        st.markdown(
            '<p style="font-family:Inter,sans-serif;font-size:0.85rem;color:#8B949E;margin-bottom:1rem;">Try asking:</p>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        chips = [col1, col2, col1, col2]
        for chip_col, suggestion in zip(chips, _SUGGESTIONS):
            with chip_col:
                if st.button(suggestion, key=f"chip_{suggestion[:20]}", use_container_width=True):
                    # Add message to history immediately for instant feedback
                    st.session_state.chat_messages.append({"role": "user", "content": suggestion})
                    st.session_state["pending_question"] = suggestion
                    st.rerun()

    # Render chat history
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Handle pending question from chip click
    pending = st.session_state.pop("pending_question", None)

    # Chat input
    prompt = st.chat_input("Ask about your business...")
    if pending and not prompt:
        prompt = pending

    if prompt:
        if not api_key:
            st.warning("Enter your Anthropic API key in the sidebar to use the concierge.")
            return

        # Check if message was already added to history (by chip click pre-append)
        already_in_history = messages and messages[-1]["role"] == "user" and messages[-1]["content"] == prompt

        # Display user message
        if not already_in_history:
            with st.chat_message("user"):
                st.write(prompt)
            messages.append({"role": "user", "content": prompt})
        else:
            with st.chat_message("user"):
                st.write(prompt)

        # Get response
        with st.chat_message("assistant"):
            tool_indicator = st.empty()

            _WRITE_TOOLS = {"send_sms", "enroll_in_workflow", "update_lead_temperature", "update_lead_score"}

            def _on_tool_call(tool_name: str) -> None:
                if tool_name in _WRITE_TOOLS:
                    tool_indicator.markdown(
                        '<p style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;margin:0;">⚡ Executing action...</p>',
                        unsafe_allow_html=True,
                    )
                else:
                    tool_indicator.markdown(
                        '<p style="font-family:Inter,sans-serif;font-size:0.8rem;color:#8B949E;margin:0;">🔍 Checking lead data...</p>',
                        unsafe_allow_html=True,
                    )

            with st.spinner("Thinking..."):
                try:
                    concierge = _get_concierge(provider, api_key, _get_model())
                    # Pass history excluding the current user message
                    history = messages[:-1]
                    response = concierge.chat(prompt, history=history, on_tool_call=_on_tool_call)
                except anthropic.AuthenticationError:
                    response = _fallback_response(prompt, provider)
                except anthropic.PermissionDeniedError:
                    response = _fallback_response(prompt, provider)
                except anthropic.RateLimitError:
                    response = _fallback_response(prompt, provider)
                except anthropic.BadRequestError as exc:
                    msg = str(exc).lower()
                    if "credit balance" in msg or "billing" in msg:
                        response = _fallback_response(prompt, provider)
                    else:
                        response = "Request failed. Please try rephrasing your question."
                except Exception:
                    response = _fallback_response(prompt, provider)
            tool_indicator.empty()
            st.write(response)

        messages.append({"role": "assistant", "content": response})
