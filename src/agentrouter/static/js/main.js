import { initFrame } from "./frame.js";
import { createShellStore } from "./store.js";
import { initPerfHUD } from "./perf-hud.js";
import { initSettings, initSettingsPanel, setTheme } from "./settings.js";
import { initRail } from "./rail.js";
import { listSessions, initSessions } from "./sessions.js";
import { initConfig } from "./config.js";
import { initTransport } from "./transport.js";
import { initInspector } from "./inspector.js";
import { initPalette, openPalette, buildActions } from "./palette.js";
import { initToasts, showToast } from "./toast.js";
import { apiFetch } from "./api.js";
import { initChat } from "./chat.js";
import { initTimeline } from "./timeline.js";

export const store = createShellStore({});

function cycleTheme() {
  try {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    const next = cur === "dark" ? "light" : cur === "light" ? "os" : "dark";
    setTheme(next, store);
    const btn = document.getElementById("themeBtn");
    if (btn) btn.textContent = next === "dark" ? "Light" : next === "light" ? "OS" : "Dark";
  } catch { /* ignore */ }
}

let toggleInspector = null;
let chatApi = null;
let agentApi = null;
let transportApi = null;

function focusComposer() {
  try {
    const c = document.getElementById("composer");
    if (c && typeof c.focus === "function") c.focus();
  } catch { /* ignore */ }
}

function shortcutsOverlay() {
  showToast("Ctrl+K palette. / focuses input. ? shows this. Enter sends.", { kind: "info" });
}

async function loadModels() {
  try {
    const res = await apiFetch("/api/models");
    const j = await res.json();
    const raw = Array.isArray(j) ? j : (j.data || j.models || []);
    const out = [];
    for (const m of raw) {
      if (typeof m === "string") { if (m) out.push({ label: m, value: m }); continue; }
      if (m && typeof m === "object") {
        const id = m.id != null ? String(m.id) : "";
        if (id) out.push({ label: id, value: id });
      }
    }
    store.set({ models: out });
    return out;
  } catch {
    return [];
  }
}

function wireThemeBtn() {
  try {
    const b = document.getElementById("themeBtn");
    if (!b) return;
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    b.textContent = cur === "dark" ? "Light" : cur === "light" ? "OS" : "Dark";
    b.onclick = cycleTheme;
  } catch { /* ignore */ }
}

function wireRailToggleMobile() {
  try {
    const b = document.getElementById("railOpenBtn");
    if (!b) return;
    b.onclick = () => {
      try {
        const rail = document.getElementById("rail");
        if (rail) rail.classList.add("drawer-open");
        const scrim = document.getElementById("scrim");
        if (scrim) { scrim.hidden = false; scrim.style.opacity = "0.45"; }
        store.set({ railDrawer: true });
      } catch { /* ignore */ }
    };
  } catch { /* ignore */ }
}

function boot() {
  initSettings(store);
  initFrame();
  initPerfHUD();
  initToasts();
  wireThemeBtn();
  wireRailToggleMobile();

  try {
    toggleInspector = initInspector({ store });
  } catch { /* ignore */ }

  try {
    initRail({
      store,
      sessionsOwned: true,
      onNew: () => {
        try {
          if (chatApi && chatApi.newChat) chatApi.newChat();
          else {
            const c = document.getElementById("composer");
            if (c) { c.value = ""; c.focus(); }
            store.set({ sessionId: "" });
          }
        } catch { /* ignore */ }
      },
    });
  } catch { /* ignore */ }

  try {
    transportApi = initTransport({
      store,
      loadModels,
      onRun: (mode) => {
        try {
          const m = mode || store.get("mode");
          if (m === "agent" && agentApi) agentApi.send();
          else if (chatApi && chatApi.send) chatApi.send();
        } catch { /* ignore */ }
      },
      onStop: () => {
        try {
          if (store.get("mode") === "agent" && agentApi) agentApi.stop();
          else if (chatApi && chatApi.stop) chatApi.stop();
        } catch { /* ignore */ }
      },
      onMode: (m) => { try { store.set({ mode: m }); } catch { /* ignore */ } },
      onModel: (v) => { try { store.set({ model: v }); } catch { /* ignore */ } },
    });
  } catch { /* ignore */ }

  try {
    try {
      const saved = localStorage.getItem("ar-model");
      if (saved) store.set({ model: saved });
    } catch { /* ignore */ }
  } catch { /* ignore */ }

  const getActions = () => buildActions({
    onNewChat: () => {
      const b = document.getElementById("newChat");
      if (b) b.click();
      else focusComposer();
    },
    onSwitchMode: () => {
      const cur = store.get("mode") === "agent" ? "chat" : "agent";
      const btn = document.querySelector('#transport [data-mode="' + cur + '"]');
      if (btn) btn.click();
    },
    onSwitchModel: () => {
      const b = document.getElementById("modelBtn");
      if (b) b.click();
    },
    onOpenSession: () => {
      const s = document.getElementById("sesSearch");
      if (s) s.focus();
    },
    onToggleTheme: cycleTheme,
    onToggleInspector: () => { if (typeof toggleInspector === "function") toggleInspector(); },
    onFocusInput: focusComposer,
    onShortcuts: shortcutsOverlay,
  });

  try {
    initPalette({ getActions, onFocusInput: focusComposer, onShortcuts: shortcutsOverlay });
  } catch { /* ignore */ }

  try {
    chatApi = initChat({
      store,
      onAgentSend: (t) => { try { if (agentApi) agentApi.send(t); } catch { /* ignore */ } },
      onAgentStop: () => { try { if (agentApi) agentApi.stop(); } catch { /* ignore */ } },
    });
  } catch { /* ignore */ }

  try {
    initSessions({
      store,
      loadSessions: listSessions,
      onLoad: (msgs, id) => { try { if (chatApi && chatApi.loadSession) chatApi.loadSession(msgs, id); } catch { /* ignore */ } },
    });
  } catch { /* ignore */ }

  try {
    initConfig({ store });
  } catch { /* ignore */ }

  try {
    initSettingsPanel(store);
  } catch { /* ignore */ }

  try {
    agentApi = initTimeline({
      store,
      transport: transportApi,
      pushMeter: (n) => { try { if (chatApi && chatApi.pushMeter) chatApi.pushMeter(n); } catch { /* ignore */ } },
    });
  } catch { /* ignore */ }

  try {
    if (typeof IntersectionObserver !== "undefined") {
      const stage = document.getElementById("stage");
      if (stage) {
        let vis = true;
        const ob = new IntersectionObserver((es) => {
          for (const e of es) vis = e.isIntersecting;
          try { store.set({ stageVisible: vis }); } catch { /* ignore */ }
        });
        ob.observe(stage);
      }
    }
  } catch { /* ignore */ }
}

try {
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
    else boot();
  }
} catch { /* ignore */ }
