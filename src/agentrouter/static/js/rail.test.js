import { test } from "node:test";
import assert from "node:assert/strict";
import { filterSessions, drawerTarget } from "./rail.js";

test("filterSessions empty query returns copy", () => {
  const s = [{ id: "a" }, { id: "b" }];
  const r = filterSessions(s, "");
  assert.deepStrictEqual(r, s);
  assert.notStrictEqual(r, s);
});

test("filterSessions matches id and preview", () => {
  const s = [{ id: "alpha", preview: "hello" }, { id: "beta", preview: "world" }];
  assert.strictEqual(filterSessions(s, "alp").length, 1);
  assert.strictEqual(filterSessions(s, "world").length, 1);
  assert.strictEqual(filterSessions(s, "zzz").length, 0);
});

test("drawerTarget velocity wins over position", () => {
  assert.strictEqual(drawerTarget(false, 10, 1.0, 260), true);
  assert.strictEqual(drawerTarget(true, 250, -1.0, 260), false);
  assert.strictEqual(drawerTarget(false, 200, 0, 260), true);
  assert.strictEqual(drawerTarget(false, 10, 0, 260), false);
});
