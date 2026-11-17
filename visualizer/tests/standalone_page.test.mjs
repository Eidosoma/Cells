// A page that holds one view standing alone (tools/build_view_page.mjs): it builds as an
// artifact page, loads scripts only from allowed hosts, says on itself that it is a preview,
// and carries exactly the list it was built from.

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { ROOT, THREE_CDN, wrap } from "../tools/lib/build_page.mjs";
import { buildViewPage, views, fill, longDate, NOTICE } from "../tools/build_view_page.mjs";
import { validate, SceneModel } from "../src/scene/model.js";

const built = buildViewPage("laws");
const blockOf = (content, attribute) => {
  const found = new RegExp(`<script type="application/json" ${attribute}[^>]*>(.*?)</script>`, "s").exec(content);
  return found ? JSON.parse(found[1]) : null;
};

test("the Laws preview builds as an artifact page and loads scripts only from allowed hosts", async () => {
  const { content, page } = await built;
  assert.ok(content.startsWith("<title>"), "the title must come first");
  assert.ok(!/<!doctype|<html|<body/i.test(content), "the artifact service adds the document around the page");
  const title = /<title>(.*?)<\/title>/.exec(content)[1];
  assert.equal(title, page.title);
  const words = title.split(/\s+/).length;
  assert.ok(words >= 2 && words <= 4, `the title is two to four words: ${title}`);
  assert.ok(content.includes(THREE_CDN), "three.js from cdnjs at the page's pinned version");
  const allowed = [/^https:\/\/cdnjs\.cloudflare\.com\//, /^https:\/\/fonts\.googleapis\.com\//];
  for (const [, url] of content.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) assert.ok(allowed.some((pattern) => pattern.test(url)), `not an allowed host: ${url}`);
  for (const [, url] of content.matchAll(/(?:from|import)\s*\(?\s*"(https?:\/\/[^"]+)"/g)) assert.equal(url, THREE_CDN, `a script from elsewhere: ${url}`);
  assert.ok(!/<script[^>]+src=/.test(content), "every script is inline but three.js");
  assert.ok(Buffer.byteLength(content) < 16 * 1024 * 1024, "over the 16 MB page limit");
  // The page's tokens: light on :root, dark under the media query (unless the page is set light) and under data-theme="dark", and a body background.
  assert.match(content, /@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\) \{[^}]*--bg:/);
  assert.match(content, /:root\[data-theme="dark"\] \{[^}]*--bg:/);
  assert.match(content, /body \{[^}]*background: var\(--bg\)/);
  // As a whole document, for a look on this machine.
  assert.ok(wrap(content).startsWith("<!doctype html>"));
});

test("the preview says on itself that it is a preview, and the revision the list was read at", async () => {
  const { content } = await built;
  const laws = JSON.parse(await readFile(path.join(ROOT, "data", "laws", "pieces.json"), "utf8"));
  const notice = /<p class="standalone-notice" role="note">(.*?)<\/p>/s.exec(content)?.[1] || "";
  assert.ok(notice.includes(`${NOTICE}.`), "the notice is in the page itself, before any script runs");
  // The manifest states the revision it was written at, and no date: the notice says the one and invents no other.
  assert.ok(notice.includes(`read from the engine's declarations at main ${laws.stamp.manifest.short}`), notice);
  assert.ok(!/committed|20[0-9]{2}/.test(notice), notice);
  assert.match(notice, /No level is shown that the declarations do not state/);
  const shell = await readFile(path.join(ROOT, "src", "standalone", "shell.js"), "utf8");
  assert.ok(shell.includes(`"${NOTICE}"`), "the page's mount says the same words");
});

test("the preview carries exactly the list it was built from, and a scene the page's model accepts", async () => {
  const { content } = await built;
  const laws = JSON.parse(await readFile(path.join(ROOT, "data", "laws", "pieces.json"), "utf8"));
  assert.deepEqual(blockOf(content, 'data-standalone-into="laws"'), laws, "the list, whole and unchanged");
  assert.match(content, /data-standalone-into="laws" data-source="data\/laws\/pieces\.json"/);
  const scene = blockOf(content, 'data-standalone="scene"');
  assert.deepEqual(validate(scene), []);
  const whole = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  assert.deepEqual(scene.statuses, whole.statuses, "the statuses the panel names");
  assert.equal(scene.meta.source_base_url, whole.meta.source_base_url, "the address its sources link to");
  assert.equal(scene.entities.length, 0, "no part of the map is carried: the view draws none");
  const model = new SceneModel({ ...scene, laws });
  assert.equal(model.raw.laws.stamp.manifest.revision, laws.stamp.manifest.revision);
});

test("the tool knows no view: every view with a mount and a page file builds, and its words are checked", async () => {
  const names = await views();
  assert.ok(names.includes("laws"));
  for (const name of names) {
    const { content, page } = await buildViewPage(name);
    assert.ok(content.includes(`<cells-standalone data-view="${name}">`), name);
    assert.ok(page.description && page.description.split(/(?<=\.)\s/).length === 1, `${name}: one sentence for whoever publishes it`);
  }
  await assert.rejects(buildViewPage("../tools"), /not a view's name/);
  assert.equal(fill("at {laws.stamp.main.revision}, {laws.stamp.main.date|date}", { laws: { stamp: { main: { revision: "abc1234", date: "2026-11-16" } } } }), "at abc1234, 16 November 2026");
  assert.throws(() => fill("{laws.nothing}", { laws: {} }), /does not hold/, "a stamp that names nothing is an error, not a blank");
  assert.equal(fill("{a.example||a.development}", { a: { development: "a run of the engine" } }), "a run of the engine", "the first of two the data holds");
  assert.equal(fill("<{a}>", { a: "<b>" }), "<&lt;b&gt;>", "the carried words are escaped");
});
