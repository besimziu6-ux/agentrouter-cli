"""Config loader for AgentRouter CLI.

Resolution order:
  1. ``AGENTROUTER_API_KEY`` environment variable (takes precedence).
  2. ``~/.config/agentrouter/config.json`` file with ``api_key``,
     ``base_url``, and ``default_model`` keys.

Only the official AgentRouter endpoint is allowed. Any other
``base_url`` is rejected.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://agentrouter.org/v1"
ENV_API_KEY = "AGENTROUTER_API_KEY"
ENV_BASE_URL = "AGENTROUTER_BASE_URL"
ENV_DEFAULT_MODEL = "AGENTROUTER_DEFAULT_MODEL"


def get_config_path() -> Path:
    return Path.home() / ".config" / "agentrouter" / "config.json"


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def validate_base_url(url: str) -> str:
    normalized = _normalize_base_url(url)
    if normalized != DEFAULT_BASE_URL:
        raise ValueError(
            f"Unsupported base URL {url!r}: only {DEFAULT_BASE_URL} is allowed."
        )
    return normalized


@dataclass
class Config:
    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    default_model: str | None = None
    config_path: Path | None = None

    def require_api_key(self) -> str:
        if not self.api_key:
            raise ValueError(
                "No API key configured. Run `agentrouter config set-key` "
                "to store a key, or set AGENTROUTER_API_KEY."
            )
        return self.api_key


def _read_config_file(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ValueError(f"Could not read config file {path}: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file {path}: expected a JSON object.")
    return data


def load_config(config_path: Path | str | None = None) -> Config:
    path = Path(config_path) if config_path else get_config_path()
    file_data = _read_config_file(path)

    file_key = file_data.get("api_key")
    file_base_url = file_data.get("base_url", DEFAULT_BASE_URL)
    file_model = file_data.get("default_model")

    env_key = os.environ.get(ENV_API_KEY)
    api_key = env_key.strip() if env_key and env_key.strip() else (
        file_key.strip() if isinstance(file_key, str) and file_key.strip() else None
    )

    env_base = os.environ.get(ENV_BASE_URL)
    raw_base = env_base if env_base and env_base.strip() else (
        file_base_url if isinstance(file_base_url, str) and file_base_url.strip()
        else DEFAULT_BASE_URL
    )
    base_url = validate_base_url(raw_base)

    env_model = os.environ.get(ENV_DEFAULT_MODEL)
    if env_model and env_model.strip():
        default_model = env_model.strip()
    elif isinstance(file_model, str) and file_model.strip():
        default_model = file_model.strip()
    else:
        default_model = None

    return Config(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        config_path=path,
    )


def save_config(
    api_key: str | None = None,
    base_url: str | None = None,
    default_model: str | None = None,
    config_path: Path | str | None = None,
) -> Config:
    path = Path(config_path) if config_path else get_config_path()
    existing = _read_config_file(path)

    if api_key is not None:
        cleaned = api_key.strip()
        if not cleaned:
            raise ValueError("API key must not be empty.")
        existing["api_key"] = cleaned
    if base_url is not None:
        existing["base_url"] = validate_base_url(base_url)
    if default_model is not None:
        cleaned_model = default_model.strip()
        if cleaned_model:
            existing["default_model"] = cleaned_model
        else:
            existing.pop("default_model", None)

    if "base_url" in existing and isinstance(existing["base_url"], str):
        existing["base_url"] = validate_base_url(existing["base_url"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    return load_config(path)
