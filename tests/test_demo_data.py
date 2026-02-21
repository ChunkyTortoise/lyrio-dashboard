"""Tests for DemoDataProvider — consistency and determinism checks."""
import pytest
from datetime import datetime
from backend.demo_data import DemoDataProvider


@pytest.fixture
def provider():
    return DemoDataProvider()


def test_lead_counts_add_up(provider):
    ls = provider.get_lead_summary()
    assert ls.hot_count + ls.warm_count + ls.cold_count == ls.total_count


def test_lead_distribution_matches_spec(provider):
    ls = provider.get_lead_summary()
    assert ls.hot_count == 3
    assert ls.warm_count == 6
    assert ls.cold_count == 9
    assert ls.total_count == 18


def test_bot_statuses_returns_three(provider):
    statuses = provider.get_bot_statuses()
    assert len(statuses) == 3
    bot_ids = {s.bot_id for s in statuses}
    assert bot_ids == {"seller", "buyer", "lead"}


def test_all_bots_online(provider):
    for status in provider.get_bot_statuses():
        assert status.is_online is True


def test_cost_adds_up(provider):
    cb = provider.get_cost_breakdown()
    per_bot_total = sum(b.total_cost_usd for b in cb.per_bot)
    assert abs(per_bot_total - cb.total_cost_usd) < 0.01


def test_daily_trends_14_days(provider):
    trends = provider.get_daily_trends(14)
    assert len(trends) == 14


def test_daily_trends_dates_sequential(provider):
    trends = provider.get_daily_trends(14)
    dates = [t.date for t in trends]
    for i in range(1, len(dates)):
        assert dates[i] > dates[i - 1]


def test_roi_math_is_sane(provider):
    cb = provider.get_cost_breakdown()
    roi = cb.roi
    assert roi.roi_multiplier > 0
    if roi.total_ai_cost > 0 and roi.total_commission_earned > 0:
        expected = roi.total_commission_earned / roi.total_ai_cost
        # Use relative tolerance — multiplier can be 40K+ so absolute diff is large
        assert abs(expected - roi.roi_multiplier) / expected < 0.02


def test_demo_data_is_deterministic(provider):
    provider2 = DemoDataProvider()
    ls1 = provider.get_lead_summary()
    ls2 = provider2.get_lead_summary()
    assert ls1.hot_count == ls2.hot_count
    assert ls1.total_count == ls2.total_count


def test_get_lead_detail_found(provider):
    result = provider.get_lead_detail("Maria")
    assert result is not None
    assert "Maria" in result.name


def test_get_lead_detail_case_insensitive(provider):
    result = provider.get_lead_detail("maria")
    assert result is not None


def test_get_lead_detail_not_found(provider):
    result = provider.get_lead_detail("zzz_nonexistent_zzz")
    assert result is None


def test_recent_conversations_limit(provider):
    convs = provider.get_recent_conversations(5)
    assert len(convs) <= 5


def test_handoff_events_have_valid_bots(provider):
    handoffs = provider.get_handoff_events(50)
    valid = {"seller", "buyer", "lead"}
    for h in handoffs:
        assert h.source_bot in valid
        assert h.target_bot in valid


def test_activity_events_reverse_chronological(provider):
    events = provider.get_recent_activity(20)
    timestamps = [e.timestamp for e in events]
    for i in range(1, len(timestamps)):
        assert timestamps[i] <= timestamps[i - 1]


def test_platform_health_is_healthy(provider):
    health = provider.get_platform_health()
    assert health.overall_status == "healthy"
    assert health.active_bots == 3
