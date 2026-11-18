// Drawing a machine's shape (src/lenses/machine_shape.js; schema/MACHINE_SHAPES.md, "Drawing a shape"): a made-up file
// and every shape file build to one mesh a machine, with the triangles their counts state; every surface's range of the
// mesh is closed; each face finds its surface; a second build is the same geometry; recolouring touches one surface's
// vertices only; disposal frees what was built and nothing of the caller's; a machine with no file is said to have none.
// It also notes what one chosen machine costs a frame at this level (draws and triangles).
//
//   node --test tests/machine_shape_drawing.test.mjs
//
// Nothing needs a browser.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { SHAPE_FORMAT, buildShape, loadShape, shapeColours, shapePath, shapeProblems } from "../src/lenses/machine_shape.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHAPES = path.join(ROOT, "data", "catalogue", "shapes");
const json = (file) => JSON.parse(readFileSync(file, "utf8"));
const catalogue = json(path.join(ROOT, "data", "catalogue", "catalogue.json"));

/** A made-up shape: two closed surfaces of one part (an octahedron and a tetrahedron), and the octahedron's two tones (its halves). */
function madeUp() {
  const octahedron = [100, 0, 0, -100, 0, 0, 0, 100, 0, 0, -100, 0, 0, 0, 100, 0, 0, -100];
  const faces = [0, 2, 4, 2, 1, 4, 1, 3, 4, 3, 0, 4, 2, 0, 5, 1, 2, 5, 3, 1, 5, 0, 3, 5];
  // Its upper half (z >= 0) and lower half, each closed by the square at z = 0 (outside faces first).
  const upper = { vertices: [100, 0, 0, -100, 0, 0, 0, 100, 0, 0, -100, 0, 0, 0, 100], triangles: [0, 2, 4, 2, 1, 4, 1, 3, 4, 3, 0, 4, 0, 3, 2, 3, 1, 2], outer: 4 };
  const lower = { vertices: [100, 0, 0, -100, 0, 0, 0, 100, 0, 0, -100, 0, 0, 0, -100], triangles: [2, 0, 4, 1, 2, 4, 3, 1, 4, 0, 3, 4, 0, 2, 3, 2, 1, 3], outer: 4 };
  return {
    format: SHAPE_FORMAT,
    entry: "MADE",
    unit_nm: 0.01,
    counts: { meshes: 2, vertices: 10, triangles: 12, tones: { meshes: 2, vertices: 10, triangles: 12 } },
    dropped: [],
    meshes: [
      { id: "part-body", part: "body", kind: "nucleoprotein", residues: 30, outer: 8, vertices: octahedron, triangles: faces },
      { id: "chain-Z", chain: "Z", entity: "2", description: "made-up", part: "body", kind: "protein", residues: 4, vertices: [300, 0, 0, 400, 0, 0, 300, 100, 0, 300, 0, 100], triangles: [0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3] },
    ],
    tones: [
      { id: "part-body-nucleic", within: "part-body", part: "body", kind: "nucleic", residues: 10, ...upper },
      { id: "part-body-protein", within: "part-body", part: "body", kind: "protein", residues: 20, ...lower },
    ],
  };
}

/** Every edge of each surface's range met by its triangles turned both ways, as often one way as the other. */
function closedRanges(built) {
  const index = built.mesh.geometry.getIndex().array;
  return built.surfaces.every((row) => {
    const edges = new Map();
    for (let t = row.first; t <= row.last; t++) {
      const [a, b, c] = [index[t * 3], index[t * 3 + 1], index[t * 3 + 2]];
      for (const [p, q] of [[a, b], [b, c], [c, a]]) {
        if (p < row.firstVertex || p >= row.firstVertex + row.vertexCount) return false;
        edges.set(`${p},${q}`, (edges.get(`${p},${q}`) || 0) + 1);
      }
    }
    return [...edges].every(([key, n]) => edges.get(key.split(",").reverse().join(",")) === n);
  });
}

const sameArrays = (one, two) => ["position", "normal", "color"].every((name) => Buffer.from(one.mesh.geometry.getAttribute(name).array.buffer).equals(Buffer.from(two.mesh.geometry.getAttribute(name).array.buffer))) && Buffer.from(one.mesh.geometry.getIndex().array.buffer).equals(Buffer.from(two.mesh.geometry.getIndex().array.buffer));

test("a made-up shape builds to one mesh: the triangles its counts state, closed ranges, faces that find their surfaces, ids as the catalogue names them", () => {
  const data = madeUp();
  assert.deepEqual(shapeProblems(data), []);
  const built = buildShape(data, { kind: "made", perNm: 0.1 });
  assert.equal(built.cost.draws, 1);
  assert.equal(built.mesh.geometry.getIndex().count / 3, data.counts.triangles);
  assert.equal(built.cost.triangles, data.counts.triangles);
  assert.ok(closedRanges(built));
  assert.deepEqual(built.surfaces.map((row) => [row.id, row.part, row.chain, row.kind, row.first, row.last]), [
    ["part-body", "machine:made:body", null, "nucleoprotein", 0, 7],
    ["chain-Z", "machine:made:body", "machine:made:chain-Z", "protein", 8, 11],
  ]);
  for (const row of built.surfaces) for (let face = row.first; face <= row.last; face++) assert.equal(built.surfaceAt(face), row);
  assert.equal(built.surfaceAt(12), null);
  // In the caller's units: a vertex of 100 units of 0.01 nm is 1 nm, and 0.1 of the caller's units a nanometre.
  const box = built.mesh.geometry.boundingBox;
  assert.ok(Math.abs(box.max.x - 0.4) < 1e-6 && Math.abs(box.min.x + 0.1) < 1e-6, `${box.min.x} to ${box.max.x}`);
  // Normals of unit length, pointing out (the octahedron's from its centre).
  const position = built.mesh.geometry.getAttribute("position"), normal = built.mesh.geometry.getAttribute("normal");
  for (let n = 0; n < 6; n++) {
    assert.ok(Math.abs(Math.hypot(normal.getX(n), normal.getY(n), normal.getZ(n)) - 1) < 1e-6);
    assert.ok(normal.getX(n) * position.getX(n) + normal.getY(n) * position.getY(n) + normal.getZ(n) * position.getZ(n) > 0);
  }
  // The two tones in the solid's place, the chain as it was; the seam's vertices shaded by the outside alone.
  const toned = buildShape(data, { kind: "made", tones: true });
  assert.deepEqual(toned.surfaces.map((row) => [row.id, row.kind, row.within]), [["part-body-nucleic", "nucleic", "part-body"], ["part-body-protein", "protein", "part-body"], ["chain-Z", "protein", null]]);
  assert.equal(toned.cost.triangles, data.counts.tones.triangles + data.meshes[1].triangles.length / 3, "the tones and the chain");
  assert.ok(closedRanges(toned));
  const seam = toned.mesh.geometry.getAttribute("normal");
  // A vertex on the seam takes the outside's normal, from both tones' outside faces (not from the hidden face between them, nor from one tone's half alone).
  assert.ok(Math.abs(seam.getX(0) - 1) < 1e-6 && Math.abs(seam.getZ(0)) < 1e-6 && Math.abs(seam.getX(5) - 1) < 1e-6, `${seam.getX(0)}, ${seam.getZ(0)}`);
  built.dispose();
  toned.dispose();
});

test("a second build is the same geometry; recolouring rewrites one surface's vertices; disposal frees what was built and nothing of the caller's", () => {
  const data = madeUp();
  const one = buildShape(data, { kind: "made" }), two = buildShape(data, { kind: "made" });
  assert.ok(sameArrays(one, two));
  const colours = one.mesh.geometry.getAttribute("color");
  const before = Array.from(colours.array);
  const row = one.surfaces[1];
  assert.equal(one.recolour(row.id, "#ff0000"), 1);
  for (let n = 0; n < colours.count; n++) {
    const inRow = n >= row.firstVertex && n < row.firstVertex + row.vertexCount;
    const now = [colours.getX(n), colours.getY(n), colours.getZ(n)];
    if (inRow) assert.deepEqual(now, [1, 0, 0]);
    else assert.deepEqual(now, before.slice(n * 3, n * 3 + 3));
  }
  one.recolour(row);
  assert.deepEqual(Array.from(colours.array), before, "recoloured again by the caller's function, as it was");
  // The caller's colours: a function of part and kind.
  const painted = buildShape(data, { kind: "made", colour: (part, kind) => (kind === "protein" ? 0x00ff00 : 0x0000ff) });
  assert.deepEqual([...painted.mesh.geometry.getAttribute("color").array.slice(0, 3)], [0, 0, 1]);
  // Disposal: the geometry and this module's material are freed; a material the caller gave is the caller's.
  const freed = [];
  one.mesh.geometry.addEventListener("dispose", () => freed.push("geometry"));
  one.mesh.material.addEventListener("dispose", () => freed.push("material"));
  const holder = new THREE.Group();
  holder.add(one.mesh);
  one.dispose();
  one.dispose();
  assert.deepEqual(freed, ["geometry", "material"]);
  assert.equal(holder.children.length, 0);
  const mine = new THREE.MeshStandardMaterial({ vertexColors: true });
  let mineFreed = false;
  mine.addEventListener("dispose", () => (mineFreed = true));
  const theirs = buildShape(data, { kind: "made", material: mine });
  theirs.dispose();
  assert.equal(mineFreed, false);
  two.dispose();
  painted.dispose();
});

test("every shape builds to the triangles its counts state, one draw a machine, with every face finding a surface the catalogue names", (t) => {
  const files = readdirSync(SHAPES).filter((name) => name.endsWith(".json")).sort();
  // Every machine and unit the catalogue measures, with the page id its view chooses it by (a kind's `machine:<kind>`, a unit's own id).
  const items = [
    ...catalogue.entries.filter((entry) => entry.size?.shape === "measured").map((entry) => ({ species: entry.species, kind: entry.id, id: null, size: entry.size })),
    ...Object.entries(catalogue.unit_sizes?.units || {}).flatMap(([unit, by]) => Object.values(by).filter((size) => size.shape === "measured").map((size) => ({ species: null, kind: null, id: unit, size }))),
  ];
  const drawn = new Set();
  const rows = [];
  for (const item of items) {
    const where = shapePath(item.species, item.kind, item.size);
    const name = where.slice("shapes/".length);
    // Syn3A's and M. pneumoniae's ribosomes are drawn at E. coli's measure and have no file of their own: the view offers them E. coli's.
    if (!files.includes(name)) {
      assert.match(item.size.whose || "", /./, `${item.species} ${item.kind}: no shape at ${where}, and its size is another species'`);
      continue;
    }
    drawn.add(name);
    const data = json(path.join(SHAPES, name));
    const prefix = item.id || `machine:${item.kind}`;
    const parts = new Set((item.size.parts || []).map((part) => `${prefix}:${part.id}`));
    const chains = new Set((item.size.chains || []).map((chain) => `${prefix}:${chain.id}`));
    for (const tones of [false, true]) {
      if (tones && !data.tones) continue;
      const built = buildShape(data, { kind: item.kind, id: item.id, perNm: 0.1, colour: shapeColours({}), tones });
      const counted = tones ? data.counts.tones.triangles + data.meshes.filter((mesh) => !data.tones.some((tone) => tone.within === mesh.id)).reduce((sum, mesh) => sum + mesh.triangles.length / 3, 0) : data.counts.triangles;
      assert.equal(built.cost.triangles, counted, `${name}${tones ? ", in two tones" : ""}`);
      assert.equal(built.cost.draws, 1);
      assert.ok(built.cost.triangles <= 12000, `${name}: ${built.cost.triangles} triangles, within the budget of one chosen machine`);
      assert.ok(closedRanges(built), `${name}: every surface closed`);
      const second = buildShape(data, { kind: item.kind, id: item.id, perNm: 0.1, colour: shapeColours({}), tones });
      assert.ok(sameArrays(built, second), `${name}: a second build is the same geometry`);
      second.dispose();
      // Every face finds its surface; every surface is named as the catalogue names its parts and chains (where it names any).
      for (const row of built.surfaces) {
        assert.equal(built.surfaceAt(row.first), row);
        assert.equal(built.surfaceAt(row.last), row);
        if (row.part && parts.size) assert.ok(parts.has(row.part), `${name}: ${row.part} is a part the catalogue names`);
        if (row.chain && chains.size) assert.ok(chains.has(row.chain), `${name}: ${row.chain} is a chain the catalogue names`);
        assert.ok(row.part || row.chain, `${name}: ${row.id} can be chosen`);
      }
      // And the reverse: a file drawn by chains has a surface for every chain the catalogue names.
      if (data.parameters?.by === "chains" && chains.size) assert.deepEqual(built.surfaces.map((row) => row.chain).sort(), [...chains].sort(), `${name}: a surface for each chain the catalogue names`);
      if (!rows.some((one) => one.startsWith(`${name}${tones ? " (tones)" : ""}:`))) rows.push(`${name}${tones ? " (tones)" : ""}: ${built.cost.draws} draw, ${built.cost.triangles} triangles, ${built.cost.vertices} vertices`);
      built.dispose();
    }
  }
  // Every shape file is one the catalogue draws.
  assert.deepEqual([...drawn].sort(), files);
  // What one chosen machine costs a frame at the Shape level.
  for (const row of rows) t.diagnostic(`frame cost: ${row}`);
});

test("a machine with no shape file is said to have none; a file that cannot be drawn is said so; a catalogue entry finds its file's path", async () => {
  const missing = await loadShape("shapes/syn3a.ribosome.json", { load: async (where) => { throw new Error(`${where} answered 404`); } });
  assert.equal(missing.status, "none");
  assert.match(missing.words, /^No shape is published for this machine \(shapes\/syn3a\.ribosome\.json\)/);
  assert.equal((await loadShape("shapes/x.y.json", { load: async (where) => { throw new Error(`${where} answered 403`); } })).status, "none", "any client error");
  // A page that carries its shapes inside it, and not this one: none, without a fetch.
  const carried = { querySelectorAll: () => [{ getAttribute: () => "shapes/ecoli.lon.json" }] };
  let fetched = false;
  assert.equal((await loadShape("shapes/syn3a.ribosome.json", { root: carried, load: async () => { fetched = true; } })).status, "none");
  assert.equal(fetched, false);
  // The page's own loader against the local server: a name it does not publish is none; one it does is found.
  const { createServer } = await import("../tools/serve.mjs");
  const server = createServer({ offline: true, log: () => {} });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const base = `http://127.0.0.1:${server.address().port}/`;
    const fetcher = (where) => fetch(new URL(where, base));
    const absent = await loadShape("shapes/syn3a.ribosome.json", { fetcher, root: null });
    assert.equal(absent.status, "none", absent.words);
    const served = await loadShape("shapes/ecoli.translocon.json", { fetcher, root: null });
    assert.equal(served.status, "found", served.words);
    assert.equal(served.data.entry, "9RBF");
  } finally {
    server.close();
  }
  const broken = await loadShape("shapes/x.y.json", { load: async () => ({ format: "something else", meshes: [] }) });
  assert.equal(broken.status, "failed");
  assert.match(broken.words, /cannot be drawn: its format is something else/);
  const away = await loadShape("shapes/x.y.json", { load: async () => { throw new Error("shapes/x.y.json could not be fetched"); } });
  assert.equal(away.status, "failed");
  const found = await loadShape("shapes/ecoli.lon.json", { load: async (where) => json(path.join(ROOT, "data", "catalogue", where.replace("shapes/", "shapes/"))) });
  assert.equal(found.status, "found");
  assert.equal(found.data.entry, "6U5Z");
  assert.equal(shapePath("ecoli", "protein-translocon", { from: "data/catalogue/measures/ecoli.translocon.json" }), "shapes/ecoli.translocon.json");
  assert.equal(shapePath("ecoli", "ribosome", { from: "cell.parts.ribosome of the species' file" }), "shapes/ecoli.ribosome.json");
  assert.equal(shapePath("syn3a", "ribosome", { from: "cell.parts.ribosome of the species' file" }), "shapes/syn3a.ribosome.json");
  assert.throws(() => buildShape({ format: SHAPE_FORMAT, unit_nm: 0.01, meshes: [{ id: "x", vertices: [0, 0], triangles: [] }] }, { kind: "x" }), /cannot be drawn/);
});
