"""Stdlib GUI backend for AgentRouter.

Uses only ``http.server.ThreadingHTTPServer`` plus the existing
``AgentRouterClient``, config/session helpers, and ``streaming.py``.
No new dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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

try:
    from agentrouter import __version__ as _GUI_VERSION
except ImportError:
    _GUI_VERSION = "0.0.0"

STATIC_DIR = Path(__file__).resolve().parent / "static"

_STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}

GUI_TOKEN_ENV = "AGENTROUTER_GUI_TOKEN"


def _resolve_gui_token(explicit: Any = None) -> str:
    if explicit is not None:
        try:
            s = str(explicit)
        except Exception:
            return ""
        return s if s.strip() else ""
    try:
        env = os.environ.get(GUI_TOKEN_ENV, "")
    except Exception:
        return ""
    if not isinstance(env, str):
        return ""
    return env if env.strip() else ""


def _inject_gui_token(html: str, token: str) -> str:
    import html as _htmlmod

    try:
        esc = _htmlmod.escape(token, quote=True)
    except Exception:
        esc = token
    placeholder = '<meta name="ar-token" content="">'
    try:
        if placeholder in html:
            return html.replace(placeholder, '<meta name="ar-token" content="' + esc + '">', 1)
        tag = '<meta name="ar-token"'
        if tag in html:
            return html
        head = "<head>"
        if head in html:
            return html.replace(head, head + '<meta name="ar-token" content="' + esc + '">', 1)
    except Exception:
        pass
    return html


def _extract_reasoning(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    direct = payload.get("reasoning")
    if isinstance(direct, str) and direct:
        return direct
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            for container_key in ("delta", "message"):
                container = first.get(container_key)
                if isinstance(container, dict):
                    for k in ("reasoning_content", "reasoning", "thought"):
                        v = container.get(k)
                        if isinstance(v, str) and v:
                            return v
            for k in ("reasoning_content", "reasoning", "text_reasoning"):
                v = first.get(k)
                if isinstance(v, str) and v:
                    return v
    return ""


def _extract_usage(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _valid_session_id(sid: Any) -> bool:
    if not isinstance(sid, str):
        return False
    if len(sid) < 1 or len(sid) > 64:
        return False
    for c in sid:
        if not (c.isalnum() or c in ("-", "_")):
            return False
    return True


def _title_path(session_id: str) -> Path:
    return get_sessions_dir() / f"{session_id}.title"


def _read_title(session_id: str) -> str:
    try:
        text = _title_path(session_id).read_text(encoding="utf-8")
    except OSError:
        return ""
    return text.strip()[:120]


def _write_title(session_id: str, title: str) -> str:
    clean = title.strip()[:120]
    path = _title_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(clean, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not save title: {exc}") from exc
    return clean


def _validate_title(body: Any) -> str:
    title = body.get("title") if isinstance(body, dict) else None
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Title must be a non-empty string.")
    if len(title.strip()) > 120:
        raise ValueError("Title must be at most 120 characters.")
    return title.strip()


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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-AgentRouter-Token")

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
        try:
            token = ""
            try:
                token = getattr(self.server, "gui_token", "") or ""
            except Exception:
                token = ""
            if not token or not str(token).strip():
                token = _resolve_gui_token(None)
            if token and str(token).strip():
                html = _inject_gui_token(html, str(token))
        except Exception:
            pass
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
                "GET /api/version, GET /api/sessions, GET /api/config, "
                "POST /api/chat, POST /api/agent"
            )
        else:
            hint = "available paths: GET /, GET /static/<path>, GET /api/health, GET /api/models"
        self._send_json({"error": "not found", "path": path, "hint": hint}, status=404)

    def _reject_foreign(self) -> bool:
        try:
            cfg = load_config()
            validate_base_url(cfg.base_url)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return True
        return False

    def _blocked_by_token(self, path: str) -> bool:
        if not path.startswith("/api/"):
            return False
        try:
            expected = getattr(self.server, "gui_token", "")
        except Exception:
            expected = ""
        if not expected:
            expected = _resolve_gui_token(None)
        if not expected or not str(expected).strip():
            return False
        provided = None
        try:
            provided = self.headers.get("X-AgentRouter-Token")
        except Exception:
            provided = None
        if provided is None:
            try:
                provided = self.headers.get("x-agentrouter-token")
            except Exception:
                provided = None
        if provided != expected:
            self._send_json({"error": "unauthorized"}, status=401)
            return True
        return False

    def _handle_health(self) -> None:
        self._send_json({"status": "ok"}, status=200)

    def _handle_version(self) -> None:
        self._send_json({"version": _GUI_VERSION}, status=200)

    def _handle_static(self, path: str) -> None:
        rel = path[len("/static/"):] if path.startswith("/static/") else ""
        try:
            rel = unquote(rel)
        except Exception:
            self._send_not_found(path)
            return
        if not rel or rel.endswith("/") or "\x00" in rel or "\\" in rel:
            self._send_not_found(path)
            return
        parts = Path(rel).parts
        if not parts or any(p in ("..", ".", "") for p in parts):
            self._send_not_found(path)
            return
        if ".." in rel.split("/"):
            self._send_not_found(path)
            return
        suffix = Path(rel).suffix.lower()
        mime = _STATIC_MIME.get(suffix)
        if not mime:
            self._send_not_found(path)
            return
        try:
            static_root = STATIC_DIR.resolve()
            target = (static_root / rel).resolve()
            try:
                target.relative_to(static_root)
            except ValueError:
                self._send_not_found(path)
                return
        except (OSError, ValueError):
            self._send_not_found(path)
            return
        try:
            if not target.is_file():
                self._send_not_found(path)
                return
            stat = target.stat()
            etag = '"%x-%x"' % (stat.st_size, stat.st_mtime_ns)
        except OSError:
            self._send_not_found(path)
            return
        try:
            inm = self.headers.get("If-None-Match")
        except Exception:
            inm = None
        if inm and (inm.strip() == etag or etag in [t.strip() for t in inm.split(",")]):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return
        try:
            data = target.read_bytes()
        except OSError:
            self._send_not_found(path)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

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
        if path.startswith("/static/"):
            self._handle_static(path)
            return
        if self._blocked_by_token(path):
            return
        if path == "/api/health":
            self._handle_health()
            return
        if path == "/api/version":
            self._handle_version()
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
        if self._blocked_by_token(path):
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

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if self._reject_foreign():
            return
        if self._blocked_by_token(path):
            return
        if path.startswith("/api/sessions/"):
            self._handle_session_patch(path[len("/api/sessions/"):])
            return
        self._send_not_found(path)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if self._reject_foreign():
            return
        if self._blocked_by_token(path):
            return
        if path.startswith("/api/sessions/"):
            self._handle_session_delete(path[len("/api/sessions/"):])
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
            raw_iter = resp.iter_lines(decode_unicode=True)

            def _tapped_lines():
                for raw in raw_iter:
                    try:
                        if isinstance(raw, bytes):
                            try:
                                line_s = raw.decode("utf-8", "replace")
                            except Exception:
                                line_s = ""
                        else:
                            line_s = raw if isinstance(raw, str) else ""
                        s = line_s.strip() if isinstance(line_s, str) else ""
                        if s.startswith("data:"):
                            data_s = s[5:].strip()
                            if data_s and data_s != "[DONE]":
                                try:
                                    payload = json.loads(data_s)
                                except (ValueError, TypeError):
                                    payload = None
                                if isinstance(payload, dict):
                                    try:
                                        reasoning = _extract_reasoning(payload)
                                    except Exception:
                                        reasoning = ""
                                    if reasoning:
                                        try:
                                            self._emit_sse({"reasoning": reasoning})
                                        except (BrokenPipeError, ConnectionResetError):
                                            pass
                                    try:
                                        usage = _extract_usage(payload)
                                    except Exception:
                                        usage = None
                                    if usage:
                                        try:
                                            self._emit_sse({"usage": usage})
                                        except (BrokenPipeError, ConnectionResetError):
                                            pass
                    except Exception:
                        pass
                    yield raw

            class _TapResp:
                def iter_lines(self, decode_unicode=True):  # noqa: N802
                    return _tapped_lines()

            for token in iter_response_content(_TapResp()):  # type: ignore[arg-type]
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
                    items.append({"id": p.stem, "title": _read_title(p.stem)})
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"sessions": items})

    def _handle_session_get(self, session_id: str) -> None:
        session_id = session_id.strip().split("/")[0].split("?")[0]
        if not _valid_session_id(session_id):
            self._send_json({"error": "Invalid session id."}, status=400)
            return
        try:
            messages = load_session(session_id)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
            return
        self._send_json({"id": session_id, "title": _read_title(session_id), "messages": messages})

    def _handle_session_patch(self, session_id: str) -> None:
        session_id = session_id.strip().split("/")[0].split("?")[0]
        if not _valid_session_id(session_id):
            self._send_json({"error": "Invalid session id."}, status=400)
            return
        try:
            title = _validate_title(self._read_json())
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        try:
            load_session(session_id)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
            return
        try:
            saved = _write_title(session_id, title)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"id": session_id, "title": saved})

    def _handle_session_delete(self, session_id: str) -> None:
        from agentrouter.session import session_path as _spath

        session_id = session_id.strip().split("/")[0].split("?")[0]
        if not _valid_session_id(session_id):
            self._send_json({"error": "Invalid session id."}, status=400)
            return
        try:
            jsonl = _spath(session_id)
        except ValueError:
            self._send_json({"error": "Invalid session id."}, status=400)
            return
        title_p = _title_path(session_id)
        if not jsonl.exists() and not title_p.exists():
            self._send_json({"error": f"Session {session_id!r} not found."}, status=404)
            return
        try:
            if jsonl.exists():
                jsonl.unlink()
            if title_p.exists():
                title_p.unlink()
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"ok": True, "id": session_id})

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


def create_server(host: str = "127.0.0.1", port: int = 8787, token: Any = None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), GuiHandler)
    try:
        server.gui_token = _resolve_gui_token(token)  # type: ignore[attr-defined]
    except Exception:
        pass
    return server


def serve(port: int = 8787, host: str = "127.0.0.1", token: Any = None) -> None:
    server = create_server(host, port, token)
    print(f"Serving at http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def run(host: str = "127.0.0.1", port: int = 8787, token: Any = None) -> None:
    server = create_server(host, port, token)
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
