"""Bot Tone Settings page — edit Jorge's bot persona, phrases, and questions."""
from __future__ import annotations

import streamlit as st
import requests
from components import render_page_title


def _api_url() -> str:
    return st.secrets["jorge_bot"]["api_url"]


def _auth_headers() -> dict:
    return {"X-Admin-Key": st.secrets["jorge_bot"]["admin_api_key"]}


def _fetch_settings() -> dict | None:
    try:
        r = requests.get(f"{_api_url()}/admin/settings", headers=_auth_headers(), timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach bot API: {e}")
        return None


def _save_settings(bot: str, payload: dict) -> bool:
    try:
        r = requests.put(
            f"{_api_url()}/admin/settings/{bot}",
            json=payload,
            headers=_auth_headers(),
            timeout=8,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


def _reset_state(bot: str, contact_id: str) -> bool:
    try:
        r = requests.delete(
            f"{_api_url()}/admin/reset-state/{bot}/{contact_id.strip()}",
            headers=_auth_headers(),
            timeout=8,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Reset failed: {e}")
        return False


def _render_bot_section(bot: str, label: str, data: dict, q_labels: dict, q_hint: str = "") -> None:
    """Render tone settings for a single bot (seller or buyer)."""
    st.markdown(f"### {label}")
    st.caption("Changes apply immediately — no restart needed.")

    with st.expander("Persona & system prompt", expanded=True):
        st.caption(
            "This is the instruction Claude follows for every reply. "
            "Change the personality here — friendly vs. direct, formal vs. casual, etc."
        )
        system_prompt = st.text_area(
            "System prompt",
            value=data.get("system_prompt", ""),
            height=160,
            label_visibility="collapsed",
            key=f"{bot}_system_prompt",
        )
        if st.button("Save system prompt", key=f"save_{bot}_prompt"):
            if _save_settings(bot, {"system_prompt": system_prompt}):
                st.success("Saved.")

    with st.expander("Opener phrases", expanded=True):
        st.caption("One of these is randomly picked and prepended to each question. Put each phrase on its own line.")
        phrases = data.get("jorge_phrases", [])
        phrases_text = st.text_area(
            "Phrases (one per line)",
            value="\n".join(phrases),
            height=150,
            label_visibility="collapsed",
            key=f"{bot}_phrases",
        )
        if st.button("Save phrases", key=f"save_{bot}_phrases"):
            updated = [p.strip() for p in phrases_text.splitlines() if p.strip()]
            if not updated:
                st.warning("Need at least one phrase.")
            elif _save_settings(bot, {"jorge_phrases": updated}):
                st.success("Saved.")

    with st.expander("Q1–Q4 questions", expanded=True):
        if q_hint:
            st.caption(q_hint)
        questions = data.get("questions", {})
        updated_questions: dict = {}
        for key, qlabel in q_labels.items():
            updated_questions[key] = st.text_area(
                qlabel,
                value=questions.get(key, questions.get(int(key), "")),
                height=90,
                key=f"{bot}_q{key}",
            )
        if st.button("Save questions", key=f"save_{bot}_questions"):
            if _save_settings(bot, {"questions": updated_questions}):
                st.success("Saved.")

    with st.expander("Live preview — what Q1 looks like"):
        import random
        phrases_list = [
            p.strip()
            for p in st.session_state.get(f"{bot}_phrases", "\n".join(phrases)).splitlines()
            if p.strip()
        ]
        q1 = st.session_state.get(f"{bot}_q1", questions.get("1", questions.get(1, "")))
        opener = random.choice(phrases_list) if phrases_list else "Hey!"
        st.info(f"{opener}. {q1}")


def _render_lead_section(data: dict) -> None:
    """Render business-rule knobs for the Lead Bot scoring rubric."""
    st.markdown("### Lead Bot — Business Rules")
    st.caption(
        "These values feed directly into the lead scoring rubric. "
        "Changes apply immediately — no restart needed."
    )

    with st.expander("Pricing & territory", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            min_price = st.number_input(
                "Min price ($)",
                value=int(data.get("min_price", 200000)),
                step=10000,
                min_value=0,
                key="lead_min_price",
            )
        with col2:
            max_price = st.number_input(
                "Max price ($)",
                value=int(data.get("max_price", 800000)),
                step=10000,
                min_value=0,
                key="lead_max_price",
            )
        service_areas = st.text_input(
            "Service areas (comma-separated)",
            value=data.get("service_areas", "Rancho Cucamonga,Ontario,Upland,Fontana,Chino Hills"),
            key="lead_service_areas",
        )
        preferred_timeline = st.number_input(
            "Preferred timeline (days)",
            value=int(data.get("preferred_timeline", 60)),
            step=5,
            min_value=1,
            key="lead_preferred_timeline",
        )
        if st.button("Save pricing & territory", key="save_lead_pricing"):
            if _save_settings("lead", {
                "min_price": min_price,
                "max_price": max_price,
                "service_areas": service_areas,
                "preferred_timeline": preferred_timeline,
            }):
                st.success("Saved.")

    with st.expander("Commission rates", expanded=True):
        std_pct = float(data.get("standard_commission", 0.06)) * 100
        min_pct = float(data.get("minimum_commission", 0.04)) * 100
        standard_commission = st.slider(
            "Standard commission (%)",
            min_value=1.0,
            max_value=10.0,
            value=std_pct,
            step=0.5,
            key="lead_standard_commission",
        )
        minimum_commission = st.slider(
            "Minimum commission (%)",
            min_value=1.0,
            max_value=10.0,
            value=min_pct,
            step=0.5,
            key="lead_minimum_commission",
        )
        if st.button("Save commission rates", key="save_lead_commission"):
            if _save_settings("lead", {
                "standard_commission": standard_commission / 100,
                "minimum_commission": minimum_commission / 100,
            }):
                st.success("Saved.")


def render(provider) -> None:
    render_page_title("Bot tone settings", "Edit bot voices, phrases, and questions")

    settings = _fetch_settings()
    if settings is None:
        return

    # ── Seller Bot ────────────────────────────────────────────────────────────
    _render_bot_section(
        bot="seller",
        label="Seller Bot",
        data=settings.get("seller", {}),
        q_labels={
            "1": "Q1 — Condition",
            "2": "Q2 — Price expectation",
            "3": "Q3 — Motivation",
            "4": "Q4 — Offer acceptance",
        },
        q_hint=(
            "The 4 qualification questions Jorge asks every seller. "
            "`{offer_amount}` in Q4 is auto-calculated (75% of seller's stated price) — keep it."
        ),
    )

    st.markdown("---")

    # ── Buyer Bot ─────────────────────────────────────────────────────────────
    _render_bot_section(
        bot="buyer",
        label="Buyer Bot",
        data=settings.get("buyer", {}),
        q_labels={
            "1": "Q1 — What they want",
            "2": "Q2 — Pre-approved / cash?",
            "3": "Q3 — Timeline",
            "4": "Q4 — Motivation",
        },
    )

    st.markdown("---")

    # ── Lead Bot ──────────────────────────────────────────────────────────────
    _render_lead_section(settings.get("lead", {}))

    st.markdown("---")

    # ── Reset Conversation ────────────────────────────────────────────────────
    with st.expander("Reset a contact's conversation"):
        st.caption(
            "If a contact's conversation got stuck or you want the bot to start fresh, "
            "enter their GHL Contact ID below. This clears their Q&A history — the bot will "
            "greet them again from Q1 on their next message."
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            reset_contact_id = st.text_input(
                "GHL Contact ID",
                placeholder="e.g. 6Nkp3mT7xYqRwLdZ",
                label_visibility="collapsed",
                key="reset_contact_id",
            )
        with col2:
            reset_bot = st.selectbox("Bot", ["seller", "buyer"], key="reset_bot")
        if st.button("Reset conversation", key="do_reset", type="secondary"):
            if not reset_contact_id.strip():
                st.warning("Enter a Contact ID first.")
            elif _reset_state(reset_bot, reset_contact_id):
                st.success(f"Cleared {reset_bot} bot state for {reset_contact_id.strip()}.")

    st.markdown("---")
    st.caption(
        "Bot tone settings are persisted to Redis (90-day TTL) — "
        "they survive server restarts and deployments automatically."
    )
