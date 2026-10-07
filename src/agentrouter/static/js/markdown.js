const URL_OK = /^(https?:\/\/|mailto:)/i;

function isWordChar(ch) {
  return !!ch && /[A-Za-z0-9_]/.test(ch);
}

function escText(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escAttr(s) {
  return escText(s).replace(/"/g, "&quot;");
}

class FakeText {
  constructor(t) { this.nodeType = 3; this._t = String(t); }
  get textContent() { return this._t; }
  set textContent(v) { this._t = String(v); }
  get outerHTML() { return escText(this._t); }
}

const VOID_TAGS = { BR: 1, HR: 1, INPUT: 1 };

class FakeEl {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attrs = {};
    this.className = "";
    this._t = null;
  }
  set textContent(v) { this.children = []; this._t = String(v); }
  get textContent() {
    if (this._t != null) return this._t;
    let s = "";
    for (const c of this.children) s += c.textContent;
    return s;
  }
  setAttribute(k, v) { this.attrs[String(k)] = String(v); }
  getAttribute(k) {
    return Object.prototype.hasOwnProperty.call(this.attrs, String(k)) ? this.attrs[String(k)] : null;
  }
  appendChild(c) { this.children.push(c); return c; }
  get outerHTML() {
    const tag = this.tagName.toLowerCase();
    let h = "<" + tag;
    if (this.className) h += ' class="' + escAttr(this.className) + '"';
    const keys = Object.keys(this.attrs);
    for (let i = 0; i < keys.length; i++) h += " " + keys[i] + '="' + escAttr(this.attrs[keys[i]]) + '"';
    if (VOID_TAGS[this.tagName]) return h + ">";
    h += ">";
    if (this._t != null) h += escText(this._t);
    else for (const c of this.children) h += c.outerHTML != null ? c.outerHTML : escText(c.textContent || "");
    return h + "</" + tag + ">";
  }
}

function fakeDoc() {
  return {
    createElement(t) { return new FakeEl(t); },
    createTextNode(t) { return new FakeText(t); },
  };
}

function ensureDoc(explicit) {
  if (explicit && typeof explicit.createElement === "function") return explicit;
  try {
    if (typeof document !== "undefined" && document && typeof document.createElement === "function") return document;
  } catch { /* use fake */ }
  return fakeDoc();
}

export function nodesToHtml(nodes) {
  let h = "";
  for (const n of nodes || []) {
    try { h += n.outerHTML != null ? n.outerHTML : ""; } catch { /* skip */ }
  }
  return h;
}

function addText(parent, d, s) {
  if (!s) return;
  try {
    if (typeof d.createTextNode === "function") {
      parent.appendChild(d.createTextNode(s));
      return;
    }
  } catch { /* fall through */ }
  const e = d.createElement("span");
  e.textContent = s;
  parent.appendChild(e);
}

function el(d, tag, cls) {
  const e = d.createElement(tag);
  if (cls) e.className = cls;
  return e;
}

function linkEl(d, href) {
  const a = el(d, "a");
  a.setAttribute("href", href);
  a.setAttribute("rel", "noopener noreferrer");
  a.setAttribute("target", "_blank");
  return a;
}

export function goodUrl(u) {
  if (typeof u !== "string" || !u) return false;
  const t = u.trim();
  if (!URL_OK.test(t) || /[\s<>"']/.test(t)) return false;
  for (let i = 0; i < t.length; i++) {
    if (t.charCodeAt(i) < 32) return false;
  }
  return true;
}

function fenceMatch(line) {
  const m = /^ {0,3}```(.*)$/.exec(line);
  return m ? m[1] : undefined;
}

export function langOf(info) {
  const m = /^([A-Za-z0-9_+#.\-]+)/.exec(String(info || "").trim());
  return m ? m[1].toLowerCase() : "";
}

export function isOpenFence(text) {
  let open = false;
  for (const ln of String(text == null ? "" : text).split("\n")) {
    if (fenceMatch(ln) !== undefined) open = !open;
  }
  return open;
}

export function splitStable(fullText) {
  const s = String(fullText == null ? "" : fullText);
  if (!s) return { stableText: "", openTail: "" };
  const lines = s.split("\n");
  let open = false;
  let openOff = 0;
  let off = 0;
  for (const ln of lines) {
    if (fenceMatch(ln) !== undefined) {
      if (!open) { open = true; openOff = off; }
      else open = false;
    }
    off += ln.length + 1;
  }
  if (open) return { stableText: s.slice(0, openOff).replace(/[ \t\n]*$/, ""), openTail: s.slice(openOff) };
  const idx = s.lastIndexOf("\n\n");
  if (idx < 0) return { stableText: "", openTail: s };
  return { stableText: s.slice(0, idx).replace(/[ \t\n]*$/, ""), openTail: s.slice(idx + 2).replace(/^\n+/, "") };
}

export function parseStable(fullText, doc) {
  const d = ensureDoc(doc);
  const sp = splitStable(fullText);
  return { stable: sp.stableText ? buildBlocks(sp.stableText, d) : [], openTail: sp.openTail };
}

export function renderFull(text, doc) {
  return buildBlocks(String(text == null ? "" : text), ensureDoc(doc));
}

function parseLinkDest(s, i) {
  let depth = 0;
  let j = i + 1;
  while (j < s.length) {
    const c = s[j];
    if (c === "\\") { j += 2; continue; }
    if (c === "[") depth++;
    else if (c === "]") {
      if (depth === 0) break;
      depth--;
    }
    j++;
  }
  if (s[j] !== "]" || s[j + 1] !== "(") return null;
  const close = s.indexOf(")", j + 2);
  if (close < 0) return null;
  return { text: s.slice(i + 1, j), href: (s.slice(j + 2, close).trim().split(/\s+/)[0] || ""), next: close + 1 };
}

const DOUBLE_TAGS = { "**": "strong", "__": "strong", "~~": "del" };

export function appendInline(parent, text, doc) {
  const d = ensureDoc(doc);
  const s = String(text == null ? "" : text);
  const n = s.length;
  let i = 0;
  let plain = "";
  const flush = () => { if (plain) { addText(parent, d, plain); plain = ""; } };
  const wrap = (tag, inner) => {
    flush();
    const e = el(d, tag);
    appendInline(e, inner, d);
    parent.appendChild(e);
  };
  while (i < n) {
    const c = s[i];
    if (c === "\\" && i + 1 < n) { plain += s[i + 1]; i += 2; continue; }
    if (c === "\n") {
      flush();
      parent.appendChild(el(d, "br"));
      i++;
      continue;
    }
    if (c === "`") {
      let k = 1;
      while (s[i + k] === "`") k++;
      const close = s.indexOf("`".repeat(k), i + k);
      if (close < 0) { plain += c; i++; continue; }
      flush();
      const code = el(d, "code", "md-ic");
      code.textContent = s.slice(i + k, close);
      parent.appendChild(code);
      i = close + k;
      continue;
    }
    const dbl = (c === "*" || c === "_" || c === "~") ? s.slice(i, i + 2) : "";
    if (DOUBLE_TAGS[dbl]) {
      const close = s.indexOf(dbl, i + 2);
      if (close < 0) { plain += c; i++; continue; }
      wrap(DOUBLE_TAGS[dbl], s.slice(i + 2, close));
      i = close + 2;
      continue;
    }
    if (c === "*" || c === "_") {
      let close = -1;
      if (c === "_") {
        const prev = i > 0 ? s[i - 1] : " ";
        const next = i + 1 < n ? s[i + 1] : " ";
        if (!isWordChar(prev) && next !== " " && next !== "\n" && next !== "") {
          for (let j = i + 1; j < n; j++) {
            if (s[j] === "_" && !isWordChar(j + 1 < n ? s[j + 1] : " ")) { close = j; break; }
          }
        }
      } else {
        close = s.indexOf("*", i + 1);
      }
      if (close < 0 || close === i + 1) { plain += c; i++; continue; }
      wrap("em", s.slice(i + 1, close));
      i = close + 1;
      continue;
    }
    if (c === "[") {
      const r = parseLinkDest(s, i);
      if (!r) { plain += c; i++; continue; }
      flush();
      if (goodUrl(r.href)) {
        const a = linkEl(d, r.href.trim());
        appendInline(a, r.text, d);
        parent.appendChild(a);
      } else {
        addText(parent, d, s.slice(i, r.next));
      }
      i = r.next;
      continue;
    }
    if (c === "<") {
      const m = /^<(https?:\/\/[^<>\s]+|mailto:[^<>\s]+)>/.exec(s.slice(i, i + 320));
      if (m && goodUrl(m[1])) {
        flush();
        const a = linkEl(d, m[1]);
        a.textContent = m[1];
        parent.appendChild(a);
        i += m[0].length;
        continue;
      }
      plain += c;
      i++;
      continue;
    }
    plain += c;
    i++;
  }
  flush();
}

function splitRow(line) {
  let t = line.trim();
  if (t[0] === "|") t = t.slice(1);
  if (t[t.length - 1] === "|") t = t.slice(0, -1);
  return t.split("|").map((x) => x.trim());
}

function isDelimRow(line) {
  const cells = splitRow(line);
  if (!cells.length) return false;
  for (const c of cells) {
    if (!/^:?-{1,}:?$/.test(c)) return false;
  }
  return true;
}

function listLine(ln) {
  return /^(\s*)([-*+]|\d{1,9}[.)])(?:\s+(.*))?\s*$/.exec(ln);
}

function blockKind(ln, lines, i) {
  if (/^\s*$/.test(ln)) return "blank";
  if (fenceMatch(ln) !== undefined) return "fence";
  if (/^ {0,3}#{1,6}\s+\S/.test(ln)) return "head";
  if (/^(-{3,}|\*{3,}|_{3,})$/.test(ln.replace(/\s/g, ""))) return "hr";
  if (/^\s*\|/.test(ln) && i + 1 < lines.length && lines[i + 1].includes("|") && isDelimRow(lines[i + 1])) return "table";
  if (/^ {0,3}>\s?/.test(ln)) return "quote";
  if (listLine(ln)) return "list";
  return "para";
}

function readFence(lines, i, out, d) {
  const lang = langOf(fenceMatch(lines[i]));
  const buf = [];
  let j = i + 1;
  let closed = false;
  while (j < lines.length) {
    if (fenceMatch(lines[j]) !== undefined) { closed = true; j++; break; }
    buf.push(lines[j]);
    j++;
  }
  const raw = buf.join("\n");
  const wrap = el(d, "div", "codeblock");
  wrap.setAttribute("data-closed", closed ? "1" : "0");
  const head = el(d, "div", "code-head");
  const lab = el(d, "span", "code-lang");
  lab.textContent = lang || "code";
  const copy = el(d, "button", "code-copy");
  copy.setAttribute("type", "button");
  copy.setAttribute("data-copy", raw);
  copy.textContent = "Copy";
  head.appendChild(lab);
  head.appendChild(copy);
  const pre = el(d, "pre");
  const code = el(d, "code", "md-code" + (lang ? " lang-" + lang : ""));
  if (lang) code.setAttribute("data-lang", lang);
  code.textContent = raw;
  pre.appendChild(code);
  wrap.appendChild(head);
  wrap.appendChild(pre);
  out.push(wrap);
  return j;
}

function readTable(lines, i, out, d) {
  const head = splitRow(lines[i]);
  const table = el(d, "table", "md-table");
  const hr = el(d, "tr");
  for (const c of head) {
    const th = el(d, "th");
    appendInline(th, c, d);
    hr.appendChild(th);
  }
  const thead = el(d, "thead");
  thead.appendChild(hr);
  table.appendChild(thead);
  const tb = el(d, "tbody");
  let j = i + 2;
  while (j < lines.length && lines[j].includes("|") && !/^\s*$/.test(lines[j])) {
    const cells = splitRow(lines[j]);
    const tr = el(d, "tr");
    for (let k = 0; k < head.length; k++) {
      const td = el(d, "td");
      appendInline(td, cells[k] || "", d);
      tr.appendChild(td);
    }
    tb.appendChild(tr);
    j++;
  }
  table.appendChild(tb);
  out.push(table);
  return j;
}

function readQuote(lines, i, out, d) {
  const buf = [];
  let j = i;
  while (j < lines.length && /^ {0,3}>\s?/.test(lines[j])) {
    buf.push(lines[j].replace(/^ {0,3}>\s?/, ""));
    j++;
  }
  const q = el(d, "blockquote", "md-q");
  for (const x of buildBlocks(buf.join("\n"), d)) q.appendChild(x);
  out.push(q);
  return j;
}

function readList(lines, i, out, d) {
  const first = listLine(lines[i]) || [];
  const base = (first[1] || "").length;
  const stack = [];
  const closeTo = (ind) => {
    while (stack.length && stack[stack.length - 1].ind > ind) stack.pop();
  };
  while (i < lines.length) {
    const m = listLine(lines[i]);
    if (!m || m[1].length < base) break;
    const ind = m[1].length;
    const ordered = /\d/.test(m[2][0]);
    closeTo(ind);
    let top = stack[stack.length - 1];
    if (!top || top.ind < ind || top.ordered !== ordered) {
      const list = el(d, ordered ? "ol" : "ul", "md-list");
      if (top && top.ind < ind && top.li) top.li.appendChild(list);
      else out.push(list);
      top = { el: list, ind, ordered, li: null };
      stack.push(top);
    }
    const li = el(d, "li", "md-li");
    const content = m[3] || "";
    const t = /^\[([ xX])\]\s?(.*)$/.exec(content);
    if (t) {
      const box = d.createElement("input");
      box.setAttribute("type", "checkbox");
      box.setAttribute("disabled", "");
      if (t[1] === "x" || t[1] === "X") box.setAttribute("checked", "");
      li.appendChild(box);
      const sp = el(d, "span");
      appendInline(sp, t[2], d);
      li.appendChild(sp);
    } else {
      appendInline(li, content, d);
    }
    top.el.appendChild(li);
    top.li = li;
    i++;
  }
  return i;
}

export function buildBlocks(src, doc) {
  const d = ensureDoc(doc);
  const lines = String(src == null ? "" : src).split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    const kind = blockKind(ln, lines, i);
    if (kind === "blank") { i++; continue; }
    if (kind === "fence") { i = readFence(lines, i, out, d); continue; }
    if (kind === "table") { i = readTable(lines, i, out, d); continue; }
    if (kind === "quote") { i = readQuote(lines, i, out, d); continue; }
    if (kind === "list") { i = readList(lines, i, out, d); continue; }
    if (kind === "head") {
      const h = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/.exec(ln);
      const e = d.createElement("h" + h[1].length);
      e.className = "md-h";
      appendInline(e, h[2], d);
      out.push(e);
      i++;
      continue;
    }
    if (kind === "hr") {
      out.push(el(d, "hr", "md-hr"));
      i++;
      continue;
    }
    const buf = [];
    while (i < lines.length && blockKind(lines[i], lines, i) === "para") {
      buf.push(lines[i]);
      i++;
    }
    const p = el(d, "p", "md-p");
    appendInline(p, buf.join("\n"), d);
    out.push(p);
  }
  return out;
}
