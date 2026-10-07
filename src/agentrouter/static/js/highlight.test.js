import { test } from "node:test";
import assert from "node:assert/strict";
import { highlight, normLang } from "./highlight.js";

function kinds(toks) {
  return toks.map((t) => t.c || "plain");
}

test("keywords flagged per language", () => {
  const js = highlight("const x = function() { return true; }", "js");
  const kw = js.filter((t) => t.c === "kw").map((t) => t.t);
  assert.ok(kw.includes("const") && kw.includes("function") && kw.includes("return"), JSON.stringify(js));
  const py = highlight("def f():\n    return None # done", "python");
  assert.ok(py.some((t) => t.t === "def" && t.c === "kw") || py.some((t) => t.t === "return" && t.c === "kw"));
  assert.ok(py.some((t) => t.c === "com" && t.t.includes("# done")), JSON.stringify(py));
  const sh = highlight("if [ -n \"$x\" ]; then echo hi; fi # c", "bash");
  assert.ok(sh.some((t) => t.c === "kw" && t.t === "if"));
  const rs = highlight("fn main() { let mut x = 0; }", "rust");
  assert.ok(rs.some((t) => t.c === "kw" && t.t === "fn"));
  const js2 = highlight("const s = \"hi // not comment\"; // real", "ts");
  assert.ok(js2.some((t) => t.c === "str" && t.t.includes("// not comment")), JSON.stringify(js2));
  assert.ok(js2.some((t) => t.c === "com" && t.t.includes("// real")));
  const num = highlight("x = 42", "c");
  assert.ok(num.some((t) => t.c === "num" && t.t === "42"));
});

test("malformed input never throws", () => {
  for (const [code, lang] of [["\"unterminated", "js"], ["/* never closed", "css"], ["'\\", "python"], ["", "js"], [null, "js"], ["<div", "html"], ["<!--x", "html"], ["`tick", "js"], ["a".repeat(5000), "rust"]]) {
    const toks = highlight(code, lang);
    assert.ok(Array.isArray(toks));
    assert.strictEqual(toks.map((t) => t.t).join(""), String(code == null ? "" : code));
  }
  assert.strictEqual(normLang("TypeScript"), "ts");
  assert.strictEqual(normLang("nope"), "");
  assert.deepStrictEqual(highlight("hello world", "nope").map((t) => t.c), [""]);
});
