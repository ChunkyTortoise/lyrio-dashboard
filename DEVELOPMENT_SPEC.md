# Lyrio Dashboard — Development Spec

**As of:** 2026-02-21
**Live URL:** https://lyrio-jorge.streamlit.app
**Repo:** github.com/ChunkyTortoise/lyrio-dashboard
**Stack:** Python 3.12 · Streamlit 1.32+ · Anthropic claude-sonnet-4-20250514 · Plotly · Pandas

---

## Current State

The Lyrio Dashboard is deployed and functional with 5 pages: Concierge Chat, Bot Command Center, Cost & ROI Tracker, Lead Activity Feed, and Lead Browser. All 25 tests pass. Supports both demo mode (deterministic seeded data) and live mode (GoHighLevel API via `GHLClient` — activated when `[ghl] api_key` and `[ghl] location_id` are set in Streamlit secrets).

---

## Recently Completed

### Wave B — UX Improvements (2026-02-21) ✅

| Item | Change | Files |
|------|--------|-------|
| B1: Lead browser | New "Leads" page — searchable table (Name · Temperature · FRS · Bot · Stage · Last Contact), temperature/bot filter dropdowns, name search, detail panel. Added `get_all_leads()` to `DataProvider` protocol and all providers. | `pages/lead_browser.py` · `backend/data_provider.py` · `backend/demo_data.py` · `backend/live_data.py` · `app.py` |
| B2: Sidebar context for Bots | Replaced static "last sync 2m ago" with live qualified-leads-today count summed from `BotStatus.leads_qualified_today`. Added Leads page sidebar context. | `components.py` |
| B3: Activity filter persistence | Filter state saved to `st.session_state["activity_filters"]` via `on_change` callbacks; restored from that dict on page load. Filters survive navigation. | `pages/lead_activity_feed.py` |
| B4: Concierge tool-call indicator | `ConciergeChat.chat()` accepts `on_tool_call: Callable[[str], None]` callback. Chat page uses `st.empty()` to show `🔍 Checking lead data...` while tool calls are in flight. | `backend/concierge.py` · `pages/concierge_chat.py` |

### Wave A — Demo Polish (2026-02-21) ✅

| Item | Change | Files |
|------|--------|-------|
| A1: Provider caching | `@st.cache_resource` on `_get_provider()` | `app.py` |
| A2: Stable response times | Pre-compute `avg_response_time_sec` in `__init__` | `backend/demo_data.py` |
| A3: Month label | Period label on cost metric card subtitle | `pages/cost_roi_tracker.py` |
| A4: Clear chat | "Clear chat" button when history exists | `pages/concierge_chat.py` |

### Wave C — Live GHL Integration (2026-02-21) ✅

| Item | Change | Files |
|------|--------|-------|
| C1: GHL API client | `GHLClient` — contacts, conversations endpoints | `backend/ghl_client.py` |
| C2: `LiveDataProvider` | Full implementation of all `DataProvider` methods from GHL data | `backend/live_data.py` |
| C3: Mode detection | `app.py` checks `[ghl]` secrets — live if present, demo fallback | `app.py` |
| C4: Mode label | Sidebar footer shows "Live — Jorge's GHL" vs "Demo mode" | `app.py` |

---

## Remaining Issues

### P0 — Functional Bugs

None open.

### P1 — High Priority

| # | Issue | File | Fix |
|---|-------|------|-----|
| H1 | ~~Month selector only filters the bar chart, not the 4 metric cards~~ **FIXED** — Metric cards now compute from month-filtered `DailyTrend` data. Month selector is dynamic from actual trend dates. | `cost_roi_tracker.py` | Resolved. |
| H4 | ~~`_NOW` is a module-level constant frozen at `datetime(2026, 2, 21)`~~ **FIXED** — `self._now` is now an instance attribute set in `__init__`, so each `DemoDataProvider()` uses current time. | `demo_data.py` | Resolved. |

### P2 — Medium Priority

| # | Issue | File | Notes |
|---|-------|------|-------|
| M1 | Suggestion chips do a full re-run before displaying the question | `concierge_chat.py:60-64` | Handled via `pending_question` + `st.rerun()`. Works but slightly slow. |
| M4 | Bot command center Overview stats are below the chart, requiring scroll | `bot_command_center.py:49-57` | Move the 4 stat cards above the chart. |
| M5 | ~~`ConciergeChat` is instantiated on every message — `anthropic.Anthropic()` client recreated each time~~ **FIXED** — `_get_concierge()` uses `@st.cache_resource` to cache the `ConciergeChat` instance (including the Anthropic client). | `concierge_chat.py:11-14` | Resolved. |

### P3 — Low Priority / Polish

| # | Issue | File | Notes |
|---|-------|------|-------|
| L1 | No loading skeleton for page content | All pages | Add `st.spinner()` at page level. |
| L2 | Handoffs tab may be empty | `bot_command_center.py:82` | Show contextual note ("No handoffs in the last 7 days"). |
| L6 | No favicon beyond `◆` | `app.py:12` | Upload a proper SVG. |

---

## Feature Roadmap

### Wave D — Architecture & Testing

**D1: Type coverage** — add `mypy` to dev dependencies and run `mypy backend/ pages/ components.py charts.py` as a pre-commit check.

**D2: Test coverage for activity filtering** — add tests verifying:
- All activity events have `lead_temperature` in metadata (non-temperature-change events)
- Temperature filter returns correct subset

**D3: Test coverage for pages** — smoke tests that import each page module and call `render()` with a mock provider.

**D4: Streamlit native multipage** — migrate to `st.Page()` / `st.navigation()` (Streamlit 1.36+) for simpler routing and deep-linking.

---

## Architecture Notes

### File Map

```
lyrio_dashboard/
├── app.py                    Entry: config, CSS, sidebar, routing, mode detection
├── theme.py                  CSS injection (fonts, colors, component classes)
├── components.py             Pure HTML render functions (no business logic)
├── charts.py                 Plotly builders (style_chart, area_chart, bar_chart, sparkline)
├── backend/
│   ├── models.py             Frozen dataclasses (all data shapes)
│   ├── data_provider.py      Protocol + factory
│   ├── demo_data.py          DemoDataProvider — seeded random, deterministic
│   ├── live_data.py          LiveDataProvider — reads from GoHighLevel API
│   ├── ghl_client.py         GHLClient — contacts + conversations HTTP client
│   ├── concierge.py          Claude tool_use chat module
│   └── seed_constants.py     Curated RC names, addresses, messages
└── pages/
    ├── concierge_chat.py     Chat UI + ConciergeChat wiring
    ├── bot_command_center.py Bot cards + tabs
    ├── cost_roi_tracker.py   Month selector + metrics + charts
    ├── lead_activity_feed.py Filter bar + event feed
    └── lead_browser.py       Searchable lead table + detail panel
```

### Data Flow

```
app.py
  └── _get_provider()  (@st.cache_resource)
        ├── [ghl] secrets present → LiveDataProvider(GHLClient)
        └── fallback → DemoDataProvider(seed=20260221)
              ├── _generate_leads() — 18 leads, deterministic
              ├── _generate_activity() — 50 events
              ├── _generate_conversations() — 18 snippets
              └── _generate_handoffs() — 5-8 events

pages/* → components.py / charts.py → provider.get_*()

concierge_chat.py
  └── ConciergeChat(provider, api_key)
        └── anthropic.Anthropic().messages.create(tools=[5 tools])
              ├── on_tool_call() → st.empty() indicator in chat bubble
              └── _execute_tool() → provider.get_*()
```

### CSS Architecture

The theme uses CSS custom properties (`--accent`, `--hot`, etc.) injected via `theme.py`. Component HTML uses both:
- **Class-based**: `.lyrio-card`, `.lyrio-stat-value`, `.lyrio-stat-label`, `.lyrio-mono` — defined in `theme.py`, used in `components.py`
- **Inline styles**: All HTML in components uses inline styles for layout/color specifics not covered by the classes

**Important:** `st.markdown` HTML blocks terminate at blank lines (CommonMark spec). Never put a blank line inside an f-string HTML template.

### Concierge Tool Loop

```
user message
  → messages.create(tools=_TOOLS)
  → if stop_reason == "tool_use":
        on_tool_call(block.name) → UI indicator
        execute all tool_use blocks
        append assistant content + tool_results to messages
        loop (max 3 rounds)
  → return first block with .text attribute
```

The concierge maintains no internal state between calls — full history is passed in on each `chat()` call. Tool results are NOT persisted in `st.session_state.chat_messages`.

---

## Demo Data Reference

| Metric | Value |
|--------|-------|
| Total leads | 18 (3 hot, 6 warm, 9 cold) |
| Total conversations | ~46 |
| Monthly AI cost | ~$0.42 |
| ROI estimate | ~43,000x |
| Cost per lead | ~$0.023 |
| Cost per conversation | ~$0.009 |
| Bot response times | Seller 2.4s · Buyer 3.4s · Lead 2.7s |
| Success rates | Seller 88% · Buyer 82% · Lead 91% |

Pricing model (Anthropic Claude Sonnet): $3/MTok input · $15/MTok output · $0.30/MTok cache reads.

---

## Testing

```bash
# Run all tests
.venv/bin/python3 -m pytest tests/ -v

# Run specific suites
.venv/bin/python3 -m pytest tests/test_demo_data.py -v
.venv/bin/python3 -m pytest tests/test_concierge.py -v
```

25 tests, all passing. Target coverage: 80%+. Next gaps: activity filter logic (D2), page smoke tests (D3).

---

## Deploy

- **Platform:** Streamlit Cloud (`share.streamlit.io`, account: chunkytortoise)
- **Branch:** `main` — auto-deploys on push
- **Secrets:** `[anthropic] api_key` · `[ghl] api_key` · `[ghl] location_id` (set in Streamlit Cloud dashboard)
- **Python version:** 3.12 (set in runtime config)
- **Mode:** Live if GHL secrets present, Demo fallback

**Feb 23 Zoom demo flow:** Chat → "How many hot leads?" (tool_use demo) → Leads → filter Hot → Maria Gonzalez detail → Bots → "6 leads qualified today" → Costs → "$0.42 / 42,857x ROI"
