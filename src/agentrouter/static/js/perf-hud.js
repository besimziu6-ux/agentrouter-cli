let hud = null;
let visible = false;
let frames = 0;
let lastT = 0;
let lastFrameMs = 0;
let longTasks = 0;
let streamAt = 0;

function qs() {
  try {
    return typeof location !== "undefined" ? location.search : "";
  } catch {
    return "";
  }
}

function el(tag, css) {
  const d = document.createElement(tag);
  d.setAttribute("style", css);
  return d;
}

function refreshHud(box) {
  const nodes = document.getElementsByTagName("*").length;
  const lag = streamAt ? Math.round(performance.now() - streamAt) : 0;
  box.textContent =
    "fps " + frames + " | frame " + lastFrameMs.toFixed(1) + "ms" +
    " | long " + longTasks + " | dom " + nodes + " | lag " + lag + "ms";
}

export function noteStream() {
  try {
    if (typeof performance !== "undefined") streamAt = performance.now();
  } catch { /* ignore */ }
}

export function initPerfHUD() {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  try {
    if (typeof PerformanceObserver !== "undefined") {
      const ob = new PerformanceObserver((list) => {
        longTasks += list.getEntries().length;
      });
      try { ob.observe({ entryTypes: ["longtask"] }); } catch { /* unsupported */ }
    }
  } catch { /* ignore */ }
  const show = () => {
    if (hud) {
      visible = !visible;
      hud.style.display = visible ? "block" : "none";
      return;
    }
    hud = el("div", "position:fixed;left:8px;bottom:8px;z-index:99;background:#111827;color:#f9fafb;font:12px monospace;padding:6px 8px;border-radius:8px;opacity:.92");
    hud.id = "perfHud";
    document.body.appendChild(hud);
    visible = true;
    const loop = (t) => {
      if (!lastT) lastT = t;
      const dt = t - lastT;
      lastT = t;
      lastFrameMs = lastFrameMs * 0.9 + dt * 0.1;
      frames = dt > 0 ? Math.round(1000 / dt) : 0;
      if (visible && hud) refreshHud(hud);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
    setInterval(() => { if (visible && hud) refreshHud(hud); }, 500);
  };
  const auto = qs().indexOf("perf=1") >= 0;
  if (auto) show();
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && (e.key === "P" || e.key === "p")) {
      e.preventDefault();
      show();
    }
  });
  try {
    window.__arPerfShow = show;
    window.__arNoteStream = noteStream;
  } catch { /* ignore */ }
}
