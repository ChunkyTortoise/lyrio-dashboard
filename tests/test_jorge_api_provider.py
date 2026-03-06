"""Tests for JorgeApiDataProvider — verifies Jorge API integration, fallback,
and 30s metrics cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.jorge_api_provider import JorgeApiDataProvider


def _make_contact(
    cid: str = "c1",
    first: str = "Maria",
    last: str = "Gonzalez",
    phone: str = "+19095551234",
    tags: list[str] | None = None,
    date_updated: str = "2026-03-01T12:00:00Z",
) -> dict:
    return {
        "id": cid,
        "firstName": first,
        "lastName": last,
        "phone": phone,
        "tags": tags or [],
        "dateUpdated": date_updated,
        "dateAdded": date_updated,
        "customFields": [],
    }


def _make_conv(
    cid: str = "conv1",
    contact_id: str = "c1",
    body: str = "Hello",
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
        "unreadCount": 0,
    }


def _make_provider(
    contacts: list[dict] | None = None,
    convs: list[dict] | None = None,
) -> JorgeApiDataProvider:
    client = MagicMock()
    client.get_contacts.return_value = contacts or [
        _make_contact(cid="c1", tags=["seller-qualified", "hot-seller"]),
    ]
    client.get_conversations.return_value = convs or [_make_conv(contact_id="c1")]
    return JorgeApiDataProvider(
        client,
        jorge_api_url="https://jorge-api.example.com",
        jorge_api_key="test-key-123",
    )


# ---------------------------------------------------------------------------
# get_bot_statuses — uses Jorge metrics
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_bot_statuses_uses_jorge_avg_response_time(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "system": {
            "bots": {
                "seller": {"avg_duration_ms": 1500, "success_rate": 0.92, "active_conversations": 5},
                "buyer": {"avg_duration_ms": 2000, "success_rate": 0.88},
                "lead": {"avg_duration_ms": 800, "success_rate": 0.95},
            },
        },
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    statuses = provider.get_bot_statuses()

    seller = next(s for s in statuses if s.bot_id == "seller")
    assert seller.avg_response_time_sec == 1.5
    assert seller.success_rate == 0.92
    assert seller.active_conversations == 5


@patch("backend.jorge_api_provider.requests.get")
def test_bot_statuses_fallback_on_api_failure(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("API down")

    provider = _make_provider()
    statuses = provider.get_bot_statuses()

    # Should still return statuses from parent (GHL-based)
    assert len(statuses) == 3
    bot_ids = {s.bot_id for s in statuses}
    assert bot_ids == {"seller", "buyer", "lead"}


# ---------------------------------------------------------------------------
# get_platform_health — uses Jorge /health/aggregate
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_platform_health_healthy(mock_get: MagicMock) -> None:
    def side_effect(url: str, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "/health/aggregate" in url:
            resp.json.return_value = {
                "status": "healthy",
                "checks": {"redis": True, "ghl": "ok", "claude": "healthy"},
            }
        elif "/api/dashboard/metrics" in url:
            resp.json.return_value = {
                "performance": {"error_rate_24h": 0.02},
            }
        return resp

    mock_get.side_effect = side_effect

    provider = _make_provider()
    health = provider.get_platform_health()

    assert health.overall_status == "healthy"
    assert health.error_rate_24h == 0.02
    assert health.active_bots == 3


@patch("backend.jorge_api_provider.requests.get")
def test_platform_health_degraded(mock_get: MagicMock) -> None:
    def side_effect(url: str, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "/health/aggregate" in url:
            resp.json.return_value = {
                "status": "degraded",
                "checks": {"redis": True, "ghl": "ok", "claude": "error"},
            }
        elif "/api/dashboard/metrics" in url:
            resp.json.return_value = {"performance": {"error_rate_24h": 0.15}}
        return resp

    mock_get.side_effect = side_effect

    provider = _make_provider()
    health = provider.get_platform_health()

    assert health.overall_status == "degraded"
    assert health.error_rate_24h == 0.15


@patch("backend.jorge_api_provider.requests.get")
def test_platform_health_fallback_on_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("unreachable")

    provider = _make_provider()
    health = provider.get_platform_health()

    # Falls back to parent which checks GHL reachability
    assert health.overall_status in ("healthy", "degraded")
    assert health.active_bots == 3


# ---------------------------------------------------------------------------
# get_handoff_events — maps Jorge API response
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_handoff_events_from_jorge_api(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "handoffs": [
            {
                "source_bot": "lead",
                "target_bot": "seller",
                "lead_name": "Maria Gonzalez",
                "confidence": 0.91,
                "success": True,
                "timestamp": "2026-03-01T14:30:00Z",
            },
            {
                "source_bot": "lead",
                "target_bot": "buyer",
                "lead_name": "Carlos Ruiz",
                "confidence": 0.78,
                "success": False,
                "timestamp": "2026-03-01T15:00:00Z",
            },
        ],
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    events = provider.get_handoff_events(limit=10)

    assert len(events) == 2
    assert events[0].source_bot == "lead"
    assert events[0].target_bot == "seller"
    assert events[0].lead_name == "Maria Gonzalez"
    assert events[0].confidence == 0.91
    assert events[0].success is True
    assert events[1].lead_name == "Carlos Ruiz"
    assert events[1].success is False


@patch("backend.jorge_api_provider.requests.get")
def test_handoff_events_fallback_on_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("API down")

    provider = _make_provider(
        contacts=[
            _make_contact(cid="c1", tags=["needs qualifying", "hot-seller", "seller-qualified"]),
        ],
    )
    events = provider.get_handoff_events(limit=10)

    # Falls back to parent (tag-based heuristic)
    assert len(events) >= 1
    assert events[0].source_bot == "lead"


# ---------------------------------------------------------------------------
# Cache behavior — 30s TTL
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_metrics_cache_reuses_within_30s(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "system": {
            "bots": {
                "seller": {"avg_duration_ms": 1500},
            },
        },
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()

    # First call fetches from API
    provider._fetch_jorge_metrics()
    assert mock_get.call_count == 1

    # Second call within 30s should use cache
    provider._fetch_jorge_metrics()
    assert mock_get.call_count == 1  # No new request


@patch("backend.jorge_api_provider.requests.get")
def test_metrics_cache_expires_after_30s(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"system": {"bots": {}}}
    mock_get.return_value = mock_resp

    provider = _make_provider()

    # First call
    provider._fetch_jorge_metrics()
    assert mock_get.call_count == 1

    # Simulate cache expiry by backdating timestamp
    provider._jorge_metrics_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=31)

    # Should re-fetch
    provider._fetch_jorge_metrics()
    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Constructor / headers
# ---------------------------------------------------------------------------

def test_headers_include_api_key() -> None:
    provider = _make_provider()
    assert provider._headers == {"X-Admin-Key": "test-key-123"}


def test_empty_api_key_no_headers() -> None:
    client = MagicMock()
    client.get_contacts.return_value = []
    client.get_conversations.return_value = []
    provider = JorgeApiDataProvider(client, "https://example.com", "")
    assert provider._headers == {}


def test_api_base_strips_trailing_slash() -> None:
    client = MagicMock()
    client.get_contacts.return_value = []
    client.get_conversations.return_value = []
    provider = JorgeApiDataProvider(client, "https://example.com/", "key")
    assert provider._api_base == "https://example.com"


# ---------------------------------------------------------------------------
# get_handoff_events — plain list format (bug fix)
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_handoff_events_plain_list_format(mock_get: MagicMock) -> None:
    """API returning a plain list (not dict with 'handoffs' key)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "source": "lead",
            "target": "buyer",
            "lead_name": "Ana Lopez",
            "confidence": 0.85,
            "success": True,
            "timestamp": "2026-03-01T10:00:00Z",
        },
    ]
    mock_get.return_value = mock_resp

    provider = _make_provider()
    events = provider.get_handoff_events(limit=10)

    assert len(events) == 1
    assert events[0].source_bot == "lead"
    assert events[0].target_bot == "buyer"
    assert events[0].lead_name == "Ana Lopez"


# ---------------------------------------------------------------------------
# New methods
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_get_q_stage_distribution(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "conversation_summary": {
            "by_stage": {"q0": 5, "q1": 3, "q2": 2, "qualified": 1, "q3": 0},
        },
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    dist = provider.get_q_stage_distribution()

    assert dist == {"Q0": 5, "Q1": 3, "Q2": 2, "QUALIFIED": 1}
    assert "Q3" not in dist  # 0 values excluded


@patch("backend.jorge_api_provider.requests.get")
def test_get_q_stage_distribution_api_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")
    provider = _make_provider()
    assert provider.get_q_stage_distribution() == {}


@patch("backend.jorge_api_provider.requests.get")
def test_get_conversation_transcript(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"bot_type": "lead", "stage": "q2", "conversation_history": [{"role": "user", "content": "Hi"}]},
    ]
    mock_get.return_value = mock_resp

    provider = _make_provider()
    result = provider.get_conversation_transcript("contact-123")

    assert len(result) == 1
    assert result[0]["bot_type"] == "lead"


@patch("backend.jorge_api_provider.requests.get")
def test_get_conversation_transcript_404(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    provider = _make_provider()
    assert provider.get_conversation_transcript("missing") == []


def test_get_conversation_transcript_empty_contact_id() -> None:
    provider = _make_provider()
    assert provider.get_conversation_transcript("") == []


@patch("backend.jorge_api_provider.requests.get")
def test_get_performance_metrics(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "performance": {"avg_response_ms": 450, "error_rate_24h": 0.01},
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    perf = provider.get_performance_metrics()

    assert perf["avg_response_ms"] == 450
    assert perf["error_rate_24h"] == 0.01


@patch("backend.jorge_api_provider.requests.get")
def test_get_performance_metrics_no_data(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")
    provider = _make_provider()
    assert provider.get_performance_metrics() == {}


@patch("backend.jorge_api_provider.requests.get")
def test_get_active_alerts(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"type": "error_rate", "severity": "warning", "message": "Error rate above 5%"},
    ]
    mock_get.return_value = mock_resp

    provider = _make_provider()
    alerts = provider.get_active_alerts()

    assert len(alerts) == 1
    assert alerts[0]["type"] == "error_rate"


@patch("backend.jorge_api_provider.requests.get")
def test_get_active_alerts_api_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")
    provider = _make_provider()
    assert provider.get_active_alerts() == []


def test_get_active_alerts_no_api_base() -> None:
    client = MagicMock()
    client.get_contacts.return_value = []
    client.get_conversations.return_value = []
    provider = JorgeApiDataProvider(client, "", "")
    assert provider.get_active_alerts() == []


# ---------------------------------------------------------------------------
# get_sms_metrics
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_get_sms_metrics_success(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "delivered": 142,
        "failed": 3,
        "read": 98,
        "delivery_rate": 0.979,
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    sms = provider.get_sms_metrics()

    assert sms["delivered"] == 142
    assert sms["failed"] == 3
    assert sms["read"] == 98
    assert sms["delivery_rate"] == 0.979


@patch("backend.jorge_api_provider.requests.get")
def test_get_sms_metrics_error_fallback(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")
    provider = _make_provider()
    sms = provider.get_sms_metrics()

    assert sms == {"delivered": 0, "failed": 0, "read": 0, "delivery_rate": 0.0}


def test_get_sms_metrics_no_api_base() -> None:
    client = MagicMock()
    client.get_contacts.return_value = []
    client.get_conversations.return_value = []
    provider = JorgeApiDataProvider(client, "", "")
    sms = provider.get_sms_metrics()

    assert sms == {"delivered": 0, "failed": 0, "read": 0, "delivery_rate": 0.0}


# ---------------------------------------------------------------------------
# get_cost_breakdown
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_get_cost_breakdown_success(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "per_bot": [
            {
                "bot_id": "seller",
                "input_tokens": 50000,
                "output_tokens": 12000,
                "cache_read_tokens": 8000,
                "total_cost_usd": 0.33,
                "api_calls": 45,
            },
        ],
        "total_cost_usd": 0.33,
        "appointments_booked": 4,
        "deals_closed": 1,
        "commission_pipeline": 18000.0,
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    cb = provider.get_cost_breakdown()

    assert cb.total_cost_usd == 0.33
    assert len(cb.per_bot) == 1
    assert cb.per_bot[0].bot_id == "seller"
    assert cb.per_bot[0].input_tokens == 50000
    assert cb.per_bot[0].api_calls == 45
    assert cb.roi.appointments_booked == 4
    assert cb.roi.deals_closed == 1
    assert cb.roi.total_commission_earned == 18000.0
    assert cb.roi.total_ai_cost == 0.33
    assert cb.roi.roi_multiplier == 18000.0 / 0.33


@patch("backend.jorge_api_provider.requests.get")
def test_get_cost_breakdown_fallback_on_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")

    provider = _make_provider()
    cb = provider.get_cost_breakdown()

    # Falls back to parent estimate — should still return a CostBreakdown
    assert cb.total_cost_usd >= 0
    assert cb.roi is not None


# ---------------------------------------------------------------------------
# get_recent_activity
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.get")
def test_get_recent_activity_success(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "events": [
            {
                "event_id": "evt1",
                "event_type": "lead.new",
                "source": "lead",
                "timestamp": "2026-03-01T14:00:00Z",
                "payload": {
                    "contact_name": "Ana Lopez",
                    "bot_id": "lead",
                    "description": "New lead captured",
                },
            },
            {
                "event_id": "evt2",
                "event_type": "bot.handoff",
                "source": "lead",
                "timestamp": "2026-03-01T14:05:00Z",
                "payload": {
                    "contact_name": "Carlos Ruiz",
                    "bot_id": "seller",
                    "description": "Handoff to seller",
                },
            },
        ],
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    events = provider.get_recent_activity(limit=10)

    assert len(events) == 2
    assert events[0].event_id == "evt1"
    assert events[0].lead_name == "Ana Lopez"
    assert events[0].bot_id == "lead"
    assert events[1].event_id == "evt2"
    assert events[1].lead_name == "Carlos Ruiz"


@patch("backend.jorge_api_provider.requests.get")
def test_get_recent_activity_event_type_mapping(mock_get: MagicMock) -> None:
    """Verify _TYPE_MAP correctly maps Jorge event types to Lyrio types."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "events": [
            {"event_id": "e1", "event_type": "lead.new", "timestamp": "2026-03-01T12:00:00Z", "payload": {}},
            {"event_id": "e2", "event_type": "lead.qualified", "timestamp": "2026-03-01T12:01:00Z", "payload": {}},
            {"event_id": "e3", "event_type": "bot.handoff", "timestamp": "2026-03-01T12:02:00Z", "payload": {}},
            {"event_id": "e4", "event_type": "bot.response", "timestamp": "2026-03-01T12:03:00Z", "payload": {}},
            {"event_id": "e5", "event_type": "message.inbound", "timestamp": "2026-03-01T12:04:00Z", "payload": {}},
            {"event_id": "e6", "event_type": "message.outbound", "timestamp": "2026-03-01T12:05:00Z", "payload": {}},
        ],
    }
    mock_get.return_value = mock_resp

    provider = _make_provider()
    events = provider.get_recent_activity(limit=10)

    assert events[0].event_type == "message_received"      # lead.new
    assert events[1].event_type == "temperature_change"     # lead.qualified
    assert events[2].event_type == "handoff"                # bot.handoff
    assert events[3].event_type == "message_sent"           # bot.response
    assert events[4].event_type == "message_received"       # message.inbound
    assert events[5].event_type == "message_sent"           # message.outbound


@patch("backend.jorge_api_provider.requests.get")
def test_get_recent_activity_fallback_on_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = ConnectionError("down")

    provider = _make_provider()
    events = provider.get_recent_activity(limit=5)

    # Falls back to parent (GHL-based activity feed)
    assert isinstance(events, list)


# ---------------------------------------------------------------------------
# acknowledge_alert
# ---------------------------------------------------------------------------

@patch("backend.jorge_api_provider.requests.post")
def test_acknowledge_alert_success(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    provider = _make_provider()
    result = provider.acknowledge_alert("alert-123")

    assert result is True
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "/api/alerts/alert-123/acknowledge" in call_url


@patch("backend.jorge_api_provider.requests.post")
def test_acknowledge_alert_failure_non_200(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_post.return_value = mock_resp

    provider = _make_provider()
    result = provider.acknowledge_alert("alert-999")

    assert result is False


def test_acknowledge_alert_no_api_base() -> None:
    client = MagicMock()
    client.get_contacts.return_value = []
    client.get_conversations.return_value = []
    provider = JorgeApiDataProvider(client, "", "")

    with patch("backend.jorge_api_provider.requests.post") as mock_post:
        result = provider.acknowledge_alert("alert-123")
        assert result is False
        mock_post.assert_not_called()
