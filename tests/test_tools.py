"""File tools sandbox and dispatch."""

import os

from agentrouter.tools import (
    execute_tool,
    tool_bash,
    tool_edit_file,
    tool_read_file,
    tool_web_fetch,
    tool_write_file,
)


def test_write_then_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "sub" / "a.txt"
    assert "Wrote" in tool_write_file(str(target), "hello")
    assert tool_read_file(str(target)) == "hello"


def test_read_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "not found" in tool_read_file("nope.txt").lower()


def test_read_empty_path():
    assert "must not be empty" in tool_read_file("").lower()


def test_edit_file_replaces_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "e.txt"
    p.write_text("aaa bbb aaa", encoding="utf-8")
    out = tool_edit_file(str(p), "aaa", "zzz")
    assert "replaced" in out.lower()
    assert p.read_text() == "zzz bbb aaa"


def test_edit_missing_old_string(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "e.txt"
    p.write_text("hello", encoding="utf-8")
    assert "not found" in tool_edit_file(str(p), "missing", "x").lower()


def test_edit_empty_old_string(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "e.txt"
    p.write_text("hello", encoding="utf-8")
    assert "must not be empty" in tool_edit_file(str(p), "", "x").lower()


def test_bash_denylist_blocked():
    assert "blocked" in tool_bash("rm -rf /").lower()
    assert "blocked" in tool_bash("mkfs.ext4 /dev/sda1").lower()


def test_bash_runs_echo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tool_bash("echo hi")
    assert "hi" in out
    assert out.startswith("Exit 0")


def test_bash_empty_command():
    assert "must not be empty" in tool_bash("").lower()


def test_bash_cwd_outside_root_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tool_bash("echo hi", cwd="/etc")
    assert "outside allowed root" in out.lower()


def test_web_fetch_rejects_scheme():
    assert "must start with http" in tool_web_fetch("ftp://x").lower()


def test_execute_tool_dispatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "Wrote" in execute_tool("write_file", {"path": "f.txt", "content": "v"})
    assert execute_tool("read_file", {"path": "f.txt"}) == "v"


def test_execute_tool_bash_disabled_by_default():
    out = execute_tool("bash", {"command": "echo hi"})
    assert "disabled" in out.lower()


def test_execute_tool_bash_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = execute_tool("bash", {"command": "echo hi"}, allow_bash=True)
    assert "hi" in out


def test_execute_tool_unknown():
    assert "unknown tool" in execute_tool("nope", {}).lower()


def test_execute_tool_relative_path_stays_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execute_tool("write_file", {"path": "inner/out.txt", "content": "x"})
    assert (tmp_path / "inner" / "out.txt").exists()
    assert os.path.realpath(tmp_path / "inner" / "out.txt").startswith(os.path.realpath(tmp_path))
