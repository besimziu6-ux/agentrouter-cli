export function createSSEParser(onEvent) {
  let buf = "";
  let done = false;
  const emit = (ev) => {
    if (typeof onEvent === "function") {
      try { onEvent(ev); } catch { /* caller handles */ }
    }
  };
  function handleRawEvent(raw) {
    const lines = raw.split("\n");
    let data = "";
    for (let ln of lines) {
      if (ln.endsWith("\r")) ln = ln.slice(0, -1);
      if (!ln) continue;
      if (ln[0] === ":") continue;
      if (ln.startsWith("data:")) data += (data ? "\n" : "") + ln.slice(5).trimStart();
    }
    if (!data) return;
    if (data === "[DONE]") {
      if (!done) {
        done = true;
        emit({ done: true });
      }
      return;
    }
    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }
    if (payload && typeof payload === "object" && typeof payload.error === "string" && payload.error) {
      emit({ error: payload.error });
      return;
    }
    emit(payload);
  }
  return {
    push(chunk) {
      if (done) return;
      const s = typeof chunk === "string" ? chunk : String(chunk == null ? "" : chunk);
      buf += s;
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        handleRawEvent(raw);
        if (done) {
          buf = "";
          return;
        }
      }
    },
    close() {
      if (done) return;
      const tail = buf.trim();
      buf = "";
      if (!tail) return;
      const raw = tail.replace(/^data:\s*/, "");
      if (!raw || raw === "[DONE]") {
        if (raw === "[DONE]" && !done) {
          done = true;
          emit({ done: true });
        }
        return;
      }
      try {
        const payload = JSON.parse(raw);
        if (payload && typeof payload === "object" && typeof payload.error === "string" && payload.error) {
          emit({ error: payload.error });
          return;
        }
        emit(payload);
      } catch { /* ignore partial tail */ }
    },
  };
}

function guiToken() {
  if (typeof document === "undefined") return "";
  try {
    const m = document.querySelector("meta[name=ar-token]");
    const v = m && m.getAttribute("content");
    return typeof v === "string" ? v : "";
  } catch {
    return "";
  }
}

export async function apiFetch(path, opts = {}) {
  const method = opts.method || "GET";
  const headers = { "Content-Type": "application/json" };
  const tok = guiToken();
  if (tok) headers["X-AgentRouter-Token"] = tok;
  if (opts.headers) Object.assign(headers, opts.headers);
  const init = { method, headers, signal: opts.signal };
  if (opts.body !== undefined) init.body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
  const res = await fetch(path, init);
  if (!res.ok) {
    let msg = "HTTP " + res.status;
    try {
      const t = await res.text();
      if (t) msg = t.slice(0, 500);
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  if (typeof opts.onEvent !== "function") return res;
  const parser = createSSEParser(opts.onEvent);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  for (;;) {
    const r = await reader.read();
    if (r.done) break;
    parser.push(dec.decode(r.value, { stream: true }));
  }
  parser.push(dec.decode(new Uint8Array(0)));
  parser.close();
  return res;
}
