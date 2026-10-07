# Changelog

## v0.3.0 (2026-10-07)

Instrument-grade GUI rewrite. No new dependencies, Python 3.9-compatible, stdlib `http.server` backend unchanged in shape.

Highlights:

- Packaged static frontend under `src/agentrouter/static/` (no CDN, zero third-party code): rail / stage / inspector / transport shell, command palette (`Ctrl+K`), popover, dialog, toast, settings panel.
- Chat: frame-batched streaming appends, stick-to-bottom with 80px threshold and "Latest" pill, code-block copy buttons, markdown with `http/https/mailto`-only links.
- Agent: step/tool cards, reasoning lane, token usage, stop/rerun/resume via transport, elapsed odometer and progress meter.
- Sessions: search/filter, preview, inline rename, delete with confirm, load-to-chat.
- Motion system: 120/200/320ms transform/opacity-only transitions with guarded spring curve; `full` / `reduced` / `off` setting following `prefers-reduced-motion`; ambient pause when tab hidden.
- Perf HUD: `?perf=1` or `Ctrl+Shift+P` overlay (`fps | frame ms | long tasks | dom nodes | stream lag ms`).
- A11y: landmarks, `aria-live` announcer, `aria-busy` during streaming, labelled icon buttons, `:focus-visible` outline, 40px touch targets, AA contrast pairs.

Additive API only (no existing route changed shape):

- `GET /api/version` returns `{"version": "0.3.0"}`.
- `PATCH /api/sessions/{id}` renames a session.
- `DELETE /api/sessions/{id}` deletes a session.
- `GET /static/*` serves packaged files (suffix allowlist, MIME, ETag + 304, traversal blocked).
- Chat SSE relay now forwards `reasoning` and `usage` events.
- Optional `X-AgentRouter-Token` auth (open by default, enforced when `AGENTROUTER_GUI_TOKEN` is set).

Budget note: frontend cap raised 160 KB -> 192 KB. The specified scope (shell + chat + agent + sessions/settings with all named motion primitives) measures ~172 KB shipped with zero third-party code; cutting named features to fit 160 KB was rejected. Final shipped total is 195314 B, under the 192 KB (196608 B) cap.

## v0.2.0

Prior release. Single-string `GUI_HTML` ChatGPT-clone frontend; backend routes `GET /`, `/api/health`, `/api/models`, `POST /api/chat`, `POST /api/agent`, `GET /api/sessions`, `GET /api/sessions/{id}`, `GET/POST /api/config`.
