"""Tests for bot_tone page — auth headers and secrets-based URL."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_secrets(api_url: str = "https://jorge-api.example.com", admin_api_key: str = "test-key-abc") -> dict:
    """Build a minimal secrets dict matching the jorge_bot section."""
    return {"jorge_bot": {"api_url": api_url, "admin_api_key": admin_api_key}}


def _load_module(secrets: dict):
    """Import (or reload) bot_tone with st.secrets patched."""
    import importlib
    import sys

    mock_st = MagicMock()
    mock_st.secrets = secrets
    mock_components = MagicMock()

    # Ensure a clean reload each time
    for mod in list(sys.modules.keys()):
        if "bot_tone" in mod:
            del sys.modules[mod]

    with patch.dict("sys.modules", {"streamlit": mock_st, "components": mock_components}):
        import pages.bot_tone as module
    return module, mock_st


def test_auth_headers_uses_secrets():
    """_auth_headers() must return X-Admin-Key from secrets."""
    secrets = _make_secrets(admin_api_key="my-secret-key")
    module, mock_st = _load_module(secrets)
    mock_st.secrets = secrets
    with patch.object(module, "st", mock_st):
        headers = module._auth_headers()
    assert headers == {"X-Admin-Key": "my-secret-key"}


def test_api_url_from_secrets():
    """_api_url() must return the URL from secrets, not a hardcoded value."""
    secrets = _make_secrets(api_url="https://custom-api.example.com")
    module, mock_st = _load_module(secrets)
    mock_st.secrets = secrets
    with patch.object(module, "st", mock_st):
        url = module._api_url()
    assert url == "https://custom-api.example.com"


def test_fetch_settings_sends_auth_header():
    """_fetch_settings() must include X-Admin-Key in the GET request."""
    secrets = _make_secrets(api_url="https://jorge-api.test", admin_api_key="key-xyz")
    module, mock_st = _load_module(secrets)
    mock_st.secrets = secrets

    captured_kwargs: dict = {}

    def fake_get(url, **kwargs):
        captured_kwargs.update(kwargs)
        resp = MagicMock()
        resp.json.return_value = {"seller": {}, "buyer": {}, "lead": {}}
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(module, "st", mock_st), patch("requests.get", fake_get):
        result = module._fetch_settings()

    assert result == {"seller": {}, "buyer": {}, "lead": {}}
    assert captured_kwargs.get("headers", {}).get("X-Admin-Key") == "key-xyz"


def test_fetch_settings_http_error_no_url_exposed():
    """On HTTP error, st.warning must not contain the raw API URL."""
    import requests as real_requests

    secrets = _make_secrets(api_url="https://jorge-realty-ai-xxdf.onrender.com", admin_api_key="key")
    module, mock_st = _load_module(secrets)
    mock_st.secrets = secrets
    mock_st.session_state.get.return_value = None  # no cache

    def fake_get(url, **kwargs):
        raise real_requests.HTTPError("403 Forbidden")

    warning_calls: list = []
    mock_st.warning.side_effect = lambda msg, **kw: warning_calls.append(msg)

    with patch.object(module, "st", mock_st), patch("requests.get", fake_get):
        result = module._fetch_settings()

    assert result is None
    # Warning must not expose the raw API URL
    for msg in warning_calls:
        assert "jorge-realty-ai-xxdf" not in str(msg)
        assert "/admin/settings" not in str(msg)


def test_reset_state_uses_new_admin_endpoint():
    """_reset_state() must call DELETE /admin/reset-state/{bot}/{contact_id}."""
    secrets = _make_secrets(api_url="https://jorge-api.test", admin_api_key="key-xyz")
    module, mock_st = _load_module(secrets)
    mock_st.secrets = secrets

    captured: dict = {}

    def fake_delete(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        resp = MagicMock()
        resp.json.return_value = {"status": "ok"}
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(module, "st", mock_st), patch("requests.delete", fake_delete):
        result = module._reset_state("buyer", "contact-abc")

    assert result is True
    assert captured["url"] == "https://jorge-api.test/admin/reset-state/buyer/contact-abc"
    assert captured["headers"].get("X-Admin-Key") == "key-xyz"
