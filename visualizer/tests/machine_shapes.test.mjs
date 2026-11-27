// A machine's shape (schema/MACHINE_SHAPES.md; tools/shape_particle.py): the tool on made-up machines whose answers
// are known (closed, outward, holding its residues' own volume, inside the bounds its atoms give, the same bytes on a
// second run, a part's solid and its two tones, slivers dropped and listed, the budget, the refusals), and E. coli's
// shape files against the contract and their measures, each made again byte for byte where its entry is saved here.
//
//   node --test tests/machine_shapes.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { execFile, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "shape_particle.py");
const SHAPES = path.join(ROOT, "data", "catalogue", "shapes");
const VOLUME = { protein: 0.135, nucleic: 0.32 };
// Each shape file's call (schema/MACHINE_SHAPES.md): its entry as saved under the datasets' folder, the measure whose
// parts, frame and left-out entities it takes, the width where it differs from the standard setting, and any other option.
const CALLS = {
  "ecoli.ribosome.json": ["ecoli/wwpdb-ribosome/7K00.cif.gz", "data/measures/ecoli.ribosome.json"],
  "ecoli.atp-synthase.json": ["ecoli/wwpdb-atp-synthase/6OQR.cif.gz", "data/catalogue/measures/ecoli.atp-synthase.json"],
  "ecoli.rna-polymerase.json": ["ecoli/wwpdb-rna-polymerase/6P1K.cif.gz", "data/catalogue/measures/ecoli.rna-polymerase.json"],
  "ecoli.translocon.json": ["ecoli/wwpdb-translocon/9RBF.cif.gz", "data/catalogue/measures/ecoli.translocon.json"],
  "ecoli.hslv.json": ["ecoli/wwpdb-hslv/1G4A-assembly1.cif.gz", "data/catalogue/measures/ecoli.hslv.json"],
  "ecoli.lon.json": ["ecoli/wwpdb-lon/6U5Z.cif.gz", "data/catalogue/measures/ecoli.lon.json"],
  "human.proteasome.json": ["human/wwpdb-proteasome-g/7QYB.cif.gz", "data/catalogue/measures/human.proteasome.json", 1.5],
  "human.atp-synthase.json": ["human/wwpdb-atp-synthase-g/8H9T.cif.gz", "data/catalogue/measures/human.atp-synthase.json"],
  "human.rna-polymerase.json": ["human/wwpdb-rna-polymerase-g/6DRD.cif.gz", "data/catalogue/measures/human.rna-polymerase.json"],
  "human.rna-polymerase-i.json": ["human/wwpdb-rna-polymerase-i-g/7OBA.cif.gz", "data/catalogue/measures/human.rna-polymerase-i.json"],
  "human.rna-polymerase-iii.json": ["human/wwpdb-rna-polymerase-iii-g/7D59.cif.gz", "data/catalogue/measures/human.rna-polymerase-iii.json"],
  "human.complex-i.json": ["human/wwpdb-complex-i-g/9I4I.cif.gz", "data/catalogue/measures/human.complex-i.json", 1.3],
  "human.mitochondrial-ribosome.json": ["human/wwpdb-mitochondrial-ribosome-g/9S7C.cif.gz", "data/catalogue/measures/human.mitochondrial-ribosome.json", 1.8, "--by", "parts"],
  "human.cmg-helicase.json": ["human/wwpdb-cmg-helicase-g/6XTX.cif.gz", "data/catalogue/measures/human.cmg-helicase.json"],
  "human.vault.json": ["vault/wwpdb-vault-9mxv-e1/9MXV-assembly1.cif.gz", "data/catalogue/measures/human.vault.json", 2.7, "--by", "parts"],
  "animals.ribosome.json": ["human/wwpdb-ribosome-80s-b/8YOP.cif.gz", "data/catalogue/measures/animals.ribosome.json", 2.0],
  "animals.sodium-pump.json": ["human/wwpdb-sodium-pump/7E1Z.cif.gz", "data/catalogue/measures/animals.sodium-pump.json"],
  "animals.serca.json": ["human/wwpdb-serca/6LLE.cif.gz", "data/catalogue/measures/animals.serca.json"],
  "animals.ip3r.json": ["human/wwpdb-ip3r/6DQJ.cif.gz", "data/catalogue/measures/animals.ip3r.json", 1.1],
  "animals.kv1-2.json": ["human/wwpdb-kv-channel/3LUT-assembly1.cif.gz", "data/catalogue/measures/animals.kv1-2.json"],
  "animals.connexin-channel.json": ["human/wwpdb-gap-junction-cx43/7Z22.cif.gz", "data/catalogue/measures/animals.connexin-channel.json"],
  "animals.innexin-channel.json": ["planarian/wwpdb-innexin-channel/5H1R.cif.gz", "data/catalogue/measures/animals.innexin-channel.json"],
  "haloferax.cetz1.json": ["visualizer/haloferax-pdb/4B46-assembly1.cif.gz", "data/catalogue/measures/haloferax.cetz1.json", 0.5],
  "haloferax.cetz2.json": ["visualizer/haloferax-pdb/4B45-assembly1.cif.gz", "data/catalogue/measures/haloferax.cetz2.json", 0.48],
  "haloferax.dihydrofolate-reductase.json": ["visualizer/haloferax-pdb/1VDR-assembly1.cif.gz", "data/catalogue/measures/haloferax.dihydrofolate-reductase.json", 0.42],
  "haloferax.haloferax-70s-ribosome.json": ["visualizer/haloferax-pdb/12DM-assembly1.cif.gz", "data/catalogue/measures/haloferax.haloferax-70s-ribosome.json", 1.5],
  "haloferax.haloferax-pcna.json": ["visualizer/haloferax-pdb/3IFV-assembly1.cif.gz", "data/catalogue/measures/haloferax.haloferax-pcna.json", 0.52],
  "haloferax.haloferax-s-layer.json": ["visualizer/haloferax-pdb/7PTR-assembly1.cif.gz", "data/catalogue/measures/haloferax.haloferax-s-layer.json", 0.89],
  "haloferax.haloferax-trna-fragment.json": ["visualizer/haloferax-pdb/8WQ2-assembly1.cif.gz", "data/catalogue/measures/haloferax.haloferax-trna-fragment.json", 1.2],
  "haloferax.haloferax-type-iv-pilus.json": ["visualizer/haloferax-pdb/8FJ5-assembly1.cif.gz", "data/catalogue/measures/haloferax.haloferax-type-iv-pilus.json", 0.86],
  "haloferax.hvo0758.json": ["visualizer/haloferax-pdb/8Q5B-assembly1.cif.gz", "data/catalogue/measures/haloferax.hvo0758.json", 0.32],
  "haloferax.hvo2753.json": ["visualizer/haloferax-pdb/6YDH-assembly1.cif.gz", "data/catalogue/measures/haloferax.hvo2753.json", 0.32],
  "haloferax.hvo2922.json": ["visualizer/haloferax-pdb/6Q2Z-assembly1.cif.gz", "data/catalogue/measures/haloferax.hvo2922.json", 0.32],
  "haloferax.malate-dehydrogenase.json": ["visualizer/haloferax-pdb/4BGU-assembly1.cif.gz", "data/catalogue/measures/haloferax.malate-dehydrogenase.json", 0.56],
  "haloferax.malate-synthase.json": ["visualizer/haloferax-pdb/3OYZ-assembly1.cif.gz", "data/catalogue/measures/haloferax.malate-synthase.json", 0.58],
  "haloferax.molybdopterin-converting-factor-1.json": ["visualizer/haloferax-pdb/2M19-assembly1.cif.gz", "data/catalogue/measures/haloferax.molybdopterin-converting-factor-1.json", 0.36],
  "haloferax.samp1.json": ["visualizer/haloferax-pdb/4HRO-assembly1.cif.gz", "data/catalogue/measures/haloferax.samp1.json", 0.32],
  "haloferax.samp2.json": ["visualizer/haloferax-pdb/4HRS-assembly1.cif.gz", "data/catalogue/measures/haloferax.samp2.json", 0.32],
  "haloferax.trm112-hvo0019.json": ["visualizer/haloferax-pdb/6F5Z-assembly1.cif.gz", "data/catalogue/measures/haloferax.trm112-hvo0019.json", 0.45],
  "haloferax.wor83.json": ["visualizer/haloferax-pdb/9Q1T-assembly1.cif.gz", "data/catalogue/measures/haloferax.wor83.json", 0.65],
  "physarum.actin-fragmin-complex.json": ["visualizer/physarum-pdb/7W51-assembly1.cif.gz", "data/catalogue/measures/physarum.actin-fragmin-complex.json", 0.48],
  "physarum.actin-fragmin-kinase.json": ["visualizer/physarum-pdb/1CJA-assembly1.cif.gz", "data/catalogue/measures/physarum.actin-fragmin-kinase.json", 0.48],
  "physarum.cbp40.json": ["visualizer/physarum-pdb/1IJ5-assembly1.cif.gz", "data/catalogue/measures/physarum.cbp40.json", 0.48],
  "physarum.cytochrome-b5-reductase.json": ["visualizer/physarum-pdb/2EIX-assembly1.cif.gz", "data/catalogue/measures/physarum.cytochrome-b5-reductase.json", 0.44],
  "physarum.fragmin-p.json": ["visualizer/physarum-pdb/6LJC-assembly1.cif.gz", "data/catalogue/measures/physarum.fragmin-p.json", 0.40],
  "physarum.haemagglutinin-i.json": ["visualizer/physarum-pdb/3A5P-assembly1.cif.gz", "data/catalogue/measures/physarum.haemagglutinin-i.json", 0.32],
  "physarum.i-ppoi.json": ["visualizer/physarum-pdb/1A73-assembly1.cif.gz", "data/catalogue/measures/physarum.i-ppoi.json", 0.44],
  "physarum.myosin-ii-regulatory-domain.json": ["visualizer/physarum-pdb/2BL0-assembly1.cif.gz", "data/catalogue/measures/physarum.myosin-ii-regulatory-domain.json", 0.40],
  "physarum.spherulin-3a.json": ["visualizer/physarum-pdb/1HDF-assembly1.cif.gz", "data/catalogue/measures/physarum.spherulin-3a.json", 0.32],
};
const run = (...args) => spawnSync("python3", ["-I", TOOL, ...args], { encoding: "utf8" });

/** A made-up entry: each chain a block of residues 3.8 Å apart, one atom standing for each (CA, or P for a nucleotide). */
function madeEntry(chains, entities) {
  const columns = ["group_PDB", "id", "type_symbol", "label_atom_id", "label_alt_id", "label_comp_id", "label_asym_id", "label_entity_id", "label_seq_id", "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z", "occupancy", "B_iso_or_equiv", "auth_asym_id", "pdbx_PDB_model_num"];
  const atoms = [];
  for (const { chain, entity, at, side, nucleic, from = 0 } of chains) {
    let seq = from;
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

/** The least distance from a point to a triangle (Ericson, Real-Time Collision Detection, 5.1.5). */
function toTriangle(p, a, b, c) {
  const sub = (u, v) => [u[0] - v[0], u[1] - v[1], u[2] - v[2]], dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  const along = (o, d, t) => [o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t];
  const ab = sub(b, a), ac = sub(c, a), ap = sub(p, a);
  const d1 = dot(ab, ap), d2 = dot(ac, ap);
  let q;
  if (d1 <= 0 && d2 <= 0) q = a;
  else {
    const bp = sub(p, b), d3 = dot(ab, bp), d4 = dot(ac, bp);
    const cp = sub(p, c), d5 = dot(ab, cp), d6 = dot(ac, cp);
    const vc = d1 * d4 - d3 * d2, vb = d5 * d2 - d1 * d6, va = d3 * d6 - d5 * d4;
    if (d3 >= 0 && d4 <= d3) q = b;
    else if (vc <= 0 && d1 >= 0 && d3 <= 0) q = along(a, ab, d1 / (d1 - d3));
    else if (d6 >= 0 && d5 <= d6) q = c;
    else if (vb <= 0 && d2 >= 0 && d6 <= 0) q = along(a, ac, d2 / (d2 - d6));
    else if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) q = along(b, sub(c, b), (d4 - d3) / (d4 - d3 + (d5 - d6)));
    else {
      const den = 1 / (va + vb + vc);
      q = [0, 1, 2].map((n) => a[n] + ab[n] * vb * den + ac[n] * vc * den);
    }
  }
  return Math.hypot(...sub(p, q));
}

/** Whether a point lies inside a closed surface, or on it (within `near` nm): the parity of a ray's crossings, in a direction no grid follows. */
function insideOrOn(point, mesh, unit, near = 0.02) {
  const v = mesh.vertices, t = mesh.triangles, at = (n) => [v[3 * n] * unit, v[3 * n + 1] * unit, v[3 * n + 2] * unit];
  const d = [1, 0.3713, 0.1781];
  let crossings = 0, least = Infinity;
  for (let i = 0; i < t.length; i += 3) {
    const [a, b, c] = [at(t[i]), at(t[i + 1]), at(t[i + 2])];
    const distance = toTriangle(point, a, b, c);
    if (Number.isFinite(distance)) least = Math.min(least, distance); // a triangle of no area (three vertices in a line) is met by its neighbours' edges
    const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const h = [d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]];
    const det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2];
    if (Math.abs(det) < 1e-12) continue;
    const s = [point[0] - a[0], point[1] - a[1], point[2] - a[2]];
    const u = (s[0] * h[0] + s[1] * h[1] + s[2] * h[2]) / det;
    if (u < 0 || u > 1) continue;
    const q = [s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]];
    const w = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) / det;
    if (w < 0 || u + w > 1) continue;
    if ((e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) / det > 0) crossings += 1;
  }
  return least <= near || crossings % 2 === 1;
}

/** Where a point stands against a measured body's ellipsoid: at most 1 inside it (the sum over its axes of the squared offset over the half-width). */
const withinEllipsoid = (point, body) => body.axes.reduce((sum, axis, n) => sum + ((point.reduce((d, x, k) => d + (x - body.centre_nm[k]) * axis[k], 0)) / (body.across_nm[n] / 2)) ** 2, 0);

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

test("a ribosome's subunits: each one solid of all its residues, the two meeting at one shared face, each in two tones inside it or on it; a sliver dropped with its tones", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    const file = path.join(folder, "made.cif");
    writeFileSync(file, madeEntry([
      { chain: "A", entity: 1, at: [0, 0, 0], side: 5, nucleic: true },
      { chain: "B", entity: 2, at: [30, 0, 0], side: 4 },
      { chain: "C", entity: 3, at: [0, 25, 0], side: 4, nucleic: true },
      { chain: "D", entity: 4, at: [30, 25, 0], side: 4 },
      // Far from the rest, a little more of the large subunit's RNA: at the whole's level its piece holds under 5% of the subunit.
      { chain: "A", entity: 1, at: [-90, 0, 0], side: 4, nucleic: true, from: 125 },
    ], [["1", "23S ribosomal RNA"], ["2", "50S ribosomal protein L2"], ["3", "16S ribosomal RNA"], ["4", "30S ribosomal protein S2"]]));
    const done = run(file, "--ribosome");
    assert.equal(done.status, 0, done.stderr);
    const shape = JSON.parse(done.stdout);
    assert.equal(shape.parameters.width_nm, 1.6);
    assert.match(shape.definition, /^each part as one solid: the closed surface that holds its residues' own volume .* protein and nucleic acid together, .* weighted by its volume/);
    assert.deepEqual(shape.meshes.map((mesh) => [mesh.id, mesh.part, mesh.kind, mesh.residues]), [["part-large", "large", "nucleoprotein", 253], ["part-small", "small", "nucleoprotein", 128]]);
    assert.deepEqual(shape.tones.map((tone) => [tone.id, tone.within, tone.kind, tone.residues]), [["part-large-nucleic", "part-large", "nucleic", 189], ["part-large-protein", "part-large", "protein", 64], ["part-small-nucleic", "part-small", "nucleic", 64], ["part-small-protein", "part-small", "protein", 64]]);
    assert.deepEqual([shape.counts.tones.meshes, shape.counts.tones.triangles], [4, shape.tones.reduce((sum, tone) => sum + tone.triangles.length / 3, 0)]);
    // The far piece is dropped from the large subunit, and listed; its tones' pieces with it (the tones below still fill the solid).
    assert.equal(shape.dropped.length, 1);
    assert.deepEqual([shape.dropped[0].surface, shape.dropped[0].pieces, shape.dropped[0].chains], ["part-large", 1, ["A"]]);
    assert.ok(shape.dropped[0].residues_within > 0);
    const far = (mesh) => Math.min(...mesh.vertices.filter((_, n) => n % 3 === 0)) * shape.unit_nm;
    assert.ok([...shape.meshes, ...shape.tones].every((mesh) => far(mesh) > far(shape.meshes[0]) - 0.001), "nothing is drawn of the far piece");
    // The two solids hold the whole's own volume between them, with what was dropped (each is the share of the whole where its cloud is the greater).
    const wanted = (189 + 64) * VOLUME.nucleic + (64 + 64) * VOLUME.protein;
    const solids = shape.meshes.map((mesh) => checked(mesh, shape.unit_nm));
    assert.ok(solids.every((one) => one.closed && one.volume > 0), "closed and facing out");
    const whole = solids.reduce((sum, one) => sum + one.volume, 0) + shape.dropped[0].volume_nm3;
    assert.ok(Math.abs(whole / wanted - 1) < 0.02, `the two hold ${whole.toFixed(2)} of ${wanted.toFixed(2)} nm³`);
    // They meet at one shared face: the vertices of the faces each has inside (after its outer ones) are the same places.
    const inner = (mesh) => new Set(mesh.triangles.slice(3 * mesh.outer).map((n) => mesh.vertices.slice(3 * n, 3 * n + 3).join(",")));
    const [large, small] = shape.meshes.map(inner);
    assert.ok(large.size > 0 && large.size === small.size && [...large].every((key) => small.has(key)), `the subunits share ${large.size} vertices of their faces between them`);
    // The tones: closed, filling their part (their volumes sum to it), and every vertex of theirs inside the part or on it.
    for (const mesh of shape.meshes) {
      const tones = shape.tones.filter((tone) => tone.within === mesh.id).map((tone) => [tone, checked(tone, shape.unit_nm)]);
      assert.ok(tones.every(([, one]) => one.closed && one.volume > 0), `${mesh.id}: its tones closed and facing out`);
      const filled = tones.reduce((sum, [, one]) => sum + one.volume, 0), solid = checked(mesh, shape.unit_nm).volume;
      assert.ok(Math.abs(filled / solid - 1) < 0.005, `${mesh.id}: its tones hold ${filled.toFixed(3)} of its ${solid.toFixed(3)} nm³`);
      for (const [tone] of tones) {
        for (let n = 0; n < tone.vertices.length / 3; n++) {
          const point = tone.vertices.slice(3 * n, 3 * n + 3).map((x) => x * shape.unit_nm);
          assert.ok(insideOrOn(point, mesh, shape.unit_nm), `${tone.id}: its vertex ${n} lies inside ${mesh.id} or on it`);
        }
      }
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("a surface's slivers: its largest piece and every piece of at least 5% of its volume kept, smaller ones dropped and listed", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  try {
    const file = path.join(folder, "made.cif");
    // One chain: a block of 343 residues, and 6 nm away a block of 64 whose surface, at the chain's level, holds under 5% of its volume.
    writeFileSync(file, madeEntry([{ chain: "A", entity: 1, at: [0, 0, 0], side: 7 }, { chain: "A", entity: 1, at: [60, 0, 0], side: 4, from: 343 }], [["1", "Motor"]]));
    const done = run(file);
    assert.equal(done.status, 0, done.stderr);
    const shape = JSON.parse(done.stdout);
    assert.equal(shape.parameters.piece_share, 0.05);
    assert.equal(shape.dropped.length, 1);
    const [lost] = shape.dropped;
    assert.deepEqual([lost.surface, lost.pieces, lost.residues_within, lost.chains], ["chain-A", 1, 64, ["A"]]);
    assert.equal(lost.residues_volume, Math.round((lost.volume_nm3 / VOLUME.protein) * 10) / 10);
    const kept = checked(shape.meshes[0], shape.unit_nm);
    assert.ok(kept.closed && kept.volume > 0);
    assert.ok(lost.volume_nm3 < 0.05 * (kept.volume + lost.volume_nm3), `${lost.volume_nm3} nm³ dropped of ${kept.volume.toFixed(2)}`);
    // What is kept and what was dropped hold the chain's own volume between them.
    assert.ok(Math.abs((kept.volume + lost.volume_nm3) / (407 * VOLUME.protein) - 1) < 0.02, `${kept.volume.toFixed(2)} and ${lost.volume_nm3} nm³`);
    // All of what is drawn lies round the large block: x within its reach (the made-up frame's origin is the whole's middle).
    const xs = shape.meshes[0].vertices.filter((_, n) => n % 3 === 0).map((x) => x * shape.unit_nm);
    assert.ok(Math.max(...xs) - Math.min(...xs) < 2.3 + 2 * 3 * shape.parameters.width_nm, "the far block is not drawn");
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the tool refuses, and writes nothing, where a part names no atom, a frame's part is not given, the budget would break, or a measure is not this entry's", () => {
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
    assert.match(done.stderr, /triangles drawn, above the budget of 10; nothing is made/);
    done = run(file, "--most-bytes", "100", "--out", out);
    assert.match(done.stderr, /bytes, above the budget of 100; nothing is made/);
    // A measure's call is taken whole, from a measure of this entry.
    const measure = path.join(folder, "measure.json");
    writeFileSync(measure, JSON.stringify({ frame: "origin at the centre of the whole's atoms; its own axes", measured: { OTHER: { entry: "OTHER" } } }));
    done = run(file, "--measure", measure, "--part", "head=1", "--out", out);
    assert.match(done.stderr, /--measure gives the parts, the frame and what is left out: give none of them besides/);
    done = run(file, "--measure", measure, "--out", out);
    assert.match(done.stderr, /measure\.json holds no measure of made; nothing is made/);
    assert.equal(existsSync(out), false);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("every shape file holds to the contract and sits where its measure's bodies sit", () => {
  const names = readdirSync(SHAPES).filter((name) => name.endsWith(".json")).sort();
  assert.deepEqual(names, Object.keys(CALLS).sort(), "a shape file for each measure the catalogue draws, and no other");
  for (const name of names) {
    const file = path.join(SHAPES, name), shape = JSON.parse(readFileSync(file, "utf8"));
    const records = Object.entries(JSON.parse(readFileSync(path.join(ROOT, CALLS[name][1]), "utf8")).measured);
    const measured = (records.find(([key]) => key === (shape.assembly ? `${shape.entry}-assembly${shape.assembly}` : shape.entry)) || records[0])[1];
    // The budget: a file at most 250,000 bytes; one chosen machine at most 12,000 triangles drawn either way (its meshes,
    // or its meshes with each part's tones in its solid's place); a chain's surface up to about 3,000.
    const tones = shape.tones || [];
    const toned = new Set(tones.map((tone) => tone.within));
    const drawnToned = [...shape.meshes.filter((mesh) => !toned.has(mesh.id)), ...tones].reduce((sum, mesh) => sum + mesh.triangles.length / 3, 0);
    assert.ok(statSync(file).size <= 250000, `${name}: ${statSync(file).size} bytes`);
    assert.ok(shape.counts.triangles <= 12000 && drawnToned <= 12000, `${name}: ${shape.counts.triangles} and ${drawnToned} triangles drawn`);
    // A change from the standard setting is stated explicitly.
    const setting = shape.parameters.by === "parts" ? 1.6 : 1.0;
    assert.equal(shape.parameters.width_nm, (CALLS[name][2] || setting), `${name}: its width`);
    if (shape.parameters.width_nm !== setting) {
      const description = shape.parameters.width_nm < setting ? `finer than the standard ${setting} nm setting` : `coarser than the setting's ${setting} nm, to hold the budget`;
      assert.equal(shape.parameters.setting_width_nm, setting);
      assert.ok(shape.definition.includes(description), `${name}: states the change of width`);
    }
    assert.equal(shape.format, "cells.visualizer.machine-shape@1");
    assert.equal(shape.tool, "tools/shape_particle.py");
    assert.equal(shape.entry, measured.entry, name);
    assert.match(shape.illustration, /the viewer's own surface of the entry's coordinates, an illustration/i);
    assert.match(shape.frame, /^the measuring tool's/);
    assert.equal(shape.counts.meshes, shape.meshes.length);
    assert.equal(shape.counts.triangles, shape.meshes.reduce((sum, mesh) => sum + mesh.triangles.length / 3, 0));
    if (tones.length) assert.deepEqual(shape.counts.tones, { meshes: tones.length, vertices: tones.reduce((sum, tone) => sum + tone.vertices.length / 3, 0), triangles: tones.reduce((sum, tone) => sum + tone.triangles.length / 3, 0) });
    // What was dropped: slivers of surfaces in the file, each with the chains it came from.
    const lost = new Map();
    for (const item of shape.dropped) {
      assert.ok(shape.meshes.some((mesh) => mesh.id === item.surface) && item.pieces > 0 && item.volume_nm3 >= 0 && item.chains.length > 0, `${name}: ${JSON.stringify(item)}`);
      lost.set(item.surface, item.volume_nm3);
    }
    const parts = measured.parts ? Object.keys(measured.parts) : ["large", "small"];
    const chains = new Map((measured.chains || []).map((chain) => [chain.chain, chain]));
    const byPart = new Map(); // a part's surfaces (protein and nucleic acid): their volume and its middle, to set against the part's ellipsoid
    for (const mesh of shape.meshes) {
      const { closed, volume, triangles } = checked(mesh, shape.unit_nm);
      assert.ok(closed && volume > 0, `${name} ${mesh.id}: closed and facing out`);
      // A chain's surface holds its own volume, with what was dropped of it; a part's solid holds its share of the whole's (below).
      if (mesh.kind !== "nucleoprotein") assert.ok(Math.abs((volume + (lost.get(mesh.id) || 0)) / (mesh.residues * VOLUME[mesh.kind]) - 1) < 0.02, `${name} ${mesh.id}: holds ${volume.toFixed(1)} nm³`);
      assert.ok(!mesh.chain || triangles <= 3000, `${name} ${mesh.id}: ${triangles} triangles, a chain's surface`);
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
        // inside it (one atom stands for each residue here, and a thin chain's volume gathers where its residues pack).
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
        const inside = withinEllipsoid(middle.map((x) => x / held), body);
        assert.ok(inside <= 1, `${name} ${mesh.id}: its middle at ${inside.toFixed(2)} of its ellipsoid's reach`);
      }
    }
    // A machine drawn by its parts: the parts' solids hold the whole's own volume between them, neighbours meet at one
    // shared face, and each part's two tones are closed, fill it, and lie inside it or on it.
    const solids = shape.meshes.filter((mesh) => mesh.kind === "nucleoprotein");
    if (solids.length) {
      const wanted = tones.reduce((sum, tone) => sum + tone.residues * VOLUME[tone.kind], 0);
      const held = solids.reduce((sum, mesh) => sum + checked(mesh, shape.unit_nm).volume + (lost.get(mesh.id) || 0), 0);
      assert.ok(Math.abs(held / wanted - 1) < 0.02, `${name}: its parts hold ${held.toFixed(1)} of ${wanted.toFixed(1)} nm³`);
      const inner = (mesh) => new Set(mesh.triangles.slice(3 * mesh.outer).map((n) => mesh.vertices.slice(3 * n, 3 * n + 3).join(",")));
      if (solids.length === 2) {
        // Where a sliver of one part was dropped against the other, the other keeps the few faces it had against it.
        const [one, two] = solids.map(inner);
        const shared = [...one].filter((key) => two.has(key)).length;
        const exact = !solids.some((mesh) => lost.has(mesh.id));
        assert.ok(shared > 0 && (exact ? shared === one.size && shared === two.size : shared >= 0.95 * Math.max(one.size, two.size)), `${name}: the two parts meet at one shared face (${shared} of ${one.size} and ${two.size} vertices)`);
      }
      for (const mesh of solids) {
        const own = tones.filter((tone) => tone.within === mesh.id);
        assert.equal(own.length, 2, `${name} ${mesh.id}: two tones`);
        const filled = own.reduce((sum, tone) => {
          const one = checked(tone, shape.unit_nm);
          assert.ok(one.closed && one.volume > 0, `${name} ${tone.id}: closed and facing out`);
          return sum + one.volume;
        }, 0);
        assert.ok(Math.abs(filled / checked(mesh, shape.unit_nm).volume - 1) < 0.005, `${name} ${mesh.id}: its tones fill it`);
        const places = new Set(Array.from({ length: mesh.vertices.length / 3 }, (_, n) => mesh.vertices.slice(3 * n, 3 * n + 3).join(",")));
        for (const tone of own) {
          for (let n = 0; n < tone.vertices.length / 3; n++) {
            const key = tone.vertices.slice(3 * n, 3 * n + 3);
            if (places.has(key.join(","))) continue;
            assert.ok(insideOrOn(key.map((x) => x * shape.unit_nm), mesh, shape.unit_nm), `${name} ${tone.id}: vertex ${n} inside ${mesh.id} or on it`);
          }
        }
      }
    }
    // A part drawn by its surfaces (a ribosome's subunit) sits on its ellipsoid as a chain does.
    for (const [part, { held, middle }] of byPart) {
      const body = measured.parts?.[part] || measured[part];
      const inside = withinEllipsoid(middle.map((x) => x / held), body);
      assert.ok(inside <= 1, `${name} ${part}: its middle at ${inside.toFixed(2)} of its ellipsoid's reach`);
    }
  }
});

const DATASETS = process.env.CELLS_DATASETS || "/mnt/datasets/Cells";
test("each shape file is the tool's shape of its entry, made again byte for byte by the contract's call", async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs, every entry here; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: Object.values(CALLS).map(([saved]) => path.join(DATASETS, path.dirname(saved))), files: Object.values(CALLS).map(([saved]) => path.join(DATASETS, saved)), env: ["CELLS_DATASETS"] })) return;
  const folder = mkdtempSync(path.join(tmpdir(), "shape-"));
  // Two at a time: the largest takes about 13 s and 650 MB.
  const remake = ([name, [saved, measure, width, ...more]]) =>
    new Promise((resolve) => {
      const out = path.join(folder, name);
      const options = [path.join(DATASETS, saved), "--measure", path.join(ROOT, measure), ...(width ? ["--width", String(width)] : []), ...more, "--out", out];
      execFile("python3", ["-I", TOOL, ...options], { encoding: "utf8" }, (error, _, stderr) => resolve({ name, error, stderr, out }));
    });
  try {
    const waiting = Object.entries(CALLS).filter(([, [saved]]) => existsSync(path.join(DATASETS, saved)));
    const missing = Object.keys(CALLS).length - waiting.length;
    if (missing) console.log(`# ${missing} entries are not on this machine; their files are not made again`);
    const done = [];
    while (waiting.length) done.push(...(await Promise.all(waiting.splice(0, 2).map(remake))));
    for (const { name, error, stderr, out } of done) {
      assert.equal(error, null, `${name}: ${stderr}`);
      assert.ok(readFileSync(out).equals(readFileSync(path.join(SHAPES, name))), `${name} is made again byte for byte`);
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
