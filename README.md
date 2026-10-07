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

```bash
agentrouter gui serve --port 8787 --open
agentrouter gui serve --host 127.0.0.1 --port 8787 --no-open
```

Open `http://127.0.0.1:8787` for chat, agent timeline, sessions, and config views.

Endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/` | HTML frontend (`text/html`, title `AgentRouter`) |
| GET | `/api/models` | List models via `AgentRouterClient` |
| POST | `/api/chat` | Chat relay, SSE `data:` lines + `data: [DONE]` |
| POST | `/api/agent` | Agent relay, SSE step/tool/done events |
| GET | `/api/sessions` | List session ids |
| GET | `/api/sessions/{id}` | Load one session |
| GET | `/api/config` | Masked config (`base_url`, `has_key`, `default_model`) |
| POST | `/api/config` | Update `api_key` / `default_model` / `base_url` |

SSE example:

```bash
curl -N -H 'Content-Type: application/json' \
  -d '{"model":"<model-id>","messages":[{"role":"user","content":"hi"}]}' \
  http://127.0.0.1:8787/api/chat
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
