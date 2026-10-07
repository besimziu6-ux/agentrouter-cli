"""Update checker for AgentRouter CLI."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PYPROJECT_URL = "https://raw.githubusercontent.com/besimziu6-ux/agentrouter-cli/main/pyproject.toml"
GIT_URL = "git+https://github.com/besimziu6-ux/agentrouter-cli.git"
CURL_HINT = "curl -fsSL https://raw.githubusercontent.com/besimziu6-ux/agentrouter-cli/main/install.sh | bash"
CACHE_TTL = 24 * 3600


def _cache_file() -> Path:
    return Path.home() / ".cache" / "agentrouter" / "last-check"


def _parse_version(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in v.strip().split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def _is_newer(latest: str, current: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return False


def _read_cache() -> tuple[str | None, float | None]:
    try:
        p = _cache_file()
        if not p.exists():
            return None, None
        data = json.loads(p.read_text(encoding="utf-8"))
        latest = data.get("latest")
        checked_at = data.get("checked_at")
        if isinstance(latest, str) and isinstance(checked_at, (int, float)):
            return latest, float(checked_at)
    except Exception:
        pass
    return None, None


def _write_cache(latest: str) -> None:
    try:
        p = _cache_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"latest": latest, "checked_at": time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass


def _fetch_latest() -> str | None:
    with urllib.request.urlopen(PYPROJECT_URL, timeout=5) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8", errors="replace")
    m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', raw, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def check_for_updates() -> tuple[bool, str, str]:
    from agentrouter import __version__ as current

    try:
        cached_latest, checked_at = _read_cache()
    except Exception:
        cached_latest, checked_at = None, None
    now = time.time()
    if cached_latest and checked_at and (now - checked_at) < CACHE_TTL:
        return (_is_newer(cached_latest, current), cached_latest, current)
    try:
        latest = _fetch_latest()
    except Exception:
        if cached_latest:
            return (_is_newer(cached_latest, current), cached_latest, current)
        return (False, current, current)
    if not latest:
        if cached_latest:
            return (_is_newer(cached_latest, current), cached_latest, current)
        return (False, current, current)
    _write_cache(latest)
    return (_is_newer(latest, current), latest, current)


def maybe_auto_check() -> None:
    try:
        has_update, latest, current = check_for_updates()
    except Exception:
        return
    if has_update:
        try:
            print(
                f"Update available: v{current} -> v{latest}, run agentrouter update apply",
                file=sys.stderr,
            )
        except Exception:
            pass


def cmd_update_check(args) -> int:  # noqa: ANN001, ANN202
    has_update, latest, current = check_for_updates()
    print(f"current: v{current}")
    print(f"latest: v{latest}")
    if has_update:
        print("Run: agentrouter update apply")
    else:
        print("Up to date.")
    return 0


def cmd_update_apply(args) -> int:  # noqa: ANN001, ANN202
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", GIT_URL],
            check=False,
        )
        rc = int(result.returncode)
    except Exception as exc:
        print(f"Error: update failed: {exc}", file=sys.stderr)
        rc = 1
    print("If you installed via curl, re-run the installer instead:")
    print(f"  {CURL_HINT}")
    return rc
