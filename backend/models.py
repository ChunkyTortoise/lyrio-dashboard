"""Lyrio Dashboard — data models. All dataclasses are frozen for hashability."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BotStatus:
    bot_id: str                    # "seller" | "buyer" | "lead"
    bot_name: str
    is_online: bool
    conversations_today: int
    conversations_total: int
    avg_response_time_sec: float
    success_rate: float
    leads_qualified_today: int
    active_conversations: int
    temp_distribution: dict        # {"hot": int, "warm": int, "cold": int}


@dataclass(frozen=True)
class LeadSummary:
    hot_count: int
    warm_count: int
    cold_count: int
    total_count: int
    qualified_today: int
    new_today: int


@dataclass(frozen=True)
class LeadDetail:
    name: str
    phone_masked: str              # "(909) ***-1234"
    temperature: str
    frs_score: float               # 0-100
    qualification_stage: str
    property_address: str
    city: str
    timeline: str
    bot_assigned: str
    conversation_count: int
    last_contact: datetime
    contact_id: str = ""


@dataclass(frozen=True)
class ActivityEvent:
    event_id: str
    event_type: str                # message_sent|message_received|temperature_change|handoff|workflow_triggered|tag_applied
    lead_name: str
    bot_id: str | None
    description: str
    timestamp: datetime
    metadata: dict


@dataclass(frozen=True)
class BotCostData:
    bot_id: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    total_cost_usd: float
    api_calls: int


@dataclass(frozen=True)
class ROIMetrics:
    leads_qualified: int
    appointments_booked: int
    deals_closed: int
    total_commission_earned: float
    total_ai_cost: float
    roi_multiplier: float
    cost_per_lead: float
    cost_per_conversation: float


@dataclass(frozen=True)
class CostBreakdown:
    period_label: str
    per_bot: list[BotCostData]
    total_cost_usd: float
    roi: ROIMetrics


@dataclass(frozen=True)
class DailyTrend:
    date: datetime
    conversations: int
    cost_usd: float
    hot_leads: int
    warm_leads: int
    cold_leads: int


@dataclass(frozen=True)
class ConversationSnippet:
    lead_name: str
    bot_id: str
    message_preview: str
    timestamp: datetime
    temperature: str
    message_count: int


@dataclass(frozen=True)
class HandoffEvent:
    source_bot: str
    target_bot: str
    lead_name: str
    confidence: float
    success: bool
    timestamp: datetime


@dataclass(frozen=True)
class PlatformHealth:
    overall_status: str            # "healthy" | "degraded"
    active_bots: int
    error_rate_24h: float


@dataclass(frozen=True)
class ActionResult:
    success: bool
    action: str          # "sms_sent" | "workflow_enrolled" | "tags_updated" | "score_updated"
    contact_name: str
    detail: str          # Human-readable summary
