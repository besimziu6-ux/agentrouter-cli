import { splitStable, renderFull } from "./markdown.js";
import { applyHighlight } from "./highlight.js";

export function roleLabel(role, model) {
  if (role === "user") return "YOU";
  const m = String(model == null ? "" : model).trim().split(/[/:]/).pop().slice(0, 14).toUpperCase();
  return m || "AI";
}

export function formatTime(ts) {
  try {
    const d = ts instanceof Date ? ts : new Date(typeof ts === "number" ? ts : Date.now());
    const p = (v) => (v < 10 ? "0" + v : String(v));
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  } catch {
    return "";
  }
}

export function shortModel(m) {
  const s = String(m == null ? "" : m);
  return s.length > 40 ? s.slice(0, 39) + "…" : s;
}

function fallbackCopy(text) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  } catch { /* ignore */ }
}

function copyText(text, onOk) {
  const done = () => { try { if (typeof onOk === "function") onOk(); } catch { /* ignore */ } };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => { fallbackCopy(text); done(); });
      return;
    }
  } catch { /* fall through */ }
  fallbackCopy(text);
  done();
}

export function flipSend(fromEl, toEl) {
  if (!fromEl || !toEl || typeof document === "undefined") return;
  try {
    if (document.documentElement.getAttribute("data-motion") !== "full") return;
    const a = fromEl.getBoundingClientRect();
    const b = toEl.getBoundingClientRect();
    if (!a.width && !a.height) return;
    toEl.style.transition = "none";
    toEl.style.transform = "translate(" + (a.left - b.left) + "px," + (a.top - b.top) + "px)";
    toEl.style.opacity = "0.4";
    void toEl.offsetWidth;
    toEl.style.transition = "transform 200ms cubic-bezier(.2,.8,.2,1),opacity 160ms";
    toEl.style.transform = "";
    toEl.style.opacity = "";
    setTimeout(() => {
      try { toEl.style.transition = ""; toEl.style.transform = ""; toEl.style.opacity = ""; } catch { /* ignore */ }
    }, 240);
  } catch { /* ignore */ }
}

function highlightNew(root) {
  try {
    if (!root || typeof root.querySelectorAll !== "function") return;
    for (const c of root.querySelectorAll("code[data-lang]:not([data-hl])")) {
      try {
        applyHighlight(c, c.textContent || "", c.getAttribute("data-lang") || "");
        c.setAttribute("data-hl", "1");
      } catch { /* keep plain */ }
    }
  } catch { /* ignore */ }
}

export function initMessages(opts) {
  opts = opts || {};
  const empty = { addUser: () => null, beginAssistant: () => null, count: () => 0, clear: () => {}, transcript: () => "", lastUserText: () => "" };
  if (typeof document === "undefined") return empty;
  const conv = opts.conv || document.getElementById("conv");
  const ok = (fn) => { try { return fn(); } catch { return undefined; } };
  let announcer = opts.announcer || document.getElementById("announcer");
  ok(() => {
    if (!announcer) {
      announcer = document.createElement("div");
      announcer.id = "announcer";
      announcer.className = "sr";
      announcer.setAttribute("aria-live", "polite");
      announcer.setAttribute("role", "status");
      document.body.appendChild(announcer);
    }
  });

  const rows = [];
  const onCopy = typeof opts.onCopy === "function" ? opts.onCopy : null;
  const announce = (msg) => ok(() => {
    if (!announcer) return;
    announcer.textContent = "";
    setTimeout(() => ok(() => { announcer.textContent = msg; }), 30);
  });
  const transcript = () => rows.map((r) => (r.role === "user" ? "YOU: " : roleLabel("assistant", r.model) + ": ") + r.text).join("\n\n");

  const mk = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const actBtn = (label, act) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mact";
    b.textContent = label;
    b.setAttribute("data-act", act);
    return b;
  };
  const gutter = (role, model) => {
    const g = mk("div", "gutter");
    g.appendChild(mk("span", "mrole", roleLabel(role, model)));
    const t = mk("time", "mtime", formatTime(Date.now()));
    ok(() => t.setAttribute("datetime", new Date().toISOString()));
    g.appendChild(t);
    return g;
  };
  const metaRow = (kind, getText) => {
    const meta = mk("div", "mmeta");
    const mu = mk("span", "mu");
    meta.appendChild(mu);
    const acts = mk("span", "macts");
    const cp = actBtn("Copy", "copy");
    cp.addEventListener("click", () => copyText(getText(), onCopy));
    acts.appendChild(cp);
    if (kind === "assistant") {
      const rg = actBtn("Regenerate", "regen");
      rg.addEventListener("click", () => ok(() => opts.onRegenerate && opts.onRegenerate()));
      const tr = actBtn("Copy transcript", "transcript");
      tr.addEventListener("click", () => copyText(transcript(), onCopy));
      acts.appendChild(rg);
      acts.appendChild(tr);
    } else {
      const ed = actBtn("Edit", "edit");
      ed.addEventListener("click", () => ok(() => opts.onEdit && opts.onEdit(getText())));
      acts.appendChild(ed);
    }
    meta.appendChild(acts);
    return { meta, mu };
  };

  return {
    count() { return rows.length; },
    transcript,
    clear() {
      rows.length = 0;
      ok(() => { conv.textContent = ""; });
    },
    lastUserText() {
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].role === "user") return rows[i].text;
      }
      return "";
    },
    addUser(text) {
      const body = String(text == null ? "" : text);
      if (!conv) return null;
      const row = mk("div", "msg msg-enter");
      row.setAttribute("data-role", "user");
      row.appendChild(gutter("user"));
      const mb = mk("div", "mbody");
      mb.appendChild(mk("div", "mcontent user-text", body));
      mb.appendChild(metaRow("user", () => body).meta);
      row.appendChild(mb);
      conv.appendChild(row);
      const rec = { role: "user", text: body, el: row };
      rows.push(rec);
      return rec;
    },
    beginAssistant(model) {
      if (!conv) return null;
      const row = mk("div", "msg msg-enter");
      row.setAttribute("data-role", "assistant");
      row.setAttribute("aria-busy", "true");
      row.appendChild(gutter("assistant", model));
      const mb = mk("div", "mbody");

      const wait = mk("div", "wait");
      const waitT = mk("span", "wait-t mono", "waiting 0ms");
      const leds = mk("span", "leds");
      leds.setAttribute("aria-hidden", "true");
      leds.appendChild(mk("i"));
      leds.appendChild(mk("i"));
      leds.appendChild(mk("i"));
      wait.appendChild(waitT);
      wait.appendChild(leds);
      mb.appendChild(wait);

      const reason = mk("div", "reason collapse");
      const inner = mk("div", "collapse-inner");
      const rhead = mk("div", "reason-head");
      rhead.appendChild(mk("span", "reason-t", "Thought"));
      const rbtn = actBtn("Hide", "reason-toggle");
      rhead.appendChild(rbtn);
      const rbody = mk("div", "reason-body");
      inner.appendChild(rhead);
      inner.appendChild(rbody);
      reason.appendChild(inner);
      mb.appendChild(reason);
      let reasonOpen = false;
      rbtn.addEventListener("click", () => {
        reasonOpen = !reasonOpen;
        reason.classList.toggle("open", reasonOpen);
        rbtn.textContent = reasonOpen ? "Hide" : "Show";
      });

      const content = mk("div", "mcontent");
      const stableWrap = mk("div", "mstable");
      const tailWrap = mk("div", "mtail");
      const caret = mk("span", "caret");
      caret.setAttribute("aria-hidden", "true");
      content.appendChild(stableWrap);
      content.appendChild(tailWrap);
      content.appendChild(caret);
      mb.appendChild(content);

      const rec = { role: "assistant", text: "", model: shortModel(model) };
      const mm = metaRow("assistant", () => rec.text);
      mb.appendChild(mm.meta);
      row.appendChild(mb);
      conv.appendChild(row);
      rows.push(rec);

      const t0 = ok(() => performance.now()) || Date.now();
      let tickId = 0;
      let firstAt = 0;
      const loop = () => {
        const ms = Math.max(0, Math.round(((ok(() => performance.now()) || Date.now()) - t0)));
        ok(() => { waitT.textContent = "waiting " + ms + "ms"; });
        if (ms >= 1000) ok(() => leds.classList.add("sweep"));
        if (!firstAt) tickId = ok(() => requestAnimationFrame(loop)) || 0;
      };
      tickId = ok(() => requestAnimationFrame(loop)) || 0;

      let full = "";
      let reasonText = "";
      let usage = null;
      let renderedStable = "";
      let done = false;
      const stopClock = () => ok(() => { if (tickId) cancelAnimationFrame(tickId); tickId = 0; });

      return {
        el: row,
        stream(nextFull) {
          full = String(nextFull == null ? "" : nextFull);
          rec.text = full;
          if (!firstAt) {
            firstAt = Date.now();
            stopClock();
            ok(() => wait.remove());
            if (reasonText) {
              reasonOpen = false;
              reason.classList.remove("open");
              rbtn.textContent = "Show";
            }
          }
          try {
            const sp = splitStable(full);
            if (sp.stableText.length >= renderedStable.length && sp.stableText.startsWith(renderedStable)) {
              const add = sp.stableText.slice(renderedStable.length);
              if (add) {
                for (const n of renderFull(add)) stableWrap.appendChild(n);
                highlightNew(stableWrap);
              }
            } else {
              stableWrap.textContent = "";
              if (sp.stableText) {
                for (const n of renderFull(sp.stableText)) stableWrap.appendChild(n);
                highlightNew(stableWrap);
              }
            }
            renderedStable = sp.stableText;
            tailWrap.textContent = "";
            if (sp.openTail) {
              for (const n of renderFull(sp.openTail)) tailWrap.appendChild(n);
            }
            tailWrap.classList.remove("fresh");
            void tailWrap.offsetWidth;
            tailWrap.classList.add("fresh");
            tailWrap.appendChild(caret);
          } catch { /* keep previous frame */ }
        },
        reason(t) {
          const chunk = String(t == null ? "" : t);
          if (!chunk) return;
          reasonText += chunk;
          ok(() => {
            if (!firstAt && !reasonOpen) {
              reasonOpen = true;
              reason.classList.add("open");
              rbtn.textContent = "Hide";
            }
            if (!firstAt || reasonOpen) rbody.textContent = reasonText;
          });
        },
        usage(u) {
          if (u && typeof u === "object") usage = u;
        },
        done(finalUsage) {
          if (done) return;
          done = true;
          if (finalUsage && typeof finalUsage === "object") usage = finalUsage;
          stopClock();
          ok(() => wait.remove());
          ok(() => {
            content.textContent = "";
            if (full) {
              for (const n of renderFull(full)) content.appendChild(n);
              highlightNew(content);
            }
            caret.classList.add("out");
            content.appendChild(caret);
            setTimeout(() => ok(() => caret.remove()), 350);
          });
          ok(() => {
            reason.classList.remove("open");
            rbtn.textContent = reasonText ? "Show" : "Hide";
          });
          ok(() => {
            const u = usage || {};
            const bits = [];
            if (u.prompt_tokens != null) bits.push(u.prompt_tokens + " in");
            if (u.completion_tokens != null) bits.push(u.completion_tokens + " out");
            if (u.total_tokens != null && u.prompt_tokens == null) bits.push(u.total_tokens + " tok");
            mm.mu.textContent = bits.join(" · ");
          });
          ok(() => row.setAttribute("aria-busy", "false"));
          announce("Response complete" + (usage && usage.completion_tokens != null ? ", " + usage.completion_tokens + " tokens" : full ? ", " + full.length + " characters" : ""));
        },
        fail(title, hint, onRetry) {
          stopClock();
          ok(() => wait.remove());
          ok(() => row.setAttribute("aria-busy", "false"));
          ok(() => {
            const err = mk("div", "merr");
            err.appendChild(mk("div", "merr-t", String(title || "Request failed")));
            if (hint) err.appendChild(mk("div", "merr-h", String(hint)));
            if (typeof onRetry === "function") {
              const rb = mk("button", "mretry", "Retry");
              rb.type = "button";
              rb.addEventListener("click", () => ok(onRetry));
              err.appendChild(rb);
            }
            caret.remove();
            mb.appendChild(err);
          });
          announce(String(title || "Request failed"));
        },
      };
    },
  };
}
