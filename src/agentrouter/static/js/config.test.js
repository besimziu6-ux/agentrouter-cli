import { test } from "node:test";
import assert from "node:assert/strict";
import { validateKey, validateModel, translateConfigError, needsOnboarding, LOCKED_BASE_URL } from "./config.js";

test("validateKey rejects empty and short", () => {
  assert.ok(!validateKey("").ok);
  assert.ok(!validateKey("   ").ok);
  assert.ok(!validateKey("short").ok);
  assert.deepStrictEqual(validateKey("  sk-abcdef123  "), { ok: true, key: "sk-abcdef123" });
});

test("validateModel allows empty, trims", () => {
  assert.deepStrictEqual(validateModel(""), { ok: true, model: "" });
  assert.deepStrictEqual(validateModel(null), { ok: true, model: "" });
  assert.deepStrictEqual(validateModel("  m1  "), { ok: true, model: "m1" });
  assert.ok(!validateModel(42).ok);
});

test("translateConfigError covers 401/429/network", () => {
  assert.ok(translateConfigError(401, "bad").title.includes("401"));
  assert.ok(translateConfigError(401, "bad").hint.includes("key"));
  assert.ok(translateConfigError(429, "").hint.includes("Wait"));
  assert.strictEqual(translateConfigError(0, "").title, "Network error");
  assert.ok(translateConfigError(500, "x").title.includes("500"));
});

test("needsOnboarding when no key", () => {
  assert.ok(needsOnboarding(null));
  assert.ok(needsOnboarding({ has_key: false }));
  assert.ok(!needsOnboarding({ has_key: true }));
});

test("base URL locked", () => {
  assert.strictEqual(LOCKED_BASE_URL, "https://agentrouter.org/v1");
});
