# Lyrio Bot Guide — Where Your Bots Live & How to Edit Them

**Last updated:** February 2026
**Your dashboard:** https://lyrio-jorge.streamlit.app

---

## Overview

Your Lyrio setup has **two layers**:

1. **GoHighLevel (GHL)** — where your bots actually run, send SMS, and manage contacts
2. **Lyrio Dashboard** — reads from GHL and gives you visibility, stats, and the AI concierge

Editing bot *behavior* (messages, workflows, triggers) happens in **GHL**.
Editing what the *dashboard shows or how it analyzes your data* happens in the **Lyrio codebase**.

---

## Your 3 Bots

| Bot | Purpose | Handles |
|-----|---------|---------|
| **Seller Bot** | Qualifies homeowners considering selling | Computes FRS (Financial Readiness Score 0–100). Hot ≥ 80, Warm 40–79, Cold < 40 |
| **Buyer Bot** | Qualifies home buyers | Financial readiness + property preferences |
| **Lead Bot** | Initial outreach + routing | First contact, then routes to Seller or Buyer Bot |

---

## Where the Bots Live in GHL

Log in at **app.gohighlevel.com** → your Rancho Cucamonga sub-account.

### 1. Workflows (bot logic — messages, triggers, branching)

**Automation → Workflows**

This is where each bot's conversation scripts live. Each bot is a separate workflow (or set of workflows). You'll see triggers like "Contact created via SMS" and action steps like "Send message → Wait for reply → Branch on answer."

- To change **what a bot says** → edit the SMS message steps inside the workflow
- To change **when a bot fires** → edit the trigger at the top of the workflow
- To change **routing logic** (e.g. when Lead Bot hands off to Seller Bot) → edit the branch/condition steps

### 2. Tags (temperature & bot assignment)

**Contacts → any contact → Tags field**

Lyrio reads these GHL tags to determine lead temperature and which bot is assigned:

| Tag | Meaning |
|-----|---------|
| `hot-seller`, `hot-lead`, `hot` | 🔴 Hot lead |
| `warm-seller`, `warm-lead`, `warm` | 🟡 Warm lead |
| *(no hot/warm tag)* | 🔵 Cold lead |
| `seller-qualified`, `hot-seller`, `warm-seller`, `cold-seller` | Assigned to Seller Bot |
| `buyer-lead`, `hot-buyer`, `warm-buyer`, `cold-buyer` | Assigned to Buyer Bot |
| `needs qualifying`, `lead-bot` | Assigned to Lead Bot |

GHL applies these tags automatically via workflow actions. You can also apply them manually on any contact.

**To change how a lead gets tagged** → edit the "Add Tag" action steps inside the relevant workflow.

### 3. Custom Fields (scores & timeline)

**Settings → Custom Fields** (or visible on each contact record)

Lyrio reads three custom fields from each contact:

| Field ID | What It Stores | Where Set |
|----------|---------------|-----------|
| `YJ9EDgHQB3UoKnnTSoUO` | Bot type (`seller` / `buyer` / `lead`) | Set by workflow |
| `FpLprsZwqpYTyUxYzgpS` | Lead score (FRS/PCS, 0–100) | Set by workflow |
| `7GGX1W3EKa51AsPU1wbP` | Timeline (e.g. "3–6 months") | Set by workflow |

To change what score gets recorded or how timeline is captured → edit the "Update Custom Field" action in the relevant workflow.

### 4. Conversations & SMS

**Conversations** tab in GHL

All SMS threads between your bots and leads are here. You can read, reply manually, or review what the bot said.

---

## What You Can Edit and Where

### Change a bot's SMS messages
**GHL → Automation → Workflows → [Bot workflow] → edit message steps**

Find the SMS action steps and update the text. Changes take effect on the next new conversation.

### Change qualification thresholds (hot/warm/cold)
Two places depending on what you want:

- **GHL tagging logic** (what tags get applied): edit the branch conditions in the workflow
- **Dashboard display** (how Lyrio reads those tags): edit `backend/live_data.py` lines 35–40 — the `_HOT_TAGS` and `_WARM_TAGS` sets

### Change the AI Concierge's personality or knowledge
**File:** `backend/concierge.py` — the `_SYSTEM_PROMPT` variable at the top

This is the instruction set given to Claude every time you ask the concierge a question. You can edit:
- Jorge's market context (neighborhoods, median prices)
- Tone and response style
- What each bot's purpose is described as

### Change what data the concierge can access
**File:** `backend/concierge.py` — the `_TOOLS` list

Each tool is a function the AI can call (get bot status, get lead detail, etc.). Adding a new tool requires both adding it to `_TOOLS` and implementing it in the `_execute_tool` method below.

### Change bot response time targets or names shown in dashboard
**File:** `backend/live_data.py`

```python
_BOT_NAMES = {"seller": "Seller Bot", "buyer": "Buyer Bot", "lead": "Lead Bot"}
_BOT_RESP_TIMES = {"seller": 2.4, "buyer": 3.1, "lead": 2.7}
```

### Change pricing used for cost calculations
**File:** `backend/demo_data.py` (demo) or `backend/live_data.py` (live) — top of file

```python
_INPUT_COST_PER_MTOK = 3.0    # $ per million input tokens
_OUTPUT_COST_PER_MTOK = 15.0  # $ per million output tokens
_CACHE_COST_PER_MTOK = 0.30   # $ per million cache read tokens
```

---

## Quick Reference — Edit by Goal

| I want to… | Go to |
|-----------|-------|
| Change what my bot says to leads | GHL → Automation → Workflows |
| Change when a bot fires or who it contacts | GHL → Automation → Workflows → Trigger |
| See all conversations | GHL → Conversations |
| Manually tag a lead as hot/warm/cold | GHL → Contacts → [lead] → Tags |
| Change the AI concierge's tone/knowledge | `backend/concierge.py` → `_SYSTEM_PROMPT` |
| Add a new question the concierge can answer | `backend/concierge.py` → `_TOOLS` + `_execute_tool` |
| Change how temperature tags are read | `backend/live_data.py` → `_HOT_TAGS`, `_WARM_TAGS` |
| Update bot names shown in dashboard | `backend/live_data.py` → `_BOT_NAMES` |
| Update AI pricing for cost calculations | `backend/live_data.py` → top constants |

---

## Switching Dashboard from Demo to Live Data

The dashboard currently runs in **demo mode** (illustrative data for presentations).

To connect it to your real GHL data:

1. Go to **Streamlit Cloud** → your app → **Settings → Secrets**
2. Change `mode = "demo"` to `mode = "live"`
3. Make sure `[ghl] api_key` and `[ghl] location_id` are set
4. Click **Save** → **Reboot app**

To switch back to demo (e.g. before a presentation): change `mode = "live"` back to `mode = "demo"` and reboot.

---

*Questions about any of this → ask Cayman.*
