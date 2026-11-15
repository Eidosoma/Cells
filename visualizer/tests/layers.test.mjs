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
import { difference, rate, charge, chargesIn, potentialTerms, DERIVATIONS, FARADAY, GAS, ELEMENTARY } from "../src/layers/derive.js";
import { declared, declaredOn, behind, family, constantOf, LIVES_ON, KINDS } from "../src/layers/records.js";
import { layersFor, feeds, readDeclarations, validateLayer, account, partsOf, Switch, CHANNELS, LAYERS_FORMAT, NOT_SAVED } from "../src/layers/layers.js";
import { shareOf, roundUp } from "../src/layers/scale.js";
import { MARKS } from "../src/layers/marks/index.js";
import { heightOf, barStretch, riseOf, crossings, BOLD_RISE } from "../src/layers/marks/relief.js";
import { dropAt, fullDrop, FLOOR } from "../src/layers/marks/wedge.js";
import { arrowOutline, lanes, BALANCE } from "../src/layers/marks/arrows.js";
import { worthFor, marksFor, spots, MOST } from "../src/layers/marks/stipple.js";
import { tokenFor, beadsASecond, ionsASecond, timeWords, tokenWords, PER_FMOL, BUSIEST } from "../src/layers/marks/beads.js";
import { membranesOf, pushPull, membraneCharge, largest } from "../src/layers/membrane.js";
import { Closeup, freeRect, cardPlace, PIECE } from "../src/layers/closeup.js";
import { ionColours } from "../src/layers/ions.js";

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
  // Which way a term drives its ion is read from the term in J/mol, never from the volts: dividing by z F
  // turns a negative ion's sign round. Potassium: more of it inside pushes it out, a negative inside pulls it in.
  assert.deepEqual(potassium.drives, { concentration: "out", electrical: "in", sum: "out" });
  assert.deepEqual([potassium.size.concentration, potassium.size.electrical, potassium.size.sum], [Math.abs(potassium.volts.concentration), 0.07, Math.abs(potassium.volts.sum)]);
  // The negative ion: more of it outside pushes it in, and the negative inside pushes it out, though its
  // concentration term in volts is positive and its electrical term in volts negative.
  assert.ok(chloride.volts.concentration > 0 && chloride.volts.electrical < 0);
  assert.ok(chloride.concentration < 0 && chloride.electrical > 0);
  assert.deepEqual(chloride.drives, { concentration: "in", electrical: "out", sum: chloride.sum > 0 ? "out" : "in" });
  assert.equal(chloride.drives.sum, "out", "at -70 mV with 10 mM inside and 120 mM outside, the voltage wins by a few millivolts");
  assert.ok(Math.abs(chloride.size.sum - 0.00362) < 1e-4, `what is left for the negative ion is ${chloride.size.sum} V`);
  // The numbers of a judged run, worked out by hand in 64 bits (cell_63 of e07-v1 a-donor-fast-k1-d37-s1.0 seed 5 at 1170 s):
  // the generic negative ion M, 13.0883 mM inside and 140 mM outside at -20.589 mV.
  const m = potentialTerms({ inside: 13.0883, outside: 140, voltage: -0.020589, valence: -1, temperature: 310 });
  assert.deepEqual([m.drives.concentration, m.drives.electrical, m.drives.sum], ["in", "out", "in"]);
  assert.ok(Math.abs(m.size.concentration - 0.063309) < 2e-6 && Math.abs(m.size.sum - 0.04272) < 2e-6, JSON.stringify(m.size));
  // In balance to the last digit: nothing is left, and it drives the ion neither way.
  const still = potentialTerms({ inside: 5, outside: 5, voltage: 0, valence: 1, temperature: 310 });
  assert.deepEqual([still.sum, still.drives.sum, still.drives.concentration, still.drives.electrical], [0, null, null, null]);
  // What the engine refuses, the viewer does not work out.
  for (const bad of [{ inside: 0 }, { outside: -1 }, { valence: 0 }, { temperature: 0 }, { voltage: NaN }]) {
    assert.equal(potentialTerms({ inside: 140, outside: 5, voltage: -0.07, valence: 1, temperature: 310, ...bad }), null);
  }
});

// ------------------------------------------------------------ the declarations

test("the declared layers follow the contract, and each names a mark the viewer has", () => {
  assert.equal(declarations.format, LAYERS_FORMAT);
  assert.deepEqual(PROBLEMS, []);
  assert.deepEqual(LAYERS.map((item) => item.id), ["voltage-tint", "voltage-relief", "junction-drops", "ion-push-pull", "membrane-charge", "ion-traffic"]);
  // The two layers of a chosen cell's membrane are drawn on its close-up, not on the sheet.
  assert.deepEqual(LAYERS.filter((item) => MARKS[item.mark].surface === "membrane").map((item) => [item.id, item.mark, item.channels[0], item.quantity.derivation]), [["ion-push-pull", "arrows", "arrows", "potential terms"], ["membrane-charge", "stipple", "surface", "charge"], ["ion-traffic", "beads", "motion", "rate"]]);
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
  // A rule with several inputs: the layer names what may fill each part of it, and no part the rule does not have.
  const several = [
    [(bad) => delete bad.quantity.of.temperature, /its rule needs temperature, and it names nothing for it/],
    [(bad) => (bad.quantity.of.inside = [{ amount: "amount" }]), /its rule needs inside/],
    [(bad) => (bad.quantity.of.permeability = ["membrane_permeability"]), /permeability is not a part of the rule potential terms/],
    [(bad) => (bad.quantity.of = "vm"), /its rule needs voltage/],
  ];
  for (const [damage, expected] of several) {
    const bad = JSON.parse(JSON.stringify(layer("ion-push-pull")));
    damage(bad);
    const problems = validateLayer(bad, MARKS);
    assert.ok(problems.some((problem) => expected.test(problem)), `expected ${expected}, got ${JSON.stringify(problems)}`);
  }
  assert.deepEqual(Object.keys(partsOf(layer("ion-push-pull").quantity)), ["voltage", "inside", "outside", "temperature", "valence"]);
  assert.deepEqual(Object.keys(partsOf(layer("membrane-charge").quantity)), ["voltage", "capacitance", "area"]);
  assert.equal(partsOf(layer("junction-drops").quantity.first_of[2]), null, "a difference has one input");
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
  assert.deepEqual(offers.map((item) => [item.layer.id, item.ok]), [["voltage-tint", true], ["voltage-relief", true], ["junction-drops", true], ["ion-push-pull", false], ["membrane-charge", false], ["ion-traffic", false], ["generation-tint", true], ["generation-relief", true]]);
  assert.equal(offer(run, "ion-traffic").why, NOT_SAVED);
  // This run's view lists no membranes: its one voltage per cell is no membrane's own, and it is said.
  for (const id of ["ion-push-pull", "membrane-charge"]) assert.equal(offer(run, id).why, "This run saved the membrane voltage for each cell, not for each membrane.");
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
  const palette = { seq0: PALETTE[0], seq1: PALETTE[1], seq2: PALETTE[2], seq3: PALETTE[3], seq4: PALETTE[4], stUnstated: "#9aa6b2", fg: "#12283a", bg: "#eef2f6", bioMembrane: "#2fb3a3", dark: false };
  // A camera that stands in for the stage's: it looks down on the sheet from a little way off, with no window behind it.
  const camera = new THREE.PerspectiveCamera(34, 1400 / 900, 0.1, 5000);
  camera.position.set(0, 220, 200);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const stage = {
    palette, invalidate() {}, scene: { add() {}, remove() {} }, sun: {}, rig: { setView() {}, limits: {}, instant: true, flyTo() {}, distance: 100, azimuth: 0, polar: 0.8 }, camera, width: 1400, height: 900, reducedMotion: true,
    project(point, out) {
      out.copy(point).project(camera);
      out.x = (out.x * 0.5 + 0.5) * 1400;
      out.y = (-out.y * 0.5 + 0.5) * 900;
      return out;
    },
  };
  const shown = [];
  const labels = {
    shown,
    clear: () => shown.splice(0),
    calloutFrame: null,
    keepClear: { top: 56 },
    blocked: () => [{ left: 0, top: 56, right: 303, bottom: 900 }],
    add: (spec) => {
      const item = { ...spec, element: { classList: { add() {}, remove() {} }, style: {}, offsetWidth: 300, offsetHeight: 44 }, hidden: false, width: 60, height: 16 };
      shown.push(item);
      return item;
    },
    setText: (item, text) => (item.text = text),
    remove: (item) => shown.splice(shown.indexOf(item), 1),
  };
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
  // This made-up run lists no membranes, so the two layers of a membrane are named as ones it cannot feed.
  assert.deepEqual(legend.layers.cannot.map((item) => item.id), ["ion-push-pull", "membrane-charge", "ion-traffic"]);
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
  assert.deepEqual(panel.sections.map((section) => section.title), ["Colour: membrane voltage", "Height: membrane voltage", "Junctions: voltage drops", "Not shown for this run"]);
  assert.deepEqual(panel.sections[3].items.map((item) => item.label), ["Arrows: push and pull on ions", "Membrane: membrane charge", "Motion: ion traffic"]);
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
  assert.deepEqual(layers.cannot.map((item) => [item.id, item.label]), [["junction-drops", "Junctions: voltage drops"], ["ion-push-pull", "Arrows: push and pull on ions"], ["membrane-charge", "Membrane: membrane charge"], ["ion-traffic", "Motion: ion traffic"]]);
  assert.match(layers.cannot[0].why, /did not save each junction's voltage/);
  assert.deepEqual(rowsOf(lens), ["Height: Off | Membrane voltage* | Generation (synthetic)"], "it has no row of its own to press");
  await lens.setLayer("junction-drops", true);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.match(lens.describe("layers:shown").sections.at(-1).items[0].detail, /did not save each junction's voltage/);
  await lens.setLayer("ion-push-pull", true);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"], "a layer the run cannot feed cannot be switched on");
  // The other run can feed the drops, but its gate's file does not come: nothing is drawn, and the row says why.
  await lens.show(lost.entry.id);
  await lens.setLayer("junction-drops", true);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  const row = lens.chrome().legend.layers.rows.find((item) => item.channel === "links");
  assert.match(row.problem, /could not be fetched: .*answered 404/);
});

// ------------------------------------------------------------ rules with several inputs, and one cell's membrane

test("a rule with several inputs is fed part by part: a saved record, one for each species, or a constant the view states", async () => {
  const { run, parts } = made({ membrane: true });
  const push = offer(run, "ion-push-pull"), stored = offer(run, "membrane-charge");
  assert.equal(push.ok, true, push.why);
  assert.equal(stored.ok, true, stored.why);
  // Each part of the rule, with what fills it in this run.
  assert.deepEqual(Object.fromEntries(Object.entries(push.inputs).map(([part, input]) => [part, `${input.how}: ${input.name}`])), {
    voltage: "record: membrane_voltage_V",
    inside: "records: concentration_mM",
    outside: "constant: extracellular_concentration_mM",
    temperature: "constant: temperature",
    valence: "constant: valence",
  });
  assert.deepEqual(Object.fromEntries(Object.entries(stored.inputs).map(([part, input]) => [part, `${input.how}: ${input.name}`])), { voltage: "record: membrane_voltage_V", capacitance: "constant: membrane_capacitance", area: "constant: membrane_area" });
  assert.equal(push.source.id, "membrane_voltage_V");
  assert.equal(push.source.lives_on, "membrane");
  // The concentrations come in files of their own, one for each ion: they are fetched when the layer is switched on. The charge needs none.
  assert.deepEqual(push.parts, ["concentration-na", "concentration-k", "concentration-m"]);
  assert.deepEqual(stored.parts, []);
  assert.deepEqual(family(run, "concentration_mM").map((record) => [record.species, record.loaded]), [["Na", false], ["K", false], ["M", false]]);
  for (const part of push.parts) await loadPart(run, part, { root: null, fetcher: fetcherOf(parts) });
  assert.deepEqual(offer(run, "ion-push-pull").parts, []);
  // A record that comes in a file of its own is no plain colouring: the offers do not grow once it is fetched.
  assert.deepEqual(layersFor(run, LAYERS, MARKS).map((item) => item.layer.id), ["voltage-tint", "voltage-relief", "junction-drops", "ion-push-pull", "membrane-charge", "ion-traffic", "generation-tint", "generation-relief"]);
  // A constant is read as the view states it, with its account of why nothing changes it.
  assert.deepEqual({ ...constantOf(run, "membrane_capacitance"), says: null }, { id: "membrane_capacitance", label: "Membrane capacitance", unit: "F", lives_on: "membrane", set: "membrane", axes: ["membrane"], says: null, from: "definition.json", constant: true });
  assert.equal(constantOf(run, "membrane_thickness"), null);
  assert.equal(run.constants.get("extracellular_concentration_mM").at(7, 1), 5, "potassium outside, at any bath");
  assert.equal(run.constants.get("temperature").at(), 310);
});

test("what a run does not give for a part of a rule is said in the page's words, and the layer is not offered", () => {
  // No word on which way the voltage is positive: an arrow would have no way to point.
  const unsigned = made({ membrane: "unsigned" }).run;
  for (const id of ["ion-push-pull", "membrane-charge"]) assert.deepEqual([offer(unsigned, id).ok, offer(unsigned, id).why], [false, "This run saved the membrane voltage, but does not say which way it is positive."]);
  // No constants, with the view's reason: the definition's values may have changed during the run.
  const unstated = made({ membrane: "unstated" }).run;
  assert.equal(offer(unstated, "ion-push-pull").why, "This run did not save the concentration of each ion outside over time. Not stated as a constant: the run's model (synthetic) is not one whose operators the viewer knows.");
  assert.equal(offer(unstated, "membrane-charge").why, "This run did not save the membrane's capacitance over time. Not stated as a constant: the run's model (synthetic) is not one whose operators the viewer knows.");
  // A view with constants and concentrations, and no word on which membrane lies on which cell.
  const { file, entry } = syntheticRun({ membrane: true });
  const membranes = file.view.sets.find((set) => set.id === "membrane");
  delete membranes.geometry;
  delete membranes.outside;
  assert.equal(offer(openReplay(file, entry), "ion-push-pull").why, "This run's files do not say which membrane lies on which cell, and which outside it faces.");
  // A run that saved amounts and no concentrations is fed by the amount over the volume the view states.
  const amounts = syntheticRun({ membrane: true });
  for (const record of amounts.file.view.records) {
    if (record.field !== "concentration_mM") continue;
    record.field = "amount";
    record.id = `amount.${record.species}`;
    record.unit = "fmol";
  }
  const fed = offer(openReplay(amounts.file, amounts.entry), "ion-push-pull");
  assert.equal(fed.ok, true, fed.why);
  assert.deepEqual([fed.inputs.inside.how, fed.inputs.inside.amount.name, fed.inputs.inside.over.name], ["ratio", "amount", "volume"]);
});

test("the push and pull on each ion at one membrane: the rule's own terms on the run's own numbers, and the way each drives its ion", async () => {
  const { run, parts } = made({ membrane: true });
  for (const part of offer(run, "ion-push-pull").parts) await loadPart(run, part, { root: null, fetcher: fetcherOf(parts) });
  const fed = offer(run, "ion-push-pull");
  const reader = pushPull(run, fed), membranes = membranesOf(run);
  assert.deepEqual(reader.species, ["Na", "K", "M"]);
  assert.deepEqual(reader.missing, [{ id: "P", lacks: "its concentration in the cell" }]);
  assert.deepEqual(membranes.of(40), [40]);
  // One membrane at one record, against the rule applied by hand to the saved arrays.
  const step = run.indexAt(1170), membrane = 40, cell = membranes.cell[membrane];
  const voltage = run.records.get("vm").at(step, cell);
  const terms = reader.at(step, membrane);
  const bath = { Na: 145, K: 5, M: 140 }, valence = { Na: 1, K: 1, M: -1 };
  for (const term of terms) {
    const inside = run.records.get(`concentration_mM.${term.id}`).at(step, cell);
    const byHand = potentialTerms({ inside, outside: bath[term.id], voltage, valence: valence[term.id], temperature: 310 });
    assert.deepEqual({ inside: term.inside, outside: term.outside, voltage: term.voltage, valence: term.valence, temperature: term.temperature }, { inside, outside: bath[term.id], voltage, valence: valence[term.id], temperature: 310 });
    assert.deepEqual([term.concentration, term.electrical, term.sum, term.size, term.drives], [byHand.concentration, byHand.electrical, byHand.sum, byHand.size, byHand.drives]);
  }
  // Sodium is pushed and pulled inwards; potassium pushed out and pulled in; the negative ion pushed in and pulled out.
  assert.deepEqual(terms.map((term) => [term.id, term.drives.concentration, term.drives.electrical]), [["Na", "in", "in"], ["K", "out", "in"], ["M", "in", "out"]]);
  assert.ok(terms[0].size.sum > terms[0].size.concentration, "for sodium the two add up");
  // The scale of the arrows is the run's largest term, over every membrane and every valid record.
  const most = largest(run, membranes.ids.length, (at, index) => Math.max(...reader.at(at, index).map((term) => Math.max(term.size.concentration, term.size.electrical, term.size.sum))));
  assert.ok(most > terms[0].size.sum * 0.9 && most < 0.2, `the largest term of the run is ${most} V`);
});

test("the charge of one membrane is its capacitance times its voltage, counted in charges and for each square micrometre", () => {
  const { run } = made({ membrane: true });
  const reader = membraneCharge(run, offer(run, "membrane-charge"));
  const step = run.indexAt(600), membrane = 3;
  const voltage = run.records.get("vm").at(step, 3);
  const reading = reader.at(step, membrane);
  assert.equal(reading.coulombs, 1.6e-11 * voltage);
  assert.equal(reading.charges, Math.abs(1.6e-11 * voltage) / ELEMENTARY);
  assert.equal(chargesIn(-2 * ELEMENTARY), 2);
  assert.equal(reading.per_um2, reading.charges / (3.2e-10 * 1e12));
  assert.equal(reading.inside, "minus", "a negative voltage: the inner face carries the minus");
  // About 23,000 charges on a square micrometre at -75 mV with 0.05 F/m2: one ion in thousands.
  assert.ok(reading.per_um2 > 20000 && reading.per_um2 < 26000, String(reading.per_um2));
  // A positive voltage puts the plus at the inner face; the record's sign, where it says the outside is the higher, turns the voltage round.
  const turned = syntheticRun({ membrane: true });
  for (const record of turned.file.view.records) if (record.sign) record.sign = { ...record.sign, high: "outside" };
  const other = openReplay(turned.file, turned.entry);
  assert.equal(membraneCharge(other, offer(other, "membrane-charge")).at(step, membrane).inside, "plus");
});

test("how many marks stand for a charge, and where: one worth for the whole run, and places that never move", () => {
  // One mark is one charge while the run's largest count fits; then two, five, ten.
  assert.deepEqual([worthFor(124), worthFor(MOST), worthFor(MOST + 1), worthFor(700), worthFor(1500)], [1, 1, 2, 5, 10]);
  assert.deepEqual([marksFor(123.97, 1), marksFor(32.13, 1), marksFor(0.4, 1), marksFor(700, 5), marksFor(1e6, 1)], [124, 32, 0, 140, MOST]);
  // The places at a face are a fixed sequence: the first N are the same whatever N is, so a mark never moves when the count changes.
  const outer = spots(PIECE, 1), inner = spots(PIECE, -1);
  assert.equal(outer.length, MOST);
  assert.deepEqual(spots(PIECE, 1).slice(0, 40), outer.slice(0, 40));
  for (const [x, y, z] of outer) assert.ok(Math.abs(x) < PIECE.width / 2 && Math.abs(z) < PIECE.depth / 2 && y > PIECE.thick / 2 && y < PIECE.thick / 2 + 0.3, `${[x, y, z]}`);
  for (const [, y] of inner) assert.ok(y < -PIECE.thick / 2 && y > -PIECE.thick / 2 - 0.3);
  assert.notDeepEqual(outer[0].map(Math.abs), inner[0].map(Math.abs), "the two faces are not mirror images");
  // They fill the face evenly at any count: no two of the first sixty stand on one another.
  for (let a = 0; a < 60; a++) for (let b = a + 1; b < 60; b++) assert.ok(Math.hypot(outer[a][0] - outer[b][0], outer[a][2] - outer[b][2]) > 0.04, `${a} and ${b}`);
  // No mark is put under the close-up's own words.
  const clear = spots(PIECE, 1, (x, y, z) => Closeup.free(x, y, z));
  assert.ok(clear.every(([x, y, z]) => Closeup.free(x, y, z)) && clear.length === MOST);
  assert.equal(Closeup.free(-PIECE.width / 2 + 0.3, 0.55, 0), false);
});

test("an arrow is as long as its term and points the way its ion is driven; the ions stand in lanes along the piece", () => {
  // An arrow enters the membrane at one face, crosses it, and stands its length out from the other face.
  const up = arrowOutline(1, 0.6, 0.05, true, 0.3), down = arrowOutline(1, 0.6, 0.05, false, 0.3);
  assert.equal(up.length, 7);
  assert.deepEqual(up[3], [1, 0.15 + 0.6], "its tip stands 0.6 out from the outer face");
  assert.deepEqual(down[3], [1, -0.15 - 0.6]);
  assert.deepEqual([up[0], up[6]], [[0.95, -0.15], [1.05, -0.15]], "an arrow out of the cell enters at the inner face");
  assert.deepEqual([down[0], down[6]], [[0.95, 0.15], [1.05, 0.15]], "an arrow into the cell enters at the outer face");
  // A term smaller than a head: the head is as long as the term, and stands on the face the arrow leaves by.
  const small = arrowOutline(0, 0.04, 0.05, true, 0.3);
  assert.deepEqual([small[3], small[2][1], small[4][1]], [[0, 0.15 + 0.04], 0.15, 0.15]);
  // Nothing of an arrow's size is in the part that crosses the membrane: two arrows differ by their lengths alone.
  assert.ok(Math.abs(arrowOutline(0, 0.9, 0.05, true, 0.3)[3][1] - up[3][1] - 0.3) < 1e-12);
  // Under a millivolt is drawn as a ring: in balance.
  assert.equal(BALANCE, 0.001);
  const three = lanes(3), five = lanes(5);
  assert.equal(three.length, 3);
  assert.ok(three[0].x - three[0].apart > -PIECE.width / 2 + 0.82, "the first ion stands clear of the words Outside and Inside");
  assert.ok(three[2].x + three[2].apart < PIECE.width / 2);
  assert.ok(five[1].x - five[0].x > 2 * five[0].apart, "with more ions the arrows stand closer, and still apart");
});

test("the close-up stands in the free part of the window, above its cell where there is room", () => {
  // The largest rectangle no panel covers: beside the cards on the left and the panel on the right, above the timeline.
  const free = freeRect(1440, 900, [{ left: 0, top: 60, right: 303, bottom: 900 }, { left: 1040, top: 56, right: 1440, bottom: 900 }, { left: 420, top: 820, right: 920, bottom: 890 }], 56);
  assert.deepEqual([free.left, free.top, free.right, free.bottom], [303, 56, 1040, 820]);
  assert.deepEqual(freeRect(390, 844, [], 56), { left: 0, top: 56, right: 390, bottom: 844, area: 390 * 788 });
  // A phone: a card across the top and a panel across the bottom leave the middle.
  const phone = freeRect(390, 844, [{ left: 8, top: 60, right: 382, bottom: 250 }, { left: 0, top: 520, right: 390, bottom: 844 }], 56);
  assert.deepEqual([phone.top, phone.bottom], [250, 520]);
  // Above the cell where it fits, the tie coming to the card's bottom; below it otherwise; inside the free part in any case.
  const above = cardPlace({ x: 700, y: 600 }, free, 430, 320);
  assert.deepEqual([above.side, above.x, above.y, above.fits], ["bottom", 700, 600 - 26 - 160, true]);
  const below = cardPlace({ x: 700, y: 200 }, free, 430, 320);
  assert.deepEqual([below.side, below.y, below.fits], ["top", 200 + 26 + 160, true]);
  // With room on neither side the card lies over its cell, and says where the cell would have to stand for it to fit above.
  const over = cardPlace({ x: 700, y: 400 }, free, 430, 420);
  assert.deepEqual([over.fits, over.room], [false, { x: 700, y: 56 + 10 + 420 + 26 + 6 }]);
  assert.ok(over.y - 210 >= free.top && over.y + 210 <= free.bottom);
  const edge = cardPlace({ x: 320, y: 600 }, free, 430, 320);
  assert.equal(edge.x, 303 + 10 + 215, "pushed in from the cards on the left");
  const tight = cardPlace({ x: 200, y: 400 }, phone, 300, 240);
  assert.ok(tight.y - 120 >= phone.top && tight.y + 120 <= phone.bottom, "kept between the card and the panel");
  assert.equal(Closeup.widthFor(1440, free), 430);
  assert.equal(Closeup.widthFor(390, { left: 0, right: 390 }), 300);
});

test("each ion has one fixed colour; a species the table does not know wears the neutral tone", async () => {
  const table = JSON.parse(await readFile(path.join(ROOT, "data", "layers", "ions.json"), "utf8"));
  const light = ionColours(table, ["Na", "K", "M", "P"], false), dark = ionColours(table, ["Na", "K", "M", "P"], true);
  assert.deepEqual([...light], [["Na", "#eb6834"], ["K", "#2a78d6"], ["M", "#1baf7a"], ["P", "#6e6a64"]]);
  assert.deepEqual([...dark], [["Na", "#d95926"], ["K", "#3987e5"], ["M", "#199e70"], ["P", "#b3aea6"]]);
  // The same ion has the same colour whatever else the run holds, and in whatever order.
  assert.equal(ionColours(table, ["K", "Ca", "Na"], false).get("Na"), light.get("Na"));
  assert.equal(ionColours(table, ["K", "Ca", "Na"], false).get("Ca"), table.other.light);
  // Cl and the generic M share the colour of a definition's mobile negative ion; where a run holds both, the later takes the neutral tone.
  assert.deepEqual([...ionColours(table, ["Cl", "M"], false)], [["Cl", "#1baf7a"], ["M", "#6e6a64"]]);
  assert.equal(ionColours(table, ["Cl"], false).get("Cl"), ionColours(table, ["M"], false).get("M"));
});

test("with a cell chosen, a layer on its membrane is drawn on a close-up: built for that cell, read at the record shown, taken down with the choice", async (t) => {
  const first = syntheticRun({ membrane: true }), second = syntheticRun({ seed: 2 });
  const { lens, asked, restore } = lensFor([first, second]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  lens.seek(1170);
  assert.deepEqual(rowsOf(lens), ["Height: Off | Membrane voltage* | Generation (synthetic)", "Junctions: Off* | Voltage drops", "Membrane: Off* | Membrane charge", "Arrows: Off* | Push and pull on ions"]);
  // Switched on with no cell chosen: the records are fetched, nothing is drawn yet, and the switch says how to see it.
  await lens.setLayer("ion-push-pull", true);
  assert.deepEqual(asked.filter((name) => name.includes("concentration")).sort(), ["k", "m", "na"].map((ion) => `${first.entry.id}.concentration-${ion}.json`));
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief", "ion-push-pull"]);
  assert.equal(lens.closeup, null);
  assert.equal(lens.chrome().legend.layers.hint, "Choose a cell of the sheet: a piece of its membrane is drawn beside it.");
  assert.match(lens.describe("layers:shown").sections[2].items.at(-1).detail, /No cell is chosen now/);
  // A cell is chosen: the close-up is built for its membrane.
  lens.setSelection("cell:40");
  assert.deepEqual([lens.closeup.cell, lens.closeup.membrane], [40, { index: 40, id: "membrane_40", of: 1 }]);
  assert.deepEqual([...lens.onMembrane.keys()], ["ion-push-pull"]);
  assert.equal(lens.chrome().legend.layers.hint, null);
  const arrows = lens.onMembrane.get("ion-push-pull").mark;
  const step = lens.player.index, cell = 40;
  const byHand = (id, bath, valence) => potentialTerms({ inside: lens.run.records.get(`concentration_mM.${id}`).at(step, cell), outside: bath, voltage: lens.run.records.get("vm").at(step, cell), valence, temperature: 310 });
  assert.deepEqual(arrows.readings.map((term) => [term.id, term.size, term.drives]), [["Na", byHand("Na", 145, 1).size, byHand("Na", 145, 1).drives], ["K", byHand("K", 5, 1).size, byHand("K", 5, 1).drives], ["M", byHand("M", 140, -1).size, byHand("M", 140, -1).drives]]);
  assert.ok(arrows.full >= Math.max(...arrows.readings.map((term) => term.size.sum)) && Number.isInteger(Math.round(arrows.full * 1e4)), `the full length of an arrow stands for ${arrows.full} V`);
  // The legend: each ion with its own colour beside its name, and what each of the three arrows is.
  const keys = lens.chrome().legend.layers.keys;
  assert.deepEqual(keys.map((item) => item.key), ["ions", "arrow-hollow", "arrow-faint", "arrow-solid", "none"]);
  assert.deepEqual(keys[0].chips, [{ label: "Na", colour: "#eb6834" }, { label: "K", colour: "#2a78d6" }, { label: "M", colour: "#1baf7a" }]);
  assert.match(keys[4].text, /^P: not drawn\. This run did not save its concentration in the cell$/);
  // The close-up says what it is: the membrane and the cell, the time, the run, and what it is worked out from.
  lens.placeCloseup();
  const words = lens.labels.shown.filter((label) => String(label.kind).startsWith("closeup")).map((label) => label.text);
  const caption = words.find((text) => text.startsWith("Membrane of"));
  // On a wide window it also says, in a line, what the three arrows are.
  assert.equal(caption, "Membrane of cell_40 at 19 min 30 s\nsynthetic-example, seed 1\nWorked out by the viewer from the saved membrane voltage and ion concentrations, with the composition outside, temperature and valences of the run's definition.\nHollow arrow: the push of the concentration difference. Faint: the pull of the voltage. Solid: what is left.");
  assert.ok(words.includes("Outside") && words.includes("Inside"));
  assert.ok(words.some((text) => /^Na\n\d+ mV in$/.test(text)), JSON.stringify(words));
  assert.ok(words.some((text) => /^K\n(\d+ mV (in|out)|in balance)$/.test(text)));
  // It stands above its cell, clear of the cards on the left, three tenths of the window wide.
  const placed = lens.closeup.placed;
  assert.ok(placed.width === 420 && placed.side === "bottom" && placed.x - placed.width / 2 >= 303 && placed.y + placed.height / 2 < placed.cell.y && placed.y - placed.height / 2 > 56, JSON.stringify(placed));
  // The cell's panel gives the numbers of the close-up at the record shown, each with the way it drives the ion.
  const panel = lens.describe("cell:40");
  assert.equal(panel.sections[0].title, "On its membrane at 19 min 30 s");
  assert.deepEqual(panel.sections[0].items.map((item) => item.label), ["Na, valence 1", "K, valence 1", "M, valence −1", "P"]);
  assert.match(panel.sections[0].items[0].lines.join(" | "), /^Push of the concentration difference: [\d.]+ mV into the cell \| Pull of the voltage \(−[\d.]+ mV\): [\d.]+ mV into the cell \| What is left: [\d.]+ mV into the cell$/);
  assert.match(panel.sections[0].items[2].lines.join(" | "), /Push of the concentration difference: [\d.]+ mV into the cell \| Pull of the voltage \(−[\d.]+ mV\): [\d.]+ mV out of the cell/);
  assert.match(panel.sections[0].items[3].detail, /Not drawn: this run did not save its concentration in the cell/);
  // The panel on what the layers show leaves the cell chosen, and says the rule and each of its inputs.
  lens.setSelection("layers:shown");
  assert.equal(lens.closeup?.cell, 40, "the close-up stays while the layers' panel is open");
  const shown = lens.describe("layers:shown");
  const push = shown.sections.find((section) => section.title === "Arrows: push and pull on ions");
  assert.match(push.items[1].lines.join(" "), /Worked out by the viewer from the saved membrane voltage and concentration of each ion in the cell, with the concentration of each ion outside, the temperature and each ion's valence as the run's definition gives them: the two terms of the engine's own electrochemical potential difference/);
  assert.match(push.items[1].lines.join(" "), /This run did not save the concentration of P in the cell: nothing is drawn for it\./);
  assert.match(push.items.at(-1).detail, /On a piece of the membrane of cell_40/);
  assert.deepEqual(shown.sections.map((section) => section.title), ["Colour: membrane voltage", "Height: membrane voltage", "Arrows: push and pull on ions", "cell_40: on its membrane at 19 min 30 s", "Not shown for this run"]);
  // The charge beside it: its own channel, so the two show together.
  await lens.setLayer("membrane-charge", true);
  assert.deepEqual([...lens.onMembrane.keys()], ["membrane-charge", "ion-push-pull"], "in the order of the channels: the signs on the membrane, then the arrows");
  const charge = lens.onMembrane.get("membrane-charge").mark;
  const voltage = lens.run.records.get("vm").at(step, cell);
  assert.deepEqual([charge.worth, charge.piece, charge.readings.marks], [1, { width_nm: 100, depth_nm: 25 }, Math.round((Math.abs(1.6e-11 * voltage) / ELEMENTARY / 320) * 0.0025)]);
  assert.deepEqual(lens.chrome().legend.layers.keys.map((item) => item.key), ["charges", "ions", "arrow-hollow", "arrow-faint", "arrow-solid", "none"]);
  assert.match(lens.chrome().legend.layers.keys[0].text, /^Each mark is one charge on a piece of membrane 100 nm by 25 nm\. Where a mark sits is illustration; so is the membrane's thickness$/);
  assert.match(lens.closeup.caption.text, /from the saved membrane voltage and ion concentrations, with the capacitance, area, composition outside, temperature and valences of the run's definition\.\nPlus and minus: each mark is one charge on a piece 100 nm by 25 nm\. Where a mark sits is illustration\.\nHollow arrow: /);
  // Another cell: the close-up is built anew for it. The time moves: the numbers are those of the new record.
  lens.setSelection("cell:7");
  assert.equal(lens.closeup.cell, 7);
  const before = lens.onMembrane.get("membrane-charge").mark.readings.voltage;
  lens.seek(0);
  assert.notEqual(lens.onMembrane.get("membrane-charge").mark.readings.voltage, before);
  assert.equal(lens.onMembrane.get("membrane-charge").mark.readings.voltage, lens.run.records.get("vm").at(0, 7));
  assert.match(lens.closeup.caption.text, /^Membrane of cell_7 at 0\.0 s\n/);
  // No cell chosen: the close-up goes. The layers stay on, waiting for a cell.
  lens.setSelection(null);
  assert.equal(lens.closeup, null);
  assert.equal(lens.onMembrane.size, 0);
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief", "membrane-charge", "ion-push-pull"]);
  assert.equal(lens.labels.shown.filter((label) => String(label.kind).startsWith("closeup")).length, 0, "its words go with it");
  // A cell chosen and the layers switched off: the close-up goes too.
  lens.setSelection("cell:7");
  assert.equal(lens.closeup.cell, 7);
  await lens.setLayer("ion-push-pull", false);
  assert.deepEqual([...lens.onMembrane.keys()], ["membrane-charge"]);
  await lens.setLayer("membrane-charge", false);
  assert.equal(lens.closeup, null);
  // A run that lists no membranes cannot feed them: switched on again, they are dropped when that run is shown.
  await lens.setLayer("membrane-charge", true);
  assert.equal(lens.closeup.cell, 7);
  await lens.show(second.entry.id);
  assert.equal(lens.closeup, null);
  assert.deepEqual(lens.chrome().legend.layers.cannot.map((item) => item.id), ["ion-push-pull", "membrane-charge", "ion-traffic"]);
});

test("at a record the run does not count as valid, nothing is drawn on the membrane and no number is given", async (t) => {
  const { lens, restore } = lensFor([syntheticRun({ membrane: true, invalidFrom: 1000 })]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  await lens.setLayers("ion-push-pull,membrane-charge");
  lens.setSelection("cell:12");
  lens.seek(500);
  assert.ok(lens.onMembrane.get("ion-push-pull").mark.readings.length === 3 && lens.onMembrane.get("membrane-charge").mark.readings.marks > 0);
  lens.seek(1200);
  assert.equal(lens.onMembrane.get("ion-push-pull").mark.readings, null);
  assert.equal(lens.onMembrane.get("membrane-charge").mark.readings, null);
  const numbers = lens.describe("cell:12").sections[0];
  assert.deepEqual(numbers.items.map((item) => item.label), ["Not a valid record"]);
  // Strength changes how a sign is drawn, never its numbers.
  lens.seek(500);
  const quiet = JSON.stringify([lens.onMembrane.get("ion-push-pull").mark.readings.map((term) => term.size), lens.onMembrane.get("membrane-charge").mark.readings.marks]);
  lens.setStrength("bold");
  assert.equal(JSON.stringify([lens.onMembrane.get("ion-push-pull").mark.readings.map((term) => term.size), lens.onMembrane.get("membrane-charge").mark.readings.marks]), quiet);
});

// ------------------------------------------------------------ beads: their place, before a run feeds them

test("beads have their place: a layer on the motion channel, declared and waiting for a run that saved the amounts carried", async (t) => {
  const traffic = layer("ion-traffic");
  assert.deepEqual({ mark: traffic.mark, channels: traffic.channels, quantity: traffic.quantity }, { mark: "beads", channels: ["motion"], quantity: { derivation: "rate", of: ["channel_transferred"] } });
  assert.deepEqual({ channels: MARKS.beads.channels, lives_on: MARKS.beads.lives_on, surface: MARKS.beads.surface, built: MARKS.beads.built }, { channels: ["motion"], lives_on: ["channel population", "pump population", "membrane"], surface: "membrane", built: false });
  assert.match(traffic.says, /A bead is a token of a rate, not an ion/);
  // A run that did not save what crossed its channels: said, as for any layer.
  const { run } = made({ membrane: true });
  assert.deepEqual([offer(run, "ion-traffic").ok, offer(run, "ion-traffic").why], [false, NOT_SAVED]);
  // A run that did: what the rule needs of the record is checked, and then the layer waits for its mark.
  const carried = (change) => {
    const { file, entry } = syntheticRun({ membrane: true });
    const source = file.view.records.find((record) => record.id === "generation");
    file.view.sets.push({ id: "channel", holds: "channel population", scale: "cell", ids: file.view.sets[0].ids.map((_, index) => `channel_${index}`), geometry: { kind: "on", set: "membrane", index: file.view.sets[0].ids.map((_, index) => index) } });
    const record = { ...source, id: "channel_transferred", label: "Carried through a channel population (made up)", unit: "fmol", set: "channel", axes: ["time", "channel"], kind: "cumulative", sign: { says: "a positive amount has left the channel's cell for its outside", from: "cell", to: "outside node", by: "made up with the rest" } };
    change(record);
    file.view.records.push(record);
    assert.deepEqual(validateReplay(file), []);
    return offer(openReplay(file, entry), "ion-traffic");
  };
  assert.deepEqual([carried(() => {}).ok, carried(() => {}).why], [false, "This run saved it. The viewer's beads are not built yet: they come with the first run that saved the amounts carried through channels and pumps."]);
  assert.equal(carried((record) => (record.kind = "level")).why, "This run saved it, but not as a total since the run's start: no rate can be worked out from it.");
  assert.equal(carried((record) => delete record.sign).why, "This run saved it, but does not say which way it is positive: a bead would have no way to go.");
  // In the page: named among the layers this run cannot feed, and not to be switched on.
  const { lens, restore } = lensFor([syntheticRun({ membrane: true })]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.deepEqual(lens.chrome().legend.layers.cannot.map((item) => [item.id, item.label, item.why]), [["ion-traffic", "Motion: ion traffic", NOT_SAVED]]);
  await lens.setLayer("ion-traffic", true);
  assert.ok(!lens.switch.on.includes("ion-traffic"));
  // The picture's time is a setting of the view: true speed as it opens.
  assert.equal(lens.slow, 1);
  lens.setSlow(1000);
  assert.equal(lens.slow, 1000);
});

test("a bead is a token of a rate: how many ions one stands for, how many pass a second, and what time the picture keeps", () => {
  assert.equal(PER_FMOL, 6.02214076e8);
  assert.equal(ionsASecond(0.03), 0.03 * 6.02214076e8);
  // The busiest stream of a run passes about ten beads a second: 18 million ions a second at true speed make a bead 2 million ions.
  assert.equal(BUSIEST, 10);
  assert.equal(tokenFor(1.8e7), 2_000_000);
  assert.equal(beadsASecond(1.8e7, 2_000_000), 9);
  // Slowed, a bead stands for fewer ions; slowed enough, a bead is an ion, and never less.
  assert.deepEqual([tokenFor(1.8e7, 1000), tokenFor(1.8e7, 1e6), tokenFor(1.8e7, 1e9), tokenFor(3, 1)], [2000, 2, 1, 1]);
  assert.equal(beadsASecond(1.8e7, 2000, 1000), 9, "the same stream passes as many beads a second at any slow-down");
  // The rate sets how many pass: a stream a tenth as busy passes a tenth as many, and a rate's sign changes nothing of the count.
  assert.equal(beadsASecond(-1.8e6, 2_000_000), 0.9);
  assert.equal(tokenFor(-1.8e7), 2_000_000);
  for (const busiest of [7, 950, 12_345, 4.4e9]) {
    const token = tokenFor(busiest), passing = beadsASecond(busiest, token);
    assert.ok(passing <= BUSIEST + 1e-9 && passing > BUSIEST / 2.5 - 1e-9, `${busiest} ions a second: ${passing} beads of ${token}`);
    assert.match(String(token), /^[125]0*$/, "a token is 1, 2 or 5 times a power of ten");
  }
  // What the legend says of the token and of the time.
  assert.equal(tokenWords(2_000_000), "One bead is 2,000,000 ions");
  assert.equal(tokenWords(1), "One bead is one ion");
  assert.equal(timeWords(1), "True speed: one second here is one second in the cell");
  assert.equal(timeWords(1000), "Slowed 1,000 times: one second here is one millisecond in the cell");
  assert.equal(timeWords(1e6), "Slowed 1,000,000 times: one second here is one microsecond in the cell");
  assert.equal(timeWords(250), "Slowed 250 times: one second here is 4 milliseconds in the cell");
  assert.deepEqual(MARKS.beads.keys(1.8e7, 1).map((item) => [item.key, item.text]), [
    ["bead", "One bead is 2,000,000 ions. More beads a second means more ions a second; how fast a bead travels stands for nothing"],
    ["time", "True speed: one second here is one second in the cell"],
  ]);
});
