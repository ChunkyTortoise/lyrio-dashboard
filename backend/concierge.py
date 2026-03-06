"""Lyrio concierge — Claude tool_use chat module for Jorge's real estate business."""
from __future__ import annotations

import json
from typing import Any, Callable

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

When asked about specific leads, use get_lead_detail. For costs, use get_cost_breakdown. For overall status, use get_bot_status or get_lead_summary.

WRITE ACTIONS — IMPORTANT RULES:
You have tools that write to GHL: send_sms, enroll_in_workflow, update_lead_temperature, update_lead_score.
Before calling ANY write tool you MUST:
1. Look up the lead first (use get_lead_detail) if you do not already have their details in context.
2. Propose exactly what you plan to do — spell out the SMS text, workflow name, new temperature, or new score.
3. Ask "Want me to go ahead?" (or similar) and wait for explicit confirmation.
4. ONLY call the write tool AFTER the user explicitly says yes, confirms, or approves.
Never combine a read lookup and a write action in the same turn. Never call a write tool speculatively.

For conversation details, use get_conversation_transcript. For system health, use get_performance_metrics or get_alerts. For stalled leads and re-engagement history, use get_stall_history (optionally pass a lead name)."""

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
        "description": "Get detailed info about a specific lead: temperature, FRS score, qualification stage, property address, timeline, assigned bot, conversation count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name (case-insensitive)"},
            },
            "required": ["lead_name"],
        },
    },
    {
        "name": "send_sms",
        "description": "Send an outbound SMS to a lead. ONLY call this after the user has explicitly confirmed the message text and recipient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name"},
                "message": {"type": "string", "description": "The exact SMS text to send"},
            },
            "required": ["lead_name", "message"],
        },
    },
    {
        "name": "enroll_in_workflow",
        "description": "Enroll a lead in a GHL workflow by name. ONLY call this after the user has explicitly confirmed the lead name and workflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name"},
                "workflow_name": {"type": "string", "description": "Workflow display name (e.g. 'Hot Seller Workflow')"},
            },
            "required": ["lead_name", "workflow_name"],
        },
    },
    {
        "name": "update_lead_temperature",
        "description": "Change a lead's temperature tag in GHL to hot, warm, or cold. ONLY call this after the user has explicitly confirmed the change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name"},
                "new_temperature": {
                    "type": "string",
                    "enum": ["hot", "warm", "cold"],
                    "description": "New temperature: hot, warm, or cold",
                },
            },
            "required": ["lead_name", "new_temperature"],
        },
    },
    {
        "name": "update_lead_score",
        "description": "Update a lead's FRS score in GHL (0-100). ONLY call this after the user has explicitly confirmed the new score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name"},
                "frs_score": {
                    "type": "number",
                    "description": "New FRS score (0-100)",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["lead_name", "frs_score"],
        },
    },
    {
        "name": "get_conversation_transcript",
        "description": "Get the full Q&A conversation transcript for a lead, showing their qualification progress through Q0-Q4-QUALIFIED stages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {"type": "string", "description": "Full or partial lead name"},
            },
            "required": ["lead_name"],
        },
    },
    {
        "name": "get_performance_metrics",
        "description": "Get real-time performance metrics: AI response times, cache hit rates, GHL API health, 5-minute rule compliance.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_alerts",
        "description": "Get currently active system alerts: threshold breaches for error rate, response time, cache hit rate, handoff failures.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_stall_history",
        "description": "Get stall/re-engagement stats for a specific lead or overall. Shows stalled count, reply rate, and stage breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name": {
                    "type": "string",
                    "description": "Full or partial lead name. Omit for overall stall stats.",
                },
            },
            "required": [],
        },
    },
]


_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ConciergeChat:
    """Synchronous Claude tool_use concierge for Lyrio dashboard."""

    def __init__(self, data_provider: DataProvider, api_key: str = "", model: str = "") -> None:
        self._provider = data_provider
        self._model = model or _DEFAULT_MODEL
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def chat(
        self,
        user_message: str,
        history: list[dict],
        on_tool_call: Callable[[str], None] | None = None,
    ) -> str:
        """Send a user message and return assistant text response.

        Args:
            user_message: The user's question or request.
            history: Prior conversation as list of {"role": str, "content": str}.
                     Should NOT include the current user_message.
            on_tool_call: Optional callback invoked with the tool name each time a
                          tool call is about to execute. Use for UI progress indicators.

        Returns:
            Assistant text response.
        """
        messages: list[dict] = list(history) + [{"role": "user", "content": user_message}]

        max_rounds = 5
        response = None
        for _ in range(max_rounds):
            response = self._client.messages.create(
                model=self._model,
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
                    if on_tool_call is not None:
                        on_tool_call(block.name)
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
                    "stage": detail.qualification_stage,
                    "property": detail.property_address,
                    "city": detail.city,
                    "timeline": detail.timeline,
                    "bot": detail.bot_assigned,
                    "conversations": detail.conversation_count,
                    "last_contact": detail.last_contact.isoformat(),
                })

            if tool_name == "send_sms":
                lead_name = tool_input.get("lead_name", "")
                message = tool_input.get("message", "")
                result = self._provider.send_sms(lead_name, message)
                return json.dumps({
                    "success": result.success,
                    "action": result.action,
                    "contact": result.contact_name,
                    "detail": result.detail,
                })

            if tool_name == "enroll_in_workflow":
                lead_name = tool_input.get("lead_name", "")
                workflow_name = tool_input.get("workflow_name", "")
                result = self._provider.enroll_in_workflow(lead_name, workflow_name)
                return json.dumps({
                    "success": result.success,
                    "action": result.action,
                    "contact": result.contact_name,
                    "detail": result.detail,
                })

            if tool_name == "update_lead_temperature":
                lead_name = tool_input.get("lead_name", "")
                new_temperature = tool_input.get("new_temperature", "")
                result = self._provider.update_lead_temperature(lead_name, new_temperature)
                return json.dumps({
                    "success": result.success,
                    "action": result.action,
                    "contact": result.contact_name,
                    "detail": result.detail,
                })

            if tool_name == "update_lead_score":
                lead_name = tool_input.get("lead_name", "")
                frs_score = tool_input.get("frs_score")
                result = self._provider.update_lead_score(lead_name, frs_score=frs_score)
                return json.dumps({
                    "success": result.success,
                    "action": result.action,
                    "contact": result.contact_name,
                    "detail": result.detail,
                })

            if tool_name == "get_conversation_transcript":
                lead_name = tool_input.get("lead_name", "")
                detail = self._provider.get_lead_detail(lead_name)
                if detail is None:
                    return json.dumps({"error": f"No lead found matching '{lead_name}'"})
                contact_id = getattr(detail, "contact_id", "")
                if not contact_id:
                    return json.dumps({"error": f"No contact ID available for '{lead_name}'. Jorge API required."})
                if not hasattr(self._provider, "get_conversation_transcript"):
                    return json.dumps({"error": "Conversation transcripts require Jorge API mode."})
                transcript = self._provider.get_conversation_transcript(contact_id)
                if not transcript:
                    return json.dumps({"message": f"No conversation transcript found for {detail.name}."})
                summaries = []
                for conv in transcript:
                    history = conv.get("conversation_history", [])
                    msg_count = len(history) if isinstance(history, list) else 0
                    summaries.append({
                        "bot": conv.get("bot_type", "unknown"),
                        "stage": conv.get("stage", "?"),
                        "temperature": conv.get("temperature", "?"),
                        "messages": msg_count,
                        "extracted_data": conv.get("extracted_data", {}),
                        "last_messages": [
                            {"role": m.get("role"), "text": str(m.get("content", ""))[:150]}
                            for m in (history[-4:] if isinstance(history, list) else [])
                        ],
                    })
                return json.dumps({"lead": detail.name, "conversations": summaries})

            if tool_name == "get_performance_metrics":
                if not hasattr(self._provider, "get_performance_metrics"):
                    return json.dumps({"error": "Performance metrics require Jorge API mode."})
                perf = self._provider.get_performance_metrics()
                return json.dumps(perf if perf else {"message": "No performance data available."})

            if tool_name == "get_alerts":
                if not hasattr(self._provider, "get_active_alerts"):
                    return json.dumps({"message": "Alerts require Jorge API mode."})
                alerts = self._provider.get_active_alerts()
                if not alerts:
                    return json.dumps({"message": "No active alerts."})
                return json.dumps({"active_alerts": alerts, "count": len(alerts)})

            if tool_name == "get_stall_history":
                if not hasattr(self._provider, "get_stall_stats"):
                    return json.dumps({"message": "Stall stats require Jorge API mode."})
                lead_name = tool_input.get("lead_name", "")
                contact_id: str | None = None
                if lead_name:
                    detail = self._provider.get_lead_detail(lead_name)
                    if detail is None:
                        return json.dumps({"error": f"No lead found matching '{lead_name}'"})
                    contact_id = getattr(detail, "contact_id", None)
                stats = self._provider.get_stall_stats(contact_id=contact_id)
                if not stats:
                    return json.dumps({"message": "No stall data available."})
                return json.dumps(stats)

            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as exc:
            return json.dumps({"error": str(exc)})
