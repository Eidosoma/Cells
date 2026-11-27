// The species the page can show: their levels, their shapes and what has no place in
// their cells. A species file is held to its contracts (schema/SPECIES.md and
// schema/SPECIES_SHAPES.md) when the scene is built, and the viewer builds every cell,
// organ and body from the parameters a species gives: it holds no drawing that belongs
// to one species.
//
// The species used to try the contracts is made up, in a temporary folder. The
// repository's own files are held to the contracts as well. Nothing needs a browser.
//
//   node --test tests/species_levels.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, writeFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { REF, cellAcross, cellFrame, polygonOutline, stadiumOutline, solidGeometry } from "../src/lenses/shapes.js";
import { outlineFrame, outlineOrigin } from "../src/lenses/outline_parts.js";
import { CellLens, defaultSpecies, MODELLED } from "../src/lenses/cell.js";
import { css } from "../src/ui/styles.js";

const SPECIES = path.join(ROOT, "data", "species");
const overlay = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const CAPABILITIES = Object.fromEntries(overlay.capabilities.map((item) => [item.id, item.scale]));
const PARTS = Object.fromEntries(overlay.capabilities.map((item) => [item.id, item.part])); // where each is drawn, for the structures table (data/parts/structures.json)
const contract = await readFile(path.join(ROOT, "schema", "SPECIES.md"), "utf8");
const shapesNote = await readFile(path.join(ROOT, "schema", "SPECIES_SHAPES.md"), "utf8");
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;

// ---------------------------------------------------------------- the reader, as the build calls it

const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import species as reader
found, shapes, warnings, remarks = reader.read_species(sys.argv[2], json.loads(sys.argv[3]), json.loads(sys.argv[4]), json.loads(sys.argv[5]))
print(json.dumps({"species": found, "shapes": shapes, "warnings": warnings, "remarks": remarks,
                  "words": {"levels": reader.LEVELS, "states": reader.STATES, "kinds": sorted(reader.CELL_KINDS), "parts": sorted(reader.PARTS), "part_kinds": sorted(reader.PART_KINDS), "organelles": reader.ORGANELLES}}))
`;
/** `leftOut` names the capabilities the map leaves out of the picture for now, as the build passes them. */
function readFolder(folder, leftOut = []) {
  const run = spawnSync("python3", ["-c", READER, path.join(ROOT, "tools"), folder, JSON.stringify(CAPABILITIES), JSON.stringify(leftOut), JSON.stringify(PARTS)], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  return JSON.parse(run.stdout);
}

const scratch = await mkdtemp(path.join(os.tmpdir(), "cells-levels-"));
test.after(() => rm(scratch, { recursive: true, force: true }));
let folders = 0;
/** Reads a folder made of the given species files (id -> data, or text) and shape files. */
async function read(files, shapes = {}, leftOut = []) {
  const folder = path.join(scratch, `set-${++folders}`);
  await mkdir(path.join(folder, "shapes"), { recursive: true });
  for (const [name, data] of Object.entries(files)) await writeFile(path.join(folder, `${name}.json`), typeof data === "string" ? data : JSON.stringify(data));
  for (const [name, data] of Object.entries(shapes)) await writeFile(path.join(folder, "shapes", `${name}.json`), typeof data === "string" ? data : JSON.stringify(data));
  return readFolder(folder, leftOut);
}

// A made-up species: a rod-shaped cell in a small sheet, with a body of its own.
const madeUp = (change = () => {}) => {
  const data = {
    format: "cells.visualizer.species@1",
    id: "rodlet",
    label: "Rodlet",
    organism: "Bacillus exemplaris",
    taxon: null,
    plain: "A made-up species, to show that a species is added with files alone.",
    order: 40,
    default: true,
    made: "2026-11-14",
    modelled: { state: "proposed", text: "A made-up species for a test: nothing of it is in the engine." },
    levels: [
      { id: "molecules" },
      { id: "cell", shape: { kind: "capsule", length_um: 4, across_um: 1.2 }, notes: ["A rod-shaped cell"], sources: ["made"] },
      { id: "tissue", shape: { kind: "cell sheet", rings: 3 } },
      { id: "organism", label: "Whole body", shape: { kind: "outline", ref: "rodlet" } },
    ],
    no_further_levels: "It has no organs.",
    cell: {
      facts: [{ label: "Length", value: "4 µm", sources: ["made"] }],
      parts: { membranes: 2, wall: true, nucleus: false, chromosome_kbp: 4000, ribosomes: 2000 },
      capabilities: { "cap.calcium": { place: "absent", why: "It has no endoplasmic reticulum." }, "cap.circuits": { place: "present", note: "At the chromosome." } },
    },
    sources: { made: { text: "Made up for the test.", url: "https://example.org/made-up", accessed: "2026-11-14" } },
  };
  change(data);
  return data;
};
const body = (change = () => {}) => {
  const data = {
    format: "cells.visualizer.outline@1",
    note: "A made-up body.",
    tissue_on: { at_um: [120, 14, 0], clearance_um: 1 },
    parts: [
      { name: "body", kind: "loft", stations: [[0, 0, 0, 0, 0], [60, 0, 0, 30, 12], [200, 0, 0, 36, 14], [320, 0, 0, 0, 0]], rings: { from: 0.1, to: 0.95, step: 0.1, points: 16 }, lines: [0.5, 1.5], strength: 0.5, edge: 1, fill: 0.07, pick: 12 },
      { name: "eye", kind: "discs", at: [[40, 13, 10]], radius_um: 4, strength: 0.8 },
      { name: "fin", kind: "lines", paths: [{ points: [[300, 0, -20], [340, 0, 0], [300, 0, 20]], closed: false }], strength: 0.7 },
    ],
  };
  change(data);
  return data;
};
const sound = await read({ rodlet: madeUp() }, { rodlet: body() });

test("a made-up species with a rod-shaped cell and a body of its own is read from files alone", () => {
  assert.deepEqual(sound.warnings, []);
  assert.equal(sound.species.length, 1);
  const [species] = sound.species;
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell", "tissue", "organism"]);
  assert.equal(species.default, true);
  assert.equal(species.no_further_levels, "It has no organs.");
  assert.deepEqual(Object.keys(sound.shapes), ["rodlet"], "the scene carries the shape files the species use");
  assert.equal(sound.shapes.rodlet.parts.length, 3);
  // Its cell is small, and is drawn in both size modes all the same: the build no longer remarks on its size.
  assert.ok(!sound.remarks.some((remark) => /size mode/.test(remark)), JSON.stringify(sound.remarks));
});

test("what breaks the contracts is warned about, and the species is left out", async () => {
  const cases = [
    ["an id that is not the file's name", (data) => (data.id = "other"), /is not the file's name/],
    ["an unknown level", (data) => data.levels.push({ id: "colony", shape: { kind: "outline", ref: "rodlet" } }), /a level's id is one of/],
    ["levels out of order", (data) => data.levels.reverse(), /from small to large/],
    ["no cell level", (data) => data.levels.splice(1, 1), /it has no cell level/],
    ["no sentence for the levels it lacks", (data) => delete data.no_further_levels, /says so in no_further_levels/],
    ["an unknown kind of cell", (data) => (data.levels[1].shape = { kind: "cube", across_um: 2 }), /unknown kind 'cube'/],
    ["a capsule without its length", (data) => delete data.levels[1].shape.length_um, /a capsule needs length_um/],
    ["a parameter the kind does not take", (data) => (data.levels[1].shape.sides = 6), /a capsule does not take sides/],
    ["a tip wider than the cell", (data) => (data.levels[1].shape.tip_um = 3), /tip is no wider than the capsule/],
    ["a prism with both widths", (data) => (data.levels[1].shape = { kind: "prism", sides: 6, across_um: 18, radius_um: 10, height_um: 13 }), /across_um or radius_um, one of the two/],
    ["a part the viewer cannot draw", (data) => (data.cell.parts.flagella = 3), /cannot draw the part flagella/],
    ["a chromosome beside a nucleus", (data) => (data.cell.parts.nucleus = true), /only in a cell without a nucleus/],
    ["a capability the map does not have", (data) => (data.cell.capabilities["cap.photosynthesis"] = { place: "absent", why: "None." }), /is not a capability of the map/],
    ["absent without a why", (data) => delete data.cell.capabilities["cap.calcium"].why, /absent without a why/],
    ["a state that is not one of the three", (data) => (data.modelled.state = "simulated"), /modelled needs a state/],
    ["a source that is not cited by a key", (data) => (data.cell.facts[0].sources = ["nowhere"]), /cites 'nowhere'/],
    ["a source without the day it was read", (data) => delete data.sources.made.accessed, /the day it was read/],
    ["a shape file that is not there", (data) => (data.levels[3].shape.ref = "missing"), /cannot be read/],
    ["a part the shape file does not have", (data) => (data.levels[3].shape.parts = ["wings"]), /no part named wings/],
    ["a machine path", (data) => (data.plain = "See /home/someone/notes."), /machine path/],
    ["a heading for the list that is not a few words", (data) => (data.group = ["Bacteria"]), /group is a heading of a few words/],
    ["an empty heading for the list", (data) => (data.group = " "), /group is a heading of a few words/],
    ["framing the level does not take", (data) => (data.levels[3].camera = "near"), /does not take camera/],
    ["a looping run named by no id", (data) => (data.cell_type = { loop: " " }), /cell_type is \{id, label, loop\}/],
    ["a cell type with a key it does not take", (data) => (data.cell_type = { loops: "x" }), /cell_type is \{id, label, loop\}/],
    ["a loop in the cell block, where the cell type holds it", (data) => (data.cell.loop = "some-run"), /cell does not take loop/],
  ];
  for (const [name, change, expected] of cases) {
    const result = await read({ rodlet: madeUp(change) }, { rodlet: body() });
    assert.ok(result.warnings.some((warning) => expected.test(warning)), `${name}: ${JSON.stringify(result.warnings)}`);
    assert.equal(result.species.length, 0, `${name}: the species is left out`);
  }
  // A species' own cell type may name its looping run among the packaged replays (CELL_TYPES.md, `loop`): the scene carries the block.
  const looped = await read({ rodlet: madeUp((data) => (data.cell_type = { loop: "some-run--its-arm" })) }, { rodlet: body() });
  assert.deepEqual([looped.warnings, looped.species[0]?.cell_type], [[], { loop: "some-run--its-arm" }]);
  const loft = await read({ rodlet: madeUp() }, { rodlet: body((data) => (data.parts[0].stations = [[0, 0, 0]])) });
  assert.ok(loft.warnings.some((warning) => /two or more stations/.test(warning)), JSON.stringify(loft.warnings));
  const kind = await read({ rodlet: madeUp() }, { rodlet: body((data) => (data.parts[1].kind = "blob")) });
  assert.ok(kind.warnings.some((warning) => /unknown kind 'blob'/.test(warning)), JSON.stringify(kind.warnings));
});

test("a file that cannot be read is one warning, and the others are still shown", async () => {
  const result = await read({ rodlet: madeUp(), broken: "{ not json" }, { rodlet: body() });
  assert.equal(result.warnings.length, 1, JSON.stringify(result.warnings));
  assert.match(result.warnings[0], /broken\.json: it cannot be read/);
  assert.deepEqual(result.species.map((item) => item.id), ["rodlet"]);
});

test("exactly one species is the one the page opens on", async () => {
  const second = madeUp((data) => Object.assign(data, { id: "second", order: 50 }));
  const two = await read({ rodlet: madeUp(), second }, { rodlet: body() });
  assert.ok(two.warnings.some((warning) => /exactly one species is the default; 2 say so/.test(warning)), JSON.stringify(two.warnings));
  const none = await read({ rodlet: madeUp((data) => (data.default = false)) }, { rodlet: body() });
  assert.ok(none.warnings.some((warning) => /exactly one species is the default; 0 say so/.test(warning)), JSON.stringify(none.warnings));
  // The scene still opens on one of them.
  assert.equal(none.species.filter((item) => item.default).length, 1);
  assert.equal(defaultSpecies({ species: two.species.map((item, index) => ({ ...item, default: index === 1 })) }), "second");
  assert.equal(defaultSpecies({}), null, "a scene that names no species has no default");
});

test("a capability that is present where the cell holds no such structure is remarked on, not warned about", async () => {
  const result = await read({ rodlet: madeUp((data) => delete data.cell.capabilities["cap.calcium"]) }, { rodlet: body() });
  assert.deepEqual(result.warnings, []);
  assert.ok(result.remarks.some((remark) => /cap\.calcium is present, but the cell holds no er/.test(remark)), JSON.stringify(result.remarks));
});

test("the contract names every word the reader takes", () => {
  const { words } = sound;
  for (const level of words.levels) assert.ok(contract.includes(`\`${level}\``), `SPECIES.md does not name the level ${level}`);
  for (const state of words.states) assert.ok(contract.includes(`\`${state}\``), `SPECIES.md does not name the state ${state}`);
  for (const kind of [...words.kinds, "cell sheet", "outline", ...words.part_kinds]) assert.ok(shapesNote.includes(`\`${kind}\``), `SPECIES_SHAPES.md does not name the kind ${kind}`);
  for (const part of [...words.parts, ...words.organelles]) assert.ok(shapesNote.includes(`\`${part}\``), `SPECIES_SHAPES.md does not name the part ${part}`);
  assert.deepEqual(Object.keys(MODELLED).sort(), [...words.states].sort(), "the viewer has words for each state");
});

// ---------------------------------------------------------------- the repository's own species

const own = readFolder(SPECIES);

test("the repository's species hold to the contracts, and one of them is the default", () => {
  assert.deepEqual(own.warnings, []);
  assert.ok(own.species.length >= 2, "at least the human and the planarian");
  assert.equal(own.species.filter((item) => item.default).length, 1);
  assert.equal(defaultSpecies({ species: own.species }), "planarian", "the page opens on the planarian");
  const orders = own.species.map((item) => item.order);
  assert.deepEqual(orders, [...orders].sort((a, b) => a - b), "the species come in their order");
  for (const item of own.species) {
    assert.ok(item.levels.some((level) => level.id === "molecules") && item.levels.some((level) => level.id === "cell"), item.id);
    assert.ok(!MACHINE.test(JSON.stringify(item)), `machine path in ${item.id}`);
  }
});

test("no species is said to be modelled by the engine, and a proposal says nothing of it is in the engine", () => {
  for (const item of own.species) {
    assert.notEqual(item.modelled.state, "modelled", `${item.id}: no registered model of an organism exists today`);
    if (item.modelled.state === "proposed") assert.match(item.modelled.text, /nothing of it is in the engine|not in the engine|no .* in the engine/i, item.id);
    if (item.modelled.state === "generic") assert.match(item.modelled.text, /generic/, item.id);
    assert.ok(!/the engine (models|simulates) (this|the) (animal|organism|species|worm|bacterium)/i.test(JSON.stringify(item)), item.id);
  }
});

test("the planarian's levels and shapes are data, with the numbers its drawing had", () => {
  const planarian = own.species.find((item) => item.id === "planarian");
  const level = (id) => planarian.levels.find((item) => item.id === id);
  assert.deepEqual(planarian.levels.map((item) => item.id), ["molecules", "cell", "tissue", "organ", "organism"]);
  assert.deepEqual(level("cell").shape, { kind: "prism", sides: 6, radius_um: 10.6, height_um: 13, corner_um: 2.4, edge_um: 1.3 });
  assert.equal(level("tissue").shape.rings, 6);
  assert.deepEqual(level("organ").view.frame_um, [2900, 1900]);
  assert.deepEqual(level("organism").view.frame_um, [15000, 9600]);
  const shape = own.shapes.planarian;
  assert.deepEqual(shape.parts.map((part) => [part.name, part.kind]), [["body", "loft"], ["eyespots and pharynx", "lines"], ["eye cups", "discs"], ["brain", "loft"], ["nerves and cords", "lines"]]);
  // The sheet lies on the back of the head, above the brain: the frame is set down from there.
  const origin = outlineOrigin(shape);
  assert.ok(Math.abs(origin.x + 790) < 1e-9 && Math.abs(origin.y + 153.9929) < 1e-3 && origin.z === 0, JSON.stringify(origin.toArray()));
  // The organ is the nervous system alone, framed as the species says; the body is every part.
  const organ = outlineFrame(level("organ"), shape), organism = outlineFrame(level("organism"), shape);
  assert.deepEqual(organ.centre.toArray(), [790, -30, 0]);
  assert.deepEqual(organ.frame, [2900, 1900]);
  assert.deepEqual(organism.centre.toArray(), [5000, 0, 0]);
  assert.ok(Math.abs(organism.size.x - 10000) < 1 && organism.size.z >= 1300 && organism.size.z < 1500, JSON.stringify(organism.size.toArray()));
  // The notes that keep the picture honest come from the file.
  const said = JSON.stringify(planarian.levels);
  for (const words of ["stands for skin-like tissue", "placeholder outline", "are not modelled", "the picture's choice"]) assert.ok(said.includes(words), words);
});

test("a level that gives no framing is framed from the size of its own parts", () => {
  const level = { id: "organism", shape: { kind: "outline", ref: "rodlet" } };
  const frame = outlineFrame(level, body());
  assert.ok(Math.abs(frame.centre.x - 170) < 1 && Math.abs(frame.size.x - 340) < 1, JSON.stringify([frame.centre.toArray(), frame.size.toArray()]));
  assert.ok(frame.frame[0] > 340 && frame.frame[1] > 0, "the frame holds the whole body");
  assert.deepEqual(outlineOrigin(body()).toArray(), [-120, -15, -0]);
  assert.deepEqual(outlineOrigin({ parts: [] }).toArray(), [0, 0, 0], "a body that says nothing of the sheet stands at the origin");
});

// ---------------------------------------------------------------- shapes from parameters

const close = (a, b, tolerance = 1e-9) => Math.abs(a - b) <= tolerance;

test("an outline of any number of sides, and a round-ended one, answer the same questions", () => {
  const outlines = [
    ["six sides", polygonOutline(6, 8.7, 2.4, 1.6)],
    ["four sides", polygonOutline(4, 5, 1, 1.6)],
    ["nine sides", polygonOutline(9, 7, 0.8, 1.6)],
    ["a circle", stadiumOutline(0, 6, 1.6)],
    ["a round-ended rod", stadiumOutline(9, 4, 1.6)],
    ["a rod that narrows to a tip", stadiumOutline(9, 5, 1.6, 2)],
  ];
  for (const [name, outline] of outlines) {
    for (let step = 0; step < 48; step++) {
      const angle = (step / 48) * Math.PI * 2 - Math.PI;
      const point = outline.point(angle, 0, 0);
      // The point named by an angle lies at that angle, on the outline, at the stated distance.
      const there = Math.atan2(point.z, point.x);
      assert.ok(close(Math.cos(there), Math.cos(angle), 1e-6) && close(Math.sin(there), Math.sin(angle), 1e-6), `${name}: angle ${angle}`);
      assert.ok(close(Math.hypot(point.x, point.z), outline.radius(angle), 1e-6), `${name}: radius at ${angle}`);
      assert.ok(close(outline.depth(point.x, point.z), 0, 1e-6), `${name}: a point of the outline is neither inside nor outside`);
      // A step inwards is inside by that much.
      const inner = outline.point(angle, -0.3, 0);
      assert.ok(close(outline.depth(inner.x, inner.z), 0.3, 1e-6), `${name}: 0.3 inside at ${angle}`);
    }
    // Walking the whole length comes back to the start.
    const start = outline.spot(0, 0, 0), again = outline.spot(outline.length, 0, 0);
    assert.ok(start.distanceTo(again) < 1e-6, `${name}: the outline closes`);
    assert.ok(outline.widest >= outline.apothem, name);
    // The same outline drawn inside itself.
    const smaller = outline.inset(0.5);
    assert.ok(close(smaller.radius(0.3), outline.radius(0.3, -0.5), 1e-6), `${name}: inset`);
    assert.ok(outline.ring(0, 0).length > 12 && outline.corners.length >= 3, name);
  }
  // A flat side faces angle 0, and a rod lies along x.
  assert.ok(close(polygonOutline(6, 8.7, 2.4, 0).radius(0), 8.7));
  assert.ok(close(stadiumOutline(9, 4, 0).radius(0), 13) && close(stadiumOutline(9, 4, 0).radius(Math.PI / 2), 4));
  assert.ok(close(stadiumOutline(9, 4, 0).length, 36 + 8 * Math.PI));
  // A tip: the wide end faces angle 0, the narrow end lies the other way, and the body is round all along.
  const club = stadiumOutline(9, 5, 0, 2);
  assert.ok(close(club.radius(0), 14, 1e-9) && close(club.radius(Math.PI), 11, 1e-9));
  assert.ok(close(club.at(0).rho, 5) && close(club.at(club.reach(Math.PI)).rho, 2), "its radius is the wide end's at one end and the tip's at the other");
  assert.ok(close(club.depth3({ x: 9, y: 3, z: 4 }), 0, 1e-9) && close(club.depth3({ x: -9, y: 0, z: 0 }), 2, 1e-9), "inside by its own radius at the tip's middle");
});

test("a cell's frame follows its shape: a prism, a sphere and a capsule", () => {
  // The reference cell is the six-sided cell of a layer: its frame is one micrometre to the unit.
  const prism = cellFrame({ kind: "prism", sides: 6, radius_um: REF.radius, height_um: 13, corner_um: 2.4, edge_um: 1.3 }, 0.9);
  assert.equal(prism.u, 1);
  assert.deepEqual([prism.top, prism.base, prism.bevel, prism.round], [6.5, -6.5, 1.3, false]);
  assert.equal(prism.outline, prism.equator, "the cut passes through its upright sides");
  assert.ok(close(prism.equator.apothem, (REF.radius * Math.sqrt(3) - 0.9) / 2));
  // The same width given between opposite sides, and other numbers of sides.
  assert.ok(close(cellAcross({ kind: "prism", sides: 6, across_um: 18 }), 18) && close(cellAcross({ kind: "prism", sides: 4, radius_um: 10 }), 10 * Math.SQRT2));
  // A sphere 0.4 µm across: about 46 units to the micrometre, round all over, cut above its middle.
  const sphere = cellFrame({ kind: "sphere", across_um: 0.4 });
  assert.ok(close(sphere.u, 0.4 / REF.pitch) && sphere.round && close(sphere.top, REF.pitch / 2, 1e-9) && close(sphere.bevel, sphere.top));
  assert.ok(sphere.outline.apothem < sphere.equator.apothem, "the cut lies above the widest girth, so its edge is a little smaller");
  for (const y of [-8, -3, 0, 1.6, 5, 8.5]) {
    const point = sphere.skin(0.7, y);
    assert.ok(close(point.length(), sphere.top, 1e-6), `the sphere's skin at height ${y} is ${point.length()} from its middle`);
  }
  assert.ok(close(sphere.inside({ x: 0, y: 0, z: 0 }), sphere.top) && sphere.inside({ x: sphere.top + 1, y: 0, z: 0 }) < 0);
  // A capsule is as wide as the sphere and longer along x.
  const capsule = cellFrame({ kind: "capsule", length_um: 4, across_um: 1.2 });
  assert.ok(close(capsule.u, 1.2 / REF.pitch) && close(capsule.equator.radius(Math.PI / 2), REF.pitch / 2, 1e-6));
  assert.ok(close(capsule.equator.radius(0) * 2 * capsule.u, 4, 1e-6), "its length in micrometres is the species' own");
  assert.ok(close(capsule.long * capsule.u, 4, 1e-6) && capsule.middle === 0);
  // With a tip it narrows to one end, keeps its length, and its middle lies toward the wide end.
  const club = cellFrame({ kind: "capsule", length_um: 2, across_um: 0.5, tip_um: 0.2 });
  assert.ok(close(club.long * club.u, 2, 1e-6) && club.middle > 0, JSON.stringify([club.long * club.u, club.middle]));
  assert.ok(close(club.equator.at(0).rho * 2 * club.u, 0.5, 1e-9) && close(club.equator.at(club.equator.reach(Math.PI)).rho * 2 * club.u, 0.2, 1e-9), "as wide as the species says at its wide end, and as its tip at the other");
  assert.ok(club.equator.radius(Math.PI) < club.equator.radius(0));
  for (const y of [-6, 0, 1.6, 4]) for (const angle of [0, 1.2, 2.6, 3.1, 4.4]) assert.ok(Math.abs(club.inside(club.skin(angle, y))) < 1e-6, `the tapered cell's skin at ${angle}, ${y}`);
  assert.ok(club.outline.apothem < club.equator.apothem, "its cut edge is narrower than its girth, at both ends");
});

test("a solid is closed and no larger than its shape", () => {
  const frames = [cellFrame({ kind: "prism", sides: 6, radius_um: REF.radius, height_um: 13, corner_um: 2.4, edge_um: 1.3 }), cellFrame({ kind: "sphere", across_um: 0.4 }), cellFrame({ kind: "capsule", length_um: 4, across_um: 1.2 }), cellFrame({ kind: "capsule", length_um: 2, across_um: 0.5, tip_um: 0.2 })];
  for (const frame of frames) {
    const geometry = solidGeometry(frame.equator, frame.top, frame.base, frame.bevel);
    const position = geometry.attributes.position;
    let top = -Infinity, base = Infinity, wide = 0;
    for (let index = 0; index < position.count; index++) {
      top = Math.max(top, position.getY(index));
      base = Math.min(base, position.getY(index));
      wide = Math.max(wide, Math.hypot(position.getX(index), position.getZ(index)));
      assert.ok(frame.inside({ x: position.getX(index), y: position.getY(index), z: position.getZ(index) }) > -1e-5, `${frame.kind}: a corner of the solid lies outside its shape`);
    }
    // The corners are kept as 32-bit numbers, so they agree to about one part in ten million.
    assert.ok(close(top, frame.top, 1e-5) && close(base, frame.base, 1e-5) && close(wide, frame.equator.widest, 1e-5), frame.kind);
    assert.equal(geometry.index.count % 3, 0);
  }
});

// ---------------------------------------------------------------- a capability left out of the picture

test("a species' place for a capability that the map leaves out is read and checked, and not carried into the scene", async () => {
  // The made-up species names a place for the regulatory circuits; say the map leaves those out for now.
  const kept = await read({ rodlet: madeUp() }, { rodlet: body() });
  assert.ok("cap.circuits" in kept.species[0].cell.capabilities);
  const result = await read({ rodlet: madeUp() }, { rodlet: body() }, ["cap.circuits"]);
  assert.deepEqual(result.warnings, []);
  assert.ok(!("cap.circuits" in result.species[0].cell.capabilities), "the place is not in what the scene gets");
  assert.ok("cap.calcium" in result.species[0].cell.capabilities, "every other place stays");
  assert.ok(result.remarks.some((remark) => /rodlet\.json: its place for cap\.circuits is not shown: left out of the picture for now/.test(remark)), result.remarks.join("; "));
  // It is still held to the contract: a place that breaks it is warned about, left out or not.
  const broken = await read({ rodlet: madeUp((data) => (data.cell.capabilities["cap.circuits"] = { place: "absent" })) }, { rodlet: body() }, ["cap.circuits"]);
  assert.match(broken.warnings.join("; "), /cap\.circuits is absent without a why/);
  // The repository's own files: whatever the map's overlay flags as left out is in no species' scene entry.
  const flagged = overlay.capabilities.filter((item) => item.left_out).map((item) => item.id);
  const shown = readFolder(SPECIES, flagged);
  assert.deepEqual(shown.warnings, []);
  for (const species of shown.species) for (const id of flagged) assert.ok(!(id in species.cell.capabilities), `${species.id}: ${id}`);
});

test("the cell does not draw a part that the scene leaves out of the picture, even as scenery", () => {
  const lens = { leftOut: new Set(["cage"]), capabilityByPart: new Map([["er", { id: "cap.calcium" }], ["wound", { id: "cap.repair" }]]), absent: new Map([["cap.calcium", "It has no endoplasmic reticulum."]]) };
  const draws = (part) => CellLens.prototype.draws.call(lens, part);
  assert.equal(draws("cage"), false, "left out of the picture");
  assert.equal(draws("er"), false, "its capability has no place in the species");
  assert.equal(draws("wound"), true, "a capability with a place");
  assert.equal(draws("cytoskeleton"), true, "a part with no capability is scenery, and is drawn");
  // Brought back: with nothing left out, the same part with no capability in the scene is scenery again.
  assert.equal(CellLens.prototype.draws.call({ ...lens, leftOut: new Set() }, "cage"), true);
});

// ---------------------------------------------------------------- what the lens works out for a species

/** What the lens plans for a species, before anything is drawn (it needs no 3D stage). */
function planned(species) {
  const lens = { species, model: { ofKind: (kind) => (kind === "capability" ? overlay.capabilities.map((item) => ({ id: item.id, scale: item.scale })) : []) }, sizeMode: "real" };
  CellLens.prototype.plan.call(lens);
  return lens;
}

test("the levels, the size modes and what has no place follow the species", () => {
  const rodlet = planned(sound.species[0]);
  assert.deepEqual(Object.entries(rodlet.levels).filter(([, level]) => level).map(([id]) => id), ["molecules", "cell", "tissue", "organism"]);
  assert.deepEqual(rodlet.modes, ["schematic", "real"], "every cell is drawn in both size modes, however small");
  assert.equal(rodlet.sizeMode, "real", "the mode asked for is kept");
  assert.equal(rodlet.absent.get("cap.calcium"), "It has no endoplasmic reticulum.");
  assert.equal(rodlet.absent.get("scale.organ"), "It has no organs.", "a level the species lacks has the species' own sentence as its reason");
  assert.ok(!rodlet.absent.has("cap.sheet") && !rodlet.absent.has("cap.circuits"));
  for (const species of own.species) {
    const lens = planned(species);
    const levels = species.levels.map((level) => level.id);
    for (const [id, scale] of Object.entries(CAPABILITIES)) {
      const said = species.cell.capabilities[id]?.place === "absent";
      assert.equal(lens.absent.has(id), said || !levels.includes(scale), `${species.id}: ${id}`);
    }
    assert.deepEqual(lens.modes, ["schematic", "real"], species.id);
  }
  // The planarian and the human are animals: every capability has a place, in both size modes.
  for (const id of ["planarian", "human"]) {
    const lens = planned(own.species.find((item) => item.id === id));
    assert.equal([...lens.absent.keys()].filter((key) => key.startsWith("cap.")).length, 0, id);
    assert.equal(lens.u, 1, id);
  }
});

test("shared views and controls take their species and model names from the scene", async () => {
  // The modules that draw and that hold the switch, but not the replay of runs, which names
  // experiments. The stage and its controls are left out: they know nothing of species, and an
  // everyday word there (a species called Mouse, say) would be a false alarm.
  const files = [];
  for (const folder of ["lenses", path.join("lenses", "parts"), "ui"]) {
    for (const name of await readdir(path.join(ROOT, "src", folder))) if (name.endsWith(".js") && name !== "replay.js") files.push(path.join("src", folder, name));
  }
  for (const name of ["cell.js", "cell_parts.js", "shapes.js", "outline_parts.js", "proteins.js", "protein_parts.js"]) assert.ok(files.includes(path.join("src", "lenses", name)), name);
  // The names the repository's species go by, whichever they are, and the organs and bodies drawn so far.
  const words = new Set(["worm", "brain", "heart", "flask"]);
  for (const name of (await readdir(SPECIES)).filter((item) => item.endsWith(".json"))) {
    const data = JSON.parse(await readFile(path.join(SPECIES, name), "utf8"));
    for (const word of [data.id, data.label, ...String(data.organism || "").split(/\s+/).slice(0, 2)]) if (word && word.length > 3) words.add(word.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  }
  // And the switch's other entries (schema/ENTRIES.md): cell types of their own files, and model systems.
  for (const folder of ["cells", "models"]) {
    const dir = path.join(ROOT, "data", folder);
    for (const name of (await readdir(dir).catch(() => [])).filter((item) => item.endsWith(".json"))) {
      const data = JSON.parse(await readFile(path.join(dir, name), "utf8"));
      for (const word of [data.id, data.label]) if (word && word.length > 3) words.add(word.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    }
  }
  // A dedicated anatomy view and the registry can name the view they provide.
  const anatomyViews = ["physarum", "haloferax"];
  const named = new RegExp(`\\b(${[...words].join("|")})\\b`, "gi");
  for (const file of files) {
    const code = (await readFile(path.join(ROOT, file), "utf8")).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
    const permitted = anatomyViews.filter((id) => file === path.join("src", "ui", "model_views.js") || file === path.join("src", "lenses", `${id}.js`));
    const found = [...code.matchAll(named)].find(([name]) => !permitted.includes(name.toLowerCase()));
    assert.ok(!found, `${file} names a species or one of its organs in its code: ${found?.[0]}`);
  }
});

test("the page has styles for the species switch and the rail's note", () => {
  for (const selector of [".species", ".species-state", ".rail-note", ".with-species"]) assert.ok(css.includes(selector), selector);
});

test("the species switch is a dropdown: a pill, a list of the page's own with its rows and headings, and a sheet under it", () => {
  for (const selector of [".species-pick", ".species-pick-caret", ".species-list", ".species-veil", ".species-group-name", ".species-option", ".species-option-organism", ".species-option-state", ".species-option.is-active"]) assert.ok(css.includes(selector), selector);
  // The organism is written in italics, and the row of buttons the switch used to be is gone from the bar's rules.
  assert.match(css, /\.species-option-organism \{[^}]*font-style: italic/);
  assert.ok(!css.includes(".species .seg button"), "the bar no longer styles a row of species buttons");
});

test("a species may say under which heading it stands in the list, and the scene carries it", async () => {
  const grouped = await read({ rodlet: madeUp((data) => (data.group = "Bacteria")) }, { rodlet: body() });
  assert.deepEqual(grouped.warnings, []);
  assert.equal(grouped.species[0].group, "Bacteria");
  assert.ok(!("group" in sound.species[0]), "a species without one has none in the scene");
  // The repository's own: each has a heading, and the species of one heading stand together in the files' order.
  const headings = own.species.map((item) => item.group);
  assert.ok(headings.every((group) => typeof group === "string" && group.trim()), JSON.stringify(headings));
  const firsts = [...new Set(headings)];
  assert.deepEqual(headings, firsts.flatMap((group) => headings.filter((other) => other === group)), "the species of one heading follow one another");
});
