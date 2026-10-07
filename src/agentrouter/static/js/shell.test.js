import { test } from "node:test";
import assert from "node:assert/strict";
import { pruneToasts, createToastQueue } from "./toast.js";
import { filterList, nextIndex } from "./popover.js";

test("pruneToasts keeps last max", () => {
  assert.deepStrictEqual(pruneToasts([1, 2, 3, 4], 3), [2, 3, 4]);
  assert.deepStrictEqual(pruneToasts([1], 3), [1]);
});

test("toast queue caps at 3", () => {
  const q = createToastQueue(3);
  q.push("a"); q.push("b"); q.push("c"); q.push("d");
  assert.strictEqual(q.size, 3);
  assert.strictEqual(q.list()[2].text, "d");
  q.clear();
  assert.strictEqual(q.size, 0);
});

test("popover filterList ranks prefix first", () => {
  const items = [{ label: "gpt-4" }, { label: "chat-gpt" }, { label: "other" }];
  const r = filterList(items, "gpt");
  assert.strictEqual(r[0].label, "gpt-4");
  assert.strictEqual(filterList(items, "").length, 3);
});

test("popover nextIndex wraps", () => {
  assert.strictEqual(nextIndex(0, 1, 3), 1);
  assert.strictEqual(nextIndex(2, 1, 3), 0);
  assert.strictEqual(nextIndex(0, -1, 3), 2);
  assert.strictEqual(nextIndex(-1, 1, 3), 0);
});
