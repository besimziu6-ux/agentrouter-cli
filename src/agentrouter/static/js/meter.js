export function createMeterState() {
  let smooth = 0;
  let peak = 0;
  let peakAt = 0;
  let lastT = 0;
  let lastN = 0;
  const decay = (t) => {
    if (lastT && t - lastT > 500) {
      smooth *= Math.exp(-((t - lastT) / 1000) * 3);
      if (smooth < 0.05) smooth = 0;
      lastT = t;
      lastN = 0;
    }
    if (t - peakAt > 3000) peak = smooth;
  };
  return {
    push(n, now) {
      const t = typeof now === "number" ? now : Date.now();
      n = typeof n === "number" && n > 0 ? n : 0;
      if (!lastT) { lastT = t; lastN = n; return; }
      const dt = (t - lastT) / 1000;
      if (dt <= 0) { lastN += n; return; }
      smooth += ((lastN + n) / dt - smooth) * (1 - Math.exp(-dt * 4));
      if (smooth > peak || t - peakAt > 3000) { peak = smooth; peakAt = t; }
      lastT = t;
      lastN = 0;
    },
    tick(now) {
      const t = typeof now === "number" ? now : Date.now();
      decay(t);
      return { rate: smooth, peak };
    },
    get rate() { return smooth; },
    get peakRate() { return peak; },
    reset() { smooth = 0; peak = 0; peakAt = 0; lastT = 0; lastN = 0; },
  };
}

export function formatRate(r) {
  const v = typeof r === "number" && r >= 0 ? r : 0;
  if (v < 9.95) return v.toFixed(1);
  if (v < 999.5) return String(Math.round(v));
  return (v / 1000).toFixed(1) + "k";
}

export function initMeter(canvas, textEl) {
  const state = createMeterState();
  const pushOnly = { state, push: (n) => state.push(n, Date.now()), stop: () => {} };
  if (typeof document === "undefined" || !canvas) return pushOnly;
  const ok = (fn) => { try { return fn(); } catch { return undefined; } };
  const W = 56;
  const H = 14;
  ok(() => {
    canvas.width = W * 2;
    canvas.height = H * 2;
    canvas.setAttribute("aria-hidden", "true");
  });
  let visible = true;
  let raf = 0;
  const hist = new Array(28).fill(0);
  const draw = () => {
    raf = 0;
    if (!visible || document.hidden) return;
    const snap = state.tick(Date.now());
    hist.push(snap.rate);
    if (hist.length > 28) hist.shift();
    ok(() => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const px = typeof devicePixelRatio === "number" && devicePixelRatio > 0 ? devicePixelRatio : 1;
      ctx.setTransform(px, 0, 0, px, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const max = Math.max(8, snap.peak, ...hist);
      ctx.fillStyle = "#5b8cff";
      for (let i = 0; i < hist.length; i++) {
        const h = Math.max(1, Math.round((hist[i] / max) * H));
        ctx.fillRect(i * 2, H - h, 1, h);
      }
      ctx.fillStyle = "#34d399";
      ctx.fillRect(0, H - Math.round((snap.peak / max) * H), W, 1);
    });
    ok(() => {
      if (!textEl) return;
      const label = formatRate(snap.rate) + " tok/s";
      if (textEl.textContent !== label) textEl.textContent = label;
      textEl.setAttribute("aria-label", label + ", peak " + formatRate(snap.peak));
    });
  };
  const api = {
    state,
    push(n, now) {
      state.push(typeof n === "number" ? n : 1, typeof now === "number" ? now : Date.now());
      if (raf || !visible) return;
      raf = typeof requestAnimationFrame !== "undefined" ? requestAnimationFrame(draw) : setTimeout(draw, 100);
    },
    stop() {
      ok(() => (typeof cancelAnimationFrame !== "undefined" ? cancelAnimationFrame(raf) : clearTimeout(raf)));
      raf = 0;
    },
  };
  ok(() => {
    if (typeof IntersectionObserver !== "undefined") {
      new IntersectionObserver((es) => {
        for (const e of es) visible = !!e.isIntersecting;
        if (visible) api.push(0);
      }).observe(canvas);
    }
    document.addEventListener("visibilitychange", () => { if (!document.hidden && visible) api.push(0); });
  });
  return api;
}
