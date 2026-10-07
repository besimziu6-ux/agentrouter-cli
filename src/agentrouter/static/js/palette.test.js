import { test } from "node:test";
import assert from "node:assert/strict";
import { filterPalette, buildActions, norm } from "./palette.js";

test("palette norm trims and lowercases", () => {
  assert.strictEqual(norm("  Hello "), "hello");
  assert.strictEqual(norm(null), "");
});

test("palette filter returns all on empty query", () => {
  const acts = buildActions({});
  assert.strictEqual(filterPalette(acts, "").length, acts.length);
  assert.strictEqual(filterPalette(acts, "   ").length, acts.length);
});

test("palette filter matches title and ranks prefix first", () => {
  const acts = [
    { id: "a", title: "Open session", hint: "", run: null },
    { id: "b", title: "Switch model", hint: "", run: null },
    { id: "c", title: "New chat", hint: "", run: null },
  ];
  const r = filterPalette(acts, "model");
  assert.strictEqual(r.length, 1);
  assert.strictEqual(r[0].id, "b");
  const r2 = filterPalette(acts, "sw");
  assert.ok(r2.length >= 1 && r2[0].id === "b");
});

test("palette filter multi-word narrows", () => {
  const acts = buildActions({});
  const r = filterPalette(acts, "toggle theme");
  assert.ok(r.some((a) => a.id === "toggle-theme"));
});

test("palette buildActions has shell actions", () => {
  const ids = buildActions({}).map((a) => a.id);
  for (const want of ["new-chat", "switch-model", "toggle-theme", "toggle-inspector", "focus-input", "shortcuts"]) {
    assert.ok(ids.includes(want), "missing " + want);
  }
});
