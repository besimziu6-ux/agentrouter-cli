"""Local tools for the agent loop: files, bash, web fetch."""

from __future__ import annotations

import os
import subprocess
import urllib.request
from pathlib import Path

MAX_FETCH_BYTES = 2 * 1024 * 1024
FETCH_TIMEOUT = 20.0
BASH_DEFAULT_TIMEOUT = 30.0

BASH_DENYLIST = (
    "rm -rf /",
    "rm -fr /",
    "rm -rf /*",
    "rm -fr /*",
    ":(){",
    "mkfs",
    "dd if=",
    "> /dev/sda",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
)

TOOL_DESCRIPTIONS = {
    "read_file": "Read a file. args: {\"path\": \"...\"}",
    "write_file": "Write content to a file (creates parents). args: {\"path\": \"...\", \"content\": \"...\"}",
    "edit_file": "Exact string replace in a file. args: {\"path\": \"...\", \"old_string\": \"...\", \"new_string\": \"...\"}",
    "bash": "Run a shell command (requires --allow-bash). args: {\"command\": \"...\"}",
    "web_fetch": "Fetch a URL as text (2MB cap). args: {\"url\": \"...\"}",
}


def _resolve_path(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def tool_read_file(path: str) -> str:
    if not path or not path.strip():
        return "Error: path must not be empty."
    p = _resolve_path(path.strip())
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except OSError as exc:
        return f"Error: could not read {path}: {exc}"


def tool_write_file(path: str, content: str) -> str:
    if not path or not path.strip():
        return "Error: path must not be empty."
    p = _resolve_path(path.strip())
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        return f"Wrote {len(content or '')} chars to {path}"
    except OSError as exc:
        return f"Error: could not write {path}: {exc}"


def tool_edit_file(path: str, old_string: str, new_string: str) -> str:
    if not path or not path.strip():
        return "Error: path must not be empty."
    if old_string is None or old_string == "":
        return "Error: old_string must not be empty."
    if new_string is None:
        new_string = ""
    p = _resolve_path(path.strip())
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except OSError as exc:
        return f"Error: could not read {path}: {exc}"
    if old_string not in text:
        return "Error: old_string not found in file."
    text = text.replace(old_string, new_string, 1)
    try:
        p.write_text(text, encoding="utf-8")
        return f"Edited {path}: replaced 1 occurrence."
    except OSError as exc:
        return f"Error: could not write {path}: {exc}"


def _bash_blocked(command: str) -> str | None:
    lowered = command.lower()
    for pat in BASH_DENYLIST:
        if pat in lowered:
            return pat
    stripped = " ".join(command.strip().split())
    if stripped in ("rm -rf /", "rm -fr /", "rm -rf /*", "rm -fr /*", "rm -rf ~", "rm -rf ."):
        return stripped
    return None


def _resolve_cwd(cwd: str | None, allowed_root: Path) -> Path:
    if not cwd or not str(cwd).strip():
        return allowed_root
    p = Path(str(cwd).strip()).expanduser()
    if not p.is_absolute():
        p = allowed_root / p
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p.absolute()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError:
        raise ValueError(f"cwd {cwd!r} is outside allowed root {allowed_root}")
    return resolved


def tool_bash(command: str, cwd: str | None = None, timeout: float = BASH_DEFAULT_TIMEOUT) -> str:
    if not command or not command.strip():
        return "Error: command must not be empty."
    hit = _bash_blocked(command)
    if hit:
        return f"Error: command blocked by denylist (matched {hit!r})."
    allowed_root = Path.cwd().resolve()
    try:
        run_cwd = _resolve_cwd(cwd, allowed_root)
    except ValueError as exc:
        return f"Error: {exc}"
    try:
        t = float(timeout) if timeout else BASH_DEFAULT_TIMEOUT
    except (TypeError, ValueError):
        t = BASH_DEFAULT_TIMEOUT
    t = max(1.0, min(t, 120.0))
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(run_cwd),
            capture_output=True,
            text=True,
            timeout=t,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {t}s."
    except OSError as exc:
        return f"Error: could not run command: {exc}"
    out = (proc.stdout or "") + (proc.stderr or "")
    out = out.strip()
    if len(out) > 20000:
        out = out[:20000] + "\n...[truncated]"
    if not out:
        return f"Exit {proc.returncode} (no output)."
    return f"Exit {proc.returncode}:\n{out}"


def tool_web_fetch(url: str) -> str:
    if not url or not url.strip():
        return "Error: url must not be empty."
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "Error: url must start with http:// or https://"
    req = urllib.request.Request(url, headers={"User-Agent": "agentrouter-cli"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = resp.read(MAX_FETCH_BYTES + 1)
    except Exception as exc:
        return f"Error: fetch failed: {exc}"
    truncated = len(data) > MAX_FETCH_BYTES
    if truncated:
        data = data[:MAX_FETCH_BYTES]
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = data.decode("latin-1", errors="replace")
    if truncated:
        text += "\n...[truncated at 2MB]"
    return text


def execute_tool(name: str, args: dict | None, allow_bash: bool = False) -> str:
    args = dict(args or {})
    if name == "read_file":
        return tool_read_file(str(args.get("path", "")))
    if name == "write_file":
        return tool_write_file(str(args.get("path", "")), str(args.get("content", "")))
    if name == "edit_file":
        return tool_edit_file(
            str(args.get("path", "")),
            str(args.get("old_string", args.get("old", ""))),
            str(args.get("new_string", args.get("new", ""))),
        )
    if name == "bash":
        if not allow_bash:
            return "Error: bash is disabled. Re-run with --allow-bash."
        return tool_bash(
            str(args.get("command", "")),
            cwd=args.get("cwd"),
            timeout=args.get("timeout", BASH_DEFAULT_TIMEOUT),
        )
    if name == "web_fetch":
        return tool_web_fetch(str(args.get("url", "")))
    return f"Error: unknown tool {name!r}. Available: read_file, write_file, edit_file, bash, web_fetch."


def is_known_tool(name: str) -> bool:
    return name in TOOL_DESCRIPTIONS
