import { apiFetch } from "./api.js";
import { renderDiff } from "./diff.js";
import { showDetail } from "./inspector.js";
import { openApproval } from "./dialog.js";
import { formatElapsed } from "./transport.js";
import { showToast } from "./toast.js";

export function resolveStop(o) {
  o = o || {};
  if (o.aborted) return "user_abort";
  if (o.error) return "error";
  const m = typeof o.maxSteps === "number" ? o.maxSteps : 0;
  return m > 0 && (typeof o.steps === "number" ? o.steps : 0) >= m ? "max_steps" : "done";
}

export function stopLabel(r) {
  return r === "max_steps" ? "max steps reached" : r === "error" ? "error" : r === "user_abort" ? "stopped by you" : "done";
}

export function barFrac(e, t) {
  if (!(t > 0)) return -1;
  e = e > 0 ? e : 0;
  return Math.min(1, e / (t * 1000));
}

export function bashTimeoutMs(tool, args) {
  try {
    if (tool !== "bash" || !args || typeof args !== "object") return 0;
    const t = Number(args.timeout);
    return t > 0 ? t : 0;
  } catch {
    return 0;
  }
}

export function hunkDelay(i, n) {
  const k = i > 0 ? Math.floor(i) : 0;
  return Math.round((200 * k) / (n > 0 ? Math.floor(n) : 1));
}

export function argSummary(args) {
  try {
    return JSON.stringify(args || {}).slice(0, 60);
  } catch {
    return "";
  }
}

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? Math.floor(n) : 0;
};
const str = (v) => (typeof v === "string" ? v : v == null ? "" : String(v));
const obj = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : {});

export function parseAgentEvent(p) {
  if (!p || typeof p !== "object") return { kind: "unknown", raw: p };
  const t = p.type;
  if (t === "step") return { kind: "step", step: num(p.step), text: str(p.text), raw: p };
  if (t === "tool") return { kind: "tool", step: num(p.step), tool: str(p.tool) || "tool", args: obj(p.args), result: str(p.result), raw: p };
  if (t === "done") return { kind: "done", text: str(p.text), sessionId: str(p.session_id || p.sessionId), raw: p };
  if (t === "error" || typeof p.error === "string") return { kind: "error", error: str(p.error == null ? t : p.error), raw: p };
  if (t === "approval") return { kind: "approval", tool: str(p.tool), args: obj(p.args), raw: p };
  return { kind: p.done ? "stream_end" : "unknown", raw: p };
}

function el(tag, cls, text, parent) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}

function byId(id) {
  try { return document.getElementById(id); } catch { return null; }
}

function modelOf(store) {
  try {
    if (store && store.get && store.get("model")) return String(store.get("model"));
    return localStorage.getItem("ar-model") || "";
  } catch { return ""; }
}

export function initTimeline(opts) {
  opts = opts || {};
  const store = opts.store || null;
  const noop = { send() {}, stop() {}, rerun() {}, resume() {}, active() { return false; } };
  if (typeof document === "undefined" || !byId("conv")) return noop;
  const conv = byId("conv");
  const ok = (fn) => { try { return fn(); } catch { return undefined; } };
  const tp = opts.transport || null;
  const tStep = (n) => ok(() => tp && tp.agentStep && tp.agentStep(n));
  const tStart = () => ok(() => tp && tp.agentStart && tp.agentStart());
  const tIdle = () => ok(() => tp && tp.agentIdle && tp.agentIdle());
  const pushM = (n) => ok(() => opts.pushMeter && opts.pushMeter(n));
  const setS = (p) => ok(() => store && store.set && store.set(p));
  const maxSteps = opts.maxSteps > 0 ? Math.floor(opts.maxSteps) : 10;
  let run = null;
  let lastGoal = "";
  let lastSession = "";

  const buttons = (busy) => {
    const rb = byId("runBtn");
    const sb = byId("stopBtn");
    if (rb) {
      rb.classList.toggle("is-stop", !!busy);
      rb.setAttribute("aria-label", busy ? "Stop" : "Send");
      const l = rb.querySelector(".send-lbl");
      if (l) l.textContent = busy ? "■" : "↑";
    }
    if (sb) sb.hidden = !busy;
  };

  const shut = (r) => {
    let max = 0;
    for (const q of r.rows) max = Math.max(max, q.elapsed);
    for (const q of r.rows) {
      q.fill.classList.remove("live");
      q.fill.style.width = (max > 0 ? Math.round((100 * q.elapsed) / max) : 100) + "%";
    }
  };

  const shutRow = (r, owner) => {
    if (!r || !r.open) return;
    r.open = false;
    r.elapsed = Math.max(0, performance.now() - r.t0);
    r.dur.textContent = formatElapsed(r.elapsed);
    r.fill.classList.remove("live");
    if (owner) shut(owner);
  };

  const dump = (a) => {
    try { return JSON.stringify(a == null ? {} : a, null, 1).slice(0, 8000); }
    catch { return str(a).slice(0, 8000); }
  };

  const detail = (args, result) => {
    const d = el("div", "tl-detail");
    el("pre", "mono tl-args", "args\n" + dump(args), d);
    el("pre", "mono tl-args", "result\n" + (str(result).slice(0, 8000) || "(empty)"), d);
    return d;
  };

  const toolRow = (ev) => {
    const now = performance.now();
    if (run.openRow) shutRow(run.openRow, run);
    const idx = run.rows.length + 1;
    const row = el("div", "tl-row", null, run.list);
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    const head = el("div", "tl-row-h", null, row);
    el("span", "tl-idx mono", String(idx).padStart(2, "0"), head);
    el("span", "tl-tool mono", ev.tool, head);
    el("span", "tl-sum", argSummary(ev.args), head);
    const dur = el("span", "tl-dur mono", "", head);
    const fill = el("i", "tl-fill live", null, el("div", "tl-bar", null, row));
    const body = el("div", "collapse", null, row);
    const inner = el("div", "collapse-inner", null, body);
    const a = ev.args || {};
    const diff = ev.tool === "edit_file" && typeof a.old_string === "string" && typeof a.new_string === "string"
      ? renderDiff(a.old_string, a.new_string) : null;
    if (diff) {
      const hs = diff.querySelectorAll(".tl-hunk");
      for (let i = 0; i < hs.length; i++) {
        hs[i].className += " fade-hunk";
        hs[i].style.animationDelay = hunkDelay(i, hs.length) + "ms";
      }
      inner.appendChild(diff);
    }
    const res = str(ev.result);
    const rw = el("div", "collapse open", null, inner);
    el("pre", "mono tl-res", (diff ? res.slice(0, 4000) : res.slice(0, 8000)), el("div", "collapse-inner", null, rw));
    const toggle = () => {
      ok(() => showDetail("step " + idx + " · " + ev.tool, detail(ev.args, ev.result)));
      row.classList.toggle("open", body.classList.toggle("open"));
    };
    row.onclick = toggle;
    row.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
    };
    fill.style.width = timeout > 0 ? "2%" : "100%";
    const rec = { fill, dur, t0: now, elapsed: 0, open: true, timeout };
    run.rows.push(rec);
    run.openRow = rec;
  };

  const finish = (why) => {
    if (!run) return;
    const r = run;
    run = null;
    clearInterval(r.tick);
    if (r.openRow) shutRow(r.openRow, r);
    if (!r.reason) r.reason = why || resolveStop({ steps: r.steps, maxSteps: r.maxSteps, error: r.error, aborted: r.aborted });
    const bad = r.reason === "error";
    r.led.classList.remove("running");
    r.led.classList.add(bad ? "err" : "done");
    if (!bad) r.led.classList.add("pulse-once");
    else {
      r.block.classList.add("tl-err", "shake");
      r.block.addEventListener("animationend", () => r.block.classList.remove("shake"), { once: true });
    }
    r.stop.textContent = stopLabel(r.reason) + " · " + r.steps + "/" + r.maxSteps + " · " + formatElapsed(performance.now() - r.t0);
    r.stop.hidden = false;
    r.rerun.hidden = false;
    if (r.sessionId) r.resume.hidden = false;
    tIdle();
    buttons(false);
    setS({ running: false, steps: r.steps });
    if (r.sessionId) lastSession = r.sessionId;
  };

  const note = (text) => {
    const t = str(text).slice(0, 2000);
    if (t.trim()) el("div", "tl-note", t, run.list);
  };

  const onEv = (ev) => {
    if (!run) return;
    if (ev.kind === "step" || ev.kind === "tool") {
      run.steps = Math.max(run.steps, ev.step || run.steps + 1);
      tStep(run.steps);
      setS({ steps: run.steps });
    }
    if (ev.kind === "step") {
      if (ev.text) pushM(ev.text.length);
      return;
    }
    if (ev.kind === "tool") {
      pushM(JSON.stringify(ev.args).length + ev.result.length);
      toolRow(ev);
    } else if (ev.kind === "done") {
      if (ev.sessionId) run.sessionId = ev.sessionId;
      if (ev.text) pushM(ev.text.length);
      note(ev.text);
      finish();
    } else if (ev.kind === "error") {
      run.error = ev.error || "error";
      note("error: " + run.error);
      finish("error");
    } else if (ev.kind === "approval") {
      openApproval({ tool: ev.tool || "tool", args: ev.args || {}, onDecision: (d) => { if (d === "deny") api.stop(); } });
    }
  };

  const start = (goal, resumeId) => {
    const g = str(goal).trim();
    if (!g) return ok(() => showToast("Type a goal first.", { kind: "err" }));
    const model = modelOf(store);
    if (!model) return ok(() => showToast("Pick a model first.", { kind: "err" }));
    lastGoal = g;
    if (resumeId) lastSession = str(resumeId);
    const box = byId("composer");
    if (box && box.value.trim() === g) box.value = "";
    const block = el("section", "tl-run", null, conv);
    const head = el("div", "tl-head", null, block);
    const led = el("span", "tl-led running", null, head);
    led.setAttribute("role", "status");
    el("span", "tl-goal", g.slice(0, 140), head);
    const stop = el("span", "tl-stop mono mut", "", head);
    stop.hidden = true;
    const acts = el("span", "tl-actions", null, head);
    const mkBtn = (label, fn) => {
      const b = el("button", "tl-btn", label, acts);
      b.type = "button";
      b.hidden = true;
      b.onclick = fn;
      return b;
    };
    const ctrl = new AbortController();
    run = { block, list: el("div", "tl-rows", null, block), led, stop, rerun: null, resume: null, steps: 0, maxSteps, t0: performance.now(), rows: [], openRow: null, error: "", aborted: false, sessionId: "", tick: 0, aborter: ctrl };
    run.rerun = mkBtn("Re-run", () => api.rerun());
    run.resume = mkBtn("Resume", () => api.resume());
    tStart();
    tStep(0);
    buttons(true);
    setS({ running: true, steps: 0 });
    run.tick = setInterval(() => {
      if (!run) return;
      const now = performance.now();
      for (const q of run.rows) {
        if (q.open && q.timeout > 0) q.fill.style.width = Math.max(2, Math.round(100 * barFrac(now - q.t0, q.timeout))) + "%";
      }
    }, 250);
    const payload = { goal: g, model, max_steps: maxSteps };
    if (resumeId && str(resumeId).trim()) payload.resume_id = str(resumeId).trim();
    ok(() => apiFetch("/api/agent", {
      method: "POST", body: payload, signal: ctrl.signal,
      onEvent: (p) => { if (p && typeof p === "object") onEv(parseAgentEvent(p)); },
    }).then(() => {
      if (run) finish();
    }).catch((e) => {
      if (!run) return;
      if (run.aborted || ctrl.signal.aborted) { finish(); return; }
      let msg = (e && e.message) || "Network error";
      try {
        const j = JSON.parse(msg);
        if (j && typeof j.error === "string" && j.error) msg = j.error;
      } catch { /* not json */ }
      run.error = msg.slice(0, 300);
      note("error: " + run.error);
      finish("error");
    }));
  };

  const api = {
    send(text) {
      if (run) return;
      start(typeof text === "string" && text ? text : (byId("composer") || {}).value || "", "");
    },
    stop() {
      if (!run) return;
      run.aborted = true;
      try { run.aborter.abort(); } catch { /* ignore */ }
    },
    rerun() {
      if (run || !lastGoal) return;
      start(lastGoal, "");
    },
    resume() {
      if (run || !lastSession) return;
      start(lastGoal || ((byId("composer") || {}).value || ""), lastSession);
    },
    active() {
      return !!run;
    },
  };
  return api;
}
