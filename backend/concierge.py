"""Lyrio concierge — Claude tool_use chat module for Jorge's real estate business."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from backend.data_provider import DataProvider

_SYSTEM_PROMPT = """You are Lyrio, the AI assistant for Jorge Salas's real estate business in Rancho Cucamonga, CA.

Jorge runs three AI bots that qualify leads via SMS through GoHighLevel (GHL):
- Seller Bot: qualifies homeowners considering selling. Computes FRS (Financial Readiness Score, 0-100). Threshold: hot ≥ 80, warm 40-79, cold < 40.
- Buyer Bot: qualifies home buyers on financial readiness and property preferences.
- Lead Bot: handles initial outreach and routes leads to Seller or Buyer Bot.

Market context: Rancho Cucamonga, CA. Median home price ~$850K. 18-25 day market time. Key neighborhoods: Alta Loma, Etiwanda, Victoria Gardens, Chino Hills.

Cost structure: $3/MTok input, $15/MTok output, $0.30/MTok cache reads (Claude Sonnet).

ROI formula: hot_leads × avg_commission / total_ai_cost. Average commission = $18,000 (3% on $600K home).

Tone: Direct, professional, not stiff. No buzzwords. Talk like a smart analyst who respects Jorge's time. 2-4 sentences for simple questions. Bullet points for complex ones. Never say "certainly" or "absolutely."

When asked about specific leads, use get_lead_detail. For costs, use get_cost_breakdown. For overall status, use get_bot_status or get_lead_summary."""

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_bot_status",
        "description": "Get current status of all 3 bots: online status, conversations today, avg response time, success rate, and lead temperature distribution.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_lead_summary",
        "description": "Get a summary of leads by temperature: hot, warm, cold counts, total leads, qualified today, and new leads today.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_cost_breakdown",
        "description": "Get total AI spend, per-bot costs (input/output tokens), and ROI metrics for the current month.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_activity",
        "description": "Get recent bot activity events: messages sent/received, temperature changes, handoffs, workflow triggers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of events to return (default 10)", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_lead_detail",
        "description": "Get detailed info about a specific lead: temperature, FRS/PCS scores, qualification stage, property address, timeline, assigned bot, conversation count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name (case-insensitive)"},
            },
            "required": ["lead_name"],
        },
    },
]


class ConciergeChat:
    """Synchronous Claude tool_use concierge for Lyrio dashboard."""

    def __init__(self, data_provider: DataProvider, api_key: str = "") -> None:
        self._provider = data_provider
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def chat(self, user_message: str, history: list[dict]) -> str:
        """Send a user message and return assistant text response.

        Args:
            user_message: The user's question or request.
            history: Prior conversation as list of {"role": str, "content": str}.
                     Should NOT include the current user_message.

        Returns:
            Assistant text response.
        """
        messages: list[dict] = list(history) + [{"role": "user", "content": user_message}]

        max_rounds = 3
        response = None
        for _ in range(max_rounds):
            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        if response is None:
            return "No response generated."

        for block in response.content:
            if hasattr(block, "text"):
                return block.text

        return "I couldn't generate a response. Please try again."

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a named tool and return a JSON string result."""
        try:
            if tool_name == "get_bot_status":
                statuses = self._provider.get_bot_statuses()
                return json.dumps([
                    {
                        "bot": s.bot_name,
                        "online": s.is_online,
                        "conversations_today": s.conversations_today,
                        "avg_response_sec": round(s.avg_response_time_sec, 1),
                        "success_rate": f"{s.success_rate * 100:.0f}%",
                        "leads": s.temp_distribution,
                    }
                    for s in statuses
                ])

            if tool_name == "get_lead_summary":
                ls = self._provider.get_lead_summary()
                return json.dumps({
                    "hot": ls.hot_count,
                    "warm": ls.warm_count,
                    "cold": ls.cold_count,
                    "total": ls.total_count,
                    "qualified_today": ls.qualified_today,
                    "new_today": ls.new_today,
                })

            if tool_name == "get_cost_breakdown":
                cb = self._provider.get_cost_breakdown()
                roi = cb.roi
                return json.dumps({
                    "period": cb.period_label,
                    "total_cost_usd": round(cb.total_cost_usd, 4),
                    "per_bot": [
                        {
                            "bot": b.bot_id,
                            "api_calls": b.api_calls,
                            "input_tokens": b.input_tokens,
                            "output_tokens": b.output_tokens,
                            "cost_usd": round(b.total_cost_usd, 4),
                        }
                        for b in cb.per_bot
                    ],
                    "roi": {
                        "leads_qualified": roi.leads_qualified,
                        "appointments": roi.appointments_booked,
                        "deals": roi.deals_closed,
                        "commission_earned": roi.total_commission_earned,
                        "roi_multiplier": round(roi.roi_multiplier, 0),
                        "cost_per_lead": round(roi.cost_per_lead, 4),
                        "cost_per_conversation": round(roi.cost_per_conversation, 4),
                    },
                })

            if tool_name == "get_recent_activity":
                limit = tool_input.get("limit", 10)
                events = self._provider.get_recent_activity(limit=limit)
                return json.dumps([
                    {
                        "type": e.event_type,
                        "lead": e.lead_name,
                        "bot": e.bot_id,
                        "description": e.description,
                        "time": e.timestamp.isoformat(),
                    }
                    for e in events
                ])

            if tool_name == "get_lead_detail":
                name = tool_input.get("lead_name", "")
                detail = self._provider.get_lead_detail(name)
                if detail is None:
                    return json.dumps({"error": f"No lead found matching '{name}'"})
                return json.dumps({
                    "name": detail.name,
                    "phone": detail.phone_masked,
                    "temperature": detail.temperature,
                    "frs_score": round(detail.frs_score, 1),
                    "pcs_score": round(detail.pcs_score, 1),
                    "stage": detail.qualification_stage,
                    "property": detail.property_address,
                    "city": detail.city,
                    "timeline": detail.timeline,
                    "bot": detail.bot_assigned,
                    "conversations": detail.conversation_count,
                    "last_contact": detail.last_contact.isoformat(),
                })

            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as exc:
            return json.dumps({"error": str(exc)})
