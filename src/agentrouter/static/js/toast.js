import { motionOK } from "./motion.js";

export function pruneToasts(list, max) {
  const m = typeof max === "number" && max > 0 ? Math.floor(max) : 3;
  if (!Array.isArray(list)) return [];
  if (list.length <= m) return list.slice();
  return list.slice(list.length - m);
}

export function createToastQueue(max) {
  const m = typeof max === "number" && max > 0 ? Math.floor(max) : 3;
  let items = [];
  let seq = 0;
  return {
    get max() { return m; },
    get size() { return items.length; },
    push(text, kind) {
      seq += 1;
      items.push({ id: seq, text: String(text == null ? "" : text), kind: kind || "info" });
      items = pruneToasts(items, m);
      return seq;
    },
    remove(id) {
      items = items.filter((t) => t.id !== id);
    },
    clear() {
      items = [];
    },
    list() {
      return items.slice();
    },
  };
}

let root = null;
let queue = null;
const timers = new Map();

function ensureRoot() {
  if (root) return root;
  try {
    root = document.getElementById("toasts");
    if (!root) {
      root = document.createElement("div");
      root.id = "toasts";
      root.setAttribute("aria-live", "polite");
      document.body.appendChild(root);
    }
    return root;
  } catch {
    return null;
  }
}

function renderToast(host, item, dur) {
  const el = document.createElement("div");
  el.className = "toast toast-in" + (item.kind === "err" || item.kind === "error" ? " err" : "");
  el.setAttribute("role", "status");
  el.dataset.toastId = String(item.id);
  const msg = document.createElement("div");
  msg.className = "toast-msg";
  msg.textContent = item.text;
  const bar = document.createElement("div");
  bar.className = "toast-bar";
  const fill = document.createElement("div");
  fill.className = "toast-fill";
  bar.appendChild(fill);
  el.appendChild(msg);
  el.appendChild(bar);
  let remaining = dur;
  let started = 0;
  let raf = 0;
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    try { cancelAnimationFrame(raf); } catch{}
    timers.delete(item.id);
    try {
      el.classList.add("toast-out");
      setTimeout(() => {
        try { if (el.parentNode) el.parentNode.removeChild(el); } catch{}
      }, motionOK() ? 180 : 0);
    } catch{}
    try { if (queue) queue.remove(item.id); } catch{}
  };
  const RF = typeof requestAnimationFrame !== "undefined" ? requestAnimationFrame : (f) => setTimeout(() => f(performance.now()), 16);
  const loop = (t) => {
    if (done) return;
    if (!started) started = t;
    const spent = t - started;
    const left = Math.max(0, remaining - spent);
    try { fill.style.transform = "scaleX(" + (left / dur) + ")"; } catch{}
    if (left <= 0) { finish(); return; }
    raf = RF(loop);
  };
  const pause = () => {
    if (done) return;
    try { cancelAnimationFrame(raf); } catch{}
    try {
      const now = performance.now();
      remaining = Math.max(0, remaining - (now - started));
    } catch { /* keep */ }
    started = 0;
  };
  const resume = () => {
    if (done || started) return;
    if (typeof document !== "undefined" && document.hidden) return;
    raf = RF(loop);
  };
  el.addEventListener("pointerenter", pause);
  el.addEventListener("pointerleave", resume);
  el.addEventListener("focusin", pause);
  el.addEventListener("focusout", resume);
  let sx = 0;
  let dx = 0;
  el.addEventListener("pointerdown", (e) => {
    sx = e.clientX || 0;
    dx = 0;
    try { el.setPointerCapture(e.pointerId); } catch{}
  });
  el.addEventListener("pointermove", (e) => {
    if (!sx) return;
    dx = (e.clientX || 0) - sx;
    try { el.style.transform = "translateX(" + dx + "px)"; el.style.opacity = String(Math.max(0.2, 1 - Math.abs(dx) / 160)); } catch{}
  });
  const release = () => {
    if (Math.abs(dx) > 70) { finish(); return; }
    try { el.style.transform = ""; el.style.opacity = ""; } catch{}
    sx = 0;
    dx = 0;
  };
  el.addEventListener("pointerup", release);
  el.addEventListener("pointercancel", release);
  timers.set(item.id, { finish });
  raf = RF(loop);
  setTimeout(() => { try { el.classList.remove("toast-in"); } catch{} }, 30);
  return el;
}

export function showToast(text, opts) {
  if (typeof document === "undefined") return -1;
  opts = opts || {};
  try {
    const host = ensureRoot();
    if (!host) return -1;
    if (!queue) queue = createToastQueue(3);
    const kind = opts.kind || opts.type || "info";
    const id = queue.push(text, kind);
    const item = queue.list().find((t) => t.id === id);
    if (!item) return id;
    while (host.children.length >= 3) {
      try { host.removeChild(host.firstChild); } catch { break; }
    }
    const dur = typeof opts.duration === "number" ? opts.duration : 4200;
    host.appendChild(renderToast(host, item, dur));
    return id;
  } catch {
    return -1;
  }
}

export function initToasts() {
  if (typeof document === "undefined") return;
  try { ensureRoot(); } catch{}
  if (!queue) queue = createToastQueue(3);
}

export function toastInfo(t) { return showToast(t, { kind: "info" }); }
export function toastError(t) { return showToast(t, { kind: "err" }); }
