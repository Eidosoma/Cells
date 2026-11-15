// Escherichia coli K-12 in the viewer: its species file, its side of the protein atlas and
// its own proteins on shelves are held to their contracts (schema/SPECIES.md,
// schema/SPECIES_ATLAS.md, schema/SPECIES_PROTEINS.md), and to what the note says of them.
// It is a data-only organism: nothing here may say that the engine models it. Where the
// folder of saved downloads is on this machine, the build tool must reproduce the five
// files from it, byte for byte; elsewhere that one check is skipped.
//
//   node --test tests/ecoli_atlas.test.mjs
//   ECOLI_DATASETS=DATA node --test tests/ecoli_atlas.test.mjs     (DATA holds every species' downloads)

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const TOOL = path.join(ROOT, "tools", "build_ecoli_atlas.py");
const FOLDER = path.join(ROOT, "data", "proteins", "ecoli");
const SPECIES = path.join(ROOT, "data", "species", "ecoli.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "ecoli.json");
const DATASETS = process.env.ECOLI_DATASETS || "/mnt/datasets/Cells";
const SAVED = existsSync(path.join(DATASETS, "ecoli", "uniprot-ecoli-k12-reviewed-proteome", "MANIFEST.json")) && existsSync(path.join(DATASETS, "human", "interpro-entries-tree-and-go", "MANIFEST.json"));
const SIDES = ["outside", "in", "inside", "not known"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const CHEMOTAXIS = ["cheA", "cheW", "cheY", "cheZ", "cheR", "cheB", "tsr", "tar", "trg", "tap", "aer", "motA", "motB", "fliG", "fliM", "fliN"];

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const species = await json(SPECIES);
const atlas = await json(ATLAS);
const shelvesText = await readFile(path.join(FOLDER, "shelves.json"), "utf8");
const shelves = JSON.parse(shelvesText);
const tableText = await readFile(path.join(FOLDER, "proteins.tsv"), "utf8");
const readme = await readFile(path.join(FOLDER, "README.md"), "utf8");
const note = await readFile(path.join(ROOT, "docs", "ECOLI.md"), "utf8");
const snapshot = await json(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"));
const [head, ...tableLines] = tableText.replace(/\n$/, "").split("\n");
const columns = head.split("\t");
const table = tableLines.map((line) => Object.fromEntries(line.split("\t").map((value, index) => [columns[index], value])));
const byGene = new Map(table.map((row) => [row.gene, row]));
const named = (names, row) => Object.fromEntries(names.map((name, index) => [name, row[index]]));
const families = shelves.families.map((row) => named(shelves.family_columns, row));
const lone = shelves.lone.parts.map((row) => named(shelves.lone.part_columns, row));
const parts = shelves.no_family.parts.map((row) => named(shelves.no_family.part_columns, row));
const lines = [...families.map((line) => ["family", line]), ...lone.map((line) => ["lone", line]), ...parts.map((line) => ["part", line])];
const sum = (numbers) => numbers.reduce((total, number) => total + number, 0);
const count = (rows, test_) => rows.filter(test_).length;
const said = (n) => n.toLocaleString("en-US");

test("the species file says what it is: a data-only organism, proposed and never modelled", async () => {
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "no_further_levels", "cell", "capability_sources", "sources"]);
  assert.deepEqual([species.format, species.id, species.label, species.organism, species.taxon, species.group, species.default], ["cells.visualizer.species@1", "ecoli", "E. coli", "Escherichia coli K-12", 83333, "Bacteria", false]);
  assert.equal(species.modelled.state, "proposed");
  assert.match(species.modelled.text, /data-only organism/);
  assert.match(species.modelled.text, /D179/);
  assert.match(species.modelled.text, /Nothing of it is in the engine: no organism definition, no model and no run\./);
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell"]);
  assert.deepEqual(species.levels[1].shape, { kind: "capsule", length_um: 2.5, across_um: 1 });
  assert.match(species.levels[1].note, /the picture's choice/);
  assert.deepEqual(species.cell.parts, { membranes: 2, wall: true, nucleus: false, chromosome_kbp: 4642, ribosomes: 6800 });
  // The same capabilities as the other single cells, each with a place or the reason it has none.
  const other = await json(path.join(ROOT, "data", "species", "mpneumoniae.json"));
  assert.deepEqual(Object.keys(species.cell.capabilities).sort(), Object.keys(other.cell.capabilities).sort());
  for (const [id, item] of Object.entries(species.cell.capabilities)) assert.ok(item.place === "present" ? item.note : item.place === "absent" && item.why, id);
  for (const fact of species.cell.facts) assert.ok(fact.sources.every((key) => species.sources[key]?.class === "permissive"), fact.label);
  // Nothing in the three files says the engine models it.
  for (const text of [JSON.stringify(species), JSON.stringify(atlas), shelvesText, readme]) assert.ok(!/\b(is|are|was|were) modelled\b|Cells models (it|this organism|E\. coli)/i.test(text));
});

test("the atlas has an entry for every unit, finds none of the animal machines, and counts no accessory subunit as one", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  const findings = Object.values(atlas.units).map((unit) => unit.finding);
  assert.deepEqual([count(findings, (f) => f === "none found"), count(findings, (f) => f === "nothing to look for"), findings.length], [43, 6, 49]);
  for (const unit of Object.values(atlas.units)) assert.deepEqual(unit.products, []);
  // One protein carries the family signature of the calcium channel's alpha-2/delta subunits and of nothing that forms a channel.
  for (const id of ["U24", "U25", "U26", "U27", "U28", "U29", "U30"]) {
    assert.match(atlas.units[id].note, /yfbK/, id);
    assert.match(atlas.units[id].note, /no candidate for the unit/, id);
  }
  const beside = atlas.extra.filter((product) => product.role === "accessory-subunit family");
  assert.deepEqual(beside.map((product) => product.gene), ["yfbK"]);
  assert.match(atlas.method.join(" "), /A unit counts as found only where a protein carries the signature of a family that makes the machine itself/);
  for (const product of atlas.extra) assert.ok(product.why && product.evidence === "reviewed entry" && byGene.get(product.gene)?.id === product.ids[0].id, product.gene);
  for (const source of atlas.sources) assert.equal(source.class, "permissive", source.name);
  assert.ok(!MACHINE.test(JSON.stringify(atlas)));
});

test("the shelves are the cell's two membranes and one that is not named; every protein is in exactly one line and the counts add up", () => {
  assert.deepEqual([shelves.format, shelves.species, shelves.predicted], ["cells.visualizer.species_proteins@1", "ecoli", false]);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["inner", "outer", "membrane"]);
  assert.equal(table.length, 4403);
  assert.deepEqual(shelves.from_counts, { reviewed: 4403, isoforms: 12, sequences: 4415, unreviewed: 0, entries: 4403, genes: 4403, state_a_place: 2174 });
  assert.equal(new Set(table.map((row) => row.id)).size, table.length);
  assert.equal(sum(lines.map(([, line]) => line.count)), table.length);
  let cursor = 0;
  for (const [kind, line] of lines) {
    const rows = table.slice(cursor, cursor + line.count);
    cursor += line.count;
    assert.ok(rows.every((row) => row.shelf === (line.shelf ?? "") && (kind === "lone" ? row.family : row.under === line.id)), `${line.id} on ${line.shelf}`);
    assert.deepEqual(Object.fromEntries(SIDES.map((side) => [side, count(rows, (row) => row.side === side)]).filter(([, n]) => n)), line.sides, `${line.id} on ${line.shelf}`);
  }
  for (const line of families) assert.equal(line.total, sum(families.filter((other) => other.id === line.id).map((other) => other.count)), line.id);
  assert.ok(families.every((line) => line.total > 1) && shelves.lone.count === sum(lone.map((line) => line.count)));
  assert.deepEqual([shelves.distinct_families, shelves.family_lines, shelves.families_in_all], [new Set(families.map((line) => line.id)).size, families.length, new Set(families.map((line) => line.id)).size + shelves.lone.families]);
  for (const side of SIDES) assert.equal(shelves.counts[side], count(table, (row) => row.side === side), side);
  for (const [shelf, counts] of Object.entries(shelves.shelf_counts)) for (const side of SIDES) assert.equal(counts[side], count(table, (row) => row.shelf === (shelf === "no shelf" ? "" : shelf) && row.side === side), `${shelf}, ${side}`);
  assert.ok(table.every((row) => (row.side === "not known") === (row.basis === "n") && (row.shelf !== "" || row.side === "not known")));
  assert.deepEqual(shelves.placed_by.map((item) => item.proteins).reduce((a, b) => a + b, 0), table.length);
  assert.ok(table.every((row) => row.units === ""), "no protein of this organism is a candidate for a unit");
});

test("what lies between the two membranes stands as the file's rule says, and is counted", () => {
  const free = (row) => /^(0200|0041)(\.|$)/.test(row.place);
  const expected = [
    count(table, (row) => row.shelf === "inner" && row.side === "outside" && free(row)),
    count(table, (row) => row.shelf === "inner" && row.side === "outside" && !free(row)),
    count(table, (row) => row.shelf === "outer" && row.side === "inside"),
    count(table, (row) => row.shelf === "membrane" && row.side === "outside"),
  ];
  assert.deepEqual(Object.values(shelves.between.counts), expected);
  assert.deepEqual(expected, [177, 23, 10, 144]);
  // A protein whose first stated place is the periplasm is on the inner membrane's shelf, outside, as stated.
  assert.ok(table.filter((row) => /^0200(\.|$)/.test(row.place)).every((row) => row.shelf === "inner" && row.side === "outside" && row.basis === "s"));
  // This file's reading: a lipid anchor at "Cell membrane", with no experiment behind it, is on the shelf of a membrane that is not named.
  const anchored = table.filter((row) => row.place === "0039.9901" || row.place.startsWith("0039.9901."));
  assert.equal(anchored.length, 40);
  assert.ok(anchored.every((row) => row.shelf === "membrane" && row.evidence !== "e"));
  assert.match(shelves.shelves[2].note, /The 40 lipid-anchored ones whose entry says "Cell membrane" with no experiment behind the statement/);
  // Of a protein stated at the outer membrane, a signal peptide settles nothing.
  assert.ok(table.filter((row) => row.shelf === "outer").every((row) => row.basis !== "p" || row.side === "in"));
});

test("chemotaxis and the assemblies are marked from UniProt's keyword and the Gene Ontology, and the file says where each marked protein stands", async () => {
  assert.deepEqual([shelves.marks.chemotaxis.source, shelves.marks.complex.source, shelves.marks.chemotaxis.measured], ["UniProt", "Gene Ontology", false]);
  assert.deepEqual(shelves.marks.complex.values, ["flagellum", "chemoreceptor array", "ribosome", "RNA polymerase", "ATP synthase"]);
  for (const gene of CHEMOTAXIS) assert.equal(byGene.get(gene)?.chemotaxis, "1", gene);
  assert.equal(count(table, (row) => row.chemotaxis === "1"), 22);
  assert.deepEqual(["cheA", "cheW", "tsr", "tar", "trg"].map((gene) => byGene.get(gene).complex), Array(5).fill("chemoreceptor array"));
  assert.deepEqual(["motA", "motB", "fliG", "fliM", "fliN", "fliC"].map((gene) => byGene.get(gene).complex), Array(6).fill("flagellum"));
  assert.deepEqual(shelves.marks.complex.values.map((value) => count(table, (row) => row.complex === value)), [34, 6, 59, 7, 8]);
  // The highlights: one row for each marked protein, with the line it stands on.
  const rows = shelves.highlights.rows.map((row) => named(shelves.highlights.columns, row));
  assert.equal(rows.length, 22 + 34 + 6 + 59 + 7 + 8);
  const lineOf = new Map();
  let cursor = 0;
  for (const [kind, line] of lines) for (const row of table.slice(cursor, (cursor += line.count))) lineOf.set(row.id, [kind, line.id]);
  for (const row of rows) {
    const protein = table.find((item) => item.id === row.id);
    assert.ok(protein && protein.gene === row.gene && (row.mark === "chemotaxis" ? protein.chemotaxis === "1" && row.value === true : protein.complex === row.value), `${row.mark}: ${row.gene}`);
    assert.deepEqual([row.kind, row.under, row.shelf ?? "", row.side], [...lineOf.get(row.id), protein.shelf, protein.side], row.gene);
  }
  // The members' files, as the page builder cuts them, carry the marks.
  const folder = await mkdtemp(path.join(os.tmpdir(), "ecoli-members-"));
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
    const cheA = members.find((member) => member.gene === "cheA");
    assert.deepEqual([cheA.marks.chemotaxis, cheA.marks.complex, cheA.marks.locus, cheA.marks.isoforms, cheA.side], [true, "chemoreceptor array", "b1888", 2, "inside"]);
    for (const member of members) for (const name of Object.keys(member.marks)) assert.ok(name in shelves.marks, `${member.id}: the mark ${name} is not declared`);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("every source states its terms and its class; the tools behind UniProt's statements are named, read through UniProt and counted", () => {
  assert.deepEqual(shelves.sources.map((source) => [source.name, source.class, source.through ?? null]), [
    ["UniProt", "permissive", null], ["InterPro", "permissive", null], ["Gene Ontology", "permissive", null],
    ["PROSITE", "non-commercial", "UniProt"], ["HAMAP", "permissive", "UniProt"], ["TMHMM", "non-commercial", "UniProt"], ["Phobius", "non-commercial", "UniProt"],
    ["SignalP", "non-commercial", "UniProt"], ["TargetP", "non-commercial", "UniProt"], ["Memsat", "no stated terms", "UniProt"], ["Predotar", "no stated terms", "UniProt"],
  ]);
  for (const source of shelves.sources.filter((item) => item.through)) assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
  // The note's section names each tool that is not permissive, and the two databases that are only pointed to.
  const section = note.slice(note.indexOf("## What rests on non-commercial or unlicensed sources"));
  assert.ok(section.length > 200);
  for (const name of ["PROSITE", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "EcoCyc", "STEPdb"]) assert.ok(section.includes(name), name);
  assert.ok(!shelves.sources.some((source) => ["EcoCyc", "STEPdb"].includes(source.name)), "the organism's own databases are pointers in the note, not sources of the file");
});

test("a family has the same id and name here as in the human's and the planarian's files", async () => {
  const mine = new Map([...families.map((line) => [line.id, line.label]), ...table.filter((row) => row.family).map((row) => [row.under, row.family])]);
  assert.equal(mine.size, shelves.families_in_all);
  for (const other of ["human", "planarian"]) {
    const theirs = await json(path.join(ROOT, "data", "proteins", other, "shelves.json"));
    const shared = theirs.families.map((row) => named(theirs.family_columns, row)).filter((line) => mine.has(line.id));
    assert.ok(new Set(shared.map((line) => line.id)).size > 100, `${other}: families in common`);
    for (const line of shared) assert.equal(mine.get(line.id), line.label, `${other}: ${line.id}`);
    assert.deepEqual(shelves.groups.map((group) => [group.id, group.label]), theirs.groups.map((group) => [group.id, group.label]), `${other}: the districts`);
  }
});

test("the files keep their limits, hold no machine path, and the notes give the files' own numbers", () => {
  assert.ok(Buffer.byteLength(shelvesText) < 1024 * 1024 && Buffer.byteLength(tableText) < 3 * 1024 * 1024);
  assert.ok(!MACHINE.test(shelvesText) && !MACHINE.test(tableText) && !MACHINE.test(readme) && !MACHINE.test(JSON.stringify(species)), "a machine path");
  const counts = shelves.shelf_counts;
  for (const text of [readme, note]) {
    for (const n of [4403, 2174, 2123, sum(Object.values(counts.inner)), shelves.families_in_all, shelves.lone.count]) assert.ok(text.includes(said(n)), `${said(n)} is not in the note`);
    for (const n of Object.values(shelves.between.counts)) assert.ok(text.includes(String(n)), `${n} is not in the note`);
  }
  assert.match(note, /proposed/);
  assert.match(note, /D179/);
});

test("the build tool reproduces the five files from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set ECOLI_DATASETS)" }, async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "ecoli-build-"));
  try {
    const built = spawnSync("python3", ["-I", TOOL, "build", "--datasets", DATASETS, "--out-dir", path.join(folder, "ecoli"), "--out-species", path.join(folder, "species.json"), "--out-atlas", path.join(folder, "atlas.json")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    assert.equal(built.status, 0, built.stderr);
    for (const [made, kept] of [["ecoli/shelves.json", path.join(FOLDER, "shelves.json")], ["ecoli/proteins.tsv", path.join(FOLDER, "proteins.tsv")], ["ecoli/README.md", path.join(FOLDER, "README.md")], ["species.json", SPECIES], ["atlas.json", ATLAS]]) {
      assert.equal(await readFile(path.join(folder, made), "utf8"), await readFile(kept, "utf8"), `${made} is not what the tool builds`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
