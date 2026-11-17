// The viewer's own measure of a ribosome, or any machine, from a Protein Data Bank entry
// (tools/measure_particle.py): what it measures on small made-up files whose answers are known
// (two subunits, a eukaryote's names; a machine's whole, named parts, chains, frame, entities and
// a biological assembly's file), what it refuses, and that the record the bacteria are drawn from
// (data/measures/ecoli.ribosome.json) is what the tool gives from the two entries saved with the
// downloads.
//
//   node --test tests/measure_particle.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "measure_particle.py");
const RECORD = path.join(ROOT, "data", "measures", "ecoli.ribosome.json");
const ENTRIES = process.env.ECOLI_RIBOSOME || "/mnt/datasets/Cells/ecoli/wwpdb-ribosome";

/** A made-up mmCIF file: a large and a small subunit, each six atoms on its own axes, a messenger beside them, and rows the tool must pass over. */
function madeUp(large = "23S ribosomal RNA", small = "16S ribosomal RNA") {
  const atoms = [];
  const add = (group, entity, [x, y, z], model = 1) => atoms.push(`${group} ${atoms.length + 1} C CA . ALA A ${entity} 1 ? ${x.toFixed(3)} ${y.toFixed(3)} ${z.toFixed(3)} 1.0 0.0 ${model}`);
  // The large subunit round the origin: 60, 40 and 20 Å from end to end along x, z and y.
  for (const [x, y, z] of [[30, 0, 0], [-30, 0, 0], [0, 10, 0], [0, -10, 0], [0, 0, 20], [0, 0, -20]]) add("ATOM", 1, [x, y, z]);
  // The small subunit 100 Å up: 80, 30 and 10 Å along x, z and y.
  for (const [x, y, z] of [[40, 100, 0], [-40, 100, 0], [0, 105, 0], [0, 95, 0], [0, 100, 15], [0, 100, -15]]) add("ATOM", 2, [x, y, z]);
  add("ATOM", 3, [500, 500, 500]); // the messenger: reported, left out
  add("HETATM", 1, [900, 0, 0]); // a ligand: not a polymer atom
  add("ATOM", 1, [-900, 0, 0], 2); // a second model: passed over
  return [
    "data_MADE",
    "#",
    "_struct.title 'A made-up particle'",
    "_exptl.method 'ELECTRON MICROSCOPY'",
    "#",
    "loop_",
    "_entity.id",
    "_entity.pdbx_description",
    `1 '${large}'`,
    `2 '${small}'`,
    "3 mRNA",
    "#",
    "loop_",
    ...["group_PDB", "id", "type_symbol", "label_atom_id", "label_alt_id", "label_comp_id", "label_asym_id", "label_entity_id", "label_seq_id", "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z", "occupancy", "B_iso_or_equiv", "pdbx_PDB_model_num"].map((name) => `_atom_site.${name}`),
    ...atoms,
    "#",
    "",
  ].join("\n");
}

const run = (...args) => spawnSync("python3", ["-I", TOOL, ...args], { encoding: "utf8" });
const COLUMNS = ["group_PDB", "id", "type_symbol", "label_atom_id", "label_alt_id", "label_comp_id", "label_asym_id", "label_entity_id", "label_seq_id", "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z", "occupancy", "B_iso_or_equiv", "auth_asym_id", "pdbx_PDB_model_num"];
const AROUND = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
/**
 * A made-up machine: chains, each six atoms round its middle (`size` Å out along x, y and z), two atoms to a residue;
 * `sequences` the entity's length in `_entity_poly_seq`. Rows the tool must pass over beside them: a ligand, a second model,
 * an atom's second place.
 */
function madeMachine(entities, chains, sequences) {
  const atoms = [];
  for (const { chain, entity, at, size } of chains) {
    AROUND.forEach(([x, y, z], k) => atoms.push(["ATOM", atoms.length + 1, "C", "CA", ".", "ALA", chain, entity, 1 + Math.floor(k / 2), "?", at[0] + x * size[0], at[1] + y * size[1], at[2] + z * size[2], 1, 0, chain, 1].join(" ")));
  }
  atoms.push(["HETATM", atoms.length + 1, "C", "C1", ".", "LIG", "Z", 9, ".", "?", 900, 0, 0, 1, 0, "Z", 1].join(" "));
  atoms.push(["ATOM", atoms.length + 1, "C", "CA", ".", "ALA", chains[0].chain, chains[0].entity, 1, "?", -900, 0, 0, 1, 0, chains[0].chain, 2].join(" "));
  atoms.push(["ATOM", atoms.length + 1, "C", "CA", "B", "ALA", chains[0].chain, chains[0].entity, 1, "?", 0, 900, 0, 1, 0, chains[0].chain, 1].join(" "));
  return [
    "data_MADE", "#", "_struct.title 'A made-up machine'", "_exptl.method 'X-RAY DIFFRACTION'", "_refine.ls_d_res_high 2.5", "#",
    "loop_", "_entity.id", "_entity.type", "_entity.pdbx_description", ...entities.map(([id, description]) => `${id} polymer '${description}'`), "#",
    "loop_", "_entity_poly_seq.entity_id", "_entity_poly_seq.num", "_entity_poly_seq.mon_id", ...Object.entries(sequences).flatMap(([id, length]) => Array.from({ length }, (_, k) => `${id} ${k + 1} ALA`)), "#",
    "loop_", ...COLUMNS.map((name) => `_atom_site.${name}`), ...atoms, "#", "",
  ].join("\n");
}
const across = (half) => Math.round(((2 * Math.sqrt((5 * half * half) / 3)) / 10) * 10) / 10; // six atoms at ±half Å: the ellipsoid of the same spread, in nm

test("the tool measures each subunit as the ellipsoid of the same spread, and how the small one lies on the large one", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made.cif");
    writeFileSync(file, madeUp());
    const done = run(file);
    assert.equal(done.status, 0, done.stderr);
    const measured = JSON.parse(done.stdout).measured.MADE;
    // Six atoms at ±a along an axis have a variance of a²/3 there: the half-width is the square root of five times that.
    const across = (a) => Math.round((2 * Math.sqrt((5 * a * a) / 3)) / 10 * 10) / 10;
    assert.deepEqual(measured.large.across_nm, [across(30), across(20), across(10)]);
    assert.deepEqual(measured.small.across_nm, [across(40), across(15), across(5)]);
    assert.deepEqual(measured.large.farthest_nm, [6, 4, 2]);
    assert.equal(measured.between_centres_nm, 10);
    // In the particle's own frame the large subunit is below its middle and the small one above, on y.
    assert.deepEqual(measured.large.centre_nm, [0, -5, 0]);
    assert.deepEqual(measured.small.centre_nm, [0, 5, 0]);
    // Each subunit's own axes, in that frame: its longest along x, then z, then y; right-handed, never mirrored.
    for (const part of [measured.large, measured.small]) {
      const [a, b, c] = part.axes;
      const det = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]);
      assert.ok(Math.abs(det - 1) < 1e-3, `right-handed: ${det}`);
      assert.ok(Math.abs(Math.abs(a[0]) - 1) < 1e-3 && Math.abs(Math.abs(b[2]) - 1) < 1e-3, JSON.stringify(part.axes));
    }
    assert.deepEqual(measured.left_out, ["mRNA"], "what is in neither subunit is reported and left out");
    assert.equal(measured.large.atoms + measured.small.atoms, 12, "only model 1's polymer atoms are read");
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the tool refuses a file with no atoms, and writes nothing", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "empty.cif"), out = path.join(folder, "out.json");
    writeFileSync(file, "data_EMPTY\n#\nloop_\n_entity.id\n_entity.pdbx_description\n1 '23S ribosomal RNA'\n#\n");
    const done = run(file, "--out", out);
    assert.notEqual(done.status, 0);
    assert.match(done.stderr, /no atoms of a large subunit were found; nothing is measured/);
    assert.equal(existsSync(out), false);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("a eukaryote's ribosome is named too: its 28S and 18S make the two subunits", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made.cif");
    writeFileSync(file, madeUp("28S ribosomal RNA", "18S ribosomal RNA"));
    const done = run(file);
    assert.equal(done.status, 0, done.stderr);
    assert.equal(JSON.parse(done.stdout).measured.MADE.between_centres_nm, 10);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("any machine: the whole but for what is left out, named parts, each chain, a frame from one part to another, and how whole each entity is", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made.cif");
    // Two copies of a motor protein, 100 Å apart on y, a rotor between them, and a strand of DNA to leave out.
    writeFileSync(file, madeMachine([["1", "Motor protein"], ["2", "Rotor"], ["3", "DNA"]], [
      { chain: "A", entity: 1, at: [0, 0, 0], size: [30, 10, 20] },
      { chain: "B", entity: 1, at: [0, 100, 0], size: [30, 10, 20] },
      { chain: "C", entity: 2, at: [0, 50, 0], size: [30, 10, 20] },
      { chain: "D", entity: 3, at: [500, 500, 500], size: [1, 1, 1] },
    ], { 1: 4, 2: 3, 3: 3 }));
    const out = path.join(folder, "out.json");
    const done = run("--machine", file, "--exclude", "3", "--part", "motor=1", "--part", "rotor=2", "--part", "low=chains:A", "--part", "high=chains:B", "--frame-from", "low", "--frame-to", "high", "--out", out);
    assert.equal(done.status, 0, done.stderr);
    const record = JSON.parse(readFileSync(out, "utf8"));
    assert.equal(record.format, "cells.visualizer.machine-measure@1");
    assert.match(record.frame, /y from the part low's centre to the part high's/);
    const measured = record.measured.MADE;
    assert.deepEqual(measured.left_out, [{ entity: "3", description: "DNA" }]);
    assert.equal(measured.whole.atoms, 18, "model 1's polymer atoms, one place each, the DNA left out");
    assert.deepEqual(measured.frame, { from: "low", to: "high", between_centres_nm: 10 });
    // Parts by entity and by chain, in the frame: y from the low part's middle to the high one's, x the whole's longest axis square to it.
    assert.deepEqual(measured.parts.low.centre_nm, [0, -5, 0]);
    assert.deepEqual(measured.parts.high.centre_nm, [0, 5, 0]);
    assert.deepEqual(measured.parts.rotor.centre_nm, [0, 0, 0]);
    assert.deepEqual([measured.parts.motor.by, measured.parts.motor.ids, measured.parts.low.by, measured.parts.low.ids], ["entities", ["1"], "chains", ["A"]]);
    assert.deepEqual(measured.parts.low.across_nm, [across(30), across(20), across(10)]);
    assert.deepEqual(measured.parts.low.farthest_nm, [6, 4, 2]);
    assert.deepEqual(measured.parts.low.axes, [[1, 0, 0], [0, 0, 1], [0, -1, 0]], "its own axes, longest first, in the frame, right-handed");
    assert.equal(measured.parts.motor.atoms, 12);
    // Each chain's own body.
    assert.deepEqual(measured.chains.map((chain) => [chain.chain, chain.entity, chain.description, chain.atoms]), [["A", "1", "Motor protein", 6], ["B", "1", "Motor protein", 6], ["C", "2", "Rotor", 6]]);
    assert.deepEqual(measured.chains[2].across_nm, [across(30), across(20), across(10)]);
    // How whole each entity is: copies, residues modelled against the sequence, atoms to a residue.
    assert.deepEqual(measured.entities, [
      { entity: "1", description: "Motor protein", copies: 2, sequence_length: 4, residues_modelled_per_copy: 3, modelled_share: 0.75, atoms_per_modelled_residue: 2 },
      { entity: "2", description: "Rotor", copies: 1, sequence_length: 3, residues_modelled_per_copy: 3, modelled_share: 1, atoms_per_modelled_residue: 2 },
    ]);
    // Without a frame, the whole's own axes.
    const plain = JSON.parse(run("--machine", file, "--exclude", "3").stdout);
    assert.match(plain.frame, /its own axes, longest first/);
    assert.equal(plain.measured.MADE.frame, undefined);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("a biological assembly's file is the machine: its id and assembly named, its copies counted as the chains it holds", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made-assembly1.cif");
    writeFileSync(file, madeMachine([["1", "Protease"]], [
      { chain: "A", entity: 1, at: [0, 0, 0], size: [30, 10, 20] },
      { chain: "A-2", entity: 1, at: [0, 0, 80], size: [30, 10, 20] },
    ], { 1: 3 }));
    const done = run("--machine", file);
    assert.equal(done.status, 0, done.stderr);
    const measured = JSON.parse(done.stdout).measured["MADE-assembly1"];
    assert.deepEqual([measured.entry, measured.assembly, measured.entities[0].copies, measured.chains.map((chain) => chain.chain)], ["MADE", "1", 2, ["A", "A-2"]]);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the machine mode refuses, and writes nothing, where a part names no atom or a frame's part is not given", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made.cif"), out = path.join(folder, "out.json");
    writeFileSync(file, madeMachine([["1", "Motor protein"]], [{ chain: "A", entity: 1, at: [0, 0, 0], size: [30, 10, 20] }], { 1: 3 }));
    let done = run("--machine", file, "--part", "nothing=7", "--out", out);
    assert.notEqual(done.status, 0);
    assert.match(done.stderr, /the part nothing \(entities 7\) names no atom; nothing is measured/);
    done = run("--machine", file, "--part", "head=1", "--frame-from", "head", "--frame-to", "ring", "--out", out);
    assert.notEqual(done.status, 0);
    assert.match(done.stderr, /the frame's part ring is not given with --part; nothing is measured/);
    done = run(file, "--part", "head=1", "--out", out);
    assert.notEqual(done.status, 0, "a part is for the machine mode");
    assert.equal(existsSync(out), false);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the two-subunit mode takes an entity the caller names for a subunit (by its id), whatever its description, and says how it placed each chain", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const file = path.join(folder, "made.cif");
    // The messenger's place taken by a small-subunit protein whose name says neither subunit (as RACK1's does).
    writeFileSync(file, madeUp().replace("3 mRNA", "3 'Receptor of activated protein C kinase 1'"));
    let done = run(file);
    assert.equal(done.status, 0, done.stderr);
    assert.deepEqual(JSON.parse(done.stdout).measured.MADE.left_out, ["Receptor of activated protein C kinase 1"]);
    assert.match(done.stderr, /chain A \(entity 3, Receptor of activated protein C kinase 1\): left out/);
    done = run(file, "--small", "3");
    assert.equal(done.status, 0, done.stderr);
    const measured = JSON.parse(done.stdout).measured.MADE;
    assert.deepEqual([measured.left_out, measured.placed_by_the_caller, measured.small.atoms], [[], { 3: { subunit: "small", description: "Receptor of activated protein C kinase 1" } }, 7]);
    assert.match(done.stderr, /\(entity 3, Receptor of activated protein C kinase 1\): small, by the caller/);
    assert.match(done.stderr, /\(entity 1, 23S ribosomal RNA\): large, by its description/);
    // Refused: an entity the entry does not hold, and one named for both subunits.
    assert.match(run(file, "--small", "9").stderr, /the entity 9 named for a subunit is not in the entry; nothing is measured/);
    assert.match(run(file, "--small", "3", "--large", "3").stderr, /the entity 3 is named for both subunits/);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the record the bacteria are drawn from is the tool's measure of the two entries saved with the downloads", { skip: !existsSync(path.join(ENTRIES, "7K00.cif.gz")) && "the entries are not on this machine" }, () => {
  const folder = mkdtempSync(path.join(tmpdir(), "particle-"));
  try {
    const out = path.join(folder, "record.json");
    const done = run(path.join(ENTRIES, "7K00.cif.gz"), path.join(ENTRIES, "5MDZ.cif.gz"), "--out", out);
    assert.equal(done.status, 0, done.stderr);
    assert.equal(readFileSync(out, "utf8"), readFileSync(RECORD, "utf8"));
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
