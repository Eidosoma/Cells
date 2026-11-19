// The experiment package's validator (tools/check_package.py; schema/EXPERIMENT_PACKAGE.md) on its conformance set, and
// the run adapter reading a manifest. The packages are built here, in the test's own scratch folder, from the fixtures
// tracked under tests/engine-views/: a world the engine's run-view writer wrote is copied as two arms, given a sidecar
// each, a refused pick, a summary of one sweep and a manifest (all made up, and said to be). Each breach of the contract
// breaks one thing of a copy and must give its own code; the sound packages must pass, and an unmanifested fixture
// folder passes with its note. The adapter must package a run folder with a manifest to the same bytes as the same
// folder without one. The schema file must be what the validator writes, and the contract must name exactly its codes
// and fields. No world is compiled, no engine is run and no browser is started.
//
//   node --test tests/check_package.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, symlinkSync, unlinkSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHECK = path.join(ROOT, "tools", "check_package.py");
const ADAPT = path.join(ROOT, "tools", "adapt_run.py");
const VIEWS = path.join(ROOT, "tests", "engine-views");
const WORLD = path.join(VIEWS, "run-view-89bd2ffb", "secretion");
const EXPERIMENT = "made-up-package";

// On disk under out/, as the adapter's tests keep theirs: /tmp is memory on the project's machine.
mkdirSync(path.join(ROOT, "out"), { recursive: true });
const scratch = mkdtempSync(path.join(ROOT, "out", "check-package-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const writeJson = (file, data) => writeFileSync(file, JSON.stringify(data, null, 1));
const edit = (file, change) => {
  const data = readJson(file);
  change(data);
  writeJson(file, data);
};

/** The validator on a folder: its exit status and its report (--json). Runs as its own process, awaited. */
function check(folder) {
  return new Promise((resolve) => {
    const child = spawn("python3", ["-I", CHECK, "--json", folder], { stdio: ["ignore", "pipe", "pipe"] });
    let out = "", err = "";
    child.stdout.on("data", (chunk) => (out += chunk));
    child.stderr.on("data", (chunk) => (err += chunk));
    child.on("close", (status) => {
      let report = null;
      try {
        report = JSON.parse(out);
      } catch {
        report = null;
      }
      resolve({ status, report, stderr: err });
    });
  });
}
const codes = (report, key = "problems") => [...new Set(report[key].map((item) => item.code))].sort();

// The world's own times and cells, as the adapter reads them from its view: what a sidecar must state.
const shape = JSON.parse(
  spawnSync("python3", ["-I", "-"], {
    encoding: "utf8",
    input: `import json, sys\nsys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})\nimport adapt_run as a\nfrom pathlib import Path\nfolder = Path(${JSON.stringify(WORLD)})\nview = json.load(open(folder / "view.json"))\nbases = {b["id"]: b for b in view["time"]["bases"]}\nline = next(i for i in ("observation", "accepted") if i in bases and bases[i].get("files"))\n_, times, _ = a.view_rows("w", folder, bases[line], bases[line].get("array"))\ncells = [c for c in next(s for s in view["sets"] if s["id"] == "cell")["ids"] if c is not None]\nprint(json.dumps({"times": list(times), "cells": cells, "models": view["run"]["engine_models"]}))\n`,
  }).stdout,
);

const MANIFEST = {
  format: "cells.experiment_package@1",
  level: "source",
  experiment: { id: EXPERIMENT, title: "A made-up package (test fixture)", status: "Made up for a test: not a run of any experiment" },
  engine: { models: shape.models },
  visibility: "public",
  licence: "CC-BY-4.0",
  summary: "summary.json",
  packages: [
    { arm: "alpha", kind: "cells.run_view@1", path: "alpha", sidecars: ["concentration.json"], label: "Alpha" },
    { arm: "beta", kind: "cells.run_view@1", path: "beta", sidecars: ["concentration.json"], label: "Beta" },
  ],
  refused: [{ arm: "gamma", file: "REFUSED.json" }],
};

/** A run folder as the engine side writes one, with no manifest: two arms of one world, a sidecar beside each, a refused pick and a summary. */
function bare(name) {
  const folder = path.join(scratch, name);
  mkdirSync(folder, { recursive: true });
  for (const [arm, shift] of [["alpha", 0], ["beta", 1]]) {
    cpSync(WORLD, path.join(folder, arm), { recursive: true });
    writeJson(path.join(folder, arm, "concentration.json"), {
      format: "cells.experiment_quantity@1",
      quantity: { id: "concentration", label: "A made-up concentration in each cell", unit: "mM" },
      times_s: shape.times,
      cells: shape.cells,
      values: shape.times.map((_, row) => shape.cells.map((_, k) => row + k + shift)),
    });
  }
  mkdirSync(path.join(folder, "gamma"));
  writeJson(path.join(folder, "gamma", "REFUSED.json"), { arm: "gamma", g: 4, status: "refused", error: "a made-up refusal", note: "Made up for a test." });
  writeJson(path.join(folder, "summary.json"), {
    format: "cells.experiment_summary@1",
    experiment: EXPERIMENT,
    note: "Made up for a test: invented numbers.",
    sweeps: [{ id: "coupling", label: "A made-up sweep", parameter: { id: "g", label: "A made-up coupling", unit: "1" }, readouts: [{ id: "first", label: "A made-up readout", unit: "mM" }], arms: [{ arm: "alpha", parameter: 1, readouts: { first: 1 } }, { arm: "beta", parameter: 2, readouts: { first: 2 } }] }],
  });
  return folder;
}
/** The same folder with its manifest. */
function sound(name, change = () => {}) {
  const folder = bare(name);
  const manifest = structuredClone(MANIFEST);
  change(manifest);
  writeJson(path.join(folder, "package.json"), manifest);
  return folder;
}

// ---------------------------------------------------------------- the conformance set

const same = (manifest) => manifest; // the sound manifest, as written
// Each breach: what it breaks, how, and the problem codes it must give (and nothing else). A note's case gives its note and passes.
const BREACHES = [
  ["the manifest is not JSON", (f) => writeFileSync(path.join(f, "package.json"), "{ not json"), ["json.invalid"]],
  ["the manifest is over the cap", (f) => edit(path.join(f, "package.json"), (m) => (m.experiment.plain = "x".repeat(1100000))), ["size.cap"]],
  ["another format", (f) => edit(path.join(f, "package.json"), (m) => (m.format = "cells.experiment_package@2")), ["manifest.format"]],
  ["the play level", (f) => edit(path.join(f, "package.json"), (m) => (m.level = "play")), ["manifest.level"]],
  ["no experiment id", (f) => edit(path.join(f, "package.json"), (m) => delete m.experiment.id), ["manifest.missing"]],
  ["packages not a list", (f) => edit(path.join(f, "package.json"), (m) => (m.packages = "alpha")), ["manifest.type"]],
  ["a date that is not a day", (f) => edit(path.join(f, "package.json"), (m) => (m.made = "yesterday")), ["manifest.type"]],
  ["an arm that is not an id", (f) => edit(path.join(f, "package.json"), (m) => Object.assign(m.packages[1], { arm: "Beta_2", path: "Beta_2" })), ["manifest.id"]],
  ["no visibility", (f) => edit(path.join(f, "package.json"), (m) => delete m.visibility), ["manifest.visibility"]],
  ["a visibility of no known word", (f) => edit(path.join(f, "package.json"), (m) => (m.visibility = "secret")), ["manifest.visibility"]],
  ["no licence", (f) => edit(path.join(f, "package.json"), (m) => delete m.licence), ["manifest.licence"]],
  ["a home folder in the manifest", (f) => edit(path.join(f, "package.json"), (m) => (m.experiment.plain = "Written in /home/made-up/runs.")), ["manifest.machine-path"]],
  ["a drive letter in the manifest", (f) => edit(path.join(f, "package.json"), (m) => (m.experiment.sources = [{ path: "C:\\made-up\\runs\\note.md" }])), ["manifest.machine-path"]],
  ["an absolute path", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].path = "/alpha")), ["path.absolute"]],
  ["a path that leaves the folder", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].path = "../alpha")), ["path.outside"]],
  ["a path of no file name", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].path = "al pha")), ["path.form"]],
  ["a path that names nothing", (f) => edit(path.join(f, "package.json"), (m) => (m.summary = "summaries.json")), ["path.missing"]],
  ["a folder where a file is wanted", (f) => edit(path.join(f, "package.json"), (m) => (m.summary = "alpha")), ["path.kind"]],
  ["a link inside a package", (f) => symlinkSync("../summary.json", path.join(f, "alpha", "linked.json")), ["path.link"]],
  ["an arm twice", (f) => edit(path.join(f, "package.json"), (m) => m.packages.push({ ...m.packages[0] })), ["package.arm-twice"]],
  ["an arm both a package and refused", (f) => edit(path.join(f, "package.json"), (m) => (m.refused[0].arm = "alpha")), ["package.arm-twice"]],
  ["a path that is not its arm's folder", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].path = "beta")), ["package.path"]],
  ["no view", (f) => unlinkSync(path.join(f, "alpha", "view.json")), ["view.missing"]],
  ["a view of another format", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.format = "cells.run_view@2")), ["view.format"]],
  ["a view that is not JSON", (f) => writeFileSync(path.join(f, "alpha", "view.json"), "[1, 2"), ["json.invalid"]],
  ["a view with no time base", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.time.bases = [])), ["view.time"]],
  ["a time base's file not there", (f) => edit(path.join(f, "alpha", "view.json"), (v) => v.time.bases.forEach((b) => (b.files[0].file = "elsewhere.npz"))), ["view.file-missing"]],
  ["an array file that is no zip", (f) => writeFileSync(path.join(f, "alpha", "trajectory.npz"), "not a zip"), ["view.array-file"]],
  ["a time base's rows that are not its file's", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.time.bases.find((b) => b.id === "observation").files[0].rows = [0, 7])), ["view.rows"]],
  ["a record's array not in its file", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.records.find((r) => r.id === "observed_membrane_transferred").array = "no_such_array")), ["view.array-missing"]],
  ["a record on no time base", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.records[0].base = "elsewhen")), ["view.record"]],
  ["a record whose shape does not fit its axes", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.records.find((r) => r.id === "electrode_charge_transferred_C").axes = ["time", "cell"])), ["view.shape"]],
  ["a sidecar not of a plain name", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].sidecars = ["Concentration.JSON"])), ["sidecar.name"]],
  ["a sidecar outside its arm's folder", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[0].sidecars = ["../summary.json"])), ["path.outside"]],
  ["a sidecar of another format", (f) => edit(path.join(f, "alpha", "concentration.json"), (s) => (s.format = "cells.experiment_quantity@2")), ["sidecar.format"]],
  ["a sidecar of other cells", (f) => edit(path.join(f, "alpha", "concentration.json"), (s) => (s.cells = ["elsewhere"])), ["sidecar.cells"]],
  ["a sidecar of other times", (f) => edit(path.join(f, "alpha", "concentration.json"), (s) => (s.times_s = s.times_s.map((t) => t + 0.25))), ["sidecar.times"]],
  ["a refusal that is not one", (f) => edit(path.join(f, "gamma", "REFUSED.json"), (r) => (r.status = "complete")), ["refused.format"]],
  ["a refused pick with a view", (f) => cpSync(path.join(WORLD, "view.json"), path.join(f, "gamma", "view.json")), ["refused.has-view"]],
  ["a refusal with no value of the parameter", (f) => edit(path.join(f, "gamma", "REFUSED.json"), (r) => delete r.g), ["refused.parameter"]],
  ["refused picks with no summary", (f) => edit(path.join(f, "package.json"), (m) => delete m.summary), ["refused.sweep"]],
  ["a summary of another format", (f) => edit(path.join(f, "summary.json"), (s) => (s.format = "cells.experiment_summary@2")), ["summary.format"]],
  ["a summary the adapter refuses", (f) => edit(path.join(f, "summary.json"), (s) => s.sweeps[0].arms.pop()), ["summary.content"]],
  ["provenance the views do not state", (f) => edit(path.join(f, "package.json"), (m) => (m.engine.models = ["resolved_pump_tissue@3"])), ["engine.provenance"]],
  ["a view the adapter refuses", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.records.find((r) => r.id === "membrane_transferred").sign.from = "elsewhere")), ["adapter.refused"]],
  ["a machine path the adapter would package", (f) => edit(path.join(f, "alpha", "view.json"), (v) => (v.constants.find((c) => c.id === "temperature").from = "/Users/made-up/definition.json")), ["adapter.machine-path"]],
];
const NOTES = [
  ["a field the reader does not know", (f) => edit(path.join(f, "package.json"), (m) => (m.colour = "made up")), "manifest.unknown-field"],
  ["a kind the reader does not know", (f) => edit(path.join(f, "package.json"), (m) => (m.packages[1].kind = "cells.made_up_kind@1")), "package.kind-unknown"],
  ["a folder with a view that is not listed", (f) => cpSync(WORLD, path.join(f, "delta"), { recursive: true }), "package.not-listed"],
];

test("the sound packages pass: the made-up package, the eight worlds and the windowed loop, each with a manifest; and the check writes nothing", async () => {
  const views = path.join(scratch, "eight-worlds");
  cpSync(path.join(VIEWS, "run-view-89bd2ffb"), views, { recursive: true });
  const loop = path.join(scratch, "loop");
  cpSync(path.join(VIEWS, "loop-b08af640"), loop, { recursive: true });
  for (const folder of [views, loop]) {
    const arms = readdirSync(folder).filter((name) => existsSync(path.join(folder, name, "view.json"))).sort();
    writeJson(path.join(folder, "package.json"), { format: "cells.experiment_package@1", level: "source", experiment: { id: "engine-views", title: "Worlds the engine's run-view writer wrote (test fixture)" }, visibility: "public", licence: "MIT", packages: arms.map((arm) => ({ arm, kind: "cells.run_view@1", path: arm })) });
  }
  const made = sound("sound");
  const before = readdirSync(made, { recursive: true }).sort().map((name) => [name, statSync(path.join(made, name)).mtimeMs]);
  const results = await Promise.all([made, views, loop].map(check));
  for (const [folder, { status, report, stderr }] of [made, views, loop].map((folder, k) => [folder, results[k]])) {
    assert.equal(status, 0, `${path.basename(folder)}: ${stderr}\n${JSON.stringify(report?.problems, null, 1)}`);
    assert.deepEqual(report.problems, []);
    assert.deepEqual(codes(report, "notes"), [], `${path.basename(folder)}: a sound package needs no note`);
    assert.ok(report.packages.length >= 1 && report.packages.every((item) => item.read), `${path.basename(folder)}: every package is read by the adapter`);
  }
  const [{ report }] = results;
  assert.deepEqual(report.packages.map((item) => [item.arm, item.run, item.sidecars]), [["alpha", `${EXPERIMENT}--alpha`, ["concentration.json"]], ["beta", `${EXPERIMENT}--beta`, ["concentration.json"]]]);
  assert.deepEqual(report.refused, [{ arm: "gamma", file: "REFUSED.json" }]);
  assert.deepEqual([report.visibility, report.licence, report.summary], ["public", "CC-BY-4.0", { file: "summary.json", sweeps: 1 }]);
  assert.equal(results[1].report.packages.length, 8, "the eight worlds");
  assert.deepEqual(readdirSync(made, { recursive: true }).sort().map((name) => [name, statSync(path.join(made, name)).mtimeMs]), before, "the check wrote nothing into the package");
});

test("an unmanifested fixture folder passes with its note, and says what a manifest would state", async () => {
  const [folder, one] = await Promise.all([check(path.join(VIEWS, "run-view-89bd2ffb")), check(path.join(VIEWS, "loop-b08af640", "planarian-b08af640"))]);
  assert.equal(folder.status, 0, JSON.stringify(folder.report?.problems));
  assert.deepEqual(codes(folder.report, "notes"), ["manifest.none"]);
  assert.equal(folder.report.packages.length, 8);
  const would = folder.report.would_state;
  assert.deepEqual([would.format, would.level, would.visibility, would.licence], ["cells.experiment_package@1", "source", null, null], "what the folder cannot say is null");
  assert.deepEqual(would.packages.map((item) => item.arm), ["condition", "division", "dose", "factors", "increments", "kinds", "secretion", "subset"]);
  // A folder that is itself one package (the windowed loop) is read as that arm.
  assert.equal(one.status, 0, JSON.stringify(one.report?.problems));
  assert.deepEqual(codes(one.report, "notes"), ["folder.one-package"]);
  assert.equal(one.report.packages[0].arm, "planarian-b08af640");
  // The made-up folder without its manifest: its sidecars are named by nothing, and noted; its refused pick is found.
  const bareReport = (await check(bare("bare"))).report;
  assert.deepEqual(codes(bareReport, "notes"), ["manifest.none", "sidecar.unnamed"]);
  assert.deepEqual(bareReport.would_state.packages.map((item) => item.sidecars), [["concentration.json"], ["concentration.json"]]);
  assert.deepEqual(bareReport.would_state.refused, [{ arm: "gamma", file: "REFUSED.json" }]);
  // Folders with no manifest, each with one thing of its own: [what, how, problems, notes].
  const rows = [
    ["an index that chooses no run", (f) => writeJson(path.join(f, "index.json"), { selected: [] }), ["index.content"], ["manifest.none"]],
    ["an index with a machine's path", (f) => writeJson(path.join(f, "index.json"), { packages: ["alpha", "beta"].map((arm) => ({ arm, view: "written", directory: `/home/made-up/${arm}`, sidecar: "concentration.json" })) }), [], ["index.machine-path", "manifest.none"]],
    ["a package's folder that is no id", (f) => cpSync(path.join(f, "alpha"), path.join(f, "Alpha_2"), { recursive: true }), [], ["manifest.none", "package.not-id", "sidecar.unnamed"]],
  ];
  const folders = rows.map(([label, change], k) => {
    const folder = bare(`bare-${k}`);
    change(folder);
    return folder;
  });
  const old = path.join(scratch, "older");
  mkdirSync(path.join(old, "a-run"), { recursive: true });
  writeJson(path.join(old, "a-run", "resolved_config.json"), { note: "made up: a run of the shared output path, with no view" });
  const results = await Promise.all([...folders, old].map(check));
  rows.forEach(([label, , problems, notes], k) => {
    assert.deepEqual(codes(results[k].report), problems, label);
    assert.deepEqual(codes(results[k].report, "notes"), notes, label);
    assert.equal(results[k].status, problems.length ? 1 : 0, label);
  });
  assert.deepEqual([codes(results[3].report), codes(results[3].report, "notes")], [["folder.no-package"], ["manifest.none", "package.no-view"]], "a run with no view is no package");
});

test("each breach of the contract gives its own code, and a note is said and the rest still read", async () => {
  const cases = [...BREACHES.map(([label, change, expected]) => ({ label, change, expected, status: 1 })), ...NOTES.map(([label, change, note]) => ({ label, change, expected: [], note, status: 0 }))];
  const folders = cases.map(({ change }, k) => {
    const folder = sound(`case-${String(k).padStart(2, "0")}`, same);
    change(folder);
    return folder;
  });
  const results = [];
  for (let start = 0; start < folders.length; start += 6) results.push(...(await Promise.all(folders.slice(start, start + 6).map(check))));
  cases.forEach(({ label, expected, note, status }, k) => {
    const { status: got, report, stderr } = results[k];
    assert.ok(report, `${label}: no report (${stderr})`);
    assert.equal(got, status, `${label}: exit ${got}; ${JSON.stringify(report.problems)}`);
    assert.deepEqual(codes(report), expected, `${label}: ${JSON.stringify(report.problems.map((item) => item.says))}`);
    if (note) assert.ok(codes(report, "notes").includes(note), `${label}: the note ${note}`);
    for (const item of report.problems) assert.ok(item.says && item.file, `${label}: a problem names its file and says it in a sentence`);
  });
  // A kind the reader does not know: named, not read, and the rest read.
  const unknown = results[cases.findIndex((item) => item.note === "package.kind-unknown")].report;
  assert.deepEqual(unknown.packages.map((item) => [item.arm, item.read]), [["alpha", true], ["beta", false]]);
  // Every code the validator has that the conformance set does not hold is a short, named list.
  const held = new Set(cases.flatMap((item) => [...item.expected, item.note]).filter(Boolean));
  const all = Object.keys(JSON.parse(spawnSync("python3", ["-I", CHECK, "--codes"], { encoding: "utf8" }).stdout));
  // Those of a folder with no manifest are held by the test above; the two faults of a reader's own cannot be planted.
  assert.deepEqual(all.filter((code) => !held.has(code)).sort(), ["adapter.error", "check.error", "folder.no-package", "folder.one-package", "index.content", "index.machine-path", "manifest.none", "package.no-view", "package.not-id", "sidecar.unnamed"].sort(), "the codes no breach here gives");
});

test("a wrong call exits with 2", () => {
  for (const args of [[], [path.join(scratch, "no-such-folder")], ["--schema", "--codes"], ["--schema", VIEWS]]) {
    assert.equal(spawnSync("python3", ["-I", CHECK, ...args], { encoding: "utf8" }).status, 2, args.join(" "));
  }
  const empty = path.join(scratch, "empty");
  mkdirSync(empty);
  const done = spawnSync("python3", ["-I", CHECK, "--json", empty], { encoding: "utf8" });
  assert.equal(done.status, 1);
  assert.deepEqual(codes(JSON.parse(done.stdout)), ["folder.no-package"]);
});

// ---------------------------------------------------------------- the adapter reads a manifest

const OVERLAY = path.join(scratch, "overlay.json");
writeJson(OVERLAY, { format: "cells.visualizer.replay_overlay@1", experiments: { [EXPERIMENT]: { adapter: "standard-history", development: true, label: "A made-up package (test fixture)", plain: "Made up for a test.", sources: [], engine_entities: [], outcome: { judged: false, status: "Made up for a test: not judged" }, parameters: {}, readouts: {}, events: {}, stops: { complete: { label: "Ran to its end" } }, summary: "summary.json", sidecar: "concentration.json", refused_picks: true } } });

/** The adapter on a run folder, its runs chosen as the selection's "index" chooses them, into `out`: [result, {file: bytes}]. */
function adapt(folder, out) {
  const selection = path.join(scratch, `selection-${path.basename(out)}.json`);
  writeJson(selection, { [EXPERIMENT]: { evidence_folder: path.basename(folder), runs: "index" } });
  const done = spawnSync("python3", ["-I", ADAPT, "--experiment", EXPERIMENT, "--root", folder, "--overlay", OVERLAY, "--selection", selection, "--out", out], { encoding: "utf8" });
  const files = done.status === 0 ? Object.fromEntries(readdirSync(out).sort().map((name) => [name, readFileSync(path.join(out, name))])) : {};
  return [done, files];
}

test("the adapter packages a run folder with a manifest to the same bytes as the same folder without one, with an index or neither", () => {
  const plain = bare("adapt-plain");
  const indexed = bare("adapt-index");
  writeJson(path.join(indexed, "index.json"), { packages: ["alpha", "beta"].map((arm) => ({ arm, view: "written", sidecar: "concentration.json" })) });
  const manifested = sound("adapt-manifest");
  const [base, before] = adapt(plain, path.join(scratch, "out-plain"));
  assert.equal(base.status, 0, base.stderr);
  for (const name of [`${EXPERIMENT}--alpha.json`, `${EXPERIMENT}--beta.json`, "index.json"]) assert.ok(name in before, `${name} is written`);
  assert.ok(Object.keys(before).length > 3, "and the runs' parts");
  const catalogue = JSON.parse(before["index.json"]);
  assert.deepEqual(catalogue.experiments[0].refused_picks, [{ arm: "gamma", sweep: "coupling", parameter: 4, file: "REFUSED.json" }], "the refused pick is named");
  assert.ok(JSON.parse(before[`${EXPERIMENT}--alpha.json`]).view.records.some((record) => record.id === "stated.concentration"), "the sidecar is read");
  for (const [label, folder] of [["an index", indexed], ["a manifest", manifested]]) {
    const [done, after] = adapt(folder, path.join(scratch, `out-${path.basename(folder)}`));
    assert.equal(done.status, 0, `${label}: ${done.stderr}`);
    assert.deepEqual(Object.keys(after), Object.keys(before), `${label}: the same files`);
    for (const name of Object.keys(before)) assert.ok(after[name].equals(before[name]), `${label}: ${name} is not the same bytes`);
  }
});

test("where a folder holds a manifest, the adapter takes its arms, sidecars and refused picks from it, and refuses one it cannot read", () => {
  const listed = (name, change) => {
    const folder = sound(name, change);
    return adapt(folder, path.join(scratch, `out-${name}`));
  };
  // One arm listed of the two folders with a view; no sidecar for it, though the overlay names one; no refused pick.
  const [done, files] = listed("adapt-one", (m) => {
    m.packages = [{ ...m.packages[0], sidecars: [] }];
    delete m.refused;
  });
  assert.equal(done.status, 0, done.stderr);
  const catalogue = JSON.parse(files["index.json"]);
  assert.deepEqual(catalogue.runs.map((run) => run.arm), ["alpha"], "the manifest's arms, not the folders that hold a view");
  assert.deepEqual(catalogue.experiments[0].refused_picks, [], "the manifest's refused picks, not the folders that hold REFUSED.json");
  assert.ok(!JSON.parse(files[`${EXPERIMENT}--alpha.json`]).view.records.some((record) => record.id.startsWith("stated.")), "the manifest's sidecars, in place of the overlay's");
  // A package of a kind the adapter does not read is named and left out.
  const [kinds, kindFiles] = listed("adapt-kind", (m) => (m.packages[1].kind = "cells.made_up_kind@1"));
  assert.equal(kinds.status, 0, kinds.stderr);
  assert.match(kinds.stderr, /the package beta is of the kind 'cells\.made_up_kind@1', which the adapter does not read; it is left out/);
  assert.deepEqual(JSON.parse(kindFiles["index.json"]).runs.map((run) => run.arm), ["alpha"]);
  // A manifest the adapter cannot read is refused, never passed over: nothing is written.
  for (const [label, change, reason] of [
    ["another format", (m) => (m.format = "cells.experiment_package@2"), /is not the manifest of a source package \(cells\.experiment_package@1, level source\)/],
    ["a path that is not its arm's", (m) => (m.packages[0].path = "beta"), /lists a package that is not read from the folder named as its arm \(arm, path\)/],
    ["an arm twice", (m) => m.packages.push({ ...m.packages[0] }), /names the arm alpha twice/],
    ["a sidecar of no plain name", (m) => (m.packages[0].sidecars = ["../concentration.json"]), /names a file beside it that is not a JSON file's plain name \(sidecars\)/],
  ]) {
    const name = `adapt-refused-${label.replace(/\W+/g, "-")}`;
    const [refused] = listed(name, change);
    assert.notEqual(refused.status, 0, label);
    assert.match(refused.stderr, reason, label);
    assert.ok(!existsSync(path.join(scratch, `out-${name}`, "index.json")), `${label}: nothing is catalogued`);
  }
  // The adapter itself reads a package from its own folder and from nowhere else, with or without the check before it:
  // a name its files give that leaves the folder, and a link, are refused, and nothing is written.
  for (const [label, breach, reason] of [
    ["a view's file that leaves the folder", (folder) => edit(path.join(folder, "alpha", "view.json"), (view) => { for (const base of view.time.bases) for (const part of base.files) part.file = `../beta/${part.file}`; }), /alpha: its view names a file of the time base \w+ that is not in the run's folder/],
    ["a link in a package", (folder) => symlinkSync(path.join(folder, "beta", "summary.json"), path.join(folder, "alpha", "kept-elsewhere.json")), /alpha holds a link \(kept-elsewhere\.json\): a run folder holds its files itself, and no link is followed/],
    ["a sidecar that is a link", (folder) => { unlinkSync(path.join(folder, "alpha", "concentration.json")); symlinkSync(path.join(folder, "beta", "concentration.json"), path.join(folder, "alpha", "concentration.json")); }, /alpha holds a link \(concentration\.json\)/],
    ["a manifest that is a link", (folder) => { const kept = path.join(scratch, "kept-manifest.json"); writeFileSync(kept, readFileSync(path.join(folder, "package.json"))); unlinkSync(path.join(folder, "package.json")); symlinkSync(kept, path.join(folder, "package.json")); }, /[\w-]+\/package\.json is a link: a file is read where it stands, and no link is followed/],
  ]) {
    const name = `adapt-outside-${label.replace(/\W+/g, "-")}`;
    const folder = sound(name);
    breach(folder);
    const [refused] = adapt(folder, path.join(scratch, `out-${name}`));
    assert.notEqual(refused.status, 0, label);
    assert.match(refused.stderr, reason, label);
    assert.ok(!existsSync(path.join(scratch, `out-${name}`, "index.json")), `${label}: nothing is catalogued`);
  }
});

// ---------------------------------------------------------------- the schema file and the contract, kept from drifting

test("the committed schema is what the validator writes from its field table, and the contract names exactly its codes and fields", () => {
  const written = spawnSync("python3", ["-I", CHECK, "--schema"], { encoding: "utf8" });
  assert.equal(written.status, 0, written.stderr);
  assert.equal(readFileSync(path.join(ROOT, "schema", "experiment_package.schema.json"), "utf8"), written.stdout, "schema/experiment_package.schema.json is not what `python3 -I tools/check_package.py --schema` writes: write it again");
  const contract = readFileSync(path.join(ROOT, "schema", "EXPERIMENT_PACKAGE.md"), "utf8");
  const all = JSON.parse(spawnSync("python3", ["-I", CHECK, "--codes"], { encoding: "utf8" }).stdout);
  const named = [...contract.matchAll(/^\| `([a-z]+\.[a-z-]+)` \| (problem|note) \|/gm)].map((match) => [match[1], match[2]]);
  assert.deepEqual(named.map(([code]) => code).sort(), Object.keys(all).sort(), "the contract's table of codes is the validator's");
  for (const [code, kind] of named) assert.equal(kind, all[code].kind, `${code}: its kind`);
  // Every field of the schema, by its path (a list's items as []), stands in the contract's table of fields, and no other.
  const fields = [];
  const walk = (node, at) => {
    for (const [name, item] of Object.entries(node.properties || {})) {
      const where = at ? `${at}.${name}` : name;
      fields.push(where);
      if (item.type === "object") walk(item, where);
      if (item.type === "array" && item.items?.type === "object") walk(item.items, `${where}[]`);
    }
  };
  walk(JSON.parse(written.stdout), "");
  const rows = [...contract.matchAll(/^\| `([a-z_]+(?:\[\])?(?:\.[a-z_]+(?:\[\])?)*)` \| (?:text|id|path|name|sidecar name|revision|day|true or false|object|list|one of)/gm)].map((match) => match[1].replace(/\[\]$/, ""));
  assert.deepEqual([...new Set(rows)].sort(), fields.sort(), "the contract's table of fields is the schema's");
});
