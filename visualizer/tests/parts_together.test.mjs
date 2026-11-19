// A run's parts published together (schema/RUN_VIEW.md, "Parts published together"): the export's packaging
// (tools/lib/build_page.mjs, packageParts) and the page's reading of it (src/replay/source.js, loadPart). The runs folder
// keeps one file a part, as the adapter writes it; a published page may hold the parts of each run of an experiment whose
// overlay entry says `parts_together` in one file for the run, as few as stay under the size limit. A view asks for one
// part as before: the file is fetched once, however many of its parts are asked for, only the part asked for is taken
// in, and an error names the file and the part.

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { syntheticRun } from "./helpers/synthetic_replay.mjs";
import { openReplay, loadPart } from "../src/replay/source.js";
import { validatePart, validateParts, PARTS_FORMAT, PART_FORMAT } from "../src/replay/run.js";
import { cutInOrder, packageParts, partsTogether, publishedReplays, readReplays, RUN_FILE_LIMIT, DEFAULT_RUNS } from "../tools/lib/build_page.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-parts-together-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));

/** A made-up run with four parts, written as the adapter writes a runs folder: its own file, one file a part, and the catalogue. */
function folderOf(name) {
  const { file, entry, parts } = syntheticRun({ membrane: true });
  const runs = path.join(scratch, name);
  mkdirSync(runs, { recursive: true });
  const sizes = {};
  const write = (where, body) => {
    const text = JSON.stringify(body) + "\n";
    sizes[where] = Buffer.byteLength(text);
    writeFileSync(path.join(runs, where), text);
  };
  write(`${entry.id}.json`, file);
  for (const [id, part] of Object.entries(parts)) write(`${entry.id}.${id}.json`, part);
  const row = { ...entry, parts: entry.parts.map((part) => ({ ...part, bytes: sizes[path.basename(part.file)] })) };
  const catalogue = { format: "cells.visualizer.replay_index@1", experiments: [{ id: "e07-v1", label: "made up" }], runs: [row] };
  return { file, entry, parts, runs, catalogue, sizes };
}

/** A fetcher that serves files by their published path, and counts what it was asked for. */
function server(files) {
  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    const text = files[url];
    return { ok: text !== undefined, status: text === undefined ? 404 : 200, json: async () => JSON.parse(text) };
  };
  return { asked, fetcher };
}

test("the overlay's word is read as true or false, and nothing else", () => {
  assert.deepEqual([...partsTogether({ experiments: { a: { parts_together: true }, b: { parts_together: false }, c: {} } })], ["a"]);
  assert.throws(() => partsTogether({ experiments: { a: { parts_together: "yes" } } }), /a: parts_together is true or false, not "yes"/);
  const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "overlay.json"), "utf8"));
  const together = partsTogether(overlay);
  for (const id of together) assert.ok(id in overlay.experiments);
});

test("an experiment that says so has its runs' parts in one file a run, each part file in it as it is; the others keep one a part", async () => {
  const { runs, catalogue, entry, sizes } = folderOf("one-file");
  const alone = await packageParts(catalogue, { runsDir: runs, together: new Set() });
  assert.deepEqual(alone, { replays: { ...catalogue, runs: catalogue.runs }, files: [] }, "an experiment that does not say so is left as it is");
  const { replays, files } = await packageParts(catalogue, { runsDir: runs, together: new Set(["e07-v1"]) });
  assert.equal(files.length, 1);
  const [one] = files;
  assert.equal(one.path, `runs/${entry.id}.parts.json`);
  assert.deepEqual(one.parts, ["junction-gate", "concentration-na", "concentration-k", "concentration-m"], "in the run's own order");
  const file = JSON.parse(one.text);
  assert.equal(file.format, PARTS_FORMAT);
  assert.deepEqual(validateParts(file, entry.id), []);
  for (const part of file.parts) assert.equal(JSON.stringify(part) + "\n", readFileSync(path.join(runs, `${entry.id}.${part.part}.json`), "utf8"), "each part as the adapter wrote it");
  assert.ok(Buffer.byteLength(one.text) < RUN_FILE_LIMIT);
  assert.deepEqual(replays.runs[0].parts.map((part) => [part.id, part.file, part.bytes]), one.parts.map((id) => [id, one.path, Buffer.byteLength(one.text)]), "the catalogue names, for each part, the file that holds it");
  assert.equal(replays.runs[0].file, catalogue.runs[0].file, "the run's own file is the same");
  assert.equal(catalogue.runs[0].parts[0].file, `runs/${entry.id}.junction-gate.json`, "the catalogue it was given is not changed");
  assert.ok(Object.values(sizes).length === 5);
});

test("where one file would reach the limit, as few as stay under it, the parts kept whole and in order", async () => {
  const { runs, catalogue, entry, sizes } = folderOf("cut");
  const each = Object.entries(sizes).filter(([name]) => name !== `${entry.id}.json`).map(([, bytes]) => bytes);
  // A limit that holds two of the parts but not three.
  const limit = Math.max(...each) * 2 + 200;
  const { replays, files } = await packageParts(catalogue, { runsDir: runs, together: new Set(["e07-v1"]), limit });
  assert.deepEqual(files.map((file) => file.path), [`runs/${entry.id}.parts.json`, `runs/${entry.id}.parts-2.json`]);
  assert.deepEqual(files.flatMap((file) => file.parts), ["junction-gate", "concentration-na", "concentration-k", "concentration-m"]);
  for (const file of files) assert.ok(Buffer.byteLength(file.text) < limit, `${file.path} is under the limit`);
  assert.deepEqual(replays.runs[0].parts.map((part) => part.file), files.flatMap((file) => file.parts.map(() => file.path)));
  await assert.rejects(packageParts(catalogue, { runsDir: runs, together: new Set(["e07-v1"]), limit: 1000 }), /one of its parts alone would reach 1000 bytes in a file of its parts/);
  const named = { ...catalogue, runs: [{ ...catalogue.runs[0], parts: [{ ...catalogue.runs[0].parts[0], id: "parts" }] }] };
  await assert.rejects(packageParts(named, { runsDir: runs, together: new Set(["e07-v1"]) }), /its part parts would have the name of the file of its parts/);
});

test("a run's parts are cut, in their order, into the fewest files under the limit, the largest of them as small as can be", () => {
  // E07-v1's runs: a junction gate and three ions' concentrations (bytes of each part's file), 1.30 MB in all.
  assert.deepEqual(cutInOrder([239121, 355104, 355103, 355103], { overhead: 100, limit: 1_000_000 }), [[0, 1], [2, 3]], "two files of 0.59 and 0.71 MB, not 0.95 and 0.36");
  assert.deepEqual(cutInOrder([10, 20, 30], { overhead: 10, limit: 100 }), [[0, 1, 2]], "one file where they fit");
  assert.deepEqual(cutInOrder([40, 40, 40, 40, 40], { overhead: 0, limit: 100 }), [[0], [1, 2], [3, 4]], "three, since two would not hold them; ties go to the first cut");
  assert.equal(cutInOrder([50, 120], { overhead: 0, limit: 100 }), null, "a part alone too large");
  assert.equal(cutInOrder([], {}), null);
});

test("a view's parts come from the file of several as they came from one a part: one fetch, only the part asked for taken in", async () => {
  const { runs, catalogue, file, parts } = folderOf("loaded");
  const { replays, files } = await packageParts(catalogue, { runsDir: runs, together: new Set(["e07-v1"]) });
  const { asked, fetcher } = server(Object.fromEntries(files.map((item) => [item.path, item.text])));
  const run = openReplay(JSON.parse(JSON.stringify(file)), replays.runs[0]);
  await Promise.all([loadPart(run, "concentration-na", { root: null, fetcher }), loadPart(run, "concentration-k", { root: null, fetcher })]);
  assert.deepEqual(asked, [files[0].path], "two parts asked for at once: the file is fetched once");
  assert.equal(run.parts.get("concentration-na").loaded && run.parts.get("concentration-k").loaded, true);
  assert.equal(run.parts.get("junction-gate").loaded, false, "a part not asked for is not taken in");
  assert.ok(run.pending.has("junction_gate"), "and its records still wait");
  await loadPart(run, "junction-gate", { root: null, fetcher });
  assert.equal(asked.length, 1, "a part asked for later comes from the file already fetched");
  // The records are those of the run's own files, one a part.
  const plain = openReplay(JSON.parse(JSON.stringify(file)), catalogue.runs[0]);
  const alone = server(Object.fromEntries(Object.entries(parts).map(([id, part]) => [`runs/${plain.id}.${id}.json`, JSON.stringify(part)])));
  for (const id of ["concentration-na", "concentration-k", "junction-gate"]) await loadPart(plain, id, { root: null, fetcher: alone.fetcher });
  for (const [id, record] of plain.records) assert.deepEqual([...run.records.get(id).array], [...record.array], id);
  assert.equal(alone.asked.length, 3);
});

test("an error names the file and the part; a file that could not be fetched is asked for again", async () => {
  const { runs, catalogue, file, entry } = folderOf("errors");
  const { replays, files } = await packageParts(catalogue, { runsDir: runs, together: new Set(["e07-v1"]) });
  const name = files[0].path;
  let up = false;
  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    return up ? { ok: true, status: 200, json: async () => JSON.parse(files[0].text) } : { ok: false, status: 503 };
  };
  const run = openReplay(JSON.parse(JSON.stringify(file)), replays.runs[0]);
  await assert.rejects(loadPart(run, "junction-gate", { root: null, fetcher }), new RegExp(`^Error: ${name.replace(/\./g, "\\.")} \\(the part junction-gate\\) answered 503$`));
  up = true;
  await loadPart(run, "junction-gate", { root: null, fetcher });
  assert.equal(asked.length, 2, "asked for again after it failed");
  // A file of another run's parts, one without the part, one that holds a part twice.
  const other = JSON.parse(files[0].text);
  const serve = (body) => async () => ({ ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(body)) });
  const fresh = () => openReplay(JSON.parse(JSON.stringify(file)), replays.runs[0]);
  await assert.rejects(loadPart(fresh(), "junction-gate", { root: null, fetcher: serve({ ...other, run: "another-run" }) }), new RegExp(`\\(the part junction-gate\\): the file holds parts of run another-run, not of ${entry.id}`));
  await assert.rejects(loadPart(fresh(), "junction-gate", { root: null, fetcher: serve({ ...other, parts: other.parts.filter((part) => part.part !== "junction-gate") }) }), /\(the part junction-gate\): the file holds no part junction-gate$/);
  await assert.rejects(loadPart(fresh(), "junction-gate", { root: null, fetcher: serve({ ...other, parts: [...other.parts, other.parts[0]] }) }), /its part junction-gate is there twice/);
  const short = JSON.parse(JSON.stringify(other));
  short.parts[0].payload.data = short.parts[0].payload.data.slice(0, 40);
  await assert.rejects(loadPart(fresh(), "junction-gate", { root: null, fetcher: serve(short) }), /\(the part junction-gate\): the part junction-gate is \d+ bytes long, not the \d+ the run states/);
});

test("the adapter writes one file a part whatever the overlay says, and leaves the word out of the catalogue", async () => {
  const { spawnSync } = await import("node:child_process");
  const tool = (name, args) => spawnSync("python3", [path.join(ROOT, "tools", name), ...args], { encoding: "utf8" });
  const fixtures = path.join(scratch, "fixtures"), out = path.join(scratch, "adapted");
  assert.equal(tool("make_run_fixture.py", ["--out", fixtures]).status, 0);
  const overlay = JSON.parse(readFileSync(path.join(fixtures, "overlay.json"), "utf8"));
  overlay.experiments["example-sheet"].parts_together = true;
  writeFileSync(path.join(scratch, "together.json"), JSON.stringify(overlay));
  const done = tool("adapt_run.py", ["--experiment", "example-sheet", "--root", path.join(fixtures, "run-example"), "--run", "invented-numbers", "--overlay", path.join(scratch, "together.json"), "--out", out]);
  assert.equal(done.status, 0, done.stderr);
  const index = JSON.parse(readFileSync(path.join(out, "index.json"), "utf8"));
  assert.equal("parts_together" in index.experiments.find((item) => item.id === "example-sheet"), false);
  const [run] = index.runs;
  assert.ok(run.parts.length > 1 && run.parts.every((part) => part.file === `runs/${run.id}.${part.id}.json` && existsSync(path.join(out, path.basename(part.file)))), "one file a part");
});

test("the shapes of a part file and of a file of several are checked", () => {
  const part = { format: PART_FORMAT, run: "r", part: "a", payload: { encoding: "base64", data: "" } };
  assert.deepEqual(validatePart(part, "r", "a"), []);
  assert.deepEqual(validatePart(part, "r", "b"), ["the file holds a of run r, not b of r"]);
  assert.deepEqual(validatePart({ ...part, format: PARTS_FORMAT }, "r"), [`the file is ${PARTS_FORMAT}, not ${PART_FORMAT}`]);
  assert.deepEqual(validatePart({ ...part, payload: { encoding: "hex", data: "" } }, "r"), ["its arrays must be base64"]);
  assert.deepEqual(validateParts({ format: PARTS_FORMAT, run: "r", parts: [part, { ...part, part: "b" }] }, "r"), []);
  assert.deepEqual(validateParts({ format: PARTS_FORMAT, run: "r", parts: [] }, "r"), ["the file lists no parts"]);
  assert.deepEqual(validateParts({ format: PARTS_FORMAT, run: "r", parts: [part, part] }, "r"), ["its part a is there twice"]);
  assert.deepEqual(validateParts({ format: PARTS_FORMAT, run: "r", parts: [{ ...part, run: "s" }] }, "r"), ["its part a: the file holds a of run s, not a part of r"]);
  assert.deepEqual(validateParts(part, "r"), [`the file is ${PART_FORMAT}, not ${PARTS_FORMAT}`]);
});

// The runs folder on this machine, where it is there: with every experiment listed, the page stays within what one version of
// an artifact holds (511 files, the page among them), every published file of a run under the limit.
const RUNS = DEFAULT_RUNS;
test("with every experiment listed, the published page holds fewer than 511 files", { skip: existsSync(path.join(RUNS, "index.json")) ? false : "no runs folder here" }, async () => {
  const index = await readReplays(RUNS);
  const all = publishedReplays({ ...index, experiments: index.experiments.map((item) => (item.part_of ? item : { ...item, listed: true })) }, {});
  const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "overlay.json"), "utf8"));
  const { replays, files } = await packageParts(all, { runsDir: RUNS, together: partsTogether(overlay) });
  const published = new Set(replays.runs.flatMap((run) => [run.file, ...(run.parts || []).map((part) => part.file)]));
  for (const file of files) assert.ok(Buffer.byteLength(file.text) < RUN_FILE_LIMIT, `${file.path} is under the limit`);
  // The page, the runs' files, and some 102 files that are no run (proteins, machines, shapes, benches, model systems): kept under the limit with room.
  assert.ok(published.size + 1 + 102 < 511 - 20, `${published.size} files of runs`);
});
