"""Concierge Chat page — AI assistant for Jorge's real estate business."""
from __future__ import annotations

import streamlit as st

from backend.concierge import ConciergeChat
from components import render_page_title

_SUGGESTIONS = [
    "How many hot leads this week?",
    "What's my cost per qualified lead?",
    "Should I follow up with Maria Gonzalez?",
    "Show me seller bot performance",
]


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

    # Empty state — suggestion chips
    if not messages:
        st.markdown(
            '<p style="font-family:Inter,sans-serif;font-size:0.85rem;color:#8B949E;margin-bottom:1rem;">Try asking:</p>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        chips = [col1, col2, col1, col2]
        for chip_col, suggestion in zip(chips, _SUGGESTIONS):
            with chip_col:
                if st.button(suggestion, key=f"chip_{suggestion[:20]}", use_container_width=True):
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

        # Display user message
        with st.chat_message("user"):
            st.write(prompt)

        # Add to history
        messages.append({"role": "user", "content": prompt})

        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    concierge = ConciergeChat(provider, api_key=api_key)
                    # Pass history excluding the current user message
                    history = messages[:-1]
                    response = concierge.chat(prompt, history=history)
                except Exception as exc:
                    response = f"Something went wrong: {exc}"
            st.write(response)

        messages.append({"role": "assistant", "content": response})
