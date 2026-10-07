import { test } from "node:test";
import assert from "node:assert/strict";
import { createPacer } from "./pacer.js";
import { buildChatPayload, frameBudget, loadConvs, saveConvs, shouldStick, translateError } from "./chat.js";
import { createMeterState, formatRate } from "./meter.js";
import { isEmptyText, shouldSendKey } from "./composer.js";
import { formatTime, roleLabel } from "./messages.js";

test("frame budget follows max(1,ceil(backlog/10))", () => {
  assert.deepStrictEqual([0, 1, 10, 11, 100, -5].map(frameBudget), [1, 1, 1, 2, 10, 1]);
});

test("pacer drains backlog per frame", () => {
  const p = createPacer({ charsPerFrame: 1000 });
  const tokens = ["Hello", " world", " this", " is", " a", " test", " stream"];
  for (const t of tokens) p.push(t);
  let full = "";
  let frames = 0;
  while (p.size > 0 && frames < 1000) {
    full += p.drain(frameBudget(p.size));
    frames++;
  }
  assert.strictEqual(full, tokens.join(""));
  assert.ok(frames > 1);
  assert.strictEqual(p.flush(), "");
});

test("chat payload shape", () => {
  const base = buildChatPayload({ model: "m", messages: [{ role: "user", content: "hi" }] });
  assert.deepStrictEqual(base, { model: "m", messages: [{ role: "user", content: "hi" }] });
  const f = buildChatPayload({ model: "m", messages: [], system: "sys", max_tokens: 50, temperature: 0.5 });
  assert.strictEqual(f.system, "sys");
  assert.strictEqual(f.max_tokens, 50);
  assert.strictEqual(f.temperature, 0.5);
});

test("errors translate with hint and retry", () => {
  const a = translateError(401, "bad key");
  assert.match(a.title, /key/i);
  assert.ok(a.retry && a.hint.length > 0);
  assert.match(translateError(429, "").title, /rate/i);
  assert.match(translateError(0, "").title, /network/i);
  const s = translateError(500, "boom");
  assert.ok(s.retry && s.hint.includes("boom"));
});

test("conversations persist capped", () => {
  const mem = new Map();
  const storage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => { mem.set(k, String(v)); } };
  assert.deepStrictEqual(loadConvs(storage), []);
  assert.ok(saveConvs(storage, [{ id: "1", messages: [{ role: "user", content: "x".repeat(100000) }] }, { id: "2", messages: [] }]));
  assert.ok(loadConvs(storage).length >= 1);
  assert.deepStrictEqual(loadConvs({ getItem: () => { throw new Error("denied"); } }), []);
  assert.strictEqual(saveConvs({ setItem: () => { throw new Error("full"); } }, []), false);
});

test("stick threshold and meter math", () => {
  assert.ok(shouldStick(80) && !shouldStick(81));
  const m = createMeterState();
  m.push(20, 1000);
  m.push(20, 1100);
  const r = m.tick(1100).rate;
  assert.ok(r > 0);
  assert.ok(m.tick(10000).rate <= r);
  assert.strictEqual(formatRate(5.25), "5.3");
  assert.strictEqual(formatRate(42), "42");
});

test("composer and message helpers", () => {
  assert.ok(shouldSendKey({ key: "Enter" }));
  assert.ok(!shouldSendKey({ key: "Enter", shiftKey: true }));
  assert.ok(!shouldSendKey({ key: "a" }));
  assert.ok(isEmptyText("   ") && !isEmptyText(" x "));
  assert.strictEqual(roleLabel("user"), "YOU");
  assert.strictEqual(roleLabel("assistant", "anthropic/claude-3"), "CLAUDE-3");
  assert.match(formatTime(Date.now()), /^\d\d:\d\d:\d\d$/);
});
