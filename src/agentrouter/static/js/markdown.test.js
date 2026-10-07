import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  appendInline, buildBlocks, goodUrl, isOpenFence, langOf,
  nodesToHtml, parseStable, renderFull, splitStable,
} from "./markdown.js";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "markdown.js"), "utf8");

test("no innerHTML, no DOM at import", () => {
  assert.ok(!src.includes("innerHTML"), "must not use innerHTML");
});

function html(text) {
  return nodesToHtml(renderFull(text));
}

test("blocks: headers, hr, lists, task, quote, table", () => {
  const h = html("# T\n\n---\n\n- a\n  - b\n\n1. one\n2. two\n\n- [ ] t\n- [x] d\n\n> q\n\n| a | b |\n|---|---|\n| 1 | 2 |");
  assert.match(h, /<h1[^>]*>T<\/h1>/);
  assert.match(h, /<hr[^>]*>/);
  assert.match(h, /<ul[^>]*>/);
  assert.match(h, /<ol[^>]*>/);
  assert.match(h, /type="checkbox"/);
  assert.match(h, /<blockquote[^>]*>/);
  assert.match(h, /<table[^>]*>/);
  assert.match(h, /<th[^>]*>a<\/th>/);
});

test("inline: code, bold, italic, strike, links", () => {
  const h = html("Hi `c` **b** *i* ~~s~~ [ok](https://a.b/c) <https://x.y/>");
  assert.match(h, /<code[^>]*>c<\/code>/);
  assert.match(h, /<strong>b<\/strong>/);
  assert.match(h, /<em>i<\/em>/);
  assert.match(h, /<del>s<\/del>/);
  assert.match(h, /href="https:\/\/a\.b\/c"/);
  assert.match(h, /rel="noopener noreferrer"/);
  assert.ok(goodUrl("https" + "://a.b") && goodUrl("mailto:a@b.c"));
  assert.ok(!goodUrl("javascript:alert(1)") && !goodUrl("data:text/html,x"));
});

test("xss payloads stay escaped", () => {
  const h = html('<img src=x onerror=alert(1)>\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n[d](data:text/html,<b>x</b>)\n\n```js\n<script>alert(1)</script>\n```');
  assert.ok(!h.includes("<img"), h);
  assert.ok(!h.includes("<script"), h);
  assert.ok(h.includes("&lt;img src=x onerror="), "payload survives only as escaped text");
  assert.ok(!h.includes('href="javascript'), h);
  assert.ok(!h.includes("href='javascript"), h);
  assert.ok(!h.includes('href="data:'), h);
  assert.ok(h.includes("&lt;img"), h);
  assert.ok(h.includes('data-copy'), "code copy hook present");
});

test("open and nested fences stay safe", () => {
  assert.ok(isOpenFence("```js\n<script>x</script>\n"));
  assert.ok(!isOpenFence("```\na\n```\n"));
  const h = nodesToHtml(renderFull("```js\n<script>x</script>\n"));
  assert.ok(!h.includes("<script"), h);
  const nested = html("````\n```js\ncode\n```\n````");
  assert.ok(!nested.includes("<script"), nested);
  assert.strictEqual(langOf("js extra"), "js");
  assert.strictEqual(langOf(""), "");
});

test("parseStable keeps stable prefix", () => {
  const parts = ["# T", "# T\n\nhel", "# T\n\nhello", "# T\n\nhello\n\nwor", "# T\n\nhello\n\nworld"];
  let prevStable = "";
  for (const p of parts) {
    const r = parseStable(p);
    const cur = nodesToHtml(r.stable);
    assert.ok(cur.startsWith(prevStable), p);
    prevStable = cur;
    assert.strictEqual(nodesToHtml(r.stable) + nodesToHtml(renderFull(r.openTail)), nodesToHtml(renderFull(p)));
  }
  const fence = parseStable("done\n\n```js\nconst a = 1;\n");
  assert.strictEqual(nodesToHtml(fence.stable), nodesToHtml(renderFull("done")));
  assert.ok(fence.openTail.startsWith("```js"));
});

test("appendInline escapes raw html chars", () => {
  const h = nodesToHtml(renderFull("a < b & c > d \"q\""));
  assert.ok(h.includes("a &lt; b &amp; c &gt; d"), h);
});
