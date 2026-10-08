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
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
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


def _get_with_headers(base, path, headers=None):
    req = urllib.request.Request(base + path, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def _start_server_with_token(token):
    server = create_server("127.0.0.1", 0, token)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base


def test_static_index_served_with_mime():
    import os

    with patch.dict(os.environ, {"AGENTROUTER_GUI_TOKEN": ""}, clear=False):
        server, thread, base = _start_server()
        try:
            status, headers, body = _get(base, "/static/index.html")
            assert status == 200
            assert "text/html" in headers.get_content_type()
            assert b"AgentRouter" in body
            status_css, h_css, _ = _get(base, "/static/css/tokens.css")
            assert status_css == 200
            assert h_css.get_content_type() == "text/css"
            status_js, h_js, _ = _get(base, "/static/js/main.js")
            assert status_js == 200
            ctype = h_js.get("Content-Type", "")
            assert "javascript" in ctype
        finally:
            _stop_server(server, thread)


def test_static_etag_304():
    server, thread, base = _start_server()
    try:
        status, headers, _ = _get(base, "/static/css/tokens.css")
        assert status == 200
        etag = headers.get("ETag")
        assert etag
        assert headers.get("Cache-Control") == "no-cache"
        status2, _, _ = _get_with_headers(base, "/static/css/tokens.css", {"If-None-Match": etag})
        assert status2 == 304
    finally:
        _stop_server(server, thread)


def test_static_traversal_blocked_and_unknown_404():
    server, thread, base = _start_server()
    try:
        for p in (
            "/static/../gui_server.py",
            "/static/%2e%2e/gui_server.py",
            "/static/css/../../gui_html.py",
            "/static/nope.css",
            "/static/js/unknown.js",
            "/static/file.txt",
        ):
            status, _, _ = _get(base, p)
            assert status == 404, p
    finally:
        _stop_server(server, thread)


def test_api_version_returns_version():
    from agentrouter import __version__ as ver

    server, thread, base = _start_server()
    try:
        status, headers, body = _get(base, "/api/version")
    finally:
        _stop_server(server, thread)
    assert status == 200
    assert headers.get_content_type() == "application/json"
    assert json.loads(body.decode("utf-8")) == {"version": ver}


def test_chat_reasoning_usage_relay():
    import io

    from agentrouter.gui_server import GuiHandler

    fake = _fake_config()

    def _rchunk():
        return {"choices": [{"delta": {"content": "Hi", "reasoning_content": "thinking"}}]}

    class FakeStream:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps(_rchunk())
            yield "data: " + json.dumps({"usage": {"prompt_tokens": 1, "completion_tokens": 2}})
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
        with patch("agentrouter.gui_server.requests.post", return_value=FakeStream()):
            handler._handle_chat()
    assert handler._status == 200
    text = handler.wfile.getvalue().decode("utf-8")
    assert "data: [DONE]" in text
    assert '"reasoning"' in text
    assert "thinking" in text
    assert '"usage"' in text
    assert '"content"' in text


def test_token_off_default_allows():
    import os

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AGENTROUTER_GUI_TOKEN", None)
        server, thread, base = _start_server_with_token(None)
        try:
            status, _, _ = _get(base, "/api/health")
        finally:
            _stop_server(server, thread)
    assert status == 200


def test_token_on_enforced():
    server, thread, base = _start_server_with_token("s3cret")
    try:
        status_no, _, _ = _get(base, "/api/health")
        assert status_no == 401
        status_ok, _, body = _get_with_headers(base, "/api/health", {"X-AgentRouter-Token": "s3cret"})
        assert status_ok == 200
        assert b"ok" in body
        status_bad, _, _ = _get_with_headers(base, "/api/health", {"X-AgentRouter-Token": "wrong"})
        assert status_bad == 401
    finally:
        _stop_server(server, thread)


def test_frontend_files_no_http_src_href():
    import re

    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"
    assert root.exists()
    pat_src = re.compile(r'\ssrc\s*=\s*["\']https?://', re.IGNORECASE)
    pat_href = re.compile(r'\shref\s*=\s*["\']https?://', re.IGNORECASE)
    pat_import = re.compile(r"@import\s+[^;]*https?://", re.IGNORECASE)
    pat_url = re.compile(r"url\s*\(\s*['\"]?https?://", re.IGNORECASE)
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix == ".test.js":
            continue
        if p.suffix not in (".html", ".css", ".js", ".json", ".svg"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        assert not pat_src.search(text), f"http src in {p}"
        assert not pat_href.search(text), f"http href in {p}"
        assert not pat_import.search(text), f"http @import in {p}"
        assert not pat_url.search(text), f"http url() in {p}"


def test_static_total_size_under_budget():
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"
    total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.name.endswith(".test.js"))
    assert total < 192 * 1024, f"shipped static total {total} exceeds 192KB"


def test_js_unit_tests_via_node():
    import shutil

    node = shutil.which("node")
    if not node:
        import pytest as _pytest

        _pytest.skip("node not available")
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static" / "js"
    cases = sorted(str(p) for p in root.glob("*.test.js"))
    assert cases, "no js tests found"
    result = subprocess.run([node, "--test"] + cases, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def _static_root():
    return pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"


def _read_index():
    return (_static_root() / "index.html").read_text(encoding="utf-8")


def test_shell_mounts_theme_boot_token_placeholder():
    text = _read_index()
    for mount in ('id="rail"', 'id="stage"', 'id="inspector"', 'id="transport"', 'id="toasts"'):
        assert mount in text, mount
    assert "skel" in text
    assert "ar-token" in text
    assert "ar-theme" in text
    assert "localStorage" in text
    assert "data-theme" in text
    assert "data-motion" in text


def test_static_shell_files_served_with_mime():
    server, thread, base = _start_server()
    try:
        for path, needle in (
            ("/static/js/rail.js", "filterSessions"),
            ("/static/js/transport.js", "formatElapsed"),
            ("/static/js/inspector.js", "initInspector"),
            ("/static/js/palette.js", "filterPalette"),
            ("/static/js/popover.js", "openPopover"),
            ("/static/js/dialog.js", "openDialog"),
            ("/static/js/toast.js", "showToast"),
            ("/static/js/settings.js", "applySettings"),
            ("/static/css/shell.css", "#rail"),
        ):
            status, headers, body = _get(base, path)
            assert status == 200, path
            ctype = headers.get("Content-Type", "")
            if path.endswith(".js"):
                assert "javascript" in ctype, path
            else:
                assert "text/css" in ctype, path
            assert needle in body.decode("utf-8"), path
    finally:
        _stop_server(server, thread)


def test_token_meta_injected_when_set():
    import os

    server, thread, base = _start_server_with_token("s3cret")
    try:
        status, _, body = _get(base, "/")
        assert status == 200
        text = body.decode("utf-8")
        assert 'name="ar-token"' in text
        assert "s3cret" in text
    finally:
        _stop_server(server, thread)
    with patch.dict(os.environ, {"AGENTROUTER_GUI_TOKEN": ""}, clear=False):
        server2, thread2, base2 = _start_server()
        try:
            status2, _, body2 = _get(base2, "/")
            assert status2 == 200
            assert 'content=""' in body2.decode("utf-8")
        finally:
            _stop_server(server2, thread2)


def test_shell_css_no_banned_effects_or_emoji():
    for name in ("shell.css", "base.css", "components.css", "motion.css", "tokens.css"):
        text = (_static_root() / "css" / name).read_text(encoding="utf-8")
        low = text.lower()
        assert "backdrop-filter" not in low, name
        assert "linear-gradient" not in low, name
        assert "radial-gradient" not in low, name
    for p in _static_root().rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in (".html", ".css", ".js"):
            continue
        if p.suffix == ".js" and p.name.endswith(".test.js"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for ch in ("😀", "✨", "🚀", "🔑"):
            assert ch not in text, f"emoji in {p.name}"


def test_shell_js_no_dom_at_import():
    import re

    pure = ("settings.js", "palette.js", "transport.js", "rail.js", "toast.js", "popover.js", "store.js")
    for name in pure:
        text = (_static_root() / "js" / name).read_text(encoding="utf-8")
        lines = text.splitlines()
        top = "\n".join(lines[:12])
        assert "document." not in top or "typeof document" in text, name
        assert re.search(r"^\s*document\.", top, re.M) is None, name
        assert re.search(r"^\s*window\.", top, re.M) is None, name


def test_gui_fits_inside_window():
    css = (_static_root() / "css" / "shell.css").read_text(encoding="utf-8")
    chat = (_static_root() / "css" / "chat.css").read_text(encoding="utf-8")

    def rule_block(text, selector):
        start = text.find(selector + "{")
        assert start >= 0, f"missing rule {selector}"
        end = text.find("}", start)
        assert end > start, f"unterminated rule {selector}"
        return text[start:end]

    shell = rule_block(css, "#shell")
    assert "100dvh" in shell, "shell must be bounded to viewport height"
    assert "overflow:hidden" in shell.replace(" ", ""), "shell must clip page-level overflow"

    stage = rule_block(css, "#stage")
    assert "overflow-y:auto" in stage.replace(" ", ""), "stage must scroll internally"

    composer = rule_block(css, "#composer")
    assert "min-width:0" in composer.replace(" ", ""), "composer must shrink in flex row"

    meta = rule_block(css, ".transport-meta")
    assert "flex-wrap:wrap" in meta.replace(" ", ""), "transport meta must wrap on narrow windows"

    insp = rule_block(css, "#inspector")
    assert "overflow-y:auto" in insp.replace(" ", ""), "inspector must scroll internally"

    msg = rule_block(chat, ".msg")
    assert "min-width:0" in msg.replace(" ", ""), "message rows must not force grid blowout"


def test_gui_panels_toggle_and_fit():
    shell = (_static_root() / "css" / "shell.css").read_text(encoding="utf-8")
    base = (_static_root() / "css" / "base.css").read_text(encoding="utf-8")
    nospace = shell.replace(" ", "")

    def rule_block(text, selector):
        start = text.find(selector + "{")
        assert start >= 0, f"missing rule {selector}"
        end = text.find("}", start)
        assert end > start, f"unterminated rule {selector}"
        return text[start:end]

    grid = rule_block(shell, "#shell")
    assert "grid-template-columns:auto" in grid.replace(" ", ""), \
        "shell tracks must be auto so collapsing rail/inspector frees space"
    assert "#rail{width:260px" in nospace, "rail must own its width for collapse to work"
    assert "#inspector{width:300px" in nospace, "inspector must own its width"
    banner = rule_block(shell, ".banner")
    assert "position:fixed" in banner.replace(" ", ""), \
        "offline banner must overlay, never grow the page"
    start = base.find("\nbody{")
    assert start >= 0, "missing body rule"
    body = base[start:start + base.find("}", start) - start]
    assert "overflow:hidden" in body.replace(" ", ""), \
        "page itself must not scroll; panels scroll internally"

    main_js = (_static_root() / "js" / "main.js").read_text(encoding="utf-8")
    assert main_js.count('getElementById("inspectorToggle")') <= 1, \
        "inspector toggle must be bound once (double bind cancels itself out)"
