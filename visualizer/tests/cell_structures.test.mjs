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
  return { parts, ctx: { part, scale: part, known: (name) => known.includes(name), neutral, neutralPoints: () => new THREE.PointsMaterial(), neutralLine: () => new THREE.LineBasicMaterial(), illustrate: () => {}, scenery: () => {}, sprite: () => {} } };
}
const built = (id, mode, known = ["nucleus", "chromatin", "golgi", "vesicles", "ribosomes", "er"]) => {
  const file = species(id), levels = Object.fromEntries(file.levels.map((level) => [level.id, level]));
  const a = stand(known);
  const handles = buildCell(a.ctx, stand(known).ctx, mode, { shape: levels.cell.shape, parts: file.cell.parts || {}, has: () => true, neighbours: Boolean(levels.tissue), notes: [] });
  return { handles, parts: a.parts };
};

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
