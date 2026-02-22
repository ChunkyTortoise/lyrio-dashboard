"""GHL API v2 client for Lyrio dashboard."""
from __future__ import annotations

import time
from typing import Any

import requests

_BASE = "https://services.leadconnectorhq.com"
_VERSION = "2021-07-28"
_MAX_CONTACTS = 500


class GHLClient:
    """Thin wrapper around GHL REST API v2 with simple rate limiting (10 req/s)."""

    def __init__(self, api_key: str, location_id: str) -> None:
        self._location_id = location_id
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Version": _VERSION,
            "Content-Type": "application/json",
        })
        self._last_request: float = 0.0

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET with 100ms rate limiting floor."""
        gap = time.monotonic() - self._last_request
        if gap < 0.1:
            time.sleep(0.1 - gap)
        self._last_request = time.monotonic()
        resp = self._session.get(f"{_BASE}{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_contacts(self, limit: int = _MAX_CONTACTS) -> list[dict]:
        """Fetch contacts for this location, paginated up to limit."""
        contacts: list[dict] = []
        params: dict[str, Any] = {
            "locationId": self._location_id,
            "limit": min(limit, 100),
        }
        while len(contacts) < limit:
            data = self._get("/contacts/", params)
            batch = data.get("contacts", [])
            contacts.extend(batch)
            meta = data.get("meta", {})
            next_id = meta.get("startAfterId")
            if not batch or not next_id:
                break
            params["startAfterId"] = next_id
        return contacts[:limit]

    def get_conversations(self, limit: int = 100) -> list[dict]:
        """Fetch recent SMS conversations for this location."""
        data = self._get("/conversations/search", {
            "locationId": self._location_id,
            "limit": min(limit, 100),
            "type": "SMS",
        })
        return data.get("conversations", [])

    def get_conversation_messages(self, conversation_id: str, limit: int = 10) -> list[dict]:
        """Fetch messages for a specific conversation."""
        data = self._get(f"/conversations/{conversation_id}/messages", {"limit": limit})
        return data.get("messages", {}).get("messages", [])
