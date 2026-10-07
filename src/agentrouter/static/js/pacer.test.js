import { test } from "node:test";
import assert from "node:assert/strict";
import { createPacer } from "./pacer.js";

test("pacer drain respects budget and flush empties", () => {
  const p = createPacer({ charsPerFrame: 4 });
  p.push("abcdef");
  assert.strictEqual(p.size, 6);
  assert.strictEqual(p.drain(), "abcd");
  assert.strictEqual(p.size, 2);
  assert.strictEqual(p.drain(), "ef");
  assert.strictEqual(p.size, 0);
  p.push("xy");
  p.push("z");
  assert.strictEqual(p.flush(), "xyz");
  assert.strictEqual(p.size, 0);
  assert.strictEqual(p.flush(), "");
});

test("pacer drain with explicit max", () => {
  const p = createPacer({ charsPerFrame: 100 });
  p.push("hello world");
  assert.strictEqual(p.drain(5), "hello");
  assert.strictEqual(p.flush(), " world");
});
