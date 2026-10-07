const SETS = {};
function addSet(names, words) {
  const s = new Set(words);
  for (const n of names) SETS[n] = s;
}
addSet(["js", "ts"], ["await", "async", "break", "case", "catch", "class", "const", "continue", "delete", "else", "export", "extends", "false", "finally", "for", "from", "function", "if", "import", "in", "let", "new", "null", "return", "super", "this", "throw", "true", "try", "typeof", "undefined", "var", "void", "while", "yield"]);
addSet(["py", "python"], ["False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"]);
addSet(["sh", "bash", "shell", "zsh"], ["case", "do", "done", "elif", "else", "esac", "fi", "for", "function", "if", "in", "select", "then", "until", "while", "echo", "exit", "export", "local", "return", "set", "source"]);
addSet(["rs", "rust"], ["as", "async", "await", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self", "static", "struct", "super", "trait", "true", "type", "unsafe", "use", "where", "while"]);
addSet(["c", "h", "cpp", "hpp", "cc"], ["auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern", "false", "float", "for", "goto", "if", "inline", "int", "long", "register", "return", "short", "signed", "sizeof", "static", "struct", "switch", "true", "typedef", "union", "unsigned", "void", "volatile", "while", "class", "namespace", "new", "private", "public", "template", "typename", "using", "virtual"]);
addSet(["css"], ["color", "background", "border", "margin", "padding", "display", "position", "width", "height", "font", "grid", "flex"]);
addSet(["json"], ["true", "false", "null"]);

function isWord(ch) {
  return !!ch && /[A-Za-z0-9_$]/.test(ch);
}

export function normLang(lang) {
  const l = String(lang == null ? "" : lang).trim().toLowerCase();
  if (l === "html" || l === "xml" || l === "svg") return "html";
  if (l === "javascript" || l === "jsx") return "js";
  if (l === "typescript" || l === "tsx") return "ts";
  return SETS[l] ? l : "";
}

export function highlight(code, lang) {
  const s = String(code == null ? "" : code);
  const key = normLang(lang);
  const out = [];
  let plain = "";
  const push = (t, c) => {
    if (!t) return;
    if (!c) { plain += t; return; }
    if (plain) { out.push({ t: plain, c: "" }); plain = ""; }
    out.push({ t, c });
  };
  const n = s.length;
  let i = 0;
  const kws = key && key !== "html" ? SETS[key] : null;
  const hashComment = key === "py" || key === "python" || key === "sh" || key === "bash" || key === "shell" || key === "zsh";
  const cStyle = !hashComment && key !== "html" && key !== "";
  const tickStr = key === "js" || key === "ts";
  const eol = (p) => {
    const e = s.indexOf("\n", p);
    return e < 0 ? n : e;
  };
  while (i < n) {
    const c = s[i];
    const two = s.slice(i, i + 2);
    if (key === "html" && s.slice(i, i + 4) === "<!--") {
      const e = s.indexOf("-->", i + 4);
      push(s.slice(i, e < 0 ? n : e + 3), "com");
      i = e < 0 ? n : e + 3;
      continue;
    }
    if (cStyle && two === "/*") {
      const e = s.indexOf("*/", i + 2);
      push(s.slice(i, e < 0 ? n : e + 2), "com");
      i = e < 0 ? n : e + 2;
      continue;
    }
    if ((hashComment && c === "#") || (!hashComment && key !== "html" && key !== "" && two === "//")) {
      const e = eol(i);
      push(s.slice(i, e), "com");
      i = e;
      continue;
    }
    if (c === '"' || c === "'" || (c === "`" && tickStr)) {
      let j = i + 1;
      let closed = false;
      while (j < n) {
        const d = s[j];
        if (d === "\\") { j += 2; continue; }
        if (d === "\n" && c !== "`") break;
        if (d === c) { closed = true; j++; break; }
        j++;
      }
      if (closed) {
        push(s.slice(i, j), "str");
        i = j;
      } else if (c === "`") {
        plain += c;
        i++;
      } else {
        const e = eol(i);
        push(s.slice(i, e), "str");
        i = e;
      }
      continue;
    }
    if (key === "html" && c === "<" && /[A-Za-z\/!]/.test(s[i + 1] || "")) {
      let j = i + 1;
      while (j < n && s[j] !== ">") j++;
      push(s.slice(i, j < n ? j + 1 : n), "kw");
      i = j < n ? j + 1 : n;
      continue;
    }
    if (c >= "0" && c <= "9" && !isWord(s[i - 1] || "")) {
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_.]/.test(s[j])) j++;
      push(s.slice(i, j), "num");
      i = j;
      continue;
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_$]/.test(s[j])) j++;
      const w = s.slice(i, j);
      push(w, kws && kws.has(w) ? "kw" : "");
      i = j;
      continue;
    }
    plain += c;
    i++;
  }
  if (plain) out.push({ t: plain, c: "" });
  return out;
}

export function applyHighlight(codeEl, code, lang) {
  if (!codeEl) return;
  let doc = null;
  try {
    if (typeof document !== "undefined" && document.createElement) doc = document;
  } catch { doc = null; }
  const toks = highlight(code, lang);
  try {
    codeEl.textContent = "";
    if (codeEl.firstChild) while (codeEl.firstChild) codeEl.removeChild(codeEl.firstChild);
  } catch { /* ignore */ }
  for (const t of toks) {
    try {
      if (!t.c || !doc) {
        if (doc) codeEl.appendChild(doc.createTextNode(t.t));
        else codeEl.textContent = (codeEl.textContent || "") + t.t;
      } else {
        const sp = doc.createElement("span");
        sp.className = "hl-" + t.c;
        sp.textContent = t.t;
        codeEl.appendChild(sp);
      }
    } catch { /* keep going */ }
  }
}
