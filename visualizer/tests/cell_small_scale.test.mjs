// A small cell drawn to scale (on 16 November 2026 the user asked for the bacteria to have the Sizes
// switch too, and answered the plan's questions on 17 November 2026; out/handover/bacteria-scale.md).
// Every cell is drawn in both size modes. To scale, a part's size is worked out in nanometres from
// the cell's own size and the part is a shape where it covers two pixels at the cell's stop, dots
// where it covers less (src/lenses/cell_layout.js): a bacterium's membranes, membrane proteins and
// ribosomes are shapes, at the sizes their sources give or the picture's stated choice; its crowd of
// proteins and its chromosome are drawn only in a slab 10 nm deep under the cut. A cell 20 µm
// across draws as it did (tests/cell_build.test.mjs holds that).
//
//   node --test tests/cell_small_scale.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildCell, buildMolecules, CUT } from "../src/lenses/cell_parts.js";
import { stopOf, TO_SCALE, CHANNEL, PUMP } from "../src/lenses/cell_layout.js";
import { cellFrame } from "../src/lenses/shapes.js";
import { CellLens } from "../src/lenses/cell.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
const capabilities = scene.entities.filter((entity) => entity.kind === "capability");
const BACTERIA = ["ecoli", "syn3a", "mpneumoniae"];

/** The lens as far as its plan needs it, for one species of the scene (cell.js: plan and draws). */
function planned(species) {
  const lens = {
    species, sizeMode: "schematic",
    model: { ofKind: (kind) => (kind === "capability" ? capabilities : []), get: (id) => scene.entities.find((item) => item.id === id) || null, raw: scene },
    capabilityByPart: new Map(capabilities.map((entity) => [entity.part, entity])),
    leftOut: new Set((scene.left_out || []).map((item) => item.part).filter(Boolean)),
  };
  CellLens.prototype.plan.call(lens);
  lens.draws = (part) => CellLens.prototype.draws.call(lens, part);
  return lens;
}

/** A stand-in for the lens's context: what each part, and the scenery, was given. */
function stand(zone, kept) {
  const keep = (object, tag) => object.traverse?.((item) => (item.isMesh || item.isPoints || item.isLine) && kept.push({ zone, tag, item }));
  const part = (name, anchor) => ({ name, anchor: anchor || new THREE.Vector3(), group: new THREE.Group(), material: (options = {}) => Object.assign(new THREE.MeshStandardMaterial(), { userData: { options } }), points: (options = {}) => Object.assign(new THREE.PointsMaterial(), { userData: { options } }), lineMaterial: () => new THREE.LineBasicMaterial(), proxyMaterial: () => new THREE.MeshBasicMaterial(), add: (...objects) => objects.forEach((object) => keep(object, name)) });
  return { part, scale: part, known: (name) => capabilities.some((entity) => entity.part === name), neutral: (options = {}) => Object.assign(new THREE.MeshStandardMaterial(), { userData: { options, neutral: true } }), neutralPoints: () => new THREE.PointsMaterial(), neutralLine: () => new THREE.LineBasicMaterial(), illustrate: (object) => keep(object, "scenery"), scenery: (object, id) => keep(object, id), sprite: () => {} };
}

/** One species' cell and close-up in one size mode, built as the lens builds them. */
function built(id, mode, species = scene.species.find((item) => item.id === id)) {
  const lens = planned(species);
  const kept = [];
  const cell = { shape: lens.levels.cell.shape, parts: species.cell.parts, has: lens.draws, neighbours: Boolean(lens.levels.tissue), notes: [] };
  const handles = buildCell(stand("cell", kept), stand("studs", kept), mode, cell);
  handles.molecule = buildMolecules(stand("molecules", kept), mode, handles.frame, lens.draws);
  return { species, handles, kept, lens, nm: 0.001 / handles.frame.u };
}
const of = (kept, tag, zone = null) => kept.filter((entry) => entry.tag === tag && (!zone || entry.zone === zone)).map((entry) => entry.item);
const triangles = (item) => ((item.geometry.index ? item.geometry.index.count : item.geometry.attributes.position.count) / 3) * (item.isInstancedMesh ? item.count : 1);
/** What a frame of the cell's stop draws: the cell and its studs, not the close-up. */
function cost(kept) {
  const drawn = kept.filter((entry) => entry.zone !== "molecules").map((entry) => entry.item);
  return {
    draws: drawn.length,
    triangles: Math.round(drawn.filter((item) => item.isMesh).reduce((sum, item) => sum + triangles(item), 0)),
    points: drawn.filter((item) => item.isPoints).reduce((sum, item) => sum + item.geometry.attributes.position.count, 0),
    segments: drawn.filter((item) => item.isLine).reduce((sum, item) => sum + item.geometry.attributes.position.count / (item.isLineSegments ? 2 : 1), 0),
  };
}

test("the rule is the same for every cell: a part is a shape where it covers two pixels at the cell's stop, and only a bacterium's molecules do", () => {
  for (const species of scene.species) {
    const lens = planned(species);
    assert.deepEqual(lens.modes, ["schematic", "real"], `${species.id}: both size modes`);
    const frame = cellFrame(lens.levels.cell.shape, lens.levels.tissue ? 0.04 : 0);
    const { pixel } = stopOf(frame);
    const small = BACTERIA.includes(species.id);
    assert.equal(TO_SCALE.ribosome / pixel >= 2, small, `${species.id}: ${pixel.toFixed(2)} nm a pixel at its stop`);
  }
  // The stop the rule reads is the stop the lens frames (cell.js, makeStops).
  const { handles } = built("ecoli", "real");
  assert.deepEqual(stopOf(handles.frame).size, [Math.min(96, Math.max(42, handles.frame.long * 1.3)), 31]);
  assert.ok(Math.abs(stopOf(handles.frame).pixel - 2.41) < 0.05, "E. coli's stop holds about 2.4 nm a pixel on a wide screen");
});

test("E. coli to scale: its envelope at the widths its file gives, from one open paper's numbers", () => {
  const { species, handles, kept, nm } = built("ecoli", "real");
  const envelope = species.cell.parts.envelope;
  assert.ok(handles.scale.fine);
  // The cell membrane's band at the cut is as thick as the file says.
  const flat = (item) => new THREE.Box3().setFromBufferAttribute(item.geometry.attributes.position).getSize(new THREE.Vector3()).y < 1e-9;
  const bands = of(kept, "membrane", "cell").filter((item) => item.isMesh && !item.isInstancedMesh && flat(item));
  assert.equal(bands.length, 2, "one band at the cut, in two pieces: the close-up's stretch and the rest");
  for (const piece of bands) {
    const band = piece.geometry.attributes.position, inner = new THREE.Vector3().fromBufferAttribute(band, 0), outer = new THREE.Vector3().fromBufferAttribute(band, band.count / 2);
    assert.ok(Math.abs(inner.distanceTo(outer) / nm - envelope.membrane_nm) < 0.05, `the membrane ${inner.distanceTo(outer) / nm} nm thick`);
  }
  // The wall and the outer membrane, each at its place: from the cell membrane's middle to each shell's middle.
  const outerAt = envelope.membrane_nm / 2 + envelope.between_nm + envelope.outer_nm / 2;
  const wallAt = envelope.membrane_nm / 2 + envelope.between_nm - envelope.wall_to_outer_nm - envelope.wall_nm / 2;
  assert.ok(Math.abs(handles.shells.outerGap / nm - outerAt) < 1e-6 && Math.abs(handles.shells.wallGap / nm - wallAt) < 1e-6, JSON.stringify(handles.shells));
  assert.ok(Math.abs(outerAt - 27.345) < 1e-9 && Math.abs(wallAt - 15.395) < 1e-9, "27.345 nm and 15.395 nm out");
  // Its threads start on their shells: the fimbriae on the outer membrane, as in the schematic picture.
  const fimbriae = of(kept, "scenery:appendage:1")[0], copy = new THREE.Matrix4(), start = new THREE.Vector3();
  fimbriae.getMatrixAt(0, copy);
  start.setFromMatrixPosition(copy);
  assert.ok(Math.abs(-handles.frame.inside(start) - handles.shells.outerGap) < 0.02, "a fimbria starts on the outer membrane");
  // No crowd of proteins: its sources disagree a hundredfold, and the card says so.
  assert.equal(handles.crowd, null);
  // The close-up shows the whole envelope, and says so.
  assert.match(handles.molecule.note, /inner membrane 5\.84 nm thick, the wall 6\.35 nm and the outer membrane 6\.87 nm/);
  assert.ok(handles.molecule.pored, "E. coli has channels: the close-up shows one");
  assert.ok(handles.molecule.view[1] / nm > 2 * outerAt, "the close-up is tall enough to hold the outer membrane");
});

test("each bacterium to scale: shapes at their sizes, the counts its file gives, dots for what is under two pixels", () => {
  for (const id of BACTERIA) {
    const { species, handles, kept, nm } = built(id, "real");
    const parts = species.cell.parts;
    assert.ok(handles.scale.fine, id);
    // Ribosomes: about 20 nm across, as many as before (those kept below the cut), with fewer faces, wholly below the cut.
    const ribosomes = of(kept, "ribosomes").filter((item) => item.isInstancedMesh);
    const large = ribosomes[0];
    const across = large.geometry.parameters.radius * 2 / nm;
    assert.ok(across > 18 && across < 22, `${id}: a ribosome ${across.toFixed(1)} nm across`);
    assert.equal(large.count, Math.round(parts.ribosomes * 0.6), id);
    assert.ok(triangles(ribosomes[0]) / large.count + triangles(ribosomes[1]) / ribosomes[1].count <= 130, `${id}: a ribosome of few faces`);
    const copy = new THREE.Matrix4(), at = new THREE.Vector3();
    for (let index = 0; index < large.count; index++) {
      large.getMatrixAt(index, copy);
      assert.ok(at.setFromMatrixPosition(copy).y < CUT, `${id}: each ribosome stands below the cut`);
    }
    // Pumps at their size: the close-up's three lobes, the largest 4.2 nm in radius.
    const lobes = of(kept, "pumps", "cell").find((item) => item.isInstancedMesh);
    lobes.getMatrixAt(0, copy);
    const scale = new THREE.Vector3(), turn = new THREE.Quaternion();
    copy.decompose(at, turn, scale);
    assert.ok(Math.abs(scale.x / nm - 4.2) < 1e-6, `${id}: a pump's lobe 4.2 nm in radius`);
    // Channels only where the species has them.
    assert.equal(of(kept, "channels", "cell").length > 0, id === "ecoli", id);
    assert.equal(handles.molecule.pored, id === "ecoli", id);
    if (id !== "ecoli") assert.match(handles.molecule.note, /the pump 8\.4 nm across/);
    // Small molecules and ions are dots: under two pixels at the stop.
    for (const tag of ["atp", "extracellular", "cytoplasm"]) assert.ok(of(kept, tag).some((item) => item.isPoints), `${id}: ${tag} as dots`);
    // The chromosome: a fine line, only in the slab under the cut, and its words say how much of it.
    const line = of(kept, "chromatin").find((item) => item.isLineSegments);
    const position = line.geometry.attributes.position, point = new THREE.Vector3();
    for (let index = 0; index < position.count; index++) {
      point.fromBufferAttribute(position, index);
      assert.ok(point.y <= CUT + 1e-9 && point.y >= CUT - TO_SCALE.slab * nm - 1e-9, `${id}: the chromosome in the slab`);
    }
    const [[label, words]] = handles.structures.chromatin;
    assert.equal(label, "Drawn");
    assert.match(words, /^A fine line, in a slab 10 nm deep under the cut/);
    assert.ok(words.includes(`${parts.chromosome_kbp.toLocaleString("en-US")} kbp`) && /the picture's choice\.$/.test(words), words);
  }
});

test("the crowd of proteins: in the slab under the cut, at the density the file's numbers give, as scenery that cannot be chosen", () => {
  for (const id of ["syn3a", "mpneumoniae"]) {
    const { species, handles, kept, nm } = built(id, "real");
    const { count, membrane = 0 } = species.cell.parts.proteins;
    const crowd = handles.crowd;
    assert.equal(crowd.count, count);
    assert.equal(crowd.loose, Math.round((count - membrane) * crowd.share), `${id}: the slab's share of the cell's volume`);
    assert.equal(crowd.held, Math.round(membrane * crowd.ring), `${id}: the slab's ring of membrane`);
    assert.ok(crowd.share > 0.02 && crowd.share < 0.1, `${id}: a thin slab holds a small share (${crowd.share})`);
    // Drawn as neutral marks through the scenery, never as a part of the map.
    const marks = of(kept, "scenery").find((item) => item.isInstancedMesh && item.geometry.type === "IcosahedronGeometry");
    assert.equal(marks.count, crowd.loose + crowd.held);
    assert.ok(marks.material.userData.neutral, `${id}: neutral scenery`);
    assert.ok(Math.abs(marks.geometry.parameters.radius / nm - TO_SCALE.protein / 2) < 1e-9, `${id}: each about 5 nm across`);
    const copy = new THREE.Matrix4(), at = new THREE.Vector3();
    for (let index = 0; index < marks.count; index++) {
      marks.getMatrixAt(index, copy);
      at.setFromMatrixPosition(copy);
      assert.ok(at.y < CUT && at.y > CUT - TO_SCALE.slab * nm, `${id}: in the slab`);
    }
  }
  // Syn3A's membrane proteins are counted from its shelves; a slab of its cut face holds about 190 of 7,685.
  assert.ok(Math.abs(built("syn3a", "real").handles.crowd.held - 189) < 5);
});

test("the schematic picture of a bacterium stays as it was, but for its ribosomes' fewer faces", () => {
  for (const id of BACTERIA) {
    const { handles, kept } = built(id, "schematic");
    assert.ok(!handles.scale.fine, `${id}: the schematic picture is not drawn to scale`);
    assert.equal(handles.crowd, null);
    assert.ok(of(kept, "chromatin").some((item) => item.geometry.type === "TubeGeometry"), `${id}: the chromosome a thread, as before`);
    const ribosomes = of(kept, "ribosomes").filter((item) => item.isInstancedMesh);
    assert.ok(triangles(ribosomes[0]) / ribosomes[0].count <= 80, `${id}: the large subunit of few faces`);
  }
});

test("what a frame costs at the cell's stop: draw calls and triangles under a ceiling, in each mode", () => {
  // The ceilings stand a little above what each draws on 17 November 2026; the human cell's own (about 125 draws, 0.39 million triangles) for scale.
  const CEILINGS = {
    "ecoli/schematic": { draws: 80, triangles: 850000, points: 0, segments: 1000 },
    "ecoli/real": { draws: 100, triangles: 700000, points: 12000, segments: 12000 },
    "syn3a/schematic": { draws: 70, triangles: 200000, points: 0, segments: 1000 },
    "syn3a/real": { draws: 90, triangles: 200000, points: 12000, segments: 6000 },
    "mpneumoniae/schematic": { draws: 70, triangles: 500000, points: 0, segments: 1000 },
    "mpneumoniae/real": { draws: 90, triangles: 300000, points: 12000, segments: 12000 },
  };
  for (const [key, ceiling] of Object.entries(CEILINGS)) {
    const [id, mode] = key.split("/");
    const spent = cost(built(id, mode).kept);
    for (const [what, most] of Object.entries(ceiling)) assert.ok(spent[what] <= most, `${key}: ${what} ${spent[what]}, above ${most}`);
  }
});

test("the card says in a short line what each mode draws of a bacterium, its panel says it in full, and a large cell's card keeps its words", () => {
  const lensOf = (id, mode) => {
    const schematic = built(id, "schematic").handles, real = built(id, "real").handles;
    return { ...planned(scene.species.find((item) => item.id === id)), cells: { schematic, real }, sizeMode: mode };
  };
  const note = (id, mode) => CellLens.prototype.sizeNote.call({ ...lensOf(id, mode), sizeWords: CellLens.prototype.sizeWords });
  const said = (id) => Object.fromEntries(CellLens.prototype.sizeWords.call(lensOf(id, "real")).drawn);
  // The card: one short line, at most about a hundred letters with its link, so that it shows whole (tools/check_species.mjs holds what shows).
  for (const id of BACTERIA) for (const mode of ["schematic", "real"]) {
    const { text, more, open } = note(id, mode);
    assert.ok(text.length <= 70 && open === "scale.cell" && more === "What each mode draws", `${id} ${mode}: ${text}`);
  }
  assert.equal(note("ecoli", "schematic").text, "Enlarged to be seen: the membrane about 5 times as thick as it is.");
  assert.equal(note("syn3a", "schematic").text, "Enlarged to be seen: the membrane about twice as thick as it is.");
  assert.equal(note("mpneumoniae", "schematic").text, "Enlarged to be seen: in a cell this thin, only the small molecules.");
  assert.equal(note("ecoli", "real").text, "To scale, a cell about 1 µm across; small molecules are dots.");
  assert.equal(note("syn3a", "real").text, "To scale, a cell about 400 nm across; small molecules are dots.");
  // The panel: nothing of the longer words is dropped.
  assert.match(said("ecoli").Schematic, /membrane is drawn about 5 times as thick as it is and its proteins about 6 times their size/);
  assert.match(said("syn3a").Schematic, /membrane is drawn about twice as thick as it is and its proteins about twice their size/);
  assert.match(said("mpneumoniae").Schematic, /near their own size.*The two pictures differ mainly in the crowd of proteins and the small molecules\./);
  assert.match(said("ecoli")["To scale"], /two membranes and its wall at the widths one paper measured, its channels 7\.4 nm and its pumps 8\.4 nm across, its ribosomes a textbook 20 nm across, its flagella and type 1 fimbriae as its file gives them\./);
  assert.match(said("ecoli")["In a slab under the cut, to scale"], /No crowd of proteins is drawn, since the sources read for its file give no one count\./);
  assert.match(said("syn3a")["To scale"], /its membrane a textbook 4\.5 nm thick, its pumps 8\.4 nm across/);
  assert.match(said("syn3a")["In a slab under the cut, to scale"], /: of its 77,028 protein molecules, 2,709 stand there\./);
  assert.match(said("mpneumoniae")["In a slab under the cut, to scale"], /: of its 120,700 protein molecules, 7,649 stand there\./);
  const human = { cells: { schematic: built("human", "schematic").handles, real: built("human", "real").handles }, sizeMode: "real" };
  assert.equal(CellLens.prototype.sizeNote.call({ ...human, sizeWords: CellLens.prototype.sizeWords }), null);
});

test("a channel's and a pump's words follow their shapes: one size each, read by the close-up, the cut edge, the skin and the words", () => {
  assert.deepEqual([CHANNEL.across, PUMP.across, TO_SCALE.channel, TO_SCALE.pump], [7.4, 8.4, 7.4, 8.4]);
  for (const id of ["ecoli", "syn3a", "human"]) {
    const { handles, kept, nm } = built(id, "real");
    const close = of(kept, "channels", "molecules").find((item) => item.isInstancedMesh);
    if (close) {
      const { radius, length } = close.geometry.parameters;
      assert.ok(Math.abs(radius / nm - CHANNEL.wall) < 1e-9 && Math.abs((length + 2 * radius) / nm - CHANNEL.length) < 1e-9, `${id}: the close-up's channel walls`);
    }
    const lobes = [...of(kept, "pumps", "molecules")].filter((item) => item.isMesh && !item.isInstancedMesh).map((item) => item.geometry.parameters.radius / nm);
    assert.ok(Math.abs(Math.max(...lobes) * 2 - PUMP.across) < 1e-9, `${id}: the close-up's pump, ${PUMP.across} nm across`);
    if (handles.scale.fine) {
      assert.match(handles.molecule.note, id === "ecoli" ? /inner membrane 5\.84 nm thick/ : new RegExp(`the pump ${PUMP.across} nm across`));
      const ring = of(kept, "channels", "studs").find((item) => item.geometry.type === "TorusGeometry");
      if (ring) assert.ok(Math.abs((ring.geometry.parameters.radius + ring.geometry.parameters.tube) * 2 / nm - CHANNEL.across) < 1e-9, `${id}: a ring on the skin as wide as the channel`);
      const dome = of(kept, "pumps", "studs").find((item) => item.isInstancedMesh);
      assert.ok(Math.abs((dome.geometry.parameters.radius * 2) / nm - PUMP.across) < 1e-9, `${id}: a dome on the skin as wide as the pump`);
    }
  }
});

test("to scale, the close-up's stretch of the cut gives way to the close-up as the camera comes to it, so the membrane is drawn once there; the rest of the cut stays", () => {
  const flat = (item) => item.isMesh && !item.isInstancedMesh && (item.geometry.computeBoundingBox(), item.geometry.boundingBox.max.y - item.geometry.boundingBox.min.y < 1e-9);
  const giving = (items) => items.filter((item) => item.material.userData.dust === true).length;
  for (const id of BACTERIA) {
    const { kept, nm, handles } = built(id, "real");
    const bands = of(kept, "membrane", "cell").filter(flat), lines = of(kept, "membrane", "cell").filter((item) => item.isLine);
    assert.ok(bands.length === 2 && giving(bands) === 1, `${id}: the band in two pieces, one of which gives way`);
    assert.ok(lines.length === 2 && giving(lines) === 1, `${id}: and its line`);
    // The piece that gives way lies along the close-up's stretch, about 150 nm of the cut, round the close-up's middle.
    const away = bands.find((item) => item.material.userData.dust === true);
    away.geometry.computeBoundingSphere();
    const middle = handles.molecule.centre;
    assert.ok(away.geometry.boundingSphere.center.distanceTo(middle) / nm < 20 && away.geometry.boundingSphere.radius / nm < 80, `${id}: about the close-up`);
  }
  const shells = of(built("ecoli", "real").kept, "scenery", "cell").filter(flat);
  assert.ok(shells.length === 4 && giving(shells) === 2, "E. coli's wall and outer membrane at the cut: the close-up's stretch of each gives way");
  // A large cell's cut is as it was.
  assert.ok(of(built("human", "real").kept, "membrane", "cell").every((item) => item.material.userData.dust !== true));
});

test("a species' file may keep a capability out of its picture for now: the bacteria's molecular machines are not drawn, and taking the flag out draws them again", () => {
  for (const id of BACTERIA) {
    const species = scene.species.find((item) => item.id === id);
    const entry = species.cell.capabilities["cap.machines"];
    assert.ok(entry.place === "present" && entry.note && entry.left_out.since === "2026-11-17" && entry.left_out.reason && /^On 17 November 2026 the user asked for /.test(entry.left_out.why), `${id}: the flag, with its place and note kept`);
    for (const mode of ["schematic", "real"]) {
      const { kept, lens } = built(id, mode);
      assert.equal(of(kept, "machine").length, 0, `${id} ${mode}: no barrel and no dots`);
      assert.ok(!lens.draws("machine") && lens.leftHere.has("cap.machines") && !lens.absent.has("cap.machines"), `${id} ${mode}: left out, not absent`);
      assert.ok(of(kept, "ribosomes").length > 0, `${id} ${mode}: its ribosomes are still drawn`);
    }
    // Without the flag the barrel is drawn again, as it was.
    const bare = structuredClone(species);
    for (const holder of [bare.cell, ...(bare.cell_types || [])]) delete holder.capabilities?.["cap.machines"]?.left_out; // the species' own cell type carries the same places
    for (const mode of ["schematic", "real"]) {
      const { kept, lens } = built(id, mode, bare);
      assert.ok(lens.draws("machine") && !lens.leftHere.has("cap.machines"), `${id} ${mode}: drawn again`);
      assert.ok(of(kept, "machine").some((item) => item.isInstancedMesh), `${id} ${mode}: the barrel is back`);
    }
  }
  // A large cell keeps its machines (tests/cell_build.test.mjs holds its numbers).
  for (const id of ["human", "planarian"]) assert.ok(of(built(id, "schematic").kept, "machine").length > 0 && !built(id, "real").lens.leftHere.size, id);
});

test("to scale, a small cell's close-up and dots give way at distances of its own stop; a large cell's are as they were", () => {
  const ranges = (u, cellStop) => {
    const stub = { u, levels: { cell: {} }, modes: ["schematic", "real"], stops: { schematic: [{ id: "molecule", size: [1, 1] }, { id: "cell", size: [cellStop * 2 * Math.tan((34 * Math.PI) / 360), cellStop * 2 * Math.tan((34 * Math.PI) / 360)] }] }, zones: [{ name: "molecules", mode: "real" }, { name: "studs", mode: "real" }, { name: "cell", mode: "real" }], cells: { schematic: { frame: { long: 1 }, reach: 0 } } };
    CellLens.prototype.setRanges.call(stub);
    return { dust: stub.dustRange, molecules: stub.zones[0].range.out };
  };
  assert.deepEqual(ranges(1, 50.7), { dust: [0.5, 1.6], molecules: [0.45, 1.2] }, "a cell 20 µm across: as before");
  const syn3a = ranges(0.0218, 1.1);
  assert.ok(syn3a.dust[1] < 1.1 * 0.5 && syn3a.molecules[1] < 1.1 * 0.5, `Syn3A's dots stay whole at its stop, 1.1 µm out: ${JSON.stringify(syn3a)}`);
  assert.ok(syn3a.dust[0] > 0.1 && syn3a.molecules[0] > 0.1, "and give way to the close-up, about 0.1 µm out");
  // A bacterium's channels and pumps on the skin are shapes to scale: they do not fade as the camera comes close.
  const stub = { u: 0.0218, levels: { cell: {} }, modes: ["schematic", "real"], stops: { schematic: [{ id: "molecule", size: [1, 1] }, { id: "cell", size: [0.67, 0.67] }] }, zones: [{ name: "studs", mode: "real" }], cells: { schematic: { frame: { long: 1 }, reach: 0 }, real: { scale: { fine: true } } } };
  CellLens.prototype.setRanges.call(stub);
  assert.equal(stub.zones[0].range.in, undefined);
});
