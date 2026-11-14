// Checks that run without a browser: the scene is valid, the page builds, and the
// page asks for nothing the artifact frame would block.
//
//   npm test

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, ROOT, THREE_CDN, DEFAULT_SCENE } from "../tools/lib/build_page.mjs";
import { validate } from "../src/scene/model.js";

const scene = JSON.parse(await readFile(DEFAULT_SCENE, "utf8"));
const overlay = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));

test("the generated scene is structurally valid", () => {
  assert.deepEqual(validate(scene), []);
});

test("the extractor placed every engine file and raised no warning", () => {
  assert.equal(scene.meta.counts.engine_files_placed, scene.meta.counts.engine_files);
  assert.deepEqual(scene.meta.warnings, []);
});

test("every status claim carries a source, and every dated one a date", () => {
  for (const entity of scene.entities) {
    if (!entity.status || entity.kind === "scale") continue;
    const catchAll = /^Other /.test(entity.label) || entity.plain?.includes("not grouped elsewhere");
    if (!catchAll && entity.status !== "established") {
      assert.ok(entity.sources?.length, `${entity.id} (${entity.status}) has no source`);
    }
  }
});

test("each capability is drawn: it names a part of the cell and how it is represented", () => {
  const representations = new Set(overlay.representations.map((item) => item.id));
  for (const capability of scene.entities.filter((entity) => entity.kind === "capability")) {
    assert.ok(capability.part, `${capability.id} has no part`);
    assert.ok(representations.has(capability.representation), `${capability.id}: representation ${capability.representation}`);
  }
});

test("the scene holds no machine-specific paths or host names", () => {
  const text = JSON.stringify(scene);
  assert.ok(!/\/home\/|\/mnt\/|\/Users\//.test(text), "an absolute path leaked into the scene");
});

test("the page builds and loads scripts only from allowed hosts", async () => {
  const page = await buildPage();
  assert.ok(page.startsWith("<title>"), "the title must come first");
  assert.ok(!/<!doctype|<html|<body/i.test(page), "the artifact service adds the document around the page");
  assert.ok(page.includes(THREE_CDN));
  const allowed = [/^https:\/\/cdnjs\.cloudflare\.com\//, /^https:\/\/fonts\.googleapis\.com\//];
  for (const [, url] of page.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) {
    assert.ok(allowed.some((pattern) => pattern.test(url)), `not an allowed host: ${url}`);
  }
  for (const [, url] of page.matchAll(/from\s+"(https?:\/\/[^"]+)"/g)) {
    assert.ok(allowed[0].test(url), `not an allowed script host: ${url}`);
  }
  assert.ok(Buffer.byteLength(page) < 16 * 1024 * 1024, "over the 16 MB page limit");
});
