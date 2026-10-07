import { test } from "node:test";
import assert from "node:assert/strict";
import { approvalKey, isApprovalEvent, isDialogOpen } from "./dialog.js";

test("isApprovalEvent matches only approval SSE", () => {
  assert.ok(isApprovalEvent({ type: "approval", tool: "bash" }));
  assert.ok(!isApprovalEvent({ type: "step" }));
  assert.ok(!isApprovalEvent({ type: "tool" }));
  assert.ok(!isApprovalEvent({ type: "done" }));
  assert.ok(!isApprovalEvent(null));
  assert.ok(!isApprovalEvent("approval"));
});

test("approvalKey maps Y/N/A", () => {
  assert.strictEqual(approvalKey("y"), "allow");
  assert.strictEqual(approvalKey("Y"), "allow");
  assert.strictEqual(approvalKey("n"), "deny");
  assert.strictEqual(approvalKey("N"), "deny");
  assert.strictEqual(approvalKey("a"), "always");
  assert.strictEqual(approvalKey("A"), "always");
  assert.strictEqual(approvalKey("x"), null);
  assert.strictEqual(approvalKey("Enter"), null);
  assert.strictEqual(approvalKey(null), null);
});

test("no dialog open at import in node", () => {
  assert.strictEqual(isDialogOpen(), false);
});
