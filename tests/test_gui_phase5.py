"""Phase 5 tests: session rename/delete, title sidecars, onboarding/settings markers."""

from __future__ import annotations

import json
import pathlib
import subprocess
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

from agentrouter.config import DEFAULT_BASE_URL, Config
from agentrouter.gui_server import create_server


def _fake_config(**kwargs):
    base = {
        "api_key": "sk-test-key-123456789",
        "base_url": DEFAULT_BASE_URL,
        "default_model": "test-model",
        "config_path": None,
    }
    base.update(kwargs)
    return Config(**base)


def _start_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}"


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


def _req(base, path, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"error": raw}


def _patched_dir(tmp_path):
    return patch("agentrouter.session.get_sessions_dir", return_value=tmp_path), patch(
        "agentrouter.gui_server.get_sessions_dir", return_value=tmp_path
    )


def _seed(tmp_path, sid, messages=None):
    from agentrouter.session import save_session

    save_session(sid, messages if messages is not None else [{"role": "user", "content": "hi"}])
    assert (tmp_path / f"{sid}.jsonl").exists()


def test_patch_rename_roundtrip(tmp_path):
    from agentrouter.session import save_session  # noqa: F401

    sid = "abc123"
    p1, p2 = _patched_dir(tmp_path)
    with p1, p2, patch("agentrouter.gui_server.load_config", return_value=_fake_config()):
        _seed(tmp_path, sid)
        server, thread, base = _start_server()
        try:
            status, data = _req(base, f"/api/sessions/{sid}", method="PATCH", payload={"title": "  My Chat  "})
            assert status == 200, data
            assert data == {"id": sid, "title": "My Chat"}
            assert (tmp_path / f"{sid}.title").read_text(encoding="utf-8") == "My Chat"
            status, data = _req(base, "/api/sessions")
            assert status == 200
            row = next((s for s in data["sessions"] if s["id"] == sid), None)
            assert row is not None and row["title"] == "My Chat"
            status, data = _req(base, f"/api/sessions/{sid}")
            assert status == 200
            assert data["title"] == "My Chat"
            assert data["messages"] == [{"role": "user", "content": "hi"}]
            status, data = _req(base, f"/api/sessions/{sid}", method="PATCH", payload={"title": "Renamed"})
            assert status == 200 and data["title"] == "Renamed"
        finally:
            _stop_server(server, thread)


def test_delete_roundtrip_removes_jsonl_and_sidecar(tmp_path):
    sid = "delme1"
    p1, p2 = _patched_dir(tmp_path)
    with p1, p2, patch("agentrouter.gui_server.load_config", return_value=_fake_config()):
        _seed(tmp_path, sid)
        (tmp_path / f"{sid}.title").write_text("T", encoding="utf-8")
        server, thread, base = _start_server()
        try:
            status, data = _req(base, f"/api/sessions/{sid}", method="DELETE")
            assert status == 200, data
            assert data == {"ok": True, "id": sid}
            assert not (tmp_path / f"{sid}.jsonl").exists()
            assert not (tmp_path / f"{sid}.title").exists()
            status, _ = _req(base, f"/api/sessions/{sid}")
            assert status == 404
            status, _ = _req(base, f"/api/sessions/{sid}", method="DELETE")
            assert status == 404
        finally:
            _stop_server(server, thread)


def test_unsafe_session_id_rejected(tmp_path):
    p1, p2 = _patched_dir(tmp_path)
    with p1, p2, patch("agentrouter.gui_server.load_config", return_value=_fake_config()):
        server, thread, base = _start_server()
        try:
            for bad in ("..", "%2e%2e", "a$b", "x" * 65, "has%20space"):
                status, _ = _req(base, f"/api/sessions/{bad}")
                assert status == 400, bad
                status, _ = _req(base, f"/api/sessions/{bad}", method="PATCH", payload={"title": "T"})
                assert status == 400, bad
                status, _ = _req(base, f"/api/sessions/{bad}", method="DELETE")
                assert status == 400, bad
        finally:
            _stop_server(server, thread)


def test_title_validation_and_missing_session(tmp_path):
    sid = "valid01"
    p1, p2 = _patched_dir(tmp_path)
    with p1, p2, patch("agentrouter.gui_server.load_config", return_value=_fake_config()):
        _seed(tmp_path, sid)
        server, thread, base = _start_server()
        try:
            for payload in ({}, {"title": ""}, {"title": "   "}, {"title": "x" * 121}, {"title": 42}, {"nottitle": "x"}):
                status, data = _req(base, f"/api/sessions/{sid}", method="PATCH", payload=payload)
                assert status == 400, (payload, data)
                assert "error" in data
            status, data = _req(base, "/api/sessions/nosuchid", method="PATCH", payload={"title": "T"})
            assert status == 404, data
        finally:
            _stop_server(server, thread)


def _static_root():
    return pathlib.Path(__file__).resolve().parent.parent / "src" / "agentrouter" / "static"


def test_phase5_frontend_markers():
    js = _static_root() / "js"
    sessions = (js / "sessions.js").read_text(encoding="utf-8")
    for marker in ("renameSession", "deleteSession", "swipeDismissed", "debounce", "copyTranscript", "Load to chat", "Copy transcript"):
        assert marker in sessions, marker
    config = (js / "config.js").read_text(encoding="utf-8")
    for marker in ("onboarding", "data-onboarding", "Test connection", "Show", "locked", "needsOnboarding", "translateConfigError"):
        assert marker in config, marker
    settings = (js / "settings.js").read_text(encoding="utf-8")
    for marker in ("data-settings-panel", "data-setting", "initSettingsPanel", "setMotion", "setDensity", "setFontScale"):
        assert marker in settings, marker
    rail = (js / "rail.js").read_text(encoding="utf-8")
    assert "sessionsOwned" in rail
    main = (js / "main.js").read_text(encoding="utf-8")
    for marker in ("initSessions", "initConfig", "initSettingsPanel", "loadSession"):
        assert marker in main, marker
    index = (_static_root() / "index.html").read_text(encoding="utf-8")
    assert 'id="configBtn"' in index


def test_phase5_shipped_size_under_budget():
    root = _static_root()
    total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.name.endswith(".test.js"))
    assert total < 192 * 1024, f"shipped static total {total} exceeds 192KB"


def test_phase5_node_pure_logic():
    import shutil

    node = shutil.which("node")
    if not node:
        import pytest as _pytest

        _pytest.skip("node not available")
    root = _static_root() / "js"
    cases = [str(root / "sessions.test.js"), str(root / "config.test.js")]
    for c in cases:
        assert pathlib.Path(c).exists(), c
    result = subprocess.run([node, "--test"] + cases, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
