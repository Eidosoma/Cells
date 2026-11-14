// The run adapter, checked on a synthetic run folder (tests/fixtures/run-small, written by
// tools/make_run_fixture.py): its output keeps the contract of schema/RUN_VIEW.md,
// "Packaged for the viewer". No browser and no real run data are needed.
//
//   node --test tests/adapt_run.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = path.join(ROOT, "tests", "fixtures", "run-small");
const TOOL = path.join(ROOT, "tools", "adapt_run.py");
const EXPERIMENT = "synthetic-sheet";
const RUN = "synthetic-s1.0/seed1";
const RUN_ID = "synthetic-sheet--synthetic-s1.0--seed1";
const TYPES = { float32: Float32Array, uint8: Uint8Array, uint16: Uint16Array, int32: Int32Array };

const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-adapt-run-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));

function adapt(root, out) {
  const args = [TOOL, "--experiment", EXPERIMENT, "--root", root, "--overlay", path.join(root, "overlay.json"), "--selection", path.join(root, "selection.json"), "--out", out];
  return spawnSync("python3", args, { encoding: "utf8" });
}
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const fixtureJson = (...parts) => readJson(path.join(FIXTURE, ...parts));

/** A copy of the fixture that a test may damage. */
function copyOfFixture(name) {
  const copy = path.join(scratch, name);
  cpSync(FIXTURE, copy, { recursive: true });
  return copy;
}

const out = path.join(scratch, "out");
const done = adapt(FIXTURE, out);
assert.equal(done.status, 0, `the adapter failed on the fixture:\n${done.stderr}`);
const index = readJson(path.join(out, "index.json"));
const runFile = path.join(out, `${RUN_ID}.json`);
const replay = readJson(runFile);
const view = replay.view;
const payload = Buffer.from(replay.payload.data, "base64");
const record = (id) => view.records.find((item) => item.id === id);
const set = (id) => view.sets.find((item) => item.id === id);

/** A record's values, read out of the payload as its dtype says. */
function values(item) {
  const Type = TYPES[item.dtype];
  const count = item.shape.reduce((a, b) => a * b, 1);
  const start = payload.byteOffset + item.offset;
  return new Type(payload.buffer.slice(start, start + count * Type.BYTES_PER_ELEMENT));
}

test("the catalogue and the run file carry the contract's formats", () => {
  assert.equal(index.format, "cells.visualizer.replay_index@1");
  assert.equal(replay.format, "cells.visualizer.replay@1");
  assert.equal(view.format, "cells.run_view@1");
  assert.equal(view.derived, true);
  assert.ok(view.derivation.length >= 3 && view.derivation.every((line) => typeof line === "string" && line.length > 20), "each derived piece has its line");
  assert.deepEqual(view.time, { unit: "s", record: "t" });
  assert.deepEqual(view.space, { unit: "um", dimensions: 2 });

  const [experiment] = index.experiments;
  const curated = fixtureJson("overlay.json").experiments[EXPERIMENT];
  assert.equal(experiment.id, EXPERIMENT);
  for (const key of ["label", "plain", "sources", "engine_entities", "groups", "classes", "regions", "records", "events", "parameters", "readouts"]) {
    assert.deepEqual(experiment[key], curated[key], `the catalogue copies the overlay's ${key}`);
  }
  assert.equal(experiment.adapter, undefined, "the adapter's own key stays out of the catalogue");

  assert.equal(index.runs.length, 1);
  const [run] = index.runs;
  assert.match(run.id, /^[a-z0-9.-]+$/);
  assert.equal(run.id, RUN_ID);
  assert.equal(run.id, view.run.id);
  assert.equal(run.file, `runs/${RUN_ID}.json`);
  assert.equal(run.bytes, statSync(runFile).size);
  assert.deepEqual(
    { experiment: run.experiment, arm: run.arm, seed: run.seed, label: run.label, group: run.group, class: run.class, stop: run.stop, records: run.records, end_s: run.end_s },
    { experiment: EXPERIMENT, arm: "synthetic-s1.0", seed: 1, label: "synthetic fixture", group: "control", class: "erosion", stop: "planned end", records: 9, end_s: 60 }
  );
});

test("every array lies inside the payload, on a multiple of four bytes, with its stated range", () => {
  assert.equal(replay.payload.encoding, "base64");
  assert.equal(payload.length, replay.payload.byte_length);
  const spans = [];
  for (const item of view.records) {
    const Type = TYPES[item.dtype];
    assert.ok(Type, `${item.id}: dtype ${item.dtype}`);
    assert.equal(item.offset % 4, 0, `${item.id}: offset ${item.offset}`);
    const bytes = item.shape.reduce((a, b) => a * b, 1) * Type.BYTES_PER_ELEMENT;
    assert.ok(item.offset + bytes <= payload.length, `${item.id} runs past the payload`);
    spans.push([item.offset, item.offset + bytes, item.id]);
    for (const key of ["id", "label", "unit", "axes", "dtype", "offset", "shape", "range"]) assert.ok(key in item, `${item.id} lacks ${key}`);
    assert.equal(item.axes.length, item.shape.length, `${item.id}: one axis per dimension`);

    const scale = item.scale ?? 1;
    const finite = [...values(item)].filter((value) => Number.isFinite(value)).map((value) => value * scale);
    assert.ok(Math.abs(item.range[0] - Math.min(...finite)) < 1e-12 && Math.abs(item.range[1] - Math.max(...finite)) < 1e-12, `${item.id}: range ${item.range}`);
    assert.equal(Boolean(item.quantised), item.scale !== undefined, `${item.id}: a scaled array is marked quantised, and only that`);
  }
  spans.sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < spans.length; i++) assert.ok(spans[i][0] >= spans[i - 1][1], `${spans[i][2]} overlaps ${spans[i - 1][2]}`);
});

test("times, sets and records agree with one another", () => {
  const cells = set("cell"), junctions = set("junction");
  const times = values(record("t"));
  assert.deepEqual(record("t").axes, ["time"]);
  assert.equal(times.length, 9);
  for (let i = 1; i < times.length; i++) assert.ok(times[i] > times[i - 1], "times increase");
  assert.deepEqual(record("vm").shape, [9, cells.ids.length]);
  assert.deepEqual([record("vm").set, record("vm").unit, record("vm").dtype], ["cell", "V", "float32"]);
  assert.deepEqual(record("generation").shape, [9, cells.ids.length]);
  assert.deepEqual(record("junction_abundance").shape, [9, junctions.ids.length]);
  assert.deepEqual([record("junction_abundance").set, record("junction_abundance").dtype, record("junction_abundance").quantised], ["junction", "uint8", true]);
  // The run's own flags: seven records on the 10 s grid, two at event times; one marked not valid.
  assert.deepEqual([...values(record("regular"))], [1, 1, 0, 1, 1, 1, 0, 1, 1]);
  assert.deepEqual([...values(record("valid"))], [1, 1, 1, 1, 1, 1, 0, 1, 1]);
  assert.ok(record("regular").note && record("valid").note, "the flags say what they mean");
  // A replacement shows from the record after its event: the generation of slot 6 steps up after 13.785 s.
  const generation = values(record("generation"));
  const slot = view.events[0].at.index, width = cells.ids.length;
  assert.deepEqual([0, 1, 2, 3].map((row) => generation[row * width + slot]), [0, 0, 0, 1]);
});

test("the sheet is a lattice: every junction joins neighbouring cells", () => {
  const cells = set("cell"), junctions = set("junction");
  assert.equal(cells.geometry.kind, "polygons");
  assert.equal(junctions.geometry.kind, "links");
  assert.equal(junctions.geometry.between, "cell");
  const { vertices, faces } = cells.geometry;
  assert.equal(faces.length, cells.ids.length);
  assert.ok(vertices.every((point) => point.length === 2 && point.every(Number.isFinite)));
  const centres = faces.map((face) => {
    assert.equal(face.length, 6);
    assert.ok(face.every((corner) => Number.isInteger(corner) && corner >= 0 && corner < vertices.length));
    return [0, 1].map((axis) => face.reduce((sum, corner) => sum + vertices[corner][axis], 0) / 6);
  });
  const apart = (a, b) => Math.hypot(centres[a][0] - centres[b][0], centres[a][1] - centres[b][1]);
  let nearest = Infinity;
  for (let a = 0; a < centres.length; a++) for (let b = a + 1; b < centres.length; b++) nearest = Math.min(nearest, apart(a, b));
  assert.ok(nearest > 1, "no two cells share a place");
  assert.equal(junctions.geometry.ends.length, junctions.ids.length);
  for (const [a, b] of junctions.geometry.ends) {
    assert.ok(a !== b && a >= 0 && b >= 0 && a < centres.length && b < centres.length);
    assert.ok(Math.abs(apart(a, b) - nearest) < 1e-3, `junction ${a}-${b} spans ${apart(a, b)}, neighbours are ${nearest} apart`);
  }
  // 19 cells in two rings: 42 neighbouring pairs, and each is a junction of the fixture.
  let pairs = 0;
  for (let a = 0; a < centres.length; a++) for (let b = a + 1; b < centres.length; b++) if (Math.abs(apart(a, b) - nearest) < 1e-3) pairs++;
  assert.equal(pairs, junctions.ids.length);
  const middle = [0, 1].map((axis) => centres.reduce((sum, centre) => sum + centre[axis], 0) / centres.length);
  assert.ok(Math.hypot(...middle) < 1e-3, "the sheet is centred");
});

test("events and regions point at cells of the sheet", () => {
  const cells = set("cell");
  const times = values(record("t"));
  const scheduled = fixtureJson("runs", RUN, "definition.json").experiment.replacement_events;
  assert.equal(view.events.length, scheduled.length);
  view.events.forEach((event, order) => {
    assert.equal(event.kind, "replacement");
    assert.equal(event.time, scheduled[order].time);
    assert.ok(event.time >= times[0] && event.time <= times[times.length - 1] + 1e-6);
    assert.equal(cells.ids[event.at.index], scheduled[order].slot);
    assert.equal(event.at.set, "cell");
    assert.equal(cells.ids[event.from.index], scheduled[order].donor);
    assert.equal(event.label, scheduled[order].carrier_id);
  });
  const plan = fixtureJson("runs", RUN, "plan.json");
  assert.equal(view.regions.length, 1);
  const [disc] = view.regions;
  assert.deepEqual([disc.id, disc.set, disc.label], ["disc", "cell", "The disc"]);
  assert.deepEqual(disc.indices, [...plan.permutation].sort((a, b) => a - b));
  assert.equal(disc.indices.length, plan.size);
});

test("the run's own words are copied and nothing is judged", () => {
  const summary = fixtureJson("summary.json"), outcome = fixtureJson("runs", RUN, "outcome.json");
  const plan = fixtureJson("runs", RUN, "plan.json"), result = fixtureJson("runs", RUN, "result.json");
  const run = view.run;
  assert.equal(run.class, summary.runs[RUN].run_class);
  assert.deepEqual([run.label, run.group, run.arm, run.seed], [plan.label, plan.group, plan.arm, plan.seed]);
  assert.deepEqual(run.engine_models, result.engine_models);
  assert.deepEqual([run.stop, run.end_s, run.judged_s], [result.stop, result.end_s, outcome.judged_s]);
  assert.equal(run.revision, fixtureJson("snapshot", "SNAPSHOT.json").git_revision.slice(0, 7));

  const readouts = Object.fromEntries(run.readouts.map((item) => [item.id, item]));
  assert.deepEqual(Object.keys(readouts), ["judged_s", "delta_J", "recruitment_fraction", "delta_J_over_records.mean"], "only the ids the catalogue names, and only those the outcome holds");
  assert.deepEqual(readouts["delta_J_over_records.mean"], { id: "delta_J_over_records.mean", value: outcome.delta_J_over_records.mean, supplementary: true, status: outcome.delta_J_over_records.status });
  assert.deepEqual(readouts.delta_J, { id: "delta_J", value: outcome.delta_J, supplementary: false, status: null });
  assert.equal(readouts.recruitment_fraction.value, null, "a readout the run recorded as empty stays empty");
  assert.deepEqual(run.parameters, [{ id: "size", value: plan.size }, { id: "s", value: plan.s }, { id: "scope", value: plan.scope }, { id: "formation.lag_s", value: plan.formation.lag_s }]);
});

test("the D mark is the constant in the evidence folder's source snapshot", () => {
  assert.deepEqual(record("vm").marks.map((mark) => mark.value), [-0.0394]);
  assert.ok(record("vm").marks[0].label);
  assert.ok(view.derivation.some((line) => line.includes("THRESHOLD_V")), "and the derivation says where it was read");
  // The disc starts above the mark and the rest below it.
  const voltages = values(record("vm")), width = set("cell").ids.length;
  const above = [...Array(width).keys()].filter((cell) => voltages[cell] > record("vm").marks[0].value);
  assert.deepEqual(above, view.regions[0].indices);
});

test("without a source snapshot the mark and the revision are left out, and said to be", () => {
  const copy = copyOfFixture("no-snapshot");
  rmSync(path.join(copy, "snapshot"), { recursive: true });
  const target = path.join(scratch, "out-no-snapshot");
  const result = adapt(copy, target);
  assert.equal(result.status, 0, result.stderr);
  const other = readJson(path.join(target, `${RUN_ID}.json`)).view;
  assert.equal(other.records.find((item) => item.id === "vm").marks, undefined);
  assert.equal(other.run.revision, null);
  assert.ok(other.derivation.some((line) => line.startsWith("No D mark")));
});

test("no machine path and no host name is written", () => {
  for (const file of [runFile, path.join(out, "index.json")]) {
    const text = readFileSync(file, "utf8");
    assert.ok(!/\/home\/|\/mnt\/|\/Users\/|\/tmp\/|[A-Za-z]:\\\\/.test(text), `${path.basename(file)} carries a machine path`);
    assert.ok(!text.includes("fixture-host"), `${path.basename(file)} carries the host name`);
    assert.ok(!text.includes("nobody"), `${path.basename(file)} carries part of a path`);
  }
});

test("the same input gives the same bytes", () => {
  const again = path.join(scratch, "out-again");
  assert.equal(adapt(FIXTURE, again).status, 0);
  for (const name of ["index.json", `${RUN_ID}.json`]) {
    assert.ok(readFileSync(path.join(out, name)).equals(readFileSync(path.join(again, name))), `${name} differs between two runs`);
  }
});

test("a run file stays under 1 MB", () => {
  assert.ok(statSync(runFile).size < 1_000_000);
});

test("a sheet that is not a hexagonal lattice is refused", () => {
  const copy = copyOfFixture("not-a-lattice");
  const file = path.join(copy, "runs", RUN, "definition.json");
  const definition = readJson(file);
  // A junction between two cells that are not neighbours: the two ends of a row.
  const centres = set("cell").geometry.faces.map((face) => face.reduce((sum, corner) => sum + set("cell").geometry.vertices[corner][0], 0) / 6);
  const left = centres.indexOf(Math.min(...centres)), right = centres.indexOf(Math.max(...centres));
  definition.model.junctions.push({ id: "junction_bad", sender: `cell_${left}`, receiver: `cell_${right}` });
  writeFileSync(file, JSON.stringify(definition));
  const result = adapt(copy, path.join(scratch, "out-not-a-lattice"));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /adapt_run: .*(hexagonal|lattice|neighbours|places)/);
});

test("a run the summary records no class for is refused", () => {
  const copy = copyOfFixture("no-class");
  const file = path.join(copy, "summary.json");
  const summary = readJson(file);
  delete summary.runs[RUN].run_class;
  writeFileSync(file, JSON.stringify(summary));
  const result = adapt(copy, path.join(scratch, "out-no-class"));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /adapt_run: .*no class/);
});
