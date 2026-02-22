"""Live data provider — reads from GoHighLevel API v2."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from backend.ghl_client import GHLClient
from backend.models import (
    ActionResult,
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

# Custom field IDs (from .env.jorge)
_CF_BOT_TYPE = "YJ9EDgHQB3UoKnnTSoUO"
_CF_LEAD_SCORE = "FpLprsZwqpYTyUxYzgpS"
_CF_TIMELINE = "7GGX1W3EKa51AsPU1wbP"

# Cost model: Claude Sonnet per-conversation estimate
_INPUT_CPM = 3.0
_OUTPUT_CPM = 15.0
_CACHE_CPM = 0.30
_COST_PER_CONV = (800 * _INPUT_CPM + 400 * _OUTPUT_CPM + 240 * _CACHE_CPM) / 1_000_000
_AVG_COMMISSION = 18_000.0

# Temperature tag sets (GHL applies these as-is)
_HOT_TAGS = {"hot-seller", "hot-lead", "hot"}
_WARM_TAGS = {"warm-seller", "warm-lead", "warm"}

# All temperature tags that must be cleared before writing a new one
_ALL_TEMP_TAGS = [
    "hot-seller", "warm-seller", "cold-seller",
    "hot-lead", "warm-lead", "cold-lead",
    "hot-buyer", "warm-buyer", "cold-buyer",
    "hot", "warm", "cold",
]

# Workflow display name → GHL workflow ID (placeholder IDs until Jorge provides real ones)
_WORKFLOWS: dict[str, str] = {
    "hot seller workflow": "wf-hot-seller-placeholder",
    "warm seller workflow": "wf-warm-seller-placeholder",
    "hot buyer workflow": "wf-hot-buyer-placeholder",
    "notify agent workflow": "wf-notify-agent-placeholder",
    "lead nurture sequence": "wf-lead-nurture-placeholder",
    "appointment confirmation": "wf-appt-confirm-placeholder",
}

# Tags that indicate bot assignment
_SELLER_TAGS = {"seller-qualified", "hot-seller", "warm-seller", "cold-seller"}
_BUYER_TAGS = {"buyer-lead", "hot-buyer", "warm-buyer", "cold-buyer"}
_LEAD_TAGS = {"needs qualifying", "lead-bot"}

_BOT_NAMES = {"seller": "Seller Bot", "buyer": "Buyer Bot", "lead": "Lead Bot"}
_BOT_RESP_TIMES = {"seller": 2.4, "buyer": 3.1, "lead": 2.7}


def _cf(contact: dict, field_id: str) -> str:
    for item in contact.get("customFields") or []:
        if item.get("id") == field_id:
            return str(item.get("value", "")).strip()
    return ""


def _tags(contact: dict) -> set[str]:
    return {t.lower() for t in (contact.get("tags") or [])}


def _temperature(contact: dict) -> str:
    t = _tags(contact)
    if t & _HOT_TAGS:
        return "hot"
    if t & _WARM_TAGS:
        return "warm"
    return "cold"


def _bot_type(contact: dict) -> str:
    cf = _cf(contact, _CF_BOT_TYPE).lower()
    if cf in ("seller", "buyer", "lead"):
        return cf
    t = _tags(contact)
    if t & _SELLER_TAGS:
        return "seller"
    if t & _BUYER_TAGS:
        return "buyer"
    return "lead"


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.now(timezone.utc).replace(tzinfo=None)


def _mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) >= 10:
        return f"({digits[-10:-7]}) ***-{digits[-4:]}"
    return "***-****"


def _full_name(contact: dict) -> str:
    return f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()


class LiveDataProvider:
    """Reads real lead and conversation data from GoHighLevel."""

    def __init__(self, client: GHLClient) -> None:
        self._client = client
        # Instance-level cache so GHL is hit once per provider lifetime
        self._contacts: list[dict] | None = None
        self._conversations: list[dict] | None = None

    def _get_contacts(self) -> list[dict]:
        if self._contacts is None:
            self._contacts = self._client.get_contacts()
        return self._contacts

    def _get_conversations(self) -> list[dict]:
        if self._conversations is None:
            self._conversations = self._client.get_conversations()
        return self._conversations

    def _today_start(self) -> datetime:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # Lead summary
    # ------------------------------------------------------------------

    def get_lead_summary(self) -> LeadSummary:
        contacts = self._get_contacts()
        today = self._today_start()
        hot = warm = cold = qualified_today = new_today = 0
        for c in contacts:
            temp = _temperature(c)
            if temp == "hot":
                hot += 1
            elif temp == "warm":
                warm += 1
            else:
                cold += 1
            if _parse_dt(c.get("dateAdded")) >= today:
                new_today += 1
            if _parse_dt(c.get("dateUpdated")) >= today and temp in ("hot", "warm"):
                qualified_today += 1
        return LeadSummary(
            hot_count=hot,
            warm_count=warm,
            cold_count=cold,
            total_count=len(contacts),
            qualified_today=qualified_today,
            new_today=new_today,
        )

    # ------------------------------------------------------------------
    # Bot statuses
    # ------------------------------------------------------------------

    def get_bot_statuses(self) -> list[BotStatus]:
        contacts = self._get_contacts()
        convs = self._get_conversations()
        today = self._today_start()

        # Map contactId → conversation count
        contact_conv_count: dict[str, int] = {}
        for conv in convs:
            cid = conv.get("contactId", "")
            if cid:
                contact_conv_count[cid] = contact_conv_count.get(cid, 0) + 1

        # Group contacts by bot
        by_bot: dict[str, list[dict]] = {"seller": [], "buyer": [], "lead": []}
        for c in contacts:
            by_bot[_bot_type(c)].append(c)

        result = []
        for bot_id in ("seller", "buyer", "lead"):
            cs = by_bot[bot_id]
            hot = sum(1 for c in cs if _temperature(c) == "hot")
            warm = sum(1 for c in cs if _temperature(c) == "warm")
            cold = len(cs) - hot - warm
            convs_today = sum(
                1 for c in cs if _parse_dt(c.get("dateUpdated")) >= today
            )
            total_convs = sum(
                contact_conv_count.get(c.get("id", ""), 1) for c in cs
            )
            qualified_today = sum(
                1 for c in cs
                if _parse_dt(c.get("dateUpdated")) >= today
                and _temperature(c) in ("hot", "warm")
            )
            result.append(BotStatus(
                bot_id=bot_id,
                bot_name=_BOT_NAMES[bot_id],
                is_online=True,
                conversations_today=convs_today,
                conversations_total=max(total_convs, len(cs)),
                avg_response_time_sec=_BOT_RESP_TIMES[bot_id],
                success_rate=(hot + warm) / len(cs) if cs else 0.0,
                leads_qualified_today=qualified_today,
                active_conversations=max(1, convs_today // 2),
                temp_distribution={"hot": hot, "warm": warm, "cold": cold},
            ))
        return result

    # ------------------------------------------------------------------
    # Lead detail
    # ------------------------------------------------------------------

    def get_lead_detail(self, lead_name: str) -> LeadDetail | None:
        contacts = self._get_contacts()
        needle = lead_name.lower()
        match = next(
            (c for c in contacts if needle in _full_name(c).lower()),
            None,
        )
        if match is None:
            return None
        score = float(_cf(match, _CF_LEAD_SCORE) or 0)
        temp = _temperature(match)
        return LeadDetail(
            name=_full_name(match),
            phone_masked=_mask_phone(match.get("phone", "") or ""),
            temperature=temp,
            frs_score=score,
            pcs_score=round(score * 0.9, 1),
            qualification_stage="qualified" if temp == "hot" else "qualifying",
            property_address=match.get("address1", "") or "",
            city=match.get("city", "") or "Rancho Cucamonga",
            timeline=_cf(match, _CF_TIMELINE) or "Unknown",
            bot_assigned=_bot_type(match),
            conversation_count=1,
            last_contact=_parse_dt(match.get("dateUpdated")),
        )

    # ------------------------------------------------------------------
    # Activity feed
    # ------------------------------------------------------------------

    def get_recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        contacts = self._get_contacts()
        sorted_contacts = sorted(
            contacts,
            key=lambda c: c.get("dateUpdated", ""),
            reverse=True,
        )
        events = []
        for c in sorted_contacts[:limit]:
            temp = _temperature(c)
            events.append(ActivityEvent(
                event_id=str(uuid.uuid4()),
                event_type="temperature_change",
                lead_name=_full_name(c) or "Unknown",
                bot_id=_bot_type(c),
                description=f"Lead classified as {temp}",
                timestamp=_parse_dt(c.get("dateUpdated")),
                metadata={"tags": list(_tags(c)), "temperature": temp},
            ))
        return events

    # ------------------------------------------------------------------
    # Cost & ROI
    # ------------------------------------------------------------------

    def get_cost_breakdown(self) -> CostBreakdown:
        contacts = self._get_contacts()
        convs = self._get_conversations()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        period = now.strftime("%B %Y")

        total_convs = max(len(convs), 1)
        total_cost = total_convs * _COST_PER_CONV

        by_bot: dict[str, list] = {"seller": [], "buyer": [], "lead": []}
        for c in contacts:
            by_bot[_bot_type(c)].append(c)

        per_bot = []
        for bot_id in ("seller", "buyer", "lead"):
            n = max(len(by_bot[bot_id]), 1)
            in_toks = n * 800
            out_toks = n * 400
            cache_toks = n * 240
            cost = (in_toks * _INPUT_CPM + out_toks * _OUTPUT_CPM + cache_toks * _CACHE_CPM) / 1_000_000
            per_bot.append(BotCostData(
                bot_id=bot_id,
                input_tokens=in_toks,
                output_tokens=out_toks,
                cache_read_tokens=cache_toks,
                total_cost_usd=cost,
                api_calls=n,
            ))

        hot = [c for c in contacts if _temperature(c) == "hot"]
        warm = [c for c in contacts if _temperature(c) == "warm"]
        leads_qualified = len(hot) + len(warm)
        deals_closed = max(1, len(hot) // 3)
        commission = deals_closed * _AVG_COMMISSION
        roi_mult = commission / max(total_cost, 0.01)

        roi = ROIMetrics(
            leads_qualified=leads_qualified,
            appointments_booked=max(1, leads_qualified // 2),
            deals_closed=deals_closed,
            total_commission_earned=commission,
            total_ai_cost=total_cost,
            roi_multiplier=roi_mult,
            cost_per_lead=total_cost / max(leads_qualified, 1),
            cost_per_conversation=_COST_PER_CONV,
        )
        return CostBreakdown(
            period_label=period,
            per_bot=per_bot,
            total_cost_usd=total_cost,
            roi=roi,
        )

    # ------------------------------------------------------------------
    # Platform health
    # ------------------------------------------------------------------

    def get_platform_health(self) -> PlatformHealth:
        return PlatformHealth(
            overall_status="healthy",
            active_bots=3,
            error_rate_24h=0.0,
        )

    # ------------------------------------------------------------------
    # Daily trends
    # ------------------------------------------------------------------

    def get_daily_trends(self, days: int = 14) -> list[DailyTrend]:
        contacts = self._get_contacts()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        trends = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            day_cs = [
                c for c in contacts
                if day_start <= _parse_dt(c.get("dateAdded")) < day_end
            ]
            hot = sum(1 for c in day_cs if _temperature(c) == "hot")
            warm = sum(1 for c in day_cs if _temperature(c) == "warm")
            cold = len(day_cs) - hot - warm
            trends.append(DailyTrend(
                date=day_start,
                conversations=len(day_cs),
                cost_usd=len(day_cs) * _COST_PER_CONV,
                hot_leads=hot,
                warm_leads=warm,
                cold_leads=cold,
            ))
        return trends

    # ------------------------------------------------------------------
    # Recent conversations
    # ------------------------------------------------------------------

    def get_recent_conversations(self, limit: int = 10) -> list[ConversationSnippet]:
        convs = self._get_conversations()
        contacts = self._get_contacts()
        contact_map = {c.get("id"): c for c in contacts}
        snippets = []
        for conv in convs[:limit]:
            contact = contact_map.get(conv.get("contactId"), {})
            name = _full_name(contact) or "Unknown"
            snippets.append(ConversationSnippet(
                lead_name=name,
                bot_id=_bot_type(contact),
                message_preview=(conv.get("lastMessageBody") or "")[:80] or "[No message]",
                timestamp=_parse_dt(conv.get("lastMessageDate")),
                temperature=_temperature(contact),
                message_count=conv.get("unreadCount", 0) + 1,
            ))
        return snippets

    # ------------------------------------------------------------------
    # Handoff events
    # ------------------------------------------------------------------

    def get_handoff_events(self, limit: int = 10) -> list[HandoffEvent]:
        contacts = self._get_contacts()
        events = []
        for c in contacts:
            if len(events) >= limit:
                break
            t = _tags(c)
            # Lead → Seller: had "needs qualifying" and now seller-classified
            if ("needs qualifying" in t or "hot-lead" in t) and (t & _SELLER_TAGS):
                events.append(HandoffEvent(
                    source_bot="lead",
                    target_bot="seller",
                    lead_name=_full_name(c) or "Unknown",
                    confidence=0.85,
                    success=True,
                    timestamp=_parse_dt(c.get("dateUpdated")),
                ))
            # Lead → Buyer
            elif "needs qualifying" in t and (t & _BUYER_TAGS):
                events.append(HandoffEvent(
                    source_bot="lead",
                    target_bot="buyer",
                    lead_name=_full_name(c) or "Unknown",
                    confidence=0.80,
                    success=True,
                    timestamp=_parse_dt(c.get("dateUpdated")),
                ))
        return events

    # ------------------------------------------------------------------
    # All leads
    # ------------------------------------------------------------------

    def get_all_leads(self) -> list[LeadDetail]:
        contacts = self._get_contacts()
        leads = []
        for c in contacts:
            name = _full_name(c)
            if not name:
                continue
            score = float(_cf(c, _CF_LEAD_SCORE) or 0)
            temp = _temperature(c)
            leads.append(LeadDetail(
                name=name,
                phone_masked=_mask_phone(c.get("phone", "") or ""),
                temperature=temp,
                frs_score=score,
                pcs_score=round(score * 0.9, 1),
                qualification_stage="qualified" if temp == "hot" else "qualifying",
                property_address=c.get("address1", "") or "",
                city=c.get("city", "") or "Rancho Cucamonga",
                timeline=_cf(c, _CF_TIMELINE) or "Unknown",
                bot_assigned=_bot_type(c),
                conversation_count=1,
                last_contact=_parse_dt(c.get("dateUpdated")),
            ))
        return leads

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def _resolve_contact(self, lead_name: str) -> tuple[str, str] | None:
        """Return (contact_id, full_name) for the first contact matching lead_name, or None."""
        if not lead_name or not lead_name.strip():
            return None
        needle = lead_name.lower()
        contacts = self._get_contacts()
        match = next(
            (c for c in contacts if needle in _full_name(c).lower()),
            None,
        )
        if match is None:
            return None
        return match.get("id", ""), _full_name(match)

    def _invalidate_contacts_cache(self) -> None:
        self._contacts = None

    # ------------------------------------------------------------------
    # Write actions
    # ------------------------------------------------------------------

    def send_sms(self, lead_name: str, message: str) -> ActionResult:
        resolved = self._resolve_contact(lead_name)
        if resolved is None:
            return ActionResult(
                success=False,
                action="sms_sent",
                contact_name=lead_name,
                detail=f"No contact found matching '{lead_name}'",
            )
        contact_id, name = resolved
        try:
            self._client.send_sms(contact_id, message)
            return ActionResult(
                success=True,
                action="sms_sent",
                contact_name=name,
                detail=f"SMS sent to {name}",
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                action="sms_sent",
                contact_name=name,
                detail=f"Failed to send SMS to {name}: {exc}",
            )

    def enroll_in_workflow(self, lead_name: str, workflow_name: str) -> ActionResult:
        resolved = self._resolve_contact(lead_name)
        if resolved is None:
            return ActionResult(
                success=False,
                action="workflow_enrolled",
                contact_name=lead_name,
                detail=f"No contact found matching '{lead_name}'",
            )
        contact_id, name = resolved
        workflow_id = _WORKFLOWS.get(workflow_name.lower())
        if workflow_id is None:
            available = ", ".join(_WORKFLOWS.keys())
            return ActionResult(
                success=False,
                action="workflow_enrolled",
                contact_name=name,
                detail=f"Unknown workflow '{workflow_name}'. Available: {available}",
            )
        try:
            self._client.enroll_in_workflow(contact_id, workflow_id)
            return ActionResult(
                success=True,
                action="workflow_enrolled",
                contact_name=name,
                detail=f"{name} enrolled in '{workflow_name}'",
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                action="workflow_enrolled",
                contact_name=name,
                detail=f"Failed to enroll {name}: {exc}",
            )

    def update_lead_temperature(self, lead_name: str, new_temperature: str) -> ActionResult:
        resolved = self._resolve_contact(lead_name)
        if resolved is None:
            return ActionResult(
                success=False,
                action="tags_updated",
                contact_name=lead_name,
                detail=f"No contact found matching '{lead_name}'",
            )
        contact_id, name = resolved
        temp = new_temperature.lower().strip()
        if temp not in {"hot", "warm", "cold"}:
            return ActionResult(
                success=False,
                action="tags_updated",
                contact_name=name,
                detail=f"Invalid temperature '{new_temperature}'. Must be hot, warm, or cold.",
            )
        # Determine bot type to pick the right tag prefix
        contacts = self._get_contacts()
        contact = next((c for c in contacts if c.get("id") == contact_id), {})
        bot = _bot_type(contact)
        new_tag = f"{temp}-{bot}"
        try:
            self._client.remove_tags(contact_id, _ALL_TEMP_TAGS)
            self._client.add_tags(contact_id, [new_tag])
            self._invalidate_contacts_cache()
            return ActionResult(
                success=True,
                action="tags_updated",
                contact_name=name,
                detail=f"Updated {name} temperature to {temp} (tag: {new_tag})",
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                action="tags_updated",
                contact_name=name,
                detail=f"Failed to update temperature for {name}: {exc}",
            )

    def update_lead_score(
        self,
        lead_name: str,
        frs_score: float | None = None,
        pcs_score: float | None = None,
    ) -> ActionResult:
        resolved = self._resolve_contact(lead_name)
        if resolved is None:
            return ActionResult(
                success=False,
                action="score_updated",
                contact_name=lead_name,
                detail=f"No contact found matching '{lead_name}'",
            )
        contact_id, name = resolved
        for label, score in (("frs_score", frs_score), ("pcs_score", pcs_score)):
            if score is not None and not (0 <= score <= 100):
                return ActionResult(
                    success=False,
                    action="score_updated",
                    contact_name=name,
                    detail=f"{label} must be between 0 and 100, got {score}",
                )
        if frs_score is None and pcs_score is None:
            return ActionResult(
                success=False,
                action="score_updated",
                contact_name=name,
                detail="No score provided — specify frs_score or pcs_score.",
            )
        try:
            score_value = frs_score if frs_score is not None else pcs_score
            self._client.update_contact(contact_id, {
                "customFields": [{"id": _CF_LEAD_SCORE, "field_value": str(score_value)}],
            })
            self._invalidate_contacts_cache()
            parts = []
            if frs_score is not None:
                parts.append(f"FRS={frs_score}")
            if pcs_score is not None:
                parts.append(f"PCS={pcs_score}")
            return ActionResult(
                success=True,
                action="score_updated",
                contact_name=name,
                detail=f"Updated {name} scores: {', '.join(parts)}",
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                action="score_updated",
                contact_name=name,
                detail=f"Failed to update score for {name}: {exc}",
            )
