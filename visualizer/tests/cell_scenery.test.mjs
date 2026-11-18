// Scenery of a species' own in the cell (src/lenses/cell_scenery.js): threads and hairs that
// stand out from it, the machine at a thread's foot, a plant cell's vacuole and chloroplasts,
// and the packing of a layer by the cell's sides (src/lenses/shapes.js). The words of the
// species' files must reach the lens, what is drawn must be the data's numbers and sizes,
// and a species without these parts must be built as before.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildCell, buildTissue } from "../src/lenses/cell_parts.js";
import { APPENDAGES, ORGANELLES, MOST, middle, words, vacuoleOf } from "../src/lenses/cell_scenery.js";
import { cellFrame, packing, REF } from "../src/lenses/shapes.js";
import { describeScenery, CellLens } from "../src/lenses/cell.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const species = (id) => json(`data/species/${id}.json`);

/** A stand-in for the lens: it keeps what the builder adds, and under which id it can be chosen. */
function stand() {
  const added = [];
  const keep = (object, tag) => object.traverse?.((item) => (item.isMesh || item.isPoints || item.isLine) && added.push({ item, tag, pick: object.userData.pick || null }));
  const standard = (options = {}) => Object.assign(new THREE.MeshStandardMaterial(), { userData: { options } });
  const part = (name, anchor) => ({ name, anchor: anchor || null, group: new THREE.Group(), material: standard, points: () => new THREE.PointsMaterial(), lineMaterial: () => new THREE.LineBasicMaterial(), proxyMaterial: () => new THREE.MeshBasicMaterial(), add: (...objects) => objects.forEach((object) => keep(object, name)) });
  return {
    added,
    ctx: {
      part,
      scale: part,
      neutral: standard,
      neutralPoints: () => new THREE.PointsMaterial(),
      neutralLine: (options = {}) => (options.dashed ? new THREE.LineDashedMaterial() : new THREE.LineBasicMaterial()),
      illustrate: (object) => keep(object, "scenery"),
      scenery: (object, id) => ((object.userData.pick = id), keep(object, "chosen")),
      sprite: () => {},
    },
  };
}
/** One species' cell, built as the lens builds it. */
function built(file, mode = "schematic") {
  const levels = Object.fromEntries(file.levels.map((level) => [level.id, level]));
  const a = stand(), b = stand();
  const cell = { shape: levels.cell.shape, parts: file.cell.parts || {}, has: () => true, neighbours: Boolean(levels.tissue), notes: [] };
  const handles = buildCell(a.ctx, b.ctx, mode, cell);
  return { handles, added: [...a.added, ...b.added], chosen: a.added.filter((entry) => entry.pick), frame: cellFrame(levels.cell.shape, 0), levels };
}
const boxOf = (geometry) => new THREE.Box3().setFromBufferAttribute(geometry.attributes.position);
/** The clear shells outside the cell membrane (a wall, an outer membrane), innermost first: drawn as scenery round the cell's own middle. */
const shellsOf = (added) => added.filter((entry) => entry.tag === "scenery" && entry.item.isMesh && entry.item.renderOrder === 7 && entry.item.position.lengthSq() === 0).map((entry) => entry.item).sort((a, b) => boxOf(a.geometry).max.x - boxOf(b.geometry).max.x);
/**
 * How far outside the cell membrane a shell's surface stands: the nearest and the farthest of its vertices.
 * Of a flat-sided cell, the upright part between its rounded edges, at the corners and along the sides: where a
 * cell's edges are rounded more than its corners, as the plant cell's are, the cell's own `inside` is not a
 * distance near the corners of its faces.
 */
function gapsOf(shell, frame) {
  const position = shell.geometry.attributes.position, point = new THREE.Vector3();
  let near = Infinity, far = -Infinity;
  for (let index = 0; index < position.count; index++) {
    point.fromBufferAttribute(position, index);
    if (!frame.round && Math.abs(point.y) > frame.top - frame.bevel + 1e-9) continue;
    const gap = -frame.inside(point);
    near = Math.min(near, gap);
    far = Math.max(far, gap);
  }
  return [near, far];
}

test("a number or a range of two: its middle, and its words", () => {
  assert.equal(middle([5, 10]), 7.5);
  assert.equal(middle(20), 20);
  assert.equal(words([200, 500]), "200 to 500");
  assert.equal(words(1, "µm"), "1 µm");
});

test("E. coli's flagella and fimbriae are drawn from the species' own words, in the numbers and sizes they give", () => {
  const file = species("ecoli");
  const [threads, hairs] = file.cell.parts.appendages;
  assert.deepEqual([threads.kind, hairs.kind], ["flagellum", "pilus"], "the file names two kinds the viewer can draw");
  const { handles, chosen, frame } = built(file);
  const ids = handles.scenery.map((item) => item.id);
  assert.deepEqual(ids, ["scenery:appendage:0", "scenery:appendage:0:base", "scenery:appendage:1"], "each kind can be chosen, and the machine at the flagellum's foot is a part of its own");
  // Flagella: as many as the middle of the range, each as long and as wide as the middle of what is given.
  const flagella = chosen.filter((entry) => entry.pick === "scenery:appendage:0");
  assert.equal(flagella.length, Math.round(middle(threads.count)));
  assert.equal(handles.scenery[0].drawn, flagella.length);
  assert.deepEqual(handles.scenery[0].of, threads.count);
  const length = middle(threads.length_um) / frame.u;
  for (const { item } of flagella) {
    assert.equal(item.geometry.type, "TubeGeometry");
    assert.ok(Math.abs(item.geometry.parameters.path.getLength() - length) / length < 0.25, "a thread's own length, with its wave, is near the length given");
    assert.ok(Math.abs(item.geometry.parameters.radius - middle(threads.width_nm) / 2000 / frame.u) < 1e-9, "and it is as wide as given");
  }
  assert.ok(handles.reach > length, "the lens is told how far the longest thread reaches, so that the camera may go out to it");
  assert.ok(length > frame.long * 2, "a flagellum is several times the cell's length");
  // Every flagellum has a foot.
  assert.equal(chosen.filter((entry) => entry.pick === "scenery:appendage:0:base").length, flagella.length);
  assert.deepEqual(handles.scenery[1].base, threads.base, "the foot carries the words under which the species' proteins list its parts");
  assert.equal(handles.scenery[1].feet.length, flagella.length, "and where each foot stands, for a closer view to be framed on later");
  for (const foot of handles.scenery[1].feet) assert.ok(Math.abs(frame.inside(foot.at)) < 0.05 && Math.abs(foot.out.length() - 1) < 1e-6, "on the cell membrane, with the way out");
  // Fimbriae: too many to draw, so a part of them is, and the picture says how many of how many.
  const fimbriae = chosen.find((entry) => entry.pick === "scenery:appendage:1").item;
  assert.equal(fimbriae.count, MOST.pilus);
  assert.ok(MOST.pilus < threads.count[0] + hairs.count[0]);
  const hair = boxOf(fimbriae.geometry);
  assert.ok(Math.abs(hair.max.y - hair.min.y - middle(hairs.length_um) / frame.u) < 1e-4, "each as long as given");
  assert.ok(Math.abs(fimbriae.geometry.parameters.radiusTop - middle(hairs.width_nm) / 2000 / frame.u) < 1e-9, "and as wide");
  const lines = handles.notes.map((item) => item.text);
  assert.ok(lines.some((line) => /^3 of 1 to 5 flagella, each drawn 7\.5 µm long: zoom out for the whole of them$/.test(line)), lines.join(" | "));
  assert.ok(lines.includes("120 of 200 to 500 type 1 fimbriae drawn"), lines.join(" | "));
  // They start at the membrane the file names: a hair at the second membrane, a thread at the cell membrane.
  const copy = new THREE.Matrix4(), at = new THREE.Vector3();
  fimbriae.getMatrixAt(0, copy);
  at.setFromMatrixPosition(copy);
  // The wall of a cell with two membranes lies between them, so the second membrane is the outermost shell.
  assert.ok(handles.shells.wallGap > 0 && handles.shells.outerGap > handles.shells.wallGap, JSON.stringify(handles.shells));
  assert.ok(Math.abs(frame.inside(at) + handles.shells.outerGap) < 0.02, "a fimbria starts on the outer membrane's shell");
  // The foot of each flagellum passes through the whole envelope, which is as wide wherever it stands.
  for (const { item } of chosen.filter((entry) => entry.pick === "scenery:appendage:0:base")) assert.ok(Math.abs(item.geometry.parameters.height - (handles.shells.outerGap + 0.03 / frame.u)) < 1e-9, "through the shells");
  // All of it is neutral glass: scenery, with no status.
  for (const { item } of chosen) assert.ok(item.material.userData.options.opacity <= 0.9 && item.material.userData.options.hue === undefined, "neutral glass, not a part's own colour");
});

test("each shell stands at one distance outside the cell membrane all round, the wall between a cell's two membranes", () => {
  // E. coli: its wall and its outer membrane stand as far out at the poles as along the sides, where they stood before (17.5 and 37.5 nm).
  const ecoli = built(species("ecoli"));
  const side = ecoli.handles.frame.equator.apothem, u = ecoli.handles.frame.u;
  const [wall, outer] = shellsOf(ecoli.added);
  assert.ok(wall && outer, "two shells round a cell with two membranes and a wall");
  for (const [shell, gap, share] of [[wall, ecoli.handles.shells.wallGap, 0.035], [outer, ecoli.handles.shells.outerGap, 0.075]]) {
    const [near, far] = gapsOf(shell, ecoli.handles.frame);
    assert.ok(far - near < 1e-3 * gap && Math.abs(near - gap) < 1e-3 * gap, `one distance all round (${near} to ${far}, ${gap})`);
    assert.ok(Math.abs(gap - side * share) < 1e-12, "the distance it had along the sides");
  }
  assert.deepEqual([ecoli.handles.shells.wallGap, ecoli.handles.shells.outerGap].map((gap) => Math.round(gap * u * 10000) / 10), [17.5, 37.5]);
  // Thale cress: its wall, at a corner as at a side, in both size modes.
  const file = species("thalecress");
  for (const mode of ["schematic", "real"]) {
    const { added, handles } = built(file, mode);
    const shells = shellsOf(added);
    assert.equal(shells.length, 1, `${mode}: one shell, the wall`);
    const [near, far] = gapsOf(shells[0], handles.frame);
    assert.ok(far - near < 1e-3 * handles.shells.wallGap && Math.abs(near - handles.shells.wallGap) < 1e-3 * handles.shells.wallGap, `${mode}: one distance all round (${near} to ${far})`);
    assert.equal(handles.shells.outerGap, 0, "no second membrane");
    if (mode === "schematic") assert.ok(Math.abs(handles.shells.wallGap - handles.frame.equator.apothem * 0.045) < 1e-12, "the distance it had along the sides");
  }
  // A cell with neither: no shell at all.
  for (const id of ["syn3a", "human"]) {
    const { added, handles } = built(species(id));
    assert.deepEqual([shellsOf(added).length, handles.shells.wallGap, handles.shells.outerGap], [0, 0, 0], id);
  }
});

test("the scale bar says small parts are enlarged for as long as they are drawn so: a single cell at any distance", () => {
  const info = (u, distance, ranges, sizeMode = "schematic") => CellLens.prototype.scaleInfo.call({ stage: { rig: { distance } }, u, sizeMode, ranges });
  const single = { cell: {} }; // a cell that gives way to no larger level
  const layered = { cell: { out: [120, 200] }, tissue: { in: [120, 200], out: [900, 1600] } };
  assert.equal(info(0.0545, 12, single).note, "small parts enlarged", "E. coli 12 µm away, past 190 of its units");
  assert.equal(info(0.0545, 0.5, single).note, "Close-up not to scale");
  assert.equal(info(0.0545, 12, single, "real").note, null, "to scale it says nothing of enlarging");
  assert.equal(info(1, 150, layered).note, "small parts enlarged");
  assert.equal(info(1, 195, layered).note, null, "a cell that gives way to its tissue: past 190 units the note goes, as before");
  assert.equal(info(1, 1000, layered).note, "the outline is a placeholder");
});

test("a species without such parts is built with none of them", () => {
  // An animal cell's centrosome is scenery that can be chosen too, drawn with its Golgi (cell_structures.js; the user,
  // 17 November 2026): it is not a part of a species' file, and tests/cell_structures.test.mjs holds it.
  const own = (id) => id !== "scenery:centrosome";
  for (const id of ["planarian", "human", "syn3a", "mpneumoniae"]) {
    for (const mode of ["schematic", "real"]) {
      const { handles, added } = built(species(id), mode);
      assert.deepEqual(handles.scenery.filter((item) => own(item.id)), [], `${id}: nothing of the kind to choose`);
      assert.equal(handles.reach, 0);
      assert.ok(!added.some((entry) => String(entry.pick || "").startsWith("scenery:") && own(entry.pick)), `${id}: nothing of the kind drawn`);
      assert.deepEqual(handles.notes, [], `${id}: and the picture says no line more`);
    }
  }
});

test("a kind the viewer does not know draws nothing and is warned of; a new kind is one function", () => {
  assert.deepEqual(Object.keys(APPENDAGES), ["flagellum", "pilus"]);
  assert.deepEqual(Object.keys(ORGANELLES), ["vacuole", "chloroplasts"], "the vacuole first: what else the cell holds is pressed against it");
  const file = species("ecoli");
  file.cell.parts.appendages = [{ kind: "stalk", label: "Stalks", count: 1, length_um: 2, width_nm: 100, where: "one pole", from: "inner membrane" }];
  const warned = [], warn = console.warn;
  console.warn = (line) => warned.push(line);
  try {
    const { handles } = built(file);
    assert.deepEqual(handles.scenery, []);
  } finally {
    console.warn = warn;
  }
  assert.ok(warned.some((line) => /no drawing for an appendage of kind "stalk"/.test(line)));
  // The contract's `where`: threads asked for at one pole stand at one end of the cell's long way.
  const polar = species("ecoli");
  polar.cell.parts.appendages = [{ ...polar.cell.parts.appendages[1], where: "one pole", count: 30 }];
  const { chosen, frame } = built(polar);
  const hairs = chosen[0].item, copy = new THREE.Matrix4(), at = new THREE.Vector3();
  for (let index = 0; index < hairs.count; index++) {
    hairs.getMatrixAt(index, copy);
    assert.ok(at.setFromMatrixPosition(copy).x > frame.middle + frame.long * 0.3, "at one pole");
  }
});

test("a plant cell: a vacuole of its share, chloroplasts of the number and size given, a wall of the thickness given, the rest pressed to the side", () => {
  const file = species("thalecress");
  const parts = file.cell.parts, sizes = parts.organelle_sizes;
  assert.ok(parts.organelles.includes("vacuole") && parts.organelles.includes("chloroplasts") && parts.wall_nm > 0);
  for (const mode of ["real", "schematic"]) {
    const { handles, chosen, frame } = built(file, mode);
    assert.deepEqual(handles.scenery.map((item) => item.id), ["scenery:vacuole", "scenery:chloroplasts"]);
    // The vacuole: the cell's own shape, smaller by the cube root of its share, in both size modes.
    const body = vacuoleOf(frame, parts);
    assert.ok(Math.abs(body.scale ** 3 - sizes.vacuole.share) < 1e-12);
    const shell = chosen.find((entry) => entry.pick === "scenery:vacuole").item;
    assert.ok(Math.abs(shell.scale.x - body.scale) < 1e-12, "drawn at that size");
    assert.equal(shell.userData.pickFilter({ point: new THREE.Vector3(0, (frame.cut + 1) * frame.u, 0) }), false, "the part of it above the cut is not there to be clicked");
    assert.equal(shell.userData.pickFilter({ point: new THREE.Vector3(0, (frame.cut - 1) * frame.u, 0) }), true);
    assert.equal(body.holds(new THREE.Vector3(0, 0, 0)), true);
    assert.equal(body.holds(new THREE.Vector3(frame.equator.widest * 0.985, 0, 0)), false, "the rim between it and the membrane is not vacuole");
    // Chloroplasts: no more than the cell holds, and only those of the part that is kept.
    const lenses = chosen.find((entry) => entry.pick === "scenery:chloroplasts").item;
    const item = handles.scenery[1];
    assert.equal(item.of, sizes.chloroplasts.count);
    assert.equal(item.drawn, lenses.count);
    assert.ok(lenses.count > 5 && lenses.count < sizes.chloroplasts.count);
    const half = boxOf(lenses.geometry).max.x;
    if (mode === "real") assert.ok(Math.abs(half - sizes.chloroplasts.across_um / 2 / frame.u) < 1e-4, "to scale, each is as wide as given");
    else assert.ok(half > sizes.chloroplasts.across_um / 2 / frame.u, "in the schematic picture they are enlarged, and the picture says so");
    assert.ok(handles.notes.some((line) => new RegExp(`^${lenses.count} of 100 chloroplasts drawn`).test(line.text)), handles.notes.map((line) => line.text).join(" | "));
    assert.ok(handles.notes.some((line) => /^The vacuole fills 84%/.test(line.text)));
    // Each lies against the inside of the membrane, below the cut.
    const copy = new THREE.Matrix4(), at = new THREE.Vector3();
    for (let index = 0; index < lenses.count; index++) {
      lenses.getMatrixAt(index, copy);
      at.setFromMatrixPosition(copy);
      const depth = frame.inside(at);
      assert.ok(depth > 0 && depth < half * 1.2, "against the membrane");
      assert.ok(at.y < frame.cut, "in the part of the cell that is kept");
    }
    // What else the cell holds is pressed to the side: the nucleus lies against the membrane, not in the middle.
    const nucleus = handles.probes.nucleus;
    assert.ok(Math.hypot(nucleus.x, nucleus.z) > frame.equator.widest * 0.3, "the nucleus is out at the side");
  }
  // The wall: to scale it stands as far outside the membrane as it is thick, at its sides and at its corners alike.
  const { added, handles } = built(file, "real");
  const [wall] = shellsOf(added);
  const [near, far] = gapsOf(wall, handles.frame);
  assert.ok(Math.abs(near * handles.frame.u * 1000 - parts.wall_nm) < 0.5 && Math.abs(far * handles.frame.u * 1000 - parts.wall_nm) < 0.5, `a shell ${parts.wall_nm} nm outside the membrane all round (${[near, far].map((gap) => gap * handles.frame.u * 1000)})`);
});

test("a layer is packed as the cell's sides ask: fours in squares, the rest in sixes, exactly as before", () => {
  const six = packing(6), four = packing(4), pitch = REF.radius * Math.sqrt(3);
  assert.equal(six.sides, 6);
  assert.equal(packing(5).sides, 6, "a cell of any other number of sides is packed in sixes");
  assert.equal(six.cells(6).length, 127);
  assert.equal(four.cells(6).length, 169);
  // Six: the lattice the sheet has always had.
  for (const cell of [{ q: 0, r: 0 }, { q: 3, r: -1 }, { q: -2, r: 3 }]) assert.deepEqual(six.centre(cell).toArray(), [REF.radius * Math.sqrt(3) * (cell.q + cell.r / 2), 0, REF.radius * 1.5 * cell.r]);
  assert.deepEqual(six.turns, [0, 1, 2, 3, 4, 5].map((step) => step * (Math.PI / 3)));
  assert.equal(six.corner(2), Math.PI / 6 + 2 * (Math.PI / 3));
  assert.equal(six.radius, REF.radius);
  assert.deepEqual(six.links, [[1, 0], [0, 1], [-1, 1]]);
  assert.equal(six.ring({ q: 2, r: -5 }), 5);
  // Four: side against side along both ways of the sheet.
  assert.deepEqual(four.centre({ q: 2, r: -1 }).toArray(), [pitch * 2, 0, -pitch]);
  assert.deepEqual(four.turns, [0, 1, 2, 3].map((step) => step * (Math.PI / 2)));
  assert.ok(Math.abs(four.radius - (pitch / 2) * Math.SQRT2) < 1e-12, "a square place's corners");
  assert.equal(four.ring({ q: 2, r: -5 }), 5);
  assert.deepEqual(four.links, [[1, 0], [0, 1]]);
  assert.ok(Math.abs(four.cornerNear((3 * Math.PI) / 2) - (7 * Math.PI) / 4) < 1e-12);
  // The plant's sheet: four-sided cells, each standing where the packing says, and joined to its four neighbours.
  const file = species("thalecress"), levels = Object.fromEntries(file.levels.map((level) => [level.id, level]));
  assert.equal(levels.cell.shape.sides, 4);
  const sheet = stand();
  const made = buildTissue(sheet.ctx, { rings: levels.tissue.shape.rings, height: 13, beyond: levels.tissue.shape.beyond, notes: [], sides: levels.cell.shape.sides });
  assert.equal(made.extent, pitch * 13);
  const body = sheet.added.find((entry) => entry.item.isInstancedMesh && entry.tag === "sheet").item;
  assert.equal(body.geometry.parameters.radialSegments, 4, "four-sided cells");
  const copy = new THREE.Matrix4(), at = new THREE.Vector3(), places = new Set(four.cells(6).map((cell) => four.centre(cell).toArray().map((n) => n.toFixed(2)).join()));
  for (let index = 0; index < body.count; index++) {
    body.getMatrixAt(index, copy);
    assert.ok(places.has(at.setFromMatrixPosition(copy).toArray().map((n) => n.toFixed(2)).join()), "each on a place of the square packing");
  }
  // And the six-sided sheet is as it was: six-sided cells on the old lattice.
  const old = stand();
  buildTissue(old.ctx, { rings: 6, height: 13, beyond: [[8, 0.3]], notes: [] });
  assert.equal(old.added.find((entry) => entry.item.isInstancedMesh && entry.tag === "sheet").item.geometry.parameters.radialSegments, 6);
});

test("what the panel says of a piece of scenery: that it is scenery, the file's facts with their sources, and the foot's door to the atlas", () => {
  const file = species("ecoli"), { handles } = built(file);
  const sources = { mears2014: { text: "Mears and others 2014", doi: "10.1/x" }, jahnke2016: { text: "Jahnke and others 2016", url: "https://example.org/j" } };
  const links = (keys) => (keys || []).map((key) => sources[key]).filter(Boolean).map((source) => ({ text: source.text, url: source.doi ? `https://doi.org/${source.doi}` : source.url }));
  const thread = describeScenery(handles.scenery[0], file, links);
  assert.equal(thread.label, "Flagella");
  assert.equal(thread.chips[0].label, "Scenery");
  assert.match(thread.plain, /scenery: nothing in the engine stands behind it/);
  const given = Object.fromEntries(thread.sections[0].items.map((item) => [item.label, item.detail]));
  assert.deepEqual(given, { "How many on a cell": "1 to 5", Length: "5 to 10 µm", Width: "20 to 40 nm", "Where on the cell": "all over", "Starts at": "the inner membrane" });
  assert.deepEqual(thread.sections[0].items.at(-1).links, [{ text: "Mears and others 2014", url: "https://doi.org/10.1/x" }], "with the sources the file names");
  assert.match(thread.sections[1].items[0].lines[0], /^3, each 7\.5 µm long and 30 nm wide/);
  assert.equal(thread.doors, undefined);
  const foot = describeScenery(handles.scenery[1], file, links);
  assert.equal(foot.label, "Flagellar motor");
  assert.match(foot.plain, /The machine at the foot of each of the cell's flagella\. Nothing in the engine stands behind it, and no closer view of it is drawn yet\./);
  assert.deepEqual(foot.doors, [{ label: "Show the proteins of the flagellar motor in the Protein atlas", lens: "proteins", show: "own", mark: "complex", value: "flagellum" }]);
  const hairs = describeScenery(handles.scenery[2], file, links);
  assert.equal(hairs.label, "Type 1 fimbriae");
  assert.match(hairs.sections[1].items[0].lines[0], /^120 of them/);
  // The door is followed by the viewer, which opens the atlas's own drawing and picks the set.
  const viewer = readFileSync(path.join(ROOT, "src/ui/viewer.js"), "utf8"), panel = readFileSync(path.join(ROOT, "src/ui/panel.js"), "utf8");
  assert.match(panel, /emit\(this, "cells-door", door\)/);
  assert.match(viewer, /addEventListener\("cells-door", \(event\) => this\.openDoor\(event\.detail\)\)/);
  assert.match(viewer, /view\.setMode\(show, \{ user: true \}\)[^]*view\.setMark\?\.\(mark\)[^]*view\.setFinding\?\.\(String\(value\)\)/);
});
