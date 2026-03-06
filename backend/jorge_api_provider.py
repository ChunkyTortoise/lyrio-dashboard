"""JorgeApiDataProvider — replaces fabricated metrics with real Jorge API data."""
from __future__ import annotations

import requests
from datetime import datetime, timezone

from backend.ghl_client import GHLClient
from backend.live_data import LiveDataProvider
from backend.models import (
    ActivityEvent,
    BotCostData,
    BotStatus,
    CostBreakdown,
    HandoffEvent,
    PlatformHealth,
    ROIMetrics,
)


class JorgeApiDataProvider(LiveDataProvider):
    """DataProvider that pulls real metrics from Jorge's dashboard API.

    Extends LiveDataProvider (GHL-based) and overrides methods that
    return fabricated/heuristic data with real data from Jorge API.
    Falls back to parent implementation if Jorge API is unavailable.
    """

    def __init__(
        self,
        client: GHLClient,
        jorge_api_url: str,
        jorge_api_key: str,
    ) -> None:
        super().__init__(client, jorge_api_url=jorge_api_url, jorge_api_key=jorge_api_key)
        self._api_base = jorge_api_url.rstrip("/")
        self._headers = {"X-Admin-Key": jorge_api_key} if jorge_api_key else {}
        self._jorge_metrics_cache: dict | None = None
        self._jorge_metrics_ts: datetime | None = None

    def _fetch_jorge_metrics(self) -> dict | None:
        """GET /api/dashboard/metrics -- cached 30s. Returns None on failure."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if (
            self._jorge_metrics_cache is not None
            and self._jorge_metrics_ts is not None
            and (now - self._jorge_metrics_ts).total_seconds() < 30
        ):
            return self._jorge_metrics_cache
        if not self._api_base:
            return None
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/metrics",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            self._jorge_metrics_cache = r.json()
            self._jorge_metrics_ts = now
            return self._jorge_metrics_cache
        except Exception:
            return None

    def get_bot_statuses(self) -> list[BotStatus]:
        """Override: replace hardcoded avg_response_time + success_rate with real data."""
        statuses = super().get_bot_statuses()
        metrics = self._fetch_jorge_metrics()
        if not metrics:
            return statuses
        # get_system_summary() returns {"bots": {...}, "handoffs": {...}, "overall": {...}}
        system = metrics.get("system", {})
        bot_metrics = system.get("bots", {})
        result = []
        for s in statuses:
            bm = bot_metrics.get(s.bot_id, {})
            avg_ms = bm.get("avg_duration_ms")
            avg_sec = avg_ms / 1000.0 if avg_ms else s.avg_response_time_sec
            success_rate = bm.get("success_rate", s.success_rate)
            active = bm.get("active_conversations", s.active_conversations)
            result.append(BotStatus(
                bot_id=s.bot_id,
                bot_name=s.bot_name,
                is_online=s.is_online,
                conversations_today=s.conversations_today,
                conversations_total=s.conversations_total,
                avg_response_time_sec=round(avg_sec, 2),
                success_rate=success_rate,
                leads_qualified_today=s.leads_qualified_today,
                active_conversations=active,
                temp_distribution=s.temp_distribution,
            ))
        return result

    def get_platform_health(self) -> PlatformHealth:
        """Override: use real error_rate_24h from Jorge /health/aggregate."""
        if not self._api_base:
            return super().get_platform_health()
        try:
            r = requests.get(
                f"{self._api_base}/health/aggregate",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            checks = data.get("checks", {})
            all_ok = all(v in (True, "ok", "healthy") for v in checks.values())
            status = "healthy" if all_ok else "degraded"
            metrics = self._fetch_jorge_metrics()
            error_rate = 0.0
            if metrics:
                perf = metrics.get("performance", {})
                error_rate = perf.get("error_rate_24h", 0.0)
            return PlatformHealth(
                overall_status=status,
                active_bots=3,
                error_rate_24h=error_rate,
            )
        except Exception:
            return super().get_platform_health()

    def get_handoff_events(self, limit: int = 10) -> list[HandoffEvent]:
        """Override: use real handoff records from Jorge BotMetricsCollector."""
        if not self._api_base:
            return super().get_handoff_events(limit)
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/handoffs",
                headers=self._headers,
                timeout=5,
                params={"limit": limit},
            )
            r.raise_for_status()
            data = r.json()
            # API returns a plain list or a dict with "handoffs" key
            raw = data if isinstance(data, list) else data.get("handoffs", [])
            events: list[HandoffEvent] = []
            for e in raw[:limit]:
                ts_str = e.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        ts = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    ts = datetime.now(timezone.utc).replace(tzinfo=None)
                # _HandoffRecord uses "source"/"target", but also accept "source_bot"/"target_bot"
                events.append(HandoffEvent(
                    source_bot=e.get("source", e.get("source_bot", "lead")),
                    target_bot=e.get("target", e.get("target_bot", "seller")),
                    lead_name=e.get("lead_name", "Unknown"),
                    confidence=float(e.get("confidence", 0.0)),
                    success=bool(e.get("success", True)),
                    timestamp=ts,
                ))
            return events if events else super().get_handoff_events(limit)
        except Exception:
            return super().get_handoff_events(limit)

    def get_q_stage_distribution(self) -> dict[str, int]:
        """GET /api/dashboard/leads/summary -> conversation_summary.by_stage."""
        if not self._api_base:
            return {}
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/leads/summary",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            by_stage = data.get("conversation_summary", {}).get("by_stage", {})
            return {str(k).upper(): int(v) for k, v in by_stage.items() if v}
        except Exception:
            return {}

    def get_conversation_transcript(self, contact_id: str) -> list[dict]:
        """GET /api/dashboard/conversations/{contact_id} -> full Q&A transcript."""
        if not self._api_base or not contact_id:
            return []
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/conversations/{contact_id}",
                headers=self._headers,
                timeout=5,
            )
            if r.status_code == 404:
                return []
            r.raise_for_status()
            result = r.json()
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def get_performance_metrics(self) -> dict:
        """GET /api/dashboard/metrics -> performance data."""
        metrics = self._fetch_jorge_metrics()
        if not metrics:
            return {}
        return metrics.get("performance", {})

    def get_active_alerts(self) -> list[dict]:
        """GET /api/alerts/active -> list of active alerts."""
        if not self._api_base:
            return []
        try:
            r = requests.get(
                f"{self._api_base}/api/alerts/active",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            result = r.json()
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def get_sms_metrics(self) -> dict:
        """GET /api/dashboard/sms-metrics -> SMS delivery stats."""
        if not self._api_base:
            return {"delivered": 0, "failed": 0, "read": 0, "delivery_rate": 0.0}
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/sms-metrics",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return {"delivered": 0, "failed": 0, "read": 0, "delivery_rate": 0.0}

    def get_cost_breakdown(self) -> CostBreakdown:
        """Override: pull real cost/ROI data from Jorge /api/dashboard/costs."""
        if not self._api_base:
            return super().get_cost_breakdown()
        try:
            r = requests.get(
                f"{self._api_base}/api/dashboard/costs",
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()

            per_bot = []
            for entry in data.get("per_bot", []):
                per_bot.append(BotCostData(
                    bot_id=entry.get("bot_id", "unknown"),
                    input_tokens=entry.get("input_tokens", 0),
                    output_tokens=entry.get("output_tokens", 0),
                    cache_read_tokens=entry.get("cache_read_tokens", 0),
                    total_cost_usd=entry.get("total_cost_usd", 0.0),
                    api_calls=entry.get("api_calls", 0),
                ))

            total_cost = data.get("total_cost_usd", 0.0)
            appointments = data.get("appointments_booked", 0)
            deals = data.get("deals_closed", 0)
            commission = data.get("commission_pipeline", 0.0)
            leads_qualified = appointments  # best available proxy

            roi = ROIMetrics(
                leads_qualified=leads_qualified,
                appointments_booked=appointments,
                deals_closed=deals,
                total_commission_earned=commission,
                total_ai_cost=total_cost,
                roi_multiplier=commission / max(total_cost, 0.01),
                cost_per_lead=total_cost / max(leads_qualified, 1),
                cost_per_conversation=total_cost / max(appointments + deals, 1),
            )

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            return CostBreakdown(
                period_label=now.strftime("%B %Y"),
                per_bot=per_bot,
                total_cost_usd=total_cost,
                roi=roi,
            )
        except Exception:
            return super().get_cost_breakdown()

    def get_recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        """Override: pull real events from Jorge /api/events/recent."""
        if not self._api_base:
            return super().get_recent_activity(limit)
        try:
            r = requests.get(
                f"{self._api_base}/api/events/recent",
                headers=self._headers,
                timeout=5,
                params={"limit": limit, "since_minutes": 60},
            )
            r.raise_for_status()
            data = r.json()
            raw_events = data.get("events", [])

            # Map Jorge event_type → Lyrio event_type
            _TYPE_MAP = {
                "lead.new": "message_received",
                "lead.qualified": "temperature_change",
                "lead.temperature_change": "temperature_change",
                "bot.handoff": "handoff",
                "bot.response": "message_sent",
                "message.inbound": "message_received",
                "message.outbound": "message_sent",
                "workflow.triggered": "workflow_triggered",
                "tag.applied": "tag_applied",
            }

            events: list[ActivityEvent] = []
            for e in raw_events[:limit]:
                ts_str = e.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                    except Exception:
                        ts = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    ts = datetime.now(timezone.utc).replace(tzinfo=None)

                jorge_type = e.get("event_type", "")
                lyrio_type = _TYPE_MAP.get(jorge_type, jorge_type)
                payload = e.get("payload", {})

                events.append(ActivityEvent(
                    event_id=e.get("event_id", ""),
                    event_type=lyrio_type,
                    lead_name=payload.get("contact_name", payload.get("lead_name", "Unknown")),
                    bot_id=payload.get("bot_id", e.get("source")),
                    description=payload.get("description", f"{lyrio_type}: {jorge_type}"),
                    timestamp=ts,
                    metadata=payload,
                ))
            return events if events else super().get_recent_activity(limit)
        except Exception:
            return super().get_recent_activity(limit)

    def get_funnel_data(self) -> dict:
        if not self._api_base:
            return {}
        try:
            r = requests.get(f"{self._api_base}/api/dashboard/funnel", headers=self._headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def get_stall_stats(self, contact_id: str | None = None) -> dict:
        if not self._api_base:
            return {}
        try:
            params = {"contact_id": contact_id} if contact_id else {}
            r = requests.get(f"{self._api_base}/api/dashboard/stall-stats", headers=self._headers, timeout=5, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def acknowledge_alert(self, alert_id: str) -> bool:
        if not self._api_base:
            return False
        try:
            resp = requests.post(
                f"{self._api_base}/api/alerts/{alert_id}/acknowledge",
                headers=self._headers,
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False