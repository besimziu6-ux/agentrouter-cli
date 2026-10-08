export function clampFontScale(n) {
  const v = typeof n === "number" ? n : parseFloat(n);
  if (!isFinite(v)) return 100;
  if (v < 85) return 85;
  if (v > 130) return 130;
  return Math.round(v);
}

export function resolveTheme(stored, prefersLight) {
  if (stored === "light" || stored === "dark") return stored;
  if (stored === "os" || stored === "system" || stored == null || stored === "") {
    if (stored === "os" || stored === "system" || !stored) {
      if (typeof prefersLight === "boolean") return prefersLight ? "light" : "dark";
      return "light";
    }
  }
  return "light";
}

export function resolveMotion(stored, prefersReduced) {
  if (stored === "full" || stored === "reduced" || stored === "off") return stored;
  if (prefersReduced) return "reduced";
  return "full";
}

export function resolveDensity(stored) {
  if (stored === "compact" || stored === "comfortable") return stored;
  return "comfortable";
}

function readLS(key) {
  try {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLS(key, val) {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(key, val);
  } catch { /* private mode */ }
}

function prefersReducedMotion() {
  try {
    if (typeof matchMedia === "undefined") return false;
    return matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

function prefersLightScheme() {
  try {
    if (typeof matchMedia === "undefined") return false;
    return matchMedia("(prefers-color-scheme: light)").matches;
  } catch {
    return false;
  }
}

export function loadSettings() {
  const t = readLS("ar-theme");
  const m = readLS("ar-motion");
  const d = readLS("ar-density");
  const f = readLS("ar-font-scale");
  return {
    theme: t || "dark",
    motion: m || "",
    density: d || "comfortable",
    fontScale: f == null || f === "" ? 100 : clampFontScale(parseFloat(f)),
  };
}

export function effectiveSettings(raw) {
  const r = raw || {};
  return {
    theme: resolveTheme(r.theme, prefersLightScheme()),
    motion: resolveMotion(r.motion || "", prefersReducedMotion()),
    density: resolveDensity(r.density),
    fontScale: clampFontScale(r.fontScale == null ? 100 : r.fontScale),
  };
}

export function applySettings(raw) {
  const eff = effectiveSettings(raw);
  if (typeof document !== "undefined") {
    try {
      const root = document.documentElement;
      root.setAttribute("data-theme", eff.theme);
      root.setAttribute("data-motion", eff.motion);
      root.setAttribute("data-density", eff.density);
      root.style.fontSize = eff.fontScale === 100 ? "" : (16 * eff.fontScale / 100) + "px";
    } catch { /* never break paint */ }
  }
  return eff;
}

export function saveSettings(raw) {
  const r = raw || {};
  if (r.theme !== undefined) writeLS("ar-theme", String(r.theme));
  if (r.motion !== undefined) writeLS("ar-motion", String(r.motion));
  if (r.density !== undefined) writeLS("ar-density", String(r.density));
  if (r.fontScale !== undefined) writeLS("ar-font-scale", String(clampFontScale(r.fontScale)));
}

export function initSettings(store) {
  const raw = loadSettings();
  const eff = applySettings(raw);
  if (store && typeof store.set === "function") {
    try { store.set({ theme: eff.theme, motion: eff.motion, density: eff.density, fontScale: eff.fontScale }); } catch { /* ignore */ }
  }
  return eff;
}

export function setTheme(name, store) {
  const v = name === "light" || name === "dark" || name === "os" ? name : "dark";
  writeLS("ar-theme", v);
  const eff = applySettings({ ...loadSettings(), theme: v });
  if (store && typeof store.set === "function") {
    try { store.set({ theme: eff.theme }); } catch { /* ignore */ }
  }
  return eff.theme;
}

export function setMotion(name, store) {
  const v = name === "full" || name === "reduced" || name === "off" ? name : "full";
  writeLS("ar-motion", v);
  const eff = applySettings({ ...loadSettings(), motion: v });
  if (store && typeof store.set === "function") {
    try { store.set({ motion: eff.motion }); } catch { /* ignore */ }
  }
  return eff.motion;
}

export function setDensity(name, store) {
  const v = resolveDensity(name);
  writeLS("ar-density", v);
  applySettings({ ...loadSettings(), density: v });
  if (store && typeof store.set === "function") {
    try { store.set({ density: v }); } catch { /* ignore */ }
  }
  return v;
}

export function setFontScale(n, store) {
  const v = clampFontScale(n);
  writeLS("ar-font-scale", String(v));
  applySettings({ ...loadSettings(), fontScale: v });
  if (store && typeof store.set === "function") {
    try { store.set({ fontScale: v }); } catch { /* ignore */ }
  }
  return v;
}

export function initSettingsPanel(store) {
  if (typeof document === "undefined") return () => {};
  try {
    const inner = document.querySelector("#inspector .insp-inner");
    if (!inner || inner.querySelector("[data-settings-panel]")) return () => {};
    const sec = document.createElement("section");
    sec.setAttribute("data-settings-panel", "1");
    sec.setAttribute("aria-label", "Settings");
    const h = document.createElement("h4");
    h.textContent = "Settings";
    sec.appendChild(h);
    const raw = loadSettings();
    const sel = (key, cur, optsList, fn) => {
      const lab = document.createElement("label");
      lab.textContent = key + " ";
      const el = document.createElement("select");
      el.setAttribute("data-setting", key);
      for (const v of optsList) {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = v;
        if (v === cur) o.selected = true;
        el.appendChild(o);
      }
      el.addEventListener("change", () => fn(el.value, store));
      lab.appendChild(el);
      sec.appendChild(lab);
      return el;
    };
    sel("theme", raw.theme || "dark", ["os", "dark", "light"], setTheme);
    sel("motion", raw.motion || "full", ["full", "reduced", "off"], setMotion);
    sel("density", raw.density || "comfortable", ["comfortable", "compact"], setDensity);
    const flab = document.createElement("label");
    flab.textContent = "fontScale ";
    const fr = document.createElement("input");
    fr.type = "range";
    fr.min = "85";
    fr.max = "130";
    fr.step = "5";
    fr.value = String(raw.fontScale || 100);
    fr.setAttribute("data-setting", "fontScale");
    fr.setAttribute("aria-label", "Font size scale");
    fr.addEventListener("change", () => setFontScale(Number(fr.value), store));
    flab.appendChild(fr);
    sec.append(flab);
    inner.appendChild(sec);
  } catch { /* ignore */ }
  return () => {};
}
