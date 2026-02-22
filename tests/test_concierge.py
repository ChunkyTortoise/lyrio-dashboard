"""Tests for ConciergeChat — tool execution with mocked API."""
import json
import pytest
from unittest.mock import MagicMock, patch
from backend.concierge import ConciergeChat
from backend.demo_data import DemoDataProvider


@pytest.fixture
def provider():
    return DemoDataProvider()


@pytest.fixture
def concierge(provider):
    with patch("anthropic.Anthropic"):
        return ConciergeChat(provider, api_key="test-key")


def test_execute_tool_get_bot_status(concierge):
    result = concierge._execute_tool("get_bot_status", {})
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 3
    assert all("bot" in item for item in data)


def test_execute_tool_get_lead_summary(concierge):
    result = concierge._execute_tool("get_lead_summary", {})
    data = json.loads(result)
    assert data["hot"] == 3
    assert data["warm"] == 6
    assert data["cold"] == 9
    assert data["total"] == 18


def test_execute_tool_get_cost_breakdown(concierge):
    result = concierge._execute_tool("get_cost_breakdown", {})
    data = json.loads(result)
    assert "total_cost_usd" in data
    assert "per_bot" in data
    assert "roi" in data
    assert len(data["per_bot"]) == 3


def test_execute_tool_get_recent_activity(concierge):
    result = concierge._execute_tool("get_recent_activity", {"limit": 5})
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) <= 5


def test_execute_tool_get_lead_detail_partial_match(concierge):
    result = concierge._execute_tool("get_lead_detail", {"lead_name": "Maria"})
    data = json.loads(result)
    assert "error" not in data
    assert "Maria" in data["name"]


def test_execute_tool_get_lead_detail_not_found(concierge):
    result = concierge._execute_tool("get_lead_detail", {"lead_name": "zzz_nobody"})
    data = json.loads(result)
    assert "error" in data


def test_execute_tool_unknown_tool(concierge):
    result = concierge._execute_tool("nonexistent_tool", {})
    data = json.loads(result)
    assert "error" in data


def test_chat_returns_text_response(provider):
    """chat() extracts text from mock response."""
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "You have 3 hot leads."

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [mock_block]

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        c = ConciergeChat(provider, api_key="test-key")
        result = c.chat("How many hot leads?", history=[])

    assert result == "You have 3 hot leads."


def test_chat_max_tool_rounds_respected(provider):
    """Tool use loop stops after max_rounds=5."""
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "get_lead_summary"
    mock_tool_block.id = "tu_123"
    mock_tool_block.input = {}

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "Done."

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [mock_tool_block]

    text_response = MagicMock()
    text_response.stop_reason = "end_turn"
    text_response.content = [mock_text_block]

    # Return tool_use 6 times, then text — but loop should stop at 5
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            tool_response, tool_response, tool_response,
            tool_response, tool_response, text_response,
        ]
        mock_anthropic.return_value = mock_client

        c = ConciergeChat(provider, api_key="test-key")
        result = c.chat("Test", history=[])

    # Should have called create at most 5 times (max_rounds)
    assert mock_client.messages.create.call_count <= 5


# ------------------------------------------------------------------
# Write tool tests
# ------------------------------------------------------------------

def test_execute_tool_send_sms_success(concierge):
    result = concierge._execute_tool("send_sms", {"lead_name": "Maria", "message": "Hi!"})
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "sms_sent"
    assert "Maria" in data["contact"]


def test_execute_tool_send_sms_unknown_lead(concierge):
    result = concierge._execute_tool("send_sms", {"lead_name": "zzz_nobody", "message": "Hi!"})
    data = json.loads(result)
    assert data["success"] is False
    assert "zzz_nobody" in data["detail"]


def test_execute_tool_enroll_in_workflow(concierge):
    result = concierge._execute_tool(
        "enroll_in_workflow", {"lead_name": "Maria", "workflow_name": "Hot Seller Workflow"}
    )
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "workflow_enrolled"


def test_execute_tool_update_temperature_success(concierge):
    result = concierge._execute_tool(
        "update_lead_temperature", {"lead_name": "Maria", "new_temperature": "warm"}
    )
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "tags_updated"


def test_execute_tool_update_temperature_invalid(concierge):
    result = concierge._execute_tool(
        "update_lead_temperature", {"lead_name": "Maria", "new_temperature": "scorching"}
    )
    data = json.loads(result)
    assert data["success"] is False


def test_execute_tool_update_score_success(concierge):
    result = concierge._execute_tool(
        "update_lead_score", {"lead_name": "Maria", "frs_score": 75.0}
    )
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "score_updated"


def test_execute_tool_update_score_out_of_range(concierge):
    result = concierge._execute_tool(
        "update_lead_score", {"lead_name": "Maria", "frs_score": 110.0}
    )
    data = json.loads(result)
    assert data["success"] is False
