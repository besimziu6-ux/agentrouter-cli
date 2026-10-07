"""Agent tool-call parsing and loop with mocked client."""

from unittest.mock import MagicMock, patch

import pytest

from agentrouter.agent import parse_tool_calls, run_agent


def test_parse_codeblock_tool_call():
    text = '```json\n{"tool": "read_file", "args": {"path": "a.txt"}}\n```'
    calls = parse_tool_calls(text)
    assert calls == [{"tool": "read_file", "args": {"path": "a.txt"}}]


def test_parse_inline_tool_call():
    text = 'tool:read_file({"path": "a.txt"})'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["tool"] == "read_file"


def test_parse_ignores_unknown_tools():
    text = '```json\n{"tool": "nope", "args": {}}\n```'
    assert parse_tool_calls(text) == []


def test_parse_empty_returns_none():
    assert parse_tool_calls("") == []
    assert parse_tool_calls("just a final answer") == []


def test_parse_multiple_calls():
    text = (
        '```json\n{"tool": "read_file", "args": {"path": "a"}}\n```\n'
        '```json\n{"tool": "read_file", "args": {"path": "b"}}\n```'
    )
    assert len(parse_tool_calls(text)) == 2


def _chat_payload(text):
    return {"choices": [{"message": {"content": text}}]}


def test_run_agent_final_answer_no_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with patch("agentrouter.agent.AgentRouterClient") as mock_cls:
        inst = MagicMock()
        inst.chat_completions.return_value = _chat_payload("done!")
        mock_cls.return_value = inst
        final, sid = run_agent("goal", "m", max_steps=3, verbose=False)
    assert final == "done!"
    assert sid


def test_run_agent_executes_tool_then_finishes(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".config" / "agentrouter").mkdir(parents=True, exist_ok=True)
    tool_call = '```json\n{"tool": "write_file", "args": {"path": "out.txt", "content": "hi"}}\n```'
    with patch("agentrouter.agent.AgentRouterClient") as mock_cls:
        inst = MagicMock()
        inst.chat_completions.side_effect = [_chat_payload(tool_call), _chat_payload("finished")]
        mock_cls.return_value = inst
        monkeypatch.chdir(tmp_path)
        final, _ = run_agent("make file", "m", max_steps=3, verbose=False)
    assert final == "finished"
    assert (tmp_path / "out.txt").read_text() == "hi"


def test_run_agent_rejects_empty_goal():
    with pytest.raises(ValueError, match="Goal must not be empty"):
        run_agent("", "m")


def test_run_agent_requires_model():
    with pytest.raises(ValueError, match="No model"):
        run_agent("goal", "")


def test_run_agent_bad_max_steps():
    with pytest.raises(ValueError):
        run_agent("goal", "m", max_steps=0)
