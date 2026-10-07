"""GUI server, update checker, and installer smoke tests (no network)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import threading
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from agentrouter.cli import build_parser
from agentrouter.config import DEFAULT_BASE_URL, Config
from agentrouter.gui_server import GUI_HTML, create_server
from agentrouter.streaming import iter_response_content, iter_sse_content


def _chunk(text):
    return {"choices": [{"delta": {"content": text}}]}


def _start_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base


def _stop_server(server, thread):
    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass
    thread.join(timeout=5)


def _get(base, path):
    req = urllib.request.Request(base + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def _post(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def _fake_config(**kwargs):
    base = {
        "api_key": "sk-test-key-123456789",
        "base_url": DEFAULT_BASE_URL,
        "default_model": "test-model",
        "config_path": None,
    }
    base.update(kwargs)
    return Config(**base)


def test_parser_gui_serve_flags():
    parser = build_parser()
    args = parser.parse_args(["gui", "serve", "--port", "8787", "--open", "--host", "127.0.0.1"])
    assert args.gui_command == "serve"
    assert args.port == 8787
    assert args.open is True
    assert args.host == "127.0.0.1"
    assert callable(getattr(args, "func", None))


def test_parser_gui_serve_defaults():
    parser = build_parser()
    args = parser.parse_args(["gui", "serve"])
    assert args.port == 8787
    assert args.host == "127.0.0.1"
    assert args.open is False


def test_parser_gui_serve_no_open():
    parser = build_parser()
    args = parser.parse_args(["gui", "serve", "--port", "9000", "--no-open"])
    assert args.port == 9000
    assert args.open is False


def test_get_root_returns_html():
    server, thread, base = _start_server()
    try:
        status, headers, body = _get(base, "/")
        assert status == 200
        ctype = headers.get_content_type()
        assert ctype == "text/html"
        text = body.decode("utf-8")
        assert "AgentRouter" in text
        assert "<title>AgentRouter</title>" in text
        assert GUI_HTML in text or "AgentRouter" in GUI_HTML
    finally:
        _stop_server(server, thread)


def test_api_models_mocked():
    fake = _fake_config()
    mock_client = MagicMock()
    mock_client.list_models.return_value = {"data": [{"id": "m1"}]}
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        with patch("agentrouter.gui_server.AgentRouterClient") as mock_cls:
            mock_cls.from_config.return_value = mock_client
            server, thread, base = _start_server()
            try:
                status, headers, body = _get(base, "/api/models")
            finally:
                _stop_server(server, thread)
    assert status == 200
    assert headers.get_content_type() == "application/json"
    data = json.loads(body.decode("utf-8"))
    assert data == {"data": [{"id": "m1"}]}
    mock_client.list_models.assert_called_once()


def test_api_config_mocked():
    fake = _fake_config()
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        server, thread, base = _start_server()
        try:
            status, headers, body = _get(base, "/api/config")
        finally:
            _stop_server(server, thread)
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert data["base_url"] == DEFAULT_BASE_URL
    assert data["default_model"] == "test-model"
    assert data["has_key"] is True
    assert data["api_key"] != "sk-test-key-123456789"
    assert "***" in data["api_key"] or data["api_key"] == "(not set)" or "sk-test" not in data["api_key"]


def test_sse_helpers_parse_data_lines():
    lines = [
        "data: " + json.dumps(_chunk("Hel")),
        "data: " + json.dumps(_chunk("lo")),
        ": ping",
        "",
        "data: [DONE]",
    ]
    assert list(iter_sse_content(lines)) == ["Hel", "lo"]

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps(_chunk("a"))
            yield "data: " + json.dumps(_chunk("b"))
            yield "data: [DONE]"

    assert list(iter_response_content(FakeResp())) == ["a", "b"]


def test_api_chat_sse_relay():
    import io

    from agentrouter.gui_server import GuiHandler

    fake = _fake_config()

    class FakeStream:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps(_chunk("Hel"))
            yield "data: " + json.dumps(_chunk("lo"))
            yield "data: [DONE]"

        def close(self):
            pass

        @property
        def text(self):
            return ""

    body_bytes = json.dumps({"model": "m1", "messages": [{"role": "user", "content": "hi"}]}).encode()
    handler = GuiHandler.__new__(GuiHandler)
    handler.headers = {"Content-Length": str(len(body_bytes))}
    handler.rfile = io.BytesIO(body_bytes)
    handler.wfile = io.BytesIO()
    handler._status = None
    handler._headers = {}

    def _send_response(code, message=None):
        handler._status = code

    def _send_header(key, value):
        handler._headers[key] = value

    handler.send_response = _send_response  # type: ignore[method-assign]
    handler.send_header = _send_header  # type: ignore[method-assign]
    handler.end_headers = lambda: None  # type: ignore[method-assign]
    handler._cors = lambda: None  # type: ignore[method-assign]

    with patch("agentrouter.gui_server.load_config", return_value=fake):
        with patch("agentrouter.gui_server.requests.post", return_value=FakeStream()) as mock_post:
            with patch(
                "agentrouter.gui_server.iter_response_content",
                side_effect=lambda resp: iter_response_content(resp),
            ) as mock_iter:
                handler._handle_chat()
    assert mock_post.call_count == 1
    assert mock_iter.call_count == 1
    assert handler._status == 200
    assert handler._headers.get("Content-Type") == "text/event-stream"
    text = handler.wfile.getvalue().decode("utf-8")
    assert "data: [DONE]" in text
    assert '"content"' in text
    assert "Hel" in text
    data_lines = [line for line in text.splitlines() if line.startswith("data:")]
    assert len(data_lines) >= 3
    payloads = []
    for line in data_lines:
        raw = line[len("data:"):].strip()
        if raw == "[DONE]":
            continue
        payloads.append(json.loads(raw))
    assert any("Hel" in json.dumps(p) for p in payloads)
    assert any("lo" in json.dumps(p) for p in payloads)


def test_agentrouter_only_guard_rejects_foreign():
    from agentrouter.config import validate_base_url

    try:
        validate_base_url("https://evil.example.com/v1")
    except ValueError as exc:
        assert "only https://agentrouter.org/v1" in str(exc)
    else:
        raise AssertionError("expected ValueError for foreign base_url")

    try:
        validate_base_url("http://agentrouter.org/v1")
    except ValueError as exc:
        assert "only https://agentrouter.org/v1" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-https base_url")

    foreign = _fake_config(base_url="https://evil.example.com/v1")
    with patch("agentrouter.gui_server.load_config", return_value=foreign):
        server, thread, base = _start_server()
        try:
            status, _, body = _get(base, "/api/models")
        finally:
            _stop_server(server, thread)
    assert status == 400
    assert "only https://agentrouter.org/v1" in body.decode("utf-8")


def test_update_offline_safe_returns_current():
    from agentrouter import __version__ as current
    from agentrouter import update as update_mod

    with patch("agentrouter.update._read_cache", return_value=(None, None)):
        with patch("agentrouter.update._write_cache", return_value=None):
            with patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("offline"),
            ):
                has_update, latest, cur = update_mod.check_for_updates()
    assert has_update is False
    assert cur == current
    assert latest == current


def test_installer_smoke():
    root = pathlib.Path(__file__).resolve().parent.parent
    installer = root / "install.sh"
    assert installer.exists()
    text = installer.read_text(encoding="utf-8")
    result = subprocess.run(["bash", "-n", str(installer)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "sudo" not in text
    assert "venv" in text.lower()
    assert "python3 -m venv" in text
    assert "ln -sf" in text
    assert "agentrouter" in text


def test_no_arg_main_launches_serve_defaults():
    from agentrouter import cli as cli_mod

    with patch("agentrouter.gui_server.serve") as mock_serve:
        with patch.object(cli_mod, "_maybe_auto_check", return_value=None):
            rc = cli_mod.main([])
    assert rc == 0
    mock_serve.assert_called_once_with(8787, "127.0.0.1")


def test_parser_serve_alias_flags():
    parser = build_parser()
    args = parser.parse_args(["serve", "--port", "9000", "--host", "0.0.0.0", "--open"])
    assert args.port == 9000
    assert args.host == "0.0.0.0"
    assert args.open is True
    assert callable(getattr(args, "func", None))


def test_parser_serve_alias_defaults():
    parser = build_parser()
    args = parser.parse_args(["serve"])
    assert args.port == 8787
    assert args.host == "127.0.0.1"
    assert args.open is False
    assert callable(getattr(args, "func", None))


def test_parser_bare_gui_defaults_to_serve():
    from agentrouter.cli import cmd_gui_serve

    parser = build_parser()
    args = parser.parse_args(["gui"])
    assert args.gui_command is None
    assert args.port == 8787
    assert args.host == "127.0.0.1"
    assert args.open is False
    assert getattr(args, "func", None) == cmd_gui_serve


def test_api_health_returns_ok():
    fake = _fake_config()
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        server, thread, base = _start_server()
        try:
            status, headers, body = _get(base, "/api/health")
        finally:
            _stop_server(server, thread)
    assert status == 200
    assert headers.get_content_type() == "application/json"
    assert json.loads(body.decode("utf-8")) == {"status": "ok"}


def test_favicon_returns_204():
    fake = _fake_config()
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        server, thread, base = _start_server()
        try:
            status, _, body = _get(base, "/favicon.ico")
        finally:
            _stop_server(server, thread)
    assert status == 204
    assert body == b""


def test_api_unknown_returns_404_json():
    fake = _fake_config()
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        server, thread, base = _start_server()
        try:
            status, headers, body = _get(base, "/api/nope")
        finally:
            _stop_server(server, thread)
    assert status == 404
    assert headers.get_content_type() == "application/json"
    data = json.loads(body.decode("utf-8"))
    assert data["error"] == "not found"
    assert data["path"] == "/api/nope"


def test_frontend_chatgpt_markers_no_cdn():
    assert "New chat" in GUI_HTML
    assert 'id="composer"' in GUI_HTML
    assert "<textarea" in GUI_HTML
    assert "Enter" in GUI_HTML
    assert "data-copy" in GUI_HTML
    assert "Copy" in GUI_HTML
    assert "toolCard" in GUI_HTML
    assert "Step " in GUI_HTML
    assert "Tool " in GUI_HTML
    assert "statusDot" in GUI_HTML
    assert "toast" in GUI_HTML
    assert "localStorage" in GUI_HTML
    assert "ar-theme" in GUI_HTML
    assert "data-theme" in GUI_HTML
    assert 'src="http' not in GUI_HTML
    assert 'href="http' not in GUI_HTML
    assert "<script src" not in GUI_HTML
