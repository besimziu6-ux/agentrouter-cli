"""Phase 4 (Agent) static checks: timeline, diff, approval, odometer, rerun."""

from __future__ import annotations

import pathlib
import re
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"
JS = ROOT / "js"
CSS = ROOT / "css"

NEW_JS = ("timeline.js", "diff.js", "odometer.js")
NEW_TESTS = ("timeline.test.js", "diff.test.js", "odometer.test.js", "dialog.test.js")


def _read_js(name):
    return (JS / name).read_text(encoding="utf-8")


def test_agent_js_modules_exist():
    for name in NEW_JS:
        assert (JS / name).is_file(), name
    assert (CSS / "agent.css").is_file()
    assert "agent.css" in (ROOT / "index.html").read_text(encoding="utf-8")


def test_agent_js_tests_exist():
    for name in NEW_TESTS:
        assert (JS / name).is_file(), name


def test_timeline_markers():
    text = _read_js("timeline.js")
    for marker in ("tl-row", "collapse", "showDetail", "Re-run", "Resume", "resume_id",
                   "/api/agent", "resolveStop", "stopLabel", "max_steps", "user_abort",
                   "tl-fill", "pulse", "shake", "hunkDelay", "renderDiff", "parseAgentEvent"):
        assert marker in text, marker


def test_diff_markers_pure_dom():
    text = _read_js("diff.js")
    for marker in ("escapeHtml", "diffLines", "renderDiff", "createElement", "@@ -", "textContent"):
        assert marker in text, marker
    assert "innerHTML" not in text
    assert "document.write" not in text


def test_odometer_markers():
    text = _read_js("odometer.js")
    for marker in ("translateY", "rollY", "paintOdometer", "mountOdometer"):
        assert marker in text, marker
    assert "innerHTML" not in text


def test_approval_markers_dormant():
    dialog = _read_js("dialog.js")
    for marker in ("isApprovalEvent", "approvalKey", "openApproval", '"approval"', "allow", "deny", "always"):
        assert marker in dialog, marker
    timeline = _read_js("timeline.js")
    assert "approval" in timeline
    assert "openApproval" in timeline
    import agentrouter.gui_server as srv

    src = pathlib.Path(srv.__file__).read_text(encoding="utf-8")
    assert "approval" not in src


def test_agent_sse_shapes_unchanged():
    import agentrouter.agent as agent_mod

    src = pathlib.Path(agent_mod.__file__).read_text(encoding="utf-8")
    assert '"type": "step"' in src
    assert '"type": "tool"' in src
    assert '"type": "done"' in src
    assert '"type": "approval"' not in src


def test_transport_agent_wiring_markers():
    text = _read_js("transport.js")
    for marker in ("paintOdometer", "agentStep", "agentStart", "agentIdle", "stepText", "formatElapsed"):
        assert marker in text, marker


def test_chat_shell_foundation_intact():
    chat = _read_js("chat.js")
    for marker in ("/api/chat", "beginAssistant", "pushMeter", "onAgentSend"):
        assert marker in chat, marker
    main = _read_js("main.js")
    assert "initTimeline" in main
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    for marker in ('id="rail"', 'id="stage"', 'id="inspector"', 'id="transport"', 'id="stepCount"', 'id="elapsed"'):
        assert marker in index, marker


def test_agent_no_innerhtml_document_write():
    for name in NEW_JS + ("dialog.js", "transport.js", "inspector.js", "main.js", "chat.js"):
        text = _read_js(name)
        assert "innerHTML" not in text, name
        assert "document.write" not in text, name


def test_agent_no_http_links():
    pat_src = re.compile(r'\ssrc\s*=\s*["\']https?://', re.IGNORECASE)
    pat_href = re.compile(r'\shref\s*=\s*["\']https?://', re.IGNORECASE)
    for name in NEW_JS + NEW_TESTS + ("dialog.js", "transport.js", "inspector.js", "main.js"):
        text = _read_js(name)
        assert not pat_src.search(text), name
        assert not pat_href.search(text), name
    css = (CSS / "agent.css").read_text(encoding="utf-8")
    assert "http://" not in css and "https://" not in css
    assert "backdrop-filter" not in css.lower()
    assert "linear-gradient" not in css.lower()


def test_agent_js_no_dom_at_import():
    for name in NEW_JS + ("dialog.js",):
        lines = _read_js(name).splitlines()
        top = "\n".join(lines[:12])
        assert re.search(r"^\s*document\.", top, re.M) is None, name
        assert re.search(r"^\s*window\.", top, re.M) is None, name


def test_shipped_size_under_budget_excl_tests():
    total = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file() and not p.name.endswith(".test.js"))
    assert total < 192 * 1024, f"shipped static total {total} exceeds 192KB"


def test_package_data_excludes_js_tests():
    root = pathlib.Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "static/**/*" not in text
    block = text.split("[tool.setuptools.package-data]", 1)[1].split("[tool.", 1)[0]
    assert ".test.js" not in block
    for marker in ("timeline.js", "diff.js", "odometer.js", "agent.css"):
        assert marker in text or "*.css" in text, marker


def test_agent_static_served_with_mime():
    import urllib.request
    from unittest.mock import patch

    from agentrouter.config import DEFAULT_BASE_URL, Config
    from agentrouter.gui_server import create_server

    fake = Config(api_key="sk-test-key-123456789", base_url=DEFAULT_BASE_URL,
                  default_model="test-model", config_path=None)
    with patch("agentrouter.gui_server.load_config", return_value=fake):
        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            for path, needle in (
                ("/static/js/timeline.js", "tl-row"),
                ("/static/js/diff.js", "renderDiff"),
                ("/static/js/odometer.js", "paintOdometer"),
                ("/static/js/dialog.js", "openApproval"),
                ("/static/css/agent.css", ".tl-row"),
            ):
                req = urllib.request.Request(base + path, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    assert resp.status == 200, path
                    body = resp.read().decode("utf-8")
                    assert needle in body, path
        finally:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
            thread.join(timeout=5)
