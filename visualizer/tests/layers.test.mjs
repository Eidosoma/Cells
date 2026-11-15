// Quantity layers, checked without a browser (schema/QUANTITY_LAYERS.md): the four declared
// derivations, the declarations in data, which layers a run can feed and why not, the rule
// of one layer per channel, what the legend says of a layer, records in files of their own,
// and the marks' arithmetic. The colouring and the heights are held to the formula the
// replay used before layers, so that layer zero changes nothing.
//
//   node --test tests/layers.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { syntheticRun } from "./helpers/synthetic_replay.mjs";
import { openReplay, loadPart } from "../src/replay/source.js";
import { validateReplay } from "../src/replay/run.js";
import { Ramp } from "../src/replay/ramp.js";
import { display } from "../src/replay/format.js";
import { difference, rate, charge, potentialTerms, DERIVATIONS, FARADAY, GAS } from "../src/layers/derive.js";
import { declared, declaredOn, behind, LIVES_ON, KINDS } from "../src/layers/records.js";
import { layersFor, feeds, readDeclarations, validateLayer, account, Switch, CHANNELS, LAYERS_FORMAT, NOT_SAVED } from "../src/layers/layers.js";
import { shareOf, roundUp } from "../src/layers/scale.js";
import { MARKS } from "../src/layers/marks/index.js";
import { heightOf, barStretch, riseOf, crossings, BOLD_RISE } from "../src/layers/marks/relief.js";
import { dropAt, fullDrop, FLOOR } from "../src/layers/marks/wedge.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const declarations = JSON.parse(await readFile(path.join(ROOT, "data", "layers", "layers.json"), "utf8"));
const contract = await readFile(path.join(ROOT, "schema", "QUANTITY_LAYERS.md"), "utf8");
const { layers: LAYERS, problems: PROBLEMS } = readDeclarations(declarations, MARKS);
const layer = (id) => LAYERS.find((item) => item.id === id);
const offer = (run, id) => layersFor(run, LAYERS, MARKS).find((item) => item.layer.id === id);

const made = (options) => {
  const { file, entry, parts } = syntheticRun(options);
  return { file, entry, parts, run: openReplay(file, entry) };
};
/** A fetcher that gives back a run's part files, as the page's does. */
const fetcherOf = (parts, files = {}) => async (url) => {
  const part = Object.values(parts).find((item) => url.endsWith(`.${item.part}.json`));
  const body = files[url] ?? part;
  return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body };
};

// ------------------------------------------------------------ the four declared rules

test("the four declared rules are the contract's, and each says it was worked out by the viewer", () => {
  assert.deepEqual(Object.keys(DERIVATIONS), ["difference", "rate", "charge", "potential terms"]);
  for (const name of Object.keys(DERIVATIONS)) {
    assert.ok(contract.includes(`\`${name}\``), `the contract does not name ${name}`);
    assert.match(DERIVATIONS[name].says("the saved membrane voltage"), /^Worked out by the viewer from the saved membrane voltage/);
  }
});

test("a difference, a mean rate and a charge are plain arithmetic on saved numbers", () => {
  assert.equal(difference(-0.02, -0.08), -0.02 - -0.08);
  assert.equal(rate(12, 9, 1.5), 2);
  assert.equal(rate(12, 9, 0), null, "no time between two records gives no rate");
  assert.equal(rate(NaN, 9, 1), null);
  assert.equal(charge(1.6e-11, -0.07), 1.6e-11 * -0.07);
});

test("the potential terms are the two terms of the engine's own law, each divided by z F", () => {
  // The engine: R T (ln ci - ln co) + z F V (src/cells/processes/electrochemistry.py), with its constants.
  assert.equal(FARADAY, 6.02214076e23 * 1.602176634e-19);
  assert.equal(GAS, 6.02214076e23 * 1.380649e-23);
  const potassium = potentialTerms({ inside: 140, outside: 5, voltage: -0.07, valence: 1, temperature: 310 });
  const engine = GAS * 310 * (Math.log(140) - Math.log(5)) + 1 * FARADAY * -0.07;
  assert.equal(potassium.sum, engine);
  assert.equal(potassium.concentration + potassium.electrical, potassium.sum);
  assert.ok(Math.abs(potassium.volts.concentration - 0.08901) < 1e-4, `the push of concentration on potassium is ${potassium.volts.concentration} V`);
  assert.equal(potassium.volts.electrical, -0.07);
  assert.ok(potassium.volts.sum > 0, "what is left drives potassium outward");
  // A negative ion: the same terms with its valence.
  const chloride = potentialTerms({ inside: 10, outside: 120, voltage: -0.07, valence: -1, temperature: 310 });
  assert.equal(chloride.sum, GAS * 310 * (Math.log(10) - Math.log(120)) + -1 * FARADAY * -0.07);
  // What the engine refuses, the viewer does not work out.
  for (const bad of [{ inside: 0 }, { outside: -1 }, { valence: 0 }, { temperature: 0 }, { voltage: NaN }]) {
    assert.equal(potentialTerms({ inside: 140, outside: 5, voltage: -0.07, valence: 1, temperature: 310, ...bad }), null);
  }
});

// ------------------------------------------------------------ the declarations

test("the declared layers follow the contract, and each names a mark the viewer has", () => {
  assert.equal(declarations.format, LAYERS_FORMAT);
  assert.deepEqual(PROBLEMS, []);
  assert.deepEqual(LAYERS.map((item) => item.id), ["voltage-tint", "voltage-relief", "junction-drops"]);
  for (const item of LAYERS) {
    assert.ok(contract.includes(`\`${item.id}\``), `the contract's table does not list ${item.id}`);
    assert.ok(MARKS[item.mark], `${item.id}: no mark ${item.mark}`);
    for (const channel of item.channels) assert.ok(CHANNELS.includes(channel) && MARKS[item.mark].channels.includes(channel));
  }
  // The contract's own words for the channels and for what a record lives on are the ones used.
  for (const channel of CHANNELS) assert.ok(contract.includes(`\`${channel}\``), `the contract does not name the channel ${channel}`);
  for (const where of LIVES_ON) assert.ok(contract.includes(`\`${where}\``), `the contract does not name ${where}`);
  for (const kind of KINDS) assert.ok(contract.includes(`\`${kind}\``), `the contract does not name the kind ${kind}`);
});

test("a layer's declaration that breaks the contract is refused with the reason", () => {
  const good = layer("junction-drops");
  const cases = [
    [(bad) => (bad.id = "Voltage Drops"), /its id/],
    [(bad) => (bad.mark = "sparkle"), /is not one the viewer has/],
    [(bad) => (bad.channels = ["smell"]), /channels/],
    [(bad) => (bad.channels = ["colour"]), /does not draw on a channel/],
    [(bad) => (bad.quantity = { derivation: "flux", of: "vm" }), /not one of the declared rules/],
    [(bad) => (bad.quantity = { derivation: "difference" }), /names the record/],
    [(bad) => (bad.quantity = { derivation: "difference", of: "vm", where: "a full moon" }), /not a condition/],
    [(bad) => (bad.quantity = {}), /neither a record nor a rule/],
    [(bad) => delete bad.says, /does not say what it shows/],
    [(bad) => (bad.also = [{ record: "junction_gate" }]), /optional record/],
  ];
  for (const [damage, expected] of cases) {
    const bad = JSON.parse(JSON.stringify(good));
    damage(bad);
    const problems = validateLayer(bad, MARKS);
    assert.ok(problems.some((problem) => expected.test(problem)), `expected ${expected}, got ${JSON.stringify(problems)}`);
  }
  const twice = readDeclarations({ format: LAYERS_FORMAT, layers: [good, good] }, MARKS);
  assert.equal(twice.layers.length, 1);
  assert.match(twice.problems.join(" "), /used twice/);
});

// ------------------------------------------------------------ a run's records as declared

test("a record is read as the run's view declares it, and what the view leaves out is said", () => {
  const { run } = made();
  const vm = declared(run, "vm");
  assert.deepEqual({ lives_on: vm.lives_on, unit: vm.unit, kind: vm.kind, representation: vm.representation, loaded: vm.loaded }, { lives_on: "cell", unit: "V", kind: "level", representation: "simulated", loaded: true });
  assert.match(vm.owner, /synthetic/);
  // A voltage is signed, and this run does not say which way is positive: that is said, not guessed.
  assert.deepEqual(vm.lacks, ["sign"]);
  assert.match(behind(vm), /^Saved by the run; computed by .*simulated\.$/);
  const gate = declared(run, "junction_gate");
  assert.deepEqual({ lives_on: gate.lives_on, part: gate.part, loaded: gate.loaded, quantised: gate.quantised }, { lives_on: "junction", part: "junction-gate", loaded: false, quantised: true });
  assert.equal(declared(run, "no_such_record"), null);
  assert.deepEqual(declaredOn(run, "cell").map((record) => record.id), ["vm", "generation"]);
  assert.equal(declared(run, "t").lives_on, "world");
  // A view that states neither owner nor representation: both are said to be missing.
  const bare = made();
  for (const record of bare.file.view.records) delete record.owner;
  for (const item of bare.file.view.layers) item.representation = null;
  const plain = declared(openReplay(bare.file, bare.entry), "vm");
  assert.deepEqual(plain.lacks, ["sign", "owner", "representation"]);
  assert.match(behind(plain), /do not say which model or law computed it\. Nor do they say how that part of the engine is represented\./);
  assert.match(behind({ owner: "a_model@1", representation: null }), /^Saved by the run; computed by a_model@1\. Its files do not say how that part of the engine is represented\.$/);
  assert.match(behind({ owner: "a_model@1", representation: "modelled", sign: { says: "the first cell is at the higher potential" } }), /modelled in aggregate\. Positive means: the first cell is at the higher potential\.$/);
});

test("a sign the run does not declare itself says where it comes from, and a record with no sign has no direction", () => {
  const by = "the engine's own convention for this family of models, confirmed by the owner of its core on 15 November 2026 and not yet declared in the run's view";
  const signed = made();
  const abundance = signed.file.view.records.find((record) => record.id === "junction_abundance");
  signed.file.view.records.push({ ...abundance, id: "junction_transferred", label: "Amount moved through the junction", unit: "fmol", kind: "cumulative", sign: { says: "a positive amount has left the sender for the receiver", from: "first", to: "second", by } });
  assert.deepEqual(validateReplay(signed.file), []);
  const record = declared(openReplay(signed.file, signed.entry), "junction_transferred");
  assert.equal(record.kind, "cumulative");
  assert.equal(record.sign.by, by);
  assert.match(behind(record), /Positive means: a positive amount has left the sender for the receiver\. That is the engine's own convention for this family of models, confirmed by the owner of its core on 15 November 2026 and not yet declared in the run's view\.$/);
  // A sign that the run itself declares says only what positive means.
  assert.match(behind({ owner: "a_law@1", representation: "simulated", sign: { says: "inside above outside" } }), /Positive means: inside above outside\.$/);
  // A malformed sign is refused.
  signed.file.view.records.at(-1).sign = { says: "x", by: 3 };
  assert.match(validateReplay(signed.file).join(" "), /a sign says in words what positive means/);
  signed.file.view.records.at(-1).sign = { says: "x", high: "third" };
  assert.match(validateReplay(signed.file).join(" "), /a sign says in words what positive means/);
});

// ------------------------------------------------------------ what a run can feed

test("a run is offered the layers it can feed: the declared ones, and a colouring and a relief of every other record over its cells", () => {
  const { run } = made();
  const offers = layersFor(run, LAYERS, MARKS);
  assert.deepEqual(offers.map((item) => [item.layer.id, item.ok]), [["voltage-tint", true], ["voltage-relief", true], ["junction-drops", true], ["generation-tint", true], ["generation-relief", true]]);
  assert.equal(offer(run, "voltage-tint").source.id, "vm");
  assert.equal(offer(run, "generation-relief").layer.plain, true);
  // The drops: this run kept neither the junctions' own voltage nor each cell's potential, so
  // the third way is taken, and its gate must be fetched from a file of its own first.
  const drops = offer(run, "junction-drops");
  assert.deepEqual(drops.quantity, { derivation: "difference", of: ["vm", "membrane_voltage_V"], across: "junction", where: "shared surroundings" });
  assert.deepEqual(drops.parts, ["junction-gate"]);
  assert.deepEqual(drops.extras.map((extra) => [extra.role, extra.record]), [["gate", "junction_gate"], ["formed", "junction_abundance"]]);
  assert.deepEqual(drops.lacking, []);
});

test("the difference of two membrane voltages is offered only where the run says its cells' surroundings share one potential", () => {
  const { run } = made({ surroundings: false });
  const drops = offer(run, "junction-drops");
  assert.equal(drops.ok, false);
  assert.match(drops.why, /did not save each junction's voltage.*surroundings share one potential/);
  // The colouring and the relief need no such condition.
  assert.equal(offer(run, "voltage-relief").ok, true);
});

test("where a run kept the engine's own readout, the layer reads it and derives nothing", () => {
  // The junctions' own voltage, with its sign declared: read as it is.
  const own = made({ surroundings: false });
  const abundance = own.file.view.records.find((record) => record.id === "junction_abundance");
  own.file.view.records.push({ ...abundance, id: "junction_voltage_V", label: "Junction voltage", unit: "V", sign: { says: "the first cell of the junction is at the higher potential", high: "first" } });
  assert.deepEqual(validateReplay(own.file), []);
  const first = offer(openReplay(own.file, own.entry), "junction-drops");
  assert.equal(first.ok, true);
  assert.deepEqual(first.quantity, { record: ["junction_voltage_V", "junction_voltage"], signed: true });
  assert.equal(first.source.lives_on, "junction");
  // Saved, but with no word on which way is positive: it gives no direction, so the next way is tried.
  delete own.file.view.records.at(-1).sign;
  const unsigned = offer(openReplay(own.file, own.entry), "junction-drops");
  assert.equal(unsigned.ok, false, "with no other way and no stated surroundings, the run cannot feed the layer");
  // Each cell's own potential: its difference is the junction's voltage whatever the surroundings.
  const cells = made({ surroundings: false });
  const vm = cells.file.view.records.find((record) => record.id === "vm");
  cells.file.view.records.push({ ...vm, id: "cell_potential_V", label: "Cell potential" });
  const second = offer(openReplay(cells.file, cells.entry), "junction-drops");
  assert.equal(second.ok, true);
  assert.deepEqual(second.quantity, { derivation: "difference", of: ["cell_potential_V", "cell_potential"], across: "junction" });
});

test("what a run did not save is said: a layer it cannot feed, and what a layer cannot show without an optional record", () => {
  const { run } = made({ gate: false });
  const drops = offer(run, "junction-drops");
  assert.equal(drops.ok, true);
  assert.deepEqual(drops.parts, []);
  assert.deepEqual(drops.lacking.map((item) => item.record), ["junction_gate"]);
  assert.match(drops.lacking[0].says, /did not save each junction's gate, so every wedge is drawn solid/);
  // A layer whose record the run lacks altogether.
  const fog = { id: "signal-fog", label: "Signal", quantity: { record: "signal_amount" }, mark: "tint", channels: ["colour"], says: "A secreted species." };
  assert.deepEqual(validateLayer(fog, MARKS), []);
  const cannot = feeds(run, fog, MARKS);
  assert.deepEqual([cannot.ok, cannot.why], [false, NOT_SAVED]);
  assert.match(NOT_SAVED, /did not save it/);
  // A layer whose mark is drawn on something else than its record lies on.
  const wrong = feeds(run, { ...fog, quantity: { record: "junction_abundance" } }, MARKS);
  assert.equal(wrong.ok, false);
  assert.match(wrong.why, /drawn on cells, and this record lies on junction/);
  // A run with no junctions between its cells cannot show drops.
  const lone = made();
  lone.file.view.sets = lone.file.view.sets.filter((set) => set.id !== "junction");
  lone.file.view.records = lone.file.view.records.filter((record) => record.set !== "junction");
  delete lone.file.view.parts;
  assert.match(offer(openReplay(lone.file, lone.entry), "junction-drops").why, /no junctions between its cells/);
});

// ------------------------------------------------------------ records in files of their own

test("a record in a file of its own is fetched when its layer is switched on, and then read like any other", async () => {
  const { run, parts, file } = made();
  assert.deepEqual(validateReplay(file), []);
  assert.equal(run.records.has("junction_gate"), false);
  assert.equal(run.pending.has("junction_gate"), true);
  assert.deepEqual(run.recordsOn("junction").map((record) => record.id), ["junction_abundance"]);
  let asked = 0;
  const fetcher = async (url) => {
    asked += 1;
    return fetcherOf(parts)(url);
  };
  await Promise.all([loadPart(run, "junction-gate", { root: null, fetcher }), loadPart(run, "junction-gate", { root: null, fetcher })]);
  assert.equal(asked, 1, "asked for twice at once, it is fetched once");
  assert.equal(run.records.has("junction_gate"), true);
  assert.equal(run.pending.size, 0);
  const gate = run.records.get("junction_gate");
  assert.ok(gate.at(0, 0) > 0 && gate.at(0, 0) <= 1);
  assert.equal(gate.text(0, 0), null, "a record stored in steps is drawn, never printed");
  assert.deepEqual(offer(run, "junction-drops").parts, []);
  await loadPart(run, "junction-gate", { root: null, fetcher });
  assert.equal(asked, 1, "once in, it is not fetched again");
  // A part found in the page is taken from there.
  const inline = made();
  const root = { querySelector: (selector) => (selector.includes(`data-replay-part="${inline.run.id}/junction-gate"`) ? { textContent: JSON.stringify(inline.parts["junction-gate"]) } : null) };
  await loadPart(inline.run, "junction-gate", { root, fetcher: null });
  assert.equal(inline.run.records.has("junction_gate"), true);
});

test("a part that is not the run's, or not the length the run states, is refused", async () => {
  const { run, parts } = made();
  const other = { ...parts["junction-gate"], run: "another-run" };
  await assert.rejects(loadPart(run, "junction-gate", { root: null, fetcher: async () => ({ ok: true, json: async () => other }) }), /of run another-run/);
  const short = JSON.parse(JSON.stringify(parts["junction-gate"]));
  short.payload.data = short.payload.data.slice(0, 40);
  await assert.rejects(loadPart(run, "junction-gate", { root: null, fetcher: async () => ({ ok: true, json: async () => short }) }), /bytes long, not the/);
  await assert.rejects(loadPart(run, "junction-gate", { root: null, fetcher: async () => ({ ok: false, status: 404 }) }), /answered 404/);
  await assert.rejects(loadPart(run, "no-such-part", {}), /has no part/);
  assert.equal(run.records.has("junction_gate"), false, "a refused part leaves the run as it was");
  // The run's file itself: a record in a part the run does not list, or longer than its part.
  const bad = made();
  bad.file.view.records.find((record) => record.id === "junction_gate").part = "elsewhere";
  assert.match(validateReplay(bad.file).join(" "), /its part elsewhere is not one of the run's/);
  const long = made();
  long.file.view.parts[0].byte_length = 8;
  assert.match(validateReplay(long.file).join(" "), /runs past the end of its part junction-gate/);
});

// ------------------------------------------------------------ one layer on each channel

test("switching a layer on takes its channels from the layer that held them; layers on different channels show together", () => {
  const state = new Switch();
  const tint = layer("voltage-tint"), relief = layer("voltage-relief"), drops = layer("junction-drops");
  const other = { id: "generation-tint", channels: ["colour"] }, both = { id: "tint-and-height", channels: ["colour", "height"] };
  assert.deepEqual(state.switchOn(tint), []);
  assert.deepEqual(state.switchOn(relief), []);
  assert.deepEqual(state.switchOn(drops), []);
  assert.deepEqual(state.on, ["voltage-tint", "voltage-relief", "junction-drops"]);
  assert.deepEqual(state.switchOn(other), ["voltage-tint"], "the colour is taken from the layer that held it");
  assert.equal(state.holder("colour"), "generation-tint");
  assert.equal(state.isOn("voltage-tint"), false);
  // A layer on two channels takes both, and a layer that loses one of its channels is off altogether.
  assert.deepEqual(state.switchOn(both).sort(), ["generation-tint", "voltage-relief"]);
  assert.deepEqual(state.switchOn(relief), ["tint-and-height"]);
  assert.equal(state.holder("colour"), null, "it does not go on showing on half of its channels");
  state.switchOff("junction-drops");
  assert.deepEqual(state.on, ["voltage-relief"]);
  state.switchOn(tint);
  state.keep(["voltage-tint"]);
  assert.deepEqual(state.on, ["voltage-tint"], "what the next run cannot feed is dropped");
  assert.equal(state.strength, "quiet");
  assert.equal(state.setStrength("bold"), "bold");
  assert.equal(state.setStrength("loud"), "bold", "a strength the contract does not name changes nothing");
});

// ------------------------------------------------------------ what the legend says

test("the legend says what stands behind a layer, and for a derivation the rule, its inputs and what it rests on", async () => {
  const { run, parts } = made();
  await loadPart(run, "junction-gate", { root: null, fetcher: fetcherOf(parts) });
  const tint = offer(run, "voltage-tint");
  const plain = account(run, tint.layer, tint);
  assert.equal(plain.derived, false);
  assert.equal(plain.channel, "Colour");
  assert.ok(!plain.lines.join(" ").includes("Worked out"), "a saved record is not said to be worked out");
  assert.match(plain.lines.join(" "), /Saved by the run; computed by/);
  const drops = offer(run, "junction-drops");
  const said = account(run, drops.layer, drops).lines.join(" ");
  assert.match(said, /Worked out by the viewer from the saved membrane voltage \(synthetic\): the value at one end of a junction less the value at the other/);
  assert.match(said, /held bath at 0 V.*So the difference is the voltage across the junction itself/);
  assert.match(said, /A hollow wedge: the junction's gate is under half open/);
  assert.match(said, /Two bars/);
  // Without the gate, the legend says what cannot be shown.
  const bare = made({ gate: false });
  const less = offer(bare.run, "junction-drops");
  assert.match(account(bare.run, less.layer, less).lines.join(" "), /did not save each junction's gate, so every wedge is drawn solid/);
});

// ------------------------------------------------------------ the marks' arithmetic

/** A sheet as the lens hands it to the marks, built here from a run's polygons. */
function surfaceOf(run) {
  const { vertices, faces } = run.sets.get("cell").geometry;
  let at = 0;
  const cells = faces.map((face) => {
    const ring = face.map((index) => vertices[index]);
    const centre = [ring.reduce((sum, [x]) => sum + x, 0) / ring.length, ring.reduce((sum, [, y]) => sum + y, 0) / ring.length];
    const cell = { face, inset: ring, centre, radius: 1, height: 0, top: new THREE.Vector3(centre[0], 0, centre[1]), start: at, walls: at + ring.length + 1, shade: ring.map((_, k) => 0.6 + 0.02 * k) };
    at += ring.length * 5 + 1;
    return cell;
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(at * 3), 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(at * 3), 3));
  const links = run.sets.get("junction").geometry.ends.map(([a, b], link) => {
    const shared = cells[a].face.filter((vertex) => cells[b].face.includes(vertex));
    const corner = (cell, vertex) => cell.inset[cell.face.indexOf(vertex)];
    return shared.length === 2 ? { a, b, link, points: [corner(cells[a], shared[0]), corner(cells[a], shared[1]), corner(cells[b], shared[1]), corner(cells[b], shared[0])] } : null;
  }).filter(Boolean);
  const pitch = 11;
  return { cells, geometry, links, pitch, low: 0.2 * pitch, high: 0.78 * pitch, extent: 70, root: new THREE.Group() };
}
const scaleOf = (record) => (record.dtype.startsWith("float") ? { shown: display(record), low: -0.09, high: -0.01, nice: { step: 10 } } : { shown: display(record), low: 0, high: Math.max(1, record.range[1]), steps: Math.max(1, Math.round(record.range[1])) });
const PALETTE = ["#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab"];
const colours = () => ({ ramp: new Ramp(PALETTE), neutral: [0.6, 0.65, 0.7], ink: new THREE.Color("#12283a"), ground: new THREE.Color("#eef2f6") });

test("layer zero: the colouring and the quiet relief write exactly what the replay wrote before layers", () => {
  const { run } = made({ invalidFrom: 2000 });
  for (const id of ["vm", "generation"]) {
    const record = run.records.get(id), domain = scaleOf(record), surface = surfaceOf(run);
    const fed = { source: declared(run, id) };
    const context = { surface, run, fed, scaleOf, shown: display, strength: "quiet", colours: colours() };
    const tint = MARKS.tint.create(context), relief = MARKS.relief.create(context);
    const ramp = new Ramp(PALETTE);
    for (const step of [0, 17, run.count - 1]) {
      const valid = run.isValid(step);
      relief.update(step, valid);
      tint.update(step, valid);
      // The replay's own loop, as it stood before layers (src/lenses/replay.js at 268ed6de).
      const position = new Float32Array(surface.geometry.attributes.position.array.length), colour = new Float32Array(position.length);
      const rgb = [0, 0, 0], linear = new THREE.Color();
      const { low, high, steps } = domain;
      surface.cells.forEach((cell, number_) => {
        let share = (record.at(step, number_) - low) / (high - low);
        if (steps) share = Math.round(share * steps) / steps;
        share = Math.min(1, Math.max(0, share));
        if (valid) ramp.at(share, rgb);
        else rgb.splice(0, 3, 0.6, 0.65, 0.7);
        const height = valid ? surface.low + (surface.high - surface.low) * share : surface.low;
        const n = cell.inset.length;
        linear.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
        for (let k = 0; k <= n; k++) {
          position[(cell.start + k) * 3 + 1] = height;
          colour.set([linear.r, linear.g, linear.b], (cell.start + k) * 3);
        }
        for (let k = 0; k < n; k++) {
          const wall = cell.walls + k * 4, shade = cell.shade[k];
          position[wall * 3 + 1] = height;
          position[(wall + 1) * 3 + 1] = height;
          linear.setRGB(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, THREE.SRGBColorSpace);
          for (let corner = 0; corner < 4; corner++) colour.set([linear.r, linear.g, linear.b], (wall + corner) * 3);
        }
        assert.equal(cell.height, height);
        assert.equal(cell.top.y, height);
      });
      assert.deepEqual(surface.geometry.attributes.color.array, colour, `${id} at record ${step}: the colours differ`);
      assert.deepEqual(surface.geometry.attributes.position.array, position, `${id} at record ${step}: the heights differ`);
    }
    assert.equal(relief.bar, null, "a quiet relief stands no bar beside the sheet");
    assert.equal(relief.ceiling, surface.low + (surface.high - surface.low));
  }
});

test("a bold relief raises the same values higher, and says with a bar how much one stretch of height is", () => {
  const { run } = made();
  const surface = surfaceOf(run);
  const relief = MARKS.relief.create({ surface, run, fed: { source: declared(run, "vm") }, scaleOf, shown: display, strength: "bold", colours: colours() });
  assert.equal(riseOf(surface, "bold"), BOLD_RISE * surface.pitch);
  assert.ok(riseOf(surface, "bold") > 4 * riseOf(surface, "quiet"));
  relief.update(0, true);
  const record = run.records.get("vm"), domain = scaleOf(record);
  surface.cells.forEach((cell, number_) => assert.equal(cell.height, heightOf(shareOf(record.at(0, number_), domain), surface.low, BOLD_RISE * surface.pitch)));
  // Height is linear in the value: equal steps of voltage are equal steps of height.
  assert.ok(Math.abs(heightOf(0.5, 2, 10) - (heightOf(0, 2, 10) + heightOf(1, 2, 10)) / 2) < 1e-12);
  // The bar: a round stretch, about a third of the scale (80 mV here), and as tall as that stretch stands.
  assert.equal(barStretch(80), 20);
  assert.equal(barStretch(60), 20);
  assert.equal(barStretch(9), 2);
  assert.equal(barStretch(0), 0);
  assert.equal(relief.bar.text, "20 mV");
  assert.ok(Math.abs(relief.bar.anchor.y - (surface.low + (20 / 80) * BOLD_RISE * surface.pitch)) < 1e-9);
  // A line at the value the experiment marks on the record (D above it, H below), where the
  // sheet crosses it: the 42 seams between the disc's rim and the cells around it.
  assert.deepEqual(relief.crossed, [42]);
  const keys = relief.keys((value, decimals) => value.toFixed(decimals));
  assert.deepEqual(keys.map((item) => item.key), ["level"]);
  assert.match(keys[0].text, /^A line where the sheet crosses -39\.4 mV: D above, H below/);
  const seams = crossings(surface.links, (number_) => record.at(0, number_), -0.0394);
  assert.equal(seams.length, 42);
  for (const [[ax, ay], [bx, by]] of seams) assert.ok(Math.hypot(bx - ax, by - ay) > 1, "each is the middle line of a seam, as long as the seam");
  assert.deepEqual(crossings(surface.links, () => -0.05, -0.0394), [], "a sheet all on one side of the value is crossed nowhere");
  // A record the run does not count as valid shows no line; quiet, the relief adds nothing to the sheet.
  relief.update(0, false);
  assert.deepEqual(relief.crossed, [0]);
  relief.setStrength("quiet");
  relief.update(0, true);
  assert.equal(relief.bar, null);
  assert.deepEqual(relief.crossed, [0]);
  assert.deepEqual(relief.keys(String), []);
  relief.dispose();
});

test("where a value stands on its scale: held to the ends, and a count in whole steps", () => {
  assert.equal(shareOf(-0.05, { low: -0.09, high: -0.01 }), (-0.05 - -0.09) / (-0.01 - -0.09));
  assert.equal(shareOf(0.2, { low: -0.09, high: -0.01 }), 1);
  assert.equal(shareOf(-0.2, { low: -0.09, high: -0.01 }), 0);
  assert.equal(shareOf(2, { low: 0, high: 5, steps: 5 }), 0.4);
  assert.deepEqual([roundUp(59.2), roundUp(0.9), roundUp(20), roundUp(0), roundUp(0.0131)], [60, 1, 20, 1, 0.015]);
});

test("a wedge is the difference of two saved voltages: its size, the way it points, and what else the run saved about the junction", () => {
  const full = 0.06;
  // Too small to draw: under the floor, which the legend states.
  assert.equal(dropAt({ here: -0.075, there: -0.0745, full }), null);
  assert.equal(FLOOR * full, 0.0024);
  // It points down the drop: at the end with the lower voltage.
  const down = dropAt({ here: -0.02, there: -0.08, full });
  assert.deepEqual([down.kind, down.towards, down.drop], ["solid", "there", difference(-0.02, -0.08)]);
  assert.ok(Math.abs(down.share - 1) < 1e-12);
  assert.equal(dropAt({ here: -0.08, there: -0.02, full }).towards, "here");
  assert.ok(Math.abs(dropAt({ here: -0.05, there: -0.08, full }).share - 0.5) < 1e-9, "its width is linear in the drop");
  // A gate under half open is drawn hollow; where no junction has formed, two bars stand in for the wedge.
  assert.equal(dropAt({ here: -0.02, there: -0.08, full, gate: 0.12, formed: 1 }).kind, "hollow");
  assert.equal(dropAt({ here: -0.02, there: -0.08, full, gate: 0.96, formed: 1 }).kind, "solid");
  assert.equal(dropAt({ here: -0.02, there: -0.08, full, gate: 0.96, formed: 0 }).kind, "break");
  assert.equal(dropAt({ here: -0.0751, there: -0.075, full, gate: 0.96, formed: 0 }), null, "two cells at one voltage show nothing, formed or not");
  // A run that kept the junction's own voltage gives it, and nothing is worked out.
  assert.equal(dropAt({ across: -0.03, full }).towards, "here");
  assert.equal(dropAt({ here: NaN, there: 0, full }), null);
});

test("the wedge mark draws one sign for each junction that carries a drop, on the run's own numbers", async () => {
  const { run, parts } = made();
  await loadPart(run, "junction-gate", { root: null, fetcher: fetcherOf(parts) });
  const surface = surfaceOf(run);
  const fed = offer(run, "junction-drops");
  const mark = MARKS.wedge.create({ surface, run, fed, shown: display, strength: "quiet", colours: colours() });
  // The full width stands for the largest drop of the whole run, rounded up in the unit shown.
  const record = run.records.get("vm");
  const largest = fullDrop(run, (step, link) => record.at(step, link.a) - record.at(step, link.b), surface.links);
  assert.ok(mark.full >= largest && mark.full <= largest * 1.26, `${mark.full} for a largest drop of ${largest}`);
  assert.ok(Math.abs(mark.full * 1000 - Math.round(mark.full * 1000)) < 1e-6, "a round number of millivolts");
  mark.update(0, true);
  const gate = run.records.get("junction_gate"), formed = run.records.get("junction_abundance");
  const expected = { solid: 0, hollow: 0, break: 0 };
  for (const link of surface.links) {
    const drawn = dropAt({ here: record.at(0, link.a), there: record.at(0, link.b), full: mark.full, gate: gate.at(0, link.link), formed: formed.at(0, link.link) });
    if (drawn) expected[drawn.kind] += 1;
  }
  assert.deepEqual({ ...mark.counts }, expected);
  // The disc's edge: 18 cells on its rim, each joined outward by two or three junctions, and their gates are shut.
  assert.ok(expected.hollow >= 18, JSON.stringify(expected));
  assert.equal(expected.solid + expected.hollow + expected.break < surface.links.length / 2, true, "most junctions join cells at one voltage and carry no sign");
  // A record the run does not count as valid shows no sign at all.
  mark.update(0, false);
  assert.deepEqual({ ...mark.counts }, { solid: 0, hollow: 0, break: 0 });
  // The legend's lines: the scale in the unit shown, and what hollow and two bars mean, since the run saved both.
  const keys = mark.keys((value, decimals) => value.toFixed(decimals));
  assert.deepEqual(keys.map((item) => item.key), ["wedge", "wedge-hollow", "break"]);
  assert.match(keys[0].text, /the widest stands for \d+ mV\. Drops under [\d.]+ mV are not drawn/);
  mark.dispose();
  // Without the gate, no line speaks of hollow wedges.
  const bare = made({ gate: false });
  const plain = MARKS.wedge.create({ surface: surfaceOf(bare.run), run: bare.run, fed: offer(bare.run, "junction-drops"), shown: display, strength: "quiet", colours: colours() });
  assert.deepEqual(plain.keys((value, decimals) => value.toFixed(decimals)).map((item) => item.key), ["wedge", "break"]);
});

// ------------------------------------------------------------ the replay lens, without a browser

// The lens is driven here as the page drives it, with stand-ins for the page, the stage and
// the labels, and made-up runs served from memory. It needs no WebGL: a mark only writes
// into arrays and makes objects of the scene.
globalThis.HTMLElement ??= class {};
globalThis.customElements ??= { define() {}, get: () => null };
const { ReplayLens } = await import("../src/lenses/replay.js");

function lensFor(runs) {
  const files = new Map();
  for (const { file, entry, parts } of runs) {
    files.set(`${entry.id}.json`, file);
    for (const [part, content] of Object.entries(parts)) files.set(`${entry.id}.${part}.json`, content);
  }
  const asked = [];
  const before = { document: globalThis.document, fetch: globalThis.fetch };
  globalThis.document = { querySelector: () => null };
  globalThis.fetch = async (url) => {
    const name = String(url).split("/").pop();
    asked.push(name);
    const body = files.get(name);
    return { ok: Boolean(body), status: body ? 200 : 404, json: async () => JSON.parse(JSON.stringify(body)) };
  };
  const palette = { seq0: PALETTE[0], seq1: PALETTE[1], seq2: PALETTE[2], seq3: PALETTE[3], seq4: PALETTE[4], stUnstated: "#9aa6b2", fg: "#12283a", bg: "#eef2f6" };
  const stage = { palette, invalidate() {}, scene: { add() {}, remove() {} }, sun: {}, rig: { setView() {}, limits: {}, instant: true, flyTo() {}, distance: 100 }, camera: { fov: 40, aspect: 1.6 }, width: 1400, height: 900, reducedMotion: true };
  const labels = { clear() {}, calloutFrame: null, add: (spec) => ({ ...spec, element: { classList: { add() {}, remove() {} } }, hidden: false }), setText: (item, text) => (item.text = text) };
  const index = { format: "cells.visualizer.replay_index@1", experiments: [{ id: "e07-v1", label: "A made-up experiment", records: { vm: { label: "Membrane voltage", shown_between: [-0.09, -0.01] } } }], runs: runs.map((run) => run.entry) };
  const lens = new ReplayLens(stage, { raw: { replays: index } }, labels);
  lens.onChrome = () => lens.chrome();
  lens.onPanel = () => {};
  return { lens, asked, restore: () => Object.assign(globalThis, before) };
}
const heights = (lens) => lens.sheet.cells.map((cell) => cell.height);
const rowsOf = (lens) => lens.chrome().legend.layers.rows.map((row) => `${row.label}: ${row.options.map((option) => option.label + (option.on ? "*" : "")).join(" | ")}`);

test("the replay opens as it always did: coloured by voltage, with the height repeating the colour", async (t) => {
  const { lens, asked, restore } = lensFor([syntheticRun()]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.equal(lens.switch.strength, "quiet");
  const legend = lens.chrome().legend;
  assert.equal(legend.scale.label, "Membrane voltage");
  assert.equal(legend.note.text, "Height repeats the colour. Every step is a saved record.");
  assert.deepEqual(legend.keys.map((item) => item.key), ["seam", "frame", "ring"], "the sheet's standing marks are listed as before");
  assert.equal(legend.folded, undefined, "and nothing asks for them to fold away");
  assert.deepEqual(rowsOf(lens), ["Height: Off | Membrane voltage* | Generation (synthetic)", "Junctions: Off* | Voltage drops"]);
  assert.deepEqual(legend.layers.cannot, []);
  assert.deepEqual(legend.layers.keys, []);
  assert.deepEqual(asked.filter((name) => name.includes("junction-gate")), [], "no record in a file of its own is fetched before a layer needs it");
  // The card's choice of colour: the records a colouring layer can show.
  assert.deepEqual(lens.chrome().run.colour, { options: [["vm", "Membrane voltage"], ["generation", "Generation (synthetic)"]], active: "vm" });
  // Quiet heights are the sheet's own, from its low to its high.
  assert.ok(Math.max(...heights(lens)) <= lens.high + 1e-9 && Math.min(...heights(lens)) >= lens.low - 1e-9);
});

test("the card's colour moves the height with it while the height repeats the colour, and not once the two are apart", async (t) => {
  const { lens, restore } = lensFor([syntheticRun()]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  lens.setRecord("generation");
  assert.deepEqual(lens.switch.on, ["generation-tint", "generation-relief"]);
  assert.equal(lens.record.id, "generation");
  assert.match(lens.chrome().legend.note.text, /^Height repeats the colour/);
  lens.setRecord("vm");
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  // Height off: the sheet lies flat, and stays flat when the colour changes.
  await lens.setLayer("voltage-relief", false);
  assert.deepEqual(lens.switch.on, ["voltage-tint"]);
  assert.ok(heights(lens).every((height) => height === lens.low));
  assert.match(lens.chrome().legend.note.text, /^The sheet is flat/);
  lens.setRecord("generation");
  assert.deepEqual(lens.switch.on, ["generation-tint"]);
  // Height by one record and colour by another: two quantities at once, and the legend says which is which.
  await lens.setLayer("voltage-relief", true);
  assert.deepEqual(lens.switch.on, ["generation-tint", "voltage-relief"]);
  assert.equal(lens.chrome().legend.note.text, "Height: membrane voltage, from −90 mV (low) to −10 mV (tall). Every step is a saved record.");
  assert.equal(lens.record.id, "generation", "the tags and the chart speak of the record that colours the sheet");
  lens.setRecord("vm");
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.match(lens.chrome().legend.note.text, /^Height repeats the colour/);
});

test("the drops are fetched when switched on, drawn beside the other layers, explained in the panel, and follow to the next run", async (t) => {
  const first = syntheticRun(), second = syntheticRun({ seed: 2 });
  const { lens, asked, restore } = lensFor([first, second]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.equal(lens.has("layers:shown"), true);
  await lens.setLayer("junction-drops", true);
  assert.deepEqual(asked.filter((name) => name.includes("junction-gate")), [`${first.entry.id}.junction-gate.json`]);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief", "junction-drops"]);
  const counts = lens.drawn.get("junction-drops").mark.counts;
  assert.ok(counts.hollow > 0 && counts.solid + counts.hollow + counts.break < lens.surface.links.length / 2, JSON.stringify(counts));
  const legend = lens.chrome().legend;
  assert.deepEqual(legend.layers.keys.map((item) => item.key), ["wedge", "wedge-hollow", "break"]);
  assert.equal(legend.folded, true, "the sheet's standing marks fold away to leave the layers' signs room");
  assert.equal(legend.layers.details, "layers:shown");
  assert.deepEqual(rowsOf(lens)[1], "Junctions: Off | Voltage drops*");
  // The panel: what each layer shows, and what stands behind its numbers.
  const panel = lens.describe("layers:shown");
  assert.deepEqual(panel.sections.map((section) => section.title), ["Colour: membrane voltage", "Height: membrane voltage", "Junctions: voltage drops"]);
  const drops = panel.sections[2].items;
  assert.deepEqual(drops.map((item) => item.label), ["What it shows", "Its numbers: worked out by the viewer", "What else the run saved about it"]);
  assert.match(drops[1].lines.join(" "), /Worked out by the viewer from the saved membrane voltage.*held bath at 0 V.*So the difference is the voltage across the junction itself.*Saved by the run; computed by/);
  assert.equal(panel.sections[0].items[1].label, "Its numbers: saved by the run");
  // Bold: the same values higher, a bar beside the sheet, and what stands over the sheet clears the tallest cell.
  const quiet = Math.max(...heights(lens));
  lens.setStrength("bold");
  assert.ok(Math.max(...heights(lens)) > 3 * quiet);
  assert.equal(lens.markOn("height").mark.bar.text, "20 mV");
  for (const frame of lens.sheet.frames) assert.ok(frame.mesh.position.y > Math.max(...heights(lens)), "the region's frame stands over the tallest cell");
  assert.deepEqual(lens.chrome().legend.layers.keys.map((item) => item.key), ["level", "wedge", "wedge-hollow", "break"]);
  lens.setStrength("quiet");
  assert.equal(Math.max(...heights(lens)), quiet);
  // Another run: the drops stay on, with that run's own gate fetched.
  await lens.show(second.entry.id);
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(lens.run.id, second.entry.id);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief", "junction-drops"]);
  assert.deepEqual(asked.filter((name) => name.includes("junction-gate")), [`${first.entry.id}.junction-gate.json`, `${second.entry.id}.junction-gate.json`]);
  // Off: the signs go, and the legend is as it was.
  await lens.setLayer("junction-drops", false);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.deepEqual(lens.chrome().legend.layers.keys, []);
});

test("a layer a run cannot feed is listed with the reason and cannot be switched on; a part that does not come is said", async (t) => {
  const bare = syntheticRun({ surroundings: false }), lost = syntheticRun({ seed: 3 });
  delete lost.parts["junction-gate"]; // its file is not beside the page
  const { lens, restore } = lensFor([bare, lost]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  const layers = lens.chrome().legend.layers;
  assert.deepEqual(layers.cannot.map((item) => [item.id, item.label]), [["junction-drops", "Junctions: voltage drops"]]);
  assert.match(layers.cannot[0].why, /did not save each junction's voltage/);
  assert.deepEqual(rowsOf(lens), ["Height: Off | Membrane voltage* | Generation (synthetic)"], "it has no row of its own to press");
  await lens.setLayer("junction-drops", true);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.match(lens.describe("layers:shown").sections.at(-1).items[0].detail, /did not save each junction's voltage/);
  // The other run can feed the drops, but its gate's file does not come: nothing is drawn, and the row says why.
  await lens.show(lost.entry.id);
  await lens.setLayer("junction-drops", true);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  const row = lens.chrome().legend.layers.rows.find((item) => item.channel === "links");
  assert.match(row.problem, /could not be fetched: .*answered 404/);
});
