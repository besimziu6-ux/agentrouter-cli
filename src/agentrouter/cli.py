"""Argparse CLI for AgentRouter: config, models, and chat with streaming."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Any

import requests

from agentrouter import __version__
from agentrouter.client import (
    CHAT_COMPLETIONS_PATH,
    DEFAULT_TIMEOUT,
    AgentRouterClient,
    AgentRouterError,
)
from agentrouter.config import load_config, save_config
from agentrouter.streaming import iter_response_content


def _add_serve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=8787, help="Port to serve on (default 8787)")
    p.add_argument("--host", default="127.0.0.1", help="Host to bind (default 127.0.0.1)")
    p.add_argument("--open", dest="open", action="store_true", default=False, help="Open browser automatically")
    p.add_argument("--no-open", dest="open", action="store_false", help="Do not open browser")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentrouter", description="CLI for AgentRouter")
    p.add_argument("--version", action="store_true", help="Print version and exit")
    p.add_argument("--update", action="store_true", help="Upgrade to latest version (same as update apply)")
    p.add_argument("--upgrade", action="store_true", help="Alias for --update")
    sub = p.add_subparsers(dest="command")

    cfg = sub.add_parser("config", help="Manage local configuration")
    cfg_sub = cfg.add_subparsers(dest="config_command", required=True)

    set_key = cfg_sub.add_parser("set-key", help="Store the API key")
    set_key.add_argument("key", nargs="?", default=None, help="API key (prompts if omitted)")
    set_key.add_argument("--stdin", action="store_true", help="Read the key from stdin")
    set_key.set_defaults(func=cmd_config_set_key)

    show = cfg_sub.add_parser("show", help="Show current configuration")
    show.add_argument("--show-key", action="store_true", help="Reveal the full API key")
    show.set_defaults(func=cmd_config_show)

    models = sub.add_parser("models", help="Query available models")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    models_list = models_sub.add_parser("list", help="List model ids")
    models_list.add_argument("--json", action="store_true", help="Print raw JSON response")
    models_list.add_argument("--timeout", type=float, default=None, help="Request timeout in seconds")
    models_list.set_defaults(func=cmd_models_list)

    chat = sub.add_parser("chat", help="Send a chat completion request")
    chat.add_argument("prompt", nargs="?", default=None, help='Prompt text, or "-" to read from stdin')
    chat.add_argument("-m", "--model", default=None, help="Model id (defaults to configured default_model)")
    chat.add_argument(
        "--stream",
        dest="stream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stream tokens as they arrive (use --no-stream to disable)",
    )
    chat.add_argument("--max-tokens", type=int, default=None, help="Maximum tokens in the completion")
    chat.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    chat.add_argument("--system", default=None, help="System prompt prepended to the conversation")
    chat.add_argument("--json", action="store_true", help="Print raw JSON response (implies --no-stream)")
    chat.add_argument("--timeout", type=float, default=None, help="Request timeout in seconds")
    chat.set_defaults(func=cmd_chat)

    agent = sub.add_parser("agent", help="Run autonomous agent loop with tools")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    run = agent_sub.add_parser("run", help="Run agent toward a goal")
    run.add_argument("goal", nargs="?", default=None, help='Goal text, or "-" to read from stdin')
    run.add_argument("-m", "--model", default=None, help="Model id (defaults to configured default_model)")
    run.add_argument("--max-steps", type=int, default=10, help="Maximum agent steps (default 10)")
    run.add_argument("--allow-bash", action="store_true", help="Allow the agent to run shell commands")
    run.add_argument("--resume", default=None, help="Resume a prior session id")
    run.add_argument("--timeout", type=float, default=None, help="Request timeout in seconds")
    run.add_argument("--max-tokens", type=int, default=None, help="Maximum tokens in each completion")
    run.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    run.add_argument("--system", default=None, help="Extra system prompt prepended to agent instructions")
    run.set_defaults(func=cmd_agent_run)

    gui = sub.add_parser("gui", help="Launch local GUI")
    _add_serve_args(gui)
    gui_sub = gui.add_subparsers(dest="gui_command", required=False)
    serve_p = gui_sub.add_parser("serve", help="Serve the local GUI in a browser")
    _add_serve_args(serve_p)
    serve_p.set_defaults(func=cmd_gui_serve)
    gui.set_defaults(func=cmd_gui_serve)

    serve_top = sub.add_parser("serve", help="Serve the local GUI in a browser")
    _add_serve_args(serve_top)
    serve_top.set_defaults(func=cmd_gui_serve)

    upd = sub.add_parser("update", help="Check for CLI updates")
    upd_sub = upd.add_subparsers(dest="update_command", required=True)
    check_p = upd_sub.add_parser("check", help="Check for updates")
    check_p.set_defaults(func=cmd_update_check)
    apply_p = upd_sub.add_parser("apply", help="Apply update to latest version")
    apply_p.set_defaults(func=cmd_update_apply)

    return p


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}{'*' * 4}{key[-4:]}"


def _read_piped_stdin() -> str:
    if sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _resolve_prompt(prompt_arg: str | None) -> str:
    if prompt_arg == "-":
        try:
            text = sys.stdin.read()
        except Exception as exc:
            raise ValueError(f"Could not read prompt from stdin: {exc}") from exc
        if not text.strip():
            raise ValueError("No prompt provided on stdin (got empty input for '-').")
        return text.strip()
    piped = _read_piped_stdin()
    if prompt_arg is not None:
        if piped.strip():
            return f"{piped.strip()}\n\n{prompt_arg}"
        if not prompt_arg.strip():
            raise ValueError("Prompt must not be empty.")
        return prompt_arg
    if piped.strip():
        return piped.strip()
    raise ValueError('No prompt provided. Pass a prompt argument, pipe stdin, or use "-" to read stdin.')


def _make_client(timeout: float | None) -> AgentRouterClient:
    config = load_config()
    try:
        return AgentRouterClient.from_config(config, timeout=timeout or DEFAULT_TIMEOUT)
    except ValueError as exc:
        raise AgentRouterError(str(exc)) from exc


def cmd_config_set_key(args: argparse.Namespace) -> int:
    key: str | None = args.key
    if key is not None:
        key = key.strip()
    elif args.stdin or not sys.stdin.isatty():
        try:
            key = sys.stdin.read().strip()
        except Exception as exc:
            raise ValueError(f"Could not read key from stdin: {exc}") from exc
    else:
        try:
            key = getpass.getpass("Enter API key: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise ValueError("No key entered.") from None
    if not key:
        raise ValueError("API key must not be empty.")
    saved = save_config(api_key=key)
    print(f"Saved API key to {saved.config_path}")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    config = load_config()
    if config.api_key:
        shown = config.api_key if args.show_key else _mask_key(config.api_key)
    else:
        shown = "(not set)"
    print(f"base_url: {config.base_url}")
    print(f"api_key: {shown}")
    print(f"default_model: {config.default_model or '(not set)'}")
    print(f"config_path: {config.config_path or '(unknown)'}")
    return 0


def _extract_model_ids(data: Any) -> list[str]:
    if isinstance(data, dict):
        items = data.get("data", data.get("models", []))
    elif isinstance(data, list):
        items = data
    else:
        items = []
    ids: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str) and item.strip():
                ids.append(item.strip())
            elif isinstance(item, dict):
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    ids.append(model_id.strip())
    return ids


def cmd_models_list(args: argparse.Namespace) -> int:
    client = _make_client(args.timeout)
    data = client.list_models()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    for model_id in _extract_model_ids(data):
        print(model_id)
    return 0


def _build_messages(prompt: str, system: str | None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system and system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


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


def _stream_error(status: int, body: str) -> AgentRouterError:
    detail = f" {body.strip()}" if body and body.strip() else ""
    if status == 401:
        return AgentRouterError(
            "Authentication failed (401): invalid or missing API key."
            " Run `agentrouter config set-key` to set a valid key." + detail,
            status_code=status,
        )
    if status == 404:
        return AgentRouterError(f"Not found (404): the requested resource does not exist.{detail}", status_code=status)
    if status == 429:
        return AgentRouterError(f"Rate limited (429): too many requests, retry later.{detail}", status_code=status)
    return AgentRouterError(
        f"Request failed ({status}):{detail}" if detail else f"Request failed ({status}).",
        status_code=status,
    )


def cmd_chat(args: argparse.Namespace) -> int:
    prompt = _resolve_prompt(args.prompt)
    config = load_config()
    model = args.model or config.default_model
    if not model:
        raise ValueError("No model specified. Pass -m/--model or set a default_model in config.")
    if args.max_tokens is not None and args.max_tokens <= 0:
        raise ValueError("--max-tokens must be a positive integer.")
    timeout = args.timeout or DEFAULT_TIMEOUT
    messages = _build_messages(prompt, args.system)

    payload: dict[str, Any] = {"model": model, "messages": messages}
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        payload["temperature"] = args.temperature

    as_json = bool(args.json)
    stream = False if as_json else bool(args.stream)

    if not stream:
        client = _make_client(args.timeout)
        data = client.chat_completions(messages, model=model, **_extra_chat_kwargs(args))
        if as_json:
            print(json.dumps(data, indent=2))
            return 0
        print(_extract_reply_text(data))
        return 0

    try:
        api_key = config.require_api_key()
    except ValueError as exc:
        raise AgentRouterError(str(exc)) from exc
    url = f"{config.base_url}{CHAT_COMPLETIONS_PATH}"
    payload["stream"] = True
    try:
        resp = requests.post(
            url,
            headers=_auth_headers(api_key),
            json=payload,
            timeout=timeout,
            stream=True,
        )
    except requests.Timeout as exc:
        raise AgentRouterError(f"Request to {url} timed out after {timeout}s.") from exc
    except requests.ConnectionError as exc:
        raise AgentRouterError(f"Could not connect to {url}: {exc}.") from exc
    except requests.RequestException as exc:
        raise AgentRouterError(f"Request to {url} failed: {exc}.") from exc

    if resp.status_code != 200:
        try:
            body = resp.text
        except Exception:
            body = ""
        raise _stream_error(resp.status_code, body)

    printed_any = False
    try:
        for token in iter_response_content(resp):
            sys.stdout.write(token)
            sys.stdout.flush()
            printed_any = True
    finally:
        try:
            resp.close()
        except Exception:
            pass
    if printed_any:
        sys.stdout.write("\n")
        sys.stdout.flush()
    return 0


def _extra_chat_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if args.max_tokens is not None:
        extra["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        extra["temperature"] = args.temperature
    return extra


def cmd_agent_run(args: argparse.Namespace) -> int:
    from agentrouter.agent import run_agent

    goal = _resolve_prompt(args.goal)
    config = load_config()
    model = args.model or config.default_model
    if not model:
        raise ValueError("No model specified. Pass -m/--model or set a default_model in config.")
    max_steps = args.max_steps if args.max_steps is not None else 10
    if max_steps <= 0:
        raise ValueError("--max-steps must be a positive integer.")
    timeout = args.timeout or DEFAULT_TIMEOUT
    final_text, session_id = run_agent(
        goal,
        model,
        max_steps=max_steps,
        allow_bash=bool(args.allow_bash),
        resume_id=args.resume,
        timeout=timeout,
        extra_kwargs=_extra_chat_kwargs(args),
        system=args.system,
        verbose=True,
    )
    if final_text:
        print(final_text)
    print(f"Session: {session_id}", file=sys.stderr)
    return 0


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


def cmd_gui_serve(args: argparse.Namespace) -> int:
    from agentrouter import gui_server

    host: str = args.host
    port: int = args.port
    url = f"http://{host}:{port}"
    if bool(getattr(args, "open", False)):
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass
    try:
        gui_server.serve(port, host)
    except OSError as exc:
        msg = str(exc).lower()
        if exc.errno in (48, 98, 99, 10013, 10048) or "in use" in msg or "already in use" in msg:
            print(f"Error: Port {port} in use, try --port {port + 1}", file=sys.stderr)
            return 1
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


def cmd_update_check(args: argparse.Namespace) -> int:
    from agentrouter.update import cmd_update_check as _check

    return int(_check(args))


def cmd_update_apply(args: argparse.Namespace) -> int:
    from agentrouter.update import cmd_update_apply as _apply

    return int(_apply(args))


def _maybe_auto_check(args: argparse.Namespace) -> None:
    cmd = getattr(args, "command", None)
    if cmd is not None and cmd not in ("chat", "agent", "gui", "serve"):
        return
    try:
        from agentrouter.update import maybe_auto_check

        maybe_auto_check()
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if getattr(args, "update", False) or getattr(args, "upgrade", False):
        from agentrouter.update import cmd_update_apply as _apply

        return int(_apply(args))
    func = getattr(args, "func", None)
    if func is None:
        command = getattr(args, "command", None)
        gui_command = getattr(args, "gui_command", None)
        if command is None or (command == "gui" and gui_command is None):
            if getattr(args, "host", None) is None:
                args.host = "127.0.0.1"
            if getattr(args, "port", None) is None:
                args.port = 8787
            if not hasattr(args, "open"):
                args.open = False
            func = cmd_gui_serve
        else:
            print("agentrouter: no command given. Use --help.", file=sys.stderr)
            return 2
    _maybe_auto_check(args)
    try:
        return int(func(args))
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        try:
            sys.stderr.close()
        except Exception:
            pass
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 1
    except (AgentRouterError, ValueError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
