const reads = [];
const writes = [];
let rafId = 0;
let running = false;

function hasFrame() {
  return typeof requestAnimationFrame !== "undefined";
}

function tick() {
  const rs = reads.splice(0, reads.length);
  for (const fn of rs) {
    try { fn(); } catch { /* keep loop alive */ }
  }
  const ws = writes.splice(0, writes.length);
  for (const fn of ws) {
    try { fn(); } catch { /* keep loop alive */ }
  }
  if (reads.length || writes.length) {
    if (hasFrame()) rafId = requestAnimationFrame(tick);
    else rafId = setTimeout(tick, 16);
  } else {
    running = false;
    rafId = 0;
  }
}

function kick() {
  if (running) return;
  if (typeof document !== "undefined" && document.hidden) return;
  running = true;
  if (hasFrame()) rafId = requestAnimationFrame(tick);
  else rafId = setTimeout(tick, 16);
}

export function onRead(fn) {
  reads.push(fn);
  kick();
}

export function onWrite(fn) {
  writes.push(fn);
  kick();
}

export function initFrame() {
  if (typeof document === "undefined") return;
  const mark = (h) => { try { document.documentElement.dataset.th = h ? "1" : "0"; } catch {} };
  mark(document.hidden);
  document.addEventListener("visibilitychange", () => {
    mark(document.hidden);
    if (!document.hidden && (reads.length || writes.length)) kick();
  });
}
