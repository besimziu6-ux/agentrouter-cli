# agentrouter-cli

CLI for [AgentRouter](https://agentrouter.org) — chat completions, model listing, and an autonomous file/shell agent with tools.

AgentRouter-only: every API request goes to `https://agentrouter.org/v1`. Any other base URL is rejected by config validation and the HTTP client, so traffic cannot be redirected elsewhere.

## Install

Requires Python 3.9+.

Quick install (creates a venv in `~/.local/share/agentrouter/venv`, no sudo):

```bash
curl -fsSL https://raw.githubusercontent.com/besimziu6-ux/agentrouter-cli/main/install.sh | bash
```

From PyPI:

```bash
pip install agentrouter-cli
```

From source:

```bash
git clone https://github.com/besimziu6-ux/agentrouter-cli
cd agentrouter-cli
pip install -e ".[dev]"
```

Verify:

```bash
agentrouter --help
```

## API key setup

Pick one. Environment variable takes precedence over the config file.

Option 1 — config file (`~/.config/agentrouter/config.json`):

```bash
agentrouter config set-key
# or non-interactive:
agentrouter config set-key sk-your-key-here
# or via stdin (CI):
echo "$AGENTROUTER_API_KEY" | agentrouter config set-key --stdin
```

Option 2 — environment variable:

```bash
export AGENTROUTER_API_KEY=sk-your-key-here
```

Inspect current config (key is masked unless `--show-key`):

```bash
agentrouter config show
agentrouter config show --show-key
```

## Quickstart

List models:

```bash
agentrouter models list
agentrouter models list --json
```

Chat (streams by default):

```bash
agentrouter chat "Explain recursion in one sentence" -m <model-id>
agentrouter chat "Summarize this file" --system "You are concise" -m <model-id>
echo "pipeline input" | agentrouter chat -m <model-id>
agentrouter chat --no-stream "One-shot answer" -m <model-id>
agentrouter chat --json "Raw JSON output" -m <model-id>
```

Set a default model so `-m` is optional:

```bash
export AGENTROUTER_DEFAULT_MODEL=<model-id>
# then:
agentrouter chat "Hello without -m flag"
```

Run the autonomous agent (reads/writes files, fetches URLs, runs shell with `--allow-bash`):

```bash
agentrouter agent run "Create hello.txt with 'hi'" -m <model-id>
agentrouter agent run "Summarize README.md" -m <model-id> --max-steps 10
agentrouter agent run "Run tests and fix failures" -m <model-id> --allow-bash
agentrouter agent run "Continue prior work" -m <model-id> --resume <session-id>
```

Sessions are stored as JSONL under `~/.config/agentrouter/sessions/`.

## GUI

Local browser UI built on stdlib `http.server` (no new dependencies, reuses `requests` only).
Frontend ships as packaged static files under `src/agentrouter/static/` (no CDN, no third-party code).

Bare `agentrouter` launches the GUI (same as `serve`):

```bash
agentrouter
agentrouter serve --port 8787 --open
agentrouter gui serve --host 127.0.0.1 --port 8787 --no-open
```

`agentrouter serve` is a shortcut for `agentrouter gui serve`.

Open `http://127.0.0.1:8787` for chat, agent timeline, sessions, and config views.

Layout (instrument-grade shell):

- Rail (`aside#rail`): session list with search/filter, rename (inline), delete (with confirm), preview, load-to-chat, New chat, theme + settings entry.
- Stage (`main#stage`): conversation (`role="log"`), chat/agent mode switch, empty states, suggestion chips, docked composer.
- Inspector (`aside#inspector`): per-run detail — agent step/tool cards, reasoning lane, token usage, elapsed time.
- Transport (`#transport`): run controls — stop/rerun/resume, step count, elapsed odometer, progress meter.
- Command palette (`Ctrl+K`): fuzzy actions (new chat, go to mode, shortcuts list, theme cycle).
- Toasts (`#toasts`, `aria-live="polite"`): one polite announcer, swipe-to-dismiss, slow-end progress trip.

Chat: streaming markdown with code Copy buttons, Enter to send / Shift+Enter newline.
Agent: step and tool cards streaming from `/api/agent`, with stop/rerun/resume via transport.
Sessions: search, preview, rename, delete, load prior sessions from the rail.
Config: set API key and default model, Test connection via `/api/models`.
Settings panel: theme (`dark` / `light` / `os`), density (`comfortable` / `compact`), font scale (85-130%), motion (see below).

Motion settings (`ar-motion` in `localStorage`, Settings panel):

- `full`: 120/200/320ms transform/opacity-only transitions, spring easing (guarded `linear()` curve with cubic-bezier fallback).
- `reduced`: shell chrome limited to opacity-only 100ms; reveals, crossfades, and odometers apply instantly.
- `off`: all transitions and animations none.
- Defaults follow `prefers-reduced-motion` when nothing is stored. Meter canvas and LED/caret animations pause when the tab is hidden.

Perf HUD: append `?perf=1` to the URL (or press `Ctrl+Shift+P`) to toggle a fixed overlay showing `fps | frame ms | long tasks | dom nodes | stream lag ms`.

Endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/` | HTML frontend (`text/html`, title `AgentRouter`) |
| GET | `/static/*` | Packaged static files (allowlisted suffixes, MIME, ETag + `If-None-Match` 304, traversal blocked, `Cache-Control: no-cache`) |
| GET | `/api/health` | Health check (`{"status":"ok"}`) |
| GET | `/api/version` | CLI version (`{"version": "0.3.0"}`) |
| GET | `/api/models` | List models via `AgentRouterClient` |
| POST | `/api/chat` | Chat relay, SSE `data:` lines + `data: [DONE]` (relays `content`, `reasoning`, `usage`) |
| POST | `/api/agent` | Agent relay, SSE step/tool/done events |
| GET | `/api/sessions` | List session ids |
| GET | `/api/sessions/{id}` | Load one session |
| PATCH | `/api/sessions/{id}` | Rename session (`{"title": "..."}`) |
| DELETE | `/api/sessions/{id}` | Delete session |
| GET | `/api/config` | Masked config (`base_url`, `has_key`, `default_model`) |
| POST | `/api/config` | Update `api_key` / `default_model` / `base_url` |

Optional token auth: set `AGENTROUTER_GUI_TOKEN` (or pass a token to `create_server`). When set, every `/api/*` request must carry `X-AgentRouter-Token`; otherwise all API routes stay open.

Keyboard shortcuts:

| Keys | Action |
|---|---|
| `Enter` / `Shift+Enter` | Send / newline in composer |
| `Ctrl+K` (or `Cmd+K`) | Open command palette |
| `/` | Focus composer input |
| `?` | Show shortcuts |
| `Ctrl+Shift+P` | Toggle perf HUD |
| `Esc` | Close palette / picker / dialog |
| `Up` / `Down`, `Enter` | Navigate / confirm in palette and model picker (`Home` / `End` jump in picker) |

Offline behavior: the shell (HTML/CSS/JS) is served locally, so the UI itself loads with no network. API calls fail soft: model list falls back to empty, chat/agent streams surface an error toast and keep the draft, session preview/rename/delete show a failure toast, Test connection reports unreachable, and the 24h update checker never blocks on network failure. Drafts persist across mode switches.

SSE example:

```bash
curl -N -H 'Content-Type: application/json' \
  -d '{"model":"<model-id>","messages":[{"role":"user","content":"hi"}]}' \
  http://127.0.0.1:8787/api/chat
```

Version check:

```bash
curl http://127.0.0.1:8787/api/version
agentrouter --version
```

AgentRouter-only applies here too: any `base_url` other than `https://agentrouter.org/v1` returns `400`.

## Update checker

Offline-safe. Checks PyPI metadata once per 24h (cached in `~/.cache/agentrouter/last-check`), never blocks on network failure.

```bash
agentrouter update check
agentrouter update apply
```

If you installed via curl, re-run the installer to upgrade:

```bash
curl -fsSL https://raw.githubusercontent.com/besimziu6-ux/agentrouter-cli/main/install.sh | bash
```

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `AGENTROUTER_API_KEY` | API key (overrides config file) | — |
| `AGENTROUTER_BASE_URL` | Must be `https://agentrouter.org/v1` if set | `https://agentrouter.org/v1` |
| `AGENTROUTER_DEFAULT_MODEL` | Default model id (overrides config file) | — |

Config file keys mirror the same three: `api_key`, `base_url`, `default_model` in `~/.config/agentrouter/config.json` (chmod 600).

## Development

```bash
pip install -e ".[dev]"
pytest -q
python -m py_compile src/agentrouter/*.py
```

Publish a release (maintainers):

```bash
bash scripts/publish.sh --dry-run   # build + twine check only
bash scripts/publish.sh             # build + check + upload + git tag
```

## License

MIT — see [LICENSE](LICENSE).
