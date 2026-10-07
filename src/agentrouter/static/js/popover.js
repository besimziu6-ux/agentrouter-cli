import { motionOK } from "./motion.js";

export function filterList(items, query, getText) {
  const q = String(query == null ? "" : query).trim().toLowerCase();
  if (!q) return items.slice();
  const pick = typeof getText === "function" ? getText : (it) => String(it == null ? "" : (it.label != null ? it.label : it));
  const scored = [];
  for (let i = 0; i < items.length; i++) {
    const t = pick(items[i]).toLowerCase();
    const at = t.indexOf(q);
    if (at < 0) continue;
    const starts = at === 0 ? 0 : 1;
    scored.push({ i, starts, at, len: t.length });
  }
  scored.sort((a, b) => (a.starts - b.starts) || (a.at - b.at) || (a.len - b.len) || (a.i - b.i));
  return scored.map((s) => items[s.i]);
}

export function nextIndex(cur, dir, len) {
  if (!len || len <= 0) return -1;
  if (cur < 0 || cur == null) return dir < 0 ? len - 1 : 0;
  const n = (cur + dir) % len;
  return n < 0 ? n + len : n;
}

let open = null;

function closeCurrent() {
  if (!open) return;
  const o = open;
  open = null;
  try {
    if (o.anchor) o.anchor.setAttribute("aria-expanded", "false");
    if (o.node && o.node.parentNode) o.node.parentNode.removeChild(o.node);
    if (o.anchor && o.returnFocus && typeof o.anchor.focus === "function") {
      try { o.anchor.focus({ preventScroll: true }); } catch { try { o.anchor.focus(); } catch{} }
    }
    if (o.onClose) o.onClose();
  } catch{}
  try {
    if (typeof document !== "undefined") document.removeEventListener("pointerdown", onDocDown, true);
  } catch{}
}

function onDocDown(e) {
  if (!open) return;
  try {
    if (open.node && open.node.contains(e.target)) return;
    if (open.anchor && open.anchor.contains(e.target)) return;
  } catch{}
  closeCurrent();
}

function onKey(e, state) {
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    closeCurrent();
    return;
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Home" || e.key === "End") {
    e.preventDefault();
    const dir = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
    if (e.key === "Home") state.active = 0;
    else if (e.key === "End") state.active = state.view.length - 1;
    else state.active = nextIndex(state.active, dir, state.view.length);
    state.render();
    return;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    const it = state.view[state.active] || state.view[0];
    if (it && state.onPick) state.onPick(it);
    closeCurrent();
  }
}

export function closePopover() {
  closeCurrent();
}

export function isPopoverOpen() {
  return !!open;
}

export function openPopover(anchor, opts) {
  if (typeof document === "undefined") return null;
  opts = opts || {};
  closeCurrent();
  const items = Array.isArray(opts.items) ? opts.items : [];
  const getText = typeof opts.getText === "function" ? opts.getText : (it) => String(it && it.label != null ? it.label : it);
  const getValue = typeof opts.getValue === "function" ? opts.getValue : (it) => (it && it.value != null ? it.value : getText(it));
  const state = {
    view: items.slice(),
    active: items.length ? 0 : -1,
    render: null,
    onPick: typeof opts.onPick === "function" ? opts.onPick : null,
  };
  let node;
  try {
    node = document.createElement("div");
    node.className = "pop" + (motionOK() ? " anim" : "");
    node.setAttribute("role", "listbox");
    if (opts.label) node.setAttribute("aria-label", opts.label);
    const box = document.createElement("input");
    box.className = "pop-search";
    box.type = "search";
    box.placeholder = opts.placeholder || "Filter...";
    box.setAttribute("aria-label", opts.placeholder || "Filter items");
    const list = document.createElement("div");
    list.className = "pop-list";
    const hi = document.createElement("div");
    hi.className = "pop-hi";
    hi.setAttribute("aria-hidden", "true");
    list.appendChild(hi);
    const rows = [];
    const paint = () => {
      while (list.querySelector(":scope > .pop-row")) {
        const r = list.querySelector(":scope > .pop-row");
        r.parentNode.removeChild(r);
      }
      rows.length = 0;
      state.view.forEach((it, idx) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pop-row" + (idx === state.active ? " on" : "");
        b.setAttribute("role", "option");
        b.setAttribute("aria-selected", idx === state.active ? "true" : "false");
        b.textContent = getText(it);
        b.addEventListener("click", () => {
          if (state.onPick) state.onPick(it);
          closeCurrent();
        });
        b.addEventListener("pointermove", () => {
          if (state.active !== idx) { state.active = idx; paint(); }
        });
        list.appendChild(b);
        rows.push(b);
      });
      const on = rows[state.active];
      if (on) {
        const top = on.offsetTop || 0;
        hi.style.transform = "translateY(" + top + "px)";
        hi.style.height = (on.offsetHeight || 32) + "px";
        hi.style.opacity = "1";
        try { on.scrollIntoView({ block: "nearest" }); } catch{}
      } else {
        hi.style.opacity = "0";
      }
    };
    state.render = paint;
    box.addEventListener("input", () => {
      state.view = filterList(items, box.value, getText);
      state.active = state.view.length ? 0 : -1;
      paint();
    });
    node.addEventListener("keydown", (e) => onKey(e, state));
    box.addEventListener("keydown", (e) => onKey(e, state));
    node.appendChild(box);
    node.appendChild(list);
    const host = opts.host || document.body;
    host.appendChild(node);
    try {
      const r = anchor.getBoundingClientRect();
      const w = Math.max(200, Math.min(320, r.width + 80));
      node.style.minWidth = w + "px";
      const x = Math.max(8, Math.min(r.left, (window.innerWidth || 800) - w - 8));
      const y = r.bottom + 6;
      node.style.left = x + "px";
      node.style.top = y + "px";
    } catch{}
    try { anchor.setAttribute("aria-expanded", "true"); } catch{}
    paint();
    try { box.focus(); } catch{}
    open = { node, anchor, onClose: opts.onClose || null, returnFocus: true };
    try { document.addEventListener("pointerdown", onDocDown, true); } catch{}
    return { close: closeCurrent, get value() { return state.view[state.active]; } };
  } catch {
    try { if (node && node.parentNode) node.parentNode.removeChild(node); } catch{}
    return null;
  }
}
