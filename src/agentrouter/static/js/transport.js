import { paintOdometer } from "./odometer.js";
import { motionOK } from "./motion.js";

export function formatElapsed(ms) {
  const t = Math.max(0, typeof ms === "number" ? ms : 0);
  const d = Math.floor((t % 1000) / 100);
  const s = Math.floor(t / 1000) % 60;
  const m = Math.floor(t / 60000);
  const mm = m < 10 ? "0" + m : String(m);
  const ss = s < 10 ? "0" + s : String(s);
  return mm + ":" + ss + "." + d;
}

export function stepText(n) {
  const v = typeof n === "number" && Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0;
  return "step " + v;
}

export function nextMode(cur) {
  return cur === "agent" ? "chat" : "agent";
}

export function pickModels(payload) {
  if (!payload) return [];
  const raw = Array.isArray(payload) ? payload : payload.data || payload.models || [];
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const m of raw) {
    if (typeof m === "string") { if (m) out.push({ label: m, value: m }); continue; }
    if (m && typeof m === "object") {
      const id = m.id != null ? String(m.id) : (m.name != null ? String(m.name) : "");
      if (id) out.push({ label: id, value: id });
    }
  }
  return out;
}

export function initTransport(opts) {
  if (typeof document === "undefined") return () => {};
  opts = opts || {};
  const store = opts.store || null;
  const get = (k, d) => {
    try { if (store && typeof store.get === "function") { const v = store.get(k); return v == null ? d : v; } } catch{}
    return d;
  };
  const set = (p) => { try { if (store && typeof store.set === "function") store.set(p); } catch{} };

  const bar = document.getElementById("transport");
  if (!bar) return () => {};
  const segChat = bar.querySelector('[data-mode="chat"]');
  const segAgent = bar.querySelector('[data-mode="agent"]');
  const ind = bar.querySelector(".seg-ind");
  const modelBtn = document.getElementById("modelBtn");
  const modelName = document.getElementById("modelName");
  const led = document.getElementById("netLed") || document.getElementById("statusDot");
  const banner = document.getElementById("offlineBanner");
  const runBtn = document.getElementById("runBtn");
  const stopBtn = document.getElementById("stopBtn");
  const stepsEl = document.getElementById("stepCount");
  const clockEl = document.getElementById("elapsed");
  const composer = document.getElementById("composer");

  let mode = get("mode", "chat") === "agent" ? "agent" : "chat";
  let models = [];
  let t0 = 0;
  let tickId = 0;
  let online = true;

  const paintMode = (animate) => {
    const btn = mode === "agent" ? segAgent : segChat;
    try {
      if (segChat) segChat.setAttribute("aria-selected", mode === "chat" ? "true" : "false");
      if (segAgent) segAgent.setAttribute("aria-selected", mode === "agent" ? "true" : "false");
      if (ind && btn) {
        const left = btn.offsetLeft || 0;
        const w = btn.offsetWidth || 0;
        if (animate === false || !motionOK()) {
          ind.style.transition = "none";
          ind.style.transform = "translateX(" + left + "px)";
          ind.style.width = w + "px";
          void ind.offsetWidth;
          ind.style.transition = "";
        } else {
          ind.style.transform = "translateX(" + left + "px)";
          ind.style.width = w + "px";
        }
      }
    } catch{}
    set({ mode });
  };

  const setMode = (m, animate) => {
    if (m !== "chat" && m !== "agent") return;
    try {
      if (composer && typeof opts.saveDraft === "function") opts.saveDraft(mode, composer.value);
      else if (composer) {
        const drafts = get("drafts", {});
        set({ drafts: { ...drafts, [mode]: composer.value } });
      }
    } catch{}
    mode = m;
    paintMode(animate);
    try {
      let draft = "";
      if (composer && typeof opts.loadDraft === "function") draft = opts.loadDraft(mode) || "";
      else {
        const drafts = get("drafts", {});
        draft = (drafts && drafts[mode]) || "";
      }
      if (composer && draft !== composer.value) composer.value = draft;
    } catch{}
    try {
      if (typeof opts.onMode === "function") opts.onMode(mode);
    } catch{}
    if (composer && typeof opts.restoreScroll === "function") {
      try { opts.restoreScroll(mode); } catch{}
    }
  };

  try {
    if (segChat) segChat.addEventListener("click", () => setMode("chat", true));
    if (segAgent) segAgent.addEventListener("click", () => setMode("agent", true));
  } catch{}

  const paintModel = () => {
    try {
      const cur = get("model", "");
      if (modelName) modelName.textContent = "model: " + (cur || "-");
      if (modelBtn) {
        modelBtn.textContent = cur || "Select model";
        modelBtn.setAttribute("aria-label", "Select model, current " + (cur || "none"));
      }
    } catch{}
  };

  const openModels = async () => {
    try {
      const mod = await import("./popover.js");
      const open = mod.openPopover;
      if (!models.length && typeof opts.loadModels === "function") {
        try { models = await opts.loadModels(); } catch { models = []; }
      }
      const list = models.length ? models : [{ label: get("model", "") || "default", value: get("model", "") || "" }];
      open(modelBtn, {
        items: list,
        label: "Models",
        placeholder: "Search models...",
        onPick: (it) => {
          const v = it && it.value != null ? String(it.value) : "";
          set({ model: v });
          try { localStorage.setItem("ar-model", v); } catch{}
          paintModel();
          if (typeof opts.onModel === "function") { try { opts.onModel(v); } catch{} }
        },
      });
    } catch{}
  };
  try { if (modelBtn) modelBtn.addEventListener("click", openModels); } catch{}

  const paintNet = (wasOnline) => {
    try {
      if (led) {
        led.className = "dot " + (online ? "ok" : "warn pulse");
        led.setAttribute("aria-label", online ? "Online" : "Offline");
      }
      if (banner) {
        if (!online) {
          banner.hidden = false;
          banner.classList.add("show");
          banner.textContent = "Offline. Retrying...";
        } else {
          if (wasOnline === false) {
            banner.hidden = false;
            banner.classList.add("show", "back");
            banner.textContent = "Back online";
            if (led) led.classList.add("flash");
            setTimeout(() => {
              try {
                banner.classList.remove("show");
                banner.hidden = true;
                banner.classList.remove("back");
                if (led) led.classList.remove("flash");
              } catch{}
            }, motionOK() ? 1400 : 200);
          } else {
            banner.classList.remove("show");
            banner.hidden = true;
          }
        }
      }
    } catch{}
    set({ online });
  };

  const checkNet = async () => {
    try {
      if (typeof opts.checkOnline === "function") {
        const ok = await opts.checkOnline();
        if (!!ok !== online) { const was = online; online = !!ok; paintNet(was); }
        return;
      }
      if (typeof navigator !== "undefined" && typeof navigator.onLine === "boolean") {
        const ok = navigator.onLine;
        if (ok !== online) { const was = online; online = ok; paintNet(was); }
      }
    } catch{}
  };

  const paint = (el, text) => {
    try {
      if (!el) return;
      if (!paintOdometer(el, text)) el.textContent = String(text);
    } catch{}
  };

  const startClock = () => {
    try {
      t0 = performance.now();
      if (tickId) cancelAnimationFrame(tickId);
      const loop = () => {
        if (typeof document !== "undefined" && document.hidden) { tickId = requestAnimationFrame(loop); return; }
        try { paint(clockEl, formatElapsed(performance.now() - t0)); } catch{}
        tickId = requestAnimationFrame(loop);
      };
      tickId = requestAnimationFrame(loop);
    } catch{}
  };
  const stopClock = () => {
    try { if (tickId) cancelAnimationFrame(tickId); } catch{}
    tickId = 0;
  };

  try {
    if (runBtn) runBtn.addEventListener("click", () => {
      set({ running: true });
      try { paint(stepsEl, stepText(0)); } catch{}
      startClock();
      if (typeof opts.onRun === "function") { try { opts.onRun(mode); } catch{} }
    });
    if (stopBtn) stopBtn.addEventListener("click", () => {
      set({ running: false });
      stopClock();
      if (typeof opts.onStop === "function") { try { opts.onStop(); } catch{} }
    });
  } catch{}

  try {
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) paintMode(false);
    });
    window.addEventListener("online", () => { const was = online; online = true; paintNet(was); });
    window.addEventListener("offline", () => { const was = online; online = false; paintNet(was); });
    window.addEventListener("resize", () => paintMode(false));
  } catch{}

  const iv = setInterval(checkNet, 5000);
  paintMode(false);
  paintModel();
  paintNet(true);
  if (clockEl && !clockEl.textContent) paint(clockEl, "00:00.0");

  const api = () => {
    try { clearInterval(iv); } catch{}
    stopClock();
  };
  api.agentStep = (n) => {
    try { paint(stepsEl, stepText(n)); } catch{}
    set({ steps: typeof n === "number" ? n : 0 });
  };
  api.agentStart = () => {
    try { paint(stepsEl, stepText(0)); } catch{}
    startClock();
    set({ running: true });
  };
  api.agentIdle = () => {
    stopClock();
    set({ running: false });
  };
  return api;
}
