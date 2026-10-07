export function spring(from, to, opts = {}) {
  const stiffness = typeof opts.stiffness === "number" ? opts.stiffness : 170;
  const damping = typeof opts.damping === "number" ? opts.damping : 26;
  const mass = typeof opts.mass === "number" && opts.mass > 0 ? opts.mass : 1;
  let x = from;
  let v = typeof opts.velocity === "number" ? opts.velocity : 0;
  let target = to;
  return {
    get value() { return x; },
    get velocity() { return v; },
    get target() { return target; },
    setTarget(t) { target = t; },
    step(dt) {
      const d = dt <= 0 ? 0.0001 : dt > 0.064 ? 0.064 : dt;
      const f = -stiffness * (x - target) - damping * v;
      v += (f / mass) * d;
      x += v * d;
      return x;
    },
    settled(eps) {
      const e = typeof eps === "number" ? eps : 0.001;
      return Math.abs(x - target) < e && Math.abs(v) < e;
    },
  };
}

export function motionOK() {
  if (typeof document === "undefined") return true;
  const m = document.documentElement.getAttribute("data-motion");
  if (m === "off" || m === "reduced") return false;
  if (typeof matchMedia !== "undefined") {
    try {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    } catch { /* ignore */ }
  }
  return true;
}

function elAdd(el, cls) {
  if (el && el.classList) el.classList.add(cls);
}

export function reveal(elm) {
  if (!elm) return;
  if (!motionOK()) {
    elAdd(elm, "in");
    return;
  }
  elAdd(elm, "reveal");
  const show = () => elAdd(elm, "in");
  if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(() => requestAnimationFrame(show));
  else show();
}

export function setCollapse(wrap, open) {
  if (!wrap || !wrap.classList) return;
  if (!motionOK()) {
    wrap.classList.toggle("open", !!open);
    wrap.style.display = open ? "" : "none";
    return;
  }
  if (!open && wrap.style) wrap.style.display = "";
  wrap.classList.toggle("open", !!open);
}

export function shake(elm) {
  if (!elm || !elm.classList) return;
  if (!motionOK()) return;
  elm.classList.remove("shake");
  void (elm.offsetWidth || 0);
  elm.classList.add("shake");
  const done = () => elm.classList.remove("shake");
  elm.addEventListener("animationend", done, { once: true });
  setTimeout(done, 500);
}

export function crossfade(oldEl, newEl) {
  if (oldEl && oldEl.style) oldEl.style.opacity = "0";
  if (newEl && newEl.style) {
    newEl.style.opacity = motionOK() ? "0" : "1";
    const show = () => { newEl.style.transition = "opacity 200ms"; newEl.style.opacity = "1"; };
    if (motionOK() && typeof requestAnimationFrame !== "undefined") requestAnimationFrame(() => requestAnimationFrame(show));
    else show();
  }
}

export function flip(measure, mutate, animate) {
  const first = measure();
  mutate();
  const last = measure();
  if (typeof animate === "function") animate(first, last);
  return { first, last };
}

export function odometer(elm, from, to) {
  if (!elm) return;
  if (!motionOK()) {
    elm.textContent = String(to);
    return;
  }
  const s = spring(from, to, { stiffness: 120, damping: 20 });
  let last = from;
  const stepFn = () => {
    s.step(1 / 60);
    const v = Math.round(s.value);
    if (v !== last) {
      last = v;
      elm.textContent = String(v);
    }
    if (!s.settled(0.5)) {
      if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(stepFn);
      else setTimeout(stepFn, 16);
    } else {
      elm.textContent = String(to);
    }
  };
  stepFn();
}

export function pumpPacer(pacer, render) {
  if (!pacer || typeof render !== "function") return;
  const tickFn = () => {
    const chunk = pacer.drain();
    if (chunk) render(chunk);
    if (pacer.size > 0) {
      if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(tickFn);
      else setTimeout(tickFn, 16);
    }
  };
  tickFn();
}
