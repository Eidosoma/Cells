// Quantity layers, checked without a browser (schema/QUANTITY_LAYERS.md): the four declared
// derivations, the declarations in data, which layers a run can feed and why not, the rule
// of one layer per channel, what the legend says of a layer, records in files of their own,
// and the marks' arithmetic. The colouring and the heights are held to the formula the
// replay used before layers, so that layer zero changes nothing.
//
//   node --test tests/layers.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { syntheticRun } from "./helpers/synthetic_replay.mjs";
import { openReplay, loadPart } from "../src/replay/source.js";
import { validateReplay } from "../src/replay/run.js";
import { Ramp } from "../src/replay/ramp.js";
import { display, rateDisplay, clock } from "../src/replay/format.js";
import { Player, SPEEDS, speedsFor } from "../src/replay/player.js";
import { Catalogue } from "../src/replay/catalogue.js";
import { difference, rate, charge, chargesIn, potentialTerms, DERIVATIONS, FARADAY, GAS, ELEMENTARY } from "../src/layers/derive.js";
import { declared, declaredOn, behind, family, constantOf, fromFirst, signedBy, cellsOf, restartsBetween, livesOn, LIVES_ON, KINDS } from "../src/layers/records.js";
import { layersFor, feeds, readDeclarations, validateLayer, account, partsOf, Switch, CHANNELS, LAYERS_FORMAT, NOT_SAVED } from "../src/layers/layers.js";
import { shareOf, roundUp } from "../src/layers/scale.js";
import { MARKS } from "../src/layers/marks/index.js";
import { heightOf, barStretch, riseOf, crossings, BOLD_RISE } from "../src/layers/marks/relief.js";
import { dropAt, fullDrop, FLOOR } from "../src/layers/marks/wedge.js";
import { arrowOutline, lanes, BALANCE } from "../src/layers/marks/arrows.js";
import { worthFor, marksFor, spots, MOST } from "../src/layers/marks/stipple.js";
import { tokenFor, beadsASecond, ionsASecond, timeWords, tokenWords, statementOf, meanRate, standing, advance, headSize, streamsOf, PER_FMOL, BUSIEST, CROSSING, MOST as MOST_BEADS, SLOWS } from "../src/layers/marks/beads.js";
import { lanesOf, busiestOf } from "../src/layers/marks/stream.js";
import { glowOf, elementsOf, brightestOf, FLOOR as GLOW_FLOOR } from "../src/layers/marks/glow.js";
import { amountDomain } from "../src/layers/marks/fog.js";
import { bordersOf, worldOf, endsOf } from "../src/layers/world.js";
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

// Runs as the page gets them: written by the run-fixture tool in the layout of the engine's shared output
// path and packaged by the run adapter. A small world with a secreted species (shaped as the engine's first
// real feed), in which the amounts add up and in which they do not; and the example sheet with invented numbers.
const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-layers-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const FIXTURES = path.join(scratch, "fixtures"), PACKAGED = path.join(scratch, "out");
for (const [tool, args] of [["make_run_fixture.py", ["--out", FIXTURES]], ["adapt_run.py", ["--evidence", FIXTURES, "--overlay", path.join(FIXTURES, "overlay.json"), "--selection", path.join(FIXTURES, "selection.json"), "--out", PACKAGED]]]) {
  const done = spawnSync("python3", [path.join(ROOT, "tools", tool), ...args], { encoding: "utf8" });
  assert.equal(done.status, 0, `${tool} failed:\n${done.stderr}`);
}
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const CATALOGUE = readJson(path.join(PACKAGED, "index.json"));
const WORLD = "synthetic-world--secreting", UNBALANCED = "synthetic-world--unbalanced", SHEET = "example-sheet--invented-numbers";
const VIEWED = "synthetic-world--viewed", RETIRING = "synthetic-world--retiring"; // the same world, packaged from a view in the engine's own shape
/** One packaged run as the lens's stand-ins serve it: { file, entry, parts }, the parts by their ids. */
const packaged = (id) => {
  const file = readJson(path.join(PACKAGED, `${id}.json`));
  return { file, entry: CATALOGUE.runs.find((row) => row.id === id), parts: Object.fromEntries((file.view.parts || []).map((part) => [part.id, readJson(path.join(PACKAGED, path.basename(part.file)))])) };
};
/** The same run opened, with every record of its parts read in. */
const opened = async (id) => {
  const { file, entry, parts } = packaged(id);
  const run = openReplay(file, entry);
  for (const part of Object.keys(parts)) await loadPart(run, part, { root: null, fetcher: fetcherOf(parts) });
  return run;
};
const near = (actual, expected, share = 1e-5) => Math.abs(actual - expected) <= Math.abs(expected) * share + 1e-30;
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
  assert.deepEqual(LAYERS.map((item) => item.id), ["voltage-tint", "voltage-relief", "junction-drops", "ion-push-pull", "membrane-charge", "transfers", "ion-traffic", "energy-glow", "signal-fog"]);
  // The layers of a chosen cell's membrane are drawn on its close-up, not on the sheet.
  assert.deepEqual(LAYERS.filter((item) => MARKS[item.mark].surface === "membrane").map((item) => [item.id, item.mark, item.channels[0], item.quantity.derivation]), [["ion-push-pull", "arrows", "arrows", "potential terms"], ["membrane-charge", "stipple", "surface", "charge"], ["ion-traffic", "beads", "motion", "rate"]]);
  // What flows and what glows on the sheet itself, and the species that colours it.
  assert.deepEqual(LAYERS.filter((item) => ["stream", "glow", "fog"].includes(item.mark)).map((item) => [item.id, item.mark, item.channels[0], item.quantity.derivation ?? "record"]), [["transfers", "stream", "motion", "rate"], ["energy-glow", "glow", "glow", "rate"], ["signal-fog", "fog", "colour", "record"]]);
  assert.deepEqual(LAYERS.filter((item) => item.opens).map((item) => item.id), ["signal-fog"], "one layer is on as a run opens, where the run can feed it");
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
  assert.match(behind({ owner: "a_model@1", representation: "modelled", sign: { says: "the first cell is at the higher potential" } }), /modelled in aggregate\. Positive means: the first cell is at the higher potential\. Declared by the run's own view\.$/);
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
  assert.match(behind({ owner: "a_law@1", representation: "simulated", sign: { says: "inside above outside" } }), /Positive means: inside above outside\. Declared by the run's own view\.$/);
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
  assert.deepEqual(offers.map((item) => [item.layer.id, item.ok]), [["voltage-tint", true], ["voltage-relief", true], ["junction-drops", true], ["ion-push-pull", false], ["membrane-charge", false], ["transfers", false], ["ion-traffic", false], ["energy-glow", false], ["signal-fog", false], ["generation-tint", true], ["generation-relief", true]]);
  for (const id of ["transfers", "ion-traffic", "energy-glow"]) assert.equal(offer(run, id).why, NOT_SAVED);
  assert.equal(offer(run, "signal-fog").why, "This run's files name no secreted species.");
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

function lensFor(runs, experiments = [{ id: "e07-v1", label: "A made-up experiment", records: { vm: { label: "Membrane voltage", shown_between: [-0.09, -0.01] } } }], { moving = false } = {}) {
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
    palette, invalidate() {}, scene: { add() {}, remove() {} }, sun: {}, rig: { setView() {}, limits: {}, instant: !moving, flyTo() {}, distance: 100, azimuth: 0, polar: 0.8 }, camera, width: 1400, height: 900, reducedMotion: !moving,
    // The stage's finishing pass for what flows, as agent K's stage offers it: what is marked to shine, how strongly, and the look's own motion held.
    shining: new Set(), bloom: 0, decoration: { holds: new Set(), pause(reason) { this.holds.add(reason); }, resume(reason) { this.holds.delete(reason); } },
    glow(object, on = true) { if (on) this.shining.add(object); else this.shining.delete(object); },
    setBloom(strength) { this.bloom = strength; },
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
  const index = { format: "cells.visualizer.replay_index@1", experiments, runs: runs.map((run) => run.entry) };
  const lens = new ReplayLens(stage, { raw: { replays: index } }, labels);
  lens.onChrome = () => lens.chrome();
  lens.onPanel = () => {};
  return { lens, asked, stage, shown, restore: () => Object.assign(globalThis, before) };
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
  assert.deepEqual(legend.layers.cannot.map((item) => item.id), ["ion-push-pull", "membrane-charge", "transfers", "ion-traffic", "energy-glow", "signal-fog"]);
  assert.deepEqual(legend.layers.keys, []);
  assert.deepEqual([legend.layers.time, legend.layers.example], [null, null], "nothing moves, and the run is no example");
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
  assert.deepEqual(panel.sections[3].items.map((item) => item.label), ["Arrows: push and pull on ions", "Membrane: membrane charge", "Motion: transfers", "Motion: ion traffic", "Glow: energy dissipated", "Colour: secreted species"]);
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
  assert.deepEqual(layers.cannot.map((item) => [item.id, item.label]), [["junction-drops", "Junctions: voltage drops"], ["ion-push-pull", "Arrows: push and pull on ions"], ["membrane-charge", "Membrane: membrane charge"], ["transfers", "Motion: transfers"], ["ion-traffic", "Motion: ion traffic"], ["energy-glow", "Glow: energy dissipated"], ["signal-fog", "Colour: secreted species"]]);
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
  assert.deepEqual(layersFor(run, LAYERS, MARKS).map((item) => item.layer.id), ["voltage-tint", "voltage-relief", "junction-drops", "ion-push-pull", "membrane-charge", "transfers", "ion-traffic", "energy-glow", "signal-fog", "generation-tint", "generation-relief"]);
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
  assert.deepEqual(lens.chrome().legend.layers.cannot.map((item) => item.id), ["ion-push-pull", "membrane-charge", "transfers", "ion-traffic", "energy-glow", "signal-fog"]);
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

// ------------------------------------------------------------ what flows: the arithmetic

test("a mean rate is the growth of a saved total between two records, and there is none at a run's first record", () => {
  const t = [0, 0.5, 1.5, 2];
  const record = { at: (step, entity) => [0, 0.2, 0.8, 0.8][step] * (entity + 1) };
  const run = { t, count: 4, isValid: (step) => step !== 3 };
  assert.equal(meanRate(run, record, 0, 0), null, "the first record has no record before it");
  assert.equal(meanRate(run, record, 0, 1), 0.4);
  assert.ok(near(meanRate(run, record, 1, 2), 1.2), "the times need not be evenly spaced");
  assert.equal(meanRate(run, record, 0, 3), null, "a record the run does not count as valid gives no rate");
  assert.equal(meanRate({ ...run, isValid: (step) => step !== 0 }, record, 0, 1), null, "nor does the record after one");
});

test("beads on a lane: as many set out a second as the rate says, each crosses in the same time, and where nothing may move they stand", () => {
  // Three beads a second for a second: three set out, none has arrived yet.
  const lane = { perSecond: 3, due: 0, beads: [] };
  for (let frame = 0; frame < 60; frame++) advance(lane, 1 / 60);
  assert.equal(lane.beads.length, 3);
  assert.ok(lane.beads.every((share) => share > 0 && share < 1));
  // After the time one takes to cross, the first is gone: about rate times crossing time are on their way, whatever the rate.
  for (let frame = 0; frame < 600; frame++) advance(lane, 1 / 60);
  assert.ok(Math.abs(lane.beads.length - 3 * CROSSING) <= 1, `${lane.beads.length} beads at 3 a second`);
  const slow = { perSecond: 0.5, due: 0, beads: [] };
  for (let frame = 0; frame < 6000; frame++) advance(slow, 1 / 60);
  assert.ok(slow.beads.length <= 1, "a bead every two seconds: at most one is crossing");
  // A bead's share of the way grows by the same amount each second, whatever the rate: the rate never sets its speed.
  const one = { perSecond: 0, due: 0, beads: [0.25] };
  advance(one, 0.4);
  assert.ok(near(one.beads[0], 0.25 + 0.4 / CROSSING));
  // With the rate at nought nothing sets out, and what is on its way arrives; then the lane is still.
  assert.equal(advance({ perSecond: 0, due: 0, beads: [0.99] }, 0.1), false);
  assert.equal(advance({ perSecond: 0, due: 0, beads: [] }, 0.1), false);
  // Never more than the most a lane holds, however long a frame.
  const burst = { perSecond: 1000, due: 0, beads: [] };
  for (let frame = 0; frame < 100; frame++) advance(burst, 0.01);
  assert.ok(burst.beads.length <= MOST_BEADS);
  // As many pass a second at two frames a second as at sixty: after the same four seconds the beads stand at the same places.
  const smooth = { perSecond: 3, due: 0, beads: [] }, coarse = { perSecond: 3, due: 0, beads: [] };
  for (let frame = 0; frame < 240; frame++) advance(smooth, 1 / 60);
  for (let frame = 0; frame < 8; frame++) advance(coarse, 0.5);
  assert.equal(coarse.beads.length, smooth.beads.length);
  assert.ok(coarse.beads.every((share, k) => Math.abs(share - smooth.beads[k]) < 1e-9), `${coarse.beads} at two frames a second, ${smooth.beads} at sixty`);
  // After a long gap the lane is as full as if it had been watched all along, and no fuller.
  const gap = { perSecond: 3, due: 0, beads: [0.5] };
  advance(gap, 600);
  assert.ok(Math.abs(gap.beads.length - 3 * CROSSING) <= 1 && gap.beads.every((share) => share >= 0 && share < 1));
  // Standing: evenly spaced, as many as would be crossing at one moment; none for a stream too thin for that, and none for nothing.
  assert.deepEqual(standing(0), []);
  assert.deepEqual(standing(0.01), [], "a bead every hundred seconds is almost never on its way: the lane's arrowhead alone stands for it");
  assert.deepEqual(standing(0.4), [0.5], "one from about a third of a bead at a time");
  assert.equal(standing(5).length, Math.round(5 * CROSSING));
  assert.deepEqual(standing(2).map((share) => Number(share.toFixed(4))), [0.1667, 0.5, 0.8333]);
  assert.equal(standing(1e6).length, MOST_BEADS);
  // A lane's arrowhead is full where a bead or more is on its way at one moment, and smaller for a thinner stream, never under two fifths.
  assert.deepEqual([headSize(5), headSize(1 / CROSSING), headSize(0.01), headSize(0)], [1, 1, 0.4, 0.4]);
  assert.ok(near(headSize(0.3), Math.sqrt(0.3 * CROSSING)));
});

test("the picture's own statement of a motion layer, and the units small amounts, rates and powers read in", () => {
  const at = (seconds) => clock(seconds, { precise: true });
  // A time of a few seconds keeps its tenth, as the timeline of a four-second run needs; a whole one and a longer one read as before.
  assert.deepEqual([clock(0.4), clock(4), clock(0), clock(9.96), clock(13.785), clock(59.4)], ["0.4 s", "4 s", "0 s", "10 s", "14 s", "59 s"]);
  assert.equal(statementOf({ token: 10_000, what: "molecule", slow: 1, interval: [1, 2], clock: at }), "One bead is 10,000 molecules · true speed · mean of 1.0 s to 2.0 s");
  assert.equal(statementOf({ token: 1, what: "ion", slow: 1e6, interval: null, clock: at }), "One bead is one ion · slowed 1,000,000 times · no rate at the run's first record");
  assert.equal(tokenWords(50_000, "molecule"), "One bead is 50,000 molecules");
  assert.equal(tokenWords(2, "ion or molecule"), "One bead is 2 ions or molecules");
  assert.deepEqual(SLOWS, [1, 1e3, 1e6]);
  // An amount far under a femtomole reads in attomoles; one of ordinary size stays as saved.
  assert.deepEqual(display({ unit: "fmol", range: [0.001, 0.001048], dtype: "float32" }), { unit: "amol", factor: 1e3, decimals: 3 });
  assert.deepEqual(display({ unit: "fmol", range: [5, 145], dtype: "float32" }), { unit: "fmol", factor: 1, decimals: 3 });
  assert.deepEqual(display({ unit: "fmol", range: [0, 0], dtype: "float32" }), { unit: "fmol", factor: 1, decimals: 3 });
  assert.deepEqual(display({ unit: "pJ", range: [0, 0.016], dtype: "float32" }), { unit: "fJ", factor: 1e3, decimals: 3 });
  assert.deepEqual(display({ unit: "V", range: [-0.08, -0.02], dtype: "float32" }), { unit: "mV", factor: 1000, decimals: 1 });
  // A rate has a unit of its own: an energy a second is a power.
  assert.deepEqual(rateDisplay("pJ", 0.004), { unit: "fW", factor: 1e3 });
  assert.deepEqual(rateDisplay("pJ", 2), { unit: "pW", factor: 1 });
  assert.deepEqual(rateDisplay("fmol", 9e-5), { unit: "zmol a second", factor: 1e6 });
  assert.deepEqual(rateDisplay("fmol", 0.0149), { unit: "amol a second", factor: 1e3 });
  assert.deepEqual(rateDisplay("mM", 3), { unit: "mM a second", factor: 1 });
  // An amount's scale starts at nought and ends on a round number at or above the most any place holds.
  const domain = amountDomain("fmol", 0.001048);
  assert.deepEqual([domain.shown.unit, domain.low, Number((domain.high * 1e3).toFixed(6))], ["amol", 0, 1.2]);
  // A glow: nothing under the floor, then from the faintest to the full, a little stronger in bold; never more than the full.
  assert.equal(glowOf(0.01 * 4, 4), 0);
  assert.ok(near(glowOf(GLOW_FLOOR * 4, 4), 0.22 + 0.6 * GLOW_FLOOR));
  assert.ok(near(glowOf(4, 4), 0.82) && near(glowOf(40, 4), 0.82) && near(glowOf(2, 4, "bold"), 0.32 + 0.33));
  assert.equal(glowOf(-1, 4), 0, "a ledger that only grows gives no negative power; were one given, nothing would glow");
});

test("a short run plays at true speed, a long one as before; and the catalogue names an example as one, after the experiments and the development runs", () => {
  assert.deepEqual([speedsFor(4), speedsFor(119), speedsFor(120), speedsFor(2340)], [[0.25, 1, 4], [0.25, 1, 4], [15, 60, 240], [15, 60, 240]]);
  const player = new Player();
  player.load({ start: 0, end: 4, t: Float32Array.of(0, 4), count: 2, indexAt: () => 0 });
  assert.deepEqual([player.speed, [...SPEEDS]], [1, [0.25, 1, 4]], "a second of watching is a second of the run");
  player.setSpeed(0.25);
  player.load({ start: 0, end: 12, t: Float32Array.of(0, 12), count: 2, indexAt: () => 0 });
  assert.equal(player.speed, 0.25, "a speed chosen is kept while the next run offers it");
  player.load({ start: 0, end: 2340, t: Float32Array.of(0, 2340), count: 2, indexAt: () => 0 });
  assert.deepEqual([player.speed, [...SPEEDS]], [60, [15, 60, 240]]);
  const catalogue = new Catalogue(CATALOGUE);
  assert.deepEqual(catalogue.sections().map((section) => section.label), [
    "Synthetic sheet (test fixture)", "Synthetic pre-screen arms (test fixture)", "Synthetic pilot (test fixture)",
    "Development run: Synthetic development run (test fixture)", "Development run: Synthetic small world (test fixture)", "Example: Example sheet (invented numbers)",
  ].map((label, k) => (k < 3 ? catalogue.sections()[k].label : label)));
  assert.deepEqual(catalogue.sections().map((section) => section.label).filter((label) => /^(Development run|Example): /.test(label)).map((label) => label.split(":")[0]), ["Development run", "Development run", "Example"]);
});

// ------------------------------------------------------------ where things stand: tiles and their borders

test("two tiles that share an edge have a border, and an entity of the run stands on the border between its two places", async () => {
  // Three hexagons round one corner, as the small world is laid out: every two share an edge.
  const world = await opened(WORLD);
  const cells = world.sets.get("cell"), outside = world.sets.get("outside");
  const tile = (set, index, geometry) => {
    const ring = geometry.faces[index].map((vertex) => geometry.vertices[vertex]);
    return { set, index, face: geometry.faces[index], ring, centre: [ring.reduce((sum, [x]) => sum + x, 0) / ring.length, ring.reduce((sum, [, y]) => sum + y, 0) / ring.length] };
  };
  const tiles = [tile("cell", 0, cells.geometry), tile("outside", 0, outside.geometry), tile("outside", 1, outside.geometry)];
  const borders = bordersOf(tiles);
  assert.equal(borders.length, 3);
  for (const border of borders) {
    assert.ok(near(Math.hypot(...border.along), 1) && near(Math.hypot(...border.across), 1));
    assert.ok(Math.abs(border.along[0] * border.across[0] + border.along[1] * border.across[1]) < 1e-3, "the way across is square to the edge, for regular tiles");
    assert.ok(near(border.length, Math.hypot(border.points[1][0] - border.points[0][0], border.points[1][1] - border.points[0][1])));
  }
  const places = worldOf(world, tiles);
  const name = (side) => `${side.set}:${side.index}`;
  const where = (set, index) => {
    const place = places.placeOf(set, index);
    return place?.border ? [name(place.border[place.first]), name(place.border[place.first === "a" ? "b" : "a"]), place.cell] : [null, null, place?.cell ?? null];
  };
  // The face from the space to the bath; each membrane from the cell to the outside it faces; a route where its membrane is.
  assert.deepEqual(where("face", 0), ["outside:1", "outside:0", null], "a face's first end is its sender");
  assert.deepEqual(where("membrane", 0), ["cell:0", "outside:0", 0]);
  assert.deepEqual(where("membrane", 1), ["cell:0", "outside:1", 0]);
  assert.deepEqual([where("route", 0), where("route", 1)], [["cell:0", "outside:1", 0], ["cell:0", "outside:1", 0]]);
  assert.deepEqual(endsOf(world, "face", 0), { first: "ecs_0", second: "bath" });
  assert.deepEqual(endsOf(world, "route", 0), { first: "cell_0", second: "ecs_0" });
  assert.equal(places.placeOf("species", 0), null, "a set that joins nothing has no place");
  // A sheet whose baths have no tiles: a junction stands on the border between its two cells, a membrane only on its cell.
  const sheet = await opened(SHEET);
  const sheetCells = sheet.sets.get("cell");
  const sheetPlaces = worldOf(sheet, sheetCells.ids.map((_, index) => tile("cell", index, sheetCells.geometry)));
  assert.equal(sheetPlaces.borders.length, 42, "one border for each pair of neighbours");
  const ends = sheet.sets.get("junction").geometry.ends;
  for (const junction of [0, 7, 41]) {
    const place = sheetPlaces.placeOf("junction", junction);
    assert.deepEqual([place.border[place.first].index, place.border[place.first === "a" ? "b" : "a"].index], ends[junction]);
  }
  assert.deepEqual(sheetPlaces.placeOf("membrane", 5), { border: null, first: null, cell: 5 });
  assert.deepEqual(sheetPlaces.placeOf("channel", 11), { border: null, first: null, cell: 5 }, "the sixth cell's second channel population");
});

// ------------------------------------------------------------ what a run with a secreted species feeds

test("a rate may be worked out from every one of several saved totals, each species' own; a layer may ask for the run's secreted species", async () => {
  const run = await opened(WORLD);
  const fog = offer(run, "signal-fog"), transfers = offer(run, "transfers"), glow = offer(run, "energy-glow");
  assert.deepEqual([fog.ok, transfers.ok, glow.ok, offer(run, "ion-traffic").ok], [true, true, true, false]);
  assert.equal(offer(run, "ion-traffic").why, NOT_SAVED, "this world has no channel populations");
  // The fog reads the secreted species' amount in the cell, and with it the amount outside and the run's ledgers of the same species.
  assert.deepEqual([fog.source.id, fog.species, fog.source.lives_on], ["amount.S", "S", "cell"]);
  assert.deepEqual(fog.extras.map((extra) => [extra.role, extra.record]), [["outside", "extracellular_amount.S"], ["made", "turnover_produced_fmol.S"], ["cleared", "turnover_cleared_fmol.S"], ["cleared outside", "turnover_outside_cleared_fmol.S"]]);
  // The transfers: every species' total across the face and the membranes, and the routes' one.
  assert.deepEqual(transfers.sources.map((record) => record.id), ["face_transferred.Na", "face_transferred.K", "face_transferred.Cl", "face_transferred.S", "membrane_transferred.Na", "membrane_transferred.K", "membrane_transferred.Cl", "membrane_transferred.S", "exchange_moved_fmol"]);
  assert.ok(transfers.sources.every((record) => record.kind === "cumulative" && record.sign));
  assert.deepEqual(glow.sources.map((record) => [record.id, record.never_falls]), [["face_dissipated_energy_pJ", true], ["membrane_dissipated_energy_pJ", true]]);
  assert.deepEqual(glow.extras.map((extra) => extra.role), ["pump"]);
  assert.deepEqual(glow.lacking.map((item) => item.record), ["channel_dissipated_energy_pJ"]);
  // What stands behind them: the rule once, each field once, and for the routes the reading that gave their direction.
  const said = account(run, layer("transfers"), transfers);
  assert.equal(said.derived, true);
  assert.match(said.numbers[0], /^Worked out by the viewer from the saved totals \(carried across a face; carried across the membrane; moved by an exchange route\): the saved total at one record less the total at the record before, divided by the time between\. A mean over that interval\.$/);
  assert.equal(said.numbers.length, 4);
  assert.match(said.numbers[1], /^Carried across a face: saved by the run; computed by resolved_pump_tissue@3\. .*Positive means: a positive amount has left the sender for the receiver\. That is the engine's own convention for this family of models, confirmed by the owner of its core on 15 November 2026 and not yet declared in the run's view\.$/);
  assert.match(said.numbers[3], /^Moved by an exchange route: saved by the run; computed by scheduled_species_exchange@1\..*That is the engine's own convention for this operator, confirmed by the engine's lead on 15 November 2026 and not yet declared in the run's view\. The run's own saved amounts agree with it: at every record/);
  // Where the amounts do not add up the routes' total has no declared direction: it is left out, and the rest is fed as before.
  const loose = await opened(UNBALANCED);
  assert.deepEqual(offer(loose, "transfers").sources.map((record) => record.id).filter((id) => !id.includes(".")), []);
  assert.equal(offer(loose, "transfers").ok, true);
  // A total that is not said to grow only is no ledger for the glow; one with no sign has no way for a bead to go.
  const file = packaged(WORLD).file;
  for (const record of file.view.records) if (/dissipated/.test(record.id)) delete record.monotone;
  for (const record of file.view.records) if (/transferred|exchange/.test(record.id)) delete record.sign;
  const bare = openReplay(file, packaged(WORLD).entry);
  assert.deepEqual([offer(bare, "energy-glow").ok, offer(bare, "energy-glow").why], [false, "This run saved it, but does not say that it only ever grows: a rate worked out from it could be negative."]);
  assert.deepEqual([offer(bare, "transfers").ok, offer(bare, "transfers").why], [false, "This run saved it, but does not say which way it is positive: a bead would have no way to go."]);
  // Only a rate may be worked out from several records at once.
  assert.match(validateLayer({ ...layer("transfers"), quantity: { derivation: "difference", any_of: ["a", "b"] } }, MARKS).join("; "), /only a rate may be worked out from every one of several records/);
});

// ------------------------------------------------------------ the small world in the lens: one cell, its surroundings, a species that leaves and is cleared

test("a run with a secreted species opens coloured by it: the cell and each space outside on one scale, the spaces as flat tiles with their names", async (t) => {
  const { lens, asked, restore } = lensFor([packaged(WORLD)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.deepEqual(lens.switch.on, ["signal-fog"], "the colour is the secreted species; nothing holds the height");
  assert.ok(asked.includes(`${WORLD}.amount.json`) && asked.includes(`${WORLD}.extracellular-amount.json`), "its records were fetched as the run opened");
  assert.ok(!asked.some((name) => /transferred|dissipated/.test(name)), "and no other layer's");
  // The spaces outside: flat tiles of their own, beside the one prism.
  const outside = lens.surface.outside;
  assert.deepEqual([lens.sheet.cells.length, outside.tiles.length, outside.tiles.map((tile) => tile.held)], [1, 2, [true, false]]);
  assert.ok(outside.level < lens.low / 4, "a tile lies on the ground; the cell stands above it");
  assert.equal(lens.surface.world.borders.length, 3);
  assert.ok(lens.sheet.cells[0].height >= lens.low - 1e-9 && lens.sheet.cells[0].height <= lens.low + 1e-9, "the sheet is flat");
  // One scale for all three places, from nought, in attomoles.
  const legend = lens.chrome().legend;
  assert.deepEqual([legend.scale.label, legend.scale.unit, legend.scale.ticks.map((tick) => tick.text)], ["Amount of S", "amol", ["0.0", "0.6", "1.2"]]);
  assert.equal(legend.note.text, "The sheet is flat: no layer is on its height. Every step is a saved record.");
  assert.deepEqual(legend.layers.keys.map((item) => item.key), ["tile", "tile-held", "amount"]);
  assert.match(legend.layers.keys[0].text, /^A flat tile is a space outside the cells, coloured on the same scale by the amount in it\. Where it stands is the viewer's choice/);
  assert.deepEqual(rowsOf(lens), ["Colour: Off | Amount of S* | Cell potential", "Height: Off* | Cell potential", "Motion: Off* | Transfers", "Glow: Off* | Energy dissipated"]);
  assert.deepEqual(legend.layers.cannot.map((item) => item.id), ["voltage-tint", "voltage-relief", "junction-drops", "ion-push-pull", "membrane-charge", "ion-traffic"]);
  assert.equal(legend.layers.example, null, "a development run is no example");
  // The colours: the cell near the top of the ramp, the space beside it about half-way, the held bath at nought.
  lens.seek(4);
  const fog = lens.drawn.get("signal-fog").mark;
  const ramp = new Ramp(PALETTE), linear = new THREE.Color();
  const expected = (amount) => {
    const rgb = ramp.at(amount / 1.2e-3);
    linear.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
    return [linear.r, linear.g, linear.b];
  };
  const tone = (array, vertex) => Array.from(array.slice(vertex * 3, vertex * 3 + 3));
  const closeTo = (actual, wanted) => actual.every((value, k) => Math.abs(value - wanted[k]) < 2e-3);
  assert.ok(closeTo(tone(lens.surface.geometry.attributes.color.array, lens.sheet.cells[0].start), expected(0.001048)), "the cell: 0.001 fmol and what was made less what left");
  const tiles = outside.geometry.attributes.color.array;
  assert.ok(closeTo(tone(tiles, outside.tiles[0].start), expected(1e-9)), "the bath");
  assert.ok(closeTo(tone(tiles, outside.tiles[1].start), expected(0.000532)), "the space beside the cell");
  // Their names stand on the tiles with the amounts; the cell's tag reads in the same unit.
  const texts = lens.labels.shown.map((label) => label.text);
  assert.ok(texts.includes("bath (held bath) · 0.000 amol") && texts.includes("ecs_0 · 0.532 amol"), texts.join(" | "));
  lens.setSelection("cell:0");
  assert.ok(lens.labels.shown.some((label) => label.text === "cell_0 · 1.048 amol"), lens.labels.shown.map((label) => label.text).join(" | "));
  // The cell's panel: what the run's ledgers say of it at the record shown.
  const totals = lens.describe("cell:0").sections.find((section) => /^Totals of S at/.test(section.title));
  assert.deepEqual(totals.items.map((item) => [item.label, item.detail]), [["Made here since the start", "0.400 amol"], ["Cleared here since the start", "0.000 amol"]]);
  assert.equal(fog.ledger(4, "outside", 1, (value, decimals) => value.toFixed(decimals))[0].text, "0.080 amol", "cleared in the space beside the cell: 2e-5 fmol a second for four seconds");
  // Switched off, the tiles wear the tone of no value; the card's colouring takes the cell.
  await lens.setLayer("signal-fog", false);
  assert.ok(closeTo(tone(outside.geometry.attributes.color.array, outside.tiles[1].start), (() => { linear.setRGB(...lens.neutral, THREE.SRGBColorSpace); return [linear.r, linear.g, linear.b]; })()));
  assert.ok(lens.labels.shown.some((label) => label.text === "ecs_0"), "and the tile keeps its name");
});

test("beads cross the borders of the small world as its saved totals grew: how many, which way, and what the picture says of them", async (t) => {
  const { lens, restore } = lensFor([packaged(WORLD)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  await lens.setLayer("transfers", true);
  assert.deepEqual(lens.switch.on, ["signal-fog", "transfers"]);
  const mark = lens.drawn.get("transfers").mark;
  // Three lanes: the species across the face, and the two routes on the contact membrane. Nothing else ever changes.
  assert.deepEqual(mark.lanes.map((lane) => [lane.name, lane.species, lane.record.id]), [["face_0", "S", "face_transferred.S"], ["secrete", "S", "exchange_moved_fmol"], ["sink", "S", "exchange_moved_fmol"]]);
  assert.deepEqual([mark.unplaced.length, mark.undirected.length, mark.what], [0, 0, "molecule"]);
  // The busiest is the export route, 9e-5 fmol a second: 54,199 molecules a second, so a bead is 10,000.
  assert.ok(near(mark.busiest, 9e-5));
  assert.equal(mark.token, 10_000);
  // At the first record there is no rate, and the picture says so.
  assert.equal(lens.player.index, 0);
  assert.ok(mark.lanes.every((lane) => lane.mean === null && lane.beads.length === 0));
  const flow = () => lens.labels.shown.find((label) => /^One bead is/.test(label.text || ""));
  assert.equal(flow().text, "One bead is 10,000 molecules · true speed, shown still · no rate at the run's first record");
  // At 2 s: the mean of 1 s to 2 s. Each lane's rate, its way, and its beads a second.
  lens.seek(2);
  assert.equal(flow().text, "One bead is 10,000 molecules · true speed, shown still · mean of 1.0 s to 2.0 s");
  const readings = Object.fromEntries(mark.readings().map((reading) => [reading.name, reading]));
  assert.ok(near(readings.face_0.mean, 6e-5) && near(readings.secrete.mean, 9e-5) && near(readings.sink.mean, -2e-6));
  assert.deepEqual([readings.face_0.from, readings.face_0.to], ["ecs_0", "bath"], "a positive face transfer leaves the sender for the receiver");
  assert.deepEqual([readings.secrete.from, readings.secrete.to], ["cell_0", "ecs_0"], "a route's positive total has left the cell");
  assert.deepEqual([readings.sink.from, readings.sink.to], ["ecs_0", "cell_0"], "the import's total fell: its beads go into the cell");
  assert.ok(near(readings.face_0.particles, 6e-5 * PER_FMOL) && near(readings.face_0.beads, (6e-5 * PER_FMOL) / 10_000) && near(readings.secrete.beads, 5.41993, 1e-4) && near(readings.sink.beads, 0.120443, 1e-4));
  assert.ok(near(readings.face_0.before, 6e-5) && near(readings.face_0.now, 12e-5) && readings.face_0.seconds === 1);
  // Nothing may move here (the stand-in visitor asks for less motion): the beads stand, as many as would be crossing.
  const count = (name) => mark.lanes.find((lane) => lane.name === name).beads.length;
  assert.deepEqual([count("face_0"), count("secrete"), count("sink")], [Math.round(3.61328 * CROSSING), Math.round(5.41993 * CROSSING), 0]);
  // Each lane that carries something ends in an arrowhead that points its beads' way: the thin import shows that alone.
  assert.deepEqual(mark.drawn, { beads: 6 + 9, heads: 3 });
  assert.equal(mark.tick(16), false, "and no frame is asked for");
  // The legend: the token, the time, by whose word a bead goes its way, and the slow-down beside the true speed.
  const layers = lens.chrome().legend.layers;
  assert.deepEqual(layers.keys.map((item) => item.key), ["tile", "tile-held", "amount", "ions", "bead", "time", "way", "way", "head"]);
  assert.deepEqual([layers.keys[3].chips.map((chip) => chip.label), layers.keys[3].text], [["S"], "The colour of the species that crosses"]);
  assert.equal(layers.keys[4].text, "One bead is 10,000 molecules. More beads a second means more molecules a second; how fast a bead travels stands for nothing");
  assert.equal(layers.keys[5].text, "True speed: one second here is one second in the cell. Shown still here: the beads stand, as many as would be on their way at one moment");
  assert.match(layers.keys[6].text, /^A bead goes the way its total grew: a positive amount has left the sender for the receiver\. That is the engine's own convention for this family of models, confirmed by the owner of its core on 15 November 2026 and not yet declared in the run's view$/);
  assert.match(layers.keys[7].text, /^A bead goes the way its total grew: a positive amount has left the route's cell for the outside its membrane faces\. That is the engine's own convention for this operator, confirmed by the engine's lead on 15 November 2026 and not yet declared in the run's view$/);
  assert.equal(layers.keys[8].text, "An arrowhead ends each lane that carries something, and points the way its beads go. A small arrowhead alone: a lane that passes a bead only now and then");
  assert.deepEqual(layers.time, { label: "Speed", options: [{ id: 1, label: "True", title: "True speed: one second here is one second in the cell", on: true }, { id: 1000, label: "1/1,000", title: "Slowed 1,000 times: one second here is one millisecond in the cell", on: false }, { id: 1e6, label: "1/1,000,000", title: "Slowed 1,000,000 times: one second here is one microsecond in the cell", on: false }] });
  // Slowed a thousand times a bead stands for a thousandth as many, and as many pass as before.
  lens.setSlow(1000);
  assert.equal(mark.token, 10);
  assert.ok(near(mark.readings()[1].beads, 5.41993, 1e-4));
  assert.equal(flow().text, "One bead is 10 molecules · slowed 1,000 times, shown still · mean of 1.0 s to 2.0 s");
  assert.equal(lens.chrome().legend.layers.keys[5].text, "Slowed 1,000 times: one second here is one millisecond in the cell. Shown still here: the beads stand, as many as would be on their way at one moment");
  lens.setSlow(1e6);
  assert.equal(mark.token, 1, "slowed a million times a bead is a molecule, and never less");
  assert.ok(near(mark.readings()[1].beads, (9e-5 * PER_FMOL) / 1e6, 1e-4), "0.054 beads a second");
  lens.setSlow(1);
  // The panel: the numbers behind each lane, enough to check by hand.
  const panel = lens.describe("layers:shown");
  const section = panel.sections.find((item) => /^Transfers, a mean from 1\.0 s to 2\.0 s$/.test(item.title));
  assert.deepEqual(section.items.map((item) => item.label), ["face_0 · S", "secrete · S", "sink · S"]);
  assert.equal(section.items[0].detail, "0.060 amol a second from ecs_0 to bath", "in the unit of its two totals, so that the three check against each other");
  assert.deepEqual(section.items[0].lines, ["0.0600 amol at 1.0 s, 0.1200 amol at 2.0 s: the difference over 1.000 s", "36,133 molecules a second; one bead is 10,000, so 3.61 beads a second pass"]);
  assert.equal(section.items[2].detail, "2.000 zmol a second from ecs_0 to cell_0");
  assert.match(section.note, /the saved total at one record less the total at the record before, divided by the time between/);
  // Where the amounts do not add up, the routes have no declared way: only the face is drawn.
  const loose = lensFor([packaged(UNBALANCED)], CATALOGUE.experiments);
  t.after(loose.restore);
  await loose.lens.ready;
  loose.lens.activate();
  await loose.lens.setLayer("transfers", true);
  assert.deepEqual(loose.lens.drawn.get("transfers").mark.lanes.map((lane) => lane.name), ["face_0"]);
});

test("a glow where energy is dissipated: the mean power of each ledger between two records, on a stated scale", async (t) => {
  const { lens, stage, restore } = lensFor([packaged(WORLD)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  await lens.setLayer("energy-glow", true);
  const mark = lens.drawn.get("energy-glow").mark;
  // Only the face's ledger ever grows: one band, on the border between the two spaces outside.
  assert.deepEqual(mark.elements.map((element) => [element.name, element.kind, element.record.id]), [["face_0", "band", "face_dissipated_energy_pJ"]]);
  assert.ok(near(mark.full, 0.004, 1e-5), "0.004 pJ a second is 4 fW, and the scale ends there");
  assert.deepEqual(mark.shown, { unit: "fW", factor: 1e3 });
  lens.seek(0);
  assert.deepEqual(mark.readings().map((reading) => [reading.mean, reading.glow]), [[null, 0]], "nothing glows at the first record");
  lens.seek(3);
  const [reading] = mark.readings();
  assert.ok(near(reading.mean, 0.004) && near(reading.share, 1) && near(reading.glow, 0.82));
  assert.ok(near(reading.before, 0.008) && near(reading.now, 0.012) && reading.seconds === 1);
  // The band's middle shows the glow in full, its edges none; it wears one hue.
  const alpha = Array.from({ length: 12 }, (_, vertex) => lens.surface.root.children.at(-1).geometry.attributes.color.array[vertex * 4 + 3]);
  assert.ok(near(Math.max(...alpha), 0.82, 1e-4) && Math.min(...alpha) === 0);
  const key = lens.chrome().legend.layers.keys.find((item) => item.key === "glow");
  assert.equal(key.text, "A glow where energy is dissipated: the brighter, the more a second. The brightest stands for 4.0 fW; under 0.08 fW nothing glows. A magnitude, not a temperature");
  const section = lens.describe("layers:shown").sections.find((item) => /^Energy dissipated, a mean from 2\.0 s to 3\.0 s$/.test(item.title));
  assert.deepEqual(section.items.map((item) => [item.label, item.detail, item.lines]), [["face_0 · energy dissipated across a face", "4.000 fW", ["8.0000 fJ at 2.0 s, 12.0000 fJ at 3.0 s: the difference over 1.000 s", "100 in a hundred of the brightest glow"]]]);
  // What flows may shine where the stage has a finishing pass: the glow is marked, bloom is asked for, and both are let go with the layer.
  assert.deepEqual([stage.shining.size, stage.bloom], [1, 0.6]);
  lens.setStrength("bold");
  assert.equal(stage.bloom, 1);
  await lens.setLayer("energy-glow", false);
  assert.deepEqual([stage.shining.size, stage.bloom], [0, 0]);
  // A ledger that lives on a route says what its value is.
  const run = await opened(WORLD);
  const surface = { root: new THREE.Group(), cells: lens.surface.cells, pitch: lens.surface.pitch, outside: lens.surface.outside, world: lens.surface.world };
  const routed = MARKS.glow.create({ surface, run, fed: { sources: [{ ...declared(run, "face_dissipated_energy_pJ"), lives_on: "route" }], extras: [] }, colours: colours() });
  assert.deepEqual(routed.keys((value, decimals) => value.toFixed(decimals)).map((item) => item.key), ["glow", "glow-route"]);
  assert.match(routed.keys((value, decimals) => value.toFixed(decimals))[1].text, /^A value for a route is an exact attribution of its row's fall in free energy between the routes that move it\. It cannot be measured apart$/);
  routed.dispose();
});

test("a lens that is not shown leaves the stage alone: it asks for no bloom, switches none off, and holds no motion still", async (t) => {
  const { lens, stage, restore } = lensFor([packaged(WORLD)], CATALOGUE.experiments, { moving: true });
  t.after(restore);
  stage.bloom = 0.7; // another lens has it on
  stage.decoration.pause("another lens");
  await lens.ready;
  await lens.setLayers("transfers,energy-glow");
  assert.deepEqual([stage.bloom, stage.shining.size, [...stage.decoration.holds]], [0.7, 0, ["another lens"]], "its layers are on, but it is not the lens shown");
  // Shown, it marks what shines and asks for bloom; left again, it gives back what it took and nothing more.
  lens.activate();
  lens.player.pause();
  assert.deepEqual([stage.bloom, stage.shining.size, [...stage.decoration.holds].sort()], [0.6, 2, ["another lens", "layers"]]);
  lens.deactivate();
  assert.deepEqual([stage.bloom, stage.shining.size, [...stage.decoration.holds]], [0, 0, ["another lens"]]);
  stage.bloom = 0.4;
  await lens.setLayer("energy-glow", false);
  assert.equal(stage.bloom, 0.4, "it switches off only the bloom it switched on");
});

test("where things may move, beads set out and cross, the look's own motion stands still meanwhile, and the lens asks for frames", async (t) => {
  const { lens, stage, restore } = lensFor([packaged(WORLD)], CATALOGUE.experiments, { moving: true });
  t.after(restore);
  await lens.ready;
  lens.activate();
  lens.player.pause();
  await lens.setLayer("transfers", true);
  assert.ok(stage.decoration.holds.has("layers"), "decoration stops while a layer on the motion channel shows (rule 12)");
  assert.equal(lens.labels.shown.find((label) => /^One bead is/.test(label.text || ""))?.text, "One bead is 10,000 molecules · true speed · no rate at the run's first record", "where things may move, nothing is called still");
  assert.equal(lens.chrome().legend.layers.keys.find((item) => item.key === "time").text, "True speed: one second here is one second in the cell");
  assert.equal(stage.shining.size, 1, "the beads are marked to shine");
  lens.seek(2);
  const mark = lens.drawn.get("transfers").mark;
  assert.ok(mark.lanes.every((lane) => lane.beads.length === 0), "a paused moment starts with no bead on its way");
  // Two seconds of frames: the export route passes about 5.4 beads a second, each 1.6 s on its way.
  let asks = 0;
  for (let frame = 0; frame < 120; frame++) asks += lens.update(1000 / 60) ? 1 : 0;
  assert.equal(asks, 120, "every frame asks for the next while beads pass");
  const secrete = mark.lanes.find((lane) => lane.name === "secrete");
  assert.ok(Math.abs(secrete.beads.length - 5.41993 * CROSSING) <= 1.5, `${secrete.beads.length} beads on the export route`);
  assert.ok(secrete.beads.every((share, k) => k === 0 || share < secrete.beads[k - 1]), "in the order they set out");
  // Back at the first record nothing sets out; what was on its way is gone at once, since the lane has no rate.
  lens.seek(0);
  assert.ok(mark.lanes.every((lane) => lane.beads.length === 0));
  assert.equal(lens.update(1000 / 60), false);
  await lens.setLayer("transfers", false);
  assert.ok(!stage.decoration.holds.has("layers"));
  assert.equal(stage.shining.size, 0);
});

// ------------------------------------------------------------ a run packaged from the engine's own view

test("the engine's own words are read as written: what a set holds, which end a sign names, whose word it is", async () => {
  const run = await opened(VIEWED);
  // A membrane patch is a membrane, an exchange route a route.
  assert.deepEqual([livesOn(run, "membrane"), livesOn(run, "exchange_route"), livesOn(run, "outside"), livesOn(run, "face")], ["membrane", "route", "outside node", "face"]);
  // A positive value goes from a link's sender, or from a membrane's inside: the view's roles and the older words alike.
  assert.deepEqual(["sender", "inside", "first", "cell"].map((from) => fromFirst({ from })), [true, true, true, true]);
  assert.deepEqual(["receiver", "outside", "second", "outside node"].map((from) => fromFirst({ from })), [false, false, false, false]);
  assert.deepEqual([fromFirst({ from: "exterior" }), fromFirst({ says: "no end named" }), fromFirst(null)], [null, null, null], "a sign that names no such end gives a bead no way");
  // A sign the view declares says so, with who confirmed it; one an adapter read says where it comes from.
  assert.equal(signedBy(declared(run, "face_transferred.S").sign), " Declared by the run's own view; confirmed by synthetic fixture: written with the rest.");
  assert.equal(signedBy({ says: "x", by: "the viewer's reading" }), " That is the viewer's reading.");
  assert.equal(signedBy({ says: "x" }), " Declared by the run's own view.");
  // What stands behind a record now says how its part of the engine is represented, as the view's layer states.
  assert.equal(behind(declared(run, "face_dissipated_energy_pJ")), "Saved by the run; computed by resolved_pump_tissue@3, simulated.");
  assert.match(behind(declared(run, "turnover_produced_fmol.S")), /^Saved by the run; computed by scheduled_species_turnover@1, prescribed by the experiment\.$/);
  // A constant of the view has no set of its own: it lies on the set its values run along.
  assert.deepEqual([constantOf(run, "membrane_capacitance").lives_on, constantOf(run, "valence").lives_on, constantOf(run, "temperature").lives_on], ["membrane", "world", "world"]);
  // The view's word for a total that only grows.
  assert.deepEqual([declared(run, "face_dissipated_energy_pJ").never_falls, declared(run, "face_transferred.S").never_falls, declared(run, "face_dissipated_energy_pJ").resets], [true, false, null]);
});

test("packaged from the engine's own view, beads go by the view's signs, and what the view does not state is said in its words", async (t) => {
  const { lens, restore } = lensFor([packaged(VIEWED)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.deepEqual(lens.switch.on, ["signal-fog"], "the species an operator declares is the one the sheet opens coloured by");
  await lens.setLayers("transfers,energy-glow");
  const mark = lens.drawn.get("transfers").mark;
  // Only the face: the view gives the exchange routes' total no kind, so no rate is worked out from it, and no bead drawn.
  assert.deepEqual(mark.lanes.map((lane) => [lane.name, lane.species]), [["face_0", "S"]]);
  lens.seek(2);
  const [reading] = mark.readings();
  assert.ok(near(reading.mean, 6e-5) && reading.from === "ecs_0" && reading.to === "bath", "the view's own sign: from the face's sender to its receiver");
  const keys = lens.chrome().legend.layers.keys;
  const way = keys.find((item) => item.key === "way").text;
  assert.equal(way, "A bead goes the way its total grew: a positive amount leaves the face's sender node for its receiver. Declared by the run's own view; confirmed by synthetic fixture: written with the rest");
  const left = keys.filter((item) => item.key === "unplaced").map((item) => item.text);
  assert.deepEqual(left, ["Not drawn: moved by an exchange route. This run saved it, but not as a total since the run's start: no rate can be worked out from it. The run's view says: scheduled_species_exchange@1 declares no kind for it."]);
  // The panel says the same, and what stands behind the face's total with its representation.
  const said = account(lens.run, layer("transfers"), lens.offer("transfers"));
  assert.match(said.numbers[1], /^Carried across a face: saved by the run; computed by resolved_pump_tissue@3, simulated\. Positive means: a positive amount leaves the face's sender node for its receiver\. Declared by the run's own view; confirmed by synthetic fixture: written with the rest\.$/);
  assert.equal(said.numbers.at(-1), `Not drawn: moved by an exchange route. ${left[0].slice("Not drawn: moved by an exchange route. ".length)}`);
  // The same world without a view draws the routes, by the adapter's own reading of its arrays: the two packages differ in exactly that.
  const tables = lensFor([packaged(WORLD)], CATALOGUE.experiments);
  t.after(tables.restore);
  await tables.lens.ready;
  tables.lens.activate();
  await tables.lens.setLayer("transfers", true);
  assert.deepEqual(tables.lens.drawn.get("transfers").mark.lanes.map((lane) => lane.name), ["face_0", "secrete", "sink"]);
  // A voltage with no declared sign feeds no layer that needs its direction, and the reason is the usual one.
  assert.equal(lens.offer("ion-push-pull").why, "This run saved the membrane voltage, but does not say which way it is positive.");
  // The glow reads the view's own word for a total that only grows.
  assert.deepEqual(lens.drawn.get("energy-glow").mark.elements.map((element) => element.name), ["face_0", "wall_cell_0", "contact_0"]);
  // The operators' ledgers have no kind in the view: the cell's panel gives them as saved, and does not call them totals.
  lens.setSelection("cell:0");
  const ledgers = lens.describe("cell:0").sections.find((section) => /^Ledgers of S at/.test(section.title));
  assert.deepEqual(ledgers.items.map((item) => [item.label, item.detail]), [["Made in the cell, as saved (the run's view does not say what kind of number it is)", "0.200 amol"], ["Cleared in the cell, as saved (the run's view does not say what kind of number it is)", "0.002 amol"]]);
  assert.equal(ledgers.note, "Saved by the run.");
});

test("no rate is taken across a reset: where a cell is retired, a total that restarts there gives no rate for that interval", async (t) => {
  // The rule itself, on a made-up run: an operator's event at a cell, and totals that say they restart where that operator retires a slot.
  const sets = new Map([
    ["cell", { ids: ["a", "b"] }],
    ["membrane", { ids: ["m0", "m1"], geometry: { kind: "on", set: "cell", index: [0, 1] } }],
    ["channel", { ids: ["c0"], geometry: { kind: "on", set: "membrane", index: [1] } }],
    ["junction", { ids: ["j0"], geometry: { kind: "links", between: "cell", ends: [[0, 1]] } }],
    ["face", { ids: ["f0"], geometry: { kind: "links", between: "outside", ends: [[0, 1]] } }],
  ]);
  const made = { sets, layers: [{ id: "replacement", owner: "retiring@1" }, { id: "membrane", owner: "inner@1" }], events: [{ time: 2.5, layer: "replacement", at: { set: "cell", index: 1 } }, { time: 3.5, layer: "membrane", at: { set: "cell", index: 0 } }] };
  const resets = { by: ["retiring@1"], says: "restarts" };
  assert.deepEqual([cellsOf(made, "cell", 1), cellsOf(made, "membrane", 1), cellsOf(made, "channel", 0), cellsOf(made, "junction", 0), cellsOf(made, "face", 0)], [[1], [1], [1], [0, 1], null]);
  const restarts = (set, entity, from, to, record = { set, resets }) => restartsBetween(made, record, entity, from, to);
  assert.equal(restarts("membrane", 1, 2, 3), true, "the retired cell's membrane, in the interval that holds the event");
  assert.equal(restarts("membrane", 0, 2, 3), false, "another cell's membrane is untouched");
  assert.equal(restarts("channel", 0, 2, 3), true, "a channel population is traced through its membrane to its cell");
  assert.equal(restarts("junction", 0, 2, 3), true, "a junction restarts where either of its two cells is retired");
  assert.deepEqual([restarts("membrane", 1, 1, 2), restarts("membrane", 1, 3, 4)], [false, false], "the intervals before and after");
  assert.deepEqual([restarts("membrane", 1, 2, 2.5), restarts("membrane", 1, 2.5, 3)], [true, true], "an event at a record's own time counts for both intervals it bounds");
  assert.equal(restarts("face", 0, 2, 3), true, "an entity that cannot be traced to a cell gives no rate in an interval that holds such an event");
  assert.equal(restarts("membrane", 0, 3, 4), false, "an event of a layer no retiring operator owns restarts nothing");
  assert.equal(restartsBetween(made, { set: "membrane", monotone: "non-decreasing" }, 1, 2, 3), false, "a total that does not say it restarts is read straight through");
  // In the lens, on the packaged run whose cell is retired at 2.5 s.
  const { lens, restore } = lensFor([packaged(RETIRING)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  const glow = offer(lens.run, "energy-glow");
  assert.deepEqual([glow.ok, glow.sources.map((record) => [record.id, record.never_falls, Boolean(record.resets)])], [true, [["face_dissipated_energy_pJ", true, false], ["membrane_dissipated_energy_pJ", false, true]]], "a ledger that says where it restarts feeds the glow like one that only grows");
  await lens.setLayer("energy-glow", true);
  const mark = lens.drawn.get("energy-glow").mark;
  const at = (seconds) => {
    lens.seek(seconds);
    return Object.fromEntries(mark.readings().map((reading) => [reading.name, reading]));
  };
  let now = at(2);
  assert.ok(near(now.wall_cell_0.mean, 0.002) && near(now.contact_0.mean, 0.002) && near(now.face_0.mean, 0.004) && !now.wall_cell_0.reset);
  now = at(3);
  assert.deepEqual([now.wall_cell_0.mean, now.wall_cell_0.reset, now.wall_cell_0.glow, now.contact_0.mean, now.contact_0.reset], [null, true, 0, null, true], "the interval from 2 s to 3 s holds the retirement: no rate for the cell's two membranes");
  assert.ok(near(now.wall_cell_0.before, 0.004) && near(now.wall_cell_0.now, 0.001), "the saved total fell from 4 fJ to 1 fJ: the difference is the operator's booking, not a flow");
  assert.ok(near(now.face_0.mean, 0.004) && now.face_0.reset === false, "the face's ledger, which no retiring operator writes, is read straight through");
  now = at(4);
  assert.ok(near(now.wall_cell_0.mean, 0.002) && !now.wall_cell_0.reset, "from 3 s to 4 s the restarted total grows as before");
  // The page says so: in the legend, in what stands behind the layer, and for the interval itself.
  assert.ok(lens.chrome().legend.layers.keys.some((item) => item.key === "glow-reset" && /^Where a cell's slot is retired its totals restart at nought: no glow is drawn for the interval in which that happens$/.test(item.text)));
  assert.ok(account(lens.run, layer("energy-glow"), lens.offer("energy-glow")).numbers.some((line) => /^Energy dissipated at the membrane: .*It restarts at nought where a slot is retired \(scheduled_cell_replacement@1\): no rate is taken across such an event\.$/.test(line)));
  lens.seek(3);
  const section = lens.describe("layers:shown").sections.find((item) => /^Energy dissipated, a mean from 2\.0 s to 3\.0 s$/.test(item.title));
  const membrane = section.items.find((item) => item.label === "wall_cell_0 · energy dissipated at the membrane");
  assert.deepEqual([membrane.detail, membrane.lines[1]], ["no rate in this interval", "A slot was retired in this interval, and its total restarted at nought: the difference is the operator's booking, not a flow, and no rate is taken across it."]);
});

// ------------------------------------------------------------ the example sheet: invented numbers, said to be

// The example's own formulas (tools/make_run_fixture.py, write_example), for the numbers expected below.
const WRITTEN = -0.0215 - -0.0796;
const faded = (seconds) => 9 * (1 - Math.exp(-seconds / 9));
const kirTotal = (inside, seconds) => 0.01 * (seconds + 0.5 * inside * faded(seconds));

test("an example says that its numbers are invented: on the picture, in the legend, in the panel, and in what stands behind every record", async (t) => {
  const { lens, restore } = lensFor([packaged(SHEET)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  const chrome = lens.chrome();
  assert.equal(chrome.legend.layers.example, "Example: invented numbers");
  assert.match(chrome.stamp, /^Example sheet \(invented numbers\) · Example: invented numbers$/);
  assert.deepEqual(chrome.run.experiments.map((item) => [item.id, item.example, item.development]), [["example-sheet", true, false]]);
  assert.ok(lens.labels.shown.some((label) => label.text === "Example: invented numbers" && /label-example/.test(label.kind) && label.boost === 1000), "the picture carries the words for as long as the run is shown");
  assert.match(lens.describe("layers:shown").plain, /^Example: invented numbers\. /);
  // No record of it is said to be computed by a model.
  const run = lens.run;
  assert.equal(behind(declared(run, "vm")), "Example: invented numbers. Written by the viewer's run-fixture tool under the engine's own name for this record; no model computed it. Positive means: a positive voltage means the cell's inside is at a higher potential than its outside. That is the viewer's reading of the run's own saved arrays, not a declaration by the run: at every record each membrane's saved voltage equals the saved potential of its cell less that of the outside node it faces.");
  for (const record of run.view.records) if (record.set) assert.match(behind(declared(run, record.id)), /^Example: invented numbers\./, record.id);
  // It opens as a sheet does: coloured and raised by its voltage; and it can feed the layers no saved run feeds yet.
  assert.deepEqual(lens.switch.on, ["voltage-tint", "voltage-relief"]);
  assert.deepEqual(rowsOf(lens).filter((row) => /^(Motion|Glow)/.test(row)), ["Motion: Off* | Transfers | Ion traffic", "Glow: Off* | Energy dissipated"]);
  assert.deepEqual(chrome.legend.layers.cannot.map((item) => item.id), ["signal-fog"]);
  assert.equal(lens.surface.outside, null, "its baths have no tiles: each cell has one of its own");
});

test("on the example sheet beads cross the junctions at the disc's edge, and a glow stands where its ledgers grow", async (t) => {
  const { lens, restore } = lensFor([packaged(SHEET)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  await lens.setLayers("transfers,energy-glow");
  const run = lens.run, stream = lens.drawn.get("transfers").mark, glow = lens.drawn.get("energy-glow").mark;
  // Which cells are inside the disc: those written to the higher voltage at the start.
  const inside = run.sets.get("cell").ids.map((_, cell) => (run.records.get("vm").at(0, cell) > -0.05 ? 1 : 0));
  assert.equal(inside.reduce((sum, value) => sum + value, 0), 7);
  const ends = run.sets.get("junction").geometry.ends;
  const edge = ends.map(([a, b]) => inside[a] - inside[b]);
  // A lane for K and one for Na on every junction; none across a membrane, whose bath has no tile here.
  assert.deepEqual([stream.lanes.length, new Set(stream.lanes.map((lane) => lane.species)).size, stream.what], [84, 2, "ion"]);
  assert.equal(stream.unplaced.length, 19 * 2, "two species leak through each of the nineteen membranes themselves");
  assert.match(lens.chrome().legend.layers.keys.find((item) => item.key === "unplaced").text, /^38 saved totals cross borders this picture does not draw/);
  // At 0.5 s: K through an edge junction at the mean of the written voltage's first half second, from the disc outwards.
  lens.seek(0.5);
  const link = edge.findIndex((side) => side !== 0);
  const expected = ((0.002 * 0.25) / WRITTEN) * (WRITTEN * edge[link] * faded(0.5) + 1e-5 * (ends[link][0] - ends[link][1]) * 0.5) / 0.5;
  const reading = stream.readings().find((item) => item.name === `junction_${link}` && item.species === "K");
  assert.ok(near(reading.mean, expected, 1e-4), `${reading.mean} fmol a second, ${expected} by the example's formula`);
  const names = run.sets.get("cell").ids;
  assert.deepEqual([reading.from, reading.to], edge[link] > 0 ? [names[ends[link][0]], names[ends[link][1]]] : [names[ends[link][1]], names[ends[link][0]]], "K leaves the cell at the higher voltage");
  assert.equal(stream.token, 50_000, "the busiest junction carries about 293,000 ions a second");
  assert.ok(near(reading.beads, (Math.abs(expected) * PER_FMOL) / 50_000, 1e-4));
  // Sodium goes the same way, a quarter as much.
  const sodium = stream.readings().find((item) => item.name === `junction_${link}` && item.species === "Na");
  assert.ok(near(sodium.mean, expected / 4, 1e-4) && sodium.from === reading.from);
  // Later the written voltage has faded, and fewer cross.
  lens.seek(12);
  assert.ok(Math.abs(stream.readings().find((item) => item.name === `junction_${link}` && item.species === "K").mean) < Math.abs(expected) * 0.3);
  // The glow: a band on each junction, a rim round each cell for its membrane, a spot for its pump and for each channel population.
  const kinds = glow.elements.reduce((count, element) => ({ ...count, [element.kind]: (count[element.kind] || 0) + 1 }), {});
  assert.deepEqual(kinds, { band: 42, rim: 19, spot: 57 });
  assert.deepEqual(lens.chrome().legend.layers.keys.filter((item) => /^glow/.test(item.key)).map((item) => item.key), ["glow", "glow-rim", "glow-spot"]);
  lens.seek(0.5);
  const kirOf = (cell) => glow.readings().find((item) => item.name === `kir_${cell}`);
  const disc = inside.indexOf(1), rest = inside.indexOf(0);
  assert.ok(near(kirOf(disc).mean, 0.004 * (1 + faded(0.5)), 1e-4) && near(kirOf(rest).mean, 0.004, 1e-4), "a K population's heat: 4 fW at rest, half as much again per unit of the written voltage");
  assert.ok(near(glow.full, 0.006), "the scale ends on a round number at or above the most: 6 fW");
  assert.ok(near(kirOf(disc).share, (0.004 * (1 + faded(0.5))) / 0.006, 1e-4));
});

test("with a cell of the example chosen, beads cross its membrane through each channel population and through its pump", async (t) => {
  const { lens, restore } = lensFor([packaged(SHEET)], CATALOGUE.experiments);
  t.after(restore);
  await lens.ready;
  lens.activate();
  await lens.setLayer("ion-traffic", true);
  assert.equal(lens.onMembrane.size, 0);
  assert.equal(lens.chrome().legend.layers.hint, "Choose a cell of the sheet: a piece of its membrane is drawn beside it.");
  assert.ok(lens.chrome().legend.layers.time, "the slow-down is offered while the layer is on");
  const run = lens.run;
  const disc = run.sets.get("cell").ids.findIndex((_, cell) => run.records.get("vm").at(0, cell) > -0.05);
  lens.setSelection(`cell:${disc}`);
  const mark = lens.onMembrane.get("ion-traffic").mark;
  // Four forms: the two channel populations, the pump, and the bare membrane; six streams, the pump's two ions and the
  // two species that leak each in a lane of their own.
  assert.deepEqual(mark.forms.map((form) => [form.name, form.kind, form.streams.length]), [[`kir_${disc}`, "channel", 1], [`nal_${disc}`, "channel", 1], ["pump", "pump", 2], ["membrane itself", "membrane", 2]]);
  assert.deepEqual(mark.streams.map((stream) => [stream.kind, stream.species, stream.per]), [["channel", "K", 1], ["channel", "Na", 1], ["pump", "Na", -3], ["pump", "K", 2], ["membrane", "K", 1], ["membrane", "M", 1]]);
  assert.ok(mark.forms.every((form, k) => k === 0 || form.x > mark.forms[k - 1].x), "side by side along the piece");
  // One token for the whole run: the busiest stream is a disc cell's K channels in the first half second.
  const most = (kirTotal(1, 0.5) - kirTotal(1, 0)) / 0.5;
  assert.ok(near(mark.busiest, most, 1e-4));
  assert.equal(mark.token, 1_000_000, "about 8.95 million ions a second");
  // At 1 s, the mean of 0.5 s to 1 s.
  lens.seek(1);
  const readings = mark.readings();
  const kir = (kirTotal(1, 1) - kirTotal(1, 0.5)) / 0.5, nal = -0.004 * (1 + 0.02 * disc), cycles = 0.002 * (1 + 0.01 * disc);
  assert.ok(near(readings[0].mean, kir, 1e-4) && readings[0].way === "out of the cell", "K leaves through its channels");
  assert.ok(near(readings[1].mean, nal, 1e-4) && readings[1].way === "into the cell", "Na enters through its own");
  assert.ok(near(readings[2].mean, -3 * cycles, 1e-4) && readings[2].way === "out of the cell", "the pump carries three Na out for each cycle");
  assert.ok(near(readings[3].mean, 2 * cycles, 1e-4) && readings[3].way === "into the cell", "and two K in");
  assert.ok(near(readings[0].beads, (kir * PER_FMOL) / 1e6, 1e-4) && near(readings[3].beads, (2 * cycles * PER_FMOL) / 1e6, 1e-4));
  // Through the membrane itself: what its own passive routes carried, a ledger apart from its channels' and its pump's, as the engine keeps them.
  assert.ok(near(readings[4].mean, 0.0003, 1e-4) && near(readings[5].mean, 0.0005, 1e-4) && readings[4].way === "out of the cell" && readings[5].way === "out of the cell");
  // What the close-up says of itself: that it is an example, and the token, the time and the interval.
  const caption = lens.closeupCaption().split("\n");
  assert.equal(caption[0], "Example: invented numbers");
  assert.match(caption[1], new RegExp(`^Membrane of cell_${disc} at 1\\.0 s$`));
  assert.ok(caption.includes("One bead is 1,000,000 ions · true speed, shown still · mean of 0.5 s to 1.0 s"), caption.join(" | "));
  assert.ok(caption.includes("Worked out by the viewer from the saved totals."));
  // The legend: the ions' colours, the token and the time, whose word the direction is, and what a pump's beads are.
  const keys = lens.chrome().legend.layers.keys;
  assert.deepEqual(keys.map((item) => item.key), ["ions", "bead", "time", "way", "head", "pump", "leak"]);
  assert.deepEqual(mark.drawn.heads, 6, "an arrowhead for each of the six streams");
  assert.equal(keys[6].text, "Through the membrane itself, with no form: what its own passive routes carried, beside its channel populations and its pump");
  assert.deepEqual(keys[0].chips.map((chip) => chip.label), ["K", "Na", "M"]);
  assert.equal(keys[1].text, "One bead is 1,000,000 ions. More beads a second means more ions a second; how fast a bead travels stands for nothing");
  assert.match(keys[2].text, /^True speed: one second here is one second in the cell\. Shown still here/);
  assert.match(keys[3].text, /^A bead goes the way its total grew: a positive amount has left the channel's cell for its outside, as for its membrane; positive cycles carry their ions into the cell: .*; a positive amount has left the membrane's cell for its outside\. That is the engine's own convention/);
  assert.equal(keys[5].text, "Through the pump: its cycles between two records, times the ions one cycle moves as the pump's declaration gives them");
  // The cell's panel gives each stream's numbers.
  const section = lens.describe(`cell:${disc}`).sections[0];
  assert.match(section.title, /^On its membrane at 1\.0 s$/);
  assert.deepEqual(section.items.map((item) => item.label), [`kir_${disc} · K`, `nal_${disc} · Na`, `pump of membrane_${disc} · Na`, `pump of membrane_${disc} · K`, `membrane_${disc} · K`, `membrane_${disc} · M`]);
  assert.match(section.items[2].detail, /amol a second out of the cell \(the pump's cycles times 3, what one cycle moves of it\)$/);
  assert.match(section.items[0].lines[1], /ions a second; one bead is 1,000,000, so [\d.]+ beads a second pass$/);
  // A cell outside the disc at the same moment: its K channels pass fewer.
  const rest = run.sets.get("cell").ids.findIndex((_, cell) => run.records.get("vm").at(0, cell) < -0.05);
  lens.setSelection(`cell:${rest}`);
  const quiet = lens.onMembrane.get("ion-traffic").mark;
  assert.equal(quiet.token, 1_000_000, "the same token, whichever cell is chosen");
  assert.ok(near(quiet.readings()[0].mean, 0.01, 1e-4));
  // The streams through one membrane, without the lens: a population with no declared direction has none.
  const sources = offer(run, "ion-traffic").sources;
  assert.equal(streamsOf(run, sources, null, rest).length, 2, "without the pump's cycles, the two channel populations");
  assert.equal(streamsOf(run, sources.map((source) => ({ ...source, sign: { says: "unknown" } })), null, rest).length, 0);
});

// ------------------------------------------------------------ beads: what a run must have saved

test("beads through a membrane need the totals carried through its channel populations, as totals with a declared direction", async (t) => {
  const traffic = layer("ion-traffic");
  assert.deepEqual({ mark: traffic.mark, channels: traffic.channels, quantity: traffic.quantity }, { mark: "beads", channels: ["motion"], quantity: { derivation: "rate", any_of: ["channel_transferred"] } });
  assert.deepEqual({ channels: MARKS.beads.channels, lives_on: MARKS.beads.lives_on, surface: MARKS.beads.surface, built: MARKS.beads.built }, { channels: ["motion"], lives_on: ["channel population", "pump population", "membrane"], surface: "membrane", built: undefined });
  assert.match(traffic.says, /A bead is a token of a rate, not an ion/);
  // A run that did not save what crossed its channels: said, as for any layer.
  const { run } = made({ membrane: true });
  assert.deepEqual([offer(run, "ion-traffic").ok, offer(run, "ion-traffic").why], [false, NOT_SAVED]);
  // A run that did: what the rule needs of the record is checked.
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
  assert.deepEqual([carried(() => {}).ok, carried(() => {}).why, carried(() => {}).lacking.map((item) => item.says)], [true, null, ["This run did not save its pumps' cycles, so no beads cross through a pump.", "This run did not save what crossed the membrane itself, beside its channel populations and its pump."]]);
  assert.equal(carried((record) => (record.kind = "level")).why, "This run saved it, but not as a total since the run's start: no rate can be worked out from it.");
  assert.equal(carried((record) => delete record.sign).why, "This run saved it, but does not say which way it is positive: a bead would have no way to go.");
  // In the page: a run that saved none is told so, and the layer cannot be switched on.
  const { lens, restore } = lensFor([syntheticRun({ membrane: true })]);
  t.after(restore);
  await lens.ready;
  lens.activate();
  assert.deepEqual(lens.chrome().legend.layers.cannot.map((item) => [item.id, item.label, item.why]).filter(([id]) => id === "ion-traffic"), [["ion-traffic", "Motion: ion traffic", NOT_SAVED]]);
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
