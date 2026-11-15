// The run adapter, checked on synthetic run folders (tests/fixtures, written by
// tools/make_run_fixture.py): its output keeps the contract of schema/RUN_VIEW.md,
// "Packaged for the viewer". No browser and no real run data are needed.
//
//   node --test tests/adapt_run.test.mjs
//
// run-small has the layout of an E07-v1 folder, run-arms that of the turnover pre-screen
// (no seed, no class, one arm with a refusal) and run-cue that of a W1 pilot (a cue, no
// replacements). The first tests read run-small alone; the later ones read all three.
//
// To check a folder of real output with the same eyes, name it:
//
//   CELLS_REPLAY_OUT=out/runs-adapter node --test tests/adapt_run.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Run, validateReplay } from "../src/replay/run.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "adapt_run.py");
const MAKER = path.join(ROOT, "tools", "make_run_fixture.py");
const KEPT = path.join(ROOT, "tests", "fixtures");
const EXPERIMENT = "synthetic-sheet";
const RUN = "synthetic-s1.0/seed1";
const RUN_ID = "synthetic-sheet--synthetic-s1.0--seed1";
const TYPES = { float32: Float32Array, uint8: Uint8Array, uint16: Uint16Array, int32: Int32Array };

const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-adapt-run-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));

// The fixtures are written afresh and read from there, so the test does not depend on which
// of them the checkout holds (the repository ignores every folder called runs/).
const FIXTURES = path.join(scratch, "fixtures");
const made = spawnSync("python3", [MAKER, "--out", FIXTURES], { encoding: "utf8" });
assert.equal(made.status, 0, `the fixture tool failed:\n${made.stderr}`);
const FIXTURE = path.join(FIXTURES, "run-small");

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

// The run's records in files of their own (schema/QUANTITY_LAYERS.md, rule 10), by part id.
const partFiles = Object.fromEntries((view.parts || []).map((part) => [part.id, readJson(path.join(out, path.basename(part.file)))]));
const partPayloads = Object.fromEntries(Object.entries(partFiles).map(([id, file]) => [id, Buffer.from(file.payload.data, "base64")]));

/** The bytes a record's array lies in: the run's own payload, or the payload of its part. */
const payloadOf = (item) => (item.part ? partPayloads[item.part] : payload);

/** A record's values, read out of its payload as its dtype says. */
function values(item) {
  const Type = TYPES[item.dtype];
  const count = item.shape.reduce((a, b) => a * b, 1);
  const bytes = payloadOf(item);
  const start = bytes.byteOffset + item.offset;
  return new Type(bytes.buffer.slice(start, start + count * Type.BYTES_PER_ELEMENT));
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
    assert.ok(item.offset + bytes <= payloadOf(item).length, `${item.id} runs past the payload`);
    spans.push([item.offset, item.offset + bytes, item.id, item.part || ""]);
    for (const key of ["id", "label", "unit", "axes", "dtype", "offset", "shape", "range"]) assert.ok(key in item, `${item.id} lacks ${key}`);
    assert.equal(item.axes.length, item.shape.length, `${item.id}: one axis per dimension`);

    const scale = item.scale ?? 1;
    const finite = [...values(item)].filter((value) => Number.isFinite(value)).map((value) => value * scale);
    assert.ok(Math.abs(item.range[0] - Math.min(...finite)) < 1e-12 && Math.abs(item.range[1] - Math.max(...finite)) < 1e-12, `${item.id}: range ${item.range}`);
    assert.equal(Boolean(item.quantised), item.scale !== undefined, `${item.id}: a scaled array is marked quantised, and only that`);
  }
  // Within one payload (the run's own, or a part's), no two arrays overlap.
  spans.sort((a, b) => a[3].localeCompare(b[3]) || a[0] - b[0]);
  for (let i = 1; i < spans.length; i++) if (spans[i][3] === spans[i - 1][3]) assert.ok(spans[i][0] >= spans[i - 1][1], `${spans[i][2]} overlaps ${spans[i - 1][2]}`);
});

test("a record in a file of its own: the file is the run's, of the stated length, and listed in the catalogue", () => {
  assert.deepEqual(view.parts, [{ id: "junction-gate", label: "Each junction's gate", file: `runs/${RUN_ID}.junction-gate.json`, byte_length: partPayloads["junction-gate"].length }]);
  const file = partFiles["junction-gate"];
  assert.deepEqual({ format: file.format, run: file.run, part: file.part, encoding: file.payload.encoding, byte_length: file.payload.byte_length }, { format: "cells.visualizer.replay_part@1", run: RUN_ID, part: "junction-gate", encoding: "base64", byte_length: partPayloads["junction-gate"].length });
  const gate = record("junction_gate");
  assert.deepEqual({ part: gate.part, set: gate.set, layer: gate.layer, kind: gate.kind, owner: gate.owner, quantised: gate.quantised, offset: gate.offset }, { part: "junction-gate", set: "junction", layer: "junctions", kind: "level", owner: "synthetic_junction_gate@0", quantised: true, offset: 0 });
  assert.deepEqual(gate.shape, record("junction_abundance").shape);
  // The fixture shuts the gate of every junction across the disc's edge to a quarter; the others are open.
  const stored = [...values(gate)].map((value) => value * gate.scale);
  assert.deepEqual([...new Set(stored.map((value) => value.toFixed(3)))].sort(), ["0.251", "1.000"]);
  const saved = fixtureJson("runs", RUN, "definition.json").model.junctions.length;
  assert.equal(stored.length, view.records.find((item) => item.id === "t").shape[0] * saved);
  // The record of the times, and everything the sheet opens with, stay in the run's own file.
  for (const id of ["t", "vm", "generation", "junction_abundance", "regular", "valid"]) assert.equal(record(id).part, undefined, `${id} is in the run's own file`);
  // The catalogue lists the file with its size, so that it can be published without opening the run.
  const [row] = index.runs;
  assert.deepEqual(row.parts, [{ id: "junction-gate", file: `runs/${RUN_ID}.junction-gate.json`, bytes: statSync(path.join(out, `${RUN_ID}.junction-gate.json`)).size }]);
  assert.ok(row.parts[0].bytes < 1_000_000);
  assert.ok(view.layers.some((layer) => layer.id === "junctions"), "the gate's layer is listed");
  assert.match(view.derivation.join(" "), /Each junction's gate .* in a file of its own beside this one/);
});

test("what a quantity layer needs of a record is stated only where the run's files state it", () => {
  // Kind and owner: from the driver and from the definition's own names.
  assert.deepEqual(["vm", "generation", "junction_abundance"].map((id) => [record(id).kind, record(id).owner]), [["level", "synthetic_sheet@0"], ["level", "synthetic_replacement@0"], ["level", "synthetic_junction_formation@0"]]);
  // The fixture's definition states no sign for the voltage, so none is written.
  for (const item of view.records) assert.equal(item.sign, undefined, `${item.id}: a sign the run does not state`);
  assert.match(view.derivation.join(" "), /Which way the membrane voltage is positive is stated by neither/);
  // The records with no set are no quantity of a layer.
  for (const id of ["t", "regular", "valid"]) assert.deepEqual([record(id).kind, record(id).owner], [undefined, undefined]);
  // Every cell's surroundings share one potential: each membrane's outside is a held bath at 0 V in the definition.
  assert.deepEqual({ shared: view.surroundings.shared, potential_V: view.surroundings.potential_V }, { shared: true, potential_V: 0 });
  assert.match(view.surroundings.says, /held bath at 0 V/);
  assert.match(view.derivation.join(" "), /every cell's surroundings share one potential is read from definition\.json/);
});

test("the adapter's own table for the tissue family: the signs the engine's owner confirmed, and no other", () => {
  const printed = spawnSync("python3", ["-c", "import json, sys; sys.path.insert(0, sys.argv[1]); import adapt_run; print(json.dumps({'fields': adapt_run.TISSUE_FIELDS, 'by': adapt_run.TISSUE_SIGN_BY, 'missing': adapt_run.tissue_field('calcium_pump_cycles')}))", path.dirname(TOOL)], { encoding: "utf8" });
  assert.equal(printed.status, 0, printed.stderr);
  const { fields, by, missing } = JSON.parse(printed.stdout);
  // A positive transfer leaves the cell for its outside, or the sender for the receiver.
  assert.deepEqual([fields.membrane_transferred.sign.from, fields.membrane_transferred.sign.to], ["cell", "outside node"]);
  assert.deepEqual([fields.channel_transferred.sign.from, fields.channel_transferred.sign.to], ["cell", "outside node"]);
  for (const name of ["junction_transferred", "face_transferred"]) assert.deepEqual([fields[name].sign.from, fields[name].sign.to], ["first", "second"], name);
  // The two exceptions: pump cycles are positive inwards; what a reservoir supplies is positive into the outside node.
  assert.deepEqual([fields.pump_cycles.sign.from, fields.pump_cycles.sign.to], ["outside node", "cell"]);
  assert.match(fields.reservoir_supplied.sign.says, /entered the outside node/);
  // Every sign says where it comes from, in plain words: the engine's convention, confirmed, not yet declared.
  const signed = Object.keys(fields).filter((name) => fields[name].sign).sort();
  assert.deepEqual(signed, ["channel_transferred", "face_transferred", "junction_transferred", "membrane_transferred", "pump_cycles", "reservoir_supplied"]);
  for (const name of signed) assert.equal(fields[name].sign.by, by, name);
  assert.match(by, /the engine's own convention.*confirmed by the owner of its core on 15 November 2026.*not yet declared in the run's view/);
  // A field with no confirmed sign has none: it is shown as a level or a size, never with a direction.
  for (const name of ["membrane_voltage_V", "cell_potential_V", "junction_voltage_V", "amount", "extracellular_amount"]) assert.equal(fields[name].sign, undefined, name);
  assert.equal(missing, null, "a field that was not confirmed by name is not listed");
  // The heat ledgers are totals that only grow; the transfers are totals too, of which a rate is worked out.
  for (const part of ["membrane", "channel", "junction", "face", "pump"]) assert.deepEqual(fields[`${part}_dissipated_energy_pJ`], { kind: "cumulative", unit: "pJ", never_falls: true });
  for (const name of signed) assert.equal(fields[name].kind, "cumulative", name);
  assert.equal(fields.metabolic_work_pJ.never_falls, undefined, "only the dissipated-energy fields were confirmed never to fall");
});

test("where the definition does not say that the surroundings share one potential, the view does not say it either", () => {
  const cases = [
    ["baths at two potentials", (definition) => (definition.model.extracellular[3].boundary_potential_V = 0.01)],
    ["a bath that is not held", (definition) => (definition.model.extracellular[0].reservoir = false)],
    ["a cell with no membrane listed", (definition) => definition.model.membranes.pop()],
    ["a control of another kind in the schedule", (definition) => (definition.experiment.bath_controls = [])],
    ["no outside nodes at all", (definition) => delete definition.model.extracellular],
  ];
  for (const [name, damage] of cases) {
    const copy = copyOfFixture(`surroundings-${name.replace(/[^a-z]+/g, "-")}`);
    const file = path.join(copy, "runs", RUN, "definition.json");
    const definition = readJson(file);
    damage(definition);
    writeFileSync(file, JSON.stringify(definition));
    const target = path.join(copy, "out");
    const result = adapt(copy, target);
    assert.equal(result.status, 0, `${name}: ${result.stderr}`);
    assert.equal(readJson(path.join(target, `${RUN_ID}.json`)).view.surroundings, undefined, `${name}: the view still says the surroundings share one potential`);
  }
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

test("the fixtures kept in the checkout are the ones the tool writes", (t) => {
  const walk = (folder, base = folder) =>
    readdirSync(folder, { withFileTypes: true }).flatMap((item) => (item.isDirectory() ? walk(path.join(folder, item.name), base) : [path.relative(base, path.join(folder, item.name))]));
  const written = walk(FIXTURES).sort();
  const kept = existsSync(KEPT) ? walk(KEPT).sort() : [];
  for (const name of kept) assert.ok(written.includes(name), `tests/fixtures/${name} is not written by the tool`);
  const missing = written.filter((name) => !kept.includes(name));
  for (const name of kept) {
    assert.ok(readFileSync(path.join(KEPT, name)).equals(readFileSync(path.join(FIXTURES, name))), `tests/fixtures/${name} differs from what the tool writes: run tools/make_run_fixture.py`);
  }
  if (missing.length) t.diagnostic(`${missing.length} fixture file(s) are not in the checkout, and the test wrote its own: ${missing.slice(0, 3).join(", ")}`);
});

// ---------------------------------------------------------------- several experiments

const SHARED = ["--overlay", path.join(FIXTURES, "overlay.json"), "--selection", path.join(FIXTURES, "selection.json")];
const ARMS = "synthetic-arms", CUE = "synthetic-cue";
const ISO = "synthetic-arms--synthetic-iso-s1.0", DONOR = "synthetic-arms--synthetic-donor-s1.0";
const WRITTEN = "synthetic-cue--study-a-world-1--seed3", REFUSED = "synthetic-cue--study-b-world-1--seed3";
const PATHS = /\/home\/|\/mnt\/|\/Users\/|\/tmp\/|[A-Za-z]:\\\\/;

const tool = (...args) => spawnSync("python3", [TOOL, ...args], { encoding: "utf8" });
const filesOf = (folder) => Object.fromEntries(readdirSync(folder).sort().map((name) => [name, readFileSync(path.join(folder, name))]));

/** A run file opened: its view, its payload and the viewer's own reading of it. */
function open(folder, id) {
  const file = readJson(path.join(folder, `${id}.json`));
  const bytes = Buffer.from(file.payload.data, "base64");
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return { file, view: file.view, run: new Run(file.view, buffer), record: (name) => file.view.records.find((item) => item.id === name) };
}

const all = path.join(scratch, "all");
const everything = tool("--evidence", FIXTURES, ...SHARED, "--out", all);
assert.equal(everything.status, 0, `the adapter failed on the three fixtures:\n${everything.stderr}`);
const catalogue = readJson(path.join(all, "index.json"));
const curated = readJson(path.join(FIXTURES, "overlay.json")).experiments;

test("one call adapts every experiment of the selection into one catalogue", () => {
  assert.equal(catalogue.format, "cells.visualizer.replay_index@1");
  assert.deepEqual(catalogue.experiments.map((item) => item.id), [EXPERIMENT, ARMS, CUE], "experiments stand in the overlay's order");
  assert.deepEqual(catalogue.runs.map((item) => item.id), [RUN_ID, ISO, DONOR, WRITTEN, REFUSED], "each experiment's runs follow, in the selection's order");
  for (const experiment of catalogue.experiments) {
    const { adapter, ...entry } = curated[experiment.id];
    assert.deepEqual(experiment, { id: experiment.id, ...entry }, `${experiment.id}: the catalogue copies the overlay's entry, with its outcome and stops`);
    assert.ok(adapter && experiment.adapter === undefined);
  }
  for (const row of catalogue.runs) {
    const file = path.join(all, `${row.id}.json`);
    assert.equal(row.file, `runs/${row.id}.json`);
    assert.equal(row.bytes, statSync(file).size);
    const { view, run } = open(all, row.id);
    assert.deepEqual(validateReplay(readJson(file)), [], `${row.id}: the viewer's own checks pass`);
    assert.equal(run.count, row.records);
    assert.equal(run.end, row.end_s);
    assert.deepEqual([view.run.id, view.run.experiment, view.run.arm, view.run.seed, view.run.label, view.run.group, view.run.stop], [row.id, row.experiment, row.arm, row.seed, row.label, row.group, row.stop]);
    for (const key of ["class", "refusal"]) assert.deepEqual(row[key], view.run[key], `${row.id}: ${key} is the same in the catalogue and in the run`);
  }
  assert.ok(readFileSync(path.join(all, `${RUN_ID}.json`)).equals(readFileSync(runFile)), "a run is the same file whichever call wrote it");
});

test("adapting one experiment leaves the others' entries and files in place", () => {
  const steps = path.join(scratch, "steps");
  const first = tool("--experiment", ARMS, "--root", path.join(FIXTURES, "run-arms"), ...SHARED, "--out", steps);
  assert.equal(first.status, 0, first.stderr);
  assert.deepEqual(readJson(path.join(steps, "index.json")).experiments.map((item) => item.id), [ARMS]);
  const before = filesOf(steps);

  const second = tool("--experiment", EXPERIMENT, "--root", FIXTURE, ...SHARED, "--out", steps);
  assert.equal(second.status, 0, second.stderr);
  const both = readJson(path.join(steps, "index.json"));
  assert.deepEqual(both.experiments.map((item) => item.id), [EXPERIMENT, ARMS], "the overlay's order, not the order of the calls");
  assert.deepEqual(both.runs.map((item) => item.id), [RUN_ID, ISO, DONOR]);
  for (const name of [`${ISO}.json`, `${DONOR}.json`]) assert.ok(readFileSync(path.join(steps, name)).equals(before[name]), `${name} was rewritten`);
  assert.match(second.stdout, /kept as they were: synthetic-arms/);

  const third = tool("--evidence", FIXTURES, "--experiment", CUE, ...SHARED, "--out", steps);
  assert.equal(third.status, 0, third.stderr);
  const one = filesOf(all), several = filesOf(steps);
  assert.deepEqual(Object.keys(several), Object.keys(one));
  for (const name of Object.keys(one)) assert.ok(several[name].equals(one[name]), `${name} differs between one call and three`);

  // An experiment adapted again has exactly the runs of that call; a file it no longer lists stays on disk.
  const again = tool("--experiment", ARMS, "--root", path.join(FIXTURES, "run-arms"), "--run", "synthetic-iso-s1.0", ...SHARED, "--out", steps);
  assert.equal(again.status, 0, again.stderr);
  assert.deepEqual(readJson(path.join(steps, "index.json")).runs.map((item) => item.id), [RUN_ID, ISO, WRITTEN, REFUSED]);
  assert.ok(existsSync(path.join(steps, `${DONOR}.json`)), "nothing is deleted");
  assert.match(again.stderr, /not in the catalogue and were left in place/);
});

test("a kept run whose file is gone is taken out of the catalogue, and said to be", () => {
  const copy = path.join(scratch, "gone");
  cpSync(all, copy, { recursive: true });
  rmSync(path.join(copy, `${DONOR}.json`));
  const result = tool("--experiment", EXPERIMENT, "--root", FIXTURE, ...SHARED, "--out", copy);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readJson(path.join(copy, "index.json")).runs.map((item) => item.id), [RUN_ID, ISO, WRITTEN, REFUSED]);
  assert.match(result.stderr, /synthetic-arms have no file/);
});

test("an index.json that is not a catalogue stops the call before anything is written", () => {
  const other = path.join(scratch, "not-a-catalogue");
  mkdirSync(other);
  writeFileSync(path.join(other, "index.json"), '{"format":"something else"}\n');
  const result = tool("--evidence", FIXTURES, ...SHARED, "--out", other);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /adapt_run: .*not a replay catalogue/);
  assert.deepEqual(readdirSync(other), ["index.json"]);
  assert.equal(readFileSync(path.join(other, "index.json"), "utf8"), '{"format":"something else"}\n');
});

test("what the call is asked for is checked before any run is read", () => {
  const target = path.join(scratch, "asked");
  for (const [args, message] of [
    [["--experiment", ARMS], /give --evidence, or --experiment with --root/],
    [["--root", FIXTURE], /give it with --experiment/],
    [["--evidence", FIXTURES, "--run", "synthetic-iso-s1.0"], /--run names runs of one experiment/],
    [["--evidence", FIXTURES, "--experiment", "no-such-experiment"], /the selection lists no experiment called no-such-experiment/],
    [["--evidence", path.join(FIXTURES, "run-small")], /the evidence folder run-small is not in the folder given with --evidence/],
  ]) {
    const result = tool(...args, ...SHARED, "--out", target);
    assert.notEqual(result.status, 0, args.join(" "));
    assert.match(result.stderr, message);
  }
  assert.ok(!existsSync(path.join(target, "index.json")));
});

// ---------------------------------------------------------------- a run with no seed and no class

test("a run with no seed and no class carries neither", () => {
  const { view, run } = open(all, ISO);
  const row = catalogue.runs.find((item) => item.id === ISO);
  assert.ok(!("class" in view.run) && !("class" in row), "no class is made up");
  assert.equal(view.run.seed, null);
  assert.equal(row.seed, null);
  assert.ok(!ISO.includes("seed"), "the id is <experiment>--<arm>");
  assert.equal(view.run.label, null);
  const plan = readJson(path.join(FIXTURES, "run-arms", "arms", "synthetic-iso-s1.0", "plan.json"));
  assert.equal(view.run.group, plan.kind, "the group is the plan's newcomer kind");
  assert.ok(view.derivation.some((line) => line.includes("no group")), "and the derivation says the plan names none");
  assert.equal(view.run.judged_s, null);
  // Isolated newcomers have no donor: the event names the cell replaced and nothing it was copied from.
  assert.equal(view.events.length, 3);
  assert.ok(view.events.every((event) => event.kind === "replacement" && event.from === undefined));
  assert.deepEqual(view.regions[0].indices, [...plan.permutation].sort((a, b) => a - b));
  assert.equal(run.records.get("vm").marks[0].value, -0.0394);
  assert.equal(view.run.revision, "0123456", "read from the snapshot folder the run's result names");
});

test("an experiment whose catalogue entry lists no classes needs none from the summary", () => {
  const copy = copyOfFixture("classless");
  const overlay = readJson(path.join(copy, "overlay.json"));
  delete overlay.experiments[EXPERIMENT].classes;
  writeFileSync(path.join(copy, "overlay.json"), JSON.stringify(overlay));
  for (const file of [path.join(copy, "summary.json"), path.join(copy, "runs", RUN, "outcome.json")]) {
    const data = readJson(file);
    delete (data.runs ? data.runs[RUN] : data).run_class;
    writeFileSync(file, JSON.stringify(data));
  }
  const target = path.join(scratch, "out-classless");
  const result = adapt(copy, target);
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!("class" in readJson(path.join(target, `${RUN_ID}.json`)).view.run));
  assert.ok(!("class" in readJson(path.join(target, "index.json")).runs[0]));
});

test("an item of a list is named with its number", () => {
  const { view } = open(all, ISO);
  const outcome = readJson(path.join(FIXTURES, "run-arms", "arms", "synthetic-iso-s1.0", "outcome.json"));
  const readouts = Object.fromEntries(view.run.readouts.map((item) => [item.id, item.value]));
  assert.deepEqual(Object.keys(readouts), ["jaccard_after_turnover.0", "jaccard_after_turnover.1", "jaccard_after_turnover_basis.0", "osmotic.max_excess", "b1_jaccard_0p8_through_two_turnovers"]);
  assert.equal(readouts["jaccard_after_turnover.0"], outcome.jaccard_after_turnover[0]);
  assert.equal(readouts["jaccard_after_turnover.1"], null, "an item the run recorded as empty stays empty");
  assert.equal(readouts["jaccard_after_turnover_basis.0"], "record");
  assert.equal(readouts.b1_jaccard_0p8_through_two_turnovers, false);
  assert.deepEqual(view.run.parameters, [{ id: "kind", value: "iso" }, { id: "size", value: 7 }, { id: "formation.lag_s", value: 5 }, { id: "seeds.order", value: 11 }]);
});

// ---------------------------------------------------------------- a refusal

test("a refusal the run records is carried as recorded", () => {
  const { view, run } = open(all, DONOR);
  const result = readJson(path.join(FIXTURES, "run-arms", "arms", "synthetic-donor-s1.0", "result.json"));
  assert.equal(view.run.stop, "refusal");
  assert.deepEqual(view.run.refusal, result.refusal);
  assert.deepEqual(catalogue.runs.find((item) => item.id === DONOR).refusal, result.refusal);
  assert.equal(run.end, 30, "the run keeps its records up to the refusal");
  assert.equal(view.events.length, 2);
  assert.ok(view.derivation.some((line) => line.startsWith("4 scheduled replacements after the run's last record")));
  // A run that records none has none.
  for (const id of [RUN_ID, ISO, WRITTEN]) {
    assert.ok(!("refusal" in open(all, id).view.run), id);
    assert.ok(!("refusal" in catalogue.runs.find((item) => item.id === id)), id);
  }
});

test("a failure a pilot run records is carried without its traceback", () => {
  const { view } = open(all, REFUSED);
  const { traceback, ...failure } = readJson(path.join(FIXTURES, "run-cue", "study-b", "run", "run.json")).failure;
  assert.ok(traceback.includes("/mnt/"), "the fixture's traceback holds a machine path");
  assert.deepEqual(view.run.refusal, failure);
  assert.equal(view.run.stop, null, "the run's files give no word for how it ended, and none is made up");
  assert.equal(view.run.end_s, 3);
  assert.deepEqual(view.run.readouts.map((item) => [item.id, item.value]), [["written", false], ["last_time_s", 3]]);
  assert.deepEqual(open(all, WRITTEN).view.run.readouts, [], "a run with no outcome file has no readouts");
});

// ---------------------------------------------------------------- an event that is not a replacement

test("a cue is an event of its own kind, at each cell it acts on", () => {
  const { view, run, record } = open(all, WRITTEN);
  const definition = readJson(path.join(FIXTURES, "run-cue", "study-a", "run", "definitions", "world-1.json"));
  // The cells the definition's schedule switches the cue on in: channel -> membrane -> cell.
  const inside = Object.fromEntries(definition.model.membranes.map((item) => [item.id, item.inside]));
  const membrane = Object.fromEntries(definition.model.channels.map((item) => [item.id, item.membrane_id]));
  const cells = view.sets.find((item) => item.id === "cell").ids;
  const switched = new Set();
  for (const control of definition.experiment.channel_controls) {
    if (control.schedule.some((step) => step.availability > 0) && control.channel_id.startsWith("cue_")) switched.add(cells.indexOf(inside[membrane[control.channel_id]]));
  }
  const disc = [...switched].sort((a, b) => a - b);
  assert.equal(disc.length, 7);
  assert.equal(definition.model.channels.filter((item) => item.id.startsWith("cue_")).length, 2 * cells.length, "every cell carries the cue on two patches; only the disc's is switched");

  assert.deepEqual(view.regions.map((region) => [region.id, region.set, region.indices]), [["disc", "cell", disc]]);
  assert.equal(view.events.length, 2 * disc.length, "one event per cell and change, not one per patch");
  const on = view.events.slice(0, disc.length), off = view.events.slice(disc.length);
  assert.ok(on.every((event) => event.kind === "cue_on" && event.time === 3 && event.label === "availability 1"));
  assert.ok(off.every((event) => event.kind === "cue_off" && event.time === 4 && event.label === "availability 0"));
  for (const group of [on, off]) assert.deepEqual(group.map((event) => event.at.index), disc);
  assert.ok(view.events.every((event) => event.layer === "cue" && event.at.set === "cell" && event.from === undefined && event.kind !== "replacement"));
  assert.deepEqual(view.layers.map((layer) => layer.id), ["membrane", "cue"]);

  // The run saved times and one voltage per cell, and nothing about replacements or flags.
  assert.deepEqual(view.records.map((item) => item.id), ["t", "vm"]);
  assert.ok(record("vm").note.includes("cell_vm_V"));
  assert.equal(record("vm").marks[0].value, -0.0394);
  assert.equal(run.validity, null);
  const vm = run.records.get("vm"), mark = record("vm").marks[0].value;
  const written = (row) => cells.map((_, cell) => cell).filter((cell) => vm.at(row, cell) > mark);
  assert.deepEqual(written(run.indexAt(3)), [], "no cell is in D when the cue comes on");
  assert.equal(written(run.indexAt(3.25)).length, disc.length - 1, "one cell is written a record later than the others");
  assert.deepEqual(written(run.count - 1), disc, "the disc is written and stays written after the cue goes off");
  assert.ok(view.derivation.some((line) => line.includes("jittered")), "the regular drawing of a jittered tissue is said");
  assert.ok(view.derivation.some((line) => line.includes("runs.jsonl")), "and where the source snapshot's name came from");

  // The refused study stops when the cue comes on: its cue never goes off in the replay.
  const refused = open(all, REFUSED).view;
  assert.deepEqual([...new Set(refused.events.map((event) => event.kind))], ["cue_on"]);
  assert.ok(refused.derivation.some((line) => line.startsWith("7 scheduled cue changes after the run's last record")));
});

test("no machine path, host name or traceback is written for any experiment", () => {
  for (const name of readdirSync(all)) {
    const data = readJson(path.join(all, name));
    // A catalogue, a run (its view), or a part of a run (everything but its arrays).
    const text = JSON.stringify(name === "index.json" ? data : data.view ?? { ...data, payload: null });
    assert.ok(!PATHS.test(text), `${name} carries a machine path`);
    for (const word of ["fixture-host", "nobody", "nowhere", "Traceback"]) assert.ok(!text.includes(word), `${name} carries "${word}"`);
  }
});

// ---------------------------------------------------------------- a folder of real output

const REAL = process.env.CELLS_REPLAY_OUT ? path.resolve(process.env.CELLS_REPLAY_OUT) : null;

test("every file of a real output folder passes the viewer's own checks", { skip: REAL ? false : "set CELLS_REPLAY_OUT to a folder the adapter wrote" }, () => {
  const real = readJson(path.join(REAL, "index.json"));
  assert.equal(real.format, "cells.visualizer.replay_index@1");
  const experiments = new Map(real.experiments.map((item) => [item.id, item]));
  assert.equal(experiments.size, real.experiments.length);
  assert.ok(!PATHS.test(JSON.stringify(real)), "index.json carries a machine path");
  const seen = new Set();
  let total = 0;
  for (const row of real.runs) {
    assert.ok(!seen.has(row.id), `${row.id} is listed twice`);
    seen.add(row.id);
    const experiment = experiments.get(row.experiment);
    assert.ok(experiment, `${row.id}: its experiment is not in the catalogue`);
    const file = path.join(REAL, `${row.id}.json`);
    const size = statSync(file).size;
    assert.equal(row.bytes, size);
    assert.ok(size < 1_000_000, `${row.id} is ${size} bytes`);
    total += size;
    const data = readJson(file);
    assert.deepEqual(validateReplay(data), [], row.id);
    const { view, run } = open(REAL, row.id);
    assert.ok(!PATHS.test(JSON.stringify(view)), `${row.id} carries a machine path`);
    assert.equal(run.count, row.records);
    assert.deepEqual([view.run.id, view.run.experiment, view.run.arm, view.run.seed, view.run.group, view.run.stop, view.run.class, view.run.refusal], [row.id, row.experiment, row.arm, row.seed, row.group, row.stop, row.class, row.refusal]);
    for (let i = 1; i < run.count; i++) assert.ok(run.t[i] > run.t[i - 1], `${row.id}: times increase`);
    for (const event of view.events) {
      assert.ok(event.time >= run.start - 1e-3 && event.time <= run.end + 1e-3, `${row.id}: an event at ${event.time} lies outside the records`);
      assert.ok(experiment.events?.[event.kind], `${row.id}: the catalogue has no label for the event kind ${event.kind}`);
    }
    for (const region of view.regions || []) assert.ok(experiment.regions?.[region.id], `${row.id}: the catalogue has no label for the region ${region.id}`);
    for (const item of [...view.run.parameters.map((p) => ["parameters", p.id]), ...view.run.readouts.map((r) => ["readouts", r.id])]) {
      assert.ok(experiment[item[0]]?.[item[1]]?.label, `${row.id}: the catalogue has no label for ${item[1]}`);
    }
    if (row.group !== null) assert.ok(experiment.groups?.[row.group], `${row.id}: the catalogue has no group ${row.group}`);
    if (row.class !== undefined) assert.ok((experiment.classes || []).some((item) => item.id === row.class), `${row.id}: the catalogue has no class ${row.class}`);
    if (row.stop !== null) assert.ok(experiment.stops?.[row.stop], `${row.id}: the catalogue has no words for the stop ${row.stop}`);
    // Its records in files of their own: each listed, of the stated size, the run's, and read by the viewer.
    assert.deepEqual((row.parts || []).map((part) => [part.id, part.file]), (view.parts || []).map((part) => [part.id, part.file]), `${row.id}: the catalogue and the run list the same parts`);
    for (const part of row.parts || []) {
      const beside = path.join(REAL, path.basename(part.file));
      const bytes = statSync(beside).size;
      assert.equal(part.bytes, bytes);
      assert.ok(bytes < 1_000_000, `${row.id}: its part ${part.id} is ${bytes} bytes`);
      total += bytes;
      const held = readJson(beside);
      assert.deepEqual([held.format, held.run, held.part], ["cells.visualizer.replay_part@1", row.id, part.id]);
      const before = run.records.size;
      run.attach(part.id, Uint8Array.from(Buffer.from(held.payload.data, "base64")).buffer);
      assert.ok(run.records.size > before && run.pending.size === 0, `${row.id}: the part ${part.id} gave no record`);
    }
  }
  for (const id of experiments.keys()) assert.ok(real.runs.some((row) => row.experiment === id), `${id} has no runs`);
  console.log(`  ${real.runs.length} runs of ${experiments.size} experiments, ${(total / 1e6).toFixed(1)} MB in all`);
});
