export function createPacer(opts = {}) {
  const budget = typeof opts.charsPerFrame === "number" ? opts.charsPerFrame : 120;
  const perDrain = typeof opts.budget === "number" ? opts.budget : budget;
  let q = "";
  return {
    push(s) {
      if (typeof s !== "string" || !s) return;
      q += s;
    },
    drain(max) {
      const n = typeof max === "number" ? max : perDrain;
      if (!q || n <= 0) return "";
      const out = q.slice(0, n);
      q = q.slice(out.length);
      return out;
    },
    flush() {
      const out = q;
      q = "";
      return out;
    },
    clear() {
      q = "";
    },
    get size() {
      return q.length;
    },
  };
}
