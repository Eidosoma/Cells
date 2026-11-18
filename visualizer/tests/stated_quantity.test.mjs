// A quantity the experiment states beside a run (schema/RUN_VIEW.md, "A quantity the experiment states"): the adapter
// copies `concentration.json` (cells.experiment_quantity@1) and `criterion.json` (cells.experiment_criterion@1, one
// threshold or two) as stated, at the replay's own times, where the run folder's index names the file; it refuses,
// with the reason, a file that does not fit the run. The page colours by the values, ticks a criterion's thresholds
// in its own words, says whose the quantity is, and carries the states as the driver states them, colouring nothing
// by them. The files are made up here, beside the synthetic world's run with a view (tools/make_run_fixture.py).
//
//   node --test tests/stated_quantity.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openReplay } from "../src/replay/source.js";
import { layersFor, readDeclarations } from "../src/layers/layers.js";
import { MARKS } from "../src/layers/marks/index.js";
import { reading, display } from "../src/replay/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const python = (args, input) => spawnSync("python3", args, { encoding: "utf8", input });

const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-stated-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const FIXTURES = path.join(scratch, "fixtures"), WORLD = path.join(FIXTURES, "run-world");
assert.equal(python([path.join(ROOT, "tools", "make_run_fixture.py"), "--out", FIXTURES]).status, 0);

// The viewed run's own times and cells, as the adapter reads them from its view.
const shape = JSON.parse(
  python(["-I", "-"], `import json, sys\nsys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})\nimport adapt_run as a\nfrom pathlib import Path\nfolder = Path(${JSON.stringify(path.join(WORLD, "viewed"))})\nview = json.load(open(folder / "view.json"))\nbases = {b["id"]: b for b in view["time"]["bases"]}\nline = next(i for i in ("observation", "accepted") if i in bases and bases[i].get("files"))\n_, times, count = a.view_rows("viewed", folder, bases[line], bases[line].get("array"))\ncells = [c for c in next(s for s in view["sets"] if s["id"] == "cell")["ids"] if c is not None]\nprint(json.dumps({"times": list(times), "cells": cells}))\n`).stdout
);
const ROWS = shape.times.length;

/** A stated file for the viewed run: the values climb from -3 by one each row, one more for each cell. */
function quantity(extra = {}) {
  return {
    format: "cells.experiment_quantity@1",
    quantity: { id: "concentration", label: "[S] in each cell, in µM, as the driver states it", unit: "uM" },
    times_s: shape.times,
    cells: shape.cells,
    values: shape.times.map((_, row) => shape.cells.map((_, k) => row - 3 + k)),
    ...extra,
  };
}
const criterion = (said, extra = {}) =>
  quantity({ format: "cells.experiment_criterion@1", quantity: { id: "score", label: "The criterion's score", unit: "1" }, criterion: { words: "A cell is epithelial above the threshold.", source: "A made-up driver, for this test", ...said }, ...extra });

/** Adapt the viewed run with `files` beside it, named by the folder's index as its `sidecar`. Returns { status, stderr, file }. */
function adapt(name, files, sidecar = Object.keys(files)) {
  for (const [file, data] of Object.entries(files)) writeFileSync(path.join(WORLD, "viewed", file), JSON.stringify(data));
  writeFileSync(path.join(WORLD, "index.json"), JSON.stringify({ packages: [{ arm: "viewed", view: "written", sidecar: sidecar.length === 1 ? sidecar[0] : sidecar }] }));
  const out = path.join(scratch, name);
  const done = python([path.join(ROOT, "tools", "adapt_run.py"), "--experiment", "synthetic-world", "--root", WORLD, "--run", "viewed", "--overlay", path.join(FIXTURES, "overlay.json"), "--out", out]);
  for (const file of Object.keys(files)) rmSync(path.join(WORLD, "viewed", file), { force: true });
  rmSync(path.join(WORLD, "index.json"), { force: true });
  if (done.status !== 0) return { status: done.status, stderr: done.stderr, file: null };
  const index = readJson(path.join(out, "index.json"));
  return { status: 0, stderr: done.stderr, file: readJson(path.join(out, `${index.runs[0].id}.json`)) };
}
const declarations = readDeclarations(readJson(path.join(ROOT, "data", "layers", "layers.json")), MARKS).layers;

test("a stated quantity is copied as stated at the replay's times, said to be the experiment's, and offered as a colour", () => {
  const { status, stderr, file } = adapt("quantity", { "concentration.json": quantity() });
  assert.equal(status, 0, stderr);
  const run = openReplay(file);
  const record = run.records.get("stated.concentration");
  assert.ok(record, "the stated quantity is a record of the run");
  assert.deepEqual([record.label, record.unit, record.set, record.axes], ["[S] in each cell, in µM, as the driver states it", "uM", "cell", ["time", "cell"]]);
  assert.deepEqual(record.stated, { file: "concentration.json", format: "cells.experiment_quantity@1", quantity: "concentration" });
  for (let row = 0; row < ROWS; row++) shape.cells.forEach((_, k) => assert.equal(record.at(row, k), row - 3 + k));
  assert.equal(record.marks, undefined, "a quantity with no criterion has no ticks");
  assert.ok(file.view.derivation.some((line) => /the experiment's own quantity and not a field of the engine; the viewer works nothing out of it/.test(line)));
  // The unit is the file's, written in its own sign and never converted.
  assert.deepEqual(display(record), { unit: "µM", factor: 1, decimals: 3 });
  assert.equal(reading(record, record.at(4, 0)), "1.000 µM");
  const offers = layersFor(run, declarations, MARKS, { offer: ["stated.concentration"] });
  assert.ok(offers.some((item) => item.ok && item.layer.id === "stated-concentration-tint"), "it is offered as a Colour layer");
});

test("a criterion with one threshold ticks it in its own words; the states are carried as stated and colour nothing", () => {
  const states = shape.times.map((_, row) => shape.cells.map(() => (row < 2 ? "M" : "E")));
  const { status, stderr, file } = adapt("one-tick", { "criterion.json": criterion({ threshold: 0, above: "epithelial", below: "mesenchymal" }, { states }) });
  assert.equal(status, 0, stderr);
  const run = openReplay(file);
  const record = run.records.get("stated.score");
  assert.deepEqual(record.marks, [{ value: 0, label: "epithelial above, mesenchymal below" }]);
  assert.deepEqual(record.criterion, { words: "A cell is epithelial above the threshold.", source: "A made-up driver, for this test" });
  assert.equal(record.states, "stated.score.state");
  const state = run.records.get("stated.score.state");
  assert.deepEqual([state.dtype, state.words], ["uint8", ["E", "M"]]);
  assert.deepEqual(shape.times.map((_, row) => reading(state, state.at(row, 0))), states.map((row) => row[0]));
  const offers = layersFor(run, declarations, MARKS, { offer: ["stated.score"] });
  assert.ok(offers.some((item) => item.ok && item.layer.id === "stated-score-tint"));
  assert.ok(!offers.some((item) => item.layer.quantity?.record === "stated.score.state"), "the states colour nothing: the colour is the values'");
});

test("a criterion with two thresholds ticks both, with the three words as given", () => {
  const { status, stderr, file } = adapt("two-ticks", { "criterion.json": criterion({ threshold: 2, above: "epithelial", lower: { threshold: -2, below: "mesenchymal" }, between: "neither (X)" }) });
  assert.equal(status, 0, stderr);
  const record = openReplay(file).records.get("stated.score");
  assert.deepEqual(record.marks, [{ value: -2, label: "mesenchymal below, neither (X) between" }, { value: 2, label: "epithelial above" }]);
});

test("a stated file that does not fit the run, or does not say what it states, is refused with the reason", () => {
  const cases = [
    ["not a stated quantity", { "concentration.json": { ...quantity(), format: "something else" } }, /is not a stated quantity/],
    ["no unit", { "concentration.json": quantity({ quantity: { id: "concentration", label: "[S]" } }) }, /does not name its quantity/],
    ["a cell the view does not have", { "concentration.json": quantity({ cells: [...shape.cells.slice(1), "elsewhere"] }) }, /names other cells than the run's view/],
    ["a time the run does not have", { "concentration.json": quantity({ times_s: shape.times.map((time) => time + 0.25) }) }, /has no row at the replay's time .* never resampled/],
    ["a row short of a value", { "concentration.json": quantity({ values: shape.times.map(() => []) }) }, /one finite number for each of its cells/],
    ["a null value", { "concentration.json": quantity({ values: shape.times.map(() => shape.cells.map(() => null)) }) }, /one finite number for each of its cells/],
    ["one threshold with no word below", { "criterion.json": criterion({ threshold: 0, above: "epithelial" }) }, /no word for what lies below it/],
    ["a lower threshold over the upper", { "criterion.json": criterion({ threshold: 0, above: "epithelial", lower: { threshold: 1, below: "mesenchymal" }, between: "neither" }) }, /lower threshold needs a value under the upper one/],
    ["two thresholds with no word between", { "criterion.json": criterion({ threshold: 2, above: "epithelial", lower: { threshold: -2, below: "mesenchymal" } }) }, /the word for between the two/],
    ["no source", { "criterion.json": criterion({ threshold: 0, above: "epithelial", below: "mesenchymal", source: "" }) }, /does not state its criterion/],
    ["states of another shape", { "criterion.json": criterion({ threshold: 0, above: "epithelial", below: "mesenchymal" }, { states: [["E"]] }) }, /states do not give one word for each of its cells/],
  ];
  for (const [label, files, reason] of cases) {
    const { status, stderr } = adapt(`refused-${label.replace(/\W+/g, "-")}`, files);
    assert.notEqual(status, 0, label);
    assert.match(stderr, reason, label);
  }
  // The index names a file by its plain name, and one that is there.
  assert.match(adapt("path", { "concentration.json": quantity() }, ["../concentration.json"]).stderr, /not a JSON file's plain name/);
  assert.match(adapt("missing", {}, ["concentration.json"]).stderr, /which its folder's index names, is not there/);
});

test("a run whose folder's index names no file beside it is packaged as before", () => {
  const { status, stderr, file } = adapt("none", {}, []);
  assert.equal(status, 0, stderr);
  assert.ok(!file.view.records.some((record) => record.id.startsWith("stated.")));
});
