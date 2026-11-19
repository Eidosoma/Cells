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

test("a link published from elsewhere: its own listing says what to remove, and --remove writes it into the first upload", async () => {
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
    assert.match(done.stdout, /the first upload removes them by name \(2\), before the new files go up/);
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

test("removals go up first, and the link never passes a version's limit of files while the uploads land", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-publish-"));
  try {
    // A link that holds the page and 359 files; the next version keeps 258 of them, drops 101 and adds 200 new ones.
    const kept = Array.from({ length: 258 }, (_, k) => `runs/kept-${String(k).padStart(3, "0")}.json`);
    const dropped = Array.from({ length: 101 }, (_, k) => `runs/dropped-${String(k).padStart(3, "0")}.json`);
    const added = Array.from({ length: 200 }, (_, k) => `runs/new-${String(k).padStart(3, "0")}.json`);
    await exported(folder, Object.fromEntries([...kept, ...dropped].map((name) => [name, "x"])));
    assert.equal(stage(folder, "--new", path.join(folder, "out", "v1")).status, 0);
    await rm(path.join(folder, "out", "runs"), { recursive: true, force: true });
    await exported(folder, Object.fromEntries([...kept, ...added].map((name) => [name, "x"])));
    const told = stage(folder, "--new", path.join(folder, "out", "v2"), "--old", path.join(folder, "out", "v1"), "--remove");
    assert.equal(told.status, 0, told.stderr);
    assert.match(told.stdout, /to send: 200 .*the same as last time: 258; published before and no longer listed: 101/);
    assert.match(told.stdout, /the first upload removes them by name \(101\)/);
    assert.match(told.stdout, /the artifact then holds 459 of at most 511 files/);
    // The uploads as written, played in order with an upload's additions counted before its removals.
    let held = 360, most = held, sent = 0, removed = 0;
    for (let number = 1; existsSync(path.join(folder, "out", "v2", `upload-${number}.json`)); number++) {
      const upload = JSON.parse(await readFile(path.join(folder, "out", "v2", `upload-${number}.json`), "utf8"));
      const entries = Array.isArray(upload) ? upload.map((item) => [item.path, item.path]) : Object.entries(upload);
      assert.ok(entries.length <= 255, `upload ${number} holds ${entries.length} entries`);
      const gone = entries.filter(([, source]) => source === null).map(([name]) => name);
      const files = entries.filter(([, source]) => source !== null).map(([name]) => name);
      if (number > 1) assert.equal(gone.length, 0, "every removal is in the first upload here");
      held += files.length; // all 200 are new to the link
      most = Math.max(most, held);
      held -= gone.length;
      sent += files.length;
      removed += gone.length;
    }
    assert.equal(sent, 200);
    assert.equal(removed, 101);
    assert.equal(held, 459);
    assert.ok(most <= 511, `the link held ${most} files at most`);
    assert.match(told.stdout, new RegExp(`while the uploads land the link holds at most ${most} files`));
    // More removals than one upload holds are spread over the first uploads, before any file that would not fit.
    const many = Array.from({ length: 300 }, (_, k) => `runs/old-${String(k).padStart(3, "0")}.json`);
    await writeFile(path.join(folder, "listing.json"), JSON.stringify(["index.html", ...many]));
    const spread = stage(folder, "--new", path.join(folder, "out", "v3"), "--remote", path.join(folder, "listing.json"), "--remove");
    assert.equal(spread.status, 0, spread.stderr);
    const first = JSON.parse(await readFile(path.join(folder, "out", "v3", "upload-1.json"), "utf8"));
    const second = JSON.parse(await readFile(path.join(folder, "out", "v3", "upload-2.json"), "utf8"));
    assert.equal(Object.values(first).filter((source) => source === null).length, 240);
    assert.equal(Object.values(second).filter((source) => source === null).length, 60);
    assert.match(spread.stdout, /the first uploads remove them by name \(300\)/);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
