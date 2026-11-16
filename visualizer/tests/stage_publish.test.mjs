// Staging a publish (tools/stage_publish.py): the page and the files it lists are copied
// into one folder laid out as the artifact is, only what changed since the last publish is
// sent, and an upload stays under the artifact's limits.
//
//   node --test tests/stage_publish.test.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "stage_publish.py");

/** A stand-in for the visualizer folder after an export: a page, the list of its files, and the files. */
async function exported(folder, files) {
  await mkdir(path.join(folder, "out", "runs"), { recursive: true });
  await mkdir(path.join(folder, "data"), { recursive: true });
  await writeFile(path.join(folder, "out", "cells-architecture.html"), "<title>page</title>");
  const listed = {};
  for (const [published, text] of Object.entries(files)) {
    const source = published.startsWith("runs/") ? `out/${published}` : `data/${path.basename(published)}`;
    await writeFile(path.join(folder, source), text);
    listed[published] = source;
  }
  await writeFile(path.join(folder, "out", "cells-architecture.files.json"), JSON.stringify(listed));
}

const stage = (folder, ...more) => spawnSync("python3", ["-I", TOOL, "--root", folder, ...more], { encoding: "utf8" });

test("a first publish sends every file, in the artifact's layout", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    await exported(folder, { "runs/a.json": "A", "runs/b.json": "B", "proteins/x/shelves.json": "S" });
    const done = stage(folder, "--new", path.join(folder, "out", "v1"));
    assert.equal(done.status, 0, done.stderr);
    assert.match(done.stdout, /3 files beside the page/);
    assert.match(done.stdout, /to send: 3 /);
    assert.equal(await readFile(path.join(folder, "out", "v1", "proteins", "x", "shelves.json"), "utf8"), "S", "a file stands under its published path, whatever its source");
    assert.equal(await readFile(path.join(folder, "out", "v1", "cells-architecture.html"), "utf8"), "<title>page</title>");
    assert.deepEqual(JSON.parse(await readFile(path.join(folder, "out", "v1", "upload-1.json"), "utf8")), [{ path: "proteins/x/shelves.json" }, { path: "runs/a.json" }, { path: "runs/b.json" }]);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a later publish sends only what changed, and names what is no longer listed", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    await exported(folder, { "runs/a.json": "A", "runs/b.json": "B", "runs/c.json": "C" });
    assert.equal(stage(folder, "--new", path.join(folder, "out", "v1")).status, 0);
    await exported(folder, { "runs/a.json": "A", "runs/b.json": "B changed", "runs/d.json": "D" });
    const done = stage(folder, "--new", path.join(folder, "out", "v2"), "--old", path.join(folder, "out", "v1"));
    assert.equal(done.status, 0, done.stderr);
    assert.match(done.stdout, /to send: 2 .*the same as last time: 1; published before and no longer listed: 1/);
    assert.match(done.stdout, /no longer listed: runs\/c\.json/);
    assert.deepEqual(JSON.parse(await readFile(path.join(folder, "out", "v2", "upload-1.json"), "utf8")), [{ path: "runs/b.json" }, { path: "runs/d.json" }]);
    assert.ok(existsSync(path.join(folder, "out", "v2", "runs", "a.json")), "the staged folder holds every file, sent or not: it is the record of what is published");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("an upload stays under the artifact's limit of files, and a missing file stops the staging", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    const many = Object.fromEntries(Array.from({ length: 250 }, (_, index) => [`runs/r${String(index).padStart(3, "0")}.json`, String(index)]));
    await exported(folder, many);
    const done = stage(folder, "--new", path.join(folder, "out", "v1"));
    assert.equal(done.status, 0, done.stderr);
    const first = JSON.parse(await readFile(path.join(folder, "out", "v1", "upload-1.json"), "utf8")), second = JSON.parse(await readFile(path.join(folder, "out", "v1", "upload-2.json"), "utf8"));
    assert.deepEqual([first.length, second.length], [240, 10]);
    await rm(path.join(folder, "out", "runs", "r000.json"));
    const broken = stage(folder, "--new", path.join(folder, "out", "v2"));
    assert.notEqual(broken.status, 0);
    assert.match(broken.stderr, /not on disk/);
    assert.ok(!existsSync(path.join(folder, "out", "v2")), "nothing is staged from an export that is not whole");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
