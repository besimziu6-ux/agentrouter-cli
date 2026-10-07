import { filterSessions } from "./rail.js";
import { motionOK, crossfade, flip } from "./motion.js";
import { showToast } from "./toast.js";
import { openDialog, closeDialog } from "./dialog.js";
import { apiFetch } from "./api.js";

export function h(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

export function isSafeId(id) {
  return typeof id === "string" && id.length > 0 && id.length <= 64 && /^[A-Za-z0-9_-]+$/.test(id);
}

export function validateTitle(t) {
  if (typeof t !== "string" || !t.trim()) return { ok: false, error: "Title must not be empty." };
  const s = t.trim();
  if (s.length > 120) return { ok: false, error: "Title max 120 chars." };
  return { ok: true, title: s };
}

export function previewText(msgs) {
  if (!Array.isArray(msgs)) return "";
  let fallback = "";
  for (const m of msgs) {
    if (!m || typeof m.content !== "string" || !m.content.trim()) continue;
    const t = m.content.trim().slice(0, 140);
    if (m.role === "user") return t;
    if (!fallback) fallback = t;
  }
  return fallback;
}

export function debounce(fn, ms) {
  let t = 0;
  const w = typeof ms === "number" && ms >= 0 ? ms : 80;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), w); };
}

export function swipeDismissed(dx, w) {
  const x = typeof dx === "number" ? dx : 0;
  if (x < -60) return true;
  const ww = typeof w === "number" && w > 0 ? w : 260;
  return x / ww < -0.3;
}

async function sesJson(path, opt) {
  const r = await apiFetch(path, opt);
  return r.json();
}

export function listSessions() {
  return sesJson("/api/sessions").then((j) => (Array.isArray(j && j.sessions) ? j.sessions : []));
}

export function getSession(id) {
  return sesJson("/api/sessions/" + encodeURIComponent(id));
}

export function renameSession(id, title) {
  return sesJson("/api/sessions/" + encodeURIComponent(id), { method: "PATCH", body: { title } });
}

export function deleteSession(id) {
  return sesJson("/api/sessions/" + encodeURIComponent(id), { method: "DELETE" });
}

export function initSessions(opts) {
  const noop = { refresh: () => {}, open: () => {} };
  if (typeof document === "undefined") return noop;
  opts = opts || {};
  const store = opts.store || null;
  const set = (p) => { try { store && store.set && store.set(p); } catch { /* ignore */ } };
  const cur = () => {
    try { return (store && store.get && store.get("sessionId")) || ""; } catch { return ""; }
  };
  const listEl = document.getElementById("sesList");
  const searchEl = document.getElementById("sesSearch");
  const conv = document.getElementById("conv");
  if (!listEl) return noop;
  let sessions = [];
  let state = "loading";
  const idOf = (s) => String((s && s.id) || "");
  const labelOf = (s) => String((s && (s.title || s.label)) || (s && s.id) || "session");
  const fail = (verb, e) => showToast(verb + " failed. " + String((e && e.message) || ""), { kind: "err" });
  const btn = (label, cls, fn) => {
    const b = h("button", cls, label);
    b.type = "button";
    b.addEventListener("click", fn);
    return b;
  };
  const snapshot = () => {
    const m = new Map();
    try {
      for (const li of listEl.children) {
        const k = li.getAttribute && li.getAttribute("data-sid");
        if (k) m.set(k, li.offsetTop || 0);
      }
    } catch { /* ignore */ }
    return m;
  };
  const playFlip = (first, last) => {
    try {
      for (const li of listEl.children) {
        const k = li.getAttribute && li.getAttribute("data-sid");
        if (!k || !first.has(k) || !last.has(k)) continue;
        const dy = (first.get(k) || 0) - (last.get(k) || 0);
        if (!dy) continue;
        li.style.transition = "none";
        li.style.transform = "translateY(" + dy + "px)";
        void li.offsetHeight;
        li.style.transition = "transform 160ms ease-out";
        li.style.transform = "";
        setTimeout(() => { try { li.style.transition = ""; } catch { /* ignore */ } }, 180);
      }
    } catch { /* ignore */ }
  };
  const afterDel = (id) => {
    sessions = sessions.filter((s) => idOf(s) !== id);
    try { if (cur() === id) set({ sessionId: "" }); } catch { /* ignore */ }
    set({ sessions: sessions.slice() });
    paint(true);
    showToast("Session deleted");
  };
  const doDelete = async (id, li) => {
    try { await deleteSession(id); } catch (e) { fail("Delete", e); return; }
    if (li && motionOK()) {
      try {
        li.style.transition = "transform 160ms ease-in, opacity 160ms";
        li.style.transform = "translateX(-40px)";
        li.style.opacity = "0";
        setTimeout(() => afterDel(id), 170);
        return;
      } catch { /* fall through */ }
    }
    afterDel(id);
  };
  const commitRename = async (id, value) => {
    const chk = validateTitle(value);
    if (!chk.ok) { showToast(chk.error, { kind: "err" }); paint(false); return; }
    try {
      const j = await renameSession(id, chk.title);
      const t = String((j && j.title) || chk.title);
      sessions = sessions.map((x) => (idOf(x) === id ? { ...x, title: t } : x));
      set({ sessions: sessions.slice() });
      paint(true);
      showToast("Renamed");
    } catch (e) { fail("Rename", e); paint(false); }
  };
  const startRename = (s, anchor) => {
    const id = idOf(s);
    const li = anchor && anchor.closest ? anchor.closest("li") : null;
    if (!li) return;
    li.textContent = "";
    const input = h("input", "ses-rename");
    input.type = "text";
    input.value = labelOf(s);
    input.maxLength = 120;
    input.setAttribute("aria-label", "Rename session");
    li.appendChild(input);
    input.focus();
    let done = false;
    const fin = (save) => {
      if (done) return;
      done = true;
      if (save) commitRename(id, input.value);
      else paint(false);
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") fin(true);
      else if (e.key === "Escape") fin(false);
    });
    input.addEventListener("blur", () => fin(true));
  };
  const copyTranscript = async (id, title, msgs) => {
    const lines = msgs.map((m) => String((m && m.role) || "?") + ": " + String(m && m.content != null ? m.content : ""));
    try {
      await navigator.clipboard.writeText("# " + (title || id) + "\n\n" + lines.join("\n\n"));
      showToast("Transcript copied");
    } catch { showToast("Copy failed", { kind: "err" }); }
  };
  const loadToChat = (id, title, msgs) => {
    const apply = () => {
      try {
        if (typeof opts.onLoad === "function") opts.onLoad(msgs, id);
        else set({ sessionId: id });
      } catch { /* ignore */ }
      showToast("Loaded " + (title || id));
    };
    try {
      if (conv && motionOK()) { crossfade(conv, conv); setTimeout(apply, 120); return; }
    } catch { /* ignore */ }
    apply();
  };
  const openPreview = async (id) => {
    let data;
    try { data = await getSession(id); } catch (e) { fail("Preview", e); return; }
    const msgs = data && Array.isArray(data.messages) ? data.messages : [];
    const title = String((data && data.title) || "");
    const box = h("section", "ses-preview");
    box.setAttribute("aria-label", "Session preview");
    const row = h("div", "ses-preview-row");
    box.append(h("h3", null, (title || id).slice(0, 120)), h("p", "mut", previewText(msgs) || "(" + msgs.length + " messages)"), row);
    row.append(
      btn("Load to chat", "pri", () => { closeDialog(); loadToChat(id, title, msgs); }),
      btn("Copy transcript", null, () => copyTranscript(id, title, msgs)),
      btn("Close", null, () => closeDialog())
    );
    (document.getElementById("center") || document.body).appendChild(box);
    if (!openDialog(box, { onClose: () => { try { box.remove(); } catch { /* ignore */ } } })) {
      try { box.remove(); } catch { /* ignore */ }
    }
  };
  const buildRow = (s) => {
    const id = idOf(s);
    const li = h("li");
    li.setAttribute("data-sid", id);
    const wrap = h("div", "ses-wrap");
    const b = btn(labelOf(s), "ses-row" + (id && id === cur() ? " on" : ""), () => {
      set({ sessionId: id });
      try {
        for (const el of listEl.querySelectorAll(".ses-row.on")) el.classList.remove("on");
        b.classList.add("on");
      } catch { /* ignore */ }
      openPreview(id);
    });
    const ren = btn("Rename", "ses-act ses-ren", (e) => { e.stopPropagation(); startRename(s, b); });
    ren.setAttribute("aria-label", "Rename " + id);
    const del = btn("Del", "ses-act ses-del", (e) => { e.stopPropagation(); doDelete(id, li); });
    del.setAttribute("aria-label", "Delete " + id);
    wrap.append(b, ren, del);
    li.appendChild(wrap);
    let sx = null;
    let dx = 0;
    li.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
      sx = e.clientX;
      dx = 0;
    });
    li.addEventListener("pointermove", (e) => {
      if (sx == null) return;
      dx = Math.min(0, (e.clientX || 0) - sx);
      try { wrap.style.transform = "translateX(" + Math.round(dx) + "px)"; } catch { /* ignore */ }
    });
    const release = () => {
      if (sx == null) return;
      sx = null;
      const w = li.offsetWidth || 260;
      if (swipeDismissed(dx, w)) {
        try {
          if (motionOK()) {
            wrap.style.transition = "transform 140ms ease-in";
            wrap.style.transform = "translateX(" + -w + "px)";
            setTimeout(() => doDelete(id, li), 150);
            return;
          }
        } catch { /* fall through */ }
        doDelete(id, li);
        return;
      }
      dx = 0;
      try {
        wrap.style.transition = "transform 160ms ease-out";
        wrap.style.transform = "";
        setTimeout(() => { try { wrap.style.transition = ""; } catch { /* ignore */ } }, 180);
      } catch { /* ignore */ }
    };
    li.addEventListener("pointerup", release);
    li.addEventListener("pointercancel", release);
    return li;
  };
  const render = () => {
    try {
      listEl.textContent = "";
      if (state !== "loaded") {
        const li = h("li", state === "loading" ? "skel ses-empty" : "ses-empty");
        if (state === "loading") li.textContent = "Loading sessions...";
        else {
          li.textContent = "Failed to load. ";
          li.appendChild(btn("Retry", null, refresh));
        }
        listEl.appendChild(li);
        return;
      }
      const view = filterSessions(sessions, searchEl && searchEl.value ? searchEl.value : "");
      if (!view.length) {
        listEl.appendChild(h("li", "skel ses-empty", sessions.length ? "No matches" : "No sessions yet"));
        return;
      }
      for (const s of view.slice(0, 60)) listEl.appendChild(buildRow(s));
    } catch { /* ignore */ }
  };
  const paint = (animated) => {
    if (animated && motionOK()) flip(snapshot, render, playFlip);
    else render();
  };
  const refresh = async () => {
    state = "loading";
    paint(false);
    try {
      const loader = typeof opts.loadSessions === "function" ? opts.loadSessions : listSessions;
      const s = await loader();
      sessions = Array.isArray(s) ? s : [];
      state = "loaded";
      set({ sessions: sessions.slice() });
    } catch (e) {
      state = "error";
      showToast("Sessions failed to load. " + String((e && e.message) || ""), { kind: "err" });
    }
    paint(true);
  };
  try {
    if (searchEl) searchEl.addEventListener("input", debounce(() => paint(true), 80));
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  } catch { /* ignore */ }
  refresh();
  return { refresh, open: openPreview };
}
