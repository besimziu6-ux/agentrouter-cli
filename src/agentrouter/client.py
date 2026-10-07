"""HTTP client for the AgentRouter API.

AgentRouter-only: every request goes to ``https://agentrouter.org/v1``.
Any other base URL is rejected up front so traffic cannot be redirected.
"""

from __future__ import annotations

from typing import Any

import requests

from agentrouter.config import DEFAULT_BASE_URL, Config, load_config, validate_base_url

BASE_URL = DEFAULT_BASE_URL
MODELS_PATH = "/models"
CHAT_COMPLETIONS_PATH = "/chat/completions"
DEFAULT_TIMEOUT = 30.0


class AgentRouterError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RooVetGit/Roo-Cline",
        "X-Title": "Roo Code",
        "User-Agent": "RooCode/3.54.0",
        "X-Stainless-Lang": "js",
        "X-Stainless-Package-Version": "5.12.2",
        "X-Stainless-OS": "Windows",
        "X-Stainless-Arch": "x64",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "node",
    }


def _error_for_status(resp: requests.Response) -> AgentRouterError:
    status = resp.status_code
    try:
        body = resp.text.strip()
    except Exception:
        body = ""
    detail = f" {body}" if body else ""
    if status == 401:
        return AgentRouterError(
            "Authentication failed (401): invalid or missing API key. "
            "Run `agentrouter config set-key` to set a valid key." + detail,
            status_code=status,
        )
    if status == 404:
        return AgentRouterError(
            f"Not found (404): the requested resource does not exist.{detail}",
            status_code=status,
        )
    if status == 429:
        return AgentRouterError(
            f"Rate limited (429): too many requests, retry later.{detail}",
            status_code=status,
        )
    return AgentRouterError(
        f"Request failed ({status}):{detail}" if detail else f"Request failed ({status}).",
        status_code=status,
    )


class AgentRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        config: Config | None = None,
    ):
        resolved_base = validate_base_url(base_url)
        resolved_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        if resolved_key is None and config is not None:
            if config.api_key and config.api_key.strip():
                resolved_key = config.api_key.strip()
        if resolved_key is None:
            loaded = load_config()
            if loaded.api_key and loaded.api_key.strip():
                resolved_key = loaded.api_key.strip()
            if resolved_base == BASE_URL and loaded.base_url != BASE_URL:
                resolved_base = validate_base_url(loaded.base_url)
        if not resolved_key:
            raise AgentRouterError(
                "No API key configured. Run `agentrouter config set-key` "
                "to store a key, or set AGENTROUTER_API_KEY."
            )
        self.api_key = resolved_key
        self.base_url = resolved_base
        self.timeout = timeout

    @classmethod
    def from_config(cls, config: Config, timeout: float = DEFAULT_TIMEOUT) -> "AgentRouterClient":
        key = config.require_api_key()
        return cls(api_key=key, base_url=config.base_url, timeout=timeout, config=config)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        headers = _auth_headers(self.api_key)
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=self.timeout)
            else:
                resp = requests.post(url, headers=headers, json=payload or {}, timeout=self.timeout)
        except requests.Timeout as exc:
            raise AgentRouterError(f"Request to {url} timed out after {self.timeout}s.") from exc
        except requests.ConnectionError as exc:
            raise AgentRouterError(f"Could not connect to {url}: {exc}.") from exc
        except requests.RequestException as exc:
            raise AgentRouterError(f"Request to {url} failed: {exc}.") from exc

        if resp.status_code in (401, 404, 429):
            raise _error_for_status(resp)
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise _error_for_status(resp) from exc

        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise AgentRouterError(f"Invalid JSON response from {url}.") from exc

    def list_models(self) -> Any:
        return self._request("GET", MODELS_PATH)

    def chat_completions(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if not messages:
            raise ValueError("messages must not be empty.")
        payload: dict[str, Any] = {"messages": messages}
        if model:
            payload["model"] = model
        payload.update(kwargs)
        if "model" not in payload or not payload["model"]:
            loaded = load_config()
            if loaded.default_model:
                payload["model"] = loaded.default_model
            else:
                raise ValueError("A model is required (pass model= or set default_model).")
        return self._request("POST", CHAT_COMPLETIONS_PATH, payload)
