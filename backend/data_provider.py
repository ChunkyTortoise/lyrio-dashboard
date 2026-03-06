"""DataProvider protocol and factory function."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.models import (
    ActionResult,
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


@runtime_checkable
class DataProvider(Protocol):
    """Runtime-checkable protocol for all dashboard data access."""

    def get_bot_statuses(self) -> list[BotStatus]: ...

    def get_lead_summary(self) -> LeadSummary: ...

    def get_cost_breakdown(self) -> CostBreakdown: ...

    def get_recent_activity(self, limit: int = 20) -> list[ActivityEvent]: ...

    def get_lead_detail(self, lead_name: str) -> LeadDetail | None: ...

    def get_platform_health(self) -> PlatformHealth: ...

    def get_daily_trends(self, days: int = 14) -> list[DailyTrend]: ...

    def get_recent_conversations(self, limit: int = 10) -> list[ConversationSnippet]: ...

    def get_handoff_events(self, limit: int = 10) -> list[HandoffEvent]: ...

    def get_all_leads(self) -> list[LeadDetail]: ...

    def send_sms(self, lead_name: str, message: str) -> ActionResult: ...

    def enroll_in_workflow(self, lead_name: str, workflow_name: str) -> ActionResult: ...

    def update_lead_temperature(self, lead_name: str, new_temperature: str) -> ActionResult: ...

    def update_lead_score(
        self,
        lead_name: str,
        frs_score: float | None = None,
    ) -> ActionResult: ...


def create_data_provider(mode: str = "demo") -> DataProvider:
    """Factory: returns DemoDataProvider or LiveDataProvider."""
    if mode == "demo":
        from backend.demo_data import DemoDataProvider
        return DemoDataProvider()
    elif mode == "live":
        from backend.live_data import LiveDataProvider
        return LiveDataProvider()
    raise ValueError(f"Unknown mode: {mode}")
