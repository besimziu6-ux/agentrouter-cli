const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC[c] || c);
}

export function splitLines(s) {
  return String(s == null ? "" : s).split(/\r\n|\r|\n/);
}

export function toHunks(rows) {
  if (!Array.isArray(rows) || !rows.length) return [];
  let fa = 0;
  let la = 0;
  let fb = 0;
  let lb = 0;
  for (const r of rows) {
    if (r.a != null) { if (!fa) fa = r.a; la = r.a; }
    if (r.b != null) { if (!fb) fb = r.b; lb = r.b; }
  }
  const ca = fa ? la - fa + 1 : 0;
  const cb = fb ? lb - fb + 1 : 0;
  return [{ head: "@@ -" + (fa || 1) + "," + ca + " +" + (fb || 1) + "," + cb + " @@", rows }];
}

export function diffLines(oldText, newText, ctx) {
  const c = typeof ctx === "number" && ctx >= 0 ? Math.min(8, Math.floor(ctx)) : 3;
  let a = splitLines(oldText);
  let b = splitLines(newText);
  if (!String(oldText == null ? "" : oldText)) a = [];
  if (!String(newText == null ? "" : newText)) b = [];
  if (a.length > 2000) a = a.slice(0, 2000);
  if (b.length > 2000) b = b.slice(0, 2000);
  let s = 0;
  while (s < a.length && s < b.length && a[s] === b[s]) s++;
  let ea = a.length - 1;
  let eb = b.length - 1;
  while (ea >= s && eb >= s && a[ea] === b[eb]) { ea--; eb--; }
  if (s > ea && s > eb) return [];
  const rows = [];
  for (let i = Math.max(0, s - c); i < s; i++) rows.push({ t: " ", s: a[i], a: i + 1, b: i + 1 });
  for (let i = s; i <= ea; i++) rows.push({ t: "-", s: a[i], a: i + 1, b: null });
  for (let i = s; i <= eb; i++) rows.push({ t: "+", s: b[i], a: null, b: i + 1 });
  const post = Math.min(c, Math.min(a.length - 1 - ea, b.length - 1 - eb));
  for (let k = 1; k <= post; k++) rows.push({ t: " ", s: a[ea + k], a: ea + k + 1, b: eb + k + 1 });
  return toHunks(rows);
}

export function renderDiff(oldText, newText) {
  try {
    if (typeof document === "undefined") return null;
    const hunks = diffLines(oldText, newText);
    if (!hunks.length) return null;
    const wrap = document.createElement("div");
    wrap.className = "tl-diff";
    for (const h of hunks) {
      const hd = document.createElement("div");
      hd.className = "tl-hunk";
      const hh = document.createElement("div");
      hh.className = "tl-hunk-h mono";
      hh.textContent = h.head;
      hd.appendChild(hh);
      for (const r of h.rows) {
        const line = document.createElement("div");
        line.className = "tl-l" + (r.t === "+" ? " add" : r.t === "-" ? " del" : " ctx");
        line.textContent = r.t + " " + r.s;
        hd.appendChild(line);
      }
      wrap.appendChild(hd);
    }
    return wrap;
  } catch {
    return null;
  }
}
