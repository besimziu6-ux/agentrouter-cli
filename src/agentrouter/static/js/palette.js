export function norm(s) {
  return String(s == null ? "" : s).trim().toLowerCase();
}

export function filterPalette(actions, query) {
  const q = norm(query);
  if (!q) return (actions || []).slice();
  const words = q.split(/\s+/).filter(Boolean);
  const scored = [];
  const list = actions || [];
  for (let i = 0; i < list.length; i++) {
    const a = list[i];
    const hay = norm((a.title || "") + " " + (a.hint || "") + " " + (a.keys || ""));
    let ok = true;
    let score = 0;
    for (const w of words) {
      const at = hay.indexOf(w);
      if (at < 0) { ok = false; break; }
      score += at === 0 ? -20 : at;
      if (norm(a.title).startsWith(w)) score -= 10;
    }
    if (ok) scored.push({ i, score, len: hay.length });
  }
  scored.sort((a, b) => (a.score - b.score) || (a.len - b.len) || (a.i - b.i));
  return scored.map((s) => list[s.i]);
}

export function buildActions(ctx) {
  const c = ctx || {};
  const hasFn = (k) => typeof c[k] === "function";
  const act = (id, title, hint, run, keys) => ({ id, title, hint: hint || "", run, keys: keys || "" });
  return [
    act("new-chat", "New chat", "Start a blank conversation", () => { if (hasFn("onNewChat")) c.onNewChat(); }, ""),
    act("switch-mode", "Switch Chat/Agent mode", "Toggle the transport mode", () => { if (hasFn("onSwitchMode")) c.onSwitchMode(); }, ""),
    act("switch-model", "Switch model", "Open the model picker", () => { if (hasFn("onSwitchModel")) c.onSwitchModel(); }, ""),
    act("open-session", "Open session", "Jump to a session in the rail", () => { if (hasFn("onOpenSession")) c.onOpenSession(); }, ""),
    act("toggle-theme", "Toggle theme", "Cycle OS, dark, light", () => { if (hasFn("onToggleTheme")) c.onToggleTheme(); }, ""),
    act("toggle-inspector", "Toggle inspector", "Show or hide the right panel", () => { if (hasFn("onToggleInspector")) c.onToggleInspector(); }, ""),
    act("focus-input", "Focus input", "Jump to the composer", () => { if (hasFn("onFocusInput")) c.onFocusInput(); }, "/"),
    act("shortcuts", "Keyboard shortcuts", "Show all shortcuts", () => { if (hasFn("onShortcuts")) c.onShortcuts(); }, "?"),
  ];
}

function measureTops(host) {
  const m = new Map();
  try {
    const rows = host.querySelectorAll(":scope > .pal-row");
    rows.forEach((r) => {
      try { m.set(r.dataset.pid, r.getBoundingClientRect().top); } catch { /* ignore */ }
    });
  } catch { /* ignore */ }
  return m;
}

function flipRows(host, before) {
  try {
    if (typeof document !== "undefined" && document.documentElement.getAttribute("data-motion") !== "full") return;
    const rows = host.querySelectorAll(":scope > .pal-row");
    rows.forEach((r) => {
      const a = before.get(r.dataset.pid);
      if (a == null) return;
      const b = r.getBoundingClientRect().top;
      const d = a - b;
      if (!d) return;
      r.style.transform = "translateY(" + d + "px)";
      requestAnimationFrame(() => requestAnimationFrame(() => {
        try {
          r.style.transition = "transform 180ms cubic-bezier(.2,.8,.2,1)";
          r.style.transform = "";
          setTimeout(() => { try { r.style.transition = ""; } catch { /* ignore */ } }, 200);
        } catch { /* ignore */ }
      }));
    });
  } catch { /* ignore */ }
}

let pal = null;

export function isPaletteOpen() {
  return !!pal;
}

export function closePalette() {
  if (!pal) return;
  const p = pal;
  pal = null;
  try {
    if (p.node && p.node.parentNode) p.node.parentNode.removeChild(p.node);
    if (p.prev && typeof p.prev.focus === "function") {
      try { p.prev.focus({ preventScroll: true }); } catch { try { p.prev.focus(); } catch { /* ignore */ } }
    }
    if (p.onClose) p.onClose();
  } catch { /* ignore */ }
  try { document.removeEventListener("keydown", p.key, true); } catch { /* ignore */ }
}

export function openPalette(opts) {
  if (typeof document === "undefined") return null;
  opts = opts || {};
  closePalette();
  let prev = null;
  try { prev = document.activeElement; } catch { /* ignore */ }
  const actions = Array.isArray(opts.actions) ? opts.actions : buildActions(opts);
  let view = actions.slice();
  let active = view.length ? 0 : -1;
  let node;
  let list;
  let input;
  try {
    node = document.createElement("div");
    node.className = "pal-wrap";
    node.innerHTML = "";
    const box = document.createElement("div");
    box.className = "pal";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Command palette");
    input = document.createElement("input");
    input.className = "pal-input";
    input.type = "search";
    input.placeholder = "Type a command...";
    input.setAttribute("aria-label", "Command search");
    list = document.createElement("div");
    list.className = "pal-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Commands");
    box.appendChild(input);
    box.appendChild(list);
    node.appendChild(box);
    document.body.appendChild(node);
    const paint = () => {
      const before = measureTops(list);
      while (list.firstChild) list.removeChild(list.firstChild);
      view.forEach((a, idx) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pal-row" + (idx === active ? " on" : "");
        b.dataset.pid = a.id;
        b.setAttribute("role", "option");
        b.setAttribute("aria-selected", idx === active ? "true" : "false");
        const t = document.createElement("span");
        t.className = "pal-t";
        t.textContent = a.title;
        const h = document.createElement("span");
        h.className = "pal-h";
        h.textContent = a.hint || "";
        b.appendChild(t);
        b.appendChild(h);
        b.addEventListener("click", () => {
          closePalette();
          try { if (typeof a.run === "function") a.run(); } catch { /* ignore */ }
        });
        b.addEventListener("pointermove", () => {
          if (active !== idx) { active = idx; paint(); }
        });
        list.appendChild(b);
      });
      flipRows(list, before);
    };
    const key = (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closePalette(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); active = view.length ? (active + 1) % view.length : -1; paint(); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); active = view.length ? (active - 1 + view.length) % view.length : -1; paint(); return; }
      if (e.key === "Enter") {
        e.preventDefault();
        const a = view[active] || view[0];
        closePalette();
        try { if (a && typeof a.run === "function") a.run(); } catch { /* ignore */ }
      }
    };
    input.addEventListener("input", () => {
      view = filterPalette(actions, input.value);
      active = view.length ? 0 : -1;
      paint();
    });
    node.addEventListener("pointerdown", (e) => {
      if (e.target === node) closePalette();
    });
    document.addEventListener("keydown", key, true);
    pal = { node, prev, key, onClose: opts.onClose || null };
    paint();
    try { input.focus(); } catch { /* ignore */ }
    return { close: closePalette };
  } catch {
    try { if (node && node.parentNode) node.parentNode.removeChild(node); } catch { /* ignore */ }
    return null;
  }
}

export function paletteShortcutText() {
  try {
    if (typeof navigator !== "undefined" && /mac/i.test(navigator.platform || "")) return "Cmd+K";
  } catch { /* ignore */ }
  return "Ctrl+K";
}

export function initPalette(opts) {
  if (typeof document === "undefined") return () => {};
  opts = opts || {};
  const getActions = typeof opts.getActions === "function" ? opts.getActions : () => buildActions(opts);
  const wantsPalette = (e) => (e.ctrlKey || e.metaKey) && String(e.key || "").toLowerCase() === "k";
  const onDoc = (e) => {
    try {
      if (wantsPalette(e)) {
        e.preventDefault();
        if (isPaletteOpen()) closePalette();
        else openPalette({ actions: getActions() });
        return;
      }
      const tag = (e.target && e.target.tagName ? e.target.tagName : "").toLowerCase();
      const typing = tag === "input" || tag === "textarea" || (e.target && e.target.isContentEditable);
      if (typing) return;
      if (e.key === "/") {
        e.preventDefault();
        if (typeof opts.onFocusInput === "function") opts.onFocusInput();
        else {
          const c = document.getElementById("composer");
          if (c && typeof c.focus === "function") c.focus();
        }
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        if (typeof opts.onShortcuts === "function") opts.onShortcuts();
        else openPalette({ actions: getActions() });
      }
    } catch { /* ignore */ }
  };
  document.addEventListener("keydown", onDoc);
  return () => {
    try { document.removeEventListener("keydown", onDoc); } catch { /* ignore */ }
  };
}
