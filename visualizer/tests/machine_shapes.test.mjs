// A machine's shape (schema/MACHINE_SHAPES.md; tools/shape_particle.py): the tool on made-up machines whose answers
// are known (closed, outward, holding its residues' own volume, inside the bounds its atoms give, the same bytes on a
// second run, the budget, the refusals), and E. coli's six shape files against the contract and their measures.
//
//   node --test tests/machine_shapes.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "shape_particle.py");
const SHAPES = path.join(ROOT, "data", "catalogue", "shapes");
const MEASURES = path.join(ROOT, "data", "catalogue", "measures");
// A machine's measure: the catalogue's, but for the ribosome, whose one record is the species files' (data/measures/).
const measureOf = (name) => (name === "ecoli.ribosome.json" ? path.join(ROOT, "data", "measures", name) : path.join(MEASURES, name));
const VOLUME = { protein: 0.135, nucleic: 0.32 };
const run = (...args) => spawnSync("python3", ["-I", TOOL, ...args], { encoding: "utf8" });

/** A made-up entry: each chain a block of residues 3.8 Å apart, one atom standing for each (CA, or P for a nucleotide). */
function madeEntry(chains, entities) {
  const columns = ["group_PDB", "id", "type_symbol", "label_atom_id", "label_alt_id", "label_comp_id", "label_asym_id", "label_entity_id", "label_seq_id", "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z", "occupancy", "B_iso_or_equiv", "auth_asym_id", "pdbx_PDB_model_num"];
  const atoms = [];
  for (const { chain, entity, at, side, nucleic } of chains) {
    let seq = 0;
    for (let i = 0; i < side; i++) for (let j = 0; j < side; j++) for (let k = 0; k < side; k++) {
      seq += 1;
      const [atom, comp] = nucleic ? ["P", "A"] : ["CA", "ALA"];
      atoms.push(["ATOM", atoms.length + 1, "C", atom, ".", comp, chain, entity, seq, "?", at[0] + i * 3.8, at[1] + j * 3.8, at[2] + k * 3.8, 1, 0, chain, 1].join(" "));
      if (!nucleic) atoms.push(["ATOM", atoms.length + 1, "C", "CB", ".", comp, chain, entity, seq, "?", at[0] + i * 3.8 + 1, at[1] + j * 3.8, at[2] + k * 3.8, 1, 0, chain, 1].join(" "));
    }
  }
  return ["data_MADE", "#", "_struct.title 'A made-up machine'", "_exptl.method 'X-RAY DIFFRACTION'", "_refine.ls_d_res_high 2.0", "#",
    "loop_", "_entity.id", "_entity.type", "_entity.pdbx_description", ...entities.map(([id, description]) => `${id} polymer '${description}'`), "#",
    "loop_", ...columns.map((name) => `_atom_site.${name}`), ...atoms, "#", ""].join("\n");
}

/** A mesh's checks: each edge met both ways as often, the volume it holds (nm³), its vertices' farthest reach from the origin (nm). */
function checked(mesh, unit) {
  const v = mesh.vertices, t = mesh.triangles, edges = new Map();
  const at = (n) => [v[3 * n] * unit, v[3 * n + 1] * unit, v[3 * n + 2] * unit];
  let volume = 0;
  for (let i = 0; i < t.length; i += 3) {
    const [a, b, c] = [t[i], t[i + 1], t[i + 2]];
    for (const [p, q] of [[a, b], [b, c], [c, a]]) edges.set(`${p}>${q}`, (edges.get(`${p}>${q}`) || 0) + 1);
    const [x1, y1, z1] = at(a), [x2, y2, z2] = at(b), [x3, y3, z3] = at(c);
    volume += (x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)) / 6;
  }
  const closed = [...edges].every(([key, count]) => edges.get(key.split(">").reverse().join(">")) === count);
  let reach = 0;
  for (let n = 0; n < v.length / 3; n++) reach = Math.max(reach, Math.hypot(...at(n)));
  return { closed, volume, reach, triangles: t.length / 3 };
}

test("the tool makes a closed, outward surface for each chain that holds its own volume, inside the bounds its atoms give, the same bytes twice", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    const file = path.join(folder, "made.cif"), out = path.join(folder, "one.json"), again = path.join(folder, "two.json");
    writeFileSync(file, madeEntry([{ chain: "A", entity: 1, at: [0, 0, 0], side: 4 }, { chain: "B", entity: 2, at: [0, 40, 0], side: 4 }], [["1", "Motor"], ["2", "Rotor"]]));
    for (const target of [out, again]) assert.equal(run(file, "--part", "low=1", "--part", "high=chains:B", "--frame-from", "low", "--frame-to", "high", "--out", target).status, 0);
    assert.equal(readFileSync(out, "utf8"), readFileSync(again, "utf8"), "the same bytes on a second run");
    const shape = JSON.parse(readFileSync(out, "utf8"));
    assert.equal(shape.format, "cells.visualizer.machine-shape@1");
    assert.match(shape.definition, /closed surface that holds its own volume \(0\.135 nm³ for each amino acid, 0\.32 nm³ for each nucleotide\) in a cloud where each residue is spread as a Gaussian 1 nm wide, on a grid 1 nm apart/);
    assert.deepEqual(shape.meshes.map((mesh) => [mesh.id, mesh.chain, mesh.part, mesh.kind, mesh.residues]), [["chain-A", "A", "low", "protein", 64], ["chain-B", "B", "high", "protein", 64]]);
    // The atoms stand within about 7.3 nm of the whole's middle (two blocks 4 nm apart, each 1.1 nm to a corner): the surface within three widths of them.
    const farthest = Math.hypot(0.57, 2 + 0.57, 0.57) + 0.1;
    for (const mesh of shape.meshes) {
      const { closed, volume, reach } = checked(mesh, shape.unit_nm);
      assert.ok(closed, `${mesh.id}: closed`);
      assert.ok(volume > 0, `${mesh.id}: facing out`);
      assert.ok(Math.abs(volume / (mesh.residues * VOLUME.protein) - 1) < 0.02, `${mesh.id}: holds ${volume.toFixed(2)} nm³`);
      assert.ok(reach < farthest + 3 * shape.parameters.width_nm, `${mesh.id}: inside its atoms' bounds (${reach.toFixed(2)} nm)`);
    }
    // In the frame, y runs from the low part to the high one: the high chain above the middle.
    const high = shape.meshes[1].vertices.filter((_, n) => n % 3 === 1);
    assert.ok(high.reduce((a, b) => a + b, 0) / high.length > 0, "the frame's y runs from low to high");
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("a ribosome's surfaces: each subunit's protein and nucleic acid apart, in two kinds", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    const file = path.join(folder, "made.cif");
    writeFileSync(file, madeEntry([
      { chain: "A", entity: 1, at: [0, 0, 0], side: 5, nucleic: true },
      { chain: "B", entity: 2, at: [25, 0, 0], side: 3 },
      { chain: "C", entity: 3, at: [0, 45, 0], side: 4, nucleic: true },
      { chain: "D", entity: 4, at: [25, 45, 0], side: 3 },
    ], [["1", "23S ribosomal RNA"], ["2", "50S ribosomal protein L2"], ["3", "16S ribosomal RNA"], ["4", "30S ribosomal protein S2"]]));
    const done = run(file, "--ribosome");
    assert.equal(done.status, 0, done.stderr);
    const shape = JSON.parse(done.stdout);
    assert.equal(shape.parameters.width_nm, 1.6);
    assert.deepEqual(shape.meshes.map((mesh) => [mesh.id, mesh.part, mesh.kind, mesh.residues]).sort(), [["part-large-nucleic", "large", "nucleic", 125], ["part-large-protein", "large", "protein", 27], ["part-small-nucleic", "small", "nucleic", 64], ["part-small-protein", "small", "protein", 27]]);
    for (const mesh of shape.meshes) {
      const { closed, volume } = checked(mesh, shape.unit_nm);
      assert.ok(closed && volume > 0 && Math.abs(volume / (mesh.residues * VOLUME[mesh.kind]) - 1) < 0.02, `${mesh.id}: ${volume}`);
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the tool refuses, and writes nothing, where a part names no atom, a frame's part is not given, or the budget would break", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    const file = path.join(folder, "made.cif"), out = path.join(folder, "out.json");
    writeFileSync(file, madeEntry([{ chain: "A", entity: 1, at: [0, 0, 0], side: 4 }], [["1", "Motor"]]));
    let done = run(file, "--part", "nothing=7", "--out", out);
    assert.notEqual(done.status, 0);
    assert.match(done.stderr, /the part nothing \(entities 7\) names no atom; nothing is made/);
    done = run(file, "--part", "head=1", "--frame-from", "head", "--frame-to", "ring", "--out", out);
    assert.match(done.stderr, /the frame's part ring is not given with --part; nothing is made/);
    done = run(file, "--most-triangles", "10", "--out", out);
    assert.match(done.stderr, /triangles, above the budget of 10; nothing is made/);
    done = run(file, "--most-bytes", "100", "--out", out);
    assert.match(done.stderr, /bytes, above the budget of 100; nothing is made/);
    assert.equal(existsSync(out), false);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("E. coli's six shape files hold to the contract and sit where their measures' bodies sit", () => {
  const names = readdirSync(SHAPES).filter((name) => name.endsWith(".json")).sort();
  assert.deepEqual(names, ["ecoli.atp-synthase.json", "ecoli.hslv.json", "ecoli.lon.json", "ecoli.ribosome.json", "ecoli.rna-polymerase.json", "ecoli.translocon.json"]);
  for (const name of names) {
    const file = path.join(SHAPES, name), shape = JSON.parse(readFileSync(file, "utf8"));
    const measured = Object.values(JSON.parse(readFileSync(measureOf(name), "utf8")).measured)[0];
    // The budget: a file under 400 KB and 20,000 triangles, a ribosome's under 8,000; a chain's surface up to about 2,000.
    assert.ok(statSync(file).size < 400000, `${name}: ${statSync(file).size} bytes`);
    assert.ok(shape.counts.triangles < (name === "ecoli.ribosome.json" ? 8000 : 20000), `${name}: ${shape.counts.triangles} triangles`);
    assert.equal(shape.format, "cells.visualizer.machine-shape@1");
    assert.equal(shape.tool, "tools/shape_particle.py");
    assert.equal(shape.entry, measured.entry, name);
    assert.match(shape.illustration, /the viewer's own surface of the entry's coordinates, an illustration/i);
    assert.match(shape.frame, /^the measuring tool's/);
    assert.equal(shape.counts.meshes, shape.meshes.length);
    assert.equal(shape.counts.triangles, shape.meshes.reduce((sum, mesh) => sum + mesh.triangles.length / 3, 0));
    const parts = measured.parts ? Object.keys(measured.parts) : ["large", "small"];
    const chains = new Map((measured.chains || []).map((chain) => [chain.chain, chain]));
    const byPart = new Map(); // a part's surfaces (protein and nucleic acid): their volume and its middle, to set against the part's ellipsoid
    for (const mesh of shape.meshes) {
      const { closed, volume, triangles } = checked(mesh, shape.unit_nm);
      assert.ok(closed && volume > 0, `${name} ${mesh.id}: closed and facing out`);
      assert.ok(Math.abs(volume / (mesh.residues * VOLUME[mesh.kind]) - 1) < 0.02, `${name} ${mesh.id}: holds ${volume.toFixed(1)} nm³`);
      assert.ok(!mesh.chain || triangles <= 2000, `${name} ${mesh.id}: ${triangles} triangles, a chain's surface`);
      assert.ok(mesh.vertices.every(Number.isInteger) && mesh.triangles.every((n) => Number.isInteger(n) && n >= 0 && n < mesh.vertices.length / 3), `${name} ${mesh.id}: integers`);
      assert.ok(mesh.part === null || parts.includes(mesh.part), `${name} ${mesh.id}: its part ${mesh.part} is the measure's`);
      if (!mesh.chain && mesh.part) {
        const v = mesh.vertices, t = mesh.triangles, at = (n) => [v[3 * n], v[3 * n + 1], v[3 * n + 2]].map((x) => x * shape.unit_nm);
        const sum = byPart.get(mesh.part) || { held: 0, middle: [0, 0, 0] };
        for (let i = 0; i < t.length; i += 3) {
          const [a, b, c] = [at(t[i]), at(t[i + 1]), at(t[i + 2])];
          const w = (a[0] * (b[1] * c[2] - c[1] * b[2]) - a[1] * (b[0] * c[2] - c[0] * b[2]) + a[2] * (b[0] * c[1] - c[0] * b[1])) / 6;
          sum.held += w;
          for (let n = 0; n < 3; n++) sum.middle[n] += (w * (a[n] + b[n] + c[n])) / 4;
        }
        byPart.set(mesh.part, sum);
      }
      if (mesh.chain) {
        // Each chain's surface is the body the catalogue names chain-<id>, and sits on its ellipsoid: the volume's middle
        // within a quarter of the chain's farthest reach of the measure's centre (one atom stands for each residue here).
        const body = chains.get(mesh.chain);
        assert.ok(body && mesh.id === `chain-${mesh.chain}`, `${name} ${mesh.id}: a chain of the measure`);
        const middle = [0, 0, 0];
        let held = 0;
        const v = mesh.vertices, t = mesh.triangles, at = (n) => [v[3 * n], v[3 * n + 1], v[3 * n + 2]].map((x) => x * shape.unit_nm);
        for (let i = 0; i < t.length; i += 3) {
          const [a, b, c] = [at(t[i]), at(t[i + 1]), at(t[i + 2])];
          const w = (a[0] * (b[1] * c[2] - c[1] * b[2]) - a[1] * (b[0] * c[2] - c[0] * b[2]) + a[2] * (b[0] * c[1] - c[0] * b[1])) / 6;
          held += w;
          for (let n = 0; n < 3; n++) middle[n] += (w * (a[n] + b[n] + c[n])) / 4;
        }
        const off = Math.hypot(...middle.map((x, n) => x / held - body.centre_nm[n]));
        assert.ok(off <= 0.25 * Math.max(...body.farthest_nm), `${name} ${mesh.id}: ${off.toFixed(2)} nm from its ellipsoid's centre`);
      }
    }
    // A part drawn by its surfaces (a ribosome's subunit) sits on its ellipsoid as a chain does.
    for (const [part, { held, middle }] of byPart) {
      const body = measured.parts?.[part] || measured[part];
      const off = Math.hypot(...middle.map((x, n) => x / held - body.centre_nm[n]));
      assert.ok(off <= 0.25 * Math.max(...body.farthest_nm), `${name} ${part}: ${off.toFixed(2)} nm from its ellipsoid's centre`);
    }
  }
});

const DATA = process.env.ECOLI_ENTRIES || "/mnt/datasets/Cells/ecoli";
test("each of the six files is the tool's shape of its entry, made again byte for byte by the contract's call", { skip: !existsSync(path.join(DATA, "wwpdb-ribosome", "7K00.cif.gz")) && "the entries are not on this machine" }, () => {
  const left = Object.values(JSON.parse(readFileSync(path.join(MEASURES, "ecoli.translocon.json"), "utf8")).measured)[0].left_out.map((item) => item.entity).join(",");
  const calls = {
    "ecoli.ribosome.json": ["wwpdb-ribosome/7K00.cif.gz", "--ribosome"],
    "ecoli.atp-synthase.json": ["wwpdb-atp-synthase/6OQR.cif.gz", "--part", "head=2,6", "--part", "central-stalk=5,4", "--part", "peripheral-stalk=3,1", "--part", "ring=7", "--part", "stator-foot=8", "--frame-from", "ring", "--frame-to", "head"],
    "ecoli.rna-polymerase.json": ["wwpdb-rna-polymerase/6P1K.cif.gz", "--part", "beta=2", "--part", "beta-prime=3", "--part", "alpha=1", "--part", "omega=4", "--part", "sigma=5"],
    "ecoli.translocon.json": ["wwpdb-translocon/9RBF.cif.gz", "--exclude", left, "--part", "secy=7", "--part", "sece=8", "--part", "secg=9"],
    "ecoli.hslv.json": ["wwpdb-hslv/1G4A-assembly1.cif.gz", "--part", "hslv=2", "--part", "hslu=1", "--frame-from", "hslv", "--frame-to", "hslu"],
    "ecoli.lon.json": ["wwpdb-lon/6U5Z.cif.gz"],
  };
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    for (const [name, [entry, ...options]] of Object.entries(calls)) {
      const out = path.join(folder, name);
      const done = run(path.join(DATA, entry), ...options, "--out", out);
      assert.equal(done.status, 0, done.stderr);
      assert.ok(readFileSync(out).equals(readFileSync(path.join(SHAPES, name))), `${name} is made again byte for byte`);
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
