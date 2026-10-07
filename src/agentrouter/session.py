"""Session memory: full message history persisted as JSONL."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def get_sessions_dir() -> Path:
    return Path.home() / ".config" / "agentrouter" / "sessions"


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def session_path(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in ("-", "_")).strip()
    if not safe:
        raise ValueError("Invalid session id.")
    return get_sessions_dir() / f"{safe}.jsonl"


def load_session(session_id: str) -> list[dict[str, Any]]:
    path = session_path(session_id)
    if not path.exists():
        raise ValueError(f"Session {session_id!r} not found at {path}.")
    messages: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read session {session_id!r}: {exc}") from exc
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append(msg)
    return messages


def save_session(session_id: str, messages: list[dict[str, Any]]) -> Path:
    path = session_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(m, ensure_ascii=False) for m in messages]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path
