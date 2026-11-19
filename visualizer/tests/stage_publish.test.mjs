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

test("the staging says how much of a version's limit the artifact then holds, and stops when it would be over", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    await exported(folder, { "runs/a.json": "A", "runs/b.json": "B", "runs/c.json": "C" });
    assert.equal(stage(folder, "--new", path.join(folder, "out", "v1")).status, 0);
    // What is no longer listed stays published until it is removed by name, so it still counts.
    await exported(folder, { "runs/a.json": "A", "runs/d.json": "D" });
    const kept = stage(folder, "--new", path.join(folder, "out", "v2"), "--old", path.join(folder, "out", "v1"));
    assert.equal(kept.status, 0, kept.stderr);
    assert.match(kept.stdout, /the artifact then holds 5 of at most 511 files, the page among them/, "two listed, the page, and two no longer listed");
    const many = Object.fromEntries(Array.from({ length: 511 }, (_, index) => [`runs/r${String(index).padStart(3, "0")}.json`, String(index)]));
    await exported(folder, many);
    const over = stage(folder, "--new", path.join(folder, "out", "v3"));
    assert.notEqual(over.status, 0, "511 files and the page are one too many");
    assert.match(over.stderr, /over what one version of an artifact holds/);
    const near = Object.fromEntries(Object.entries(many).slice(0, 470));
    await exported(folder, near);
    const close = stage(folder, "--new", path.join(folder, "out", "v4"));
    assert.equal(close.status, 0, close.stderr);
    assert.match(close.stdout, /nine tenths of the limit or more/);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a link published from elsewhere: its own listing says what to remove, and --remove writes it into the last upload", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    await exported(folder, { "runs/a.json": "A", "runs/d.json": "D" });
    // The Artifact tool's listing of the link, as it prints it: the page, a file still listed, two that are not.
    const listing = ['Published files of https://example.invalid/artifact/x (version 1), 4 files by path:', '- "index.html"  text/html  1192437 bytes',
      '- "runs/a.json"  application/json  1 bytes', '- "runs/old-1.json"  application/json  870940 bytes', '- "runs/old-2.json"  application/json  12 bytes'].join("\n");
    await writeFile(path.join(folder, "listing.txt"), listing);
    const told = stage(folder, "--new", path.join(folder, "out", "v1"), "--remote", path.join(folder, "listing.txt"));
    assert.equal(told.status, 0, told.stderr);
    assert.match(told.stdout, /to send: 2 .*published before and no longer listed: 2/, "with no staged folder to compare with, every listed file is sent");
    assert.match(told.stdout, /the artifact then holds 5 of at most 511 files/, "two listed, the page, and the two that stay until they are removed");
    assert.deepEqual(JSON.parse(await readFile(path.join(folder, "out", "v1", "upload-1.json"), "utf8")), [{ path: "runs/a.json" }, { path: "runs/d.json" }], "without --remove the upload only sends");
    const done = stage(folder, "--new", path.join(folder, "out", "v2"), "--remote", path.join(folder, "listing.txt"), "--remove");
    assert.equal(done.status, 0, done.stderr);
    assert.deepEqual(JSON.parse(await readFile(path.join(folder, "out", "v2", "upload-1.json"), "utf8")),
      { "runs/a.json": "runs/a.json", "runs/d.json": "runs/d.json", "runs/old-1.json": null, "runs/old-2.json": null }, "the page's own file is never removed");
    assert.match(done.stdout, /the last upload removes them by name \(2\)/);
    assert.match(done.stdout, /the artifact then holds 3 of at most 511 files/);
    // A JSON list of paths is a listing too, and removals alone make an upload when nothing is to be sent.
    await writeFile(path.join(folder, "listing.json"), JSON.stringify(["index.html", "runs/a.json", "runs/d.json", "runs/old-1.json"]));
    const only = stage(folder, "--new", path.join(folder, "out", "v3"), "--old", path.join(folder, "out", "v2"), "--remote", path.join(folder, "listing.json"), "--remove");
    assert.equal(only.status, 0, only.stderr);
    assert.match(only.stdout, /to send: 0 /);
    assert.deepEqual(JSON.parse(await readFile(path.join(folder, "out", "v3", "upload-1.json"), "utf8")), { "runs/old-1.json": null });
    const empty = path.join(folder, "empty.txt");
    await writeFile(empty, "nothing here");
    const refused = stage(folder, "--new", path.join(folder, "out", "v4"), "--remote", empty);
    assert.notEqual(refused.status, 0);
    assert.match(refused.stderr, /no file is named in the listing/);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
