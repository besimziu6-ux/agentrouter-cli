import { test } from "node:test";
import assert from "node:assert/strict";
import {
  argSummary,
  barFrac,
  bashTimeoutMs,
  hunkDelay,
  parseAgentEvent,
  resolveStop,
  stopLabel,
} from "./timeline.js";

test("resolveStop prefers abort, then error, then max_steps", () => {
  assert.strictEqual(resolveStop({ steps: 10, maxSteps: 10 }), "max_steps");
  assert.strictEqual(resolveStop({ steps: 3, maxSteps: 10 }), "done");
  assert.strictEqual(resolveStop({ steps: 3, maxSteps: 10, error: "x" }), "error");
  assert.strictEqual(resolveStop({ steps: 10, maxSteps: 10, aborted: true }), "user_abort");
  assert.strictEqual(resolveStop({}), "done");
  assert.strictEqual(resolveStop(null), "done");
});

test("stopLabel covers all reasons", () => {
  assert.strictEqual(stopLabel("done"), "done");
  assert.strictEqual(stopLabel("max_steps"), "max steps reached");
  assert.strictEqual(stopLabel("error"), "error");
  assert.strictEqual(stopLabel("user_abort"), "stopped by you");
  assert.strictEqual(stopLabel("bogus"), "done");
});

test("barFrac is determinate only with timeout", () => {
  assert.strictEqual(barFrac(1000, 0), -1);
  assert.strictEqual(barFrac(1000, null), -1);
  assert.strictEqual(barFrac(500, 2), 0.25);
  assert.strictEqual(barFrac(9999, 2), 1);
  assert.strictEqual(barFrac(-5, 2), 0);
});

test("bashTimeoutMs reads only bash timeout", () => {
  assert.strictEqual(bashTimeoutMs("bash", { timeout: 5 }), 5);
  assert.strictEqual(bashTimeoutMs("bash", {}), 0);
  assert.strictEqual(bashTimeoutMs("read_file", { timeout: 5 }), 0);
  assert.strictEqual(bashTimeoutMs("bash", null), 0);
});

test("hunkDelay spreads fades within 200ms", () => {
  assert.strictEqual(hunkDelay(0, 4), 0);
  assert.ok(hunkDelay(3, 4) <= 200);
  assert.ok(hunkDelay(9, 10) <= 200);
  assert.strictEqual(hunkDelay(0, 0), 0);
});

test("argSummary stringifies safely", () => {
  assert.strictEqual(argSummary({ command: "ls" }), '{"command":"ls"}');
  assert.strictEqual(argSummary(null), "{}");
  assert.ok(typeof argSummary(42) === "string");
});

test("parseAgentEvent normalizes backend shapes", () => {
  assert.strictEqual(parseAgentEvent({ type: "step", step: 1, text: "hi" }).kind, "step");
  const t = parseAgentEvent({ type: "tool", step: 2, tool: "bash", args: { command: "ls" }, result: "ok" });
  assert.strictEqual(t.kind, "tool");
  assert.strictEqual(t.tool, "bash");
  const d = parseAgentEvent({ type: "done", text: "fin", session_id: "s1" });
  assert.strictEqual(d.kind, "done");
  assert.strictEqual(d.sessionId, "s1");
  assert.strictEqual(parseAgentEvent({ type: "error", error: "boom" }).kind, "error");
  assert.strictEqual(parseAgentEvent({ type: "approval", tool: "bash" }).kind, "approval");
  assert.strictEqual(parseAgentEvent(null).kind, "unknown");
  assert.strictEqual(parseAgentEvent("x").kind, "unknown");
  assert.strictEqual(parseAgentEvent({ type: "weird" }).kind, "unknown");
});
