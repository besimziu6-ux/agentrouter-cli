import { test } from "node:test";
import assert from "node:assert/strict";
import { clampFontScale, resolveTheme, resolveMotion, resolveDensity, effectiveSettings } from "./settings.js";

test("clampFontScale bounds", () => {
  assert.strictEqual(clampFontScale(100), 100);
  assert.strictEqual(clampFontScale(10), 85);
  assert.strictEqual(clampFontScale(500), 130);
  assert.strictEqual(clampFontScale("xx"), 100);
});

test("resolveTheme handles os and fallback", () => {
  assert.strictEqual(resolveTheme("dark", false), "dark");
  assert.strictEqual(resolveTheme("light", false), "light");
  assert.strictEqual(resolveTheme("os", true), "light");
  assert.strictEqual(resolveTheme("os", false), "dark");
  assert.strictEqual(resolveTheme("bogus", false), "light");
});

test("resolveMotion prefers reduced default", () => {
  assert.strictEqual(resolveMotion("", true), "reduced");
  assert.strictEqual(resolveMotion("", false), "full");
  assert.strictEqual(resolveMotion("off", false), "off");
});

test("resolveDensity fallback comfortable", () => {
  assert.strictEqual(resolveDensity("compact"), "compact");
  assert.strictEqual(resolveDensity("nope"), "comfortable");
});

test("effectiveSettings has no DOM at import and resolves", () => {
  const e = effectiveSettings({ theme: "dark", motion: "full", density: "compact", fontScale: 120 });
  assert.strictEqual(e.theme, "dark");
  assert.strictEqual(e.motion, "full");
  assert.strictEqual(e.density, "compact");
  assert.strictEqual(e.fontScale, 120);
});
