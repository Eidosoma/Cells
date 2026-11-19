// The fruit fly in the viewer: its species file and outlines, its side of the protein atlas and
// its own proteins on shelves are held to their contracts (schema/SPECIES.md, SPECIES_SHAPES.md,
// SPECIES_ATLAS.md, SPECIES_PROTEINS.md) and to what the note says of them. The catalogue is the
// whole reference proteome: one protein for each gene, reviewed or not. Where the saved downloads
// are on this machine, the build tool must reproduce the six files byte for byte.
//
//   node --test tests/fruitfly_atlas.test.mjs
//   FRUITFLY_DATASETS=DATA node --test tests/fruitfly_atlas.test.mjs    (DATA holds every species' downloads)

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

const TOOL = path.join(ROOT, "tools", "build_fruitfly_atlas.py");
const FOLDER = path.join(ROOT, "data", "proteins", "fruitfly");
const SPECIES = path.join(ROOT, "data", "species", "fruitfly.json");
const SHAPES = path.join(ROOT, "data", "species", "shapes", "fruitfly.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "fruitfly.json");
const DATASETS = process.env.FRUITFLY_DATASETS || "/mnt/datasets/Cells";
const SAVED = existsSync(path.join(DATASETS, "fruitfly", "uniprot-fruitfly-reference-proteome", "MANIFEST.json")) && existsSync(path.join(DATASETS, "human", "interpro-entries-tree-and-go", "MANIFEST.json"));
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
const note = await readFile(path.join(ROOT, "docs", "FRUITFLY.md"), "utf8");
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

test("the species file says what it is: an animal whose generic cell and sheet Cells models, with placeholder outlines", () => {
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "cell", "sources"]);
  assert.deepEqual([species.format, species.id, species.label, species.organism, species.taxon, species.group, species.default], ["cells.visualizer.species@1", "fruitfly", "Fruit fly", "Drosophila melanogaster", 7227, "Animals", false]);
  assert.equal(species.modelled.state, "generic");
  assert.match(species.modelled.text, /not this animal/);
  assert.match(species.modelled.text, /placeholder outlines: nothing at those scales is simulated/);
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell", "tissue", "organ", "organism"]);
  const [, , , organ, organism] = species.levels;
  assert.deepEqual([organ.label, organ.shape, organism.shape], ["Wing", { kind: "outline", ref: "fruitfly", parts: ["wings"], context: ["body"] }, { kind: "outline", ref: "fruitfly" }]);
  // Every size of the outlines is said to be the picture's choice: none was read from a source.
  for (const level of [organ, organism]) assert.match(level.note, /the picture's choice/);
  assert.match(organ.note, /No wing and no wing disc is modelled/);
  assert.deepEqual(species.cell.parts, { membranes: 1, wall: false, nucleus: true, organelles: ["er", "golgi", "mitochondria"] });
  for (const fact of species.cell.facts) assert.ok(fact.sources.every((key) => species.sources[key]?.class === "permissive"), fact.label);
  assert.deepEqual([shapes.format, shapes.parts.map((part) => [part.name, part.group ?? null, part.kind])], ["cells.visualizer.outline@1", [["body", null, "loft"], ["left wing", "wings", "loft"], ["right wing", "wings", "loft"]]]);
  assert.match(shapes.note, /the picture's choice, and no measurement was read/);
  for (const text of [JSON.stringify(species), JSON.stringify(atlas), shelvesText, readme]) assert.ok(!/\b(is|are|was|were) modelled\b(?! \.)|Cells models (the fly|this animal|Drosophila)/i.test(text.replace(/No wing and no wing disc is modelled/g, "").replace(/own cells are not modelled/g, "")));
});

test("the catalogue is the whole reference proteome: one protein for each gene, reviewed or not, with its gene's further entries counted", () => {
  const from = shelves.from_counts;
  assert.deepEqual([from.entries, from.reviewed, from.unreviewed, from.genes, from.shown, from.shown_reviewed, from.shown_unreviewed, from.further], [21941, 3885, 18056, 13814, 13814, 3850, 9964, 8127]);
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

test("the shelves are an animal cell's six; every protein is in exactly one line and the counts add up", () => {
  assert.deepEqual([shelves.format, shelves.species], ["cells.visualizer.species_proteins@1", "fruitfly"]);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["cell", "er", "mito", "nucleus", "other", "membrane"]);
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
});

test("the atlas holds found to a family that makes the machine itself, and its products are the proteins that name the units", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  const findings = Object.values(atlas.units).map((unit) => unit.finding);
  assert.deepEqual(["found", "different family", "none found", "nothing to look for"].map((word) => count(findings, (f) => f === word)), [38, 3, 2, 6]);
  for (const [id, unit] of Object.entries(atlas.units)) {
    assert.equal(unit.products.length > 0, ["found", "different family"].includes(unit.finding), id);
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
  // The sodium channel, the Shaker channel and the innexins, by name.
  assert.ok(atlas.units.U01.products.some((product) => product.gene === "para") && atlas.units.U05.products.some((product) => product.gene === "Sh"));
  for (const id of ["U36", "U37", "U38"]) {
    assert.equal(atlas.units[id].finding, "different family");
    assert.ok(atlas.units[id].products.every((product) => product.role === "innexins") && atlas.units[id].products.some((product) => product.gene === "shakB"));
  }
  // A Kv2 channel is not found by signature, and the note says what a reader would look for.
  for (const id of ["U11", "U12"]) assert.match(atlas.units[id].note, /Shab.*carries the signature of another family/);
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
  for (const name of ["PROSITE", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI", "FlyBase"]) assert.ok(section.includes(name), name);
});

test("a family has the same id and name here as in the human's file, and the districts are the same", async () => {
  const mine = new Map([...families.map((line) => [line.id, line.label]), ...table.filter((row) => row.family).map((row) => [row.under, row.family])]);
  assert.equal(mine.size, shelves.families_in_all);
  const theirs = await json(path.join(ROOT, "data", "proteins", "human", "shelves.json"));
  const shared = theirs.families.map((row) => named(theirs.family_columns, row)).filter((line) => mine.has(line.id));
  assert.ok(new Set(shared.map((line) => line.id)).size > 1000, "families in common with the human");
  for (const line of shared) assert.equal(mine.get(line.id), line.label, line.id);
  assert.deepEqual(shelves.groups.map((group) => [group.id, group.label]), theirs.groups.map((group) => [group.id, group.label]));
  assert.deepEqual(shelves.shelves.map((shelf) => [shelf.id, shelf.label]), theirs.shelves.map((shelf) => [shelf.id, shelf.label]));
});

test("the files keep their limits, hold no machine path, and the notes give the files' own numbers", () => {
  assert.ok(Buffer.byteLength(shelvesText) < 1024 * 1024 && Buffer.byteLength(tableText) < 3 * 1024 * 1024);
  assert.ok(!MACHINE.test(shelvesText) && !MACHINE.test(tableText) && !MACHINE.test(readme) && !MACHINE.test(JSON.stringify(species)) && !MACHINE.test(JSON.stringify(shapes)), "a machine path");
  for (const n of [21941, 3885, 18056, 13814, 3850, 9964]) assert.ok(note.includes(said(n)), `${said(n)} is not in the note`);
  for (const n of [13814, sum(Object.values(shelves.shelf_counts.cell)), shelves.families_in_all]) assert.ok(readme.includes(said(n)) && note.includes(said(n)), `${said(n)} is not in the notes`);
});

test("the tool cuts the members' files as the lines say, and every member carries the declared marks", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "fruitfly-members-"));
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
    const para = members.find((member) => member.gene === "para");
    assert.deepEqual([para.marks.reviewed, para.side, para.unit], [true, "in", ["U01", "U02", "U03", "U04"]]);
    assert.ok(para.marks.entries > 1);
    for (const member of members) for (const name of Object.keys(member.marks)) assert.ok(name in shelves.marks, `${member.id}: the mark ${name} is not declared`);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("the build tool reproduces the six files from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set FRUITFLY_DATASETS)" }, async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: [path.join(DATASETS, "*", "*")], env: ["FRUITFLY_DATASETS"] })) return;
  const folder = await mkdtemp(path.join(os.tmpdir(), "fruitfly-build-"));
  try {
    const built = spawnSync("python3", ["-I", TOOL, "build", "--datasets", DATASETS, "--out-dir", path.join(folder, "fruitfly"), "--out-species", path.join(folder, "species.json"), "--out-shapes", path.join(folder, "shapes.json"), "--out-atlas", path.join(folder, "atlas.json")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    assert.equal(built.status, 0, built.stderr);
    for (const [made, kept] of [["fruitfly/shelves.json", path.join(FOLDER, "shelves.json")], ["fruitfly/proteins.tsv", path.join(FOLDER, "proteins.tsv")], ["fruitfly/README.md", path.join(FOLDER, "README.md")], ["species.json", SPECIES], ["shapes.json", SHAPES], ["atlas.json", ATLAS]]) {
      assert.equal(await readFile(path.join(folder, made), "utf8"), await readFile(kept, "utf8"), `${made} is not what the tool builds`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
