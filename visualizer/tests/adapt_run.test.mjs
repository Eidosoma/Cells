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
import { layersFor, readDeclarations } from "../src/layers/layers.js";
import { MARKS } from "../src/layers/marks/index.js";
import { readLoop, loopStreams, closesWords, engineWords } from "../src/layers/loop.js";
import declaredLayers from "../data/layers/layers.json" with { type: "json" };

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
    // A record declared the same as another (a membrane's voltage, where each cell has one membrane) is that array, not a second one.
    if (item.same_as) assert.deepEqual([item.offset, item.dtype, item.shape], [record(item.same_as).offset, record(item.same_as).dtype, record(item.same_as).shape], `${item.id} is the array of ${item.same_as}`);
    else spans.push([item.offset, item.offset + bytes, item.id, item.part || ""]);
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
  assert.deepEqual(view.parts[0], { id: "junction-gate", label: "Each junction's gate", file: `runs/${RUN_ID}.junction-gate.json`, byte_length: partPayloads["junction-gate"].length });
  assert.deepEqual(view.parts.map((part) => part.id), ["junction-gate", "concentration-na", "concentration-k", "concentration-m"]);
  const file = partFiles["junction-gate"];
  assert.deepEqual({ format: file.format, run: file.run, part: file.part, encoding: file.payload.encoding, byte_length: file.payload.byte_length }, { format: "cells.visualizer.replay_part@1", run: RUN_ID, part: "junction-gate", encoding: "base64", byte_length: partPayloads["junction-gate"].length });
  const gate = record("junction_gate");
  assert.deepEqual({ part: gate.part, set: gate.set, layer: gate.layer, kind: gate.kind, owner: gate.owner, quantised: gate.quantised, offset: gate.offset }, { part: "junction-gate", set: "junction", layer: "junctions", kind: "level", owner: "junction_voltage_relaxation@1", quantised: true, offset: 0 });
  assert.deepEqual(gate.shape, record("junction_abundance").shape);
  // The fixture shuts the gate of every junction across the disc's edge to a quarter; the others are open.
  const stored = [...values(gate)].map((value) => value * gate.scale);
  assert.deepEqual([...new Set(stored.map((value) => value.toFixed(3)))].sort(), ["0.251", "1.000"]);
  const saved = fixtureJson("runs", RUN, "definition.json").model.junctions.length;
  assert.equal(stored.length, view.records.find((item) => item.id === "t").shape[0] * saved);
  // The record of the times, and everything the sheet opens with, stay in the run's own file.
  for (const id of ["t", "vm", "membrane_voltage_V", "generation", "junction_abundance", "regular", "valid"]) assert.equal(record(id).part, undefined, `${id} is in the run's own file`);
  // The catalogue lists every file with its size, so that it can be published without opening the run.
  const [row] = index.runs;
  assert.deepEqual(row.parts, view.parts.map((part) => ({ id: part.id, file: `runs/${RUN_ID}.${part.id}.json`, bytes: statSync(path.join(out, `${RUN_ID}.${part.id}.json`)).size })));
  for (const part of row.parts) assert.ok(part.bytes < 1_000_000, part.id);
  assert.ok(view.layers.some((layer) => layer.id === "junctions"), "the gate's layer is listed");
  assert.match(view.derivation.join(" "), /Each junction's gate .* in a file of its own beside this one/);
});

test("what a quantity layer needs of a record is stated only where the run's files state it", () => {
  // Kind and owner: from the driver and from the definition's own names.
  assert.deepEqual(["vm", "generation", "junction_abundance"].map((id) => [record(id).kind, record(id).owner]), [["level", "resolved_pump_replacement@1"], ["level", "scheduled_cell_replacement@1"], ["level", "delayed_first_order_junction_formation@1"]]);
  // No record but the voltage is given a sign; the voltage's is the adapter's reading of the run's files, and says so.
  for (const item of view.records) if (!["vm", "membrane_voltage_V"].includes(item.id)) assert.equal(item.sign, undefined, `${item.id}: a sign the run does not state`);
  assert.deepEqual({ high: record("vm").sign.high, says: record("vm").sign.says }, { high: "inside", says: "a positive voltage means the cell's inside is positive against its outside" });
  assert.match(record("vm").sign.by, /the viewer's reading of the run's own files, not a declaration by the run.*saved voltage equals the charge its definition gives the cell, over the capacitance/);
  assert.doesNotMatch(record("vm").sign.by, /confirmed by the owner/, "this sign is not one the owner of the engine's core confirmed");
  assert.match(view.derivation.join(" "), /Which way the membrane voltage is positive is not declared by the run\. It is read from the run's own files/);
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
  for (const part of ["membrane", "channel", "junction", "face", "pump"]) assert.deepEqual(fields[`${part}_dissipated_energy_pJ`], { kind: "cumulative", unit: "pJ", monotone: "non-decreasing" }, "in the engine's own word for a total that never falls");
  for (const name of signed) assert.equal(fields[name].kind, "cumulative", name);
  assert.equal(fields.metabolic_work_pJ.monotone, undefined, "only the dissipated-energy fields were confirmed never to fall");
  // The membrane's own total holds its passive routes only, as the engine's run view notes: its channels and its pump keep ledgers of their own.
  assert.match(fields.membrane_transferred.note, /^the passive membrane routes only: what each channel population and each pump carried is its own ledger/);
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

/** Adapt a copy of the fixture whose definition a test has changed (and its plan, with `plan`), and give back the run's view. */
function viewAfter(name, damage, plan = null) {
  const copy = copyOfFixture(name);
  const file = path.join(copy, "runs", RUN, "definition.json");
  const definition = readJson(file);
  damage(definition);
  writeFileSync(file, JSON.stringify(definition));
  if (plan) {
    const planned = readJson(path.join(copy, "runs", RUN, "plan.json"));
    plan(planned);
    writeFileSync(path.join(copy, "runs", RUN, "plan.json"), JSON.stringify(planned));
  }
  const target = path.join(copy, "out");
  const result = adapt(copy, target);
  assert.equal(result.status, 0, `${name}: ${result.stderr}`);
  return readJson(path.join(target, `${RUN_ID}.json`)).view;
}

test("each ion's concentration is a record of its own, in a file of its own, as the run saved it", () => {
  const definition = fixtureJson("runs", RUN, "definition.json");
  const cells = definition.model.cells.length, times = record("t").shape[0];
  // The fixture saves 8, 140 and 20 mM for its first three species, a hundredth more for each cell along.
  for (const [species, first] of [["Na", 8.0], ["K", 140.0], ["M", 20.0]]) {
    const item = record(`concentration_mM.${species}`);
    assert.deepEqual(
      { unit: item.unit, set: item.set, layer: item.layer, kind: item.kind, owner: item.owner, field: item.field, species: item.species, part: item.part, dtype: item.dtype, axes: item.axes, shape: item.shape, quantised: item.quantised },
      { unit: "mM", set: "cell", layer: "ions", kind: "level", owner: "resolved_pump_replacement@1", field: "concentration_mM", species, part: `concentration-${species.toLowerCase()}`, dtype: "float32", axes: ["time", "cell"], shape: [times, cells], quantised: undefined }
    );
    const stored = values(item);
    for (const step of [0, times - 1]) for (const cell of [0, 7, cells - 1]) assert.equal(stored[step * cells + cell], Math.fround(first + 0.01 * cell), `${species} at record ${step}, cell ${cell}`);
  }
  // The fourth species was not saved: no record is made up for it, and the view says so.
  assert.equal(record("concentration_mM.P"), undefined);
  const said = view.derivation.join(" ");
  assert.match(said, /takes the first 3 species of the definition, in its order \(Na, K, M\), each cell's amount over its volume, in mM/);
  assert.match(said, /That is checked: at the first record every value equals the definition's own amount over its own volume/);
  assert.match(said, /The run did not save the concentration of P\./);
  assert.ok(view.layers.some((layer) => layer.id === "ions"), "the concentrations' layer is listed");
});

test("the membranes, their outsides and the species are sets of the view; a membrane's voltage is the cell's own array", () => {
  const definition = fixtureJson("runs", RUN, "definition.json");
  const cells = set("cell").ids.length;
  assert.deepEqual(set("species").ids, ["Na", "K", "M", "P"]);
  assert.deepEqual({ holds: set("outside").holds, ids: set("outside").ids }, { holds: "outside node", ids: definition.model.extracellular.map((node) => node.id) });
  const membranes = set("membrane");
  assert.deepEqual(membranes.ids, definition.model.membranes.map((membrane) => membrane.id));
  // Each membrane lies on the cell its definition names as its inside, and faces the bath it names as its outside.
  assert.deepEqual(membranes.geometry, { kind: "on", set: "cell", index: definition.model.membranes.map((membrane) => set("cell").ids.indexOf(membrane.inside)) });
  assert.deepEqual(membranes.outside, { set: "outside", index: definition.model.membranes.map((membrane) => set("outside").ids.indexOf(membrane.outside)) });
  assert.deepEqual(membranes.geometry.index, Array.from({ length: cells }, (_, index) => index), "one membrane for each cell, in the cells' order");
  const own = record("membrane_voltage_V"), saved = record("vm");
  assert.deepEqual({ set: own.set, axes: own.axes, same_as: own.same_as, offset: own.offset, shape: own.shape, sign: own.sign, marks: own.marks }, { set: "membrane", axes: ["time", "membrane"], same_as: "vm", offset: saved.offset, shape: saved.shape, sign: saved.sign, marks: undefined });
  assert.match(view.derivation.join(" "), /The run saved one voltage per cell\. Its definition gives every cell exactly one membrane, in the cells' order.*no array is added/);
  assert.deepEqual(validateReplay(replay), []);
});

test("the constants of the definition are stated with the definition's own numbers, each with why nothing changes it", () => {
  const { model } = fixtureJson("runs", RUN, "definition.json");
  const constant = (id) => view.constants.find((item) => item.id === id);
  assert.deepEqual(view.constants.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM"]);
  assert.deepEqual({ unit: constant("temperature").unit, axes: constant("temperature").axes, values: constant("temperature").values }, { unit: "K", axes: [], values: model.temperature_K });
  assert.deepEqual({ axes: constant("valence").axes, values: constant("valence").values }, { axes: ["species"], values: model.species.map((item) => item.valence) });
  assert.deepEqual({ unit: constant("volume").unit, set: constant("volume").set, values: constant("volume").values }, { unit: "pL", set: "cell", values: model.cells.map((cell) => cell.volume_pL) });
  assert.deepEqual({ unit: constant("membrane_capacitance").unit, set: constant("membrane_capacitance").set, axes: constant("membrane_capacitance").axes, values: constant("membrane_capacitance").values }, { unit: "F", set: "membrane", axes: ["membrane"], values: model.membranes.map((membrane) => membrane.capacitance_F) });
  assert.deepEqual({ unit: constant("membrane_area").unit, values: constant("membrane_area").values }, { unit: "m2", values: model.membranes.map((membrane) => membrane.area_m2) });
  // The composition outside: each held bath's declared amounts over its declared volume, for every species.
  const outside = constant("extracellular_concentration_mM");
  assert.deepEqual({ unit: outside.unit, set: outside.set, axes: outside.axes }, { unit: "mM", set: "outside", axes: ["species", "outside"] });
  assert.deepEqual(outside.values, model.species.map((item) => model.extracellular.map((node) => node.initial_amount_fmol[item.id] / node.volume_pL)));
  assert.deepEqual(outside.values.map((row) => row[0]), [145, 5, 140, 10]);
  for (const item of view.constants) {
    assert.equal(item.from, "definition.json", item.id);
    assert.ok(item.says.length > 30, `${item.id} says why it is a constant of this run`);
  }
  assert.match(constant("membrane_capacitance").says, /a newcomer's template names no capacitance and no area \(checked on the definition\), and no control of the run changes one/);
  assert.match(constant("volume").says, /A replacement keeps the volume of its place/);
  assert.match(outside.says, /held bath.*A held bath keeps its composition, and the run schedules no control of a bath/);
  assert.equal(view.unstated, undefined, "nothing is left unstated for this run");
  assert.match(view.derivation.join(" "), /Named constants \(temperature, valence, volume, extracellular_volume, membrane_capacitance, membrane_area, extracellular_concentration_mM\) are the definition's own numbers/);
});

test("a definition the adapter does not know everything of states no constant, and says why", () => {
  const cases = [
    ["another model", (definition) => (definition.model.id = "some_other_tissue@4"), /the run's model \(some_other_tissue@4\) is not one whose operators the viewer knows/],
    ["a part of the model it does not know", (definition) => (definition.model.water = { law: "osmotic_water@1" }), /the run's model has a part the viewer does not know \(water\)/],
    ["a part of the definition it does not know", (definition) => (definition.operators = [{ law: "bath_schedule@1" }]), /the run's definition has a part the viewer does not know \(operators\)/],
    ["a control it does not know", (definition) => (definition.experiment.bath_controls = []), /the run schedules a control the viewer does not know \(bath_controls\)/],
    ["a control that schedules more than an availability", (definition) => (definition.experiment.membrane_controls = [{ membrane_id: "membrane_0", schedule: [{ time: 0, availability: 1, capacitance_F: 2e-11 }] }]), /a control of the run \(membrane_controls\) schedules more than an availability/],
    ["another replacement law", (definition) => (definition.model.replacement.law = "scheduled_cell_division@1"), /replaces cells by a law the viewer does not know \(law: scheduled_cell_division@1\)/],
    ["another inner model", (definition) => (definition.model.replacement.inner_model = "resolved_pump_water@1"), /a law the viewer does not know \(inner model: resolved_pump_water@1\)/],
    ["a template that names a capacitance", (definition) => (definition.model.replacement.templates[0].capacitance_F = 3e-11), /a newcomer's template gives a value the viewer does not know \(capacitance_F\)/],
    ["a template whose route values name an area", (definition) => (definition.model.replacement.templates[0].route_values.membrane_area_m2 = 1e-10), /a newcomer's template gives a value the viewer does not know \(membrane_area_m2\)/],
    ["a replacement that names a volume", (definition) => (definition.experiment.replacement_events[0].volume_pL = 0.9), /a replacement gives a value the viewer does not know \(volume_pL\)/],
    // The first replacement takes a template in place of a donor (in the plan too), and the template has another volume than its place.
    ["a template of another volume than its place", (definition) => {
      definition.model.replacement.templates[0].volume_pL = 0.9;
      Object.assign(definition.experiment.replacement_events[0], { newcomer: "isolated_template", template: "h_isolated", donor: null });
    }, /a newcomer's template has another volume than the cell it replaces/, (plan) => (plan.events[0][2] = null)],
    ["a membrane with a value it does not know", (definition) => (definition.model.membranes[2].capacitance_schedule = []), /gives its membranes a value the viewer does not know \(capacitance_schedule\)/],
  ];
  for (const [name, damage, why, plan] of cases) {
    const changed = viewAfter(`constants-${name.replace(/[^a-z]+/g, "-")}`, damage, plan);
    assert.equal(changed.constants, undefined, `${name}: a constant is still stated`);
    assert.deepEqual(changed.unstated.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM"], name);
    for (const item of changed.unstated) assert.match(item.why, why, `${name}: ${item.id}`);
    assert.match(changed.derivation.join(" "), /Not stated as constants: temperature, valence, volume, extracellular_volume, membrane_capacitance, membrane_area, extracellular_concentration_mM\./, name);
    assert.deepEqual(validateReplay({ format: "cells.visualizer.replay@1", view: changed, payload: replay.payload }).filter((problem) => !/runs past/.test(problem)), [], name);
  }
});

test("a value the definition does not give is left out by itself, and the others stay", () => {
  const stated = (changed) => (changed.constants || []).map((item) => item.id);
  const left = (changed) => Object.fromEntries((changed.unstated || []).map((item) => [item.id, item.why]));
  // A bath that is not held: its composition changes during the run and was not saved.
  let changed = viewAfter("constant-bath-not-held", (definition) => (definition.model.extracellular[4].reservoir = false));
  assert.deepEqual(stated(changed), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area"]);
  assert.match(left(changed).extracellular_concentration_mM, /not every membrane's outside is a held bath with a declared composition, and the run did not save the composition outside over time/);
  // A membrane with no capacitance in the definition.
  changed = viewAfter("constant-no-capacitance", (definition) => delete definition.model.membranes[3].capacitance_F);
  assert.deepEqual(stated(changed), ["temperature", "valence", "volume", "extracellular_volume", "membrane_area", "extracellular_concentration_mM"]);
  assert.match(left(changed).membrane_capacitance, /does not give every membrane its capacitance/);
  // No temperature.
  changed = viewAfter("constant-no-temperature", (definition) => delete definition.model.temperature_K);
  assert.ok(!stated(changed).includes("temperature") && /gives no temperature/.test(left(changed).temperature));
});

test("the voltage's sign is said only where every cell's first voltage is its declared charge over its membrane's capacitance", () => {
  const signs = (changed) => changed.records.filter((item) => item.sign).map((item) => item.id);
  // One cell whose declared charge does not give its first saved voltage: the reading does not hold, and nothing is said.
  let changed = viewAfter("sign-one-charge-off", (definition) => (definition.model.cells[5].initial_charge_C *= 1.001));
  assert.deepEqual(signs(changed), []);
  assert.match(changed.derivation.join(" "), /Which way the membrane voltage is positive is stated by neither, so it is shown as a level and given no direction/);
  assert.ok(changed.records.some((item) => item.id === "membrane_voltage_V"), "the membranes' own declaration of the voltage does not rest on the sign");
  // A charge of the other sign, a missing capacitance, a cell with two membranes: the same.
  changed = viewAfter("sign-other-way", (definition) => (definition.model.cells[0].initial_charge_C *= -1));
  assert.deepEqual(signs(changed), []);
  changed = viewAfter("sign-no-capacitance", (definition) => delete definition.model.membranes[0].capacitance_F);
  assert.deepEqual(signs(changed), []);
  changed = viewAfter("sign-two-membranes", (definition) => definition.model.membranes.push({ ...definition.model.membranes[0], id: "membrane_extra" }));
  assert.deepEqual(signs(changed), []);
  assert.ok(!changed.records.some((item) => item.id === "membrane_voltage_V"), "with two membranes on a cell, the cell's saved voltage is not declared as a membrane's");
  assert.equal(changed.sets.find((item) => item.id === "membrane").ids.length, set("cell").ids.length + 1);
});

test("concentrations whose species and unit the run's files do not show are left out, and said to be", () => {
  // The definition's amounts no longer give the first saved concentrations: which row is which species is not shown.
  const changed = viewAfter("concentration-not-shown", (definition) => (definition.model.cells[2].initial_amount_fmol.K *= 1.5));
  assert.ok(!changed.records.some((item) => item.field === "concentration_mM"));
  assert.deepEqual(changed.parts.map((part) => part.id), ["junction-gate"]);
  assert.ok(!changed.layers.some((layer) => layer.id === "ions"));
  assert.match(changed.derivation.join(" "), /records\.npz holds concentrations, but the run's files do not show which species and which unit they are.*They are left out/);
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
  // Only what the tool writes is its to keep: the folders and files at the top of its output. Other tests keep their
  // own fixtures beside these (tests/fixtures/entries, say), and this test leaves them alone.
  const owned = new Set(readdirSync(FIXTURES));
  const kept = existsSync(KEPT) ? walk(KEPT).filter((name) => owned.has(name.split(path.sep)[0])).sort() : [];
  for (const name of kept) assert.ok(written.includes(name), `tests/fixtures/${name} is not written by the tool`);
  const missing = written.filter((name) => !kept.includes(name));
  for (const name of kept) {
    assert.ok(readFileSync(path.join(KEPT, name)).equals(readFileSync(path.join(FIXTURES, name))), `tests/fixtures/${name} differs from what the tool writes: run tools/make_run_fixture.py`);
  }
  if (missing.length) t.diagnostic(`${missing.length} fixture file(s) are not in the checkout, and the test wrote its own: ${missing.slice(0, 3).join(", ")}`);
});

// ---------------------------------------------------------------- several experiments

const SHARED = ["--overlay", path.join(FIXTURES, "overlay.json"), "--selection", path.join(FIXTURES, "selection.json")];
const ARMS = "synthetic-arms", CUE = "synthetic-cue", HISTORY = "synthetic-history", WORLD = "synthetic-world", EXAMPLE = "example-sheet";
const WHOLE = "synthetic-history--whole-run", WINDOWED = "synthetic-history--windowed-run";
const SECRETING = "synthetic-world--secreting", UNBALANCED = "synthetic-world--unbalanced", SHEET = "example-sheet--invented-numbers";
const VIEWED = "synthetic-world--viewed", RETIRING = "synthetic-world--retiring"; // the same world with the engine's own view beside its files
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
assert.equal(everything.status, 0, `the adapter failed on the fixtures:\n${everything.stderr}`);
const catalogue = readJson(path.join(all, "index.json"));
const curated = readJson(path.join(FIXTURES, "overlay.json")).experiments;

test("one call adapts every experiment of the selection into one catalogue", () => {
  assert.equal(catalogue.format, "cells.visualizer.replay_index@1");
  assert.deepEqual(catalogue.experiments.map((item) => item.id), [EXPERIMENT, ARMS, CUE, HISTORY, WORLD, EXAMPLE], "experiments stand in the overlay's order");
  assert.deepEqual(catalogue.runs.map((item) => item.id), [RUN_ID, ISO, DONOR, WRITTEN, REFUSED, WHOLE, WINDOWED, SECRETING, UNBALANCED, VIEWED, RETIRING, SHEET], "each experiment's runs follow, in the selection's order");
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
  for (const experiment of [HISTORY, WORLD, EXAMPLE]) {
    const next = tool("--evidence", FIXTURES, "--experiment", experiment, ...SHARED, "--out", steps);
    assert.equal(next.status, 0, next.stderr);
  }
  const one = filesOf(all), several = filesOf(steps);
  assert.deepEqual(Object.keys(several), Object.keys(one));
  for (const name of Object.keys(one)) assert.ok(several[name].equals(one[name]), `${name} differs between one call and three`);

  // An experiment adapted again has exactly the runs of that call; a file it no longer lists stays on disk.
  const again = tool("--experiment", ARMS, "--root", path.join(FIXTURES, "run-arms"), "--run", "synthetic-iso-s1.0", ...SHARED, "--out", steps);
  assert.equal(again.status, 0, again.stderr);
  assert.deepEqual(readJson(path.join(steps, "index.json")).runs.map((item) => item.id), [RUN_ID, ISO, WRITTEN, REFUSED, WHOLE, WINDOWED, SECRETING, UNBALANCED, VIEWED, RETIRING, SHEET]);
  assert.ok(existsSync(path.join(steps, `${DONOR}.json`)), "nothing is deleted");
  assert.match(again.stderr, /not in the catalogue and were left in place/);
});

test("a kept run whose file is gone is taken out of the catalogue, and said to be", () => {
  const copy = path.join(scratch, "gone");
  cpSync(all, copy, { recursive: true });
  rmSync(path.join(copy, `${DONOR}.json`));
  const result = tool("--experiment", EXPERIMENT, "--root", FIXTURE, ...SHARED, "--out", copy);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readJson(path.join(copy, "index.json")).runs.map((item) => item.id), [RUN_ID, ISO, WRITTEN, REFUSED, WHOLE, WINDOWED, SECRETING, UNBALANCED, VIEWED, RETIRING, SHEET]);
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

/** The values of one record of an opened run, whether they lie in the run's own file or in one of its parts. */
function valuesOf(folder, opened, name) {
  const item = opened.record(name);
  const source = item.part ? readJson(path.join(folder, `${opened.view.run.id}.${item.part}.json`)).payload.data : opened.file.payload.data;
  const bytes = Buffer.from(source, "base64");
  const count = item.shape.reduce((a, b) => a * b, 1);
  return new Float32Array(bytes.buffer.slice(bytes.byteOffset + item.offset, bytes.byteOffset + item.offset + count * 4));
}

test("a run written by the engine's shared output path is read under the engine's own names, one file for each field", () => {
  const whole = open(all, WHOLE);
  const definition = readJson(path.join(FIXTURES, "run-history", "whole", "run", "resolved_config.json"));
  const cells = definition.model.cells.length, junctions = definition.model.junctions.length;
  assert.deepEqual(validateReplay(whole.file), []);
  assert.deepEqual(whole.view.sets.map((item) => [item.id, item.ids.length, item.holds]), [["cell", cells, undefined], ["junction", junctions, undefined], ["species", 4, undefined], ["outside", cells, "outside node"], ["membrane", cells, undefined], ["channel", cells, "channel population"]]);
  assert.deepEqual(whole.view.sets.at(-1).geometry, { kind: "on", set: "membrane", index: Array.from({ length: cells }, (_, index) => index) });
  // The records are the engine's readouts, by its names; one for each species where a field has a row for each.
  assert.deepEqual(whole.view.records.map((item) => item.id), [
    "t", "membrane_voltage_V", "vm", "cell_potential_V", "extracellular_potential_V", "junction_voltage_V", "junction_gate",
    "amount.Na", "amount.K", "amount.M", "amount.P", "extracellular_amount.Na", "extracellular_amount.K", "extracellular_amount.M", "extracellular_amount.P",
    "membrane_transferred.Na", "membrane_transferred.K", "membrane_transferred.M", "membrane_transferred.P", "channel_transferred", "pump_cycles", "membrane_dissipated_energy_pJ",
  ]);
  // What the sheet opens with is in the run's own file; every other field is in a file of its own.
  assert.deepEqual(whole.view.records.filter((item) => !item.part).map((item) => item.id), ["t", "membrane_voltage_V", "vm", "cell_potential_V"]);
  assert.deepEqual(whole.view.parts.map((part) => part.id), ["extracellular-potential-v", "junction-voltage-v", "junction-gate", "amount", "extracellular-amount", "membrane-transferred", "channel-transferred", "pump-cycles", "membrane-dissipated-energy-pj"]);
  assert.deepEqual(catalogue.runs.find((row) => row.id === WHOLE).parts.map((part) => [part.id, part.bytes]), whole.view.parts.map((part) => [part.id, statSync(path.join(all, `${WHOLE}.${part.id}.json`)).size]));
  // The numbers are the run's: a value for each of the run's places, the spare places of the engine's arrays cut off.
  const voltage = valuesOf(all, whole, "membrane_voltage_V");
  assert.equal(voltage.length, 5 * cells);
  assert.equal(voltage[3 * cells + 7], Math.fround(-0.0796 + 1e-5 * 7 + 2e-6 * 30) === voltage[3 * cells + 7] ? voltage[3 * cells + 7] : Math.fround(-0.0215 + 1e-5 * 7 + 2e-6 * 30));
  assert.equal(valuesOf(all, whole, "amount.K")[2 * cells + 4], Math.fround((140 + 0.01 * 4) * 0.75 + 0.001 * 20));
  assert.equal(valuesOf(all, whole, "extracellular_amount.M")[cells + 2], 140);
  assert.equal(valuesOf(all, whole, "channel_transferred")[4 * cells + 5], Math.fround(0.004 * 40 * (1 + 0.02 * 5)));
  // Each cell has one membrane: the membranes' voltage is also the cells', the same array.
  assert.deepEqual({ set: whole.record("vm").set, same_as: whole.record("vm").same_as, offset: whole.record("vm").offset }, { set: "cell", same_as: "membrane_voltage_V", offset: whole.record("membrane_voltage_V").offset });
  // Kind, unit and the way a carried amount is positive: the viewer's own table for this family of models, saying where each sign comes from.
  assert.deepEqual([whole.record("amount.Na").kind, whole.record("amount.Na").unit, whole.record("amount.Na").field, whole.record("amount.Na").species], ["amount", "fmol", "amount", "Na"]);
  const carried = whole.record("membrane_transferred.K");
  assert.deepEqual([carried.kind, carried.unit, carried.sign.from, carried.sign.to], ["cumulative", "fmol", "cell", "outside node"]);
  assert.match(carried.sign.by, /confirmed by the owner of its core on 15 November 2026/);
  assert.deepEqual([whole.record("pump_cycles").sign.from, whole.record("pump_cycles").sign.to], ["outside node", "cell"]);
  assert.equal(whole.record("membrane_dissipated_energy_pJ").sign, undefined);
  // Which way a voltage is positive is read from the run's own arrays, and said to be.
  assert.equal(whole.record("membrane_voltage_V").sign.high, "inside");
  assert.match(whole.record("membrane_voltage_V").sign.by, /the viewer's reading of the run's own saved arrays, not a declaration by the run: at every record each membrane's saved voltage equals the saved potential of its cell less that of the outside node it faces/);
  assert.equal(whole.record("junction_voltage_V").sign.high, "first");
  assert.match(whole.record("junction_voltage_V").sign.by, /each junction's saved voltage equals the saved potential of its sender less that of its receiver/);
  // A composition with no operator over the known inner model: its definition's values are constants of the run.
  assert.deepEqual(whole.view.constants.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM"]);
  assert.deepEqual(whole.view.run.engine_models, ["resolved_pump_composite@1", "resolved_pump_tissue@3"]);
  assert.deepEqual([whole.view.run.stop, whole.view.run.end_s, whole.view.run.seed, whole.view.run.revision], ["complete", 40, null, null]);
  assert.equal(whole.view.events.length, 0);
  // It stands in the catalogue as a development run, apart from the experiments.
  assert.equal(catalogue.experiments.find((item) => item.id === HISTORY).development, true);
  assert.equal(catalogue.experiments.find((item) => item.id === HISTORY).outcome.judged, false);
});

test("a windowed run gives the same records as the same run in one file: its windows put end to end, a repeated record left out", () => {
  const whole = open(all, WHOLE), windowed = open(all, WINDOWED);
  assert.equal(windowed.file.payload.data, whole.file.payload.data);
  assert.deepEqual(windowed.view.records, whole.view.records);
  for (const part of whole.view.parts) assert.equal(readJson(path.join(all, `${WINDOWED}.${part.id}.json`)).payload.data, readJson(path.join(all, `${WHOLE}.${part.id}.json`)).payload.data, part.id);
  assert.match(windowed.view.derivation.join(" "), /put end to end from its 2 window file\(s\) in the order windows\.jsonl lists them/);
  assert.match(windowed.view.derivation.join(" "), /1 record\(s\) at the first time of a window repeat the record at the end of the window before, and are left out/);
  assert.match(whole.view.derivation.join(" "), /trajectory\.npz, the arrays called observed_/);
});

test("the engine's output with an operator, a model of another family, or a voltage that is not the potentials' difference", () => {
  const adaptHistory = (name, change) => {
    const copy = path.join(scratch, `history-${name}`);
    cpSync(path.join(FIXTURES, "run-history"), path.join(copy, "run-history"), { recursive: true });
    for (const file of ["overlay.json", "selection.json"]) cpSync(path.join(FIXTURES, file), path.join(copy, file));
    const file = path.join(copy, "run-history", "whole", "run", "resolved_config.json");
    const definition = readJson(file);
    change(definition);
    writeFileSync(file, JSON.stringify(definition));
    const result = tool("--evidence", copy, "--experiment", HISTORY, "--run", "whole/run", "--overlay", path.join(copy, "overlay.json"), "--selection", path.join(copy, "selection.json"), "--out", path.join(copy, "out"));
    assert.equal(result.status, 0, `${name}: ${result.stderr}`);
    return open(path.join(copy, "out"), WHOLE);
  };
  // An operator the adapter does not know: the definition's values may change, so none is stated, and the operator is named.
  const operated = adaptHistory("operator", (definition) => definition.model.operators.push({ law: "scheduled_species_exchange@1" }));
  assert.equal(operated.view.constants, undefined);
  for (const item of operated.view.unstated) assert.match(item.why, /the run's composition has an operator whose effect on these values the viewer does not know \(scheduled_species_exchange@1\)/);
  assert.deepEqual(operated.view.run.engine_models, ["resolved_pump_composite@1", "resolved_pump_tissue@3", "scheduled_species_exchange@1"]);
  assert.equal(operated.record("membrane_transferred.Na").sign.from, "cell", "the family's signs do not depend on the constants");
  // A model of another family: no kind and no sign from the viewer's table; a unit only where the field's name ends in one.
  const other = adaptHistory("family", (definition) => (definition.model.id = "some_other_family@2"));
  assert.deepEqual([other.record("amount.Na").kind, other.record("amount.Na").unit, other.record("membrane_transferred.Na").sign], [undefined, "", undefined]);
  assert.equal(other.record("membrane_dissipated_energy_pJ").unit, "pJ");
  assert.equal(other.record("membrane_voltage_V").sign.high, "inside", "the voltage's sign is read from the arrays, whatever the family");
  assert.match(other.view.derivation.join(" "), /The run's model \(some_other_family@2\) is not of the family the viewer's table speaks of/);
  // A world with no junctions: the fields that lie on junctions are empty, and the view says so; nothing is called misshapen.
  const alone = adaptHistory("no-junctions", (definition) => (definition.model.junctions = []));
  assert.ok(!alone.view.records.some((item) => item.set === "junction"));
  assert.match(alone.view.derivation.join(" "), /The run has no junctions, so the fields that lie on them are empty and are not packaged: junction_voltage_V, junction_gate\./);
  assert.doesNotMatch(alone.view.derivation.join(" "), /do not have the shape/);
  // A cell with two membranes: no voltage is declared for a cell, and none is averaged.
  const patched = adaptHistory("two-membranes", (definition) => {
    definition.model.membranes[1].inside = definition.model.membranes[0].inside;
  });
  assert.equal(patched.record("vm"), undefined);
  assert.equal(patched.record("membrane_voltage_V").sign, undefined, "its voltage is no longer the potential of its cell less its outside's, so no sign is read");
  assert.match(patched.view.derivation.join(" "), /A cell of this run has several membranes, or none: no voltage is declared for a cell, and none is averaged/);
});

test("cells whose junctions make no hexagonal sheet are drawn side by side, and the view says so", () => {
  const copy = path.join(scratch, "history-row");
  cpSync(path.join(FIXTURES, "run-history"), path.join(copy, "run-history"), { recursive: true });
  for (const file of ["overlay.json", "selection.json"]) cpSync(path.join(FIXTURES, file), path.join(copy, file));
  const file = path.join(copy, "run-history", "whole", "run", "resolved_config.json");
  const definition = readJson(file);
  // Only the junctions between cells that follow one another in the definition are kept: a chain, no sheet.
  const order = definition.model.cells.map((cell) => cell.id);
  definition.model.junctions = definition.model.junctions.filter((junction) => Math.abs(order.indexOf(junction.sender) - order.indexOf(junction.receiver)) === 1).slice(0, 3);
  writeFileSync(file, JSON.stringify(definition));
  const result = tool("--evidence", copy, "--experiment", HISTORY, "--run", "whole/run", "--overlay", path.join(copy, "overlay.json"), "--selection", path.join(copy, "selection.json"), "--out", path.join(copy, "out"));
  assert.equal(result.status, 0, result.stderr);
  const { view, file: written } = open(path.join(copy, "out"), WHOLE);
  assert.deepEqual(validateReplay(written), []);
  assert.match(view.derivation[0], /its junctions do not make a hexagonal sheet\. The cells are drawn side by side in the definition's order/);
  const faces = view.sets[0].geometry.faces, vertices = view.sets[0].geometry.vertices;
  const middle = (face) => face.reduce((sum, vertex) => sum + vertices[vertex][1], 0) / face.length;
  assert.ok(faces.every((face) => Math.abs(middle(face) - middle(faces[0])) < 1e-6), "the cells stand in one row");
});

test("the pre-screen's arms go the same way: a full definition states its constants, a bare one states none and says why", () => {
  // The arm with isolated newcomers has a full definition: a template takes each place, and has the place's volume.
  const full = open(all, ISO);
  assert.deepEqual(full.view.constants.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM"]);
  assert.equal(full.view.unstated, undefined);
  assert.deepEqual(full.view.sets.map((item) => item.id), ["cell", "junction", "species", "outside", "membrane"]);
  assert.deepEqual(full.view.records.filter((item) => item.field === "concentration_mM").map((item) => item.species), ["Na", "K", "M"]);
  assert.equal(full.record("vm").sign.high, "inside");
  assert.equal(full.record("membrane_voltage_V").same_as, "vm");
  assert.deepEqual(validateReplay(full.file), []);
  // The other arm's definition names a model the adapter does not know and lists no membranes: nothing is stated.
  const bare = open(all, DONOR);
  assert.equal(bare.view.constants, undefined);
  assert.deepEqual(bare.view.unstated.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM"]);
  for (const item of bare.view.unstated) assert.match(item.why, /the run's model \(synthetic_sheet@0\) is not one whose operators the viewer knows/);
  assert.deepEqual(bare.view.sets.map((item) => item.id), ["cell", "junction"], "no membranes are listed, so none are made up");
  assert.ok(!bare.view.records.some((item) => item.sign || item.id === "membrane_voltage_V" || item.field));
  assert.match(bare.view.derivation.join(" "), /records\.npz holds concentrations, but the run's files do not show which species and which unit they are/);
  assert.deepEqual(validateReplay(bare.file), []);
});

test("a pilot world saved one voltage per cell, averaged over its patches of membrane: no membrane is declared for it", () => {
  const { view, file } = open(all, WRITTEN);
  assert.deepEqual(view.sets.map((item) => item.id), ["cell", "junction"]);
  assert.equal(view.constants, undefined);
  assert.ok(!view.records.some((item) => item.id === "membrane_voltage_V" || item.field || item.sign));
  assert.match(view.records.find((item) => item.id === "vm").note, /averages the membrane voltages of the cell's patches/);
  assert.deepEqual(validateReplay(file), []);
});

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

// ---------------------------------------------------------------- a small world, and an example

test("a small world: each space outside the cells has a tile beside the cell, a held bath is called one, and the secreted species is named", () => {
  const { view, file } = open(all, SECRETING);
  assert.deepEqual(validateReplay(file), []);
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  assert.deepEqual(sets.outside.ids, ["bath", "ecs_0"]);
  assert.deepEqual(sets.outside.reservoir, [true, false], "the bath is a reservoir in the definition; the space beside the cell is not");
  assert.deepEqual(sets.species.secreted, ["S"], "the species the run's operators make, clear and exchange");
  // One list of corners for the cell's tile and the two outside it; every two of the three tiles share an edge.
  assert.equal(sets.outside.geometry.kind, "polygons");
  assert.deepEqual(sets.outside.geometry.vertices, sets.cell.geometry.vertices);
  const faces = [...sets.cell.geometry.faces, ...sets.outside.geometry.faces];
  assert.equal(faces.length, 3);
  const shared = (a, b) => a.filter((vertex) => b.includes(vertex)).length;
  assert.deepEqual([shared(faces[0], faces[1]), shared(faces[0], faces[2]), shared(faces[1], faces[2])], [2, 2, 2], "a membrane or a face joins every two of them, and so their tiles touch");
  assert.ok(view.derivation.some((line) => /Where the outside nodes stand: the run saves no positions.*That layout is the viewer's own/.test(line)));
  // The face lies between the two spaces outside, sender first; a membrane on the cell faces each.
  assert.deepEqual(sets.face.geometry, { kind: "links", between: "outside", ends: [[1, 0]] });
  assert.deepEqual([sets.membrane.geometry.index, sets.membrane.outside.index], [[0, 0], [0, 1]]);
  // A sheet whose every cell has a bath of its own gives the baths no place, and says so.
  const sheet = open(all, SHEET).view;
  assert.equal(sheet.sets.find((item) => item.id === "outside").geometry, undefined);
  assert.ok(sheet.derivation.some((line) => /^The outside nodes are not drawn/.test(line)));
});

test("an operator's ledgers are read as totals where they start at nought and never fall, and each record's owner is the one the run's manifest names", () => {
  const { view, record } = open(all, SECRETING);
  for (const id of ["turnover_produced_fmol.S", "turnover_cleared_fmol.S", "turnover_outside_cleared_fmol.S"]) {
    assert.deepEqual([record(id).kind, record(id).monotone, record(id).owner, record(id).unit], ["cumulative", "non-decreasing", "scheduled_species_turnover@1", "fmol"], id);
  }
  assert.equal(record("amount.S").owner, "resolved_pump_tissue@3", "the manifest's word 'inner' is the inner model");
  assert.equal(record("face_dissipated_energy_pJ").monotone, "non-decreasing");
  assert.equal(record("face_transferred.S").sign.from, "first");
  assert.ok(view.derivation.some((line) => /^Read as totals since the run's start, because their arrays begin at nought and never fall: turnover_cleared_fmol, turnover_outside_cleared_fmol, turnover_produced_fmol\./.test(line)));
  assert.ok(view.derivation.some((line) => /^Each record's owner is the one the run's own manifest names/.test(line)));
  // The view lists each of its layers once.
  assert.equal(new Set(view.layers.map((layer) => layer.id)).size, view.layers.length);
});

test("an exchange route's total is positive out of the cell by the engine's confirmed convention, and gets a direction only where the run's amounts agree", () => {
  const good = open(all, SECRETING), bad = open(all, UNBALANCED);
  const moved = good.record("exchange_moved_fmol");
  assert.deepEqual([moved.set, moved.kind, moved.unit, moved.owner], ["route", "cumulative", "fmol", "scheduled_species_exchange@1"]);
  assert.deepEqual([moved.sign.says, moved.sign.from, moved.sign.to], ["a positive amount has left the route's cell for the outside its membrane faces", "cell", "outside node"]);
  assert.match(moved.sign.by, /^the engine's own convention for this operator, confirmed by the engine's lead on 15 November 2026 and not yet declared in the run's view\. The run's own saved amounts agree with it: at every record the amount of the route's species in its cell is the amount at the start.*Read the other way round or along each route's declared direction, the amounts do not add up$/);
  assert.ok(good.view.derivation.some((line) => /^Which way moved by an exchange route is positive is not declared by the run's files\. It is the engine's own convention for this operator, confirmed by the engine's lead on 15 November 2026/.test(line)));
  // The routes are a set of their own: each on its membrane, with the species it carries.
  const routes = good.view.sets.find((item) => item.id === "route");
  assert.deepEqual([routes.holds, routes.ids, routes.geometry, routes.species], ["route", ["secrete", "sink"], { kind: "on", set: "membrane", index: [1, 1] }, ["S", "S"]]);
  // The check itself, on the saved numbers: the cell's amount of S follows what was made less what the routes carried out.
  const run = good.run, last = run.count - 1;
  const value = (file, id, entity) => {
    const item = file.record(id);
    if (!item.part) return file.run.records.get(id).at(last, entity);
    const part = readJson(path.join(all, `${file.view.run.id}.${item.part}.json`));
    const bytes = Buffer.from(part.payload.data, "base64");
    return new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), item.offset, item.shape[0] * item.shape[1])[last * item.shape[1] + entity];
  };
  const gain = value(good, "amount.S", 0) - 0.001, made = value(good, "turnover_produced_fmol.S", 0), carried = value(good, "exchange_moved_fmol", 0) + value(good, "exchange_moved_fmol", 1);
  assert.ok(Math.abs(gain - (made - carried)) < 1e-9, `${gain} is ${made} less ${carried}`);
  assert.ok(Math.abs(gain - (made + carried)) > 1e-5, "read the other way round, the amounts do not add up");
  // Where the cell's amount does not follow, no reading holds: the record has no sign and no kind, and nothing is said of its direction.
  const loose = bad.record("exchange_moved_fmol");
  assert.deepEqual([loose.sign, loose.kind], [undefined, undefined]);
  assert.ok(!bad.view.derivation.some((line) => /exchange route is positive/.test(line)));
});

test("an example says of itself that it is one: its view carries the word, names no model, and it is listed only under an entry that says so", () => {
  const { view, file } = open(all, SHEET);
  assert.deepEqual(validateReplay(file), []);
  assert.deepEqual(view.example, { says: "Invented numbers · no run of Cells' engine", made_by: "tools/make_run_fixture.py" });
  assert.match(view.derivation[0], /^Invented numbers · no run of Cells' engine\. Every number of this run was written by the run-fixture tool.*No engine ran, and no model is named as the owner of a record\.$/);
  assert.deepEqual(view.run.engine_models, []);
  assert.deepEqual([...new Set(view.records.filter((item) => item.id !== "t").map((item) => item.owner))], [undefined], "no record names a model as its owner");
  assert.equal(view.run.class, undefined, "an example has no result class");
  const row = catalogue.runs.find((item) => item.id === SHEET), entry = catalogue.experiments.find((item) => item.id === EXAMPLE);
  assert.deepEqual([row.example, entry.example, entry.outcome, row.class], [true, true, undefined, undefined]);
  // No other run is one.
  for (const other of catalogue.runs.filter((item) => item.id !== SHEET)) {
    assert.equal(other.example, undefined);
    assert.equal(open(all, other.id).view.example, undefined);
  }
  // An example under an entry that does not say so is refused, and so is a run that is none under an entry that does.
  const overlay = readJson(path.join(FIXTURES, "overlay.json"));
  const wrong = path.join(scratch, "overlay-wrong.json");
  delete overlay.experiments[EXAMPLE].example;
  overlay.experiments[WORLD].example = true;
  writeFileSync(wrong, JSON.stringify(overlay));
  const target = path.join(scratch, "wrong-heading");
  const asExperiment = tool("--evidence", FIXTURES, "--experiment", EXAMPLE, "--overlay", wrong, "--selection", path.join(FIXTURES, "selection.json"), "--out", target);
  assert.notEqual(asExperiment.status, 0);
  assert.match(asExperiment.stderr, /the run is an example with invented numbers, and its catalogue entry does not say so/);
  const asExample = tool("--evidence", FIXTURES, "--experiment", WORLD, "--overlay", wrong, "--selection", path.join(FIXTURES, "selection.json"), "--out", target);
  assert.notEqual(asExample.status, 0);
  assert.match(asExample.stderr, /its catalogue entry calls it an example, and the run folder does not/);
  assert.ok(!existsSync(path.join(target, "index.json")), "nothing is catalogued");
});

test("what one cycle of a pump moves and what a channel population lets through are the definition's own, and the example's totals keep the engine's shapes", () => {
  const { view, record } = open(all, SHEET);
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  // In the shape the engine's own run view gives a pump: what one cycle moves, by role, a positive count into the cell.
  assert.equal(sets.membrane.pumps.length, 19);
  assert.deepEqual(sets.membrane.pumps[0], { id: "pump_0", law_id: "nak_atp_mass_action_positive@1", per_cycle: [{ role: "sodium", species: "Na", count: -3 }, { role: "potassium", species: "K", count: 2 }], per_cycle_sign: "inward-positive" });
  assert.ok(view.derivation.some((line) => /^What one cycle of each membrane's pump moves is the pump's own declaration in the run's definition/.test(line)));
  assert.equal(sets.channel.ids.length, 38);
  assert.deepEqual([sets.channel.ids.slice(0, 2), sets.channel.species.slice(0, 2), sets.channel.geometry.index.slice(0, 4)], [["kir_0", "nal_0"], [["K"], ["Na"]], [0, 0, 1, 1]]);
  // Totals and ledgers under the engine's names, each over the set the engine keeps it for; the spare column of capacity is cut.
  const shapes = Object.fromEntries(["channel_transferred", "pump_cycles", "membrane_transferred.K", "junction_transferred.K", "junction_dissipated_energy_pJ", "channel_dissipated_energy_pJ", "membrane_dissipated_energy_pJ", "pump_dissipated_energy_pJ"].map((id) => [id, [record(id).set, record(id).shape[1], record(id).kind]]));
  assert.deepEqual(shapes, {
    channel_transferred: ["channel", 38, "cumulative"], pump_cycles: ["membrane", 19, "cumulative"], "membrane_transferred.K": ["membrane", 19, "cumulative"], "junction_transferred.K": ["junction", 42, "cumulative"],
    junction_dissipated_energy_pJ: ["junction", 42, "cumulative"], channel_dissipated_energy_pJ: ["channel", 38, "cumulative"], membrane_dissipated_energy_pJ: ["membrane", 19, "cumulative"], pump_dissipated_energy_pJ: ["membrane", 19, "cumulative"],
  });
  for (const id of ["junction_dissipated_energy_pJ", "channel_dissipated_energy_pJ", "membrane_dissipated_energy_pJ", "pump_dissipated_energy_pJ"]) assert.equal(record(id).monotone, "non-decreasing", id);
  // The membrane's own total is its passive routes only, and says so; what its channels and its pump carried are their own records.
  assert.match(record("membrane_transferred.K").note, /^the passive membrane routes only/);
  assert.equal(record("pump_cycles").sign.from, "outside node", "pump cycles are positive inwards");
  assert.equal(record("channel_transferred").sign.from, "cell");
  // The world of the first feed has no pump and no channel population: its view states neither.
  const world = open(all, SECRETING).view;
  assert.equal(world.sets.find((item) => item.id === "membrane").pumps, undefined);
  assert.equal(world.sets.find((item) => item.id === "channel"), undefined);
});

// ---------------------------------------------------------------- a run with the engine's own view beside its files

test("a run with the engine's own view is packaged from that view: its kinds, its signs by role, its layers and owners, and nothing of the adapter's own", () => {
  const { view, file, record } = open(all, VIEWED);
  assert.deepEqual(validateReplay(file), []);
  assert.match(view.derivation[0], /^Read from the engine's own view of the run \(view\.json, cells\.run_view@1\), beside its files: every set, unit, kind, sign, owner and layer is as that view declares it\. The viewer adds no table of its own and reads nothing out of the arrays' values/);
  // What the view says of the run, and of each layer: who owns it and how it is represented.
  assert.deepEqual([view.run.label, view.run.revision, view.run.engine_models.length, view.run.stop], ["synthetic fixture: a small world with a view", "0123456", 4, "complete"]);
  assert.deepEqual(view.layers, [
    { id: "membrane", label: "Membrane voltage and ions", representation: "simulated", owner: "resolved_pump_tissue@3" },
    { id: "pumps", label: "Pump populations", representation: "modelled", owner: "resolved_pump_tissue@3" },
    { id: "turnover", label: "Species turnover", representation: "prescribed", owner: "scheduled_species_turnover@1" },
    { id: "exchange", label: "Species exchange", representation: "prescribed", owner: "scheduled_species_exchange@1" },
  ]);
  // A sign is the view's own, by the roles of the record's set, with who confirmed it: no word of the adapter's is put beside it.
  assert.deepEqual(record("face_transferred.S").sign, { confirmed: "synthetic fixture: written with the rest", from: "sender", says: "a positive amount leaves the face's sender node for its receiver", to: "receiver" });
  assert.deepEqual([record("membrane_transferred.S").sign.from, record("pump_cycles").sign.from, record("reservoir_supplied.S").sign.from], ["inside", "outside", "exterior"]);
  for (const item of view.records) assert.equal(item.sign?.by, undefined, `${item.id}: no reading of the adapter's`);
  // What the view does not state is not stated: the operators' ledgers have no kind and no direction here, the voltages no sign,
  // though the same numbers without a view get them from the adapter's own readings.
  assert.deepEqual([record("exchange_moved_fmol").kind, record("exchange_moved_fmol").sign, record("turnover_produced_fmol.S").kind, record("turnover_produced_fmol.S").monotone, record("membrane_voltage_V").sign], [undefined, undefined, undefined, undefined, undefined]);
  assert.deepEqual([open(all, SECRETING).record("exchange_moved_fmol").kind, open(all, SECRETING).record("turnover_produced_fmol.S").kind], ["cumulative", "cumulative"], "the same world with no view of the engine's");
  assert.deepEqual(view.unstated.map((item) => [item.id, item.what]), [["geometry", "geometry"], ["exchange_moved_fmol", "kind"], ["turnover_cleared_fmol", "kind"], ["turnover_outside_cleared_fmol", "kind"], ["turnover_produced_fmol", "kind"]]);
  assert.equal(view.unstated[1].why, "scheduled_species_exchange@1 declares no kind for it");
  // The heat ledgers say in the engine's word that they only grow; each record names its array and its time base.
  assert.deepEqual([record("face_dissipated_energy_pJ").monotone, record("face_dissipated_energy_pJ").array, record("face_dissipated_energy_pJ").base, record("face_dissipated_energy_pJ").owner], ["non-decreasing", "observed_face_dissipated_energy_pJ", "observation", "resolved_pump_tissue@3"]);
  // The sets as the view names them: what a membrane and a route are called, which bath is a reservoir, each species' valence.
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  assert.deepEqual([sets.membrane.holds, sets.exchange_route.holds, sets.exchange_route.geometry, sets.exchange_route.owner], ["membrane patch", "exchange route", { kind: "on", set: "membrane", index: [1, 1] }, "scheduled_species_exchange@1"]);
  assert.deepEqual([sets.outside.reservoir, sets.species.valence, sets.membrane.pumps], [[true, false], [1, 1, -1, 0], undefined]);
  // The species an operator declares is taken as the secreted one, and the view says that this is the viewer's reading of it.
  assert.deepEqual(sets.species.secreted, ["S"]);
  assert.ok(view.derivation.some((line) => /^The species an operator of the run declares \(S, by scheduled_species_turnover@1\) is taken as the species the run secretes: the view names the operator that declares it, and does not itself call it secreted\.$/.test(line)));
  // The constants are the view's own, with its own words for why nothing changes them; a flag is no number a layer reads.
  assert.deepEqual(view.constants.map((item) => item.id), ["temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area"]);
  assert.deepEqual(view.constants[0], { id: "temperature", unit: "K", axes: [], values: 310, from: "the definition (the bound layout)", says: "no operator of this composition changes it" });
  // No positions in the view: the tiles are the viewer's own layout, as for the same world without a view.
  assert.deepEqual(sets.outside.geometry.faces, open(all, SECRETING).view.sets.find((item) => item.id === "outside").geometry.faces);
});

test("a slot with no name is left out with its column, and the replay steps through one of the view's two time bases", () => {
  const { view, record, run } = open(all, VIEWED);
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  // The cells' second slot has no name in the view: it is padding, and neither the set nor an array keeps it.
  assert.deepEqual(sets.cell.ids, ["cell_0"]);
  assert.deepEqual([record("amount.S").shape, record("cell_potential_V").shape, view.constants.find((item) => item.id === "volume").values], [[5, 1], [5, 1], [1]]);
  assert.ok(view.derivation.some((line) => line === "Slots the view gives no name (padding) are left out, with their columns: 1 of cell."));
  // The observed rows are the replay's records; the state's rows are named, with how many there are.
  assert.deepEqual(view.time, { unit: "s", record: "t", base: { id: "observation", says: "the observed rows", others: [{ id: "accepted", says: "the state's accepted rows", rows: 9 }] } });
  assert.deepEqual([run.count, run.start, run.end], [5, 0, 4]);
  assert.ok(view.derivation.some((line) => /^The replay steps through the view's time base 'observation' \(the observed rows\): 5 records\./.test(line)));
  // A field saved with the state too is packaged once, from the observed rows.
  assert.equal(record("amount.S").base, "observation");
  assert.ok(view.derivation.some((line) => /^1 record\(s\) of the view's other time base hold the same fields as records packaged here/.test(line)));
  // A field saved with the state only is packaged at the rows of that base that fall on the replay's times, and says so.
  const cleared = record("turnover_cleared_fmol.S");
  assert.deepEqual([cleared.base, cleared.array, cleared.rows, cleared.shape, cleared.kind], ["accepted", "turnover_cleared_fmol", "the row of the base 'accepted' that falls on each of the replay's times", [5, 1], undefined]);
  const part = readJson(path.join(all, `${VIEWED}.${cleared.part}.json`));
  const bytes = Buffer.from(part.payload.data, "base64");
  const values = new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), cleared.offset, 5);
  assert.deepEqual(Array.from(values, (value) => Number(value.toExponential(3))), [0, 1e-6, 2e-6, 3e-6, 4e-6], "the rows at 0, 1, 2, 3 and 4 s of nine");
  assert.ok(view.derivation.some((line) => line === "Saved on another time base only, and packaged at the rows of that base that fall on the replay's times: turnover_cleared_fmol."));
});

test("a retirement is an event of the view, and a total that restarts there says so in place of claiming that it only grows", () => {
  const { view, file, record } = open(all, RETIRING);
  assert.deepEqual(validateReplay(file), []);
  assert.deepEqual(view.events, [{ time: 2.5, kind: "retirement", layer: "replacement", label: "cell_0 retired", at: { set: "cell", index: 0 } }]);
  assert.deepEqual(view.sets.find((item) => item.id === "cell").lifetimes, [[null, 2.5]]);
  const heat = record("membrane_dissipated_energy_pJ");
  assert.deepEqual([heat.kind, heat.monotone, heat.resets.by], ["cumulative", undefined, ["scheduled_cell_replacement@1"]]);
  assert.match(heat.resets.says, /on a retired slot the ledger restarts at zero/);
  assert.equal(record("face_dissipated_energy_pJ").monotone, "non-decreasing", "a ledger no retiring operator writes still only grows");
  // The layer of the operator that retires goes with its event, with its owner: that is how a reader knows which events restart a total.
  assert.deepEqual(view.layers.find((layer) => layer.id === "replacement"), { id: "replacement", label: "Cell replacement", representation: "prescribed", owner: "scheduled_cell_replacement@1" });
  assert.equal(open(all, VIEWED).view.layers.some((layer) => layer.id === "replacement"), false);
});

test("a view the adapter cannot read whole is refused with the reason, and nothing is written", () => {
  const broken = (name, change) => {
    const copy = path.join(scratch, `view-${name}`);
    cpSync(path.join(FIXTURES, "run-world"), path.join(copy, "run-world"), { recursive: true });
    const file = path.join(copy, "run-world", "viewed", "view.json");
    const view = readJson(file);
    change(view, path.join(copy, "run-world", "viewed"));
    writeFileSync(file, JSON.stringify(view));
    const target = path.join(scratch, `view-${name}-out`);
    return [tool("--experiment", WORLD, "--root", path.join(copy, "run-world"), "--run", "viewed", ...SHARED, "--out", target), target];
  };
  for (const [name, change, message] of [
    ["subset", (view) => (view.recording.subset = { fields: ["amount"], elements: null, every: 2 }), /its view gives records of .*, which its recording subset does not keep/],
    ["format", (view) => (view.format = "cells.run_view@2"), /its view\.json is not a run view \(cells\.run_view@1\)/],
    ["keys", (view) => delete view.unstated, /its view\.json lacks unstated/],
    ["array", (view) => (view.records.find((item) => item.id === "observed_amount").array = "observed_amounts"), /trajectory\.npz does not hold observed_amounts, which its view says is saved there/],
    ["rows", (view) => (view.time.bases[1].files[0].rows = [0, 4]), /trajectory\.npz does not hold the rows its view gives it for the time base observation/],
    ["shape", (view) => view.sets.find((item) => item.id === "cell").ids.push(null), /does not have the shape its view's axes give it/],
    ["example", (view, folder) => writeFileSync(path.join(folder, "example.json"), JSON.stringify({ example: true, says: "Example: invented numbers" })), /an example with invented numbers has no view of the engine's/],
  ]) {
    const [result, target] = broken(name, change);
    assert.notEqual(result.status, 0, name);
    assert.match(result.stderr, message, name);
    assert.ok(!existsSync(path.join(target, "index.json")), `${name}: nothing is catalogued`);
  }
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

// ---------------------------------------------------------------- views written by the engine's own writer
//
// tests/engine-views/run-view-fd008813 holds small runs that the engine's run-view writer wrote on its development
// branch, now on main through its merge (run-view-d154 at fd008813; tools/make_engine_view_fixture.sh makes them again): the short secretion world through
// io.write_run, and S5's partition world, a division, through the windowed path. They are the writer's output, kept
// apart from the fixtures the run-fixture tool writes. A test that needs a view the writer does not give (a source, a
// loop, a contradiction) changes a copy, and says so.

const WRITER = path.join(ROOT, "tests", "engine-views", "run-view-fd008813");
const VIEWS = "engine-views";
const VIEW_ARGS = ["--overlay", path.join(scratch, "views-overlay.json"), "--selection", path.join(scratch, "views-selection.json")];
writeFileSync(VIEW_ARGS[1], JSON.stringify({ format: "cells.visualizer.replay_overlay@1", experiments: { [VIEWS]: { adapter: "standard-history", development: true, label: "The run view's writer (test fixture)", plain: "Two unit-test worlds the engine's run-view writer wrote on its branch.", sources: [], engine_entities: [], outcome: { judged: false, status: "A development run: not judged" }, parameters: {}, readouts: {}, events: { current: { label: "Electrode current", plain: "The electrode's current changes." } }, stops: { complete: { label: "Ran to its end" } } } } }));
writeFileSync(VIEW_ARGS[3], JSON.stringify({ [VIEWS]: { evidence_folder: path.basename(WRITER), runs: ["secretion", "division"] } }));
const viewsOut = path.join(scratch, "views-out");
const viewsDone = tool("--experiment", VIEWS, "--root", WRITER, ...VIEW_ARGS, "--out", viewsOut);
assert.equal(viewsDone.status, 0, `the adapter failed on the writer's views:\n${viewsDone.stderr}`);
const { layers: LAYERS } = readDeclarations(declaredLayers, MARKS);
const writtenView = (world) => readJson(path.join(WRITER, world, "view.json"));

/** A packaged run opened with every one of its parts attached, as the page has it once each is fetched. */
function openWhole(folder, id) {
  const opened = open(folder, id);
  for (const part of opened.view.parts || []) {
    const held = readJson(path.join(folder, path.basename(part.file)));
    opened.run.attach(part.id, Uint8Array.from(Buffer.from(held.payload.data, "base64")).buffer);
  }
  return opened;
}

/** The secretion world (or another) with its view changed in a copy, adapted; [result, output folder, run id]. */
function changedView(label, change, world = "secretion") {
  const copy = path.join(scratch, `writer-${label}`);
  cpSync(WRITER, copy, { recursive: true });
  const file = path.join(copy, world, "view.json");
  const view = readJson(file);
  change(view, path.join(copy, world));
  writeFileSync(file, JSON.stringify(view));
  const target = path.join(scratch, `writer-${label}-out`);
  return [tool("--experiment", VIEWS, "--root", copy, "--run", world, ...VIEW_ARGS, "--out", target), target, `${VIEWS}--${world}`];
}

test("the kept views are the writer's own, of the revision their note names", () => {
  const note = readFileSync(path.join(WRITER, "README.md"), "utf8");
  assert.match(note, /branch run-view-d154, fd008813/);
  assert.match(note, /fd00881394d10fd33c05e47e17c88838fcf2b7c7/);
  // The writer learns its source only from an execution snapshot, which an export is not: the one revision in the views is a planted label.
  assert.match(note, /is a caller's label \*\*planted\*\* by the script;\s+it is not the engine's own word for its source/);
  assert.deepEqual([writtenView("secretion").run.revision, writtenView("subset").run.revision, writtenView("division").run.revision], ["fd008813", undefined, undefined]);
  for (const world of ["secretion", "subset", "division"]) {
    const view = writtenView(world);
    assert.equal(view.run.source, undefined, `${world}: no engine source`);
    assert.equal(view.format, "cells.run_view@1");
    assert.deepEqual(Object.keys(view).sort(), ["constants", "events", "format", "layers", "recording", "records", "run", "sets", "space", "time", "unstated"], `${world}: the writer's top-level keys, and no loop block (not built at this revision)`);
    assert.deepEqual(view.unstated.find((item) => item.id === "source")?.what, "engine source", `${world}: run from an export, the writer states no engine source and says why`);
  }
  const size = (folder) => readdirSync(folder, { withFileTypes: true }).reduce((total, item) => total + (item.isDirectory() ? size(path.join(folder, item.name)) : statSync(path.join(folder, item.name)).size), 0);
  assert.ok(size(WRITER) < 500_000, `the kept views are ${size(WRITER)} bytes`);
  assert.ok(!PATHS.test(readdirSync(WRITER, { recursive: true }).filter((name) => /\.(json|jsonl|md)$/.test(name)).map((name) => readFileSync(path.join(WRITER, name), "utf8")).join("\n")), "no kept text file names a machine path");
});

test("a view from the engine's writer: a voltage's difference is the run's own sign, and the layers that need it are offered", () => {
  const { view, file, record, run } = openWhole(viewsOut, `${VIEWS}--secretion`);
  assert.deepEqual(validateReplay(file), []);
  const stated = writtenView("secretion").records.find((item) => item.id === "observed_membrane_voltage_V").difference;
  assert.deepEqual([stated.plus, stated.minus], ["inside", "outside"]);
  // The difference is carried as written; the page's sign says which side is the higher, in the view's own words and with their source.
  assert.deepEqual(record("membrane_voltage_V").difference, stated);
  assert.deepEqual(record("membrane_voltage_V").sign, { says: stated.says, high: "inside", source: stated.source });
  for (const item of view.records) assert.equal(item.sign?.by, undefined, `${item.id}: no reading of the adapter's`);
  assert.ok(view.derivation.some((line) => line.startsWith("Which way membrane_voltage_V is positive is the run's own statement (its difference, plus less minus by the roles of its set)") && line.includes(stated.source)));
  // The committed adapter read the same view with no sign for the voltage, and these two layers were not offered.
  const offered = Object.fromEntries(layersFor(run, LAYERS, MARKS).map((offer) => [offer.layer.id, offer.ok]));
  assert.deepEqual([offered["ion-push-pull"], offered["membrane-charge"], offered.transfers], [true, true, true]);
  // The roles of each set, with what each is, come with it; a flow's sign names two of them.
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  assert.deepEqual(sets.membrane.roles, writtenView("secretion").sets.find((item) => item.id === "membrane").roles);
  assert.ok(sets.membrane.roles[record("membrane_transferred.S").sign.from] && sets.membrane.roles[record("membrane_transferred.S").sign.to]);
  assert.equal(sets.cell.roles, undefined, "a set that states no roles gets none");
  // Changed copies: the higher end is read from the role `plus`, whichever it is; a role the page has no word for gives no sign.
  const [swapped, swappedOut, id] = changedView("difference-swapped", (view) => {
    const difference = view.records.find((item) => item.id === "observed_membrane_voltage_V").difference;
    [difference.plus, difference.minus] = [difference.minus, difference.plus];
  });
  assert.equal(swapped.status, 0, swapped.stderr);
  assert.equal(open(swappedOut, id).record("membrane_voltage_V").sign.high, "outside");
  const [wordless, wordlessOut] = changedView("difference-wordless", (view) => {
    view.sets.find((item) => item.id === "membrane").roles.lumen = "a planted role, with no word of the page's";
    view.records.find((item) => item.id === "observed_membrane_voltage_V").difference.plus = "lumen";
  });
  assert.equal(wordless.status, 0, wordless.stderr);
  const unread = open(wordlessOut, id);
  assert.deepEqual([unread.record("membrane_voltage_V").difference.plus, unread.record("membrane_voltage_V").sign], ["lumen", undefined]);
  assert.ok(unread.view.derivation.includes("The view states which way membrane_voltage_V is positive between roles the page has no word for: the difference is carried as written, with no sign, and the page draws no direction for it."));
});

test("a view from the engine's writer: each route's species, direction and kind are the run's, and the secreted species rests on them", () => {
  const { view, record } = open(viewsOut, `${VIEWS}--secretion`);
  const sets = Object.fromEntries(view.sets.map((item) => [item.id, item]));
  // The exchange routes: the species each carries is the set's species (what the page reads for a route), with its declared direction.
  assert.deepEqual([sets.exchange_route.ids, sets.exchange_route.species, sets.exchange_route.direction, sets.exchange_route.holds], [["secrete", "sink"], ["S", "S"], ["export", "import"], "exchange route"]);
  assert.deepEqual(record("exchange_moved_fmol").sign, writtenView("secretion").records.find((item) => item.id === "observed_exchange_moved_fmol").sign, "the route's total has the sign its operator declares");
  // Turnover's routes lie on no record's axis, and are carried for what the view states of them: where each acts, and its kind.
  assert.deepEqual([sets.turnover_route.species, sets.turnover_route.kinds, sets.turnover_route.at], [["S", "S"], ["production", "clearance"], [{ cell: "cell_0" }, { outside: "ecs_0" }]]);
  assert.ok(view.derivation.includes("What the run's operators state of each of their entities is carried as the view gives it (turnover_route: produce (production) carries S at cell_0; clear (clearance) carries S at ecs_0 | exchange_route: secrete (export) carries S; sink (import) carries S); a route's species is the one the view says it carries."));
  // "Secreted" stays the viewer's word, now resting on what the view states of each route.
  assert.deepEqual(sets.species.secreted, ["S"]);
  assert.ok(view.derivation.some((line) => /^The species that the run's operators carry, make or clear \(S, by what the view states of each of their entities: turnover_route, exchange_route\) is taken as the species the run secretes: the view states which species each entity carries, and does not itself call any species secreted\.$/.test(line)));
});

test("a view from the engine's writer: its revision, how it ended and which row an event's time holds are the run's own words", () => {
  const { view } = open(viewsOut, `${VIEWS}--secretion`);
  const written = writtenView("secretion");
  // Run from an export, the writer states no engine source: the revision given is the caller's label, and said to be.
  assert.equal(view.run.revision, written.run.revision);
  assert.equal(view.run.source, undefined);
  assert.ok(view.derivation.includes(`The view does not state the engine's own source (${written.unstated.find((item) => item.id === "source").why}). The revision given, fd008813, is the caller's label for the run (run.revision), not the engine's own record of its source.`));
  assert.deepEqual([view.run.end, view.run.stop], [written.run.end, "complete"]);
  assert.ok(view.derivation.includes("How the run ended is the run's own statement (run.end): 'complete' at 0.01 s, at step 10."));
  assert.equal(view.time.event_rows, written.time.event_rows);
  assert.ok(view.derivation.some((line) => line.endsWith(`(time.event_rows), carried as written: ${written.time.event_rows}`)));
  // The division world gives no caller's label either: no revision at all.
  const division = open(viewsOut, `${VIEWS}--division`).view;
  assert.equal(division.run.revision, null);
  assert.ok(division.derivation.some((line) => /^The view does not state the engine's own source \(.*\)\. No revision is given\.$/.test(line)));
});

test("a view from the engine's writer: a division's events, the slots that restart, and the merged views its operators change", () => {
  const { view, file, record, run } = openWhole(viewsOut, `${VIEWS}--division`);
  assert.deepEqual(validateReplay(file), []);
  const written = writtenView("division");
  assert.deepEqual(view.events.map((event) => [event.time, event.kind, event.at]), [[0.002, "birth", { set: "cell", index: 1 }], [0.002, "birth", { set: "cell", index: 2 }], [0.002, "retirement", { set: "cell", index: 0 }]]);
  assert.deepEqual(view.sets.find((item) => item.id === "cell").lifetimes, [[null, 0.002], [0.002, null], [0.002, null]]);
  // Which slots restart is the run's own statement: the mask of the record's set (resets.mask), carried with the rest of resets.
  const heat = record("membrane_dissipated_energy_pJ");
  assert.deepEqual(heat.resets, written.records.find((item) => item.id === "observed_membrane_dissipated_energy_pJ").resets);
  assert.equal(heat.resets.mask, "membrane_active");
  assert.ok(view.derivation.some((line) => line.startsWith("Which slots restart when an operator retires one is the run's own statement") && line.includes("membrane_dissipated_energy_pJ: membrane_active")));
  // What the composition changes is a merged view at each observed row: the two a layer reads are packaged under the field's own name.
  const area = record("membrane_area");
  assert.deepEqual([area.array, area.base, area.kind, area.set, area.unit, area.owner], ["view_membrane_area", "observation", "level", "membrane", "m2", "membrane_entity_state@1"]);
  assert.ok(!view.constants.some((item) => item.id === "membrane_area"), "a field the composition changes is no constant");
  assert.ok(view.derivation.includes("Changed by the run's operators, and so saved as the merged view at each observed row (the arrays view_<field>), not as constants: membrane_area, membrane_capacitance, packaged under the field's own name."));
  assert.ok(view.derivation.some((line) => line.startsWith("The view saves the merged view of 9 more field(s) that the run's operators change, which no layer of the page reads; they are not packaged: active, ")));
  const offered = Object.fromEntries(layersFor(run, LAYERS, MARKS).map((offer) => [offer.layer.id, offer.ok]));
  assert.equal(offered["membrane-charge"], true, "the membrane's charge is read from the merged area and capacitance");
});

test("the engine's own source: the replay's revision is filled from it, and a dirty tree is carried and said", () => {
  // A changed copy: the writer states a source only from an execution snapshot, which the kept views were not run from.
  const source = { revision: "fd00881394d10fd33c05e47e17c88838fcf2b7c7", dirty: true, from: "the execution snapshot's record (SNAPSHOT.json)" };
  const [result, target, id] = changedView("source", (view) => {
    view.run.source = source;
    view.unstated = view.unstated.filter((item) => item.id !== "source");
  });
  assert.equal(result.status, 0, result.stderr);
  const { view, run } = open(target, id);
  assert.deepEqual([view.run.revision, view.run.source], [source.revision, source]);
  assert.ok(view.derivation.includes(`The engine's revision is the run's own record of its source (run.source, from ${source.from}): ${source.revision}; its tree was dirty when the run was made, so the revision alone does not give the source that ran: the difference is in the run's frozen snapshot, which the view does not carry.`));
  assert.equal(run.info.source.dirty, true);
  // A caller's label that is the same revision, shorter, is no contradiction; another revision is.
  const [other] = changedView("two-revisions", (view) => {
    view.run.source = source;
    view.run.revision = "0123abcd";
    view.unstated = view.unstated.filter((item) => item.id !== "source");
  });
  assert.notEqual(other.status, 0);
  assert.match(other.stderr, /its view names two revisions for the run: 0123abcd as the caller's label \(run\.revision\) and fd00881394d10fd33c05e47e17c88838fcf2b7c7 as the engine's own source \(run\.source\)/);
});

test("a loop block is carried in the shape the page's loop reader takes", () => {
  // The writer at fd008813 builds no loop block (FR-11's design): a changed copy gives one in the designed shape. The
  // writer refuses a loop without the engine's source, so the copy is given one too, planted for this test: the kept
  // views state none (their revision is a caller's label, which the loop reader must not take as the engine's).
  const closes = { within: 3e-7, tolerance: 1e-4, says: "the last record meets the first within 3e-7" };
  const planted = { revision: "0000000000000000000000000000000000000000", dirty: false, from: "planted by this test" };
  const asLoop = (loop) => (view) => {
    view.loop = loop;
    delete view.run.revision;
    view.run.source = planted;
    view.unstated = view.unstated.filter((item) => item.id !== "source");
  };
  const [result, target, id] = changedView("loop", asLoop({ species: "planarian", cell: "cell_0", period: 0.01, closes, follows: [] }));
  assert.equal(result.status, 0, result.stderr);
  const { view, run } = open(target, id);
  assert.deepEqual(view.loop, { species: "planarian", cell: "cell_0", period: 0.01, closes, follows: [] });
  const read = readLoop(run, "planarian");
  assert.equal(read.ok, true, read.why);
  assert.deepEqual([read.loop.cell, read.loop.revision, read.loop.closes, read.loop.length], [0, planted.revision, closes, 0.01]);
  // With only the kept view's caller's label, a loop is refused: the writer writes one only for a run that names its
  // engine's source, and a caller's label is no engine's word for a looping package's revision.
  const [labelled, labelledOut] = changedView("loop-label", (view) => (view.loop = { species: "planarian", cell: "cell_0", period: 0.01, closes }));
  assert.notEqual(labelled.status, 0);
  assert.match(labelled.stderr, /its view gives a loop for a run that names no engine source \(run\.source\)/);
  assert.ok(!existsSync(path.join(labelledOut, "index.json")));
  // Refused, each with what and where.
  for (const [label, loop, message] of [
    ["loop-open", { species: "planarian", cell: "cell_0", period: 0.01, closes: { ...closes, within: 2e-4 } }, /its view's loop says its last record meets its first within 0\.0002, above its own tolerance of 0\.0001/],
    ["loop-period", { species: "planarian", cell: "cell_0", period: 0.02, closes }, /its view's loop gives a period of 0\.02 s, and its records span 0\.01 s: they must be the same/],
    ["loop-cell", { species: "planarian", cell: "cell_9", period: 0.01, closes }, /its view's loop is of a cell the run does not have \(cell_9\)/],
    ["loop-follows", { species: "planarian", cell: "cell_0", period: 0.01, closes, follows: [{ time: 0.005, from: "cell_0", to: "d1" }] }, /its view's loop follows a cell the run does not have/],
    ["loop-shape", { species: "planarian", cell: "cell_0", closes }, /its view's loop does not give its species, cell, period and closure/],
  ]) {
    const [refused, out] = changedView(label, asLoop(loop));
    assert.notEqual(refused.status, 0, label);
    assert.match(refused.stderr, message, label);
    assert.ok(!existsSync(path.join(out, "index.json")), `${label}: nothing is catalogued`);
  }
});

test("a view of the writer's shape that contradicts itself, or that the page could not honour, is refused with what and where", () => {
  const record = (view, id) => view.records.find((item) => item.id === id);
  const set = (view, id) => view.sets.find((item) => item.id === id);
  for (const [label, change, message, world] of [
    ["sign-and-difference", (view) => (record(view, "observed_membrane_voltage_V").sign = { from: "inside", to: "outside", says: "s" }), /its view's record observed_membrane_voltage_V gives both a sign \(a flow's ends\) and a difference/],
    ["sign-roles", (view) => (record(view, "observed_membrane_transferred").sign.to = "receiver"), /its view's record observed_membrane_transferred names, as the ends its sign goes from and to, what are not two roles of its set membrane/],
    ["difference-roles", (view) => (record(view, "observed_membrane_voltage_V").difference.minus = "inside"), /its view's record observed_membrane_voltage_V gives a difference whose plus and minus are not two roles of its set membrane/],
    ["difference-without-roles", (view) => delete set(view, "membrane").roles, /gives a difference whose plus and minus are not two roles of its set membrane/],
    ["roles", (view) => (set(view, "membrane").roles = { inside: "" }), /its view gives the set membrane roles that do not each say what the role is/],
    ["carries-count", (view) => set(view, "exchange_route").carries.pop(), /its view gives the set exchange_route 'carries' that is not one value for each of its entities/],
    ["carries-species", (view) => (set(view, "exchange_route").carries[0] = "Xe"), /its view says an entity of exchange_route carries a species that is not among the run's species/],
    ["at", (view) => (set(view, "turnover_route").at[0] = { cell: "cell_9" }), /its view says an entity of turnover_route acts at an entity that is not one of the view's/],
    ["direction", (view) => (set(view, "exchange_route").direction[1] = 7), /its view gives the set exchange_route 'direction' that is not a word for each of its entities/],
    ["source", (view) => (view.run.source = { revision: "fd008813", dirty: "no", from: "x" }), /its view's run\.source does not give the engine's revision, whether its tree was dirty, and where that is recorded/],
    ["source-unstated", (view) => (view.run.source = { revision: "fd008813", dirty: false, from: "x" }), /its view states the engine's source \(run\.source\) and also lists it as unstated/],
    ["end", (view) => (view.run.end = { status: "complete", time: 0.01 }), /its view's run\.end does not give the run's status, its end time and its step/],
    ["end-status", (view) => (view.run.end.status = "refused"), /its view says the run ended 'refused' \(run\.end\), and its summary\.json says 'complete'/],
    ["end-time", (view) => (view.run.end.time = 0.005), /its view says the run ended at 0\.005 s \(run\.end\), before its last record at 0\.01 s/],
    ["event-rows", (view) => (view.time.event_rows = ""), /its view's time\.event_rows does not say in words which state a record at an event's time holds/],
    ["mask", (view) => (record(view, "observed_membrane_dissipated_energy_pJ").resets.mask = null), /its view's record observed_membrane_dissipated_energy_pJ says it restarts at a retirement, and names no mask/, "division"],
    ["constant-and-view", (view) => view.constants.push({ id: "membrane_area", axes: ["membrane"], unit: "m2", values: [1e-10, 1e-10, 1e-10], from: "the definition (the bound layout)", says: "said" }), /its view states membrane_area both as a constant of the definition and as the merged view the composition changes \(view_<field>\)/, "division"],
  ]) {
    const [result, target] = changedView(`bad-${label}`, change, world);
    assert.notEqual(result.status, 0, label);
    assert.match(result.stderr, message, label);
    assert.ok(!existsSync(path.join(target, "index.json")), `${label}: nothing is catalogued`);
  }
});

// ---------------------------------------------------------------- a recorded subset, and the engine's first looping run
//
// tests/engine-views/run-view-fd008813/subset: the short secretion world with a recording subset, as the branch's own test
// records one (four fields, of the species only S, every second observed row). tests/engine-views/loop-d7a11d5b: the
// interim planarian loop, a development run with no verdict that the writer at d7a11d5b wrote from an execution snapshot,
// copied unchanged from the engine's lead's folder; its writer is on main since 050aa741.

const LOOPS = path.join(ROOT, "tests", "engine-views", "loop-d7a11d5b");
const LOOP_RUN = "planarian-d7a11d5b", LOOP_ID = `${VIEWS}--${LOOP_RUN}`;
const loopsOut = path.join(scratch, "loops-out");
const loopsDone = tool("--experiment", VIEWS, "--root", LOOPS, "--run", LOOP_RUN, ...VIEW_ARGS, "--out", loopsOut);
assert.equal(loopsDone.status, 0, `the adapter failed on the looping run:\n${loopsDone.stderr}`);
const loopView = () => readJson(path.join(LOOPS, LOOP_RUN, "view.json"));

/** The looping run with its view changed in a copy, adapted; [result, output folder]. */
function changedLoop(label, change) {
  const copy = path.join(scratch, `loop-${label}`);
  cpSync(LOOPS, copy, { recursive: true });
  const file = path.join(copy, LOOP_RUN, "view.json");
  const view = readJson(file);
  change(view);
  writeFileSync(file, JSON.stringify(view));
  const target = path.join(scratch, `loop-${label}-out`);
  return [tool("--experiment", VIEWS, "--root", copy, "--run", LOOP_RUN, ...VIEW_ARGS, "--out", target), target];
}

test("a recorded subset: what the run kept is packaged, for the recorded species and rows only, and what it did not keep is said", () => {
  const [result, target, id] = changedView("subset-read", () => {}, "subset");
  assert.equal(result.status, 0, result.stderr);
  const { view, file, run } = open(target, id);
  assert.deepEqual(validateReplay(file), []);
  const written = writtenView("subset");
  assert.deepEqual(written.recording.subset, { elements: { species: ["S"] }, every: 2, fields: ["membrane_voltage_V", "cell_potential_V", "amount", "exchange_moved_fmol"] });
  // The species set stays whole; a field saved for each species is packaged for the recorded one only.
  assert.deepEqual(view.sets.find((item) => item.id === "species").ids, ["Na", "K", "Cl", "S"]);
  assert.deepEqual(view.records.filter((item) => item.field === "amount").map((item) => item.id), ["amount.S"]);
  // Every second observed row: the replay's records are the rows the run kept.
  assert.deepEqual(Array.from(run.t, (time) => Number(time.toFixed(6))), [0, 0.004, 0.008]);
  // A field the page has a name for and the subset does not list: no record, nothing standing in, and the run's reason.
  assert.equal(view.records.some((item) => item.id.startsWith("extracellular_amount")), false);
  const why = "The run's recording subset does not list it (recording.subset.fields): the run kept only the fields that list names";
  assert.deepEqual(view.unstated.find((item) => item.id === "extracellular_amount"), { id: "extracellular_amount", what: "record", why });
  assert.ok(view.derivation.includes("The run recorded a subset of itself (recording.subset, its own statement): 4 field(s) (membrane_voltage_V, cell_potential_V, amount, exchange_moved_fmol), and of the species only S, one observed row in every 2, from its first. The replay's records are the rows it kept."));
  const unkept = view.derivation.find((line) => line.startsWith("Of the fields the page has a name for, the run's recording subset lists none of these, and its view gives no record of them: "));
  assert.ok(unkept && ["extracellular_potential_V", "extracellular_amount", "membrane_transferred", "pump_cycles", "face_transferred", "turnover_produced_fmol"].every((field) => unkept.includes(field)) && !/[:,] amount[,.]/.test(unkept) && !unkept.includes("exchange_moved_fmol"), unkept);
  // This world has no junctions: what lies on them is no field the run could have kept, and is not named.
  assert.ok(!unkept.includes("junction_voltage_V") && !unkept.includes("junction_transferred"), unkept);
  assert.ok(view.derivation.includes("A field saved once for each species is packaged for the recorded species only (S); the others were not recorded."));
  // A layer that needs what the run did not keep says so, in the run's words.
  const offers = Object.fromEntries(layersFor(run, LAYERS, MARKS).map((offer) => [offer.layer.id, offer]));
  assert.equal(offers["ion-push-pull"].ok, false);
  assert.match(offers["ion-push-pull"].why, /The run's recording subset does not list it/);
});

test("the engine's first looping run: its subset, its source, its own geometry and its junction voltage, read as it states them", () => {
  const { view, file, record, run } = openWhole(loopsOut, LOOP_ID);
  assert.deepEqual(validateReplay(file), []);
  const written = loopView();
  // The note says what the run is and where it came from; the source is the run's own, from its execution snapshot.
  const note = readFileSync(path.join(LOOPS, "README.md"), "utf8");
  assert.match(note, /a development run with no verdict/);
  assert.match(note, /its writer is on main since 050aa741/);
  assert.match(note, /copied unchanged from the engine's lead's folder/);
  assert.deepEqual(written.run.source, { dirty: false, from: "the execution snapshot's record (SNAPSHOT.json)", revision: "d7a11d5b0e20f3133c081386e487fe21b8b8f893" });
  assert.deepEqual([view.run.revision, view.run.source], [written.run.source.revision, written.run.source]);
  assert.ok(view.derivation.includes("The engine's revision is the run's own record of its source (run.source, from the execution snapshot's record (SNAPSHOT.json)): d7a11d5b0e20f3133c081386e487fe21b8b8f893; its tree was clean when the run was made."));
  // 17 fields recorded, every observed row of the one period: 101 records from 8 s to 10 s.
  assert.equal(written.recording.subset.fields.length, 17);
  assert.deepEqual([run.count, run.start, run.end], [101, 8, 10]);
  for (const field of ["extracellular_amount", "membrane_dissipated_energy_pJ", "reservoir_supplied"]) assert.match(run.unstated.get(field), /^The run's recording subset does not list it/, field);
  // Only what the run could have recorded is said to be left out: not a ledger of an operator it does not have, nor a
  // field over a set it has no entity of (it has no faces). Of those, as for a full recording, nothing is said.
  const unkept = view.derivation.find((line) => line.startsWith("Of the fields the page has a name for, the run's recording subset lists none of these"));
  assert.ok(unkept.includes("extracellular_amount") && !unkept.includes("turnover_produced_fmol") && !unkept.includes("exchange_moved_fmol") && !unkept.includes("face_transferred"), unkept);
  assert.deepEqual([run.unstated.has("turnover_produced_fmol"), run.unstated.has("face_transferred")], [false, false]);
  assert.equal(new Set(written.run.composition.operators).has("scheduled_species_turnover@1"), false);
  const offers = Object.fromEntries(layersFor(run, LAYERS, MARKS).map((offer) => [offer.layer.id, offer]));
  assert.deepEqual([offers["energy-glow"].ok, offers["ion-push-pull"].ok, offers["junction-drops"].ok, offers["ion-traffic"].ok, offers.transfers.ok], [false, false, true, true, true]);
  assert.equal(offers["energy-glow"].why, "This run did not save it. The run's recording subset does not list it (recording.subset.fields): the run kept only the fields that list names.");
  // The cells stand where the run's own geometry places them: its hexagons, with the vertices they share given one index.
  const cells = view.sets.find((item) => item.id === "cell");
  const given = written.sets.find((item) => item.id === "cell").geometry;
  assert.deepEqual([given.vertices.length, cells.geometry.vertices.length, cells.geometry.faces.length], [42, 24, 7]);
  for (const [k, face] of cells.geometry.faces.entries()) {
    face.forEach((v, corner) => {
      const [x, y] = given.vertices[given.faces[k][corner]];
      assert.ok(Math.hypot(cells.geometry.vertices[v][0] - x, cells.geometry.vertices[v][1] - y) < 1e-12, `cell ${k}: its corners where the run puts them`);
    });
  }
  assert.ok(view.derivation.some((line) => /Vertices that coincide are given one index \(42 given, 24 kept\), so that the page finds the edge two cells share; the corners so joined were at most \de-1\d um apart\.$/.test(line)));
  assert.ok(view.derivation.some((line) => line.startsWith("Cell positions and shapes are the run's own geometry (prescribed, from validation/replay/planarian.py")));
  assert.ok(!view.derivation.some((line) => line.includes("the run saves no coordinates")), "nothing says the run saves no coordinates");
  // Joined corners let the page find the seam of every junction: its two cells share exactly two vertices.
  const links = view.sets.find((item) => item.id === "junction").geometry.ends;
  assert.equal(links.length, 12);
  for (const [a, b] of links) assert.equal(cells.geometry.faces[a].filter((v) => cells.geometry.faces[b].includes(v)).length, 2, `cells ${a} and ${b} share an edge`);
  // The run's events: ten current changes from 0 s. A replay runs over its records: the two that lie within the recorded
  // period are its events, and the eight before it are said, with when, never dropped in silence.
  assert.deepEqual(loopView().events.map((event) => event.time), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.deepEqual(view.events.map((event) => [event.time, event.kind, event.at]), [[8, "current", { set: "cell", index: 3 }], [9, "current", { set: "cell", index: 3 }]]);
  assert.ok(view.derivation.includes("Of the run's 10 events (of the kind 'current'), 8 lie before its recorded period, which begins at 8 s: the first at 0 s, the last at 7 s. They are not shown, because the replay runs over its records; the 2 that lie within them are."));
  for (const event of view.events) assert.ok(event.time >= run.start && event.time <= run.end, "every event lies within the records");
  // The junction voltage is the sender's potential less the receiver's: the sender is the first end the page draws from.
  assert.deepEqual([record("junction_voltage_V").sign.high, record("junction_voltage_V").difference.plus], ["first", "sender"]);
});

test("the engine's first looping run: its loop block is carried as the writer built it, and the page's loop reader takes it", () => {
  const { view, run } = openWhole(loopsOut, LOOP_ID);
  const written = loopView().loop;
  assert.deepEqual(written.closes.within, 2.7606981408476794e-05);
  assert.deepEqual([written.species, written.cell, written.period, written.closes.tolerance, written.closes.zero, written.not_measured.map((group) => group.records.length)], ["planarian", "cell_3", 2, 0.0001, [], [7]]);
  assert.deepEqual(view.loop, { species: written.species, cell: written.cell, period: written.period, closes: written.closes, not_measured: written.not_measured });
  assert.ok(view.derivation.includes(`The loop's closure leaves out 7 record(s), in the run's words '${written.not_measured[0].why}': ${written.not_measured[0].records.join(", ")}. Not measured says nothing of how they stand at the seam.`));
  const read = readLoop(run, "planarian");
  assert.equal(read.ok, true, read.why);
  const { loop } = read;
  assert.deepEqual([loop.cell, loop.membrane, loop.start, loop.length, loop.revision, loop.dirty], [3, 3, 8, 2, "d7a11d5b0e20f3133c081386e487fe21b8b8f893", false]);
  assert.deepEqual([loop.notMeasured, loop.zero], [written.not_measured, []]);
  assert.equal(engineWords(loop), "Made by the engine at revision d7a11d5b0e20f3133c081386e487fe21b8b8f893, from a clean tree");
  assert.equal(closesWords(loop), `Its last record meets its first within 2.8e-5 (tolerance 1.0e-4), in the records it measures; of its records, 7 are not measured (${written.not_measured[0].why})`);
  // The streams through the loop's cell: its channel populations, its pump, its membrane, and its six junctions.
  const streams = loopStreams(loop);
  assert.equal(streams.ok, true, streams.why);
  const count = (kind) => streams.streams.filter((stream) => stream.kind === kind).length;
  assert.deepEqual([count("channel"), count("pump"), count("membrane"), count("junction"), count("route")], [8, 2, 3, 18, 0]);
  assert.deepEqual([...new Set(streams.streams.filter((stream) => stream.kind === "junction").map((stream) => stream.name))].sort(), ["junction_0", "junction_10", "junction_4", "junction_6", "junction_7", "junction_8"]);
  assert.equal(readLoop(run, "human").ok, false, "the planarian's loop is no other species' run");
});

test("a recorded subset or a loop block that contradicts itself, or that the page could not lay out, is refused with what and where", () => {
  const cellSet = (view) => view.sets.find((item) => item.id === "cell");
  for (const [label, change, message] of [
    ["every", (view) => (view.recording.subset.every = 0), /its view's recording subset does not give the fields it keeps, the elements it keeps and its cadence/],
    ["stray", (view) => (view.recording.subset.fields = view.recording.subset.fields.filter((field) => field !== "junction_gate")), /its view gives records of junction_gate, which its recording subset does not keep/],
    ["cells", (view) => {
      view.recording.subset.elements = { cell: ["cell_3"] };
      cellSet(view).recorded = [3];
    }, /its view records only some entities of cell \(recording\.subset\.elements\), which the adapter does not lay out yet/],
    ["recorded-alone", (view) => (cellSet(view).recorded = [3]), /its view's set cell and its recording subset disagree on whether only some of its entities were recorded/],
    ["recorded-other", (view) => {
      view.recording.subset.elements = { species: ["K"] };
      view.sets.find((item) => item.id === "species").recorded = [0];
    }, /its view's set species records entities \(recorded\) that are not the ones its recording subset names/],
    ["not-measured", (view) => (view.loop.not_measured[0].records.push("observed_no_such_record")), /its view's loop does not give, for each group of records its closure leaves out, the records by the view's ids and the reason/],
    ["zero", (view) => (view.loop.closes.zero = ["observed_no_such_record"]), /its view's loop names, as records identically zero over the loop, what are not records of the view/],
    ["above", (view) => (view.loop.closes.within = 2e-4), /its view's loop says its last record meets its first within 0\.0002, above its own tolerance of 0\.0001/],
    ["no-source", (view) => {
      delete view.run.source;
      view.unstated.push({ id: "source", what: "engine source", why: "planted by this test" });
    }, /its view gives a loop for a run that names no engine source \(run\.source\)/],
  ]) {
    const [result, target] = changedLoop(label, change);
    assert.notEqual(result.status, 0, label);
    assert.match(result.stderr, message, label);
    assert.ok(!existsSync(path.join(target, "index.json")), `${label}: nothing is catalogued`);
  }
});

// ---------------------------------------------------------------- the writer that reads the engine's own declarations
//
// tests/engine-views/run-view-050aa741: five small worlds main's run-view writer wrote at 050aa741
// (tools/make_engine_view_fixture.sh), byte for byte what the development branch's b08af640 wrote but for the label the
// script plants (the two writers are the same file). From b08af640 the writer takes @3's own
// view declarations and record roles: a voltage's difference is confirmed, each increment names its fixed reference
// (amount_reference becomes a named constant), the engine's check residuals are marked diagnostics, and a kind's set
// (the passive routes) carries a list of species for each route. tests/engine-views/loop-b08af640: the looping run
// again, written by that writer from an execution snapshot (copied from the engine's lead's folder; not published).

const WRITER_B = path.join(ROOT, "tests", "engine-views", "run-view-050aa741");
const B_WORLDS = ["secretion", "subset", "increments", "kinds", "division"];
const bOut = path.join(scratch, "views-050aa741-out");
const bDone = tool("--experiment", VIEWS, "--root", WRITER_B, ...B_WORLDS.flatMap((world) => ["--run", world]), ...VIEW_ARGS, "--out", bOut);
assert.equal(bDone.status, 0, `the adapter failed on the views written at 050aa741:\n${bDone.stderr}`);
const writtenB = (world) => readJson(path.join(WRITER_B, world, "view.json"));

/** A world of 050aa741 with its view changed in a copy, adapted; [result, output folder, run id]. */
function changedB(label, change, world = "secretion") {
  const copy = path.join(scratch, `main-${label}`);
  cpSync(WRITER_B, copy, { recursive: true });
  const file = path.join(copy, world, "view.json");
  const view = readJson(file);
  change(view);
  writeFileSync(file, JSON.stringify(view));
  const target = path.join(scratch, `main-${label}-out`);
  return [tool("--experiment", VIEWS, "--root", copy, "--run", world, ...VIEW_ARGS, "--out", target), target, `${VIEWS}--${world}`];
}

test("the views written by main's writer at 050aa741 are its own, of the revision their note names, each well under 1 MB", () => {
  const note = readFileSync(path.join(WRITER_B, "README.md"), "utf8");
  assert.match(note, /^# Runs written by the engine's run-view writer \(050aa741\)/);
  assert.match(note, /050aa741ddff540971169225d7ccd275c2e89462/);
  assert.match(note, /that is main at `050aa741`: the writer is on main since 050aa741 \(16 November 2026\)/);
  assert.equal(writtenB("secretion").run.revision, "050aa741", "the caller's label the script plants, and no more");
  const size = (folder) => readdirSync(folder, { withFileTypes: true }).reduce((total, item) => total + (item.isDirectory() ? size(path.join(folder, item.name)) : statSync(path.join(folder, item.name)).size), 0);
  for (const world of B_WORLDS) {
    const view = writtenB(world);
    assert.equal(view.format, "cells.run_view@1");
    assert.equal(view.run.source, undefined, `${world}: run from an export, no engine source`);
    assert.ok(size(path.join(WRITER_B, world)) < 300_000, `${world} is ${size(path.join(WRITER_B, world))} bytes`);
  }
  assert.ok(!PATHS.test(readdirSync(WRITER_B, { recursive: true }).filter((name) => /\.(json|jsonl|md)$/.test(name)).map((name) => readFileSync(path.join(WRITER_B, name), "utf8")).join("\n")));
});

test("main's writer (from b08af640): a voltage's difference is confirmed, the check residuals are diagnostics, and the increments name their references", () => {
  const { view, file, record, run } = openWhole(bOut, `${VIEWS}--secretion`);
  assert.deepEqual(validateReplay(file), []);
  const written = writtenB("secretion");
  const stated = written.records.find((item) => item.id === "observed_membrane_voltage_V").difference;
  assert.equal(stated.source, undefined);
  assert.deepEqual(record("membrane_voltage_V").sign, { says: stated.says, high: "inside", confirmed: stated.confirmed });
  assert.match(stated.confirmed, /^the core's owner, from the code/);
  // The diagnostics are read past and counted, in the view's words; none is shown.
  const diagnostics = written.records.filter((item) => "diagnostic" in item).map((item) => item.field);
  assert.deepEqual([...new Set(diagnostics)].sort(), ["charge_residual_C", "component_current_residual_A", "energy_balance_pJ_s"]);
  assert.ok(view.derivation.some((line) => line.startsWith("The view marks 3 field(s) as diagnostics, in its words 'a diagnostic: the residual of the engine's own check") && line.endsWith(": charge_residual_C, component_current_residual_A, energy_balance_pJ_s. The page shows none of them.")));
  // The references: each increment names its fixed reference, a named constant of the view; amount_reference is new.
  assert.deepEqual(written.records.find((item) => item.id === "observed_amount_increment").reference, { constant: "amount_reference" });
  const reference = view.constants.find((item) => item.id === "amount_reference");
  assert.deepEqual([reference.unit, reference.axes], ["fmol", ["species", "cell"]]);
  assert.ok(view.derivation.includes("The view stores 2 field(s) as an increment over a fixed reference (its reference): amount_increment over amount_reference, extracellular_amount_increment over extracellular_amount_reference."));
  // The amounts themselves were saved: they are read as saved, and nothing is worked out.
  assert.equal(record("amount.S").note, undefined);
  assert.ok(Object.fromEntries(layersFor(run, LAYERS, MARKS).map((offer) => [offer.layer.id, offer.ok]))["ion-push-pull"]);
});

test("main's writer (from b08af640): a level saved only as an increment is the named reference plus the increment, worked out and said", () => {
  const sums = open(bOut, `${VIEWS}--increments`);
  const saved = open(bOut, `${VIEWS}--secretion`);
  assert.deepEqual(validateReplay(sums.file), []);
  assert.deepEqual(writtenB("increments").recording.subset.fields, ["membrane_voltage_V", "cell_potential_V", "amount_increment", "extracellular_amount_increment"]);
  for (const [level, reference] of [["amount.S", "amount_reference"], ["extracellular_amount.S", "extracellular_amount_reference"]]) {
    const item = sums.record(level);
    assert.match(item.note, new RegExp(`^Worked out by the viewer: the run's fixed reference ${reference} \\(a named constant of the view\\) plus its record observed_`));
    assert.deepEqual(item.reference, { constant: reference });
    // The same world, whose run saved the level itself: the sum gives the engine's own readout.
    const part = (opened, id) => {
      const entry = opened.record(id);
      const held = readJson(path.join(bOut, path.basename(opened.view.parts.find((item) => item.id === entry.part).file)));
      const bytes = Buffer.from(held.payload.data, "base64");
      return Array.from(new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), entry.offset, entry.shape[0] * entry.shape[1]));
    };
    assert.deepEqual(part(sums, level), part(saved, level), `${level}: reference plus increment is the level the engine saved`);
  }
  assert.ok(sums.view.derivation.includes("Saved only as an increment over a fixed reference (the view's reference), and so worked out by the viewer as the reference plus the increment, row by row: amount is amount_reference plus amount_increment; extracellular_amount is extracellular_amount_reference plus extracellular_amount_increment. Each such record says so in its note."));
  // Not said to be unrecorded: the run kept it, as an increment.
  assert.equal(sums.run.unstated.has("amount"), false);
  // A reference the run did not save (a field only) cannot be added: the level is not packaged, and that is said with the
  // view's reason. Such a reference stands only with the field's entry under unstated (the format items of d64fb664; no
  // saved view before them has one): without the entry it is refused.
  const why = "planted by this test: the run did not save it";
  const [unsaved, unsavedOut, id] = changedB("unsaved-reference", (view) => {
    for (const item of view.records) if (item.field === "amount_increment") item.reference = { field: "amount_reference" };
    view.unstated.push({ id: "amount_reference", what: "view field", why });
    view.constants = view.constants.filter((item) => item.id !== "amount_reference");
  }, "increments");
  assert.equal(unsaved.status, 0, unsaved.stderr);
  const left = open(unsavedOut, id);
  assert.equal(left.view.records.some((item) => item.id === "amount.S"), false);
  assert.ok(left.view.derivation.includes(`Not packaged: amount (its increment amount_increment is stored over the field amount_reference, which the run did not save (${why}), so the adapter cannot add it).`));
  const [bare, bareOut] = changedB("unsaved-reference-bare", (view) => {
    for (const item of view.records) if (item.field === "amount_increment") item.reference = { field: "amount_reference" };
  }, "increments");
  assert.notEqual(bare.status, 0);
  assert.match(bare.stderr, /its view's record (observed_)?amount_increment is stored over the field amount_reference \(its reference\), which the run did not save, and its view gives no entry for amount_reference under unstated saying why/);
  assert.ok(!existsSync(path.join(bareOut, "index.json")));
});

test("main's writer (from b08af640): a kind's set carries a list of species for each entity, read as written, and is no operator's for the secreted species", () => {
  const { view, file } = open(bOut, `${VIEWS}--kinds`);
  assert.deepEqual(validateReplay(file), []);
  const routes = view.sets.find((item) => item.id === "passive_route");
  assert.deepEqual(writtenB("kinds").sets.find((item) => item.id === "passive_route").carries, [["H"]]);
  assert.deepEqual([routes.species, routes.kinds, routes.at, routes.owner], [[["H"]], ["proton_constant_field_leak@1"], [{ membrane: "bounding_0" }], "resolved_pump_tissue@3"]);
  assert.ok(view.derivation.includes("What the run's operators state of each of their entities is carried as the view gives it (passive_route: proton_leak_0 (proton_constant_field_leak@1) carries H at bounding_0); a route's species is the one the view says it carries."));
  assert.equal(view.sets.find((item) => item.id === "species").secreted, undefined, "a leak of the inner model's is no operator's secretion");
  // A list that names a species the run does not have, or names none, is refused.
  for (const [label, carries] of [["carries-foreign", [["H", "Xe"]]], ["carries-empty", [[]]]]) {
    const [result, target] = changedB(label, (view) => (view.sets.find((item) => item.id === "passive_route").carries = carries), "kinds");
    assert.notEqual(result.status, 0, label);
    assert.match(result.stderr, /its view says an entity of passive_route carries a species that is not among the run's species/, label);
    assert.ok(!existsSync(path.join(target, "index.json")));
  }
});

test("main's writer (from 050aa741): a pH condition's own set and a kind's records are read past, never refused", () => {
  // Main's kinds at 050aa741 (patch damage, the pH condition, the transporter) bring sets and records of their own. No kept
  // world uses them, so a changed copy of the kind world gives the pH condition's set as its view_sets declares it:
  // roles, the law under kinds (the queued mismatch), the node it reads at, and two facts of its own (ph50, slope).
  const condition = { id: "ph_condition", ids: ["acid_0"], scale: "cell", owner: "resolved_pump_tissue@3", roles: { node: "the node whose free proton read sets the condition's pH" }, kinds: ["ph_conditioned_factor@1"], at: [{ node: "lumen_0" }], ph50: [5.5], slope: [1.0] };
  const [result, target, id] = changedB("ph-condition", (view) => view.sets.push(condition), "kinds");
  assert.equal(result.status, 0, result.stderr);
  const { view, file } = open(target, id);
  assert.deepEqual(validateReplay(file), []);
  const carried = view.sets.find((item) => item.id === "ph_condition");
  assert.deepEqual([carried.kinds, carried.at, carried.roles, carried.owner], [condition.kinds, condition.at, condition.roles, condition.owner]);
  assert.ok(view.derivation.some((line) => line.includes("ph_condition: acid_0 (ph_conditioned_factor@1) at lumen_0")));
});

test("main's writer (from b08af640): a malformed role is refused with what and where", () => {
  for (const [label, change, message] of [
    ["diagnostic", (view) => (view.records.find((item) => item.id === "observed_charge_residual_C").diagnostic = ""), /its view's record observed_charge_residual_C is marked a diagnostic with no words for what it is/],
    ["reference", (view) => (view.records.find((item) => item.id === "observed_amount_increment").reference = { constant: "no_such_constant" }), /its view's record observed_amount_increment names a reference that is not one constant, record or field of the view/],
  ]) {
    const [result, target] = changedB(label, change);
    assert.notEqual(result.status, 0, label);
    assert.match(result.stderr, message, label);
    assert.ok(!existsSync(path.join(target, "index.json")), `${label}: nothing is catalogued`);
  }
});

test("the looping run written at b08af640: read as before, its source the new revision, and a loop's cell type and diagnostics carried", () => {
  const LOOPS_B = path.join(ROOT, "tests", "engine-views", "loop-b08af640");
  const note = readFileSync(path.join(LOOPS_B, "README.md"), "utf8");
  assert.match(note, /a development run with no verdict/);
  assert.match(note, /its writer is on main since 050aa741/);
  const written = readJson(path.join(LOOPS_B, "planarian-b08af640", "view.json"));
  assert.deepEqual(written.run.source, { dirty: false, from: "the execution snapshot's record (SNAPSHOT.json)", revision: "b08af640c3db83e891e29ade36c300d6f8e5a553" });
  assert.deepEqual(written.loop, loopView().loop, "the same loop block as the run written at d7a11d5b");
  const adapt = (label, change) => {
    const copy = path.join(scratch, `loop-b-${label}`);
    cpSync(LOOPS_B, copy, { recursive: true });
    const file = path.join(copy, "planarian-b08af640", "view.json");
    const view = readJson(file);
    change(view);
    writeFileSync(file, JSON.stringify(view));
    const target = path.join(scratch, `loop-b-${label}-out`);
    return [tool("--experiment", VIEWS, "--root", copy, "--run", "planarian-b08af640", ...VIEW_ARGS, "--out", target), target];
  };
  const [result, target] = adapt("as-written", () => {});
  assert.equal(result.status, 0, result.stderr);
  const { view, run, record } = openWhole(target, `${VIEWS}--planarian-b08af640`);
  assert.deepEqual(view.loop, { species: "planarian", cell: "cell_3", period: 2, closes: written.loop.closes, not_measured: written.loop.not_measured });
  const read = readLoop(run, "planarian");
  assert.equal(read.ok, true, read.why);
  assert.equal(engineWords(read.loop), "Made by the engine at revision b08af640c3db83e891e29ade36c300d6f8e5a553, from a clean tree");
  assert.match(record("junction_voltage_V").sign.confirmed, /^the core's owner, from the code/);
  // A loop of one of the species' cell types names it (from 0fac9d56): carried as written; a cell type with no word is refused.
  const [typed, typedOut] = adapt("cell-type", (view) => (view.loop.cell_type = "neoblast"));
  assert.equal(typed.status, 0, typed.stderr);
  assert.equal(open(typedOut, `${VIEWS}--planarian-b08af640`).view.loop.cell_type, "neoblast");
  const [blank] = adapt("cell-type-blank", (view) => (view.loop.cell_type = ""));
  assert.notEqual(blank.status, 0);
  assert.match(blank.stderr, /its view's loop names its cell type with no word/);
  // Where the closure leaves out diagnostics as well as running totals, each group is said with the run's reason.
  const diagnostics = { why: "diagnostics: residuals of the engine's own checks, held to their own absolute tolerances", records: ["observed_membrane_voltage_V"] };
  const [grouped, groupedOut] = adapt("diagnostics", (view) => view.loop.not_measured.unshift(diagnostics));
  assert.equal(grouped.status, 0, grouped.stderr);
  const both = readLoop(openWhole(groupedOut, `${VIEWS}--planarian-b08af640`).run, "planarian");
  assert.equal(closesWords(both.loop), `Its last record meets its first within 2.8e-5 (tolerance 1.0e-4), in the records it measures; of its records, 1 is not measured (${diagnostics.why}); 7 are not measured (${written.loop.not_measured[0].why})`);
});

test("the planarian's loop for the page: its catalogue entry's words, and a package the page's checks and loop reader take", () => {
  // The run is the kept fixture loop-b08af640 (the lead's folder replay-20261116/planarian-b08af640, copied unchanged),
  // packaged with the catalogue's own entry and selection as `npm run adapt:runs` packages it.
  const LOOPS_B = path.join(ROOT, "tests", "engine-views", "loop-b08af640");
  const overlay = path.join(ROOT, "data", "replays", "overlay.json"), selection = path.join(ROOT, "data", "replays", "selection.json");
  const entry = readJson(overlay).experiments["planarian-loop"];
  assert.deepEqual(readJson(selection)["planarian-loop"].runs, ["planarian-b08af640"]);
  assert.equal(readJson(selection)["planarian-loop"].evidence_folder, "replay-20261116");
  // The words the page carries for it: a development run of the engine, not judged; what it is and what it may not claim.
  assert.deepEqual([entry.development, entry.outcome.judged, entry.outcome.answer, entry.label], [true, false, null, "Planarian loop (development run)"]);
  assert.match(entry.plain, /^A development run of the engine, not judged: FR-11's interim planarian loop\./);
  assert.match(entry.plain, /It is not a measurement of a planarian, and it shows no result\.$/);
  assert.equal(entry.outcome.text, "FR-11's first looping run: a planarian development run (not judged) that closes within 2.76e-5 against a tolerance of 1e-4, bitwise the same before and after the adoption.");
  const out = path.join(scratch, "planarian-loop-out");
  const done = tool("--experiment", "planarian-loop", "--root", LOOPS_B, "--run", "planarian-b08af640", "--overlay", overlay, "--selection", selection, "--out", out);
  assert.equal(done.status, 0, done.stderr);
  const { view, file, run } = openWhole(out, "planarian-loop--planarian-b08af640");
  assert.deepEqual(validateReplay(file), []);
  // The model and the revision, from the run's own record of its source.
  assert.deepEqual([view.run.engine_models, view.run.revision, view.run.source.dirty], [["resolved_pump_composite@1", "resolved_pump_tissue@3", "electrode_current_injection@1"], "b08af640c3db83e891e29ade36c300d6f8e5a553", false]);
  // How it closes, in the run's own sentence and numbers, and what the closure leaves out.
  const read = readLoop(run, "planarian");
  assert.equal(read.ok, true, read.why);
  assert.equal(read.loop.closes.says, "the last observed row meets the first within 2.8e-05 relative (largest in observed_membrane_flux_fmol_s)");
  assert.deepEqual([read.loop.closes.within, read.loop.closes.tolerance], [2.7606981408476794e-05, 0.0001]);
  assert.equal(closesWords(read.loop), "Its last record meets its first within 2.8e-5 (tolerance 1.0e-4), in the records it measures; of its records, 7 are not measured (cumulative totals: they grow by design, so the reader differences them inside the loop)");
  assert.equal(engineWords(read.loop), "Made by the engine at revision b08af640c3db83e891e29ade36c300d6f8e5a553, from a clean tree");
  // What the catalogue names for it, as the real-output check asks: every event kind, the stop, the parameters and readouts.
  const listed = readJson(path.join(out, "index.json")).experiments.find((item) => item.id === "planarian-loop");
  for (const event of view.events) {
    assert.ok(listed.events?.[event.kind], `the catalogue labels the event kind ${event.kind}`);
    assert.ok(event.time >= run.start && event.time <= run.end, "an event lies within the records");
  }
  assert.ok(listed.stops?.[view.run.stop]);
  for (const [kind, id] of [...view.run.parameters.map((item) => ["parameters", item.id]), ...view.run.readouts.map((item) => ["readouts", item.id])]) assert.ok(listed[kind]?.[id]?.label, id);
  const size = ["planarian-loop--planarian-b08af640.json", ...(view.parts || []).map((part) => path.basename(part.file))].reduce((total, name) => total + statSync(path.join(out, name)).size, 0);
  assert.ok(size < 200_000, `the package is ${size} bytes`);
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
      assert.ok(run.records.size > before, `${row.id}: the part ${part.id} gave no record`);
    }
    // With every part in, no record is left waiting for a file.
    assert.equal(run.pending.size, 0, `${row.id}: a record names a part the run does not list`);
  }
  for (const id of experiments.keys()) assert.ok(real.runs.some((row) => row.experiment === id), `${id} has no runs`);
  console.log(`  ${real.runs.length} runs of ${experiments.size} experiments, ${(total / 1e6).toFixed(1)} MB in all`);
});
