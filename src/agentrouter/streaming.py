"""SSE parsing helpers for AgentRouter streaming chat completions.

Parses Server-Sent Events lines of the form ``data: {...}`` and extracts
incremental token text from OpenAI-compatible chunk payloads.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

DONE_MARKER = "[DONE]"


def extract_content_from_chunk(payload: dict[str, Any]) -> str:
    """Extract incremental text from a single chat chunk payload."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    if isinstance(text, str):
        return text
    return ""


def content_from_sse_data(data: str) -> str | None:
    """Map one SSE ``data:`` payload to text.

    Returns ``None`` when the stream is finished or the payload carries
    no usable text, otherwise returns the (possibly empty) token string.
    """
    text = data.strip()
    if not text or text == DONE_MARKER:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    content = extract_content_from_chunk(payload)
    return content if content else None


def parse_sse_line(line: str) -> str | None:
    """Parse a raw SSE line and return token text, or ``None`` to skip."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith(":"):
        return None
    if stripped.startswith("data:"):
        return content_from_sse_data(stripped[5:].strip())
    return None


def iter_sse_content(lines: Iterable[str]) -> Iterator[str]:
    """Yield token strings from an iterable of raw SSE lines."""
    for line in lines:
        if not isinstance(line, str):
            continue
        content = parse_sse_line(line)
        if content:
            yield content


def iter_response_content(response: Any) -> Iterator[str]:
    """Yield token strings from a ``requests`` streaming response."""
    yield from iter_sse_content(response.iter_lines(decode_unicode=True))
