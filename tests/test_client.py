"""Client auth header and request behaviour with mocked requests."""

from unittest.mock import MagicMock, patch

import pytest

from agentrouter.client import (
    AgentRouterClient,
    AgentRouterError,
    _auth_headers,
)


def _resp(status=200, payload=None, text="", content=b'{"ok": true}'):
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.content = content
    if payload is not None:
        m.json.return_value = payload
    else:
        m.json.return_value = {}
    return m


def test_auth_headers_use_bearer():
    h = _auth_headers("sk-123")
    assert h["Authorization"] == "Bearer sk-123"
    assert h["Content-Type"] == "application/json"


def test_list_models_sends_auth_header():
    client = AgentRouterClient(api_key="k1")
    r = _resp(payload={"data": []})
    with patch("agentrouter.client.requests.get", return_value=r) as mock_get:
        client.list_models()
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer k1"
    args, _ = mock_get.call_args
    assert args[0] == "https://agentrouter.org/v1/models"


def test_chat_sends_payload_with_model():
    client = AgentRouterClient(api_key="k1")
    r = _resp(payload={"choices": []})
    with patch("agentrouter.client.requests.post", return_value=r) as mock_post:
        with patch("agentrouter.client.load_config") as mock_cfg:
            mock_cfg.return_value.default_model = None
            client.chat_completions([{"role": "user", "content": "hi"}], model="m1")
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "m1"
    assert kwargs["headers"]["Authorization"] == "Bearer k1"


def test_chat_uses_default_model_from_config():
    client = AgentRouterClient(api_key="k1")
    r = _resp(payload={"choices": []})
    fake_cfg = MagicMock()
    fake_cfg.default_model = "default-m"
    with patch("agentrouter.client.requests.post", return_value=r) as mock_post:
        with patch("agentrouter.client.load_config", return_value=fake_cfg):
            client.chat_completions([{"role": "user", "content": "hi"}])
    assert mock_post.call_args[1]["json"]["model"] == "default-m"


def test_chat_requires_model():
    client = AgentRouterClient(api_key="k1")
    fake_cfg = MagicMock()
    fake_cfg.default_model = None
    with patch("agentrouter.client.load_config", return_value=fake_cfg):
        with pytest.raises(ValueError, match="model is required"):
            client.chat_completions([{"role": "user", "content": "hi"}])


def test_401_maps_to_helpful_error():
    client = AgentRouterClient(api_key="bad")
    r = _resp(status=401, text="unauthorized", content=b"unauthorized")
    with patch("agentrouter.client.requests.get", return_value=r):
        with pytest.raises(AgentRouterError, match="Authentication failed"):
            client.list_models()


def test_404_and_429_mapped():
    client = AgentRouterClient(api_key="k1")
    for status, match in [(404, "Not found"), (429, "Rate limited")]:
        r = _resp(status=status, text="x", content=b"x")
        with patch("agentrouter.client.requests.get", return_value=r):
            with pytest.raises(AgentRouterError, match=match):
                client.list_models()


def test_rejects_foreign_base_url():
    with pytest.raises(ValueError, match="only https://agentrouter.org/v1"):
        AgentRouterClient(api_key="k1", base_url="https://evil.example.com/v1")


def test_missing_key_raises():
    with patch("agentrouter.client.load_config") as mock_cfg:
        mock_cfg.return_value.api_key = None
        mock_cfg.return_value.base_url = "https://agentrouter.org/v1"
        with pytest.raises(AgentRouterError, match="No API key"):
            AgentRouterClient()


def test_timeout_wrapped():
    import requests

    client = AgentRouterClient(api_key="k1")
    with patch("agentrouter.client.requests.get", side_effect=requests.Timeout()):
        with pytest.raises(AgentRouterError, match="timed out"):
            client.list_models()


def test_invalid_json_response():
    client = AgentRouterClient(api_key="k1")
    r = _resp(content=b"not-json{")
    r.json.side_effect = ValueError("bad")
    with patch("agentrouter.client.requests.get", return_value=r):
        with pytest.raises(AgentRouterError, match="Invalid JSON"):
            client.list_models()
