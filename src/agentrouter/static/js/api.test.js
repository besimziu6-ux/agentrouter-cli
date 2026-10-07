import { test } from "node:test";
import assert from "node:assert/strict";
import { createSSEParser } from "./api.js";

test("sse parser handles mangled chunks, keepalive, done and errors", () => {
  const events = [];
  const p = createSSEParser((ev) => events.push(ev));
  p.push('data: {"content": "Hel');
  p.push('lo"}\n\ndata: {"content": " world"}\n\n');
  p.push(": keepalive\n\n");
  p.push('data: {"error": "mid-stream boom"}\n\n');
  p.push("data: [DONE]\n\n");
  p.push('data: {"content": "late"}\n\n');
  const contents = events.filter((e) => typeof e.content === "string").map((e) => e.content);
  assert.ok(contents.join("").includes("Hello"), JSON.stringify(events));
  assert.ok(contents.join("").includes(" world"), JSON.stringify(events));
  assert.ok(events.some((e) => e.error === "mid-stream boom"), JSON.stringify(events));
  assert.ok(events.some((e) => e.done === true), JSON.stringify(events));
  assert.ok(!contents.includes("late"), "no events after DONE");
});

test("sse parser split done marker across chunks", () => {
  const events = [];
  const p = createSSEParser((ev) => events.push(ev));
  p.push("data: [DO");
  p.push("NE]\n\n");
  assert.ok(events.some((e) => e.done === true), JSON.stringify(events));
});
