# Lyrio Dashboard — Configuration Guide

## How to Access Files

All files live inside the `lyrio_dashboard/` folder on the developer's machine. For changes to take effect on the **live app** at `lyrio-analytics.streamlit.app`, the developer pushes updates to GitHub and Streamlit Cloud rebuilds automatically. You don't edit files directly on the live site.

---

## 1. Secrets & API Keys
**File: `.streamlit/secrets.toml`** _(not visible in GitHub — stored privately)_

This is the most important file. It holds all sensitive credentials.

| What | Variable | Current Value | How to Change |
|------|----------|---------------|---------------|
| **Anthropic API Key** (powers the AI Chat) | `[anthropic] api_key` | Your `sk-ant-...` key | Replace the value in this file, or get a new key at console.anthropic.com |
| **GHL API Key** (connects to GoHighLevel) | `[ghl] api_key` | `pit-688beb58...` | Replace with a new key from GHL → Settings → API Keys |
| **GHL Location ID** (your specific GHL account location) | `[ghl] location_id` | `3xt4qayAh35BlDLaUv7P` | Find this in GHL → Settings → Business Profile |
| **Data Mode** | `mode` | `"live"` | Change to `"demo"` to force demo mode across all pages |

> If you rotate your GHL API key, update it here. If you get a new Anthropic key, update it here.

---

## 2. App Behavior Defaults
**File: `app.py`** — lines 25–36

These control what the app shows when it first loads.

| Setting | Default | What It Does |
|---------|---------|--------------|
| `page` | `"Chat"` | Which page opens first |
| `cost_month` | `"2026-02"` | Default month shown on the Costs page |
| `activity_items_shown` | `20` | How many events show in the Activity feed |
| `data_mode` | `"Demo"` | Starting mode (Demo or Live) |

---

## 3. AI Chat Settings
**File: `backend/concierge.py`** — lines 166–167

| Setting | Current Value | What It Does | How to Change |
|---------|--------------|--------------|---------------|
| AI Model | `claude-sonnet-4-20250514` | Which Claude model answers questions | Change to a different model ID (e.g. Opus for smarter, Haiku for cheaper) |
| Max Tokens | `1024` | Max length of AI responses | Raise this number for longer answers |

The **chat suggestion buttons** (the quick-tap prompts on the Chat page) are in `pages/concierge_chat.py` lines 15–20. You can change the wording of those four suggestion buttons there.

---

## 4. Demo Data (Demo mode)
**File: `backend/demo_data.py`** and **`seed_constants.py`**

| Setting | Value | What It Controls |
|---------|-------|-----------------|
| Random Seed | `20260221` | Which "random" data gets generated — changing this changes all the names, scores, etc. |
| Total Leads | 18 | The 18 sample lead names |
| Hot / Warm / Cold split | 3 / 6 / 9 | How many leads fall in each category |
| Activity events shown | 50 | Events in the Activity Feed |
| Lead names | 18 hardcoded names | Maria Gonzalez, David Chen, etc. (in `seed_constants.py`) |
| Addresses | 18 Rancho Cucamonga area addresses | Listed in `seed_constants.py` |

> Demo data is **illustrative only** — it doesn't affect your real GHL data.

---

## 5. Cost & ROI Calculation
**Files: `backend/demo_data.py`** (demo) and **`backend/live_data.py`** (live)

These numbers drive the Cost & ROI Tracker page.

| Setting | Value | What It Means |
|---------|-------|--------------|
| Claude input cost | `$3.00 / 1M tokens` | Anthropic's pricing for input |
| Claude output cost | `$15.00 / 1M tokens` | Anthropic's pricing for output |
| Average commission | `$18,000` | Assumed 3% on a $600K sale — adjust if your average deal size differs |
| Expected closed deals | `1` per period | Used to calculate ROI |

> If your average deal commission changes, update the `$18,000` figure.

---

## 6. Live Mode — GoHighLevel Field Mappings
**File: `backend/live_data.py`** — lines 24–54

These are GHL-specific IDs that must match **your** GHL account exactly.

| Item | Current ID | What It Is |
|------|-----------|-----------|
| Bot Type custom field | `YJ9EDgHQB3UoKnnTSoUO` | GHL custom field that stores which bot handled a lead |
| Lead Score custom field | `FpLprsZwqpYTyUxYzgpS` | GHL custom field for the lead's score |
| Timeline custom field | `7GGX1W3EKa51AsPU1wbP` | GHL custom field for buyer/seller timeline |
| Hot Seller Workflow | `wf-hot-seller-placeholder` | **Placeholder** — needs your real GHL workflow ID |
| Warm Seller Workflow | `wf-warm-seller-placeholder` | **Placeholder** — needs your real GHL workflow ID |
| Hot Buyer Workflow | `wf-hot-buyer-placeholder` | **Placeholder** — needs your real GHL workflow ID |
| Notify Agent Workflow | `wf-notify-agent-placeholder` | **Placeholder** — needs your real GHL workflow ID |

> The workflow IDs marked "Placeholder" need to be replaced with the actual IDs from your GHL account (GHL → Automations → copy the workflow ID from the URL).

---

## 7. Visual Theme
**File: `.streamlit/config.toml`** and **`theme.py`**

| Setting | Value | How to Change |
|---------|-------|--------------|
| App accent color | `#6366f1` (indigo) | Edit `primaryColor` in `config.toml` |
| Background | Near-black `#05070A` | Edit `backgroundColor` in `config.toml` |
| Hot lead color | Red `#ef4444` | Edit in `theme.py` |
| Warm lead color | Amber `#f59e0b` | Edit in `theme.py` |
| Cold lead color | Blue `#3b82f6` | Edit in `theme.py` |

---

## 8. Quick Reference — What to Update When

| Situation | File to Change | What to Update |
|-----------|---------------|----------------|
| GHL API key rotated | `.streamlit/secrets.toml` | `[ghl] api_key` |
| Anthropic key rotated | `.streamlit/secrets.toml` | `[anthropic] api_key` |
| New GHL location | `.streamlit/secrets.toml` | `[ghl] location_id` |
| Want Live data instead of Demo | `.streamlit/secrets.toml` | `mode = "live"` |
| Average deal commission changed | `backend/demo_data.py` + `live_data.py` | `$18,000` value |
| Connect real GHL workflows | `backend/live_data.py` lines 49–54 | Replace placeholder IDs |
| Change AI response style/length | `backend/concierge.py` lines 166–167 | Model name or `max_tokens` |

---

Bottom line: The only file you'd ever need to give someone new access to update is `.streamlit/secrets.toml` — that's where all credentials live. Everything else is app behavior that a developer would adjust.
