import { test } from "node:test";
import assert from "node:assert/strict";
import { spring } from "./motion.js";

test("spring converges to target", () => {
  const s = spring(0, 1, { stiffness: 170, damping: 26 });
  for (let i = 0; i < 600; i++) s.step(1 / 60);
  assert.ok(Math.abs(s.value - 1) < 0.01, "value=" + s.value);
  assert.ok(s.settled(0.02));
});

test("spring retarget preserves velocity", () => {
  const s = spring(0, 1, { stiffness: 120, damping: 14 });
  for (let i = 0; i < 30; i++) s.step(1 / 60);
  const vBefore = s.velocity;
  assert.ok(Math.abs(vBefore) > 0.01, "should be moving, v=" + vBefore);
  s.setTarget(0);
  assert.strictEqual(s.velocity, vBefore);
  for (let i = 0; i < 600; i++) s.step(1 / 60);
  assert.ok(Math.abs(s.value - 0) < 0.02, "value=" + s.value);
});
