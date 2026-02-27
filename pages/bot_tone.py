"""Bot Tone Settings page — edit Jorge's bot persona, phrases, and questions."""
from __future__ import annotations

import streamlit as st
import requests
from components import render_page_title

BOT_API = "https://jorge-realty-ai-xxdf.onrender.com"


def _fetch_settings() -> dict | None:
    try:
        r = requests.get(f"{BOT_API}/admin/settings", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach bot API: {e}")
        return None


def _save_settings(bot: str, payload: dict) -> bool:
    try:
        r = requests.put(f"{BOT_API}/admin/settings/{bot}", json=payload, timeout=8)
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


def render(provider) -> None:
    render_page_title("Bot tone settings", "Edit the seller bot's voice, phrases, and questions")

    settings = _fetch_settings()
    if settings is None:
        return

    seller = settings.get("seller", {})

    st.markdown("### Seller Bot")
    st.caption("Changes apply immediately — no restart needed.")

    # ── System Prompt ─────────────────────────────────────────────────────────
    with st.expander("Persona & system prompt", expanded=True):
        st.caption(
            "This is the instruction Claude follows for every reply. "
            "Change the personality here — friendly vs. direct, formal vs. casual, etc."
        )
        system_prompt = st.text_area(
            "System prompt",
            value=seller.get("system_prompt", ""),
            height=160,
            label_visibility="collapsed",
            key="seller_system_prompt",
        )
        if st.button("Save system prompt", key="save_prompt"):
            if _save_settings("seller", {"system_prompt": system_prompt}):
                st.success("Saved.")

    # ── Opener Phrases ────────────────────────────────────────────────────────
    with st.expander("Opener phrases", expanded=True):
        st.caption(
            "One of these is randomly picked and prepended to each question. "
            "Put each phrase on its own line."
        )
        phrases = seller.get("jorge_phrases", [])
        phrases_text = st.text_area(
            "Phrases (one per line)",
            value="\n".join(phrases),
            height=180,
            label_visibility="collapsed",
            key="seller_phrases",
        )
        if st.button("Save phrases", key="save_phrases"):
            updated = [p.strip() for p in phrases_text.splitlines() if p.strip()]
            if not updated:
                st.warning("Need at least one phrase.")
            elif _save_settings("seller", {"jorge_phrases": updated}):
                st.success("Saved.")

    # ── Q1–Q4 Questions ───────────────────────────────────────────────────────
    with st.expander("Q1–Q4 questions", expanded=True):
        st.caption(
            "The 4 qualification questions Jorge asks every seller. "
            "`{offer_amount}` in Q4 is auto-calculated (75% of seller's stated price) — keep it."
        )
        questions = seller.get("questions", {})
        q_labels = {
            "1": "Q1 — Condition",
            "2": "Q2 — Price expectation",
            "3": "Q3 — Motivation",
            "4": "Q4 — Offer acceptance",
        }
        updated_questions: dict = {}
        for key, label in q_labels.items():
            updated_questions[key] = st.text_area(
                label,
                value=questions.get(key, questions.get(int(key), "")),
                height=100,
                key=f"seller_q{key}",
            )

        if st.button("Save questions", key="save_questions"):
            if _save_settings("seller", {"questions": updated_questions}):
                st.success("Saved.")

    # ── Live preview ──────────────────────────────────────────────────────────
    with st.expander("Live preview — what Q1 looks like"):
        import random
        phrases_list = [p.strip() for p in st.session_state.get("seller_phrases", "\n".join(phrases)).splitlines() if p.strip()]
        q1 = st.session_state.get("seller_q1", questions.get("1", questions.get(1, "")))
        opener = random.choice(phrases_list) if phrases_list else "Hey!"
        st.info(f"{opener}. {q1}")

    st.markdown("---")
    st.caption(
        "⚠️ Settings are stored in bot memory — they reset if the bot restarts (rare). "
        "Re-save after any deployment."
    )
