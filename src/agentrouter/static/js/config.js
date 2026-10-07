import { showToast } from "./toast.js";
import { openDialog, closeDialog, isDialogOpen } from "./dialog.js";
import { apiFetch } from "./api.js";
import { h } from "./sessions.js";

export const LOCKED_BASE_URL = "https://agentrouter.org/v1";

export function validateKey(k) {
  if (typeof k !== "string" || !k.trim()) return { ok: false, error: "API key must not be empty." };
  if (k.trim().length < 8) return { ok: false, error: "API key looks too short." };
  return { ok: true, key: k.trim() };
}

export function validateModel(m) {
  if (m == null || m === "") return { ok: true, model: "" };
  if (typeof m !== "string" || !m.trim()) return { ok: false, error: "Model must be a string." };
  return { ok: true, model: m.trim().slice(0, 200) };
}

export function translateConfigError(status, body) {
  const b = String(body == null ? "" : body).slice(0, 200);
  if (!status) return { title: "Network error", hint: "Check your connection, then retry." };
  if (status === 401) return { title: "Unauthorized (401)", hint: "API key missing or invalid. Check the key, then retry." + (b ? " " + b : "") };
  if (status === 429) return { title: "Rate limited (429)", hint: "Wait a moment, then retry." + (b ? " " + b : "") };
  if (status >= 500) return { title: "Server error (" + status + ")", hint: "Upstream failed. Retry in a bit." + (b ? " " + b : "") };
  return { title: "Request failed (" + status + ")", hint: b || "Retry." };
}

export function needsOnboarding(cfg) {
  return !cfg || cfg.has_key !== true;
}

async function cfgJson(path, opt) {
  const r = await apiFetch(path, opt);
  return r.json();
}

export function loadConfig() {
  return cfgJson("/api/config");
}

export function saveConfig(payload) {
  return cfgJson("/api/config", { method: "POST", body: payload });
}

export function testConnection() {
  return cfgJson("/api/models").then((j) => {
    const n = j && Array.isArray(j.data) ? j.data.length : (Array.isArray(j) ? j.length : -1);
    return { ok: true, models: n };
  });
}

export function dismissOnboarding() {
  if (typeof document === "undefined") return;
  try {
    const el = document.getElementById("onboard");
    if (el && el.parentNode) el.parentNode.removeChild(el);
  } catch { /* ignore */ }
}

export function showOnboarding(onOpen) {
  if (typeof document === "undefined") return false;
  try {
    if (document.getElementById("onboard")) return true;
    const card = h("div");
    card.id = "onboard";
    card.setAttribute("data-onboarding", "first-run");
    card.setAttribute("role", "status");
    const b = h("button", "pri", "Open config");
    b.type = "button";
    b.addEventListener("click", () => { try { onOpen && onOpen(); } catch { /* ignore */ } });
    card.append(h("h2", null, "Add your API key to begin"), h("p", "mut", "Paste a key in config to start."), b);
    const empty = document.getElementById("empty");
    if (empty) { empty.hidden = false; empty.prepend(card); }
    else (document.getElementById("stage") || document.body).appendChild(card);
    return true;
  } catch {
    return false;
  }
}

export function openConfig(opts) {
  if (typeof document === "undefined") return null;
  if (isDialogOpen()) closeDialog();
  opts = opts || {};
  const box = h("section", "cfg");
  box.setAttribute("aria-label", "Configuration");
  box.appendChild(h("h3", null, "Config"));
  const field = (label, type, id, ph) => {
    const lab = h("label", null, label);
    const el = h("input");
    el.type = type;
    el.id = id;
    el.placeholder = ph || "";
    el.autocomplete = "off";
    lab.appendChild(el);
    box.appendChild(lab);
    return el;
  };
  const keyInp = field("API key", "password", "cfgKey", "sk-...");
  const showBtn = h("button", null, "Show");
  showBtn.type = "button";
  showBtn.addEventListener("click", () => {
    keyInp.type = keyInp.type === "password" ? "text" : "password";
    showBtn.textContent = keyInp.type === "password" ? "Show" : "Hide";
  });
  const modelInp = field("Default model", "text", "cfgModel", "model id (optional)");
  const st = h("p", "mut");
  st.setAttribute("aria-live", "polite");
  const row = h("div", "cfg-row");
  const say = (t) => { try { st.textContent = t; } catch { /* ignore */ } };
  const sayErr = (t) => { say(t); showToast(t, { kind: "err" }); };
  const saveBtn = h("button", "pri", "Save");
  saveBtn.type = "button";
  const testBtn = h("button", null, "Test connection");
  testBtn.type = "button";
  const closeBtn = h("button", null, "Close");
  closeBtn.type = "button";
  closeBtn.addEventListener("click", () => closeDialog());
  box.append(showBtn, h("p", "mut", "Base URL locked to " + LOCKED_BASE_URL), st, row);
  row.append(saveBtn, testBtn, closeBtn);
  saveBtn.addEventListener("click", async () => {
    const kv = keyInp.value ? validateKey(keyInp.value) : { ok: true, key: "" };
    const mv = validateModel(modelInp.value);
    if (keyInp.value && !kv.ok) { sayErr(kv.error); return; }
    if (!mv.ok) { sayErr(mv.error); return; }
    const payload = {};
    if (kv.key) payload.api_key = kv.key;
    if (mv.model) payload.default_model = mv.model;
    if (!payload.api_key && !payload.default_model) { say("Nothing to update."); return; }
    saveBtn.disabled = true;
    try {
      const j = await saveConfig(payload);
      say("Saved. Key: " + (j && j.has_key ? "set" : "missing"));
      showToast("Config saved");
      try { opts.onSaved && opts.onSaved(j); } catch { /* ignore */ }
      if (j && j.has_key) dismissOnboarding();
    } catch (e) {
      const t = translateConfigError(e && e.status, e && e.message);
      sayErr(t.title + ". " + t.hint);
    } finally {
      try { saveBtn.disabled = false; } catch { /* ignore */ }
    }
  });
  testBtn.addEventListener("click", async () => {
    testBtn.disabled = true;
    say("Testing...");
    try {
      const j = await testConnection();
      say(j.models >= 0 ? "Connected. " + j.models + " models." : "Connected.");
      showToast("Connection OK");
    } catch (e) {
      const m = String((e && e.message) || "");
      const t = translateConfigError(/401/.test(m) ? 401 : /429/.test(m) ? 429 : 0, m);
      sayErr(t.title + ". " + t.hint);
    } finally {
      try { testBtn.disabled = false; } catch { /* ignore */ }
    }
  });
  loadConfig().then((j) => {
    try {
      if (j && j.default_model) modelInp.value = String(j.default_model);
      say(j && j.has_key ? "Key set." : "No key set. Paste a key, then Save.");
    } catch { /* ignore */ }
  }).catch(() => say("Could not load config."));
  (document.getElementById("center") || document.body).appendChild(box);
  const handle = openDialog(box, { onClose: () => { try { box.remove(); } catch { /* ignore */ } } });
  if (!handle) { try { box.remove(); } catch { /* ignore */ } return null; }
  return handle;
}

export function initConfig(opts) {
  if (typeof document === "undefined") return () => {};
  opts = opts || {};
  const open = () => openConfig({ store: opts.store, onSaved: opts.onSaved });
  try {
    const btn = document.getElementById("configBtn");
    if (!btn) return open;
    btn.addEventListener("click", open);
    if (opts.store && opts.store.subscribe) {
      opts.store.subscribe((s) => {
        try { btn.classList.toggle("off", !!(s && s.online === false)); } catch { /* ignore */ }
      });
    }
  } catch { /* ignore */ }
  loadConfig().then((j) => {
    try {
      if (needsOnboarding(j)) showOnboarding(open);
      else dismissOnboarding();
    } catch { /* ignore */ }
  }).catch(() => { try { showOnboarding(open); } catch { /* ignore */ } });
  return open;
}
