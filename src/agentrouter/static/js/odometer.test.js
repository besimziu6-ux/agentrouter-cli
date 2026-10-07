import { test } from "node:test";
import assert from "node:assert/strict";
import { isDigit, mountOdometer, paintOdometer, rollY, toChars } from "./odometer.js";

test("isDigit accepts 0-9 only", () => {
  assert.ok(isDigit("0") && isDigit("7"));
  assert.ok(!isDigit("a") && !isDigit("") && !isDigit(null) && !isDigit("12"));
});

test("toChars stringifies safely", () => {
  assert.deepStrictEqual(toChars("00:01.5"), ["0", "0", ":", "0", "1", ".", "5"]);
  assert.deepStrictEqual(toChars(null), []);
  assert.deepStrictEqual(toChars(42), ["4", "2"]);
});

test("rollY maps digit to -em offset", () => {
  assert.strictEqual(rollY("0"), 0);
  assert.strictEqual(rollY("3"), -3);
  assert.strictEqual(rollY("9"), -9);
  assert.strictEqual(rollY(":"), null);
  assert.strictEqual(rollY(""), null);
});

test("mount/paint degrade without DOM", () => {
  assert.strictEqual(mountOdometer(null, "00:00.0"), false);
  assert.strictEqual(paintOdometer(null, "step 1"), false);
  assert.strictEqual(paintOdometer(undefined, "x"), false);
});
