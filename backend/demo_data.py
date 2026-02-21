"""Deterministic demo data provider seeded with random.Random(20260221)."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from backend.models import (
    ActivityEvent,
    BotCostData,
    BotStatus,
    ConversationSnippet,
    CostBreakdown,
    DailyTrend,
    HandoffEvent,
    LeadDetail,
    LeadSummary,
    PlatformHealth,
    ROIMetrics,
)
from backend.seed_constants import (
    BUYER_SMS_MESSAGES,
    GHL_TAGS,
    LEAD_NAMES,
    LEAD_SMS_MESSAGES,
    NEIGHBORHOODS,
    PROPERTY_ADDRESSES,
    SELLER_SMS_MESSAGES,
    TIMELINE_OPTIONS,
    WORKFLOW_NAMES,
)

# Pricing: Anthropic Claude 3.5 Sonnet
_INPUT_COST_PER_MTOK = 3.0
_OUTPUT_COST_PER_MTOK = 15.0
_CACHE_COST_PER_MTOK = 0.30

_NOW = datetime(2026, 2, 21, 12, 0, 0)

# Cost per conversation: 800 input + 400 output + 240 cache (30% of input)
_COST_PER_CONV = (800 * _INPUT_COST_PER_MTOK + 400 * _OUTPUT_COST_PER_MTOK + 240 * _CACHE_COST_PER_MTOK) / 1_000_000


class DemoDataProvider:
    """Fully deterministic demo data backed by seeded random."""

    def __init__(self, seed: int = 20260221) -> None:
        self._rng = random.Random(seed)
        self._leads = self._generate_leads()
        self._activity = self._generate_activity()
        self._conversations = self._generate_conversations()
        self._handoffs = self._generate_handoffs()
        # Pre-compute once so get_bot_statuses() returns stable values across calls
        self._bot_response_times: dict[str, float] = {
            "seller": round(self._rng.uniform(2.0, 3.0), 1),
            "buyer": round(self._rng.uniform(3.0, 4.0), 1),
            "lead": round(self._rng.uniform(2.0, 3.0), 1),
        }

    # ------------------------------------------------------------------
    # Lead generation
    # ------------------------------------------------------------------

    def _generate_leads(self) -> list[dict]:
        leads: list[dict] = []
        # Positional assignment: [0:3] hot, [3:9] warm, [9:18] cold
        temps = ["hot"] * 3 + ["warm"] * 6 + ["cold"] * 9

        for i, name in enumerate(LEAD_NAMES):
            temp = temps[i]

            if temp == "hot":
                conv_count = self._rng.randint(4, 6)
                stage = self._rng.choice(["Appointment Scheduled", "Qualified"])
                bot = "seller"
                frs = round(self._rng.uniform(80, 98), 1)
                pcs = round(self._rng.uniform(80, 98), 1)
                timeline = self._rng.choice(["ASAP", "1-3 months"])
            elif temp == "warm":
                conv_count = self._rng.randint(2, 4)
                stage = "Qualifying"
                bot = self._rng.choice(["seller", "buyer"])
                frs = round(self._rng.uniform(45, 79), 1)
                pcs = round(self._rng.uniform(45, 79), 1)
                timeline = self._rng.choice(TIMELINE_OPTIONS[1:3])  # "1-3 months" or "3-6 months"
            else:
                conv_count = self._rng.randint(1, 2)
                stage = "Initial Contact"
                bot = "lead"
                frs = round(self._rng.uniform(10, 39), 1)
                pcs = round(self._rng.uniform(10, 39), 1)
                timeline = self._rng.choice(TIMELINE_OPTIONS[3:])  # "6-12 months" or "Just curious"

            last_digits = f"{self._rng.randint(1000, 9999)}"
            phone = f"(909) ***-{last_digits}"
            hours_ago = self._rng.randint(1, 48)

            leads.append({
                "name": name,
                "phone_masked": phone,
                "temperature": temp,
                "frs_score": frs,
                "pcs_score": pcs,
                "qualification_stage": stage,
                "property_address": PROPERTY_ADDRESSES[i],
                "city": "Rancho Cucamonga",
                "neighborhood": self._rng.choice(NEIGHBORHOODS),
                "timeline": timeline,
                "bot_assigned": bot,
                "conversation_count": conv_count,
                "last_contact": _NOW - timedelta(hours=hours_ago),
            })
        return leads

    # ------------------------------------------------------------------
    # Activity events
    # ------------------------------------------------------------------

    def _generate_activity(self) -> list[ActivityEvent]:
        event_types = [
            "message_sent", "message_received", "temperature_change",
            "handoff", "workflow_triggered", "tag_applied",
        ]
        events: list[ActivityEvent] = []

        # Generate 1-3 events per lead, aiming for ~50 total
        for lead in self._leads:
            n_events = self._rng.randint(1, 3)
            for _ in range(n_events):
                etype = self._rng.choice(event_types)
                bot = lead["bot_assigned"] if etype != "handoff" else None
                minutes_ago = self._rng.randint(5, 2880)  # last 48 hours
                ts = _NOW - timedelta(minutes=minutes_ago)

                if etype == "message_sent":
                    bot_name = {"seller": "Seller", "buyer": "Buyer", "lead": "Lead"}.get(lead["bot_assigned"], "Lead")
                    desc = f"{bot_name} Bot sent follow-up to {lead['name']}"
                elif etype == "message_received":
                    desc = f"Reply from {lead['name']}"
                elif etype == "temperature_change":
                    desc = f"Lead temperature changed to {lead['temperature'].title()}"
                elif etype == "handoff":
                    src, tgt = self._rng.sample(["seller", "buyer", "lead"], 2)
                    desc = f"Handoff from {src} bot to {tgt} bot for {lead['name']}"
                    bot = None
                elif etype == "workflow_triggered":
                    wf = self._rng.choice(WORKFLOW_NAMES)
                    desc = f"Triggered '{wf}' for {lead['name']}"
                else:
                    tag = self._rng.choice(GHL_TAGS)
                    desc = f"Tag '{tag}' applied to {lead['name']}"

                metadata: dict = {}
                if etype == "temperature_change":
                    metadata = {"temperature": lead["temperature"]}
                elif etype in ("message_sent", "message_received"):
                    metadata = {"bot": lead["bot_assigned"], "lead_temperature": lead["temperature"]}
                elif etype in ("workflow_triggered", "tag_applied", "handoff"):
                    metadata = {"lead_temperature": lead["temperature"]}

                events.append(ActivityEvent(
                    event_id=str(uuid.UUID(int=self._rng.getrandbits(128))),
                    event_type=etype,
                    lead_name=lead["name"],
                    bot_id=bot,
                    description=desc,
                    timestamp=ts,
                    metadata=metadata,
                ))

        # Pad to exactly 50 if needed
        while len(events) < 50:
            lead = self._rng.choice(self._leads)
            minutes_ago = self._rng.randint(5, 2880)
            events.append(ActivityEvent(
                event_id=str(uuid.UUID(int=self._rng.getrandbits(128))),
                event_type="message_sent",
                lead_name=lead["name"],
                bot_id=lead["bot_assigned"],
                description=f"Follow-up message to {lead['name']}",
                timestamp=_NOW - timedelta(minutes=minutes_ago),
                metadata={"bot": lead["bot_assigned"], "lead_temperature": lead["temperature"]},
            ))

        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:50]

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def _generate_conversations(self) -> list[ConversationSnippet]:
        snippets: list[ConversationSnippet] = []
        for lead in self._leads:
            msgs = {"seller": SELLER_SMS_MESSAGES, "buyer": BUYER_SMS_MESSAGES, "lead": LEAD_SMS_MESSAGES}
            preview = self._rng.choice(msgs.get(lead["bot_assigned"], LEAD_SMS_MESSAGES))
            preview = preview.replace("{name}", lead["name"]).replace("{address}", lead["property_address"]).replace("{neighborhood}", lead["neighborhood"])
            if len(preview) > 60:
                preview = preview[:57] + "..."
            minutes_ago = self._rng.randint(10, 1440)
            snippets.append(ConversationSnippet(
                lead_name=lead["name"],
                bot_id=lead["bot_assigned"],
                message_preview=preview,
                timestamp=_NOW - timedelta(minutes=minutes_ago),
                temperature=lead["temperature"],
                message_count=lead["conversation_count"] * self._rng.randint(3, 8),
            ))
        snippets.sort(key=lambda s: s.timestamp, reverse=True)
        return snippets

    # ------------------------------------------------------------------
    # Handoffs (5-8 events, lead -> seller or lead -> buyer)
    # ------------------------------------------------------------------

    def _generate_handoffs(self) -> list[HandoffEvent]:
        handoffs: list[HandoffEvent] = []
        n_handoffs = self._rng.randint(5, 8)
        for _ in range(n_handoffs):
            lead = self._rng.choice(self._leads)
            target = self._rng.choice(["seller", "buyer"])
            minutes_ago = self._rng.randint(30, 1440 * 7)  # last 7 days
            handoffs.append(HandoffEvent(
                source_bot="lead",
                target_bot=target,
                lead_name=lead["name"],
                confidence=round(self._rng.uniform(0.70, 0.95), 2),
                success=self._rng.random() <= 0.80,
                timestamp=_NOW - timedelta(minutes=minutes_ago),
            ))
        handoffs.sort(key=lambda h: h.timestamp, reverse=True)
        return handoffs

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------

    def _bot_cost(self, bot_id: str) -> tuple[int, int, int, int]:
        """Return (input_tokens, output_tokens, cache_tokens, api_calls) for a bot."""
        bot_leads = [l for l in self._leads if l["bot_assigned"] == bot_id]
        total_convs = sum(l["conversation_count"] for l in bot_leads)
        input_tok = total_convs * 800
        output_tok = total_convs * 400
        cache_tok = int(input_tok * 0.30)
        return input_tok, output_tok, cache_tok, total_convs

    # ==================================================================
    # DataProvider interface
    # ==================================================================

    def get_bot_statuses(self) -> list[BotStatus]:
        configs = [
            ("seller", "Seller Bot", 0.88, 7, 2, 2),
            ("buyer", "Buyer Bot", 0.82, 4, 1, 1),
            ("lead", "Lead Qualifier Bot", 0.91, 9, 3, 3),
        ]
        statuses: list[BotStatus] = []
        for bot_id, name, success, conv_day, qualified_today, active in configs:
            bot_leads = [l for l in self._leads if l["bot_assigned"] == bot_id]
            total_convs = sum(l["conversation_count"] for l in bot_leads)
            hot = sum(1 for l in bot_leads if l["temperature"] == "hot")
            warm = sum(1 for l in bot_leads if l["temperature"] == "warm")
            cold = sum(1 for l in bot_leads if l["temperature"] == "cold")

            statuses.append(BotStatus(
                bot_id=bot_id,
                bot_name=name,
                is_online=True,
                conversations_today=conv_day,
                conversations_total=total_convs,
                avg_response_time_sec=self._bot_response_times[bot_id],
                success_rate=success,
                leads_qualified_today=qualified_today,
                active_conversations=active,
                temp_distribution={"hot": hot, "warm": warm, "cold": cold},
            ))
        return statuses

    def get_lead_summary(self) -> LeadSummary:
        hot = sum(1 for l in self._leads if l["temperature"] == "hot")
        warm = sum(1 for l in self._leads if l["temperature"] == "warm")
        cold = sum(1 for l in self._leads if l["temperature"] == "cold")
        qualified = sum(1 for l in self._leads if l["qualification_stage"] in ("Qualified", "Appointment Scheduled"))
        recent_cutoff = _NOW - timedelta(hours=24)
        new_today = sum(1 for l in self._leads if l["last_contact"] >= recent_cutoff)
        return LeadSummary(
            hot_count=hot,
            warm_count=warm,
            cold_count=cold,
            total_count=len(self._leads),
            qualified_today=qualified,
            new_today=new_today,
        )

    def get_cost_breakdown(self) -> CostBreakdown:
        bot_costs: list[BotCostData] = []
        total_cost = 0.0
        total_calls = 0
        for bot_id in ("seller", "buyer", "lead"):
            inp, out, cache, calls = self._bot_cost(bot_id)
            cost = (inp * _INPUT_COST_PER_MTOK + out * _OUTPUT_COST_PER_MTOK + cache * _CACHE_COST_PER_MTOK) / 1_000_000
            total_cost += cost
            total_calls += calls
            bot_costs.append(BotCostData(
                bot_id=bot_id,
                input_tokens=inp,
                output_tokens=out,
                cache_read_tokens=cache,
                total_cost_usd=round(cost, 4),
                api_calls=calls,
            ))

        # ROI: 3 hot leads -> 2 appointments -> 1 deal, 3% commission on $600K
        rounded_cost = round(total_cost, 2)
        roi = ROIMetrics(
            leads_qualified=sum(1 for l in self._leads if l["qualification_stage"] in ("Qualified", "Appointment Scheduled")),
            appointments_booked=2,
            deals_closed=1,
            total_commission_earned=18000.0,
            total_ai_cost=rounded_cost,
            roi_multiplier=round(18000.0 / max(rounded_cost, 0.01), 1),
            cost_per_lead=round(rounded_cost / max(len(self._leads), 1), 4),
            cost_per_conversation=round(rounded_cost / max(total_calls, 1), 4),
        )
        return CostBreakdown(
            period_label="2026-02",
            per_bot=bot_costs,
            total_cost_usd=round(total_cost, 2),
            roi=roi,
        )

    def get_recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        return self._activity[:limit]

    def get_lead_detail(self, lead_name: str) -> LeadDetail | None:
        query = lead_name.lower()
        for lead in self._leads:
            if query in lead["name"].lower():
                return LeadDetail(
                    name=lead["name"],
                    phone_masked=lead["phone_masked"],
                    temperature=lead["temperature"],
                    frs_score=lead["frs_score"],
                    pcs_score=lead["pcs_score"],
                    qualification_stage=lead["qualification_stage"],
                    property_address=lead["property_address"],
                    city=lead["city"],
                    timeline=lead["timeline"],
                    bot_assigned=lead["bot_assigned"],
                    conversation_count=lead["conversation_count"],
                    last_contact=lead["last_contact"],
                )
        return None

    def get_platform_health(self) -> PlatformHealth:
        return PlatformHealth(
            overall_status="healthy",
            active_bots=3,
            error_rate_24h=0.02,
        )

    def get_daily_trends(self, days: int = 14) -> list[DailyTrend]:
        trends: list[DailyTrend] = []
        for d in range(days):
            day = _NOW - timedelta(days=days - 1 - d)
            # Base: seller=3, buyer=2, lead=4 = 9/day + noise
            seller_conv = 3 + self._rng.randint(-1, 2)
            buyer_conv = 2 + self._rng.randint(-1, 2)
            lead_conv = 4 + self._rng.randint(-1, 2)
            total_conv = seller_conv + buyer_conv + lead_conv
            cost = round(total_conv * _COST_PER_CONV, 4)
            # Approximate proportional distribution with noise
            hot = max(0, self._rng.randint(0, 2))
            warm = max(0, self._rng.randint(1, 4))
            cold = max(0, total_conv - hot - warm + self._rng.randint(-1, 1))
            trends.append(DailyTrend(
                date=day.replace(hour=0, minute=0, second=0),
                conversations=total_conv,
                cost_usd=cost,
                hot_leads=hot,
                warm_leads=warm,
                cold_leads=cold,
            ))
        return trends

    def get_recent_conversations(self, limit: int = 10) -> list[ConversationSnippet]:
        return self._conversations[:limit]

    def get_handoff_events(self, limit: int = 10) -> list[HandoffEvent]:
        return self._handoffs[:limit]

    def get_all_leads(self) -> list[LeadDetail]:
        return [
            LeadDetail(
                name=l["name"],
                phone_masked=l["phone_masked"],
                temperature=l["temperature"],
                frs_score=l["frs_score"],
                pcs_score=l["pcs_score"],
                qualification_stage=l["qualification_stage"],
                property_address=l["property_address"],
                city=l["city"],
                timeline=l["timeline"],
                bot_assigned=l["bot_assigned"],
                conversation_count=l["conversation_count"],
                last_contact=l["last_contact"],
            )
            for l in self._leads
        ]
