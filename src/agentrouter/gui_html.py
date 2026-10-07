"""Thin loader for the packaged GUI frontend (no npm, no build, no CDN)."""

from __future__ import annotations

_FALLBACK: str = """<!doctype html>
<html lang="en" data-theme="dark" data-motion="full">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AgentRouter</title></head>
<body>
<div id="app"><div id="bar"><span id="statusDot" class="dot"></span><button id="newChat">+ New chat</button></div>
<div id="wrap"><div id="conv"></div><div id="empty"></div>
<div id="dock"><div id="composerRow"><textarea id="composer"></textarea></div><p class="hint">Enter sends.</p></div></div></div>
<div id="toasts" class="toast"></div>
<template><div class="toolCard"><span>Step </span><span>Tool </span><button data-copy="">Copy</button></div></template>
<script>try{var t=localStorage.getItem("ar-theme")||"dark";document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>
</body></html>"""

GUI_HTML: str = _FALLBACK

try:
    try:
        from importlib.resources import files as _files

        _p = _files("agentrouter").joinpath("static/index.html")
        try:
            if _p.is_file():
                GUI_HTML = _p.read_text(encoding="utf-8")
        except (OSError, ValueError):
            pass
    except (ImportError, TypeError, ValueError):
        try:
            import importlib.resources as _res

            try:
                GUI_HTML = _res.read_text("agentrouter.static", "index.html", encoding="utf-8")  # type: ignore[attr-defined]
            except (FileNotFoundError, ModuleNotFoundError, OSError):
                pass
        except (ImportError, ModuleNotFoundError):
            pass
except Exception:
    pass
