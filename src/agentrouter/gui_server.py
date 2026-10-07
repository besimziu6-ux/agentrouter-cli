"""Stdlib GUI backend for AgentRouter.

Uses only ``http.server.ThreadingHTTPServer`` plus the existing
``AgentRouterClient``, config/session helpers, and ``streaming.py``.
No new dependencies.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

from agentrouter.client import (
    CHAT_COMPLETIONS_PATH,
    DEFAULT_TIMEOUT,
    AgentRouterClient,
    AgentRouterError,
    _auth_headers,
)
from agentrouter.config import (
    DEFAULT_BASE_URL,
    load_config,
    save_config,
    validate_base_url,
)
from agentrouter.session import get_sessions_dir, load_session
from agentrouter.streaming import iter_response_content

try:
    from agentrouter.gui_html import GUI_HTML
except ImportError:
    GUI_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>AgentRouter</title></head>
<body><h1>AgentRouter GUI</h1>
<p>gui_html.py not found. API is available under /api/.</p>
</body></html>"""


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}{'*' * 4}{key[-4:]}"


def _masked_config() -> dict[str, Any]:
    config = load_config()
    validate_base_url(config.base_url)
    if config.api_key:
        shown = _mask_key(config.api_key)
        has_key = True
    else:
        shown = "(not set)"
        has_key = False
    return {
        "base_url": config.base_url,
        "api_key": shown,
        "has_key": has_key,
        "default_model": config.default_model,
    }


def _resolve_model(body: dict[str, Any], config: Any) -> str | None:
    for key in ("model", "default_model"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    if config.default_model and config.default_model.strip():
        return config.default_model.strip()
    return None


def _resolve_messages(body: dict[str, Any]) -> list[dict[str, Any]] | None:
    msgs = body.get("messages")
    if isinstance(msgs, list) and msgs:
        return msgs
    for key in ("prompt", "goal", "input", "text"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return [{"role": "user", "content": val.strip()}]
    return None


class GuiHandler(BaseHTTPRequestHandler):
    server_version = "AgentRouterGUI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_favicon(self) -> None:
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def _send_not_found(self, path: str) -> None:
        if path.startswith("/api/"):
            hint = (
                "available paths: GET /api/health, GET /api/models, "
                "GET /api/sessions, GET /api/config, "
                "POST /api/chat, POST /api/agent"
            )
        else:
            hint = "available paths: GET /, GET /api/health, GET /api/models"
        self._send_json({"error": "not found", "path": path, "hint": hint}, status=404)

    def _reject_foreign(self) -> bool:
        try:
            cfg = load_config()
            validate_base_url(cfg.base_url)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return True
        return False

    def _handle_health(self) -> None:
        self._send_json({"status": "ok"}, status=200)

    def _send_sse_headers(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()

    def _emit_sse(self, data: Any) -> None:
        line = f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
        self.wfile.write(line)
        self.wfile.flush()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if self._reject_foreign():
            return
        if path == "/" or path == "/index.html":
            self._send_html(GUI_HTML)
            return
        if path == "/favicon.ico":
            self._send_favicon()
            return
        if path == "/api/health":
            self._handle_health()
            return
        if path == "/api/models":
            self._handle_models()
            return
        if path == "/api/sessions":
            self._handle_sessions_list()
            return
        if path.startswith("/api/sessions/"):
            self._handle_session_get(path[len("/api/sessions/"):])
            return
        if path == "/api/config":
            self._handle_config_get()
            return
        self._send_not_found(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if self._reject_foreign():
            return
        if path == "/api/chat":
            self._handle_chat()
            return
        if path == "/api/agent":
            self._handle_agent()
            return
        if path == "/api/config":
            self._handle_config_post()
            return
        self._send_not_found(path)

    def _handle_models(self) -> None:
        try:
            config = load_config()
            validate_base_url(config.base_url)
            client = AgentRouterClient.from_config(
                config, timeout=DEFAULT_TIMEOUT
            )
            data = client.list_models()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        except AgentRouterError as exc:
            self._send_json(
                {"error": str(exc)}, status=exc.status_code or 502
            )
            return
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json(data)

    def _handle_chat(self) -> None:
        body = self._read_json()
        try:
            config = load_config()
            validate_base_url(config.base_url)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        try:
            api_key = config.require_api_key()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=401)
            return
        messages = _resolve_messages(body)
        if not messages:
            self._send_json({"error": "messages must not be empty."}, status=400)
            return
        model = _resolve_model(body, config)
        if not model:
            self._send_json(
                {"error": "No model specified. Pass model or set default_model."},
                status=400,
            )
            return
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        for key in ("max_tokens", "temperature"):
            if body.get(key) is not None:
                payload[key] = body[key]
        url = f"{config.base_url}{CHAT_COMPLETIONS_PATH}"
        try:
            resp = requests.post(
                url,
                headers=_auth_headers(api_key),
                json=payload,
                timeout=DEFAULT_TIMEOUT,
                stream=True,
            )
        except requests.Timeout:
            self._send_json(
                {"error": f"Request to {url} timed out."}, status=504
            )
            return
        except requests.RequestException as exc:
            self._send_json({"error": f"Request failed: {exc}"}, status=502)
            return
        if resp.status_code != 200:
            try:
                detail = resp.text
            except Exception:
                detail = ""
            try:
                resp.close()
            except Exception:
                pass
            self._send_json(
                {"error": detail.strip() or f"Request failed ({resp.status_code})."},
                status=resp.status_code,
            )
            return
        self._send_sse_headers()
        try:
            for token in iter_response_content(resp):
                try:
                    self._emit_sse({"content": token})
                except (BrokenPipeError, ConnectionResetError):
                    break
            try:
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _handle_agent(self) -> None:
        from agentrouter.agent import run_agent

        body = self._read_json()
        try:
            config = load_config()
            validate_base_url(config.base_url)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        goal = ""
        for key in ("goal", "prompt", "input", "text"):
            val = body.get(key)
            if isinstance(val, str) and val.strip():
                goal = val.strip()
                break
        if not goal:
            self._send_json({"error": "Goal must not be empty."}, status=400)
            return
        model = _resolve_model(body, config)
        if not model:
            self._send_json(
                {"error": "No model specified. Pass model or set default_model."},
                status=400,
            )
            return
        try:
            max_steps = int(body.get("max_steps", 10))
        except (TypeError, ValueError):
            max_steps = 10
        if max_steps <= 0:
            self._send_json(
                {"error": "--max-steps must be a positive integer."}, status=400
            )
            return
        allow_bash = bool(body.get("allow_bash", False))
        resume_id = body.get("resume_id") or body.get("session_id") or body.get("resume")
        if resume_id is not None and not str(resume_id).strip():
            resume_id = None
        system = body.get("system")
        if system is not None and not str(system).strip():
            system = None
        extra: dict[str, Any] = {}
        for key in ("max_tokens", "temperature"):
            if body.get(key) is not None:
                extra[key] = body[key]
        timeout = body.get("timeout")
        try:
            timeout_f = float(timeout) if timeout else None
        except (TypeError, ValueError):
            timeout_f = None

        self._send_sse_headers()

        def on_event(event: dict[str, Any]) -> None:
            self._emit_sse(event)

        try:
            run_agent(
                goal,
                model,
                max_steps=max_steps,
                allow_bash=allow_bash,
                resume_id=str(resume_id) if resume_id else None,
                timeout=timeout_f,
                extra_kwargs=extra,
                system=str(system) if system else None,
                verbose=False,
                on_event=on_event,
            )
        except (BrokenPipeError, ConnectionResetError):
            return
        except (ValueError, AgentRouterError) as exc:
            try:
                self._emit_sse({"type": "error", "error": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        except Exception as exc:
            try:
                self._emit_sse({"type": "error", "error": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

    def _handle_sessions_list(self) -> None:
        sessions_dir = get_sessions_dir()
        items: list[dict[str, Any]] = []
        try:
            if sessions_dir.exists():
                for p in sorted(sessions_dir.glob("*.jsonl")):
                    items.append({"id": p.stem})
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"sessions": items})

    def _handle_session_get(self, session_id: str) -> None:
        session_id = session_id.strip().split("/")[0].split("?")[0]
        if not session_id:
            self._send_json({"error": "Invalid session id."}, status=400)
            return
        try:
            messages = load_session(session_id)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
            return
        self._send_json({"id": session_id, "messages": messages})

    def _handle_config_get(self) -> None:
        try:
            data = _masked_config()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json(data)

    def _handle_config_post(self) -> None:
        body = self._read_json()
        api_key = body.get("api_key", body.get("key"))
        if api_key is not None and not isinstance(api_key, str):
            self._send_json({"error": "API key must be a string."}, status=400)
            return
        model = body.get("default_model", body.get("model"))
        if model is not None and not isinstance(model, str):
            self._send_json({"error": "Model must be a string."}, status=400)
            return
        base_url = body.get("base_url")
        if base_url is not None:
            if not isinstance(base_url, str):
                self._send_json({"error": "base_url must be a string."}, status=400)
                return
            try:
                validate_base_url(base_url)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
        if (
            (api_key is None or not api_key.strip())
            and (model is None or not model.strip())
            and base_url is None
        ):
            self._send_json({"error": "Nothing to update."}, status=400)
            return
        try:
            save_config(
                api_key=api_key.strip() if isinstance(api_key, str) and api_key.strip() else None,
                base_url=base_url if isinstance(base_url, str) and base_url.strip() else None,
                default_model=model.strip() if isinstance(model, str) and model.strip() else None,
            )
            data = _masked_config()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json(data)


def create_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), GuiHandler)


def serve(port: int = 8787, host: str = "127.0.0.1") -> None:
    server = create_server(host, port)
    print(f"Serving at http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = create_server(host, port)
    print(f"Serving AgentRouter GUI on http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgentRouter GUI backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    run(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
