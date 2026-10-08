import { createSSEParser } from "./api.js";
import { onWrite } from "./frame.js";
import { createPacer } from "./pacer.js";
import { initComposer, readParams } from "./composer.js";
import { initMessages, flipSend } from "./messages.js";
import { initMeter } from "./meter.js";
import { showToast } from "./toast.js";

export function frameBudget(backlog) {
  const b = typeof backlog === "number" && backlog > 0 ? backlog : 0;
  return Math.max(1, Math.ceil(b / 10));
}

export function shouldStick(dist) {
  return (typeof dist === "number" ? dist : 1e9) <= 80;
}

export function buildChatPayload(o) {
  o = o || {};
  const out = { model: String(o.model || ""), messages: Array.isArray(o.messages) ? o.messages : [] };
  if (typeof o.system === "string" && o.system.trim()) out.system = o.system.trim().slice(0, 8000);
  const mt = Number(o.max_tokens);
  if (o.max_tokens != null && Number.isFinite(mt) && mt > 0) out.max_tokens = Math.min(128000, Math.floor(mt));
  const tp = Number(o.temperature);
  if (o.temperature != null && String(o.temperature) !== "" && Number.isFinite(tp)) {
    out.temperature = Math.min(2, Math.max(0, tp));
  }
  return out;
}

export function translateError(status, body) {
  const b = String(body == null ? "" : body).slice(0, 300);
  if (status === 401) return { title: "API key missing or invalid", hint: "Set your key in config, then retry." + (b ? " " + b : ""), retry: true };
  if (status === 429) return { title: "Rate limited", hint: "Wait a moment, then retry." + (b ? " " + b : ""), retry: true };
  if (!status) return { title: "Network error", hint: "Check your connection, then retry.", retry: true };
  if (status >= 500) return { title: "Server error (" + status + ")", hint: "Upstream failed. Retry in a bit." + (b ? " " + b : ""), retry: true };
  return { title: "Request failed (" + status + ")", hint: b || "Retry.", retry: true };
}

const CONV_KEY = "ar-convs-v1";
const CONV_CAP = 180000;

function storage() {
  try {
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch {
    return null;
  }
}

export function loadConvs(st) {
  try {
    const s = st || storage();
    if (!s) return [];
    const j = JSON.parse(s.getItem(CONV_KEY) || "[]");
    return Array.isArray(j) ? j : [];
  } catch {
    return [];
  }
}

export function saveConvs(st, list) {
  const s = st || storage();
  if (!s) return false;
  let items = Array.isArray(list) ? list.slice() : [];
  try {
    let raw = JSON.stringify(items);
    while (raw.length > CONV_CAP && items.length > 1) {
      items = items.slice(1);
      raw = JSON.stringify(items);
    }
    if (raw.length > CONV_CAP) return false;
    s.setItem(CONV_KEY, raw);
    return true;
  } catch {
    try {
      s.setItem(CONV_KEY, JSON.stringify(items.slice(1)));
      return true;
    } catch {
      return false;
    }
  }
}

function guiToken() {
  try {
    if (typeof document === "undefined") return "";
    const m = document.querySelector("meta[name=ar-token]");
    const v = m && m.getAttribute("content");
    return typeof v === "string" ? v : "";
  } catch {
    return "";
  }
}

function currentModel(store) {
  try {
    if (store && typeof store.get === "function" && store.get("model")) return String(store.get("model"));
    return storage().getItem("ar-model") || "";
  } catch {
    return "";
  }
}

export function initChat(opts) {
  opts = opts || {};
  const store = opts.store || null;
  const noop = { send: () => {}, stop: () => {}, newChat: () => {}, resend: () => {}, pushMeter: () => {} };
  if (typeof document === "undefined") return noop;
  const conv = document.getElementById("conv");
  const stage = document.getElementById("stage") || (conv && conv.parentElement);
  const box = document.getElementById("composer");
  const emptyBox = document.getElementById("empty");
  if (!conv || !box) return noop;
  const ok = (fn) => { try { return fn(); } catch { return undefined; } };
  const setStore = (p) => ok(() => store && typeof store.set === "function" && store.set(p));

  const msgApi = initMessages({
    conv,
    onRegenerate: () => api.resend(),
    onEdit: (t) => ok(() => {
      box.value = t;
      box.focus();
      if (composerApi && composerApi.grow) composerApi.grow();
    }),
  });

  let meterApi = null;
  ok(() => { meterApi = initMeter(document.getElementById("meter"), document.getElementById("meterVal")); });

  let pill = document.getElementById("latestPill");
  ok(() => {
    if (!pill) {
      pill = document.createElement("button");
      pill.id = "latestPill";
      pill.type = "button";
      pill.hidden = true;
      pill.textContent = "Latest ↓";
      (stage || conv).appendChild(pill);
    }
  });

  let history = [];
  let convId = "c" + Date.now().toString(36);
  let streaming = false;
  let aborter = null;
  let stick = true;
  let syncing = false;
  let usage = null;
  let full = "";
  let handle = null;
  let pumping = false;
  const pacer = createPacer({ charsPerFrame: 240 });

  const persist = () => ok(() => {
    const list = loadConvs();
    const rec = { id: convId, updatedAt: Date.now(), title: (msgApi.lastUserText() || "chat").slice(0, 60), messages: history.slice(-200) };
    const rest = list.filter((c) => c.id !== convId);
    rest.push(rec);
    saveConvs(null, rest.slice(-20));
  });

  const paintEmpty = (endpoint) => ok(() => {
    if (!emptyBox) return;
    if (msgApi.count() > 0) { emptyBox.hidden = true; return; }
    emptyBox.hidden = false;
    emptyBox.textContent = "";
    const hh=document.createElement("h2");hh.textContent="How can I help you today?";emptyBox.appendChild(hh);
    const mm=document.createElement("div");mm.className="mut";mm.textContent="model: "+(currentModel(store)||"no model selected");emptyBox.appendChild(mm);
    const cc=document.createElement("div");cc.className="chips";
    for(const s of["Explain recursion","List models"]){const b=document.createElement("button");b.type="button";b.setAttribute("data-s",s);b.textContent=s;b.addEventListener("click",()=>{try{box.value=s;box.focus()}catch{}});cc.appendChild(b)}
    emptyBox.appendChild(cc);
  });

  ok(() => {
    fetch("/api/config").then((r) => (r.ok ? r.json() : null)).then((j) => {
      paintEmpty(j && j.base_url ? String(j.base_url).replace(/^https?:\/\//, "") : "");
    }).catch(() => paintEmpty(""));
  });
  paintEmpty("");

  const stickNow = () => {
    if (!stick || !stage) return;
    ok(() => { syncing = true; stage.scrollTop = stage.scrollHeight; });
    ok(() => {
      if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(() => { syncing = false; });
      else syncing = false;
    });
  };
  const showPill = (on) => ok(() => { if (pill) pill.hidden = !on; });

  const springToLatest = () => ok(() => {
    if (!stage) return;
    if (document.documentElement.getAttribute("data-motion") !== "full") {
      stick = true; stickNow(); showPill(false); return;
    }
    if (typeof requestAnimationFrame === "undefined") {
      stick = true; stickNow(); showPill(false); return;
    }
    const from = stage.scrollTop;
    const to = stage.scrollHeight - stage.clientHeight;
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 250);
      ok(() => { stage.scrollTop = from + (to - from) * (1 - Math.pow(1 - k, 3)); });
      if (k < 1) requestAnimationFrame(step);
      else { stick = true; showPill(false); stickNow(); }
    };
    requestAnimationFrame(step);
  });

  ok(() => {
    if (pill) pill.addEventListener("click", springToLatest);
    if (stage) {
      stage.addEventListener("scroll", () => {
        if (syncing) return;
        const dist = stage.scrollHeight - stage.scrollTop - stage.clientHeight;
        stick = shouldStick(dist);
        showPill(!stick && msgApi.count() > 0);
      }, { passive: true });
      stage.addEventListener("wheel", (e) => {
        if (e.deltaY < 0 && streaming) { stick = false; showPill(true); }
      }, { passive: true });
      stage.addEventListener("touchmove", () => {
        if (streaming) { stick = false; showPill(true); }
      }, { passive: true });
    }
    document.addEventListener("keydown", (e) => {
      const tag = e.target && e.target.tagName ? String(e.target.tagName).toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if ((e.key === "ArrowUp" || e.key === "PageUp" || e.key === "Home") && streaming) {
        stick = false;
        showPill(true);
      }
    });
  });

  const pumpStep = () => {
    const chunk = ok(() => pacer.drain(frameBudget(pacer.size))) || "";
    if (chunk && handle) {
      full += chunk;
      ok(() => handle.stream(full));
      ok(() => meterApi && meterApi.push(chunk.length, Date.now()));
    }
    stickNow();
    if (pacer.size > 0 && streaming) onWrite(pumpStep);
    else pumping = false;
  };
  const schedule = () => {
    if (pumping) return;
    pumping = true;
    onWrite(pumpStep);
  };

  const teardown = () => {
    streaming = false;
    aborter = null;
    ok(() => composerApi.paintSendStop(false));
    ok(() => conv.setAttribute("aria-busy", "false"));
    setStore({ running: false });
    showPill(false);
  };

  const finish = () => {
    const t0 = Date.now();
    const rest = ok(() => pacer.flush()) || "";
    if (rest) {
      full += rest;
      ok(() => meterApi && meterApi.push(rest.length, Date.now()));
    }
    ok(() => handle && handle.stream(full));
    ok(() => handle && handle.done(usage));
    stickNow();
    teardown();
    if (full.trim()) {
      history.push({ role: "assistant", content: full });
      persist();
    }
    if (Date.now() - t0 > 250) ok(() => showToast("End flush was slow", { kind: "info", duration: 2000 }));
    paintEmpty("");
  };

  const fail = (info, retryFn) => {
    teardown();
    ok(() => handle && handle.fail(info.title, info.hint, info.retry ? retryFn : null));
    ok(() => showToast(info.title + ". " + (info.hint || ""), { kind: "err" }));
  };

  const runStream = (payload, userText, isResend) => {
    const model = payload.model;
    if (!isResend) {
      const rec = ok(() => msgApi.addUser(userText));
      ok(() => flipSend(box, rec ? rec.el : null));
      history.push({ role: "user", content: userText });
      persist();
    }
    paintEmpty("");
    full = "";
    usage = null;
    pacer.clear();
    streaming = true;
    stick = true;
    showPill(false);
    ok(() => conv.setAttribute("aria-busy", "true"));
    ok(() => composerApi.paintSendStop(true));
    handle = ok(() => msgApi.beginAssistant(model));
    const ctrl = new AbortController();
    aborter = ctrl;
    const parser = createSSEParser((ev) => {
      if (!ev || typeof ev !== "object") return;
      if (typeof ev.reasoning === "string" && ev.reasoning) {
        ok(() => handle && handle.reason(ev.reasoning));
        return;
      }
      if (ev.usage && typeof ev.usage === "object") {
        usage = ev.usage;
        ok(() => handle && handle.usage(ev.usage));
        return;
      }
      if (typeof ev.content === "string" && ev.content) {
        pacer.push(ev.content);
        schedule();
        return;
      }
      if (ev.error) {
        fail({ title: "Request failed", hint: String(ev.error).slice(0, 300), retry: true }, () => api.resend());
        ok(() => ctrl.abort());
        return;
      }
      if (ev.done) finish();
    });
    const headers = { "Content-Type": "application/json" };
    const tok = guiToken();
    if (tok) headers["X-AgentRouter-Token"] = tok;
    fetch("/api/chat", { method: "POST", headers, body: JSON.stringify(payload), signal: ctrl.signal }).then(async (res) => {
      if (!res.ok) {
        const body = await ok(() => res.text()) || "";
        ok(() => handle && handle.el && handle.el.remove());
        handle = ok(() => msgApi.beginAssistant(model));
        if (!isResend) ok(() => history.pop());
        fail(translateError(res.status, body), () => api.send(userText, { resend: true }));
        return;
      }
      try {
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        for (;;) {
          const r = await reader.read();
          if (r.done) break;
          parser.push(dec.decode(r.value, { stream: true }));
        }
        parser.push(dec.decode(new Uint8Array(0)));
        parser.close();
        if (streaming) finish();
      } catch {
        if (ctrl.signal.aborted) finish();
        else fail(translateError(0, ""), () => api.send(userText, { resend: true }));
      }
    }).catch(() => {
      if (ctrl.signal.aborted) { finish(); return; }
      ok(() => handle && handle.el && handle.el.remove());
      handle = ok(() => msgApi.beginAssistant(model));
      if (!isResend) ok(() => history.pop());
      fail(translateError(0, ""), () => api.send(userText, { resend: true }));
    });
  };

  const composerApi = initComposer({
    running: () => streaming,
    onSend: (v) => api.send(v),
    onStop: () => api.stop(),
  });

  const payloadFor = (userText) => {
    const params = readParams(document);
    return buildChatPayload({
      model: currentModel(store),
      messages: history.concat([{ role: "user", content: userText }]),
      system: params.system,
      max_tokens: params.max_tokens,
      temperature: params.temperature,
    });
  };

  const api = {
    send(text, o) {
      if (streaming) return;
      o = o || {};
      try {
        if (store && typeof store.get === "function" && store.get("mode") === "agent" && typeof opts.onAgentSend === "function") {
          const raw = typeof text === "string" ? text : ok(() => box.value);
          opts.onAgentSend(raw);
          return;
        }
      } catch { /* fall through to chat */ }
      const raw = typeof text === "string" ? text : ok(() => box.value);
      const isResend = !!o.resend;
      const userText = isResend ? (raw || msgApi.lastUserText()) : raw;
      if (!userText || !userText.trim()) return;
      if (!currentModel(store)) {
        ok(() => showToast("Pick a model first.", { kind: "err" }));
        return;
      }
      if (!isResend) {
        ok(() => { box.value = ""; });
        ok(() => composerApi.grow());
      }
      runStream(payloadFor(userText), userText, isResend);
    },
    resend() {
      if (streaming) return;
      const t = msgApi.lastUserText();
      if (!t || !currentModel(store)) return;
      runStream(payloadFor(t), t, true);
    },
    stop() {
      try {
        if (store && typeof store.get === "function" && store.get("mode") === "agent" && typeof opts.onAgentStop === "function") opts.onAgentStop();
      } catch{}
      ok(() => aborter && aborter.abort());
    },
    pushMeter(n) {
      ok(() => meterApi && meterApi.push(typeof n === "number" ? n : 1, Date.now()));
    },
    newChat() {
      ok(() => aborter && aborter.abort());
      streaming = false;
      history = [];
      full = "";
      usage = null;
      convId = "c" + Date.now().toString(36);
      ok(() => msgApi.clear());
      ok(() => { box.value = ""; box.focus(); });
      paintEmpty("");
      showPill(false);
    },
    loadSession(msgs, id) {
      ok(() => aborter && aborter.abort());
      streaming = false;
      history = Array.isArray(msgs) ? msgs.slice(-200) : [];
      full = "";
      usage = null;
      if (typeof id === "string" && id) convId = id;
      ok(() => msgApi.clear());
      for (const m of history) {
        if (m.role === "user") ok(() => msgApi.addUser(m.content));
        else {
          const hh = ok(() => msgApi.beginAssistant(currentModel(store)));
          if (hh) { ok(() => hh.stream(m.content)); ok(() => hh.done(null)); }
        }
      }
      ok(() => { box.value = ""; });
      paintEmpty("");
      showPill(false);
    },
  };

  ok(() => {
    const list = loadConvs();
    const last = list.length ? list[list.length - 1] : null;
    if (last && Array.isArray(last.messages) && last.messages.length) {
      convId = last.id || convId;
      history = last.messages.slice(-200);
      for (const m of history) {
        if (m.role === "user") msgApi.addUser(m.content);
        else {
          const hh = msgApi.beginAssistant(currentModel(store));
          if (hh) { hh.stream(m.content); hh.done(null); }
        }
      }
      paintEmpty("");
    }
  });

  return api;
}
