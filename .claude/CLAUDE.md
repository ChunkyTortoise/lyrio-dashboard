# Lyrio Dashboard

## Stack
Python 3.11 | Streamlit | Anthropic Claude (tool_use) | Plotly | Pandas

## Architecture
Real estate analytics dashboard with AI concierge (5 tools via Claude tool_use).
Pages: Concierge Chat, Bot Command Center, Cost & ROI, Lead Activity Feed.
Backend: DemoDataProvider (seeded random, seed 20260221) or JorgeApiDataProvider (live API).

## JorgeApiDataProvider Methods
`backend/jorge_api_provider.py` -- connects to Jorge API at `JORGE_API_URL`:
- `get_bot_statuses()` -- Bot health from `/api/dashboard/metrics`
- `get_platform_health()` -- Platform health summary
- `get_handoff_events(limit)` -- From `/api/dashboard/handoffs`
- `get_q_stage_distribution()` -- Q-stage counts from `/api/dashboard/leads`
- `get_conversation_transcript(contact_id)` -- From `/api/dashboard/conversations/{id}`
- `get_performance_metrics()` -- From `/api/dashboard/metrics`
- `get_active_alerts()` -- From `/api/alerts/active`
- `get_sms_metrics()` -- From `/api/dashboard/sms-metrics`
- `get_cost_breakdown()` -- From `/api/dashboard/costs`
- `get_recent_activity(limit)` -- From `/api/dashboard/leads`
- `get_funnel_data()` -- From `/api/dashboard/funnel`
- `get_stall_stats(contact_id)` -- From `/api/dashboard/stall-stats`
- `acknowledge_alert(alert_id)` -- POST `/api/alerts/{id}/acknowledge`

## Deploy
Live: lyrio-jorge.streamlit.app (Streamlit Cloud, account: chunkytortoise)

## Test
```
pytest tests/ -v  # 39 tests
```
