import { test } from "node:test";
import assert from "node:assert/strict";
import { diffLines, escapeHtml, renderDiff, splitLines, toHunks } from "./diff.js";

test("escapeHtml escapes markup first", () => {
  assert.strictEqual(escapeHtml("<b>&\"'"), "&lt;b&gt;&amp;&quot;&#39;");
  assert.strictEqual(escapeHtml(null), "");
  assert.strictEqual(escapeHtml(7), "7");
});

test("splitLines handles CRLF and junk", () => {
  assert.deepStrictEqual(splitLines("a\r\nb\rc"), ["a", "b", "c"]);
  assert.deepStrictEqual(splitLines(null), [""]);
  assert.deepStrictEqual(splitLines(5), ["5"]);
});

test("identical texts yield no hunks", () => {
  assert.deepStrictEqual(diffLines("a\nb", "a\nb"), []);
  assert.strictEqual(renderDiff("a\nb", "a\nb"), null);
});

test("single-line change makes one hunk with header", () => {
  const h = diffLines("a\nb\nc", "a\nB\nc");
  assert.strictEqual(h.length, 1);
  assert.match(h[0].head, /^@@ -\d+,\d+ \+\d+,\d+ @@$/);
  const kinds = h[0].rows.map((r) => r.t).join("");
  assert.ok(kinds.includes("-") && kinds.includes("+"));
});

test("insert-only hunk uses zero-count header", () => {
  const h = diffLines("a\nc", "a\nb\nc", 0);
  assert.strictEqual(h.length, 1);
  assert.match(h[0].head, /-1,0/);
});

test("malformed input stays safe", () => {
  assert.ok(Array.isArray(diffLines(null, undefined)));
  assert.ok(Array.isArray(diffLines({}, [])));
  assert.ok(Array.isArray(toHunks(null)));
  assert.ok(Array.isArray(toHunks("nope")));
  assert.strictEqual(renderDiff(null, null), null);
});

test("large inputs stay linear", () => {
  const big = new Array(600).fill("x").join("\n");
  const t0 = Date.now();
  const h = diffLines(big, big + "\ny");
  assert.ok(h.length >= 1);
  assert.ok(Date.now() - t0 < 2000);
});

test("empty side yields clean insert", () => {
  const h = diffLines("", "x\ny");
  assert.strictEqual(h.length, 1);
  assert.match(h[0].head, /-1,0 \+1,2/);
  assert.deepStrictEqual(diffLines("", ""), []);
});
