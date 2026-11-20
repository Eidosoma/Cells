// Thale cress in the viewer: its species file and outlines, its side of the protein atlas and
// its own proteins on a plant cell's shelves are held to their contracts and to what the note
// says of them. The catalogue is the whole reference proteome: one protein for each gene,
// reviewed or not. A plant cell has three shelves more than an animal cell: the plastid's
// envelope, the thylakoid membrane and the vacuole's membrane. Where the saved downloads are on
// this machine, the build tool must reproduce the six files byte for byte.
//
//   node --test tests/thalecress_atlas.test.mjs
//   THALECRESS_DATASETS=DATA node --test tests/thalecress_atlas.test.mjs    (DATA holds every species' downloads)

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { accessoryRoles } from "./helpers/atlas_products.mjs";

const ACCESSORY = accessoryRoles();

const TOOL = path.join(ROOT, "tools", "build_thalecress_atlas.py");
const FOLDER = path.join(ROOT, "data", "proteins", "thalecress");
const SPECIES = path.join(ROOT, "data", "species", "thalecress.json");
const SHAPES = path.join(ROOT, "data", "species", "shapes", "thalecress.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "thalecress.json");
const DATASETS = process.env.THALECRESS_DATASETS || "/mnt/datasets/Cells";
const SAVED = existsSync(path.join(DATASETS, "thalecress", "uniprot-thalecress-reference-proteome", "MANIFEST.json")) && existsSync(path.join(DATASETS, "human", "interpro-entries-tree-and-go", "MANIFEST.json"));
const SIDES = ["outside", "in", "inside", "not known"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const species = await json(SPECIES);
const shapes = await json(SHAPES);
const atlas = await json(ATLAS);
const shelvesText = await readFile(path.join(FOLDER, "shelves.json"), "utf8");
const shelves = JSON.parse(shelvesText);
const tableText = await readFile(path.join(FOLDER, "proteins.tsv"), "utf8");
const readme = await readFile(path.join(FOLDER, "README.md"), "utf8");
const note = await readFile(path.join(ROOT, "docs", "THALECRESS.md"), "utf8");
const snapshot = await json(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"));
const [head, ...tableLines] = tableText.replace(/\n$/, "").split("\n");
const columns = head.split("\t");
const table = tableLines.map((line) => Object.fromEntries(line.split("\t").map((value, index) => [columns[index], value])));
const byId = new Map(table.map((row) => [row.id, row]));
const named = (names, row) => Object.fromEntries(names.map((name, index) => [name, row[index]]));
const families = shelves.families.map((row) => named(shelves.family_columns, row));
const lone = shelves.lone.parts.map((row) => named(shelves.lone.part_columns, row));
const parts = shelves.no_family.parts.map((row) => named(shelves.no_family.part_columns, row));
const lines = [...families.map((line) => ["family", line]), ...lone.map((line) => ["lone", line]), ...parts.map((line) => ["part", line])];
const sum = (numbers) => numbers.reduce((total, number) => total + number, 0);
const count = (rows, test_) => rows.filter(test_).length;
const said = (n) => n.toLocaleString("en-US");

test("the species file says what it is: a plant whose cell is given as data, with placeholder outlines and no model", () => {
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "cell", "capability_sources", "sources"]);
  assert.deepEqual([species.format, species.id, species.label, species.organism, species.taxon, species.group, species.default], ["cells.visualizer.species@1", "thalecress", "Thale cress", "Arabidopsis thaliana", 3702, "Plants", false]);
  assert.equal(species.modelled.state, "generic");
  assert.match(species.modelled.text, /No plant cell is modelled, and the project's record names no model of this plant/);
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell", "tissue", "organ", "organism"]);
  const [, cell, , organ, organism] = species.levels;
  assert.deepEqual(cell.shape, { kind: "prism", sides: 4, across_um: 47, height_um: 45, corner_um: 4 });
  assert.deepEqual([organ.label, organ.shape, organism.shape], ["Leaf", { kind: "outline", ref: "thalecress", parts: ["leaf"], context: ["other leaves"] }, { kind: "outline", ref: "thalecress" }]);
  for (const level of [cell, organ, organism]) assert.match(level.note, /the picture's choice/);
  // A plant cell's parts, as data: a wall with its thickness, chloroplasts and a vacuole with their numbers, each from a permissive source.
  const parts = species.cell.parts;
  assert.deepEqual([parts.membranes, parts.wall, parts.wall_nm, parts.nucleus, parts.organelles], [1, true, 150, true, ["er", "golgi", "mitochondria", "chloroplasts", "vacuole"]]);
  assert.deepEqual(parts.organelle_sizes, { chloroplasts: { count: 100, volume_fl: 93, across_um: 5.6, sources: ["tolleter2024"] }, vacuole: { share: 0.84, sources: ["tolleter2024"] } });
  for (const item of Object.values(parts.organelle_sizes)) assert.ok(item.sources.every((key) => species.sources[key]?.class === "permissive"));
  for (const label of ["A leaf cell's size", "Chloroplasts", "Vacuole", "Wall", "Leaf and rosette", "What joins its cells"]) assert.ok(species.cell.facts.some((fact) => fact.label === label), label);
  for (const fact of species.cell.facts) assert.ok(fact.sources.every((key) => species.sources[key]?.class === "permissive"), fact.label);
  assert.deepEqual([species.cell.capabilities["cap.junctions"].place, species.cell.capabilities["cap.pumps"].place], ["absent", "present"]);
  assert.deepEqual([shapes.format, shapes.parts.map((part) => [part.name, part.group ?? null, part.kind])], ["cells.visualizer.outline@1", [["leaf", "leaf", "loft"], ["other leaves", null, "lines"]]]);
  assert.match(shapes.note, /the picture's choice/);
});

test("the catalogue is the whole reference proteome: one protein for each gene, reviewed or not, with its gene's further entries counted", () => {
  const from = shelves.from_counts;
  assert.deepEqual([from.entries, from.reviewed, from.unreviewed, from.genes, from.shown, from.shown_reviewed, from.shown_unreviewed, from.further], [39144, 16217, 22927, 27368, 27368, 16212, 11156, 11776]);
  assert.equal(table.length, from.shown);
  assert.equal(new Set(table.map((row) => row.id)).size, table.length);
  assert.deepEqual([count(table, (row) => row.reviewed === "1"), count(table, (row) => row.reviewed === "0")], [from.shown_reviewed, from.shown_unreviewed]);
  assert.ok(table.every((row) => Number(row.entries) >= 1) && sum(table.map((row) => Number(row.entries) - 1)) >= from.further_tied_to_a_shown_gene);
  assert.deepEqual([shelves.predicted, shelves.marks.reviewed.values, shelves.marks.entries.values], [false, [true, false], "number"]);
  // What stands behind each place, for curated and for automatic entries, adds up to the catalogue.
  const curated = shelves.curated.rows;
  assert.deepEqual([sum(curated.map((row) => row[1])), sum(curated.map((row) => row[2]))], [from.shown_reviewed, from.shown_unreviewed]);
  const kind = (row) => (row.basis === "p" ? "predicted from a segment or a signal" : row.basis === "n" ? "not known" : { e: "stated, on an experiment", s: "stated, by likeness", c: "stated, by a curator's inference", r: "stated, by a rule", n: "stated, with no evidence given" }[row.evidence]);
  for (const [what, reviewed, unreviewed] of curated) assert.deepEqual([count(table, (row) => row.reviewed === "1" && kind(row) === what), count(table, (row) => row.reviewed === "0" && kind(row) === what)], [reviewed, unreviewed], what);
  // No curator wrote an unreviewed entry: what it states is stated by a rule.
  assert.ok(table.every((row) => row.reviewed === "1" || row.basis !== "s" || row.evidence === "r"));
});

test("the shelves are a plant cell's nine; every protein is in exactly one line and the counts add up", () => {
  assert.deepEqual([shelves.format, shelves.species], ["cells.visualizer.species_proteins@1", "thalecress"]);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["cell", "er", "mito", "plastid", "thylakoid", "vacuole", "nucleus", "other", "membrane"]);
  assert.equal(sum(lines.map(([, line]) => line.count)), table.length);
  let cursor = 0;
  for (const [kind, line] of lines) {
    const rows = table.slice(cursor, cursor + line.count);
    cursor += line.count;
    assert.ok(rows.every((row) => row.shelf === (line.shelf ?? "") && (kind === "lone" ? row.family : row.under === line.id)), `${line.id} on ${line.shelf}`);
    assert.deepEqual(Object.fromEntries(SIDES.map((side) => [side, count(rows, (row) => row.side === side)]).filter(([, n]) => n)), line.sides, `${line.id} on ${line.shelf}`);
  }
  const totals = new Map();
  for (const line of families) totals.set(line.id, (totals.get(line.id) || 0) + line.count);
  for (const line of families) assert.equal(line.total, totals.get(line.id), line.id);
  assert.deepEqual([shelves.distinct_families, shelves.family_lines, shelves.families_in_all, shelves.lone.count], [totals.size, families.length, totals.size + shelves.lone.families, sum(lone.map((line) => line.count))]);
  for (const side of SIDES) assert.equal(shelves.counts[side], count(table, (row) => row.side === side), side);
  for (const [shelf, counts] of Object.entries(shelves.shelf_counts)) for (const side of SIDES) assert.equal(counts[side], count(table, (row) => row.shelf === (shelf === "no shelf" ? "" : shelf) && row.side === side), `${shelf}, ${side}`);
  assert.ok(table.every((row) => (row.side === "not known") === (row.basis === "n") && (row.shelf !== "" || row.side === "not known")));
  assert.equal(sum(shelves.placed_by.map((item) => item.proteins)), table.length);
  // What a plant cell adds is counted apart, and the counts are the table's.
  const on = (shelf, side) => count(table, (row) => row.shelf === shelf && row.side === side);
  const first = (code) => count(table, (row) => row.place === code || row.place.startsWith(`${code}.`));
  assert.deepEqual(Object.values(shelves.plant.counts).slice(0, 12), ["plastid", "thylakoid", "vacuole"].flatMap((shelf) => ["in", "inside", "outside", "not known"].map((side) => on(shelf, side))));
  const codeOf = (ending) => shelves.places.find((row) => row[1].endsWith(ending))[0].slice(3);
  assert.deepEqual(Object.values(shelves.plant.counts).slice(12, 14), [first(codeOf("cell wall")), first(codeOf("apoplast"))]);
  // Known proteins stand where the rule puts them: in the thylakoid's lumen, in its membrane, in the envelope, in the vacuole's membrane.
  const at = (gene, id) => { const row = table.find((item) => item.gene === gene && (!id || item.id === id)); return [row.shelf, row.side]; };
  assert.deepEqual([at("PSBO1"), at("LHCB1.1"), at("TIC110"), at("TPK1", "Q8LBL1"), at("AHA1")], [["thylakoid", "inside"], ["thylakoid", "in"], ["plastid", "in"], ["vacuole", "in"], ["cell", "in"]]);
});

test("the atlas holds found to a family that makes the machine itself, and its products are the proteins that name the units", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  const findings = Object.values(atlas.units).map((unit) => unit.finding);
  assert.deepEqual(["found", "different family", "none found", "nothing to look for"].map((word) => count(findings, (f) => f === word)), [5, 0, 38, 6]);
  for (const [id, unit] of Object.entries(atlas.units)) {
    assert.equal(unit.products.length > 0, unit.finding === "found", id);
    for (const product of unit.products) {
      const row = byId.get(product.ids[0].id);
      assert.ok(row && row.units.split(";").includes(id), `${id}: ${product.gene}`);
      // Two facts, apart: its record is its entry's, from the table; how it was found is its family's part in the machine, never its entry's.
      assert.equal(product.entry, row.reviewed === "1" ? "reviewed" : "unreviewed", `${id}: ${product.gene}`);
      assert.equal(product.found_by, ACCESSORY.has(product.role) ? "accessory signature" : "family signature", `${id}: ${product.gene}`);
      assert.ok(!("evidence" in product), `${id}: ${product.gene} carries the older word`);
    }
  }
  for (const row of table) for (const id of row.units ? row.units.split(";") : []) assert.ok(atlas.units[id].products.some((product) => product.ids[0].id === row.id), `${row.gene}: ${id}`);
  assert.deepEqual(Object.keys(atlas.units).filter((id) => atlas.units[id].finding === "found"), ["U40", "U41", "U44", "U45", "U47"]);
  // No gap junction and no sodium-potassium pump: the notes say what joins a plant's cells.
  for (const id of ["U36", "U37", "U38"]) assert.match(atlas.units[id].note, /joined in another way: by plasmodesmata/);
  assert.equal(atlas.units.U39.finding, "none found");
  for (const source of atlas.sources) assert.equal(source.class, "permissive", source.name);
  assert.ok(!MACHINE.test(JSON.stringify(atlas)));
});

test("every source states its terms and its class; the tools behind UniProt's statements are named, read through UniProt and counted", () => {
  assert.deepEqual(shelves.sources.map((source) => [source.name, source.class, source.through ?? null]), [
    ["UniProt", "permissive", null], ["InterPro", "permissive", null], ["Gene Ontology", "permissive", null],
    ["PROSITE", "non-commercial", "UniProt"], ["HAMAP", "permissive", "UniProt"], ["TMHMM", "non-commercial", "UniProt"], ["Phobius", "non-commercial", "UniProt"],
    ["SignalP", "non-commercial", "UniProt"], ["TargetP", "non-commercial", "UniProt"], ["Memsat", "no stated terms", "UniProt"], ["Predotar", "no stated terms", "UniProt"], ["big-PI", "no stated terms", "UniProt"],
  ]);
  for (const source of shelves.sources.filter((item) => item.through)) assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
  const section = note.slice(note.indexOf("## What rests on non-commercial or unlicensed sources"));
  for (const name of ["PROSITE", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI", "MitoFates", "TAIR"]) assert.ok(section.includes(name), name);
});

test("a family has the same id and name here as in the human's file, and the districts are the same", async () => {
  const mine = new Map([...families.map((line) => [line.id, line.label]), ...table.filter((row) => row.family).map((row) => [row.under, row.family])]);
  assert.equal(mine.size, shelves.families_in_all);
  const theirs = await json(path.join(ROOT, "data", "proteins", "human", "shelves.json"));
  const shared = theirs.families.map((row) => named(theirs.family_columns, row)).filter((line) => mine.has(line.id));
  assert.ok(new Set(shared.map((line) => line.id)).size > 500, "families in common with the human");
  for (const line of shared) assert.equal(mine.get(line.id), line.label, line.id);
  assert.deepEqual(shelves.groups.map((group) => [group.id, group.label]), theirs.groups.map((group) => [group.id, group.label]));
  // The shelves an animal cell also has carry the same names here.
  const labels = new Map(shelves.shelves.map((shelf) => [shelf.id, shelf.label]));
  for (const shelf of theirs.shelves) assert.equal(labels.get(shelf.id), shelf.label, shelf.id);
});

test("the files keep their limits, hold no machine path, and the notes give the files' own numbers", () => {
  assert.ok(Buffer.byteLength(shelvesText) < 1024 * 1024 && Buffer.byteLength(tableText) < 3 * 1024 * 1024);
  assert.ok(!MACHINE.test(shelvesText) && !MACHINE.test(tableText) && !MACHINE.test(readme) && !MACHINE.test(JSON.stringify(species)) && !MACHINE.test(JSON.stringify(shapes)), "a machine path");
  for (const n of [39144, 16217, 22927, 27368, 16212, 11156]) assert.ok(note.includes(said(n)), `${said(n)} is not in the note`);
  for (const n of [27368, sum(Object.values(shelves.shelf_counts.plastid)), shelves.families_in_all]) assert.ok(readme.includes(said(n)) && note.includes(said(n)), `${said(n)} is not in the notes`);
});

test("the tool cuts the members' files as the lines say, and every member carries the declared marks", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "thalecress-members-"));
  try {
    const cut = spawnSync("python3", ["-I", TOOL, "members", "--out", folder], { encoding: "utf8" });
    assert.equal(cut.status, 0, cut.stderr);
    const members = [];
    for (const file of [...new Set(lines.map(([, line]) => line.file))].sort()) {
      const data = await json(path.join(folder, file));
      assert.equal(data.format, "cells.visualizer.species_protein_members@1");
      members.push(...data.members.map((row) => named(data.columns, row)));
    }
    assert.deepEqual(members.map((member) => member.id), table.map((row) => row.id));
    const pump = members.find((member) => member.id === "F4I111");
    assert.deepEqual([pump.gene, pump.marks.reviewed, pump.side, pump.unit], ["MCU1", true, "in", ["U47"]]);
    for (const member of members) for (const name of Object.keys(member.marks)) assert.ok(name in shelves.marks, `${member.id}: the mark ${name} is not declared`);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("the build tool reproduces the six files from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set THALECRESS_DATASETS)" }, async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: [path.join(DATASETS, "*", "*")], env: ["THALECRESS_DATASETS"] })) return;
  const folder = await mkdtemp(path.join(os.tmpdir(), "thalecress-build-"));
  try {
    const built = spawnSync("python3", ["-I", TOOL, "build", "--datasets", DATASETS, "--out-dir", path.join(folder, "thalecress"), "--out-species", path.join(folder, "species.json"), "--out-shapes", path.join(folder, "shapes.json"), "--out-atlas", path.join(folder, "atlas.json")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    assert.equal(built.status, 0, built.stderr);
    for (const [made, kept] of [["thalecress/shelves.json", path.join(FOLDER, "shelves.json")], ["thalecress/proteins.tsv", path.join(FOLDER, "proteins.tsv")], ["thalecress/README.md", path.join(FOLDER, "README.md")], ["species.json", SPECIES], ["shapes.json", SHAPES], ["atlas.json", ATLAS]]) {
      assert.equal(await readFile(path.join(folder, made), "utf8"), await readFile(kept, "utf8"), `${made} is not what the tool builds`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
