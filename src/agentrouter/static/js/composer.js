export function shouldSendKey(e) {
  return !!e && e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing;
}

export function isEmptyText(v) {
  return !String(v == null ? "" : v).trim();
}

function clampNum(v, lo, hi, fb) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fb;
}

function docOf(doc) {
  if (doc && typeof doc.getElementById === "function") return doc;
  try {
    return typeof document !== "undefined" ? document : null;
  } catch {
    return null;
  }
}

export function readParams(doc) {
  const d = docOf(doc);
  const out = {};
  if (!d) return out;
  try {
    const sys = d.getElementById("sysPrompt");
    const mt = d.getElementById("maxTokens");
    const tp = d.getElementById("temperature");
    if (sys && sys.value.trim()) out.system = sys.value.trim().slice(0, 8000);
    const n = mt && Math.floor(Number(mt.value));
    if (mt && String(mt.value).trim() && Number.isFinite(n) && n > 0) out.max_tokens = Math.min(128000, n);
    if (tp && String(tp.value).trim() !== "") out.temperature = clampNum(tp.value, 0, 2, 1);
  } catch{}
  return out;
}

function saveParams(p) {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem("ar-chat-params", JSON.stringify(p));
  } catch { /* capped or blocked, ignore */ }
}

export function initComposer(opts) {
  const noop = { send: () => {}, getParams: () => ({}), grow: () => {}, paintSendStop: () => {}, box: null };
  if (typeof document === "undefined") return noop;
  opts = opts || {};
  const ok = (fn) => { try { return fn(); } catch { return undefined; } };
  const box = document.getElementById("composer");
  const row = document.getElementById("composerRow");
  const runBtn = document.getElementById("runBtn");
  const stopBtn = document.getElementById("stopBtn");
  const params = document.getElementById("chatParams");
  if (!box) return noop;

  ok(() => {
    const saved = JSON.parse(localStorage.getItem("ar-chat-params") || "{}") || {};
    const set = (id, v) => {
      const n = document.getElementById(id);
      if (n && v != null && v !== "") n.value = String(v);
    };
    set("sysPrompt", String(saved.system || "").slice(0, 8000));
    set("maxTokens", saved.max_tokens);
    set("temperature", saved.temperature);
    if (saved.open && params) params.open = true;
  });

  let rafId = 0;
  const grow = () => {
    if (rafId) return;
    ok(() => {
      try {
        if (getComputedStyle(box).getPropertyValue("field-sizing").trim() === "content") return;
      } catch { /* measure instead */ }
      const measure = () => {
        rafId = 0;
        ok(() => {
          box.style.height = "auto";
          box.style.height = Math.min(220, Math.max(44, box.scrollHeight)) + "px";
          box.style.overflowY = box.scrollHeight > 220 ? "auto" : "hidden";
        });
      };
      rafId = typeof requestAnimationFrame !== "undefined" ? requestAnimationFrame(measure) : (measure(), 0);
    });
  };

  ok(() => {
    box.addEventListener("input", grow);
    box.addEventListener("focus", () => {
      box.classList.add("focus-ring");
      if (row) row.classList.add("focused");
    });
    box.addEventListener("blur", () => setTimeout(() => ok(() => {
      box.classList.remove("focus-ring");
      if (row) row.classList.remove("focused");
    }), 100));
    box.addEventListener("keydown", (e) => {
      if (shouldSendKey(e)) { e.preventDefault(); doSend(); }
    });
  });

  const shakeEmpty = () => ok(() => {
    box.classList.remove("shake");
    void box.offsetWidth;
    box.classList.add("shake");
    const done = () => box.classList.remove("shake");
    box.addEventListener("animationend", done, { once: true });
    setTimeout(done, 500);
    box.focus();
  });

  const doSend = () => {
    const isRunning = typeof opts.running === "function" ? opts.running() : !!opts.running;
    if (isRunning) {
      ok(() => opts.onStop && opts.onStop());
      return;
    }
    if (isEmptyText(box.value)) { shakeEmpty(); return; }
    ok(() => opts.onSend && opts.onSend(box.value));
  };

  ok(() => {
    if (runBtn) runBtn.addEventListener("click", doSend);
    if (stopBtn) stopBtn.addEventListener("click", () => ok(() => opts.onStop && opts.onStop()));
    const wrap = row || box.parentElement;
    if (wrap) {
      let depth = 0;
      wrap.addEventListener("dragenter", (e) => {
        if (!e.dataTransfer) return;
        depth++;
        wrap.classList.add("drop-hi");
      });
      wrap.addEventListener("dragleave", () => {
        depth = Math.max(0, depth - 1);
        if (!depth) wrap.classList.remove("drop-hi");
      });
      wrap.addEventListener("drop", (e) => {
        depth = 0;
        wrap.classList.remove("drop-hi");
        const f = e.dataTransfer && e.dataTransfer.files;
        if (f && f.length && typeof opts.onDropFile === "function") {
          e.preventDefault();
          opts.onDropFile(f[0]);
        }
      });
    }
    for (const id of ["sysPrompt", "maxTokens", "temperature"]) {
      const n = document.getElementById(id);
      if (n) n.addEventListener("change", () => saveParams(readParams(document)));
    }
    if (params) params.addEventListener("toggle", () => ok(() => {
      const p = readParams(document);
      p.open = !!params.open;
      saveParams(p);
    }));
  });

  grow();
  ok(() => {
    const vv = typeof visualViewport !== "undefined" ? visualViewport : null;
    if (vv) vv.addEventListener("resize", () => {
      try { if (document.activeElement === box) box.scrollIntoView({ block: "nearest" }); } catch {}
    });
  });
  return {
    send: doSend,
    getParams: () => readParams(document),
    grow,
    box,
    paintSendStop: (isRunning) => ok(() => {
      if (runBtn) {
        runBtn.classList.toggle("is-stop", !!isRunning);
        runBtn.setAttribute("aria-label", isRunning ? "Stop" : "Send");
        const lbl = runBtn.querySelector(".send-lbl");
        if (lbl) lbl.textContent = isRunning ? "Stop" : "Send";
      }
      if (stopBtn) stopBtn.hidden = !isRunning;
      if (row) row.classList.toggle("sending", !!isRunning);
    }),
  };
}
