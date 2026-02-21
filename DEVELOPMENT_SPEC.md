# Lyrio Dashboard — Development Spec

**As of:** 2026-02-21
**Live URL:** https://lyrio-jorge.streamlit.app
**Repo:** github.com/ChunkyTortoise/lyrio-dashboard
**Stack:** Python 3.12 · Streamlit 1.32+ · Anthropic claude-sonnet-4-20250514 · Plotly · Pandas

---

## Current State

The Lyrio Dashboard is deployed and functional with 4 pages: Concierge Chat, Bot Command Center, Cost & ROI Tracker, and Lead Activity Feed. All 25 tests pass. The app is in demo mode — all data is deterministically generated from a seeded random provider.

---

## Recently Fixed (2026-02-21)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `</div>` rendered as literal text in Costs and Bots metric cards | CommonMark terminates HTML blocks at blank lines; `{delta_html}=""` created a blank line before `</div>` | Collapsed `render_stat()` and `render_page_title()` templates to single-line HTML |
| Bot area chart showed hardcoded 35/22/43% splits | Fixed percentages in `bot_command_center.py` | Derive proportions from `BotStatus.conversations_total` |
| Temperature filter on Activity page had no effect | `lead_temperature` key missing from event metadata | Added `lead_temperature` to metadata for all non-temperature-change events |

---

## Remaining Issues

### P0 — Functional Bugs

None open.

### P1 — High Priority

| # | Issue | File | Fix |
|---|-------|------|-----|
| H1 | Month selector only filters the bar chart, not the 4 metric cards | `cost_roi_tracker.py:21` | Demo limitation: `DemoDataProvider` only has one month of data. Short-term: show the selected month label next to each metric. Long-term: `LiveDataProvider` will query by month. |
| H2 | `rng` state mutates across `get_bot_statuses()` calls | `demo_data.py:263` | `avg_response_time_sec` calls `self._rng.uniform()` at call time, making values non-deterministic after the first call. Pre-compute response times in `_generate_leads()` or `__init__`. |
| H3 | `DemoDataProvider` is re-instantiated on every Streamlit re-run | `app.py:38` | Wrap `create_data_provider()` with `@st.cache_resource` to avoid re-seeding and re-generating on every interaction. |
| H4 | `_NOW` is a module-level constant frozen at `datetime(2026, 2, 21)` | `demo_data.py:38` | Demo data always appears 0–48h old relative to Feb 21 regardless of actual date. Use `datetime.now()` with a date-seeded `random.Random` for realistic relative timestamps. |

### P2 — Medium Priority

| # | Issue | File | Notes |
|---|-------|------|-------|
| M1 | Suggestion chips in Concierge don't appear once chat has messages (correct) but the empty state layout is 2x2 `st.button` — tapping a chip does a full re-run before displaying the question in chat | `concierge_chat.py:60-64` | Already handled via `pending_question` session state + `st.rerun()`. Works but feels slightly slow. Consider using `st.chat_input` value injection when Streamlit supports it natively. |
| M2 | Activity feed "Showing N of M" counts incorrectly after filters because `shown` is pulled from session state before filtering | `lead_activity_feed.py:34-61` | Displayed count says "Showing 20 of 40" but after filters that 40 may be much smaller. Fix: display `min(shown, len(filtered)) of len(filtered)` (already done) but ensure `shown` resets when filters change. |
| M3 | Concierge chat history grows unbounded in session state | `concierge_chat.py:89-103` | Add a `Clear chat` button. Optionally cap history at last N turns before sending to API. |
| M4 | Bot command center "Overview" stats (total conversations, avg response, etc.) are below the chart, requiring scroll | `bot_command_center.py:49-57` | Move the 4 stat cards above the tabs or at minimum above the chart. |
| M5 | `ConciergeChat` is instantiated on every message — `anthropic.Anthropic()` client is recreated each time | `concierge_chat.py:95` | Cache client or lift `ConciergeChat` instantiation into `@st.cache_resource`. |

### P3 — Low Priority / Polish

| # | Issue | File | Notes |
|---|-------|------|-------|
| L1 | No loading skeleton for page content — first load feels blank briefly | All pages | Add `st.spinner()` or shimmer state at page level. |
| L2 | Handoffs tab in Bot Command Center may be empty if `get_handoff_events()` returns 0 | `bot_command_center.py:82` | The info message is correct but could show a more contextual note ("No handoffs in the last 7 days"). |
| L3 | `cost_roi_tracker.py` "Top contacts by cost" uses `message_count × cost_per_conversation` as proxy — this double-counts if a lead has multiple conversations with different bots | `cost_roi_tracker.py:87` | Acceptable approximation for demo; fix in live mode with actual per-interaction token data. |
| L4 | Session state key `cost_month` (`app.py:29`) is never read — the actual month comes from widget key `cost_month_select` | `app.py:29`, `cost_roi_tracker.py:13` | Remove the unused default from `_DEFAULTS`. |
| L5 | `activity_items_shown` resets to 20 if the user navigates away and back | `app.py:30`, `lead_activity_feed.py:34` | Acceptable behavior. |
| L6 | No favicon beyond `◆` — could use a real SVG | `app.py:12` | Minor. Upload a proper SVG to the repo and reference it. |

---

## Feature Roadmap

### Wave A — Demo Polish (before next client demo)

**A1: Provider caching** (`app.py`)
```python
@st.cache_resource
def _get_provider():
    return create_data_provider(mode="demo")

provider = _get_provider()
```
Prevents re-seeding on every Streamlit re-run (interaction, widget change, etc.).

**A2: Pre-compute response times** (`backend/demo_data.py`)
Move `self._rng.uniform(rt_lo, rt_hi)` into `_generate_leads()` so response times are stable across multiple `get_bot_statuses()` calls.

**A3: Month label on metric cards** (`pages/cost_roi_tracker.py`)
Show the period label next to the "Total LLM Spend" heading so it's clear the numbers are for Feb 2026, not the selected month.

**A4: Clear chat button** (`pages/concierge_chat.py`)
Add `if st.button("Clear"):` that clears `st.session_state.chat_messages` and re-runs.

---

### Wave B — UX Improvements

**B1: Lead browser** — new tab or page showing all 18 leads in a searchable table with temperature pills, FRS scores, bot assignment, last contact. Currently there's no way to browse all leads; you have to know a name to use `get_lead_detail`.

Proposed layout:
- Filter: temperature (hot/warm/cold/all), bot, FRS range
- Table: Name · Temperature · FRS · Bot · Stage · Last Contact · Actions
- Click a row → modal or detail panel with full `LeadDetail`

**B2: Sidebar lead count context** — update `render_sidebar_context()` for the Bots page to show today's qualified leads, not just "N bots active — last sync 2m ago".

**B3: Activity filter persistence** — activity filters reset on page navigation. Save to `st.session_state["activity_filters"]` on every widget change and restore on page load.

**B4: Concierge tool call visibility** — show a subtle "🔍 Checking lead data..." indicator while tool calls are in flight (between tool_use and final text_delta). Adds transparency without cluttering the chat.

---

### Wave C — Live Data Integration

The `LiveDataProvider` stub in `backend/live_data.py` needs implementation. When Jorge's Render service is live and healthy, Lyrio can pull real data instead of demo data.

**C1: GHL / Render API client** (`backend/live_data.py`)

Methods to implement (matching `DataProvider` protocol):
- `get_bot_statuses()` — call `GET /api/ghl/health` + contact/conversation stats from GHL API
- `get_lead_summary()` — GHL contact search filtered by tag (`Hot-Seller`, `Warm-Buyer`, etc.)
- `get_cost_breakdown()` — read from `llm_cost_log` table (already implemented in `cost_tracker.py`)
- `get_recent_activity()` — GHL conversation webhook history
- `get_lead_detail(name)` — GHL contact lookup by name
- `get_daily_trends(days)` — aggregate from `llm_cost_log` + GHL conversation history

**C2: Mode toggle** (`app.py`)
Add a sidebar control (or `st.secrets`-based flag) to switch between `demo` and `live`:
```python
mode = "live" if st.secrets.get("render", {}).get("base_url") else "demo"
provider = create_data_provider(mode=mode)
```

**C3: Data freshness indicator** (`components.py`)
Replace the static "last sync 2m ago" in `render_sidebar_context()` with an actual timestamp from the live provider.

**C4: Caching with TTL** (`backend/live_data.py`)
Wrap expensive GHL API calls in `@st.cache_data(ttl=60)` to avoid hitting the API on every Streamlit re-run.

---

### Wave D — Architecture & Testing

**D1: Type coverage** — add `mypy` to dev dependencies and run `mypy backend/ pages/ components.py charts.py` as a pre-commit check. Most functions already have return type annotations; fill in the missing `provider` parameter types.

**D2: Test coverage for activity filtering** — add tests in `tests/test_demo_data.py` that verify:
- All activity events have `lead_temperature` in metadata (non-temperature-change events)
- Temperature filter returns correct subset

**D3: Test coverage for pages** — add smoke tests that import each page module and call `render()` with a mock provider. Prevents import errors from breaking the live app silently.

**D4: Streamlit native multipage** — currently using manual `if page == "X":` routing with a radio button. Migrating to `st.Page()` / `st.navigation()` (Streamlit 1.36+) would simplify `app.py` and allow deep-linking to specific pages.

---

## Architecture Notes

### File Map

```
lyrio_dashboard/
├── app.py                    Entry: config, CSS, sidebar, routing
├── theme.py                  CSS injection (fonts, colors, component classes)
├── components.py             Pure HTML render functions (no business logic)
├── charts.py                 Plotly builders (style_chart, area_chart, bar_chart, sparkline)
├── backend/
│   ├── models.py             Frozen dataclasses (all data shapes)
│   ├── data_provider.py      Protocol + factory
│   ├── demo_data.py          DemoDataProvider — seeded random, deterministic
│   ├── live_data.py          LiveDataProvider — stub
│   ├── concierge.py          Claude tool_use chat module
│   └── seed_constants.py     Curated RC names, addresses, messages
└── pages/
    ├── concierge_chat.py     Chat UI + ConciergeChat wiring
    ├── bot_command_center.py Bot cards + tabs
    ├── cost_roi_tracker.py   Month selector + metrics + charts
    └── lead_activity_feed.py Filter bar + event feed
```

### Data Flow

```
app.py
  └── create_data_provider("demo")
        └── DemoDataProvider(seed=20260221)
              ├── _generate_leads() — 18 leads, deterministic
              ├── _generate_activity() — 50 events
              ├── _generate_conversations() — 18 snippets
              └── _generate_handoffs() — 5-8 events

pages/* → components.py / charts.py → provider.get_*()

concierge_chat.py
  └── ConciergeChat(provider, api_key)
        └── anthropic.Anthropic().messages.create(tools=[5 tools])
              └── _execute_tool() → provider.get_*()
```

### CSS Architecture

The theme uses CSS custom properties (`--accent`, `--hot`, etc.) injected via `theme.py`. Component HTML uses both:
- **Class-based**: `.lyrio-card`, `.lyrio-stat-value`, `.lyrio-stat-label`, `.lyrio-mono` — defined in `theme.py`, used in `components.py`
- **Inline styles**: All HTML in components uses inline styles for layout/color specifics not covered by the classes

**Important:** `st.markdown` HTML blocks terminate at blank lines (CommonMark spec). Never put a blank line inside an f-string HTML template — use `variable=""` empty strings on the same line as adjacent content.

### Concierge Tool Loop

```
user message
  → messages.create(tools=_TOOLS)
  → if stop_reason == "tool_use":
        execute all tool_use blocks
        append assistant content + tool_results to messages
        loop (max 3 rounds)
  → return first block with .text attribute
```

The concierge maintains no internal state between calls — full history is passed in on each `chat()` call. Tool results are added to the messages list temporarily and are NOT persisted in `st.session_state.chat_messages`.

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
| Bot response times | Seller 2-3s · Buyer 3-4s · Lead 2-3s |
| Success rates | Seller 88% · Buyer 82% · Lead 91% |

Pricing model (Anthropic Claude Sonnet): $3/MTok input · $15/MTok output · $0.30/MTok cache reads.

---

## Testing

```bash
# Run all tests
/opt/homebrew/bin/python3.12 -m pytest tests/ -v

# Run specific suites
/opt/homebrew/bin/python3.12 -m pytest tests/test_demo_data.py -v
/opt/homebrew/bin/python3.12 -m pytest tests/test_concierge.py -v
```

25 tests, all passing. Target coverage: 80%+. Next test gaps to fill: activity filter logic (D2) and page smoke tests (D3).

---

## Deploy

- **Platform:** Streamlit Cloud (`share.streamlit.io`, account: chunkytortoise)
- **Branch:** `main` — auto-deploys on push
- **Secrets:** `[anthropic] api_key` set in Streamlit Cloud dashboard
- **Python version:** 3.12 (set in runtime config)

Show Jorge at Feb 23 Zoom: open https://lyrio-jorge.streamlit.app → Chat page → ask "How many hot leads?" → watch the concierge call `get_lead_summary` and return "3 hot leads".
