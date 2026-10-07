export function filterSessions(sessions, query) {
  const q = String(query == null ? "" : query).trim().toLowerCase();
  const list = Array.isArray(sessions) ? sessions : [];
  if (!q) return list.slice();
  return list.filter((s) => {
    const id = String((s && (s.id || s.label || s.title)) || "");
    const prev = String((s && (s.preview || s.snippet)) || "");
    return id.toLowerCase().includes(q) || prev.toLowerCase().includes(q);
  });
}

export function drawerTarget(open, x, velocity, width) {
  const w = typeof width === "number" && width > 0 ? width : 260;
  const v = typeof velocity === "number" ? velocity : 0;
  if (v > 0.35) return true;
  if (v < -0.35) return false;
  if (typeof x === "number") return x > w / 2;
  return !!open;
}

import { motionOK } from "./motion.js";

export function initRail(opts) {
  if (typeof document === "undefined") return () => {};
  opts = opts || {};
  const store = opts.store || null;
  const set = (p) => { try { if (store && typeof store.set === "function") store.set(p); } catch{} };
  const get = (k, d) => {
    try { if (store && typeof store.get === "function") { const v = store.get(k); return v == null ? d : v; } } catch{}
    return d;
  };

  const rail = document.getElementById("rail");
  if (!rail) return () => {};
  const inner = rail.querySelector(".rail-inner") || rail;
  const listEl = document.getElementById("sesList");
  const searchEl = document.getElementById("sesSearch");
  const newBtn = document.getElementById("newChat");
  const collapseBtn = document.getElementById("railToggle");
  const keyLed = document.getElementById("keyLed");
  const verEl = document.getElementById("railVer");
  const scrim = document.getElementById("scrim");

  let sessions = Array.isArray(opts.sessions) ? opts.sessions.slice() : [];
  let collapsed = get("railCollapsed", false) === true;
  let drawer = false;
  let dragX = null;
  let lastX = 0;
  let lastT = 0;
  let vel = 0;
  let raf = 0;

  const isMobile = () => {
    try { return window.matchMedia("(max-width: 900px)").matches; } catch { return false; }
  };

  const sessionsOwned = !!opts.sessionsOwned;

  const paintList = () => {
    if (sessionsOwned) return;
    try {
      if (!listEl) return;
      const q = searchEl && searchEl.value ? searchEl.value : "";
      const view = filterSessions(sessions, q);
      while (listEl.firstChild) listEl.removeChild(listEl.firstChild);
      if (!view.length) {
        const li = document.createElement("li");
        li.className = "skel ses-empty";
        li.textContent = sessions.length ? "No matches" : "No sessions yet";
        listEl.appendChild(li);
        return;
      }
      const cur = get("sessionId", "");
      view.slice(0, 60).forEach((s) => {
        const id = String(s.id || s.label || "");
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "ses-row" + (id && id === cur ? " on" : "");
        b.dataset.sid = id;
        b.textContent = id || "session";
        b.addEventListener("click", () => {
          set({ sessionId: id });
          try { if (typeof opts.onOpen === "function") opts.onOpen(id); } catch{}
          if (isMobile()) setDrawer(false, true);
        });
        li.appendChild(b);
        listEl.appendChild(li);
      });
    } catch{}
  };

  const paintCollapse = (animate) => {
    try {
      rail.classList.toggle("collapsed", !!collapsed);
      rail.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (!isMobile() && inner) {
        if (animate === false || !motionOK()) {
          inner.style.transition = "none";
          inner.style.transform = collapsed ? "translateX(-212px)" : "";
          void inner.offsetWidth;
          inner.style.transition = "";
        } else {
          inner.style.transform = collapsed ? "translateX(-212px)" : "";
        }
      }
      if (collapseBtn) collapseBtn.textContent = collapsed ? ">" : "<";
      if (collapseBtn) collapseBtn.setAttribute("aria-label", collapsed ? "Expand sessions" : "Collapse sessions");
    } catch{}
    set({ railCollapsed: !!collapsed });
  };

  const paintScrim = (p) => {
    try {
      if (!scrim) return;
      const v = Math.max(0, Math.min(1, p));
      if (v <= 0) { scrim.hidden = true; scrim.style.opacity = "0"; return; }
      scrim.hidden = false;
      scrim.style.opacity = String(v * 0.45);
    } catch{}
  };

  const setDrawer = (open, animate) => {
    drawer = !!open;
    try {
      rail.classList.toggle("drawer-open", drawer);
      if (drawer) rail.classList.remove("collapsed");
    } catch{}
    paintScrim(drawer ? 1 : 0);
    if (!motionOK() || animate === false) {
      try { rail.style.transform = drawer ? "" : ""; } catch{}
    }
    set({ railDrawer: drawer });
  };

  const onDragMove = (x) => {
    try {
      const w = rail.offsetWidth || 260;
      const p = Math.max(0, Math.min(1, x / w));
      rail.style.transform = "translateX(" + Math.round((p - 1) * w) + "px)";
      paintScrim(p);
    } catch{}
  };

  const endDrag = (x) => {
    try { rail.style.transform = ""; } catch{}
    setDrawer(drawerTarget(drawer, x, vel, rail.offsetWidth || 260), true);
    dragX = null;
    vel = 0;
    try { if (raf) cancelAnimationFrame(raf); } catch{}
    raf = 0;
  };

  try {
    if (searchEl && !sessionsOwned) searchEl.addEventListener("input", paintList);
    if (newBtn) newBtn.addEventListener("click", () => {
      try { if (typeof opts.onNew === "function") opts.onNew(); } catch{}
      if (isMobile()) setDrawer(false, true);
    });
    if (collapseBtn) collapseBtn.addEventListener("click", () => {
      collapsed = !collapsed;
      paintCollapse(true);
    });
    if (scrim) scrim.addEventListener("click", () => setDrawer(false, true));
    rail.addEventListener("pointerdown", (e) => {
      if (!isMobile() || !drawer) return;
      if (e.pointerType !== "touch" && e.pointerType !== "pen" && e.button !== 0) return;
      dragX = e.clientX;
      lastX = e.clientX;
      lastT = performance.now();
      vel = 0;
    });
    rail.addEventListener("pointermove", (e) => {
      if (dragX == null || !isMobile()) return;
      const now = performance.now();
      const dx = e.clientX - lastX;
      const dt = Math.max(1, now - lastT) / 1000;
      vel = 0.8 * vel + 0.2 * (dx / dt / 1000);
      lastX = e.clientX;
      lastT = now;
      onDragMove(e.clientX);
    });
    const up = (e) => {
      if (dragX == null) return;
      try { endDrag(e.clientX); } catch{}
    };
    rail.addEventListener("pointerup", up);
    rail.addEventListener("pointercancel", up);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) { paintList(); paintCollapse(false); }
    });
    window.addEventListener("resize", () => { paintCollapse(false); paintScrim(drawer && isMobile() ? 1 : 0); });
  } catch{}

  const loadMeta = async () => {
    try {
      if (typeof opts.loadVersion === "function") {
        const v = await opts.loadVersion();
        if (verEl && v) verEl.textContent = "v" + String(v);
        return;
      }
      const r = await fetch("/api/version", { headers: { Accept: "application/json" } });
      if (r.ok) {
        const j = await r.json();
        if (verEl && j && j.version) verEl.textContent = "v" + String(j.version);
      }
    } catch { /* kept placeholder */ }
    try {
      if (typeof opts.loadKey === "function") {
        const has = await opts.loadKey();
        if (keyLed) { keyLed.className = "dot " + (has ? "ok" : "bad"); }
        return;
      }
      const r = await fetch("/api/config", { headers: { Accept: "application/json" } });
      if (r.ok) {
        const j = await r.json();
        if (keyLed) {
          keyLed.className = "dot " + (j && j.has_key ? "ok" : "bad");
          keyLed.setAttribute("aria-label", j && j.has_key ? "API key set" : "API key missing");
        }
      } else if (keyLed) {
        keyLed.className = "dot warn";
      }
    } catch {
      try { if (keyLed) keyLed.className = "dot warn"; } catch{}
    }
    try {
      if (typeof opts.loadSessions === "function") {
        const s = await opts.loadSessions();
        if (Array.isArray(s)) { sessions = s; paintList(); }
      }
    } catch{}
  };

  paintList();
  paintCollapse(false);
  loadMeta();

  return () => {
    try { if (raf) cancelAnimationFrame(raf); } catch{}
  };
}

export function openRailDrawer() {
  try {
    const rail = document.getElementById("rail");
    if (rail) rail.classList.add("drawer-open");
    const scrim = document.getElementById("scrim");
    if (scrim) { scrim.hidden = false; scrim.style.opacity = "0.45"; }
  } catch{}
}
