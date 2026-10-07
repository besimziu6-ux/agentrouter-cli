import { test } from "node:test";
import assert from "node:assert/strict";
import { formatElapsed, nextMode, pickModels, stepText } from "./transport.js";

test("formatElapsed mm:ss.d", () => {
  assert.strictEqual(formatElapsed(0), "00:00.0");
  assert.strictEqual(formatElapsed(61500), "01:01.5");
  assert.strictEqual(formatElapsed(59999), "00:59.9");
  assert.strictEqual(formatElapsed(-5), "00:00.0");
});

test("nextMode toggles", () => {
  assert.strictEqual(nextMode("chat"), "agent");
  assert.strictEqual(nextMode("agent"), "chat");
  assert.strictEqual(nextMode("x"), "agent");
});

test("stepText clamps step counter", () => {
  assert.strictEqual(stepText(0), "step 0");
  assert.strictEqual(stepText(7), "step 7");
  assert.strictEqual(stepText(-3), "step 0");
  assert.strictEqual(stepText(null), "step 0");
});
test("pickModels normalizes payloads", () => {
  assert.deepStrictEqual(pickModels({ data: [{ id: "m1" }, { id: "m2" }] }), [
    { label: "m1", value: "m1" },
    { label: "m2", value: "m2" },
  ]);
  assert.deepStrictEqual(pickModels(["a", "b"]), [
    { label: "a", value: "a" },
    { label: "b", value: "b" },
  ]);
  assert.deepStrictEqual(pickModels(null), []);
});
