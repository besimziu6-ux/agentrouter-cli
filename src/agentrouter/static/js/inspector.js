export function showDetail(title, node) {
  if (typeof document === "undefined") return false;
  try {
    const panel = document.getElementById("inspector");
    if (!panel) return false;
    let inner = panel.querySelector(".insp-inner");
    if (!inner) {
      inner = document.createElement("div");
      inner.className = "insp-inner";
      panel.appendChild(inner);
    }
    inner.textContent = "";
    const h = document.createElement("h3");
    h.textContent = String(title == null ? "Detail" : title).slice(0, 120);
    inner.appendChild(h);
    if (node) inner.appendChild(node);
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    const t = document.getElementById("inspectorToggle");
    if (t) {
      t.setAttribute("aria-expanded", "true");
      t.textContent = "Hide panel";
    }
    return true;
  } catch {
    return false;
  }
}

export function initInspector(opts) {
  if (typeof document === "undefined") return () => {};
  opts = opts || {};
  const store = opts.store || null;
  const set = (p) => { try { if (store && typeof store.set === "function") store.set(p); } catch { /* ignore */ } };
  const get = (k, d) => {
    try { if (store && typeof store.get === "function") { const v = store.get(k); return v == null ? d : v; } } catch { /* ignore */ }
    return d;
  };

  const panel = document.getElementById("inspector");
  if (!panel) return () => {};
  let open = get("inspectorOpen", true) !== false;

  const paint = (animate) => {
    try {
      const mobile = window.matchMedia("(max-width: 900px)").matches;
      panel.classList.toggle("open", !!open);
      panel.classList.toggle("sheet", mobile && !!open);
      panel.setAttribute("aria-hidden", open ? "false" : "true");
      if (!mobile) {
        if (animate === false) {
          panel.style.transition = "none";
          panel.style.display = open ? "" : "none";
          void panel.offsetWidth;
          panel.style.transition = "";
        } else {
          panel.style.display = open ? "" : "none";
        }
      } else {
        panel.style.display = "";
      }
      const t = document.getElementById("inspectorToggle");
      if (t) {
        t.setAttribute("aria-expanded", open ? "true" : "false");
        t.textContent = open ? "Hide panel" : "Show panel";
      }
    } catch { /* ignore */ }
    set({ inspectorOpen: !!open });
  };

  const toggle = async (next) => {
    open = typeof next === "boolean" ? next : !open;
    try {
      if (window.matchMedia("(max-width: 900px)").matches && open) {
        const mod = await import("./dialog.js");
        mod.openDialog(panel, { onClose: () => { open = false; paint(true); } });
      }
    } catch { /* ignore */ }
    paint(true);
    try { if (typeof opts.onToggle === "function") opts.onToggle(open); } catch { /* ignore */ }
  };

  try {
    const t = document.getElementById("inspectorToggle");
    if (t) t.addEventListener("click", () => toggle());
    window.addEventListener("resize", () => paint(false));
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) paint(false);
    });
  } catch { /* ignore */ }

  paint(false);
  return toggle;
}
