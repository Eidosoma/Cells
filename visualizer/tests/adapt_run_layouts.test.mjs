// The run adapter on packages the engine wrote before and after its second source move (D188's
// move 2, on main before b5d3faf0: `cells.run_view`, `cells.io` and `cells.window_io` became
// `cells.records.run_view`, `cells.records.io` and `cells.records.window_io`). Both are real
// views of the same five unit-test worlds, made by tools/make_engine_view_fixture.sh:
// tests/engine-views/run-view-050aa741 (written at 050aa741, before the move) and
// tests/engine-views/run-view-b5d3faf0 (at b5d3faf0, after it). Nothing here runs the engine or
// makes a fixture: the adapter reads the kept files only.
//
//   node --test tests/adapt_run_layouts.test.mjs
//
// What the adapter's own names of the engine decide is the format's ID of a view
// (`cells.run_view@1`, VIEW_FORMAT), which the move did not change; its comments name the
// writer's functions. It checks no module path of a package. So "both layouts" are held here as
// the same files read alike, and a folder of neither shape is refused as before. These views name
// no engine source (an export has no execution snapshot's record), so a package's stated source
// after the move is not exercised by them.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "adapt_run.py");
const VIEWS = path.join(ROOT, "tests", "engine-views");
const BEFORE = "050aa741", AFTER = "b5d3faf0";
const WORLDS = ["secretion", "subset", "increments", "kinds", "division"];
const EXPERIMENT = "engine-views";

// On disk under out/, as the laws tests keep theirs: /tmp is memory on the project's machine.
mkdirSync(path.join(ROOT, "out"), { recursive: true });
const scratch = mkdtempSync(path.join(ROOT, "out", "adapt-layouts-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const folderOf = (revision) => path.join(VIEWS, `run-view-${revision}`);
const walk = (folder, base = folder) => readdirSync(folder, { withFileTypes: true }).flatMap((item) => (item.isDirectory() ? walk(path.join(folder, item.name), base) : [path.relative(base, path.join(folder, item.name))])).sort();

const OVERLAY = path.join(scratch, "overlay.json");
writeFileSync(OVERLAY, JSON.stringify({ format: "cells.visualizer.replay_overlay@1", experiments: { [EXPERIMENT]: { adapter: "standard-history", development: true, label: "The run view's writer (test fixture)", plain: "Unit-test worlds the engine's run-view writer wrote, before and after a source move.", sources: [], engine_entities: [], outcome: { judged: false, status: "A development run: not judged" }, parameters: {}, readouts: {}, events: { current: { label: "Electrode current", plain: "The electrode's current changes." } }, stops: { complete: { label: "Ran to its end" } } } } }));

/** Adapt the named worlds of one folder of views into `out`; the adapter's result. */
function adapt(root, worlds, out) {
  const selection = path.join(scratch, `selection-${path.basename(out)}.json`);
  writeFileSync(selection, JSON.stringify({ [EXPERIMENT]: { evidence_folder: path.basename(root), runs: worlds } }));
  return spawnSync("python3", ["-I", TOOL, "--experiment", EXPERIMENT, "--root", root, ...worlds.flatMap((world) => ["--run", world]), "--overlay", OVERLAY, "--selection", selection, "--out", out], { encoding: "utf8" });
}

/** Every leaf where two parsed files differ, as [path, before, after]. */
function differences(a, b, at = []) {
  if (a && b && typeof a === "object" && typeof b === "object" && Array.isArray(a) === Array.isArray(b) && (!Array.isArray(a) || a.length === b.length)) {
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].flatMap((key) => differences(a[key], b[key], [...at, key]));
  }
  return JSON.stringify(a) === JSON.stringify(b) ? [] : [[at.join("."), a, b]];
}

test("the writer's views of the five worlds are the same files before and after the move, but for the label the script plants", () => {
  for (const [revision, full] of [[BEFORE, "050aa741ddff540971169225d7ccd275c2e89462"], [AFTER, "b5d3faf064444db7dbc9321ec0f7e77c9ccc9ee2"]]) {
    const note = readFileSync(path.join(folderOf(revision), "README.md"), "utf8");
    assert.match(note, new RegExp(`^# Runs written by the engine's run-view writer \\(${revision}\\)`));
    assert.ok(note.includes(full), `${revision}: its note names the revision it was written at`);
  }
  for (const world of WORLDS) {
    const files = walk(path.join(folderOf(BEFORE), world));
    assert.deepEqual(walk(path.join(folderOf(AFTER), world)), files, `${world}: the same files`);
    for (const file of files) {
      const [a, b] = [BEFORE, AFTER].map((revision) => readFileSync(path.join(folderOf(revision), world, file)));
      if (world === "secretion" && file === "view.json") {
        assert.deepEqual(differences(JSON.parse(a), JSON.parse(b)), [["run.revision", BEFORE, AFTER]], "only the caller's label the script plants");
      } else assert.ok(a.equals(b), `${world}/${file}: the same bytes`);
    }
    const view = readJson(path.join(folderOf(AFTER), world, "view.json"));
    assert.equal(view.format, "cells.run_view@1", `${world}: the format's ID, which the move did not change`);
    assert.equal(view.run.source, undefined, `${world}: run from an export, so no engine source is stated`);
  }
});

test("the adapter packages each world of both layouts alike: the same files, the same bytes, but the planted label and the line that names it", () => {
  const out = Object.fromEntries([BEFORE, AFTER].map((revision) => [revision, path.join(scratch, `out-${revision}`)]));
  for (const revision of [BEFORE, AFTER]) {
    const done = adapt(folderOf(revision), WORLDS, out[revision]);
    assert.equal(done.status, 0, `the adapter failed on the views written at ${revision}:\n${done.stderr}`);
  }
  const files = readdirSync(out[BEFORE]).sort();
  assert.deepEqual(readdirSync(out[AFTER]).sort(), files);
  assert.equal(files.filter((name) => /^engine-views--[a-z]+\.json$/.test(name)).length, WORLDS.length, "a run file for each world");
  for (const name of files) {
    const [a, b] = [BEFORE, AFTER].map((revision) => readFileSync(path.join(out[revision], name)));
    if (name !== "engine-views--secretion.json") {
      assert.ok(a.equals(b), `${name}: the same bytes`);
      continue;
    }
    const changed = differences(JSON.parse(a), JSON.parse(b));
    // Exactly two leaves: the run's label, and the one line of the derivation that names it (found by its words, not its place).
    assert.equal(changed.length, 2, JSON.stringify(changed));
    assert.deepEqual(changed.find(([at]) => at === "view.run.revision")?.slice(1), [BEFORE, AFTER]);
    const line = changed.find(([at]) => at.startsWith("view.derivation."));
    assert.ok(line, "the other is a line of the derivation");
    const [, said, saidAfter] = line;
    assert.ok(said.includes(`The revision given, ${BEFORE}, is the caller's label`), said);
    assert.equal(saidAfter, said.replace(`The revision given, ${BEFORE}, is the caller's label`, `The revision given, ${AFTER}, is the caller's label`), "the line that names the label, and nothing else of it");
    assert.match(saidAfter, /is the caller's label for the run \(run\.revision\), not the engine's own record of its source\.$/);
  }
});

test("a folder of neither shape is refused at both revisions, as before: a view of another format, or no view and no history", () => {
  for (const revision of [BEFORE, AFTER]) {
    const copy = path.join(scratch, `neither-${revision}`);
    cpSync(folderOf(revision), copy, { recursive: true });
    // A view.json that is not the writer's format.
    const file = path.join(copy, "secretion", "view.json");
    const view = readJson(file);
    view.format = "cells.run_view@2";
    writeFileSync(file, JSON.stringify(view));
    const other = adapt(copy, ["secretion"], path.join(scratch, `neither-${revision}-format`));
    assert.notEqual(other.status, 0, `${revision}: another format`);
    assert.match(other.stderr, /secretion: its view\.json is not a run view \(cells\.run_view@1\)/);
    assert.ok(!existsSync(path.join(scratch, `neither-${revision}-format`, "index.json")), "nothing is catalogued");
    // No view and none of the shared output path's files.
    rmSync(file);
    rmSync(path.join(copy, "secretion", "trajectory.npz"));
    const none = adapt(copy, ["secretion"], path.join(scratch, `neither-${revision}-none`));
    assert.notEqual(none.status, 0, `${revision}: neither shape`);
    assert.match(none.stderr, /secretion: neither trajectory\.npz nor windows\.jsonl is in the run's folder/);
    assert.ok(!existsSync(path.join(scratch, `neither-${revision}-none`, "index.json")), "nothing is catalogued");
  }
});
