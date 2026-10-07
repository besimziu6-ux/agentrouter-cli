"""Agent loop: system prompt, tool-call parsing, step execution."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from agentrouter.client import AgentRouterClient, AgentRouterError
from agentrouter.session import load_session, new_session_id, save_session
from agentrouter.tools import execute_tool, is_known_tool

AGENT_SYSTEM_PROMPT = """You are a file and shell agent. You have these local tools:

- read_file: {"path": "..."} - read a file.
- write_file: {"path": "...", "content": "..."} - write a file.
- edit_file: {"path": "...", "old_string": "...", "new_string": "..."} - exact string replace.
- bash: {"command": "..."} - run a shell command (only if user enabled it).
- web_fetch: {"url": "..."} - fetch a URL as text.

To use a tool, output exactly one of these forms, one tool call per message step:
1. A JSON codeblock:
```json
{"tool": "write_file", "args": {"path": "hello.txt", "content": "hi"}}
```
2. Or inline form: tool:write_file({"path": "hello.txt", "content": "hi"})

Rules:
- To do file work you MUST call tools. Do not claim you did it without a tool call.
- One step may contain multiple tool calls; each is executed in order.
- After tool results arrive, continue until the goal is done.
- When the goal is complete, reply with a plain final answer (no tool calls).
- Keep tool args as valid JSON.
"""

CODEBLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
TOOL_INLINE_RE = re.compile(r"tool:([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE)


def _parse_json_obj(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _coerce_args(tool: str, raw_args: Any) -> dict:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str) and raw_args.strip():
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        if tool in ("read_file",):
            return {"path": raw_args.strip()}
        if tool in ("web_fetch",):
            return {"url": raw_args.strip()}
        if tool in ("bash",):
            return {"command": raw_args.strip()}
    return {}


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not text or not text.strip():
        return found
    for m in CODEBLOCK_RE.finditer(text):
        obj = _parse_json_obj(m.group(1))
        if obj is None:
            continue
        tool = obj.get("tool")
        if not isinstance(tool, str) or not is_known_tool(tool):
            continue
        args = obj.get("args", obj.get("arguments", {}))
        if not isinstance(args, dict):
            args = _coerce_args(tool, args)
        found.append({"tool": tool, "args": args})
        continue
    for m in TOOL_INLINE_RE.finditer(text):
        tool = m.group(1)
        if not is_known_tool(tool):
            continue
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        inner = text[start:i - 1].strip() if depth == 0 else ""
        if not inner:
            continue
        args: dict = {}
        if inner.startswith("{") or inner.startswith("["):
            try:
                parsed = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                if "tool" in parsed and is_known_tool(str(parsed.get("tool"))):
                    args = parsed.get("args", parsed.get("arguments", {}))
                    if not isinstance(args, dict):
                        args = {}
                    found.append({"tool": str(parsed["tool"]), "args": args})
                else:
                    args = parsed
                    found.append({"tool": tool, "args": args})
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and is_known_tool(str(item.get("tool", ""))):
                        a = item.get("args", item.get("arguments", {}))
                        found.append({"tool": str(item["tool"]), "args": a if isinstance(a, dict) else {}})
            continue
        else:
            args = _coerce_args(tool, inner)
            if args:
                found.append({"tool": tool, "args": args})
    seen: list[dict[str, Any]] = []
    for f in found:
        if f not in seen:
            seen.append(f)
    return seen


def _extract_reply_text(data: Any) -> str:
    if isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content:
                        return content
                    if isinstance(content, list):
                        parts = []
                        for p in content:
                            if isinstance(p, dict) and isinstance(p.get("text"), str):
                                parts.append(p["text"])
                            elif isinstance(p, str):
                                parts.append(p)
                        joined = "".join(parts)
                        if joined:
                            return joined
                    reasoning = message.get("reasoning_content")
                    if isinstance(reasoning, str) and reasoning:
                        return reasoning
                    if isinstance(content, str):
                        return content
                if isinstance(first.get("text"), str):
                    return first["text"]
                reasoning = first.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning:
                    return reasoning
    return json.dumps(data, indent=2) if isinstance(data, dict) else str(data)


def run_agent(
    goal: str,
    model: str,
    max_steps: int = 10,
    allow_bash: bool = False,
    resume_id: str | None = None,
    timeout: float | None = None,
    extra_kwargs: dict[str, Any] | None = None,
    system: str | None = None,
    verbose: bool = True,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[str, str]:
    if not goal or not goal.strip():
        raise ValueError("Goal must not be empty.")
    if max_steps <= 0:
        raise ValueError("--max-steps must be a positive integer.")
    if not model or not model.strip():
        raise ValueError("No model specified.")

    base_system = AGENT_SYSTEM_PROMPT
    if system and system.strip():
        base_system = f"{system.strip()}\n\n{base_system}"

    if resume_id:
        session_id = resume_id
        try:
            messages = load_session(session_id)
        except ValueError as exc:
            raise AgentRouterError(str(exc)) from exc
        if not messages:
            messages = [
                {"role": "system", "content": base_system},
                {"role": "user", "content": goal.strip()},
            ]
        else:
            has_system = any(m.get("role") == "system" for m in messages)
            if not has_system:
                messages = [{"role": "system", "content": base_system}] + messages
            messages.append({"role": "user", "content": goal.strip()})
    else:
        session_id = new_session_id()
        messages = [
            {"role": "system", "content": base_system},
            {"role": "user", "content": goal.strip()},
        ]

    save_session(session_id, messages)

    client = AgentRouterClient(timeout=timeout) if timeout else AgentRouterClient()
    kwargs = dict(extra_kwargs or {})

    final_text = ""
    for step in range(1, max_steps + 1):
        data = client.chat_completions(messages, model=model, **kwargs)
        reply = _extract_reply_text(data)
        messages.append({"role": "assistant", "content": reply})
        save_session(session_id, messages)
        if verbose:
            print(f"[step {step}/{max_steps}] model reply:\n{reply}\n")
        if on_event is not None:
            on_event({"type": "step", "step": step, "text": reply})

        calls = parse_tool_calls(reply)
        if not calls:
            final_text = reply
            break

        for call in calls:
            name = call["tool"]
            args = call.get("args", {})
            if verbose:
                print(f"[step {step}] tool:{name} {json.dumps(args)}")
            result = execute_tool(name, args, allow_bash=allow_bash)
            if verbose:
                preview = result[:2000]
                print(f"[step {step}] result:\n{preview}\n")
            if on_event is not None:
                on_event({"type": "tool", "step": step, "tool": name, "args": args, "result": result})
            messages.append({"role": "user", "content": f"Tool {name} result:\n{result}"})
        save_session(session_id, messages)
        final_text = ""
    else:
        final_text = messages[-1].get("content", "") if messages else ""

    save_session(session_id, messages)
    if on_event is not None:
        on_event({"type": "done", "text": final_text, "session_id": session_id})
    return final_text, session_id
