import { test } from "node:test";
import assert from "node:assert/strict";
import { isSafeId, validateTitle, previewText, debounce, swipeDismissed, h } from "./sessions.js";

test("isSafeId rejects traversal and unsafe chars", () => {
  assert.ok(isSafeId("abc-123_X"));
  assert.ok(!isSafeId(""));
  assert.ok(!isSafeId("../x"));
  assert.ok(!isSafeId("a/b"));
  assert.ok(!isSafeId("a$b"));
  assert.ok(!isSafeId("%2e%2e"));
  assert.ok(!isSafeId("x".repeat(65)));
});

test("validateTitle requires non-empty max 120", () => {
  assert.ok(!validateTitle("").ok);
  assert.ok(!validateTitle("   ").ok);
  assert.ok(!validateTitle("x".repeat(121)).ok);
  assert.deepStrictEqual(validateTitle("  hi  "), { ok: true, title: "hi" });
  assert.ok(!validateTitle(42).ok);
});

test("previewText prefers first user message", () => {
  const msgs = [{ role: "assistant", content: "a" }, { role: "user", content: "  hello  " }];
  assert.strictEqual(previewText(msgs), "hello");
  assert.strictEqual(previewText([]), "");
  assert.strictEqual(previewText(null), "");
});

test("swipeDismissed threshold", () => {
  assert.ok(swipeDismissed(-70, 260));
  assert.ok(!swipeDismissed(-10, 260));
  assert.ok(swipeDismissed(-80, 200));
});

test("h helper is DOM-free at import in node", () => {
  assert.strictEqual(typeof h, "function");
});

test("debounce fires once after wait", async () => {
  let n = 0;
  const d = debounce(() => { n += 1; }, 10);
  d(); d(); d();
  await new Promise((r) => setTimeout(r, 40));
  assert.strictEqual(n, 1);
});
