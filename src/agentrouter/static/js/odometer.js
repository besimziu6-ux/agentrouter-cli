export function isDigit(ch) {
  return typeof ch === "string" && ch.length === 1 && ch >= "0" && ch <= "9";
}

export function toChars(text) {
  return String(text == null ? "" : text).split("");
}

export function rollY(ch) {
  if (!isDigit(ch)) return null;
  const d = ch.charCodeAt(0) - 48;
  return d === 0 ? 0 : -d;
}

function col(doc, ch) {
  const cell = doc.createElement("span");
  cell.className = "odo-c";
  if (!isDigit(ch)) {
    cell.textContent = ch;
    return { cell, reel: null, ch, digit: false };
  }
  const reel = doc.createElement("span");
  reel.className = "odo-r";
  for (let d = 0; d < 10; d++) {
    const s = doc.createElement("span");
    s.className = "odo-d";
    s.textContent = String(d);
    reel.appendChild(s);
  }
  cell.appendChild(reel);
  reel.style.transform = "translateY(" + rollY(ch) + "em)";
  return { cell, reel, ch, digit: true };
}

export function mountOdometer(elm, text) {
  try {
    if (!elm || typeof document === "undefined") return false;
    elm.textContent = "";
    const cols = [];
    for (const ch of toChars(text == null ? "" : text)) {
      const c = col(document, ch);
      cols.push(c);
      elm.appendChild(c.cell);
    }
    elm.__odo = cols;
    return true;
  } catch {
    return false;
  }
}

export function paintOdometer(elm, text) {
  try {
    if (!elm || typeof document === "undefined") return false;
    const want = String(text == null ? "" : text);
    const cols = elm.__odo;
    if (!Array.isArray(cols) || cols.length !== want.length) {
      if (mountOdometer(elm, want)) return true;
      elm.textContent = want;
      return true;
    }
    const chars = toChars(want);
    for (let i = 0; i < chars.length; i++) {
      const c = cols[i];
      const ch = chars[i];
      if (c.ch === ch) continue;
      if (c.digit && isDigit(ch)) {
        c.ch = ch;
        c.reel.style.transform = "translateY(" + rollY(ch) + "em)";
      } else {
        const n = col(document, ch);
        try { elm.replaceChild(n.cell, c.cell); } catch { /* keep */ }
        cols[i] = n;
      }
    }
    return true;
  } catch {
    try { elm.textContent = String(text == null ? "" : text); } catch { /* ignore */ }
    return false;
  }
}
