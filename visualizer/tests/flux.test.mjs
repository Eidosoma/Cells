// Flux in the Cell view, checked without a browser (schema/QUANTITY_LAYERS.md, "Flux in the
// Cell view", with rules 3, 7, 11 and 12): the declarations in data, what is drawn for each
// species through its file and on what basis, where the lanes run on the cell as its builder
// draws it, the beads' arithmetic in three dimensions, the lens's side (the switch, a chosen
// part, the bloom and the hold on the look's motion, the words on the picture, the legend
// and the panels), and the reader of a species' looping run against a fixture made here.
//
//   node --test tests/flux.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { openReplay, loadPart } from "../src/replay/source.js";
import { readFlux, planFor, speaksFor, shownKinds, shownWithheld, illustrationWords, FLUX_FORMAT, PACE, FORMS } from "../src/layers/flux.js";
import { readLoop, loopAt, loopStreams, loopToken, loopRates, planFromLoop, loopWords, closesWords, engineWords, bordersOf, READ_WORDS } from "../src/layers/loop.js";
import { CellFlux, seatsOf, arrange, FLUX, PROBLEMS, SIZES, BLOOM, FLUX_PANEL, FLUX_SWITCH, STATEMENT, REST_WORDS, CLOSE_PUMP } from "../src/layers/cellflux.js";
import { Tokens, swell, RIM } from "../src/layers/marks/tokens.js";
import { Flow, CHEVRONS, STYLES, widthOf, STREAK_PACE } from "../src/layers/marks/flow.js";
import { fitOnRow, clearOf } from "../src/layers/statement.js";
import { CROSSING, standing, tokenFor, ionsASecond, beadsASecond, meanRate, paceAt, paceKey, modeAt, blendAt, resolveAt, flowWords, headSize, advance, slowAt, positionOf, slowLabel, STILL_WORDS, SLOWS, SLOWEST, SLIDER, BUSIEST } from "../src/layers/marks/beads.js";
import { CellLens } from "../src/lenses/cell.js";
import { cellTypeOf } from "../src/scene/entries.js";
import { buildCell, buildMolecules } from "../src/lenses/cell_parts.js";
import { clock } from "../src/replay/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const declarations = json("data/layers/flux.json");
const contract = readFileSync(path.join(ROOT, "schema", "QUANTITY_LAYERS.md"), "utf8").replace(/\s+/g, " "); // its lines are folded
const scene = json("data/architecture/architecture.scene.json");
const capabilities = scene.entities.filter((entity) => entity.kind === "capability");
const SPECIES = scene.species.map((species) => species.id);
const copy = (value) => JSON.parse(JSON.stringify(value));
const near = (actual, expected, share = 1e-6) => Math.abs(actual - expected) <= Math.abs(expected) * share + 1e-12;

// ------------------------------------------------------------ stand-ins

/** A stand-in for the builder's context: the cell's builder asks it for parts and materials, and nothing is drawn. */
function context() {
  const standard = (options = {}) => Object.assign(new THREE.MeshStandardMaterial(), { userData: { options } });
  const part = (name, anchor) => ({ name, anchor: anchor || null, group: new THREE.Group(), material: standard, points: () => new THREE.PointsMaterial(), lineMaterial: () => new THREE.LineBasicMaterial(), proxyMaterial: () => new THREE.MeshBasicMaterial(), add() {} });
  return { part, scale: part, neutral: standard, neutralPoints: () => new THREE.PointsMaterial(), neutralLine: (options = {}) => (options.dashed ? new THREE.LineDashedMaterial() : new THREE.LineBasicMaterial()), illustrate() {}, scenery() {}, sprite() {} };
}

/** A stand-in for the stage: what is marked to shine, how strongly the bloom is on, and what holds the look's motion. */
function stageOf({ moving = true, width = 1280, height = 800, dark = false } = {}) {
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  camera.position.set(0, 40, 60);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  return {
    palette: { bg: dark ? "#0b151e" : "#eef2f6", fg: dark ? "#e8eef4" : "#12283a", bioIon: "#c9a227", bioWater: "#4aa3df", bioSignal: "#b565c9", dark }, // the picture's own hues are there, and are not used
    camera, width, height, reducedMotion: !moving, rig: { instant: false }, invalidated: 0,
    invalidate() { this.invalidated++; },
    shining: new Set(), bloom: 0, blooms: [],
    decoration: { holds: new Set(), pause(reason) { this.holds.add(reason); }, resume(reason) { this.holds.delete(reason); } },
    glow(object, on = true) { if (on) this.shining.add(object); else this.shining.delete(object); },
    setBloom(strength) { this.bloom = strength; this.blooms.push(strength); },
  };
}

/** A stand-in for the label layer: it keeps the labels the flux adds and what they say, and measures them as a page would (seven pixels a letter, sixteen a line). */
function labelLayer() {
  const made = [];
  const measure = (label) => {
    const lines = String(label.text || "").split("\n");
    label.width = Math.max(...lines.map((line) => line.length)) * 7 + 14;
    label.height = 16 * lines.length + 2;
    return label;
  };
  return { made, add: (spec) => (made.push(measure({ ...spec, hidden: false })), made.at(-1)), setText: (label, text) => measure(Object.assign(label, { text })) };
}

/**
 * The cell lens as far as flux needs it, for one species of the scene: what the species has
 * (worked out by the lens's own plan), its cell built by the cell's own builder in each size
 * mode it is drawn in, and stand-ins for the zones, the stage and the labels.
 */
function lensFor(id, { mode = null, stage = stageOf(), flux = FLUX, replays = null, before = null } = {}) {
  const species = scene.species.find((item) => item.id === id);
  const lens = {
    species, sizeMode: mode || "schematic", selected: null, active: true, dustFade: 1, chromes: 0, stage,
    // `replays`: the page's catalogue of runs, for a species whose cell type names its looping run.
    model: { ofKind: (kind) => (kind === "capability" ? capabilities : []), get: (entity) => scene.entities.find((item) => item.id === entity) || null, raw: replays ? { ...scene, replays } : scene },
    capabilityByPart: new Map(capabilities.map((entity) => [entity.part, entity])),
    leftOut: new Set((scene.left_out || []).map((item) => item.part).filter(Boolean)),
    zones: [], cells: {},
    onChrome() { this.chromes++; },
  };
  CellLens.prototype.plan.call(lens);
  if (mode && lens.modes.includes(mode)) lens.sizeMode = mode;
  lens.draws = (part) => CellLens.prototype.draws.call(lens, part);
  for (const size of lens.modes) {
    const cell = { shape: lens.levels.cell.shape, parts: cellTypeOf(species).parts || {}, has: lens.draws, neighbours: Boolean(lens.levels.tissue), notes: [] }; // the default cell type's, as the lens builds it
    const handles = buildCell(context(), context(), size, cell);
    handles.molecule = buildMolecules(context(), size, handles.frame, lens.draws);
    lens.cells[size] = handles;
    lens.zones.push({ name: "cell", mode: size, root: new THREE.Group(), fade: 1 }, { name: "molecules", mode: size, root: new THREE.Group(), fade: 1 });
  }
  before?.(lens); // what a test sets on the lens before its flux is built (a fetch that serves the catalogue's files)
  lens.flux = new CellFlux(lens, flux);
  lens.flux.build();
  lens.labels = labelLayer();
  lens.flux.label(lens.labels);
  lens.flux.refresh(); // as the lens does once its picture stands
  lens.chromes = 0;
  // The lens's own calls, as cell.js makes them.
  lens.choose = (entity) => {
    lens.selected = entity;
    lens.flux.refresh();
  };
  return lens;
}
const lanesOf = (lens) => lens.flux.tokens.flatMap((set) => set.lanes);
// A species shown as the engine's generic cell whose file names no looping run: its flux is illustration (rule 11). The
// planarian's own cell type names its run, so its flux comes from that run, and it has tests of its own below.
const ILLUSTRATED = "human";
const kindsOf = (plan) => plan.kinds.map((kind) => kind.id);

// ------------------------------------------------------------ the declarations

test("the declarations are sound, and the two forms of illustration are the contract's", () => {
  assert.deepEqual(PROBLEMS, []);
  assert.equal(declarations.format, FLUX_FORMAT);
  assert.deepEqual(FLUX.kinds.map((kind) => kind.id), ["channels", "pumps", "junctions", "water", "secretion", "fuel", "membrane"]);
  // Rule 11: two declared forms, and the words the picture carries.
  assert.deepEqual(Object.keys(declarations.illustration.forms), FORMS);
  for (const form of FORMS) assert.ok(contract.includes(`\`${form}\``), `the contract does not name the form ${form}`);
  assert.ok(contract.includes(`"${declarations.illustration.notice}"`), "the notice is the contract's own words");
  assert.equal(declarations.illustration.notice, "Illustration: not a run");
  // `direction only` is built; `typical values` is declared and holds nothing: each number needs a cited source.
  assert.equal(declarations.illustration.forms["direction only"].offered, true);
  assert.equal(declarations.illustration.forms["typical values"].offered, false);
  assert.deepEqual(declarations.illustration.forms["typical values"].entries, []);
  assert.match(declarations.illustration.forms["typical values"].needs, /licence/);
  assert.deepEqual(illustrationWords(FLUX), ["Illustration: not a run", "Direction only: the number of beads and their pace stand for no number"]);
  assert.equal(illustrationWords(FLUX, true)[1], "Direction only: the number of beads and their pace stand for no number · shown still");
});

test("every law a direction is drawn from is cited: its id, the file it was read in and the revision", () => {
  assert.match(declarations.engine.revision, /^[0-9a-f]{7,40}$/);
  assert.match(declarations.engine.read, /^\d{4}-\d{2}-\d{2}$/);
  const used = new Set();
  for (const kind of declarations.kinds) for (const group of kind.groups) if (group.law) used.add(group.law);
  assert.deepEqual([...used].sort(), Object.keys(declarations.laws).sort(), "every law declared is used, and every law used is declared");
  for (const law of Object.values(declarations.laws)) {
    assert.match(law.id, /^[a-z0-9_]+@\d+$/, "an engine law's own id");
    assert.match(law.path, /^src\/cells\/.+\.py$/);
    assert.ok(law.declares.length > 20 && law.limit.length > 20);
  }
  // A group with no law claims no direction: it draws both ways and says so.
  for (const kind of declarations.kinds) {
    for (const group of kind.groups) {
      if (group.law) continue;
      assert.deepEqual(group.lanes.map((lane) => lane.way).sort(), ["in", "out"], `${kind.id}/${group.id}`);
      assert.match(group.says, /^Both ways are drawn, and neither is claimed to carry more\./);
      assert.match(group.says, /which only a run knows\.$/);
    }
  }
  // The pump's two lanes show as many beads as each other: the three and the two stand in words.
  const pump = declarations.kinds.find((kind) => kind.id === "pumps").groups[0];
  assert.deepEqual(pump.lanes.map((lane) => [lane.species, lane.way, lane.count]), [["Na", "out", 3], ["K", "in", 2]]);
  assert.match(pump.says, /3 sodium out of the cell and 2 potassium in/);
  // Fuel: nothing is drawn, and the file says why.
  assert.match(declarations.kinds.find((kind) => kind.id === "fuel").nothing, /no law of the engine says where fuel travels/);
});

test("declarations that would claim what they cannot are refused, kind by kind", () => {
  const broken = (change) => {
    const file = copy(declarations);
    change(file);
    return readFlux(file);
  };
  assert.deepEqual(readFlux({ format: "other" }).flux, null);
  const kind = (file, id) => file.kinds.find((item) => item.id === id);
  // A group with no law and one way only would claim a direction with no basis.
  let read = broken((file) => kind(file, "channels").groups[0].lanes.pop());
  assert.match(read.problems.join("; "), /kind "channels", group "ions" claims no direction and does not draw both ways/);
  assert.ok(!read.flux.kinds.some((item) => item.id === "channels"), "the kind is left out");
  assert.ok(read.flux.kinds.some((item) => item.id === "pumps"), "the others stay");
  // A law that is not declared.
  read = broken((file) => (kind(file, "pumps").groups[0].law = "a textbook"));
  assert.match(read.problems.join("; "), /names the law "a textbook", which is not declared/);
  // A law with no word on what happens where it does not speak for a species.
  read = broken((file) => delete kind(file, "pumps").groups[1].without);
  assert.match(read.problems.join("; "), /does not say what is drawn where its law does not speak for a species/);
  // Nothing drawn and no reason.
  read = broken((file) => delete kind(file, "fuel").nothing);
  assert.match(read.problems.join("; "), /kind "fuel" draws nothing and does not say why/);
  // Typical values offered with nothing behind them.
  read = broken((file) => (file.illustration.forms["typical values"].offered = true));
  assert.match(read.problems.join("; "), /`typical values` is offered with no entries/);
  // A lane with no way.
  read = broken((file) => (kind(file, "water").groups[0].lanes[0].way = "round"));
  assert.match(read.problems.join("; "), /a lane needs an id and a way, in or out/);
});

// ------------------------------------------------------------ what is drawn for a species, through its file

test("a law of the engine speaks for a species shown as the generic cell whose file says nothing of its own on the part", () => {
  const species = (id) => scene.species.find((item) => item.id === id);
  const pumps = capabilities.find((entity) => entity.part === "pumps");
  assert.deepEqual(speaksFor(species("planarian"), pumps), { ok: true });
  assert.deepEqual(speaksFor(species("human"), pumps), { ok: true });
  const cress = speaksFor(species("thalecress"), pumps);
  assert.equal(cress.ok, false);
  assert.equal(cress.proposed, false);
  assert.match(cress.note, /^Not the sodium-potassium pump of animal cells/);
  const coli = speaksFor(species("ecoli"), pumps);
  assert.deepEqual([coli.ok, coli.proposed], [false, true]);
  // A proposed species with no words of its own on a part: still nothing of it is in the engine.
  assert.deepEqual(speaksFor({ modelled: { state: "proposed" }, cell: { capabilities: {} } }, pumps), { ok: false, proposed: true, note: null });
});

test("for each species the plan follows its file: nothing for a part it lacks, and no direction its file sets apart", () => {
  const plans = Object.fromEntries(SPECIES.map((id) => [id, lensFor(id).flux.plan]));
  // The animals with no run of their own, shown as the engine's generic cell: all of it, with fuel alone withheld.
  for (const id of ["human", "mouse", "fruitfly"]) {
    assert.deepEqual(kindsOf(plans[id]), ["channels", "pumps", "junctions", "water", "secretion"], id);
    assert.deepEqual(plans[id].withheld.map((item) => item.id), ["fuel"], id);
    const pumps = plans[id].kinds[1];
    assert.deepEqual(pumps.groups.map((group) => [group.id, group.claimed]), [["sodium-potassium", true], ["calcium", true]]);
    assert.deepEqual(pumps.groups[0].lanes.map((lane) => [lane.species, lane.way, lane.count]), [["Na", "out", 3], ["K", "in", 2]]);
    assert.deepEqual(pumps.groups[1].lanes.map((lane) => [lane.species, lane.way, lane.count]), [["Ca", "out", 1]]);
    assert.match(pumps.groups[0].basis, /^Basis: the engine's law nak_atp_mass_action_positive@1, read in src\/cells\/processes\/kinetic_pump\.py at main [0-9a-f]{8}\. It declares SODIUM_PER_CYCLE = -3 and POTASSIUM_PER_CYCLE = 2/);
    assert.match(pumps.groups[0].basis, /The law's cycles are signed\./);
    assert.match(plans[id].kinds[4].groups[0].basis, /scheduled_species_exchange@1/);
  }
  // Thale cress: its file says its pumps are not the sodium-potassium pump of animal cells, and that it has no
  // gap junctions. No direction is drawn for its pumps, in its file's own words; nothing is said of junctions.
  assert.deepEqual(kindsOf(plans.thalecress), ["channels", "water", "secretion"]);
  assert.deepEqual(plans.thalecress.withheld.map((item) => item.id), ["pumps/sodium-potassium", "pumps/calcium", "fuel"]);
  assert.match(plans.thalecress.withheld[0].why, /^No direction is drawn for Thale cress: its file says of its own part, “Not the sodium-potassium pump of animal cells: .*” The engine's law claims nothing about it\.$/);
  assert.ok(!plans.thalecress.withheld.some((item) => item.part === "junctions"));
  // The proposed species: nothing of them is in the engine, so no law of the engine gives a direction.
  assert.deepEqual(kindsOf(plans.ecoli), ["channels", "water", "secretion"]);
  assert.deepEqual(kindsOf(plans.syn3a), ["water", "secretion"], "no ion channel was found in it: none is offered");
  assert.deepEqual(kindsOf(plans.mpneumoniae), ["water", "secretion"]);
  for (const id of ["ecoli", "syn3a", "mpneumoniae"]) {
    assert.deepEqual(plans[id].withheld.map((item) => item.id), ["pumps/sodium-potassium", "pumps/calcium", "fuel"], id);
    assert.match(plans[id].withheld[0].why, /Nothing of it is in the engine, and the engine's law claims nothing about it\.$/);
    const signals = plans[id].kinds.at(-1).groups[0];
    assert.equal(signals.claimed, false);
    assert.equal(signals.basis, null);
    assert.match(signals.says, /^Both ways are drawn, and neither is claimed to carry more: no law of the engine speaks for what this species releases and takes up\.$/);
  }
  // The planarian's own cell type names its looping run: no illustration is planned for it, whether or not the run is had.
  assert.deepEqual([kindsOf(plans.planarian), lensFor("planarian").flux.source.kind], [[], "pending"]);
  // Whatever the species: a lane is either the engine's declaration with its law named, or one of two ways neither of which is claimed.
  for (const [id, plan] of Object.entries(plans)) {
    for (const kind of plan.kinds) {
      for (const group of kind.groups) {
        if (group.claimed) assert.ok(group.law?.id && group.basis.includes(group.law.id) && group.basis.includes(declarations.engine.revision), `${id}/${kind.id}`);
        else assert.deepEqual([...new Set(group.lanes.map((lane) => lane.way))].sort(), ["in", "out"], `${id}/${kind.id}`);
        assert.ok(group.lanes.every((lane) => lane.claimed === group.claimed && (group.claimed || lane.count === null)));
      }
    }
    for (const item of plan.withheld) assert.ok(item.why.length > 30, `${id}/${item.id} says why`);
  }
});

test("a part's flux shows when the part is chosen, alone; the switch shows all; at rest nothing", () => {
  const plan = lensFor(ILLUSTRATED).flux.plan;
  assert.deepEqual(shownKinds(plan, {}), []);
  assert.deepEqual(shownKinds(plan, { part: "pumps" }).map((kind) => kind.id), ["pumps"]);
  assert.deepEqual(shownKinds(plan, { on: true }).map((kind) => kind.id), ["channels", "pumps", "junctions", "water", "secretion"]);
  assert.deepEqual(shownKinds(plan, { on: true, part: "water" }).map((kind) => kind.id), ["water"], "a chosen part shows alone, whatever the switch");
  assert.deepEqual(shownKinds(plan, { on: true, part: "nucleus" }).map((kind) => kind.id).length, 5, "a part nothing flows through leaves the switch's choice as it is");
  assert.deepEqual(shownWithheld(plan, { part: "atp" }).map((item) => item.id), ["fuel"], "a chosen part that is not drawn says why");
  assert.deepEqual(shownWithheld(plan, { part: "pumps" }), []);
  assert.deepEqual(shownWithheld(plan, { on: true }).map((item) => item.id), ["fuel"]);
  assert.deepEqual(shownWithheld(plan, {}), []);
});

// ------------------------------------------------------------ where the lanes run

test("each kind's lanes cross the membrane where the cell's builder put the part", () => {
  const lens = lensFor(ILLUSTRATED);
  const cell = lens.cells.schematic, depth = (point) => cell.shape.depth(point);
  assert.deepEqual(Object.keys(cell.spots).sort(), ["channels", "charges", "furrow", "gap", "junction", "pumps", "secretion", "water", "wound"]);
  const count = (kind) => seatsOf(kind, cell, "schematic").length;
  assert.deepEqual(["channels", "pumps", "junctions", "water", "secretion", "membrane", "fuel"].map(count), [6, 3, 1, 2, 1, 4, 0]);
  for (const kind of ["channels", "pumps", "water", "membrane"]) {
    for (const seat of seatsOf(kind, cell, "schematic")) {
      const lane = seat.inward(0);
      assert.ok(depth(lane(0)) < -0.3, `${kind}: a lane into the cell starts outside it (${depth(lane(0))})`);
      assert.ok(depth(lane(1)) > 0.3, `${kind}: and ends inside it (${depth(lane(1))})`);
      assert.ok(near(lane(0).y, cell.frame.cut + SIZES.schematic.over[kind]), "above the cut face, clear of the part it passes");
      // Two lanes at one place run side by side: moved along the membrane, not across it.
      const beside = seat.inward(SIZES.schematic.pitch)(0.5), here = lane(0.5);
      assert.ok(near(beside.distanceTo(here), SIZES.schematic.pitch, 0.05));
      assert.ok(Math.abs(depth(beside) - depth(here)) < 0.03);
    }
  }
  // A junction joins the cell to its neighbour: its lane starts beyond the cleft, in the neighbour.
  const bridge = seatsOf("junctions", cell, "schematic")[0].inward(0);
  assert.ok(depth(bridge(0)) < -cell.spots.gap - 0.3 && depth(bridge(1)) > 0.3);
  // What is released goes the way the picture's own signals leave; what is taken up crosses beside that corner.
  const signals = seatsOf("secretion", cell, "schematic")[0];
  const leaving = signals.outward(0);
  assert.ok(leaving(0).distanceTo(cell.signalPath(0)) < 1e-9 && leaving(1).distanceTo(cell.signalPath(1)) < 1e-9);
  assert.ok(depth(leaving(1)) < depth(leaving(0)), "outward");
  assert.ok(depth(signals.inward(0)(0)) < 0 && depth(signals.inward(0)(1)) > 0);
  // A species that lives as single cells has no neighbour for a junction to lead to; and to scale every lane is smaller.
  const coli = lensFor("ecoli");
  assert.equal(seatsOf("junctions", coli.cells[coli.sizeMode], coli.sizeMode).length, 0);
  assert.equal(coli.cells[coli.sizeMode].spots.junction, null);
  const real = lensFor(ILLUSTRATED, { mode: "real" });
  const toScale = seatsOf("channels", real.cells.real, "real")[0].inward(0);
  assert.ok(near(toScale(0).distanceTo(toScale(1)), 2 * SIZES.real.reach, 0.02), "to scale a lane is under a micrometre long");
  assert.equal(seatsOf("channels", null, "schematic").length, 0);
});

test("an illustration draws each lane at every place of its group; a run gives each stream one lane", () => {
  const lens = lensFor(ILLUSTRATED);
  const cell = lens.cells.schematic, pitch = SIZES.schematic.pitch;
  const pumps = lens.flux.plan.kinds.find((kind) => kind.id === "pumps");
  const placed = arrange(pumps, seatsOf("pumps", cell, "schematic"), { every: true, pitch });
  // Sodium and potassium at the first two pumps, calcium at the third: which pump stands for which is the picture's choice.
  assert.deepEqual(placed.map((item) => [item.lane.species, item.key.split("@")[1], item.reverse]), [["Na", "0", true], ["K", "0", false], ["Na", "1", true], ["K", "1", false], ["Ca", "2", true]]);
  // Side by side at one pump, and opposite ways: sodium out, potassium in.
  const [sodium, potassium] = placed;
  assert.ok(near(sodium.path(0.5).distanceTo(potassium.path(0.5)), pitch, 0.05));
  const depth = (point) => cell.shape.depth(point);
  assert.ok(depth(potassium.path(0)) < 0 && depth(potassium.path(1)) > 0, "the lane is laid inward");
  // A run: three streams over six channel places, one lane each; seven over three places, side by side.
  const run = (count) => ({ groups: [{ lanes: Array.from({ length: count }, (_, k) => ({ key: `s${k}`, way: null })) }] });
  assert.deepEqual(arrange(run(3), seatsOf("channels", cell, "schematic"), { every: false, pitch }).map((item) => item.key), ["s0@0", "s1@1", "s2@2"]);
  assert.deepEqual(arrange(run(7), seatsOf("pumps", cell, "schematic"), { every: false, pitch }).map((item) => item.key).sort(), ["s0@0", "s1@1", "s2@2", "s3@0", "s4@1", "s5@2", "s6@0"]);
  assert.ok(arrange(run(2), seatsOf("channels", cell, "schematic"), { every: false, pitch }).every((item) => item.reverse === false), "a run's lane is laid inward, and turned by the run's sign");
  assert.deepEqual(arrange(pumps, [], { every: true, pitch }), []);
});

// ------------------------------------------------------------ the beads in three dimensions

const straight = (from, to) => (share) => new THREE.Vector3().lerpVectors(from, to, share);
const placeOf = (mesh, index) => new THREE.Vector3().setFromMatrixPosition(new THREE.Matrix4().fromArray(mesh.instanceMatrix.array, index * 16));
const sizeOf = (mesh, index) => new THREE.Vector3().setFromMatrixScale(new THREE.Matrix4().fromArray(mesh.instanceMatrix.array, index * 16)).x;

test("beads in three dimensions keep the bead layer's arithmetic: as many a second as the rate says, at any frame rate", () => {
  const a = new THREE.Vector3(0, 0, 0), b = new THREE.Vector3(4, 0, 0);
  // Beads with today's arrowhead at each lane's end (the style kept to be compared; the page's own is chevrons, below).
  const make = () => new Tokens({ lanes: [{ key: "in", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: PACE, reverse: false }, { key: "out", path: straight(a, b), colour: new THREE.Color("#eb6834"), perSecond: PACE, reverse: true }], radius: 0.1, ground: new THREE.Color("#eef2f6"), style: "arrow" });
  const tokens = make();
  // As full as it would be had it been watched all along: a bead and a quarter a second, a crossing of 1.6 s.
  assert.equal(CROSSING, 1.6);
  assert.deepEqual(tokens.drawn, { beads: 4, heads: 2, chevrons: 0, streams: 0 });
  // Sixty frames of a sixtieth, or two frames of half a second: the same beads stand at the same places.
  const fine = make(), coarse = make();
  for (let frame = 0; frame < 60; frame++) fine.tick(1 / 60);
  coarse.tick(0.5);
  coarse.tick(0.5);
  assert.equal(fine.drawn.beads, coarse.drawn.beads);
  for (let index = 0; index < fine.drawn.beads; index++) assert.ok(placeOf(fine.cores, index).distanceTo(placeOf(coarse.cores, index)) < 1e-6);
  // A bead of the lane that goes the other way stands at the mirrored place.
  const lane = fine.lanes[0], back = fine.lanes[1];
  assert.ok(near(placeOf(fine.cores, 0).x, 4 * lane.beads[0], 1e-5));
  assert.ok(near(placeOf(fine.cores, lane.beads.length).x, 4 * (1 - back.beads[0]), 1e-5));
  // An arrowhead ends each lane, at the end its beads go to, and points on that way.
  const turned = (index) => {
    const turn = new THREE.Quaternion();
    new THREE.Matrix4().fromArray(fine.heads.instanceMatrix.array, index * 16).decompose(new THREE.Vector3(), turn, new THREE.Vector3());
    return new THREE.Vector3(0, 1, 0).applyQuaternion(turn);
  };
  assert.ok(placeOf(fine.heads, 0).distanceTo(b) < 1e-6 && turned(0).distanceTo(new THREE.Vector3(1, 0, 0)) < 1e-6);
  assert.ok(placeOf(fine.heads, 1).distanceTo(a) < 1e-6 && turned(1).distanceTo(new THREE.Vector3(-1, 0, 0)) < 1e-6);
  // A rim in the ground's colour stands round every bead, a little larger.
  assert.ok(near(sizeOf(fine.rims, 0), sizeOf(fine.cores, 0) * RIM, 1e-6));
  assert.ok(near(sizeOf(fine.cores, 0), 0.1 * swell(lane.beads[0]), 1e-6));
});

test("where nothing may move the beads stand, as many as would be on their way; the arrowheads still say the way", () => {
  const a = new THREE.Vector3(0, 0, 0), b = new THREE.Vector3(0, 0, 3);
  const tokens = new Tokens({ lanes: [{ key: "k", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: PACE, reverse: false }, { key: "thin", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: 0.1, reverse: false }, { key: "none", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: 0, reverse: false }], radius: 0.1, ground: new THREE.Color("#ffffff"), style: "arrow" });
  assert.equal(tokens.tick(1, true), false, "nothing moves");
  assert.deepEqual(standing(PACE), [0.25, 0.75]);
  assert.deepEqual(tokens.drawn, { beads: 2, heads: 2, chevrons: 0, streams: 0 }, "two beads stand on the lane that carries a bead and a quarter a second; the thin lane shows its arrowhead alone; the empty one nothing");
  assert.ok(near(placeOf(tokens.cores, 0).z, 0.75) && near(placeOf(tokens.cores, 1).z, 2.25));
  assert.ok(sizeOf(tokens.heads, 1) < sizeOf(tokens.heads, 0), "a thin stream's arrowhead is smaller");
  // A lane of a run that turns round starts empty: no bead is carried back.
  const moving = new Tokens({ lanes: [{ key: "k", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: 2, reverse: false }], radius: 0.1, ground: new THREE.Color("#ffffff"), style: "arrow" });
  assert.ok(moving.drawn.beads > 0);
  moving.setRate("k", 2, true);
  moving.tick(0);
  assert.equal(moving.drawn.beads, 0);
  moving.tick(0.6);
  assert.equal(moving.drawn.beads, 1);
  assert.ok(placeOf(moving.cores, 0).z > 1.5, "the first bead of the new way sets out from the far end");
});

test("the beads stay out of the look, cannot be chosen, and fade with the part of the picture they stand in", () => {
  const tokens = new Tokens({ lanes: [{ key: "k", path: straight(new THREE.Vector3(), new THREE.Vector3(1, 0, 0)), colour: new THREE.Color("#2a78d6"), perSecond: PACE, reverse: false }], radius: 0.1, ground: new THREE.Color("#ffffff") });
  for (const material of tokens.materials) {
    assert.equal(material.toneMapped, false, "filmic light leaves a bead's colour as the legend shows it");
    assert.equal(material.userData.noContact, true, "no contact shade");
    assert.equal(material.depthWrite, false);
    assert.equal(material.transparent, true, "drawn after what is solid, with what is see-through");
  }
  assert.equal(tokens.group.userData.unpickable, true);
  assert.deepEqual(tokens.shines, [tokens.cores, tokens.heads, tokens.flow.chevrons], "the beads, the arrowheads and the chevrons are what the bloom shines from; their rims are not");
  for (const material of tokens.flow.materials) assert.deepEqual([material.toneMapped, material.userData.noContact, material.depthWrite, material.transparent], [false, true, false, true], "the chevrons and the streams stay out of the look as the beads do");
  assert.equal(tokens.setFade(0.5), true);
  assert.equal(tokens.materials[0].opacity, 0.5);
  assert.equal(tokens.setFade(0), false);
  assert.equal(tokens.group.visible, false);
  const parent = new THREE.Group();
  parent.add(tokens.group);
  tokens.dispose();
  assert.equal(parent.children.length, 0);
});

// ------------------------------------------------------------ the lens's side

test("the page opens with nothing flowing: the switch off, no bloom asked for, the look's motion free", () => {
  const lens = lensFor(ILLUSTRATED);
  const { flux, stage } = lens;
  assert.equal(flux.on, false);
  assert.equal(flux.tokens.length, 0);
  assert.equal(flux.frame(), false);
  assert.deepEqual([stage.bloom, stage.blooms.length, stage.shining.size, stage.decoration.holds.size], [0, 0, 0, 0]);
  assert.ok(lens.labels.made.every((label) => label.hidden), "nothing is said on the picture");
  const legend = flux.legend();
  assert.equal(legend.title, "Flux");
  assert.equal(legend.example, null, "no notice while nothing shows");
  assert.deepEqual(legend.rows, [{ channel: "motion", label: "Show", options: [{ label: "Off", off: FLUX_SWITCH, on: true }, { id: FLUX_SWITCH, label: "All", on: false, title: "Show all that flows in this cell" }] }]);
  // The cell's own drops, signals and ions move at rest: the legend says beside the switch that it is the picture's own motion.
  assert.equal(legend.hint, `Or choose a part to see its flux. ${REST_WORDS}`);
  assert.equal(REST_WORDS, "What moves at rest is the picture's own, not a measured flow.");
  assert.deepEqual([legend.keys, legend.cannot, legend.time, legend.details], [[], [], null, null]);
  for (const part of ["water", "secretion", "channels", "pumps"]) assert.equal(flux.takes(part), false, "the picture's own drops, signals and ions are as they are");
  assert.equal(flux.flowing, false);
  // Where nothing may move, nothing is said of motion at rest.
  assert.equal(lensFor(ILLUSTRATED, { stage: stageOf({ moving: false }) }).flux.legend().hint, "Or choose a part to see its flux.");
});

test("at rest the cell's own drops, signals and ions move; while flux shows they hold where they stood, and the chosen part's give way", () => {
  const lens = lensFor(ILLUSTRATED);
  const cell = lens.cells[lens.sizeMode];
  Object.assign(lens, { clock: 0, fades: () => false, animate: (time, resting) => CellLens.prototype.animate.call(lens, time, resting) });
  const update = (ms) => CellLens.prototype.update.call(lens, ms);
  const drop = cell.streams[0].drops[0], signal = cell.signals[0], ion = cell.molecule.ions[0];
  const where = () => [drop, signal, ion].map((item) => item.position.toArray().map((value) => Number(value.toFixed(9))).join());
  assert.ok(drop && signal && ion, "the planarian's cell has drops, signals and a channel's ions");
  update(16);
  const first = where();
  assert.equal(update(100), true, "frames keep coming while they move");
  const moved = where();
  assert.ok(moved.every((at, k) => at !== first[k]), "at rest each moves");
  // A pump chosen: its flux shows. The other parts' tokens hold where they stood; none is hidden but the pump's own (it has none).
  lens.choose("cap.pumps");
  assert.equal(lens.flux.flowing, true);
  update(100);
  assert.deepEqual(where(), moved, "held while flux shows");
  assert.ok([drop, signal, ion].every((item) => item.visible));
  // Water chosen: its drops give way to the beads; the others still hold.
  lens.choose(lens.capabilityByPart.get("water").id);
  update(100);
  assert.deepEqual([drop.visible, signal.visible, ion.visible], [false, true, true]);
  assert.deepEqual(where().slice(1), moved.slice(1));
  // Nothing chosen: they move on from where they stood, by one frame and no more.
  lens.choose(null);
  update(16);
  const after = where();
  assert.ok(after.every((at, k) => at !== moved[k]) && drop.visible);
  const step = (a, b) => Math.hypot(...a.split(",").map((value, k) => Number(value) - Number(b.split(",")[k])));
  assert.ok(step(after[1], moved[1]) < step(moved[1], first[1]), "no jump: a frame of 16 ms moves a signal less than one of 100 ms did");
  // For a visitor who asks for less motion they stand, as before.
  lens.stage.reducedMotion = true;
  update(100);
  const still = where();
  update(100);
  assert.deepEqual(where(), still);
});

test("choosing a part shows that part's flux alone, with bloom, the look's motion held and the notice on the picture", () => {
  const lens = lensFor(ILLUSTRATED);
  const { flux, stage } = lens;
  lens.choose("cap.pumps");
  assert.equal(flux.on, false, "the switch stays off");
  assert.equal(flux.tokens.length, 1);
  assert.deepEqual(lanesOf(lens).map((item) => item.lane.key), ["pumps/sodium-potassium/sodium", "pumps/sodium-potassium/potassium", "pumps/sodium-potassium/sodium", "pumps/sodium-potassium/potassium", "pumps/calcium/calcium"]);
  assert.ok(lanesOf(lens).every((item) => item.perSecond === PACE), "one pace on every lane: the number of beads stands for no number");
  assert.equal(flux.tokens[0].tokens.group.parent, lens.zones[0].root, "the beads stand in the cell's own part of the picture");
  // Each ion in its own colour, as the bead layer has it; calcium, with no colour of its own, in the neutral tone.
  assert.deepEqual(lanesOf(lens).slice(1, 2).concat(lanesOf(lens).slice(0, 1), lanesOf(lens).slice(4)).map((item) => `#${item.colour.getHexString()}`), ["#2a78d6", "#eb6834", "#6e6a64"]);
  // Bloom on what is marked to shine, and the look's own motion held, for as long as it shows.
  assert.equal(stage.bloom, BLOOM);
  assert.deepEqual([...stage.shining], flux.tokens[0].tokens.shines);
  assert.deepEqual([...stage.decoration.holds], ["flux"]);
  // The picture says what it is.
  const [notice, lines] = lens.labels.made;
  assert.deepEqual([notice.text, notice.hidden], ["Illustration: not a run", false]);
  assert.deepEqual([lines.text, lines.hidden], ["Direction only: the number of beads and their pace stand for no number", false]);
  assert.match(notice.kind, /label-example/);
  // The picture's own tokens of that part give way; the others stand.
  assert.equal(flux.takes("pumps"), true);
  assert.equal(flux.takes("water"), false);
  // The legend: the notice, the ions by name, what a bead stands for, whose word the direction is, and where a lane runs.
  const legend = flux.legend();
  assert.equal(legend.example, "Illustration: not a run");
  assert.equal(legend.rows[0].options[0].on, true, "Off stays pressed: the part was chosen, not the switch");
  assert.deepEqual(legend.keys.map((item) => item.key), ["ions", "bead", "bead", "way", "head", "pump"]);
  assert.deepEqual(legend.keys[0].chips, [{ label: "Na", colour: "#eb6834" }, { label: "K", colour: "#2a78d6" }, { label: "Ca", colour: "#6e6a64" }]);
  assert.equal(legend.keys[1].text, "Sodium and potassium wear their own colours. Every other bead wears one neutral tone and is told by the part it passes");
  assert.equal(legend.keys[2].text, "Direction only: the number of beads and their pace stand for no number");
  assert.equal(legend.keys[3].text, "A lane that goes one way goes as a law of the engine declares for that part; the panel names the law");
  assert.equal(legend.keys[5].text, "Where a lane runs is the picture's choice: the engine has no place for a single channel or pump");
  assert.equal(legend.details, null, "the chosen part's own panel says what stands behind it");
  assert.equal(legend.time, null, "no slow-down: an illustration keeps no time");
  // The part's panel carries the notice too, and the basis of each direction.
  const panel = flux.inPanel(lens.model.get("cap.pumps"));
  const section = panel.sections.at(-1);
  assert.equal(section.title, "Flux. Illustration: not a run");
  assert.deepEqual(section.items.map((item) => item.label), ["Ions through the pumps: Sodium–potassium pump", "Ions through the pumps: Calcium pump"]);
  assert.equal(section.items[0].detail, "sodium, out of the cell; potassium, into the cell");
  assert.match(section.items[0].lines[1], /^Basis: the engine's law nak_atp_mass_action_positive@1, read in src\/cells\/processes\/kinetic_pump\.py at main /);
  assert.match(section.items[1].lines[1], /ca_atp_mass_action_positive@1/);
  // Choosing nothing again: all of it goes, and the stage is as it was.
  lens.choose(null);
  assert.equal(flux.tokens.length, 0);
  assert.deepEqual([stage.bloom, stage.shining.size, stage.decoration.holds.size], [0, 0, 0]);
  assert.ok(lens.labels.made.every((label) => label.hidden));
  assert.equal(lens.zones[0].root.children.length, 0);
  assert.ok(lens.chromes >= 2, "the page was told each time what shows changed");
});

test("a part that the page's address names is chosen as the page opens and shows no flux until the visitor chooses", () => {
  const lens = lensFor(ILLUSTRATED);
  const { flux, stage } = lens;
  // The viewer chooses the part the address names, then tells the view that the choice was the address's.
  lens.selected = "cap.pumps";
  flux.refresh();
  flux.hold("cap.pumps");
  assert.equal(flux.tokens.length, 0, "nothing flows as the page opens");
  assert.deepEqual([stage.bloom, stage.shining.size, stage.decoration.holds.size], [0, 0, 0]);
  assert.ok(lens.labels.made.every((label) => label.hidden), "and the picture says nothing of flux");
  assert.equal(flux.legend().example, null);
  assert.equal(flux.legend().hint, `Or choose a part to see its flux. ${REST_WORDS}`);
  assert.equal(flux.takes("pumps"), false);
  // The part's panel still says what would flow through it, and on what basis.
  assert.equal(flux.inPanel(lens.model.get("cap.pumps")).sections.at(-1).title, "Flux. Illustration: not a run");
  // The colours or the size mode may change meanwhile: still nothing flows.
  flux.refresh(true);
  assert.equal(flux.tokens.length, 0);
  // The visitor chooses another part: its flux shows. And the first again: it shows as any chosen part does.
  lens.choose("cap.water");
  assert.deepEqual([...new Set(lanesOf(lens).map((item) => item.lane.key.split("/")[0]))], ["water"]);
  lens.choose("cap.pumps");
  assert.deepEqual([...new Set(lanesOf(lens).map((item) => item.lane.key.split("/")[0]))], ["pumps"]);
  // Or the visitor chooses nothing and then the same part again.
  const again = lensFor(ILLUSTRATED);
  again.selected = "cap.pumps";
  again.flux.hold("cap.pumps");
  again.choose(null);
  again.choose("cap.pumps");
  assert.equal(again.flux.tokens.length, 1);
  // Or presses the name of the very part the address chose: the viewer says that a choice was made, and sets the same one.
  const same = lensFor(ILLUSTRATED);
  same.selected = "cap.pumps";
  same.flux.hold("cap.pumps");
  same.flux.refresh(); // the view is shown again, or its species changes: no choice of the visitor's, and nothing flows
  assert.equal(same.flux.tokens.length, 0);
  same.flux.release();
  same.choose("cap.pumps");
  assert.equal(same.flux.tokens.length, 1);
  // Or presses the switch: from then on the part, still chosen, shows alone as any chosen part does.
  const pressed = lensFor(ILLUSTRATED);
  pressed.selected = "cap.pumps";
  pressed.flux.hold("cap.pumps");
  assert.equal(pressed.flux.tokens.length, 0);
  pressed.flux.setOn(true);
  assert.deepEqual([...new Set(lanesOf(pressed).map((item) => item.lane.key.split("/")[0]))], ["pumps"]);
  pressed.flux.setOn(false);
  assert.equal(pressed.flux.tokens.length, 1, "the chosen part goes on showing: the visitor has chosen");
  // An address that names nothing holds nothing.
  const plain = lensFor(ILLUSTRATED);
  plain.flux.hold(null);
  plain.choose("cap.pumps");
  assert.equal(plain.flux.tokens.length, 1);
});

test("a statement has room on a row where no card lies, as near to where it was wanted as can be", () => {
  const legend = { left: 16, top: 330, right: 252, bottom: 884 }, panel = { left: 1024, top: 64, right: 1384, bottom: 884 };
  const row = { width: 1400, blocked: [legend, panel], top: 550, tall: 18 };
  // Wanted at 448 and 400 wide, it would start four pixels under the legend: it moves ten along, to stand six clear.
  assert.equal(fitOnRow({ ...row, wide: 400, wanted: 448 }), 252 + 6 + 200);
  assert.equal(fitOnRow({ ...row, wide: 400, wanted: 640 }), 640, "with room where it is wanted, it stays");
  assert.equal(fitOnRow({ ...row, wide: 400, wanted: 1300 }), 1024 - 6 - 200, "and it stands clear of the panel as well");
  assert.equal(fitOnRow({ ...row, wide: 800, wanted: 448 }), null, "no room between the two cards for one this wide");
  // A row above the legend: only the panel lies there.
  assert.equal(fitOnRow({ ...row, top: 200, wide: 400, wanted: 100 }), 6 + 200);
  assert.equal(fitOnRow({ width: 400, blocked: [], top: 0, tall: 10, wide: 500, wanted: 200 }), null, "wider than the window");
  // The same for a label that follows a point of the scene: its point is moved, along its row or up, never cut.
  const camera = new THREE.PerspectiveCamera(34, 1400 / 900, 0.1, 5000);
  camera.position.set(0, 220, 200);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const stage = { width: 1400, height: 900, camera, project: (point, out) => (out.copy(point).project(camera), (out.x = (out.x * 0.5 + 0.5) * 1400), (out.y = (-out.y * 0.5 + 0.5) * 900), out) };
  const home = new THREE.Vector3(-60, 0, 40), natural = stage.project(home, new THREE.Vector3());
  const placed = (blocked, wide) => stage.project(clearOf({ stage, blocked, home, wide, tall: 18, lift: 0, out: new THREE.Vector3() }), new THREE.Vector3());
  const column = { left: 0, top: 56, right: natural.x - 150, bottom: 900 };
  assert.ok(placed([column], 200).distanceTo(natural) < 1e-6, "clear of the card: it stays at home");
  const moved = placed([column], 400);
  assert.ok(near(moved.x - 200, natural.x - 150 + 6, 1e-6) && Math.abs(moved.y - natural.y) < 1e-6, "its start would lie under the card: it moves along its row until it stands clear");
  assert.ok(near(moved.z, natural.z, 1e-6), "at the same depth");
  const lifted = placed([{ left: 0, top: natural.y - 40, right: 1400, bottom: 900 }], 400);
  assert.ok(lifted.y <= natural.y - 40 - 6 + 1e-6 && lifted.y > natural.y - 80 && Math.abs(lifted.x - natural.x) < 1e-6, `no room on its row: it moves up, over the card (${lifted.y} from ${natural.y})`);
  assert.ok(placed([{ left: 0, top: 0, right: 1400, bottom: 900 }], 400).distanceTo(natural) < 1e-6, "no room anywhere: it stays at home");
});

test("the Flux switch shows all of it under one legend, and a panel says what stands behind it", () => {
  const lens = lensFor(ILLUSTRATED);
  const { flux } = lens;
  flux.setOn(true);
  const keys = lanesOf(lens).map((item) => item.lane.key.split("/")[0]);
  const count = (kind) => keys.filter((key) => key === kind).length;
  // Six channels and two water corners with a lane each way, five lanes at the three pumps, two at the junction, two for signals.
  assert.deepEqual(["channels", "pumps", "junctions", "water", "secretion"].map(count), [12, 5, 2, 4, 2]);
  assert.equal(new Set(lanesOf(lens).map((item) => item.key)).size, 25, "each lane has a name of its own");
  const legend = flux.legend();
  assert.equal(legend.rows[0].options[1].on, true);
  assert.equal(legend.example, "Illustration: not a run");
  assert.deepEqual(legend.keys.map((item) => item.key), ["ions", "bead", "bead", "way", "way", "head", "pump"]);
  assert.equal(legend.keys[4].text, "Two lanes side by side, one each way: no direction is claimed. Which way more goes depends on the cell's state, which only a run knows");
  // Rule 8: sodium and potassium in their own colours, and every other bead in the one neutral tone. No hue of the
  // cell picture (its blue for water, say) is put beside them: only those colours were validated together.
  const tones = new Map();
  for (const item of lanesOf(lens)) tones.set(`#${item.colour.getHexString()}`, (tones.get(`#${item.colour.getHexString()}`) || 0) + 1);
  assert.deepEqual([...tones].sort(), [["#2a78d6", 2], ["#6e6a64", 21], ["#eb6834", 2]]);
  assert.deepEqual(legend.cannot.map((item) => [item.id, item.label]), [["fuel", "Fuel (ATP)"]]);
  assert.equal(legend.compact, "What the beads mean", "the view's card stands just above the legend: the signs, what is not drawn and the door to the panel keep to one line");
  assert.equal(legend.details, FLUX_PANEL);
  // The panel: what is drawn with each basis, what is not and why, the laws as cited, and the two forms.
  assert.equal(flux.has(FLUX_PANEL), true);
  const panel = flux.describe(FLUX_PANEL);
  assert.equal(panel.chips[0].label, "Illustration: not a run");
  assert.match(panel.plain, /^Illustration: not a run\. Human has no looping run of its own cell, so what flows is shown as illustration\. Direction only: /);
  assert.equal(panel.note, declarations.illustration.speaks_for);
  assert.deepEqual(panel.sections.map((section) => section.title), ["Drawn", "Not drawn", "The laws the directions are drawn from", "The two forms of illustration"]);
  assert.deepEqual(panel.sections[0].items.map((item) => item.label), ["Ions through the channels: Ions", "Ions through the pumps: Sodium–potassium pump", "Ions through the pumps: Calcium pump", "Exchange with neighbours: Ions", "Water", "Secreted signals: Signals"]);
  assert.deepEqual(panel.sections[1].items.map((item) => item.label), ["Fuel (ATP)"]);
  assert.deepEqual(panel.sections[2].items.map((item) => item.label), ["nak_atp_mass_action_positive@1", "ca_atp_mass_action_positive@1", "scheduled_species_exchange@1"]);
  assert.match(panel.sections[2].items[0].detail, /^src\/cells\/processes\/kinetic_pump\.py at main [0-9a-f]{8}$/);
  assert.match(panel.sections[3].items[1].lines[0], /None is entered yet, so this form is not offered\.$/);
  // With the switch on, a chosen part shows alone; choosing a part nothing flows through leaves all of it.
  lens.choose("cap.water");
  assert.deepEqual([...new Set(lanesOf(lens).map((item) => item.lane.key.split("/")[0]))], ["water"]);
  assert.equal(flux.takes("water"), true);
  assert.equal(flux.takes("channels"), false);
  lens.choose("cap.circuits");
  assert.equal(lanesOf(lens).length, 25);
  // Fuel, chosen: nothing is drawn, and the legend and its panel say why.
  lens.choose("cap.energy");
  assert.equal(flux.tokens.length, 0);
  assert.equal(flux.legend().example, null, "nothing shows, so nothing is marked as illustration");
  assert.match(flux.legend().cannot[0].why, /^Nothing is drawn for fuel\./);
  assert.equal(flux.inPanel(lens.model.get("cap.energy")).sections.at(-1).items[0].label, "Fuel (ATP): not drawn");
  flux.setOn(false);
  lens.choose(null);
  assert.equal(flux.tokens.length, 0);
});

test("for a visitor who asks for less motion the beads stand, and the picture and the legend say so", () => {
  const lens = lensFor(ILLUSTRATED, { stage: stageOf({ moving: false }) });
  const { flux, stage } = lens;
  flux.setOn(true);
  const tokens = flux.tokens[0].tokens;
  assert.equal(flux.advance(2), false, "nothing moves");
  assert.deepEqual(tokens.drawn, { beads: 50, heads: 0, chevrons: 75, streams: 0 }, "two beads stand on each lane, and each lane has its chevrons, which stand too and point its way");
  assert.equal(lens.labels.made[1].text, "Direction only: the number of beads and their pace stand for no number · shown still");
  assert.equal(flux.legend().keys.at(-2).text, STILL_WORDS);
  assert.deepEqual([...stage.decoration.holds], ["flux"], "the look's own motion is held all the same");
  // The statement keeps its place on the screen wherever the camera looks: under the top bar, in the middle.
  const foot = (label, lens_) => {
    const point = label.anchor.clone().project(lens_.stage.camera);
    return [Math.round(((point.x + 1) / 2) * lens_.stage.width), Math.round(((1 - point.y) / 2) * lens_.stage.height)];
  };
  const [notice, lines] = lens.labels.made;
  assert.deepEqual(foot(notice, lens), [640, STATEMENT.top + 18], "a label stands just above its point: the notice's foot");
  assert.deepEqual(foot(lines, lens), [640, STATEMENT.top + 18 + STATEMENT.gap + 18], "the lines under it");
  stage.camera.position.set(30, 12, -44);
  stage.camera.lookAt(3, 1, 2);
  stage.camera.updateMatrixWorld();
  flux.advance(0);
  assert.deepEqual(foot(notice, lens), [640, STATEMENT.top + 18]);
  assert.equal(notice.boost, 1000, "it gives way to no other label");
});

test("the statement is said in the fewest lines that have room between the cards, and is never put under them", () => {
  const foot = (label, lens) => {
    const point = label.anchor.clone().project(lens.stage.camera);
    return [Math.round(((point.x + 1) / 2) * lens.stage.width), Math.round(((1 - point.y) / 2) * lens.stage.height)];
  };
  /** The statement as it stands with these cards over the picture: its two labels, and where their feet lie. */
  const shown = (lens, blocked) => {
    lens.labels.blocked = () => blocked;
    lens.flux.setOn(true);
    const [notice, lines] = lens.labels.made;
    return { notice, lines, at: [foot(notice, lens), foot(lines, lens)] };
  };
  const whole = "Direction only: the number of beads and their pace stand for no number";
  const inTwo = "Direction only: the number of beads\nand their pace stand for no number";
  const card = { left: 16, top: 64, right: 252, bottom: 250 };
  // A wide window: the view's card at the left, the rail at the right's middle. The middle of the window is free at the top.
  let said = shown(lensFor(ILLUSTRATED), [card, { left: 1180, top: 300, right: 1264, bottom: 500 }]);
  assert.equal(said.lines.text, whole);
  assert.deepEqual(said.at, [[640, STATEMENT.top + 18], [640, STATEMENT.top + 18 + STATEMENT.gap + 18]]);
  // A part's panel open at the right: the statement moves aside as little as will do, and stays whole.
  said = shown(lensFor(ILLUSTRATED), [card, { left: 888, top: 64, right: 1264, bottom: 780 }]);
  assert.equal(said.lines.text, whole);
  assert.equal(said.at[0][0], 888 - STATEMENT.margin - said.lines.width / 2);
  // Less room between the two cards than the whole line needs: it is said in two lines.
  said = shown(lensFor(ILLUSTRATED), [card, { left: 700, top: 64, right: 1264, bottom: 780 }]);
  assert.equal(said.lines.text, inTwo);
  assert.ok(Math.abs(said.at[0][0] - (700 - STATEMENT.margin - said.lines.width / 2)) <= 1 && said.at[0][1] === STATEMENT.top + 18);
  // A phone: the view's card takes the top left and the rail the right from 124 px down. Beside the card there is
  // no room, so the statement stands under the card, in two lines, over the top of the picture; never in the foot.
  const phone = () => lensFor(ILLUSTRATED, { stage: stageOf({ width: 400, height: 780 }) });
  const small = { left: 16, top: 54, right: 224, bottom: 196 }, rail = { left: 316, top: 124, right: 390, bottom: 262 }, toggle = { left: 16, top: 716, right: 130, bottom: 764 };
  said = shown(phone(), [small, rail, toggle]);
  assert.equal(said.lines.text, inTwo);
  assert.ok(said.at[0][1] - 18 >= 196 + STATEMENT.margin && said.at[1][1] < 300, `under the card (${said.at})`);
  assert.ok(said.at[1][0] + said.lines.width / 2 <= 316 - STATEMENT.margin + 1 && said.at[1][0] - said.lines.width / 2 >= STATEMENT.margin - 1, "clear of the rail and of the window's edge");
  assert.deepEqual([said.notice.hidden, said.lines.hidden], [false, false]);
  // The phone with a part's panel open: the panel is a sheet over the lower half, and the card and the legend are away.
  said = shown(phone(), [rail, { left: 0, top: 345, right: 400, bottom: 780 }]);
  assert.equal(said.lines.text, inTwo);
  assert.ok(said.at[1][1] <= 345 - STATEMENT.margin && said.at[0][1] - 18 >= STATEMENT.top, `above the panel (${said.at})`);
  // The phone with its legend opened over the picture: no room is left, and the statement is not put under the cards
  // in pieces. The legend in front carries the notice.
  const covered = phone();
  said = shown(covered, [small, rail, { left: 16, top: 181, right: 384, bottom: 764 }]);
  assert.deepEqual([said.notice.hidden, said.lines.hidden], [true, true]);
  assert.equal(covered.flux.legend().example, "Illustration: not a run");
  // The legend closed again: the statement is back.
  covered.labels.blocked = () => [small, rail, toggle];
  covered.flux.advance(0);
  assert.deepEqual([said.notice.hidden, said.lines.hidden, said.lines.text], [false, false, inTwo]);
  // A window 800 wide with the view's card, the legend and a part's panel all open: between the card and the panel
  // 160 px are left, less than the statement needs in any of its ways. It is not shown on the picture there; the
  // legend and the panel, which lie in front, carry the notice. (Rule 11 asks for it on the picture: reported.)
  const tight = lensFor(ILLUSTRATED, { stage: stageOf({ width: 800, height: 700 }) });
  said = shown(tight, [{ left: 16, top: 64, right: 252, bottom: 218 }, { left: 16, top: 226, right: 252, bottom: 684 }, { left: 424, top: 64, right: 784, bottom: 684 }]);
  assert.deepEqual([said.notice.hidden, said.lines.hidden], [true, true]);
  assert.equal(tight.flux.legend().example, "Illustration: not a run");
  assert.equal(tight.flux.inPanel(tight.model.get("cap.pumps")).sections.at(-1).title, "Flux. Illustration: not a run");
  // A window narrower still: short lines.
  said = shown(lensFor(ILLUSTRATED, { stage: stageOf({ width: 270, height: 600 }) }), []);
  assert.equal(said.lines.text, "Direction only:\nthe number of beads and their pace\nstand for no number");
  assert.deepEqual([said.notice.hidden, said.lines.hidden], [false, false]);
  // Where nothing may move the last line says so, in every way of breaking it.
  const still = lensFor(ILLUSTRATED, { stage: stageOf({ moving: false, width: 270, height: 600 }) });
  assert.equal(shown(still, []).lines.text, "Direction only:\nthe number of beads and their pace\nstand for no number\nshown still");
});

test("the beads move in the time that passed, fade with the cell, and leave with the view", () => {
  const lens = lensFor(ILLUSTRATED);
  const { flux, stage } = lens;
  lens.choose("cap.channels");
  const tokens = flux.tokens[0].tokens;
  assert.equal(flux.advance(0.4), true);
  const first = tokens.lanes[0].beads.slice();
  flux.advance(0.4);
  const onward = first.filter((share) => share + 0.4 / CROSSING < 1);
  assert.ok(onward.length > 0 && onward.every((share) => tokens.lanes[0].beads.some((now) => near(now, share + 0.4 / CROSSING, 1e-9))), "a bead is a quarter of its way further after a quarter of a crossing");
  // Zoomed out to the tissue the cell's own picture fades, and its beads with it.
  lens.zones[0].fade = 0;
  assert.equal(flux.advance(0.1), false);
  assert.equal(tokens.group.visible, false);
  lens.zones[0].fade = 1;
  flux.advance(0.1);
  assert.equal(tokens.group.visible, true);
  // Another view is shown: the bloom and the hold go with this one, and come back with it.
  lens.active = false;
  flux.shine();
  assert.deepEqual([stage.bloom, stage.shining.size, stage.decoration.holds.size], [0, 0, 0]);
  lens.active = true;
  flux.refresh();
  assert.deepEqual([stage.bloom, stage.shining.size, [...stage.decoration.holds]], [BLOOM, 3, ["flux"]], "the beads, the arrowheads and the chevrons shine");
  // The colours follow the page's theme: the rims take the dark ground.
  stage.palette = { ...stage.palette, bg: "#0b151e", dark: true };
  flux.refresh();
  assert.equal(`#${flux.tokens[0].tokens.ground.getHexString()}`, "#0b151e");
  // The lens takes its picture down (another species): the beads go first.
  flux.clear();
  assert.equal(flux.tokens.length, 0);
  assert.equal(stage.bloom, 0);
});

test("every species goes through its own file: what its cell lacks is never offered", () => {
  // Thale cress: its pumps are chosen, and nothing is drawn; the legend gives the reason in its file's words.
  const cress = lensFor("thalecress");
  cress.choose("cap.pumps");
  assert.equal(cress.flux.tokens.length, 0);
  const legend = cress.flux.legend();
  assert.equal(legend.example, null);
  assert.deepEqual(legend.cannot.map((item) => item.label), ["Sodium–potassium pump", "Calcium pump"]);
  assert.deepEqual([legend.compact, legend.hint, legend.keys], ["Why nothing is drawn here", REST_WORDS, []], "nothing flows, so the cell's own tokens move, and the legend says what that motion is");
  assert.match(legend.cannot[0].why, /^No direction is drawn for Thale cress: its file says of its own part, “Not the sodium-potassium pump of animal cells/);
  assert.deepEqual(cress.flux.inPanel(cress.model.get("cap.pumps")).sections.at(-1).items.map((item) => item.label), ["Sodium–potassium pump: not drawn", "Calcium pump: not drawn"]);
  cress.choose(null);
  cress.flux.setOn(true);
  assert.deepEqual([...new Set(lanesOf(cress).map((item) => item.lane.key.split("/")[0]))], ["channels", "water", "secretion"]);
  assert.equal(cress.flux.legend().cannot.length, 3);
  // JCVI-syn3A: no ion channel, no junction; nothing of it is in the engine, so no lane claims a direction.
  const minimal = lensFor("syn3a");
  minimal.flux.setOn(true);
  assert.deepEqual([...new Set(lanesOf(minimal).map((item) => item.lane.key.split("/")[0]))], ["water", "secretion"]);
  assert.ok(lanesOf(minimal).every((item) => item.lane.claimed === false));
  assert.deepEqual(minimal.flux.legend().keys.map((item) => item.key), ["bead", "bead", "way", "head", "pump"]);
  assert.match(minimal.flux.legend().keys[0].text, /^Sodium and potassium wear their own colours\. Every other bead wears one neutral tone/);
  assert.equal(minimal.flux.inPanel(minimal.model.get("cap.channels")), minimal.model.get("cap.channels"), "a part the species lacks gets no word of flux");
  assert.equal(minimal.flux.describe(FLUX_PANEL).sections.find((section) => section.title === "The laws the directions are drawn from"), undefined, "no law is cited where none is drawn from");
  // Every species, every size mode it is drawn in: the switch draws what the plan says and nothing else.
  for (const id of SPECIES) {
    const first = lensFor(id);
    for (const mode of first.modes) {
      const lens = mode === first.sizeMode ? first : lensFor(id, { mode });
      lens.flux.setOn(true);
      const drawn = [...new Set(lanesOf(lens).map((item) => item.lane.key.split("/")[0]))].sort();
      assert.deepEqual(drawn, kindsOf(lens.flux.plan).sort(), `${id}, ${mode}`);
      for (const kind of drawn) assert.ok(lens.draws(lens.flux.plan.kinds.find((item) => item.id === kind).part), `${id}: ${kind}`);
      for (const set of lens.flux.tokens) assert.ok(set.tokens.drawn.beads > 0 && set.tokens.drawn.chevrons === set.lanes.length * CHEVRONS, "every lane has its chevrons");
    }
  }
});

test("drawn to scale, lanes of the channel's own size stand in the close-up, where the cell's own lanes fade", () => {
  const lens = lensFor(ILLUSTRATED, { mode: "real" });
  assert.equal(lens.sizeMode, "real");
  lens.choose("cap.channels");
  assert.equal(lens.flux.tokens.length, 2);
  const [wide, close] = lens.flux.tokens;
  assert.equal(wide.zone.name, "cell");
  assert.equal(close.zone.name, "molecules");
  assert.deepEqual([wide.lanes.length, close.lanes.length], [12, 2]);
  const nm = 0.001 / lens.cells.real.frame.u;
  assert.ok(near(close.tokens.radius, 0.3 * nm));
  const [inward, outward] = close.lanes;
  assert.ok(near(inward.path(0).distanceTo(inward.path(1)), 22 * nm, 1e-6), "through the channel, 22 nm from end to end");
  assert.ok(near(inward.path(0.5).distanceTo(outward.path(0.5)), 0.7 * nm, 1e-6));
  assert.deepEqual([inward.reverse, outward.reverse], [false, true]);
  // The camera close: the cell's own lanes fade with the membrane's dots; far: the close-up's fade with the close-up.
  lens.dustFade = 0;
  lens.flux.advance(0.1);
  assert.deepEqual([wide.tokens.group.visible, close.tokens.group.visible], [false, true]);
  lens.dustFade = 1;
  close.zone.fade = 0;
  lens.flux.advance(0.1);
  assert.deepEqual([wide.tokens.group.visible, close.tokens.group.visible], [true, false]);
  // A species without ion channels has no such close-up of one.
  const minimal = lensFor("syn3a");
  minimal.flux.setOn(true);
  assert.equal(minimal.flux.tokens.length, 1);
});

test("drawn to scale, the close-up's pump has lanes of its own size, over the pump where the cell's builder stands it", () => {
  const lens = lensFor(ILLUSTRATED, { mode: "real" });
  lens.choose("cap.pumps");
  assert.equal(lens.flux.tokens.length, 2);
  const [wide, close] = lens.flux.tokens;
  assert.deepEqual([wide.zone.name, close.zone.name], ["cell", "molecules"]);
  // The close-up has one pump: the sodium–potassium pump's two lanes stand there, sodium out and potassium in, by the engine's law.
  assert.deepEqual(close.lanes.map((item) => [item.lane.key, item.reverse]), [["pumps/sodium-potassium/sodium", true], ["pumps/sodium-potassium/potassium", false]]);
  const nm = 0.001 / lens.cells.real.frame.u;
  assert.ok(near(close.tokens.radius, 0.3 * nm));
  // Where the builder stands the pump: its lobes, recorded as it adds them.
  const lobes = [], recording = context(), made = recording.part;
  recording.part = (name, anchor) => {
    const part = made(name, anchor);
    if (name === "pumps") part.add = (mesh) => lobes.push(mesh.position.clone());
    return part;
  };
  buildMolecules(recording, "real", lens.cells.real.frame, lens.draws);
  assert.equal(lobes.length, 3, "the builder's pump has three lobes");
  const middle = close.lanes[0].path(0.5).add(close.lanes[1].path(0.5)).multiplyScalar(0.5);
  assert.ok(Math.hypot(middle.x - lobes[0].x, middle.z - lobes[0].z) < 0.01 * nm, `the lanes cross the membrane where the pump's main lobe stands (${CLOSE_PUMP.beside} nm from the channel)`);
  assert.ok(near(middle.y - lobes[0].y, (CLOSE_PUMP.over - 0.5) * nm, 1e-6), "over its lobes, clear of them");
  assert.ok(near(close.lanes[0].path(0).distanceTo(close.lanes[0].path(1)), 22 * nm, 1e-6), "22 nm from end to end, as through the channel");
  assert.ok(near(close.lanes[0].path(0.5).distanceTo(close.lanes[1].path(0.5)), CLOSE_PUMP.pitch * nm, 1e-6));
  // All of it: the channel's lanes and the pump's share the close-up.
  lens.choose(null);
  lens.flux.setOn(true);
  const near_ = lens.flux.tokens.find((set) => set.zone.name === "molecules");
  assert.deepEqual(near_.lanes.map((item) => item.lane.key), ["channels/ions/in", "channels/ions/out", "pumps/sodium-potassium/sodium", "pumps/sodium-potassium/potassium"]);
  // Thale cress: the engine's pump law does not speak for its pumps, so the close-up has no pump lanes.
  const cress = lensFor("thalecress", { mode: "real" });
  cress.flux.setOn(true);
  assert.ok(!cress.flux.tokens.some((set) => set.lanes.some((item) => item.lane.key.startsWith("pumps/"))));
});

// ------------------------------------------------------------ a species' looping run (rule 7), against a fixture made here

// The fixture is test-only: the example sheet of the run-fixture tool, packaged by the run adapter as the page
// gets its runs, and then, in memory, given what a loop of the engine would say of itself. Nothing of it is
// written where the page could find it. Its numbers are invented; here they only stand in for a run's.
const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-flux-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const FIXTURES = path.join(scratch, "fixtures"), PACKAGED = path.join(scratch, "out");
for (const [tool, args] of [["make_run_fixture.py", ["--out", FIXTURES]], ["adapt_run.py", ["--evidence", FIXTURES, "--overlay", path.join(FIXTURES, "overlay.json"), "--selection", path.join(FIXTURES, "selection.json"), "--out", PACKAGED]]]) {
  const done = spawnSync("python3", [path.join(ROOT, "tools", tool), ...args], { encoding: "utf8" });
  assert.equal(done.status, 0, `${tool} failed:\n${done.stderr}`);
}
const SHEET = "example-sheet--invented-numbers";
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const CATALOGUE = readJson(path.join(PACKAGED, "index.json"));
const CLOSES = { within: 1e-9, tolerance: 1e-6, says: "The fixture's last record is taken to meet its first." };
/** The packaged example (or another packaged fixture), opened with every record read in; `change(view)` makes it say what a loop would. */
async function opened(change = null, id = SHEET) {
  const file = readJson(path.join(PACKAGED, `${id}.json`));
  const parts = Object.fromEntries((file.view.parts || []).map((part) => [part.id, readJson(path.join(PACKAGED, path.basename(part.file)))]));
  if (change) change(file.view);
  const run = openReplay(file, CATALOGUE.runs.find((row) => row.id === id));
  const fetcher = async (url) => {
    const part = Object.values(parts).find((item) => url.endsWith(`.${item.part}.json`));
    return { ok: Boolean(part), status: part ? 200 : 404, json: async () => part };
  };
  for (const part of Object.keys(parts)) await loadPart(run, part, { root: null, fetcher });
  return run;
}
/** What the fixture says to be read as a loop of the planarian's cell: no longer an example, a model and a revision named, the loop declared. */
const asLoop = (cell, more = {}) => (view) => {
  delete view.example;
  view.run.engine_models = ["fixture_model@1"];
  view.run.revision = "0000000";
  view.loop = { species: "planarian", cell, period: view.run.end_s, closes: CLOSES, ...more };
};
/** A cell of the sheet's written disc, where every stream runs. */
const discOf = (run) => run.sets.get("cell").ids.findIndex((_, cell) => run.records.get("vm").at(0, cell) > -0.05);

test("a run is read as a species' loop only where it says so, names the engine, and says that it closes", async () => {
  const plain = await opened();
  assert.deepEqual(readLoop(plain, "planarian"), { ok: false, why: "The run does not say that it is a loop." });
  const cell = plain.sets.get("cell").ids[discOf(plain)];
  // An example's numbers are invented: it is no species' run, whatever it says of looping.
  const example = await opened((view) => (view.loop = { species: "planarian", cell, closes: CLOSES }));
  assert.match(readLoop(example, "planarian").why, /^The run is an example with invented numbers/);
  const run = await opened(asLoop(cell));
  const read = readLoop(run, "planarian");
  assert.equal(read.ok, true);
  assert.deepEqual([read.loop.name, read.loop.species, read.loop.models, read.loop.revision], [SHEET, "planarian", ["fixture_model@1"], "0000000"]);
  assert.equal(read.loop.cell, discOf(run));
  assert.equal(run.sets.get("membrane").geometry.index[read.loop.membrane], read.loop.cell, "the membrane read is the one on the loop's cell");
  assert.deepEqual([read.loop.start, read.loop.length], [run.start, run.end - run.start]);
  assert.deepEqual(read.loop.closes, CLOSES);
  assert.equal(loopWords(read.loop, "Planarian", clock), `Planarian · the engine's looping run ${SHEET} · a loop of ${clock(run.end - run.start)} of the cell's time`);
  // Refused, each with its reason.
  assert.match(readLoop(run, "human").why, /^The run is the loop of another species' cell \(planarian\)\.$/);
  assert.match(readLoop(await opened(asLoop("no-such-cell")), "planarian").why, /^The run has no cell called no-such-cell\.$/);
  assert.match(readLoop(await opened(asLoop(cell, { closes: undefined })), "planarian").why, /does not say that its end meets its start/);
  assert.match(readLoop(await opened(asLoop(cell, { closes: { within: 1e-9, says: "said" } })), "planarian").why, /does not say that its end meets its start within a tolerance/, "the block the engine writes declares its tolerance");
  assert.equal(readLoop(await opened(asLoop(cell, { closes: { within: 2e-6, tolerance: 1e-6, says: "said" } })), "planarian").why, "The run's last record meets its first within 2.0e-6, above its own tolerance of 1.0e-6: it is not played as a loop.");
  // The period is the loop's length, and must be the records' span.
  assert.equal(read.loop.length, run.end - run.start);
  assert.match(readLoop(await opened(asLoop(cell, { period: 11 })), "planarian").why, /^The run's loop gives a period of 11, and its records span 12 s: they must be the same\.$/);
  assert.match(readLoop(await opened(asLoop(cell, { period: undefined })), "planarian").why, /gives a period of none/);
  assert.equal(closesWords(read.loop), "Its last record meets its first within 1.0e-9 (tolerance 1.0e-6)");
  assert.deepEqual([read.loop.notMeasured, read.loop.zero], [[], []], "a loop that names nothing left out has nothing to say of it");
  // The block the engine's writer builds names what its closure leaves out, by reason, and the records identically zero:
  // both are said with the closure, in the run's words, so a running total is never read as one that meets itself.
  const totals = { why: "cumulative totals: they grow by design, so the reader differences them inside the loop", records: ["observed_membrane_transferred", "observed_pump_cycles"] };
  const measured = readLoop(await opened(asLoop(cell, { closes: { ...CLOSES, zero: ["observed_cell_potential_V"] }, not_measured: [totals] })), "planarian");
  assert.equal(measured.ok, true);
  assert.deepEqual([measured.loop.notMeasured, measured.loop.zero], [[totals], ["observed_cell_potential_V"]]);
  assert.equal(closesWords(measured.loop), `Its last record meets its first within 1.0e-9 (tolerance 1.0e-6), in the records it measures; of its records, 2 are not measured (${totals.why}); 1 is identically zero over the loop`);
  // The revision: the package's own, or where it carries the engine's source instead, that one, with its dirty flag.
  const sourced = readLoop(await opened((view) => {
    asLoop(cell)(view);
    delete view.run.revision;
    view.run.source = { revision: "abc1234", dirty: true };
  }), "planarian");
  assert.deepEqual([sourced.ok, sourced.loop?.revision, sourced.loop?.dirty], [true, "abc1234", true]);
  // As the adapter packages a view that states its source: the revision filled from it, and the source carried beside it.
  const filled = readLoop(await opened((view) => {
    asLoop(cell)(view);
    view.run.revision = "abc1234";
    view.run.source = { revision: "abc1234", dirty: true, from: "an execution snapshot" };
  }), "planarian");
  assert.deepEqual([filled.ok, filled.loop?.revision, filled.loop?.dirty], [true, "abc1234", true], "a dirty tree is not lost where the package also names the revision");
  const clean = readLoop(await opened((view) => {
    asLoop(cell)(view);
    view.run.revision = "abc1234";
    view.run.source = { revision: "abc1234", dirty: false };
  }), "planarian");
  assert.equal(clean.loop?.dirty, false);
  assert.equal(read.loop.dirty, null, "a package that carries no source says nothing of its tree");
  // The page says the revision, and of the tree only what the run says.
  assert.equal(engineWords(read.loop), "Made by the engine at revision 0000000");
  assert.equal(engineWords(clean.loop), "Made by the engine at revision abc1234, from a clean tree");
  assert.equal(engineWords(filled.loop), "Made by the engine at revision abc1234, from a tree with changes that were not committed");
  // A cycle: from a time the loop follows a daughter cell. It is carried, and the picture says so; nothing is refused for it.
  const daughter = run.sets.get("cell").ids.find((id) => id !== cell);
  const cycle = readLoop(await opened(asLoop(cell, { follows: [{ time: 6, from: cell, to: daughter }] })), "planarian");
  assert.equal(cycle.ok, true);
  assert.deepEqual(cycle.loop.follows, [{ time: 6, from: cell, to: daughter }]);
  assert.match(loopWords(cycle.loop, "JCVI-syn3A", clock), new RegExp(`· a loop of 12 s of the cell's time · from 6 s it follows ${daughter}, a daughter of ${cell}$`));
  assert.match(readLoop(await opened(asLoop(cell, { follows: [{ time: 6, from: cell, to: "no-such-cell" }] })), "planarian").why, /^The loop follows a cell the run does not have/);
  // A run's own label is carried in its words for the legend and the panel; the picture names the run and keeps the label off.
  const label = "one period of a periodic drive, at a low level of detail (illustration)";
  const paced = readLoop(await opened((view) => {
    asLoop(cell)(view);
    view.run.label = label;
  }), "planarian");
  assert.equal(paced.loop.label, label);
  assert.equal(loopWords(paced.loop, "Generic cell", clock), `Generic cell · the engine's looping run ${SHEET} · a loop of 12 s of the cell's time`);
  assert.equal(loopWords({ ...paced.loop, title: "Planarian loop (development run)" }, "Planarian", clock), "Planarian loop (development run) · a loop of 12 s of the cell's time", "the catalogue's title, where the page has it; it names the species already");
  assert.equal(loopWords({ ...paced.loop, title: "Interim loop" }, "Planarian", clock), "Planarian · Interim loop · a loop of 12 s of the cell's time");
  const unnamed = await opened((view) => {
    asLoop(cell)(view);
    view.run.engine_models = [];
  });
  assert.match(readLoop(unnamed, "planarian").why, /^The run names no model of the engine, or no revision/);
});

test("the loop's rates are means inside the loop, never across its seam", async () => {
  const plain = await opened();
  const run = await opened(asLoop(plain.sets.get("cell").ids[discOf(plain)]));
  const { loop } = readLoop(run, "planarian");
  // Where the loop stands: the record that ends the interval the time lies in; never the first record.
  assert.deepEqual(loopAt(loop, 0), { time: run.start, step: 1, interval: [run.t[0], run.t[1]], turns: 0 });
  const gap = run.t[1] - run.t[0];
  assert.equal(loopAt(loop, gap * 0.5).step, 1);
  assert.equal(loopAt(loop, gap).step, 2, "at a record's own time the next interval begins");
  assert.equal(loopAt(loop, loop.length - gap * 0.5).step, run.count - 1);
  // Round the seam: the time falls back to the start, and the interval is the loop's first again.
  const round = loopAt(loop, loop.length + gap * 0.5);
  assert.deepEqual([round.step, round.turns, round.interval], [1, 1, [run.t[0], run.t[1]]]);
  assert.ok(near(round.time, run.start + gap * 0.5, 1e-9));
  for (let k = 0; k <= 400; k++) {
    const at = loopAt(loop, (k / 400) * loop.length * 2.5);
    assert.ok(at.step >= 1 && at.step <= run.count - 1 && at.interval[1] > at.interval[0] && at.time >= run.start && at.time < run.end);
  }
  // The streams through the loop's cell, as the replay's bead layer reads them; then across its junctions, as the transfers layer does.
  const read = loopStreams(loop);
  assert.equal(read.ok, true);
  assert.deepEqual(read.streams.slice(0, 6).map((stream) => [stream.kind, stream.species, stream.per]), [["channel", "K", 1], ["channel", "Na", 1], ["pump", "Na", -3], ["pump", "K", 2], ["membrane", "K", 1], ["membrane", "M", 1]]);
  // A junction stream for each junction that has the cell at one end, and each species whose total there ever changes: a
  // positive total leaves the cell where the cell is the junction's sender, by the total's declared sign, and enters it otherwise.
  const junctions = run.sets.get("junction"), crossing = read.streams.slice(6);
  assert.ok(crossing.length > 0 && crossing.every((stream) => stream.kind === "junction" && stream.per === 1));
  for (const stream of crossing) {
    const ends = junctions.geometry.ends[stream.entity];
    assert.ok(ends.includes(loop.cell), stream.name);
    assert.equal(stream.out, ends[0] === loop.cell, `${stream.name}: the cell is ${ends[0] === loop.cell ? "its sender" : "its receiver"}`);
    assert.match(stream.source.sign.says, /sender/);
  }
  const touching = junctions.geometry.ends.filter((ends) => ends.includes(loop.cell)).length;
  assert.ok(new Set(crossing.map((stream) => stream.name)).size <= touching);
  // The busiest of this cell's streams over any interval of the loop sizes the token.
  let most = 0;
  for (const stream of read.streams) for (let step = 1; step < run.count; step++) most = Math.max(most, Math.abs(meanRate(run, stream.record, stream.entity, step) * stream.per));
  assert.equal(read.busiest, most);
  const token = loopToken(read.busiest, 1);
  assert.equal(token, tokenFor(ionsASecond(most), 1));
  assert.ok(beadsASecond(ionsASecond(most), token, 1) <= 10 + 1e-9, "the busiest lane passes ten beads a second at most");
  // Each stream's rate at a record: the bead layer's own arithmetic, with the way by the run's own sign.
  const rates = loopRates(loop, read.streams, 2, token, 1);
  for (const rate of rates) {
    const mean = meanRate(run, rate.stream.record, rate.stream.entity, 2) * rate.stream.per;
    assert.equal(rate.mean, mean);
    assert.ok(near(rate.ions, Math.abs(ionsASecond(mean))));
    assert.ok(near(rate.perSecond, beadsASecond(ionsASecond(mean), token, 1)));
    assert.equal(rate.out, mean > 0 === rate.stream.out);
  }
  // The pump: sodium out and potassium in, three for two, from the run's cycles and its declaration.
  const [sodium, potassium] = rates.filter((rate) => rate.stream.kind === "pump");
  assert.deepEqual([sodium.out, potassium.out], [true, false]);
  assert.ok(near(sodium.ions / potassium.ions, 1.5, 1e-9));
  // Slowed a thousand times, a smaller token, and fewer beads a second on the busiest lane: four at most, where true speed has ten.
  const slowed = loopToken(read.busiest, 1000);
  assert.ok(slowed <= token / 200 && slowed >= 1);
  assert.ok(beadsASecond(ionsASecond(most), slowed, 1e-3) <= 4 + 1e-9);
});

test("with a looping run the Cell view shows the run and no illustration, even for what the run lacks", async () => {
  const plain = await opened();
  const run = await opened(asLoop(plain.sets.get("cell").ids[discOf(plain)]));
  const lens = lensFor("planarian");
  const { flux, stage } = lens;
  assert.deepEqual(flux.setLoop("planarian", run), { ok: true });
  assert.equal(flux.source.kind, "run");
  // What the run has saved is drawn from it; the rest is named as not read, or as not saved, and illustration never fills it in.
  assert.deepEqual(kindsOf(flux.plan), ["channels", "pumps", "junctions", "membrane"]);
  assert.deepEqual(flux.plan.withheld.map((item) => [item.id, item.why]), [
    ["water", `Not read from the run: ${READ_WORDS}, and no total of this is among them.`],
    ["secretion", "The run has no exchange route: nothing is secreted or taken up in it."],
    ["fuel", FLUX.kinds.find((kind) => kind.id === "fuel").nothing],
  ]);
  assert.equal(flux.tokens.length, 0, "the switch is still off");
  lens.choose("cap.water");
  assert.equal(flux.tokens.length, 0, "no bead is drawn for water: the run says nothing of it, and illustration is not mixed in");
  assert.equal(flux.legend().example, null);
  assert.match(flux.legend().cannot[0].why, /^Not read from the run/);
  // The pumps, from the run: one lane a stream, turned by the run's sign. The pump is one element of the run: its two ions share one seat, side by side.
  lens.choose("cap.pumps");
  const lanes = lanesOf(lens);
  assert.deepEqual(lanes.map((item) => [item.lane.species, item.key.split("@")[1]]), [["Na", "0"], ["K", "0"]]);
  assert.ok(lanes[0].path(0.5).distanceTo(lanes[1].path(0.5)) > 0.1, "side by side, apart");
  const tokens = flux.tokens[0].tokens;
  const readings = flux.readings().filter((rate) => rate.stream.kind === "pump");
  assert.deepEqual(tokens.lanes.map((lane) => [near(lane.perSecond, readings.find((rate) => rate.stream.species === (lane.key.includes("/Na@") ? "Na" : "K")).perSecond), lane.reverse]), [[true, true], [true, false]]);
  // The picture names the run, says that it loops, gives the loop's length, the token, the time and the interval.
  const [notice, lines] = lens.labels.made;
  assert.equal(notice.hidden, true, "no notice of illustration: this is a run");
  const token = loopToken(flux.loop.busiest, 1);
  // At true speed a record's interval (half a second here) passes too fast to read its place: the picture gives its length. And it says what the cell takes from the run.
  const cellId = run.sets.get("cell").ids[flux.loop.cell];
  // At true speed there is no single ion to follow: each lane is a stream, as wide as its rate; the picture says the widest's rate.
  const widest = Math.round(ionsASecond(flux.loop.busiest)).toLocaleString("en-US");
  assert.equal(lines.text, `Planarian · the engine's looping run ${SHEET} · a loop of ${clock(run.end - run.start)} of the cell's time\nStreams as wide as their rates: the widest carries ${widest} ions a second · true speed · means over each 500 ms between records\nFrom the run's lumped cell ${cellId}\nNot a measurement of a living cell`);
  assert.deepEqual([tokens.mode, tokens.drawn.beads, tokens.drawn.streams > 0, tokens.drawn.chevrons > 0], ["stream", 0, true, true], "no bead to count: streams, and chevrons for their way");
  // The legend: the slow-down, what a bead stands for, the time with the loop's length, whose word the direction is.
  let legend = flux.legend();
  assert.deepEqual(legend.time.options.map((option) => [option.id, option.label, option.on]), [[1, "True", true], [1000, "1/1,000", false], [1000000, "1/1,000,000", false]]);
  assert.deepEqual(legend.keys.map((item) => item.key), ["ions", "bead", "time", "way", "head", "from", "closes", "pump"]);
  assert.equal(legend.keys[1].text, `Streams as wide as their rates: the widest carries ${widest} ions a second. A stream's width and brightness carry its rate; how fast its streaks run stands for nothing`);
  assert.equal(legend.keys[5].text, `From the run's cell ${cellId}: a lumped cell with the run's own laws. Not a measurement of a living cell. Drawn: channels from channel_transferred (kir_1, nal_1); pumps from pump_cycles (pump of membrane_1); neighbours from junction_transferred (6 junctions); membrane itself from membrane_transferred (membrane_1)`, "the whole cell's: which part takes a flux from which record");
  assert.equal(legend.keys[6].text, closesWords(flux.loop));
  assert.equal(legend.keys[2].text, `True speed: one second here is one second of the run. The run loops: ${clock(run.end - run.start)} of the cell's time, then again from its start. ${paceKey(1)}`);
  assert.equal(legend.keys[3].text, "A lane flows the way its total grew over the interval shown, by the run's own signs");
  assert.equal(flux.inPanel(lens.model.get("cap.pumps")).sections.at(-1).title, "Flux, from the looping run");
  // Time passes at true speed: the interval shown moves on with the loop, and comes round to its start. The words stay the same, so nothing is laid out again.
  const gap = run.t[1] - run.t[0];
  const said = flux.said;
  flux.advance(gap * 1.5);
  assert.equal(flux.step, 2);
  assert.equal(flux.said, said, "the same words: the statement is not written again at each record");
  flux.advance(flux.loop.length);
  assert.equal(flux.step, 2, "once round");
  // Slowed a thousand times: the loop's time runs a thousandth as fast, and the token is smaller. Each interval now lasts long enough to read its place.
  flux.setSlow(1000);
  legend = flux.legend();
  assert.deepEqual(legend.time.options.map((option) => option.on), [false, true, false]);
  assert.match(lens.labels.made[1].text, /\nOne packet is [\d,]+ ions · slowed 1,000 times: packets, crossing more slowly · mean of 0\.5 s to 1\.0 s of the loop\n/);
  assert.equal(flux.tokens[0].tokens.mode, "packets");
  const before = flux.elapsed;
  flux.advance(1);
  assert.ok(near(flux.elapsed - before, 0.001, 1e-9));
  assert.ok(loopToken(flux.loop.busiest, 1000) < token);
  // The slider: any slow-down from true speed to its end, never faster than life; the slider's own words come with it.
  flux.setSlow(7);
  assert.equal(flux.slow, 7);
  flux.setSlow(0.25);
  assert.equal(flux.slow, 1, "never faster than life");
  flux.setSlow(1e9);
  assert.equal(flux.slow, SLOWEST);
  flux.setSlow({ slow: 1000, live: true });
  assert.equal(flux.slow, 1000);
  const chromes = lens.chromes;
  flux.setSlow({ slow: 2000, live: true });
  assert.equal(lens.chromes, chromes, "while the slider is dragged the legend is left as it is");
  flux.setSlow({ slow: 2000, live: false });
  assert.equal(lens.chromes, chromes + 1, "and written again when it is let go");
  flux.setSlow(1000);
  // The panel behind all of it names the run and says that no rate crosses the seam.
  lens.choose(null);
  flux.setOn(true);
  assert.equal(lanesOf(lens).length, flux.loop.streams.length, "one lane a stream");
  assert.ok(flux.loop.streams.length > 6, "the six through the membrane, and those across the junctions");
  const panel = flux.describe(FLUX_PANEL);
  assert.equal(panel.chips[0].label, "From the looping run");
  assert.equal(panel.plain, `Planarian · the engine's looping run ${SHEET} · a loop of ${clock(run.end - run.start)} of the cell's time. ${CLOSES.says} Its last record meets its first within 1.0e-9 (tolerance 1.0e-6). Made by the engine at revision 0000000.`);
  // The run's own sentence on its closure stands after a full stop: the panel begins it with a capital, and the run's
  // sentence is left as the run wrote it.
  const says = flux.loop.closes.says;
  flux.loop.closes.says = "the last observed row meets the first within 2.8e-05 relative (largest in observed_membrane_flux_fmol_s)";
  assert.match(flux.describe(FLUX_PANEL).plain, /of the cell's time\. The last observed row meets the first within 2\.8e-05 relative \(largest in observed_membrane_flux_fmol_s\)\. Its last record/);
  assert.equal(flux.loop.closes.says, "the last observed row meets the first within 2.8e-05 relative (largest in observed_membrane_flux_fmol_s)");
  flux.loop.closes.says = says;
  assert.match(panel.note, /no difference is taken across the seam/);
  assert.deepEqual(panel.sections.map((section) => section.title), ["What this cell takes from the run", "Drawn", "Not drawn", "Over the interval shown"]);
  assert.deepEqual(panel.sections[0].items.map((item) => [item.label, item.detail]), [["Ions through the channels", "from channel_transferred"], ["Ions through the pumps", "from pump_cycles"], ["Exchange with neighbours", "from junction_transferred"], ["Ions through the membrane itself", "from membrane_transferred"]]);
  assert.equal(panel.sections[3].items.length, flux.loop.streams.length);
  assert.deepEqual([stage.bloom, [...stage.decoration.holds]], [BLOOM, ["flux"]]);
  // Another species keeps illustration: the run is the planarian's.
  const other = lensFor("human");
  assert.equal(other.flux.setLoop("human", run).ok, false);
  assert.equal(other.flux.source.kind, "illustration");
  // And an example is never taken for a species' run: the planarian, which names a run of its own, still shows no illustration.
  const refused = lensFor("planarian");
  const answer = refused.flux.setLoop("planarian", plain);
  assert.equal(answer.ok, false);
  assert.equal(refused.flux.source.kind, "pending");
  assert.equal(refused.flux.plan.kinds.length, 0);
});

test("a loop's exchange routes are read as its secreted signals: released out, taken up in, by the run's own signs", async () => {
  const WORLD = "synthetic-world--secreting";
  const plain = await opened(null, WORLD);
  const cell = plain.sets.get("cell").ids[0];
  const run = await opened(asLoop(cell), WORLD);
  const { loop } = readLoop(run, "planarian");
  const read = loopStreams(loop);
  assert.equal(read.ok, true, read.why);
  // The world's two routes on its cell's membrane, each with the species it carries; its face joins two spaces outside, not the cell.
  assert.deepEqual(read.streams.map((stream) => [stream.kind, stream.name, stream.species, stream.out]), [["route", "secrete", "S", true], ["route", "sink", "S", true]]);
  // An import route's total falls: over any interval its beads go into the cell; the export's go out.
  const step = 2, token = loopToken(read.busiest, 1);
  const [secrete, sink] = loopRates(loop, read.streams, step, token, 1);
  assert.deepEqual([secrete.out, sink.out], [true, false]);
  assert.ok(near(secrete.mean, meanRate(run, read.streams[0].record, read.streams[0].entity, step)));
  // In the Cell view: the signals' lanes are the run's two routes, and nothing else of the run is drawn.
  const lens = lensFor("planarian");
  assert.deepEqual(lens.flux.setLoop("planarian", run), { ok: true });
  assert.deepEqual(kindsOf(lens.flux.plan), ["secretion"]);
  assert.deepEqual(lens.flux.plan.kinds[0].groups[0].lanes.map((lane) => lane.label), ["secrete · S", "sink · S"]);
  assert.equal(lens.flux.plan.withheld.find((item) => item.id === "channels").why, "The run saved no total for it.");
  lens.choose("cap.secretion");
  assert.equal(lanesOf(lens).length, 2);
  lens.flux.advance(0);
  assert.deepEqual(lens.flux.tokens[0].tokens.lanes.map((lane) => lane.reverse), lens.flux.readings().map((rate) => rate.out === true));
  // A route whose amounts do not add up has no declared way, and is not read (rule 1).
  const loose = await opened(asLoop(cell), "synthetic-world--unbalanced");
  assert.deepEqual(loopStreams(readLoop(loose, "planarian").loop).streams.filter((stream) => stream.kind === "route"), []);
  // The reader alone: a total with no declared direction gives no stream.
  const across = bordersOf(run, [{ id: "exchange_moved_fmol", set: read.streams[0].source.set, sign: { says: "unknown" } }], loop.cell);
  assert.deepEqual(across, []);
});

test("a run that is the species' loop and cannot be read still stands in illustration's place", async () => {
  const plain = await opened();
  const cell = plain.sets.get("cell").ids[discOf(plain)];
  // The same loop, with no total of what its channel populations or its junctions carried: nothing the viewer reads of a loop is left.
  const bare = await opened((view) => {
    asLoop(cell)(view);
    const gone = new Set(view.records.filter((record) => /^(channel|junction)_transferred/.test(record.id) || /^(channel|junction)_transferred/.test(record.field || "")).map((record) => record.id));
    view.records = view.records.filter((record) => !gone.has(record.id));
  });
  assert.equal(readLoop(bare, "planarian").ok, true);
  const unread = loopStreams(readLoop(bare, "planarian").loop);
  assert.equal(unread.ok, false);
  assert.ok(unread.why.length > 10);
  const lens = lensFor("planarian");
  const answer = lens.flux.setLoop("planarian", bare);
  assert.deepEqual([answer.ok, answer.reads, answer.why], [true, false, unread.why]);
  assert.equal(lens.flux.source.kind, "run", "the species has a run: illustration is no longer shown for it");
  assert.deepEqual(kindsOf(lens.flux.plan), []);
  assert.match(unread.why, /^The run saved no total of anything that crossed this cell's borders that the viewer reads/);
  assert.deepEqual(lens.flux.plan.withheld.map((item) => [item.id, item.why === unread.why]), [["channels", true], ["pumps", true], ["junctions", true], ["water", false], ["secretion", true], ["fuel", false], ["membrane", true]]);
  lens.flux.setOn(true);
  assert.equal(lens.flux.tokens.length, 0);
  assert.equal(lens.flux.legend().example, null);
  assert.equal(lens.labels.made.every((label) => label.hidden), true);
  assert.equal(lens.flux.legend().cannot.length, 7);
});

test("a looping run and an illustration never share a picture", async () => {
  const plain = await opened();
  const run = await opened(asLoop(plain.sets.get("cell").ids[discOf(plain)]));
  const lens = lensFor("planarian");
  lens.flux.setOn(true);
  assert.ok(lanesOf(lens).every((item) => !item.lane.stream), "before the run: illustration alone");
  lens.flux.setLoop("planarian", run);
  assert.ok(lanesOf(lens).length > 0 && lanesOf(lens).every((item) => item.lane.stream), "with the run: lanes of the run alone");
  assert.equal(lens.flux.legend().example, null);
  assert.equal(lens.labels.made[0].hidden, true);
  const plan = planFromLoop(FLUX, lens.flux.loop, lens.flux.loop.streams, { has: () => true });
  assert.ok(plan.kinds.every((kind) => kind.groups.every((group) => group.id === "run")));
  assert.equal(planFor(FLUX, { species: lens.species, has: () => true }).kinds.some((kind) => kind.id === "membrane"), false, "the membrane's own routes are drawn only from a run");
});

test("a chosen part that draws no flux: the legend says so in place of asking for a choice, and the part's panel says why", () => {
  const human = lensFor("human");
  human.choose("cap.nucleus");
  const legend = human.flux.legend();
  assert.equal(human.flux.tokens.length, 0);
  assert.match(legend.hint, /^This part draws no flux: its panel says why\./);
  const panel = human.flux.inPanel(scene.entities.find((item) => item.id === "cap.nucleus"));
  assert.match(JSON.stringify(panel.sections), /The picture draws flux only for ions through the channels, ions through the pumps, exchange with neighbours, water and secreted signals\. This part is none of them\./);
  // With nothing chosen, as before.
  human.choose(null);
  assert.match(human.flux.legend().hint, /^Or choose a part to see its flux\./);
});

test("the Speed row is offered wherever a rate stands behind what moves: a machine's rotor as it turns", () => {
  const ecoli = lensFor("ecoli");
  assert.equal(ecoli.flux.legend().time, null, "nothing turns, no looping run: no Speed row");
  ecoli.machine = { open: true, legend: () => ({ turning: true, keys: [{ key: "way", text: "Turning" }], hint: null, example: "Illustration: not a run" }), statement: () => null };
  const legend = ecoli.flux.legend();
  assert.deepEqual(legend.time.options.map((option) => [option.label, option.on]), [["True", true], ["1/1,000", false], ["1/1,000,000", false]]);
  assert.equal(legend.example, "Illustration: not a run");
  ecoli.machine.legend = () => ({ turning: false, keys: [], hint: "The motor stands.", example: null });
  assert.equal(ecoli.flux.legend().time, null, "standing, it offers none");
  // The one place the speed is put in words.
  assert.equal(ecoli.flux.slowSaid(), "true speed");
  ecoli.flux.slow = 1000;
  assert.equal(ecoli.flux.slowSaid(), "slowed 1,000 times");
});

// ------------------------------------------------------------ the planarian's own looping run (FR-11), from the fixture in the tree

// The engine's first looping run, as its run-view writer wrote it (tests/engine-views/loop-b08af640/), packaged here as the
// page gets its runs, under the experiment id the page's catalogue gives it. The overlay holds what the catalogue says of it.
const LOOPED = path.join(scratch, "loop"), LOOP_ID = "planarian-loop--planarian-b08af640";
{
  const overlay = { format: "cells.visualizer.replay_overlay@1", experiments: { "planarian-loop": { adapter: "standard-history", development: true, label: "Planarian loop (development run)", plain: "A development run of the engine, not judged.", sources: [], engine_entities: [], outcome: { judged: false, status: "Development run, no verdict" }, parameters: {}, readouts: {}, events: { current: { label: "Electrode current", plain: "The electrode's current changes." } }, stops: { complete: { label: "Ran to its end" } } } } };
  const settings = path.join(scratch, "loop-settings");
  spawnSync("mkdir", ["-p", settings]);
  for (const [name, content] of [["overlay.json", overlay], ["selection.json", { "planarian-loop": { evidence_folder: "loop-b08af640", runs: ["planarian-b08af640"] } }]]) spawnSync("python3", ["-c", `import json,sys; json.dump(json.loads(sys.argv[2]), open(sys.argv[1], "w"))`, path.join(settings, name), JSON.stringify(content)]);
  const done = spawnSync("python3", [path.join(ROOT, "tools", "adapt_run.py"), "--evidence", path.join(ROOT, "tests", "engine-views"), "--overlay", path.join(settings, "overlay.json"), "--selection", path.join(settings, "selection.json"), "--out", LOOPED], { encoding: "utf8" });
  assert.equal(done.status, 0, `adapt_run.py failed:\n${done.stderr}`);
}

/** The planarian's lens, its species naming its run, with the page's catalogue of runs and a fetch that serves the packaged files. */
function planarianWithLoop({ catalogue = readJson(path.join(LOOPED, "index.json")), fail = false, refuse = 0 } = {}) {
  const asked = [];
  const before = globalThis.fetch;
  let refused = refuse; // how many loads the network gives up on first
  globalThis.fetch = async (url) => {
    asked.push(String(url));
    if (refused-- > 0) throw new TypeError("Failed to fetch");
    if (fail) return { ok: false, status: 404 };
    const file = path.join(LOOPED, path.basename(String(url)));
    return { ok: true, status: 200, json: async () => readJson(file) };
  };
  // The scene's planarian: its own cell type names the run (ENTRIES.md, CELL_TYPES.md: `cell_type.loop`), as its file does.
  const lens = lensFor("planarian", { replays: catalogue });
  assert.deepEqual(lens.species.cell_type, { loop: LOOP_ID });
  const restore = () => (globalThis.fetch = before);
  return { lens, asked, restore };
}
const settle = async (flux) => {
  for (let tries = 0; tries < 200 && flux.fetches.size; tries++) await new Promise((resolve) => setTimeout(resolve, 5));
};

test("the planarian names its own looping run: the page fetches it from its catalogue, and the Cell view plays it as what the catalogue says it is", async (t) => {
  // The species' file names it for its own cell type, and the scene carries that as it is (tools/lib/species.py).
  assert.deepEqual(json("data/species/planarian.json").cell_type, { loop: LOOP_ID });
  assert.equal(json("data/species/planarian.json").cell.loop, undefined, "the loop belongs to a cell type, not to the cell block");
  const { lens, asked, restore } = planarianWithLoop();
  t.after(restore);
  const { flux } = lens;
  assert.deepEqual([flux.named, flux.typeKey], [LOOP_ID, "planarian/cell"]);
  // Once the species is read through its entries, the default cell type names it: the same run, found the same way.
  const typed = { ...lens.species, cell_types: [{ id: "cell", label: "Generic cell", loop: LOOP_ID }], default_cell_type: "cell" };
  assert.equal(Object.getOwnPropertyDescriptor(CellFlux.prototype, "named").get.call({ get cellType() { return Object.getOwnPropertyDescriptor(CellFlux.prototype, "cellType").get.call({ species: typed, lens: {} }); } }), LOOP_ID);
  // As the species is shown, its run is asked for; until it is read, nothing is drawn and no illustration stands in.
  flux.build();
  assert.equal(flux.source.kind, "pending");
  assert.ok(flux.plan.kinds.length === 0 && flux.plan.withheld.every((item) => item.why === "The Planarian's own run is being fetched."));
  assert.equal(flux.legend().hint, "The Planarian's own run is being fetched. What moves at rest is the picture's own, not a measured flow.");
  await settle(flux);
  assert.equal(flux.source.kind, "run");
  assert.ok(asked[0].endsWith(`${LOOP_ID}.json`) && asked.length > 1, "the run, then the files of records it reads");
  const loop = flux.loop;
  assert.deepEqual([loop.title, loop.status, loop.cell, loop.length, loop.revision], ["Planarian loop (development run)", "Development run of the engine, not judged", 3, 2, "b08af640c3db83e891e29ade36c300d6f8e5a553"]);
  // What it draws, from which of the run's records: the centre cell's channels (only those that pass something), its pump, its membrane itself and its six junctions.
  assert.deepEqual(flux.plan.kinds.map((kind) => kind.id), ["channels", "pumps", "junctions", "membrane"]);
  assert.deepEqual(flux.plan.withheld.map((item) => [item.id, item.why]), [
    ["water", `Not read from the run: ${READ_WORDS}, and no total of this is among them.`],
    ["secretion", "The run has no exchange route: nothing is secreted or taken up in it."],
    ["fuel", FLUX.kinds.find((kind) => kind.id === "fuel").nothing],
  ]);
  assert.deepEqual(loop.streams.filter((stream) => stream.kind === "channel").map((stream) => [stream.name, stream.species]), [["nav_3", "Na"], ["kir_3", "K"]], "a channel population's total of an ion it never passes gets no lane");
  assert.equal(new Set(loop.streams.filter((stream) => stream.kind === "junction").map((stream) => stream.name)).size, 6);
  // At true speed: a bead is a million ions, sized by the busiest stream (the membrane's own sodium, about five million a second).
  assert.equal(loopToken(loop.busiest, 1), 1_000_000);
  assert.ok(ionsASecond(loop.busiest) > 4e6 && ionsASecond(loop.busiest) < 6e6);
  // All of it shown: the picture says what the run is, names it, says that it loops, the token and speed, and what the cell takes from it.
  flux.setOn(true);
  const [notice, lines] = lens.labels.made;
  assert.equal(notice.text, "Development run of the engine, not judged");
  assert.equal(lines.text, "Planarian loop (development run) · a loop of 2 s of the cell's time\nStreams as wide as their rates: the widest carries 5,083,478 ions a second · true speed · means over each 20 ms between records\nFrom the run's lumped cell cell_3, with a prescribed electrode current injection (not drawn)\nNot a measurement of a living cell");
  assert.match(flux.legend().keys.find((item) => item.key === "from").text, /^From the run's cell cell_3: a lumped cell with the run's own laws, under the run's prescribed electrode current injection, which is not drawn\. Not a measurement of a living cell\. Drawn: /, "the legend says it in full");
  const legend = flux.legend();
  assert.equal(legend.example, "Development run of the engine, not judged", "the legend carries it too, for a narrow screen whose picture has no room");
  assert.match(legend.keys.find((item) => item.key === "from").text, /Drawn: channels from channel_transferred \(nav_3, kir_3\); pumps from pump_cycles \(pump of membrane_3\); neighbours from junction_transferred \(6 junctions\); membrane itself from membrane_transferred \(membrane_3\)$/);
  assert.equal(legend.keys.find((item) => item.key === "closes").text, "Its last record meets its first within 2.8e-5 (tolerance 1.0e-4), in the records it measures; of its records, 7 are not measured (cumulative totals: they grow by design, so the reader differences them inside the loop)");
  assert.deepEqual(legend.time.options.map((option) => [option.label, option.on]), [["True", true], ["1/1,000", false], ["1/1,000,000", false]]);
  // The six junctions each cross a side of their own, the three species of one junction side by side there.
  const junctions = flux.tokens[0].lanes.filter((item) => item.lane.stream?.kind === "junction");
  const sides = new Set(junctions.map((item) => item.key.split("@")[1]));
  assert.equal(sides.size, 6);
  for (const side of sides) assert.equal(new Set(junctions.filter((item) => item.key.endsWith(`@${side}`)).map((item) => item.lane.stream.name)).size, 1, "one junction on a side");
  // A chosen part's panel says what the run is, where the legend is hidden behind it.
  lens.choose("cap.pumps");
  assert.equal(flux.inPanel(lens.model.get("cap.pumps")).sections.at(-1).title, "Flux, from the looping run. Development run of the engine, not judged");
  const panel = (lens.choose(null), flux.describe(FLUX_PANEL));
  assert.equal(panel.chips[0].label, "Development run of the engine, not judged");
  assert.match(panel.plain, /^Planarian loop \(development run\) · a loop of 2 s of the cell's time\. A development run of the engine, not judged\. The last observed row meets the first within 2\.8e-05 relative/);
  assert.match(panel.plain, /Made by the engine at revision b08af640c3db83e891e29ade36c300d6f8e5a553, from a clean tree\.$/);
  assert.match(panel.sections[0].note, /The run's own words for itself: “interim planarian loop: .*\(illustration, no verdict\)”\.$/);
  // On a phone the picture keeps the notice and the run's name, in two lines; the rest stands in the legend and the panel.
  const phone = planarianWithLoop({ });
  t.after(phone.restore);
  phone.lens.stage.width = 400;
  phone.lens.stage.height = 780;
  await settle(phone.lens.flux);
  phone.lens.flux.setOn(true);
  assert.deepEqual([phone.lens.labels.made[0].text, phone.lens.labels.made[1].text], ["Development run of the engine, not judged", "Planarian loop (development run)\nloops every 2 s"]);
  assert.ok(phone.lens.flux.legend().keys.some((item) => /^Streams as wide as their rates: the widest carries 5,083,478 ions a second/.test(item.text)), "what is drawn, and the numbers, stand in the legend");
  // Slowed a thousand times: the record's interval lasts twenty seconds of watching, long enough to read its place in the loop.
  flux.setOn(true);
  flux.setSlow(1000);
  assert.match(lens.labels.made[1].text, /^Planarian loop .*\nOne packet is 5,000 ions · slowed 1,000 times: packets, crossing more slowly · mean of 0\.00 s to 0\.02 s of the loop\n/);
  // Slowed a million times: single beads crossing slowly.
  flux.setSlow(1e6);
  assert.match(lens.labels.made[1].text, /\nOne bead is 10 ions · slowed 1,000,000 times: single beads, crossing slowly · /);
  assert.deepEqual([flux.tokens[0].tokens.mode, Number(flux.tokens[0].tokens.lanes[0].crossing.toFixed(6))], ["beads", 4.096]);
});

test("a species whose own run cannot be had shows no illustration in its place, and says why", async (t) => {
  const missing = planarianWithLoop({ catalogue: { experiments: [], runs: [] } });
  t.after(missing.restore);
  missing.lens.flux.build();
  assert.equal(missing.lens.flux.source.kind, "pending");
  assert.equal(missing.lens.flux.source.state, "failed");
  assert.equal(missing.lens.flux.source.why, `The Planarian's own run (${LOOP_ID}) is not among the runs this page carries.`);
  missing.lens.flux.setOn(true);
  assert.equal(missing.lens.flux.tokens.length, 0, "nothing drawn, and no illustration");
  assert.match(missing.lens.flux.describe(FLUX_PANEL).plain, /no illustration stands in for it/);
  // A load the network gave up on is asked for again: the second answer is had.
  const flaky = planarianWithLoop({ refuse: 1 });
  t.after(flaky.restore);
  for (let tries = 0; tries < 400 && flaky.lens.flux.source.kind !== "run"; tries++) await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(flaky.lens.flux.source.kind, "run", "read on the second asking");
  assert.equal(flaky.asked.filter((url) => url.endsWith(`${LOOP_ID}.json`)).length, 2);
  flaky.restore();
  const broken = planarianWithLoop({ fail: true });
  t.after(broken.restore);
  broken.lens.flux.build();
  await settle(broken.lens.flux);
  for (let tries = 0; tries < 200 && broken.lens.flux.fetches.get("planarian/cell")?.state !== "failed"; tries++) await new Promise((resolve) => setTimeout(resolve, 5));
  assert.match(broken.lens.flux.source.why, /^The Planarian's own run could not be read: runs\/planarian-loop--planarian-b08af640\.json answered 404$/);
});

// ------------------------------------------------------------ slowing down is seen (17 November 2026)

test("each step of the Speed row is seen: a stream at true speed, packets slowed a thousand times, single beads slowed a million times", () => {
  // The pace: at most ten, 2.5 and 0.625 beads a second on the busiest lane; a crossing of 1.6, 2.56 and 4.1 s. True speed and faster alike.
  const at = (speed) => paceAt(speed);
  assert.deepEqual([at(1), at(4), at(240)].map((pace) => [pace.busiest, pace.crossing]), [[10, 1.6], [10, 1.6], [10, 1.6]]);
  assert.ok(near(at(1e-3).busiest, 2.5, 1e-12) && near(at(1e-3).crossing, 2.56, 1e-12));
  assert.ok(near(at(1e-6).busiest, 0.625, 1e-12) && near(at(1e-6).crossing, 4.096, 1e-12));
  assert.ok(at(0.25).busiest < 10 && at(0.25).busiest > 2.5 && at(0.25).crossing > 1.6 && at(0.25).crossing < 2.56, "the replay's quarter speed lies between");
  assert.deepEqual([1, 0.5, 0.25, 1e-3, 1e-4, 1e-5, 1e-6].map(modeAt), ["stream", "stream", "stream", "packets", "packets", "beads", "beads"]);
  // Between the steps nothing jumps: the stream gives way to packets by a thousandfold, a packet rounds into a bead by a millionfold.
  assert.deepEqual([0, 3, 6].map((decades) => blendAt(decades)), [{ stream: 1, beads: 0, stretch: 3.9 }, { stream: 0, beads: 1, stretch: 1.5 }, { stream: 0, beads: 1, stretch: 1 }]);
  for (let decades = 0; decades < 7; decades += 0.01) {
    const here = blendAt(decades), next = blendAt(decades + 0.01);
    assert.ok(Math.abs(next.stream - here.stream) < 0.02 && Math.abs(next.beads - here.beads) < 0.02 && Math.abs(next.stretch - here.stretch) < 0.04, `no jump at ${decades.toFixed(2)}`);
  }
  // The token: 1, 2 or 5 times a power of ten, never under one ion, and the arithmetic exact at every step.
  for (const busiest of [7, 950, 5.08e6, 4.4e9]) {
    for (const speed of [1, 1e-3, 1e-6, 0.25, 4]) {
      const token = tokenFor(busiest, speed), passing = beadsASecond(busiest, token, speed);
      assert.match(String(token), /^[125]0*$/, `${busiest} at ${speed}`);
      assert.ok(token >= 1);
      assert.ok(near(passing * token, busiest * speed, 1e-12), "beads a second times ions in a bead is ions a second of the run times the speed");
      if (token > 1) assert.ok(passing <= paceAt(speed).busiest + 1e-9 && passing > paceAt(speed).busiest / 2.5 - 1e-9, `${busiest} at ${speed}: ${passing}`);
    }
  }
  // The planarian's busiest stream, about 5.08 million ions a second: a bead (or packet) is a million, five thousand, ten ions.
  assert.deepEqual([1, 1e-3, 1e-6].map((speed) => tokenFor(5.083478e6, speed)), [1_000_000, 5000, 10]);
  assert.deepEqual([1, 1e-3, 1e-6].map((speed) => Number(beadsASecond(5.083478e6, tokenFor(5.083478e6, speed), speed).toFixed(2))), [5.08, 1.02, 0.51], "fewer at each step");
  // A lane at each pace: as many set out a second as its rate says, each crossing in its time; standing, fewer when slowed.
  const lane = (perSecond, crossing) => ({ perSecond, crossing, due: 0, beads: [] });
  for (const [perSecond, crossing] of [[5.08, 1.6], [1.02, 2.56], [0.51, 4.096]]) {
    const one = lane(perSecond, crossing);
    advance(one, 100);
    assert.equal(one.sent, Math.floor(perSecond * 100), "beads set out in a hundred seconds");
    const first = one.beads.at(-1);
    advance(one, 0.5);
    assert.ok(near(one.beads.find((share) => share > first) - first, 0.5 / crossing, 1e-9) || one.beads.length, "a bead moves half a second over its crossing");
  }
  assert.deepEqual([standing(5.08, 1.6).length, standing(1.02, 2.56).length, standing(0.51, 4.096).length], [8, 3, 2], "fewer stand when slowed");
  assert.deepEqual([headSize(5.08, 1.6), headSize(0.51, 4.096)], [1, 1], "the arrowhead follows the beads on the lane at one moment");
  // The words.
  assert.equal(flowWords({ speed: 1, token: 1e6, widest: 5.083478e6 }), "Streams as wide as their rates: the widest carries 5,083,478 ions a second");
  assert.equal(flowWords({ speed: 1e-3, token: 5000 }), "One packet is 5,000 ions");
  assert.equal(flowWords({ speed: 1e-6, token: 10 }), "One bead is 10 ions");
  assert.match(paceKey(1e-3), /^Slowed, the stream resolves into packets: at most 2\.5 a second on the busiest lane, each taking 2\.6 s to cross/);
  assert.match(paceKey(1e-6), /single beads: at most 0\.63 a second on the busiest lane, each taking 4\.1 s to cross/);
  assert.match(paceKey(1e-3, false), /^Slowed, fewer beads pass \(at most 2\.5 a second on the busiest lane, where true speed has 10\) and each takes 2\.6 s to cross/);
});

test("a stream is as wide as its rate, its streaks run its way, and chevrons tell the way when nothing moves", () => {
  const a = new THREE.Vector3(0, 0, 0), b = new THREE.Vector3(4, 0, 0);
  const lanes = () => [
    { key: "busy", path: straight(a, b), colour: new THREE.Color("#2a78d6"), perSecond: 5, reverse: false },
    { key: "thin", path: straight(a, b), colour: new THREE.Color("#eb6834"), perSecond: 0.5, reverse: true },
    { key: "none", path: straight(a, b), colour: new THREE.Color("#eb6834"), perSecond: 0, reverse: false },
  ];
  const stream = new Tokens({ lanes: lanes(), radius: 0.1, ground: new THREE.Color("#ffffff"), mode: "stream", full: 5 });
  stream.tick(0.5);
  assert.deepEqual(stream.drawn, { beads: 0, heads: 0, chevrons: 2 * CHEVRONS, streams: 2 }, "no bead to count; a stream and its chevrons on each lane that carries something");
  // Widths: the busiest the fullest; the area goes with the rate.
  const widths = stream.flow.widths.array, per = widths.length / 3;
  assert.deepEqual([widths[0], widths[per], widths[2 * per]], [widthOf(1), Math.fround(widthOf(0.1)), 0], "kept in 32 bits for the card");
  assert.ok(near(widthOf(1), 1) && widthOf(0.1) < widthOf(1) && widthOf(0) === 0.25);
  // The streaks run on, and stand where nothing may move.
  const before = stream.flow.time;
  stream.tick(0.5);
  assert.ok(near(stream.flow.time - before, 0.5 * STREAK_PACE, 1e-12));
  stream.tick(0.5, true);
  assert.ok(near(stream.flow.time - before, 0.5 * STREAK_PACE, 1e-12), "still: the streaks stand");
  // A chevron points the way its lane flows: along +x on the first lane, along -x on the reversed one.
  const turned = (index) => {
    const turn = new THREE.Quaternion();
    new THREE.Matrix4().fromArray(stream.flow.chevrons.instanceMatrix.array, index * 16).decompose(new THREE.Vector3(), turn, new THREE.Vector3());
    return new THREE.Vector3(0, 1, 0).applyQuaternion(turn);
  };
  assert.ok(turned(0).distanceTo(new THREE.Vector3(1, 0, 0)) < 1e-6 && turned(CHEVRONS).distanceTo(new THREE.Vector3(-1, 0, 0)) < 1e-6);
  // Still, they stand where they are: the way is told without motion.
  const where = () => Array.from(stream.flow.chevrons.instanceMatrix.array.slice(12, 15));
  const standingAt = where();
  stream.tick(2, true);
  assert.deepEqual(where(), standingAt);
  // The streams are one draw call, the chevrons another: nothing per lane.
  assert.equal(stream.flow.group.children.length, 2);
  // Packets: long along their lane; beads: round. The tapered trail and today's arrowhead are kept to be compared.
  const packets = new Tokens({ lanes: lanes(), radius: 0.1, ground: new THREE.Color("#ffffff"), mode: "packets", full: 5 });
  packets.tick(1);
  const scale = new THREE.Vector3();
  new THREE.Matrix4().fromArray(packets.cores.instanceMatrix.array, 0).decompose(new THREE.Vector3(), new THREE.Quaternion(), scale);
  assert.ok(scale.y > 1.3 * scale.x, "a packet is long the way it travels");
  const taper = new Tokens({ lanes: lanes(), radius: 0.1, ground: new THREE.Color("#ffffff"), mode: "stream", style: "taper", full: 5 });
  assert.deepEqual([taper.drawn.chevrons, taper.flow.streams.material.uniforms.uTaper.value], [0, 1], "a tapered trail: the head leads the flow, still or moving");
  const arrow = new Tokens({ lanes: lanes(), radius: 0.1, ground: new THREE.Color("#ffffff"), mode: "beads", style: "arrow", full: 5 });
  assert.equal(arrow.drawn.heads, 2);
  assert.deepEqual(STYLES, ["chevrons", "taper", "arrow"]);
});

test("the Speed slider: true speed at its start, a thousandfold at its middle, a millionfold at three quarters, ten millionfold at its end, and nothing jumps between", () => {
  assert.deepEqual(SLIDER.map((mark) => [mark.at, mark.slow, mark.label]), [[0, 1, "True"], [0.5, 1e3, "1/1,000"], [0.75, 1e6, "1/1,000,000"], [1, 1e7, "1/10,000,000"]]);
  for (const mark of SLIDER) {
    assert.ok(near(slowAt(mark.at), mark.slow, 1e-9), mark.label);
    assert.ok(near(positionOf(mark.slow), mark.at, 1e-9) || mark.at === 0, mark.label);
  }
  // Evenly in powers of ten between two marks, and back again.
  assert.ok(near(slowAt(0.25), Math.pow(10, 1.5), 1e-9) && near(slowAt(0.625), Math.pow(10, 4.5), 1e-9) && near(slowAt(0.875), Math.pow(10, 6.5), 1e-9));
  for (let p = 0; p <= 1; p += 0.01) assert.ok(near(positionOf(slowAt(p)), p, 1e-9) || p < 1e-9, `there and back at ${p.toFixed(2)}`);
  assert.deepEqual([slowAt(-1), slowAt(2)], [1, 1e7], "never faster than life, never past its end");
  assert.deepEqual([slowLabel(1), slowLabel(1000), slowLabel(31_622.8), slowLabel(1e7)], ["True", "1/1,000", "1/32,000", "1/10,000,000"]);
  // At its end a bead of the planarian's busiest stream (about 5.08 million ions a second) is two ions, one setting out every four seconds.
  assert.equal(tokenFor(5.083478e6, 1 / SLOWEST), 2);
  // Along it, what the eye sees thins without a jump: fewer on the busiest lane, each crossing more slowly.
  let before = null;
  for (let p = 0; p <= 1; p += 0.05) {
    const speed = 1 / slowAt(p), pace = paceAt(speed), blend = blendAt(resolveAt(speed));
    if (before) assert.ok(pace.busiest <= before.busiest + 1e-9 && pace.crossing >= before.crossing - 1e-9 && blend.stream <= before.stream + 1e-9, `at ${p.toFixed(2)}`);
    before = { ...pace, stream: blend.stream };
  }
});

test("the page's address may carry a slow-down (`slow=`): the Cell view opens slowed so, never faster than life", () => {
  const before = globalThis.location;
  try {
    globalThis.location = { search: "?lens=cell&slow=1000" };
    assert.equal(lensFor(ILLUSTRATED).flux.slow, 1000);
    globalThis.location = { search: "?slow=0.5" };
    assert.equal(lensFor(ILLUSTRATED).flux.slow, 1, "never faster than life");
    globalThis.location = { search: "?slow=1e12" };
    assert.equal(lensFor(ILLUSTRATED).flux.slow, SLOWEST);
  } finally {
    globalThis.location = before;
  }
});
