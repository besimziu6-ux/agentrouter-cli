"""Phase 3 (Chat) static checks: markers, budgets, no-CDN, safe rendering."""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"
JS = ROOT / "js"
CSS = ROOT / "css"

CHAT_JS = ("markdown.js", "highlight.js", "composer.js", "messages.js", "meter.js", "chat.js")
CHAT_TESTS = ("markdown.test.js", "highlight.test.js", "chat.test.js")


def _read_index():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def test_chat_js_modules_exist():
    for name in CHAT_JS:
        assert (JS / name).is_file(), name


def test_chat_js_tests_exist():
    for name in CHAT_TESTS:
        assert (JS / name).is_file(), name


def test_chat_css_exists_and_linked():
    assert (CSS / "chat.css").is_file()
    assert "chat.css" in _read_index()


def test_composer_markers():
    text = _read_index()
    for marker in ('id="composer"', 'id="chatParams"', 'id="sysPrompt"', 'id="maxTokens"', 'id="temperature"', 'id="runBtn"', 'id="stopBtn"'):
        assert marker in text, marker
    composer = (JS / "composer.js").read_text(encoding="utf-8")
    assert "field-sizing" in (CSS / "chat.css").read_text(encoding="utf-8")
    assert "shake" in composer


def test_meter_markers():
    text = _read_index()
    assert 'id="meter"' in text
    assert 'id="meterVal"' in text
    assert "tok/s" in text
    meter = (JS / "meter.js").read_text(encoding="utf-8")
    assert "56" in meter and "aria-hidden" in meter


def test_reasoning_markers():
    messages = (JS / "messages.js").read_text(encoding="utf-8")
    assert "reason" in messages
    assert "collapse" in messages
    chat = (JS / "chat.js").read_text(encoding="utf-8")
    assert "reasoning" in chat
    assert "usage" in chat


def test_copy_markers():
    messages = (JS / "messages.js").read_text(encoding="utf-8")
    assert "Copy transcript" in messages
    markdown = (JS / "markdown.js").read_text(encoding="utf-8")
    assert "data-copy" in markdown
    assert "Copy" in markdown
    assert 'id="latestPill"' in (JS / "chat.js").read_text(encoding="utf-8") or "latestPill" in (JS / "chat.js").read_text(encoding="utf-8")


def test_chat_payload_shape_markers():
    chat = (JS / "chat.js").read_text(encoding="utf-8")
    for marker in ("model", "messages", "system", "max_tokens", "temperature", "/api/chat"):
        assert marker in chat, marker


def test_chat_no_innerhtml_document_write():
    for name in CHAT_JS:
        text = (JS / name).read_text(encoding="utf-8")
        assert "innerHTML" not in text, name
        assert "document.write" not in text, name


def test_chat_no_http_links():
    pat_src = re.compile(r'\ssrc\s*=\s*["\']https?://', re.IGNORECASE)
    pat_href = re.compile(r'\shref\s*=\s*["\']https?://', re.IGNORECASE)
    for name in CHAT_JS + CHAT_TESTS + ("chat.js",):
        text = (JS / name).read_text(encoding="utf-8", errors="replace")
        assert not pat_src.search(text), name
        assert not pat_href.search(text), name
    css = (CSS / "chat.css").read_text(encoding="utf-8")
    assert "http://" not in css and "https://" not in css


def test_chat_rel_noopener_for_links():
    assert "noopener noreferrer" in (JS / "markdown.js").read_text(encoding="utf-8")


def test_static_total_size_still_under_budget():
    total = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file() and not p.name.endswith(".test.js"))
    assert total < 192 * 1024, f"shipped static total {total} exceeds 192KB"
