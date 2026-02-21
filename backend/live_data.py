"""Live data provider — placeholder until Render admin API is wired."""
from __future__ import annotations

from backend.models import (
    ActivityEvent,
    BotStatus,
    ConversationSnippet,
    CostBreakdown,
    DailyTrend,
    HandoffEvent,
    LeadDetail,
    LeadSummary,
    PlatformHealth,
)

_MSG = "Live mode not yet implemented. Set RENDER_ADMIN_KEY to enable."


class LiveDataProvider:
    """Reads from jorge-realty-ai Render service. Set RENDER_ADMIN_KEY env var to enable."""

    def get_bot_statuses(self) -> list[BotStatus]:
        raise NotImplementedError(_MSG)

    def get_lead_summary(self) -> LeadSummary:
        raise NotImplementedError(_MSG)

    def get_cost_breakdown(self) -> CostBreakdown:
        raise NotImplementedError(_MSG)

    def get_recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        raise NotImplementedError(_MSG)

    def get_lead_detail(self, lead_name: str) -> LeadDetail | None:
        raise NotImplementedError(_MSG)

    def get_platform_health(self) -> PlatformHealth:
        raise NotImplementedError(_MSG)

    def get_daily_trends(self, days: int = 14) -> list[DailyTrend]:
        raise NotImplementedError(_MSG)

    def get_recent_conversations(self, limit: int = 10) -> list[ConversationSnippet]:
        raise NotImplementedError(_MSG)

    def get_handoff_events(self, limit: int = 10) -> list[HandoffEvent]:
        raise NotImplementedError(_MSG)
