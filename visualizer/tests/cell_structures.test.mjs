// The cell's own structures (src/lenses/cell_structures.js): the nucleus, the ER, the Golgi
// and the ribosomes as parts of their own (the user, 16 November 2026; docs/CELL_STRUCTURES.md).
// What a cell holds comes from its species' file; a door into the Protein atlas is offered only
// where the species' own proteins can show the set; and each part is drawn whole and says what
// the picture chose.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildCell } from "../src/lenses/cell_parts.js";
import { structureAbsence, structureDoors, organelles } from "../src/lenses/cell_structures.js";
import { makeLayout } from "../src/lenses/cell_layout.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const species = (id) => json(`data/species/${id}.json`);
const CAPS = [
  { id: "cap.nucleus", part: "nucleus" },
  { id: "cap.golgi", part: "golgi" },
  { id: "cap.trafficking", part: "vesicles" },
  { id: "cap.ribosomes", part: "ribosomes" },
  { id: "cap.calcium", part: "er" },
  { id: "cap.circuits", part: "chromatin" },
];

test("a capability drawn at a structure the cell does not hold has no place in it, with the reason read from its file", () => {
  const syn3a = structureAbsence(CAPS, species("syn3a"));
  assert.equal(syn3a.get("cap.nucleus"), "It has no nucleus: its chromosome lies free in the cytoplasm.");
  assert.equal(syn3a.get("cap.golgi"), "It has no Golgi apparatus.");
  assert.ok(!syn3a.has("cap.trafficking") && !syn3a.has("cap.calcium"), "what the file itself places is left to the file");
  assert.ok(!syn3a.has("cap.ribosomes") && !syn3a.has("cap.circuits"), "every cell has ribosomes, and DNA");
  for (const id of ["human", "planarian", "fruitfly", "thalecress"]) assert.deepEqual([...structureAbsence(CAPS, species(id)).keys()], [], `${id} holds them all`);
  assert.deepEqual(organelles({ nucleus: true }), ["er", "golgi", "mitochondria"], "a cell with a nucleus and no list holds an animal cell's");
  assert.deepEqual(organelles({ nucleus: false }), []);
});

test("one table of structures, data/parts/structures.json, is the one the page and the species reader both read", () => {
  const table = json("data/parts/structures.json");
  // The species reader's view of it, asked of tools/lib/species.py for a cell with each structure and with none.
  const cells = [{ nucleus: true }, { nucleus: false, organelles: [] }, { nucleus: true, organelles: ["mitochondria"] }, { organelles: ["er", "golgi"] }, {}];
  const run = spawnSync("python3", ["-c", "import json, sys; sys.path.insert(0, sys.argv[1]); from lib import species as s; cells = json.loads(sys.argv[2]); print(json.dumps({'table': s.STRUCTURES, 'organelles': s.ANIMAL_ORGANELLES, 'holds': [[s.holds_structure(c, p) for p in sorted(s.STRUCTURES['structures'])] for c in cells]}))", path.join(ROOT, "tools"), JSON.stringify(cells)], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const python = JSON.parse(run.stdout);
  assert.deepEqual(python.table, table, "the reader holds the table as the file gives it");
  assert.deepEqual(python.organelles, table.nucleated_organelles);
  assert.deepEqual(organelles({ nucleus: true }), table.nucleated_organelles, "the page's organelles of a cell with a nucleus are the table's");
  // For each cell and structure, the page leaves a capability drawn there out exactly where the reader says the cell does not hold it.
  const parts = Object.keys(table.structures).sort();
  cells.forEach((cell, index) => {
    const absent = structureAbsence(parts.map((part) => ({ id: `cap.${part}`, part })), { cell: { parts: cell, capabilities: {} } });
    parts.forEach((part, at) => {
      assert.equal(!absent.has(`cap.${part}`), python.holds[index][at], `${JSON.stringify(cell)} and ${part}`);
      if (absent.has(`cap.${part}`)) assert.ok([table.structures[part].why, table.structures[part].why_free_chromosome].includes(absent.get(`cap.${part}`)), part);
    });
  });
});

test("a door into the Protein atlas only where the species' own proteins can show the set", () => {
  const scene = json("data/architecture/architecture.scene.json");
  const summary = (id) => (scene.proteins?.shelves || []).find((item) => item.id === id) || null;
  const human = { id: "human" };
  const [nucleus] = structureDoors({ part: "nucleus" }, human, summary("human"));
  assert.deepEqual([nucleus.lens, nucleus.show, nucleus.shelf], ["proteins", "own", "nucleus"]);
  assert.match(nucleus.label, /^Show the [\d,]+ proteins of the nuclear envelope shelf in the Protein atlas$/);
  assert.equal(structureDoors({ part: "er" }, human, summary("human"))[0].shelf, "er");
  assert.equal(structureDoors({ part: "mitochondria" }, human, summary("human"))[0].shelf, "mito");
  assert.deepEqual(structureDoors({ part: "golgi" }, human, summary("human")), [], "no shelf of its own: no door");
  assert.deepEqual(structureDoors({ part: "nucleus" }, { id: "planarian" }, summary("planarian")), [], "one shelf for all membranes: no door");
  assert.deepEqual(structureDoors({ part: "nucleus" }, human, null), [], "no proteins of its own: no door");
  // A set a species' marks name: read from the summary's sets, never from a species' id.
  const sets = { id: "x", shelves: [{ id: "cell", label: "Cell membrane", proteins: 3 }], sets: { complex: ["flagellum", "ribosome"] } };
  assert.deepEqual(structureDoors({ part: "ribosomes" }, { id: "x" }, sets).map(({ mark, value, shelf }) => [mark, value, shelf]), [["complex", "ribosome", undefined]]);
  assert.deepEqual(structureDoors({ part: "ribosomes" }, { id: "x" }, { ...sets, sets: { complex: ["flagellum"] } }), []);
});

/** A stand-in for the lens: what each part was given, and whether the scene knows the part. */
function stand(known) {
  const parts = new Map();
  const part = (name, anchor) => {
    const made = { name, anchor: anchor || null, materials: [], objects: [], group: new THREE.Group() };
    const keep = (options) => (material) => (made.materials.push({ options, material }), material);
    Object.assign(made, {
      material: (options = {}) => keep(options)(new THREE.MeshStandardMaterial()),
      points: (options = {}) => keep(options)(new THREE.PointsMaterial()),
      lineMaterial: (options = {}) => keep(options)(new THREE.LineBasicMaterial()),
      proxyMaterial: () => new THREE.MeshBasicMaterial(),
      add: (...objects) => made.objects.push(...objects),
    });
    if (!parts.has(name)) parts.set(name, []);
    parts.get(name).push(made);
    return made;
  };
  const neutral = () => new THREE.MeshStandardMaterial();
  const chosen = new Map(); // scenery that can be chosen, by its id
  return { parts, chosen, ctx: { part, scale: part, known: (name) => known.includes(name), neutral, neutralPoints: () => new THREE.PointsMaterial(), neutralLine: () => new THREE.LineBasicMaterial(), illustrate: () => {}, scenery: (object, id) => chosen.set(id, object), sprite: () => {} } };
}
const built = (id, mode, known = ["nucleus", "chromatin", "golgi", "vesicles", "ribosomes", "er"]) => {
  const file = species(id), levels = Object.fromEntries(file.levels.map((level) => [level.id, level]));
  const a = stand(known);
  const cell = { shape: levels.cell.shape, parts: file.cell.parts || {}, has: () => true, neighbours: Boolean(levels.tissue), notes: [] };
  const handles = buildCell(a.ctx, stand(known).ctx, mode, cell);
  return { handles, parts: a.parts, chosen: a.chosen, layout: makeLayout(mode, cell) };
};
/** Every vertex of a part's objects (proxies too), in the cell's frame, with each copy of an instanced shape placed. */
function vertices(objects) {
  const out = [], v = new THREE.Vector3(), m = new THREE.Matrix4();
  for (const root of objects) {
    root.updateMatrixWorld(true);
    root.traverse((object) => {
      if (!object.geometry) return;
      const position = object.geometry.attributes.position;
      for (let copy = 0; copy < (object.isInstancedMesh ? object.count : 1); copy++) {
        if (object.isInstancedMesh) object.getMatrixAt(copy, m);
        else m.identity();
        for (let at = 0; at < position.count; at++) out.push(v.fromBufferAttribute(position, at).clone().applyMatrix4(m).applyMatrix4(object.matrixWorld));
      }
    });
  }
  return out;
}
/** How many objects a part draws, and how many triangles: what a frame pays for it. */
function cost(objects) {
  let draws = 0, triangles = 0;
  for (const root of objects) {
    root.traverse((object) => {
      if (!object.geometry) return;
      draws += 1;
      const count = object.geometry.index ? object.geometry.index.count : object.geometry.attributes.position.count;
      if (object.isMesh) triangles += Math.round(count / 3) * (object.isInstancedMesh ? object.count : 1);
    });
  }
  return { draws, triangles };
}
const angleAbout = (centre, point) => Math.atan2(point.z - centre.z, point.x - centre.x);
const apart = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));

test("each structure is drawn whole, in its own colour, and says what the picture chose", () => {
  for (const mode of ["schematic", "real"]) {
    const { handles, parts } = built("human", mode);
    for (const name of ["nucleus", "chromatin", "er", "golgi", "vesicles", "ribosomes"]) assert.ok(parts.has(name), `${mode}: ${name} is a part`);
    const hues = (name) => new Set(parts.get(name).flatMap((part) => part.materials.map((item) => item.options.hue)).filter(Boolean));
    assert.deepEqual([...hues("golgi")], ["bioGolgi"]);
    assert.deepEqual([...hues("ribosomes")], ["bioRibosome"]);
    assert.ok(hues("nucleus").has("bioNucleus") && hues("er").has("bioEr"));
    for (const [name] of parts) for (const part of parts.get(name)) for (const { options } of part.materials) assert.ok(!options.line && !options.wire, `${mode}: ${name} asks for no sketch of its own`);
    for (const name of ["nucleus", "golgi", "vesicles", "ribosomes"]) assert.ok(handles.structures[name]?.[0]?.[1].includes("the picture's choice"), `${mode}: ${name} says what the picture chose`);
    assert.ok(handles.probes.chromatin, "a place where a click reaches the chromatin");
  }
});

test("a cell without a nucleus: its chromosome carries the circuits, and its ribosomes are the file's count", () => {
  const file = species("syn3a");
  const { handles, parts } = built("syn3a", "schematic");
  assert.ok(!parts.has("nucleus") && !parts.has("golgi") && parts.has("chromatin") && parts.has("ribosomes"));
  assert.match(handles.structures.ribosomes[0][1], new RegExp(`of the ${file.cell.parts.ribosomes} the species' file gives`));
  const { parts: old } = built("syn3a", "schematic", []);
  assert.ok(old.has("nucleus") && !old.has("chromatin") && !old.has("ribosomes"), "a scene made before: the chromosome under the nucleus's part, the ribosomes scenery");
});

test("a small cell's ribosomes are drawn about 20 nm across, as its panel says, however thin the cell", () => {
  for (const id of ["ecoli", "syn3a", "mpneumoniae"]) {
    const { handles, parts } = built(id, "schematic");
    const meshes = parts.get("ribosomes")[0].objects.filter((object) => object.isInstancedMesh);
    const large = meshes[0].geometry.parameters.radius * 2 * handles.frame.u * 1000; // the large subunit, in nanometres
    assert.ok(large > 18 && large < 22, `${id}: the large subunit is ${large.toFixed(1)} nm across`);
    assert.match(handles.structures.ribosomes[0][1], /Each is drawn about 20 nm across/);
  }
});

test("a free chromosome's panel says what was drawn: the thread's width and length against what its length in base pairs makes", () => {
  for (const id of ["ecoli", "syn3a", "mpneumoniae"]) {
    const file = species(id), kbp = file.cell.parts.chromosome_kbp;
    const { handles, parts } = built(id, "schematic");
    const tube = parts.get("chromatin")[0].objects.find((object) => object.geometry?.type === "TubeGeometry").geometry;
    const drawn = tube.parameters.path.getLength() * handles.frame.u, whole = kbp * 0.34;
    const [[label, text]] = handles.structures.chromatin;
    assert.equal(label, "Drawn");
    assert.ok(text.startsWith(`One closed thread ${Number((tube.parameters.radius * 2 * handles.frame.u * 1000).toPrecision(2))} nm thick and ${Number(drawn.toPrecision(2)).toLocaleString("en-US")} µm long`), text);
    assert.ok(text.includes(`Its ${kbp.toLocaleString("en-US")} kbp would make about ${Math.round(whole).toLocaleString("en-US")} µm of DNA`), text);
    assert.ok(text.includes(`about ${Math.max(1, Math.round((drawn / whole) * 100))}% of that length`) && /the picture's choice\.$/.test(text), text);
  }
  const { handles } = built("human", "schematic");
  assert.equal(handles.structures.chromatin, undefined, "a cell with a nucleus: its chromatin is the nucleus's, and says nothing of a free thread");
});

// ------------------------------------------------------------------ where the Golgi stands (the user, 17 November 2026: option B)

test("an animal cell's Golgi stands beside the nucleus, round a centrosome, in a window its ER leaves", () => {
  for (const id of ["human", "mouse", "planarian", "fruitfly"]) {
    for (const [mode, gap] of [["schematic", 1.0], ["real", 0.43]]) {
      const { handles, parts, chosen, layout } = built(id, mode);
      const c = layout.NUCLEUS, R = layout.style.nucleusRadius, facing = layout.ER_FACING;
      // The cis face: the Golgi's nearest point to the nucleus, about the gap from the envelope.
      const golgi = vertices(parts.get("golgi").flatMap((part) => part.objects).filter((object) => object.material?.type !== "MeshBasicMaterial")); // not the body a click reaches
      const nearest = Math.min(...golgi.map((point) => Math.hypot(point.x - c.x, point.z - c.z))) - R;
      assert.ok(Math.abs(nearest - gap) < 0.12, `${id} ${mode}: the cis face is ${nearest.toFixed(2)} from the envelope, about ${gap}`);
      // It stands toward the cell's middle, where the ER faces, and the ER's sheets keep out of its window.
      assert.ok(apart(angleAbout(c, layout.GOLGI), facing) < 1e-9, `${id} ${mode}: toward the cell's middle`);
      const walls = parts.get("er")[0].objects.filter((object) => object.isMesh);
      assert.equal(walls.length, 2, `${id} ${mode}: the ER is two arms`);
      const window = Math.max(...golgi.map((point) => apart(angleAbout(c, point), facing)));
      for (const wall of walls) {
        const points = vertices([wall]);
        // Each arm runs on from the envelope: it starts inside the outer nuclear membrane.
        assert.ok(Math.min(...points.map((point) => Math.hypot(point.x - c.x, point.z - c.z))) < R, `${id} ${mode}: an arm runs on from the envelope`);
        const intruding = points.filter((point) => Math.hypot(point.x - c.x, point.z - c.z) > R + 0.3 && apart(angleAbout(c, point), facing) < window * 0.8);
        assert.equal(intruding.length, 0, `${id} ${mode}: no sheet of the ER stands in the Golgi's place`);
      }
      // The centrosome, between the nucleus and the Golgi: scenery that can be chosen, and its panel says what it is and that nothing stands behind it.
      assert.ok(chosen.has("scenery:centrosome"), `${id} ${mode}: the centrosome is drawn as scenery that can be chosen`);
      const item = handles.scenery.find((entry) => entry.id === "scenery:centrosome");
      assert.ok(item && item.label === "Centrosome" && item.sizes.some(([label, text]) => label === "What it is" && /Golgi gathers round it/.test(text)) && item.sizes.some(([, text]) => /Nothing in the engine stands behind it/.test(text)), id);
      const between = layout.CENTROSOME.distanceTo(c.clone().setY(layout.CENTROSOME.y)) - R;
      assert.ok(between > 0 && between < gap, `${id} ${mode}: between the envelope and the cis face`);
      // To scale a ribbon of four stacks; enlarged, one. The panel says which, and that its place is the picture's choice.
      assert.match(handles.structures.golgi[0][1], mode === "real" ? /^A ribbon of 4 stacks of 6 cisternae/ : /^A stack of 5 cisternae/);
      assert.match(handles.structures.golgi[0][1], /beside the nucleus/);
      assert.match(handles.structures.golgi[0][1], /the picture's choice/);
      assert.match(handles.structures.er[0][1], /in two arms, one each side of the Golgi/);
    }
  }
});

test("a plant cell's Golgi is many small stacks in the thin cytoplasm, with no ribbon and no centrosome; its ER is as it was", () => {
  for (const [mode, count] of [["schematic", 14], ["real", 40]]) {
    const { handles, parts, chosen, layout } = built("thalecress", mode);
    assert.ok(!chosen.has("scenery:centrosome") && !handles.scenery.some((entry) => entry.id === "scenery:centrosome"), `${mode}: no centrosome`);
    assert.match(handles.structures.golgi[0][1], new RegExp(`^${count} small stacks`));
    assert.match(handles.structures.golgi[0][1], /no ribbon and no centrosome/);
    // Each stack's body (what a click reaches) stands in the cytoplasm, out of the vacuole.
    const bodies = parts.get("golgi")[0].objects.filter((object) => object.material?.type === "MeshBasicMaterial");
    assert.equal(bodies.length, 1, `${mode}: one body for every stack`);
    const inCytoplasm = vertices(bodies).filter((point) => !layout.vacuole.holds(point)).length / vertices(bodies).length;
    assert.ok(inCytoplasm > (mode === "real" ? 0.6 : 0.3), `${mode}: the stacks stand in the thin cytoplasm (${inCytoplasm.toFixed(2)} of their bodies out of the vacuole; enlarged, they reach into it)`);
    const levels = parts.get("golgi")[0].objects.filter((object) => object.isMesh && !object.isInstancedMesh && object.material.type !== "MeshBasicMaterial");
    assert.equal(levels.length, mode === "real" ? 6 : 5, `${mode}: one mesh for each level of cisterna, however many stacks`);
    assert.equal(parts.get("er")[0].objects.filter((object) => object.isMesh).length, 1, `${mode}: the ER is one arm, on the nucleus's inner side, as before`);
    assert.ok(layout.CENTROSOME === null);
  }
});

test("the stacks are one shared geometry: what a frame pays for the cell's structures stays under its ceiling", () => {
  // Builder objects (each one a draw) and triangles, measured on 17 November 2026 before option B and after it:
  // the Golgi drew 8 objects enlarged and 9 to scale before, and draws as many now, however many stacks it has.
  // The whole cell may draw at most three more objects than before (the ER's second arm and the centrosome).
  const ceilings = {
    "human:schematic": { golgi: [8, 12000], cell: [132, 370000] },
    "human:real": { golgi: [9, 52000], cell: [120, 420000] },
    "thalecress:schematic": { golgi: [8, 22000], cell: [129, 405000] },
    "thalecress:real": { golgi: [9, 70000], cell: [117, 470000] },
  };
  for (const [key, ceiling] of Object.entries(ceilings)) {
    const [id, mode] = key.split(":");
    const { parts } = built(id, mode);
    const golgi = cost(parts.get("golgi").flatMap((part) => part.objects));
    assert.ok(golgi.draws <= ceiling.golgi[0] && golgi.triangles <= ceiling.golgi[1], `${key}: the Golgi draws ${golgi.draws} objects and ${golgi.triangles} triangles`);
    const all = cost([...parts.values()].flat().flatMap((part) => part.objects));
    assert.ok(all.draws <= ceiling.cell[0] && all.triangles <= ceiling.cell[1], `${key}: the cell's structures and parts draw ${all.draws} objects and ${all.triangles} triangles`);
  }
});
