let current = null;

function focusables(root) {
  if (!root || typeof root.querySelectorAll !== "function") return [];
  try {
    const els = root.querySelectorAll(
      'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
    );
    const out = [];
    for (const el of els) {
      try {
        if (el.disabled) continue;
        if (el.getAttribute("aria-hidden") === "true") continue;
        out.push(el);
      } catch { /* skip */ }
    }
    return out;
  } catch {
    return [];
  }
}

export function isDialogOpen() {
  return !!current;
}

export function trapTab(root, e) {
  const f = focusables(root);
  if (!f.length) {
    e.preventDefault();
    return;
  }
  const first = f[0];
  const last = f[f.length - 1];
  const active = document.activeElement;
  if (e.shiftKey && (active === first || !root.contains(active))) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (active === last || !root.contains(active))) {
    e.preventDefault();
    first.focus();
  }
}

export function isApprovalEvent(ev) {
  return !!ev && typeof ev === "object" && ev.type === "approval";
}

export function approvalKey(key) {
  if (key === "y" || key === "Y") return "allow";
  if (key === "n" || key === "N") return "deny";
  if (key === "a" || key === "A") return "always";
  return null;
}

function decideApproval(result) {
  const c = current;
  if (!c || !c.approval) return false;
  const cb = c.decide;
  closeDialog();
  try { if (typeof cb === "function") cb(result); } catch { /* ignore */ }
  return true;
}

export function openApproval(opts) {
  if (typeof document === "undefined") return null;
  opts = opts || {};
  const mk = (tag, cls, text, parent) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  };
  let argsText = "";
  try { argsText = JSON.stringify(opts.args == null ? {} : opts.args, null, 2).slice(0, 2000); }
  catch { argsText = String(opts.args); }
  const box = mk("section", "appr");
  box.setAttribute("aria-label", "Approve tool call");
  mk("h3", null, "Approve " + String(opts.tool || "tool") + "?", box);
  mk("pre", "mono appr-args", argsText, box);
  const row = mk("div", "appr-row", null, box);
  const btn = ([label, val, hint]) => {
    const b = mk("button", null, label + " (" + hint + ")", row);
    b.addEventListener("click", () => decideApproval(val));
    return b;
  };
  btn(["Allow", "allow", "Y"]);
  btn(["Deny", "deny", "N"]);
  btn(["Always this run", "always", "A"]);
  (document.getElementById("center") || document.body).appendChild(box);
  const handle = openDialog(box, {
    onClose: () => { try { box.remove(); } catch { /* ignore */ } },
  });
  if (!handle) { try { box.remove(); } catch { /* ignore */ } return null; }
  if (current) {
    current.approval = true;
    current.decide = typeof opts.onDecision === "function" ? opts.onDecision : null;
  }
  return { close: () => decideApproval("deny") };
}

function onKey(e) {
  if (!current) return;
  if (current.approval) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      decideApproval("deny");
      return;
    }
    const tag = e.target && e.target.tagName ? String(e.target.tagName).toLowerCase() : "";
    const r = approvalKey(e.key);
    if (r && tag !== "input" && tag !== "textarea" && tag !== "select") {
      e.preventDefault();
      e.stopPropagation();
      decideApproval(r);
      return;
    }
  }
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    closeDialog();
    return;
  }
  if (e.key === "Tab") {
    try { trapTab(current.node, e); } catch { /* ignore */ }
    return;
  }
}

export function openDialog(node, opts) {
  if (typeof document === "undefined" || !node) return null;
  opts = opts || {};
  closeDialog();
  let prev = null;
  try { prev = document.activeElement; } catch { /* ignore */ }
  try {
    node.classList.add("dlg-open");
    node.setAttribute("aria-hidden", "false");
    if (!node.getAttribute("role")) node.setAttribute("role", "dialog");
    if (!node.getAttribute("aria-modal")) node.setAttribute("aria-modal", "true");
    document.addEventListener("keydown", onKey, true);
    const f = focusables(node);
    if (opts.initialFocus && typeof opts.initialFocus.focus === "function") {
      try { opts.initialFocus.focus(); } catch { /* ignore */ }
    } else if (f.length) {
      try { f[0].focus(); } catch { /* ignore */ }
    } else if (typeof node.focus === "function") {
      try {
        if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "-1");
        node.focus();
      } catch { /* ignore */ }
    }
    current = { node, prev, onClose: opts.onClose || null, returnFocus: opts.returnFocus !== false };
    return { close: closeDialog };
  } catch {
    return null;
  }
}

export function closeDialog() {
  if (!current) return;
  const c = current;
  current = null;
  try { document.removeEventListener("keydown", onKey, true); } catch { /* ignore */ }
  try {
    c.node.classList.remove("dlg-open");
    c.node.setAttribute("aria-hidden", "true");
    if (typeof c.onClose === "function") c.onClose();
    if (c.returnFocus && c.prev && typeof c.prev.focus === "function") {
      try { c.prev.focus({ preventScroll: true }); } catch { try { c.prev.focus(); } catch { /* ignore */ } }
    }
  } catch { /* ignore */ }
}
