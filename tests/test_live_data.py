"""Tests for LiveDataProvider — verifies diverse activity events, filtered leads,
real conversation counts, and FRS score derivation."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.live_data import LiveDataProvider, _is_junk_contact, _derive_score_and_stage


def _make_contact(
    cid: str = "c1",
    first: str = "Maria",
    last: str = "Gonzalez",
    phone: str = "+19095551234",
    tags: list[str] | None = None,
    date_updated: str = "2026-03-01T12:00:00Z",
    custom_fields: list[dict] | None = None,
) -> dict:
    return {
        "id": cid,
        "firstName": first,
        "lastName": last,
        "phone": phone,
        "tags": tags or [],
        "dateUpdated": date_updated,
        "dateAdded": date_updated,
        "customFields": custom_fields or [],
    }


def _make_conv(
    cid: str = "conv1",
    contact_id: str = "c1",
    body: str = "I'm interested",
    direction: str = "inbound",
    date: str = "2026-03-01T12:00:00Z",
) -> dict:
    return {
        "id": cid,
        "contactId": contact_id,
        "lastMessageBody": body,
        "lastMessageDirection": direction,
        "lastMessageDate": date,
        "dateUpdated": date,
        "unreadCount": 1,
    }


def _make_provider(contacts: list[dict], convs: list[dict]) -> LiveDataProvider:
    client = MagicMock()
    client.get_contacts.return_value = contacts
    client.get_conversations.return_value = convs
    return LiveDataProvider(client)


# ---------------------------------------------------------------------------
# Junk contact filter
# ---------------------------------------------------------------------------

def test_junk_filter_rejects_test_name():
    c = _make_contact(first="Test", last="User")
    assert _is_junk_contact(c)


def test_junk_filter_rejects_no_phone():
    c = _make_contact(phone="")
    assert _is_junk_contact(c)


def test_junk_filter_rejects_none_none():
    c = _make_contact(first="None", last="None")
    assert _is_junk_contact(c)


def test_junk_filter_keeps_real_contact():
    c = _make_contact(first="Maria", last="Gonzalez", phone="+19095551234")
    assert not _is_junk_contact(c)


# ---------------------------------------------------------------------------
# FRS score derivation
# ---------------------------------------------------------------------------

def test_derive_score_hot_no_raw():
    score, stage = _derive_score_and_stage(0.0, "hot", set())
    assert score >= 80
    assert stage in ("Qualified", "Qualifying")


def test_derive_score_warm_no_raw():
    score, _ = _derive_score_and_stage(0.0, "warm", set())
    assert 40 <= score < 80


def test_derive_score_cold_no_raw():
    score, _ = _derive_score_and_stage(0.0, "cold", set())
    assert score < 40


def test_derive_score_uses_raw_when_set():
    score, _ = _derive_score_and_stage(75.0, "cold", set())
    assert score == 75.0


def test_derive_stage_qualified_tag():
    _, stage = _derive_score_and_stage(0.0, "cold", {"qualified"})
    assert stage == "Qualified"


def test_derive_stage_appointment_tag():
    _, stage = _derive_score_and_stage(0.0, "warm", {"appointment"})
    assert stage == "Appointment Scheduled"


# ---------------------------------------------------------------------------
# Activity feed — diverse event types
# ---------------------------------------------------------------------------

def test_activity_feed_includes_message_received():
    contacts = [_make_contact(cid="c1", tags=["hot"])]
    convs = [_make_conv(contact_id="c1", direction="inbound")]
    provider = _make_provider(contacts, convs)
    events = provider.get_recent_activity(20)
    types = {e.event_type for e in events}
    assert "message_received" in types


def test_activity_feed_includes_message_sent():
    contacts = [_make_contact(cid="c1", tags=["hot"])]
    convs = [_make_conv(contact_id="c1", direction="outbound")]
    provider = _make_provider(contacts, convs)
    events = provider.get_recent_activity(20)
    types = {e.event_type for e in events}
    assert "message_sent" in types


def test_activity_events_have_lead_names():
    contacts = [_make_contact(cid="c1", first="Maria", last="Gonzalez", tags=["hot"])]
    convs = [_make_conv(contact_id="c1")]
    provider = _make_provider(contacts, convs)
    events = provider.get_recent_activity(20)
    for e in events:
        assert e.lead_name, f"Event {e.event_type} has no lead_name"
        assert e.lead_name != "", f"Event {e.event_type} has empty lead_name"


def test_activity_events_have_bot_ids():
    contacts = [_make_contact(cid="c1", tags=["hot-seller"])]
    convs = [_make_conv(contact_id="c1")]
    provider = _make_provider(contacts, convs)
    events = provider.get_recent_activity(20)
    for e in events:
        assert e.bot_id is not None


def test_activity_feed_sorted_reverse_chronological():
    contacts = [
        _make_contact(cid="c1", tags=["hot"], date_updated="2026-03-01T10:00:00Z"),
        _make_contact(cid="c2", tags=["warm"], date_updated="2026-03-01T11:00:00Z"),
    ]
    convs = []
    provider = _make_provider(contacts, convs)
    events = provider.get_recent_activity(20)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# Filtered leads — real conversation counts
# ---------------------------------------------------------------------------

def test_get_all_leads_filters_junk():
    contacts = [
        _make_contact(cid="c1", first="Test", last="User"),   # junk
        _make_contact(cid="c2", first="Maria", last="Gonzalez", tags=["hot"]),
    ]
    provider = _make_provider(contacts, [])
    leads = provider.get_all_leads()
    names = [l.name for l in leads]
    assert "Test User" not in names
    assert "Maria Gonzalez" in names


def test_get_all_leads_filters_no_phone():
    contacts = [
        _make_contact(cid="c1", first="No", last="Phone", phone=""),
        _make_contact(cid="c2", first="Has", last="Phone", phone="+1234567890"),
    ]
    provider = _make_provider(contacts, [])
    leads = provider.get_all_leads()
    names = [l.name for l in leads]
    assert "No Phone" not in names
    assert "Has Phone" in names


def test_get_all_leads_uses_conversation_count():
    contacts = [_make_contact(cid="c1", first="Maria", last="Gonzalez", phone="+19095551234")]
    convs = [
        _make_conv(cid="conv1", contact_id="c1"),
        _make_conv(cid="conv2", contact_id="c1"),
        _make_conv(cid="conv3", contact_id="c1"),
    ]
    provider = _make_provider(contacts, convs)
    leads = provider.get_all_leads()
    assert len(leads) == 1
    assert leads[0].conversation_count == 3


def test_get_lead_detail_uses_conversation_count():
    contacts = [_make_contact(cid="c1", first="Maria", last="Gonzalez", phone="+19095551234")]
    convs = [
        _make_conv(cid="conv1", contact_id="c1"),
        _make_conv(cid="conv2", contact_id="c1"),
    ]
    provider = _make_provider(contacts, convs)
    detail = provider.get_lead_detail("Maria")
    assert detail is not None
    assert detail.conversation_count == 2


def test_get_all_leads_derives_frs_score_for_hot():
    contacts = [_make_contact(cid="c1", first="Hot", last="Lead", phone="+1", tags=["hot"])]
    provider = _make_provider(contacts, [])
    leads = provider.get_all_leads()
    assert leads[0].frs_score >= 80


def test_get_all_leads_qualification_stage_from_tag():
    contacts = [
        _make_contact(cid="c1", first="Qual", last="Lead", phone="+1", tags=["qualified"])
    ]
    provider = _make_provider(contacts, [])
    leads = provider.get_all_leads()
    assert leads[0].qualification_stage == "Qualified"
