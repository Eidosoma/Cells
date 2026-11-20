// The mouse in the viewer: its species file and outlines, its side of the protein atlas and its
// own proteins on shelves are held to their contracts (schema/SPECIES.md, SPECIES_SHAPES.md,
// SPECIES_ATLAS.md, SPECIES_PROTEINS.md) and to what the note says of them. The catalogue is the
// whole reference proteome: one protein for each gene, reviewed or not. Its cell and its sheet
// are the planarian's, standing for skin-like tissue (the user, 16 November 2026: "same skin
// cell"). Where the saved downloads are on this machine, the build tool must reproduce the six
// files byte for byte; it builds into out/, never into the memory-backed /tmp.
//
//   node --test tests/mouse_atlas.test.mjs
//   MOUSE_DATASETS=DATA node --test tests/mouse_atlas.test.mjs    (DATA holds every species' downloads)

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { accessoryRoles } from "./helpers/atlas_products.mjs";

const ACCESSORY = accessoryRoles();

const TOOL = path.join(ROOT, "tools", "build_mouse_atlas.py");
const FOLDER = path.join(ROOT, "data", "proteins", "mouse");
const SPECIES = path.join(ROOT, "data", "species", "mouse.json");
const SHAPES = path.join(ROOT, "data", "species", "shapes", "mouse.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "mouse.json");
const DATASETS = process.env.MOUSE_DATASETS || "/mnt/datasets/Cells";
const SAVED = ["mouse/uniprot-mouse-reference-proteome", "mouse/europepmc-open-papers", "human/interpro-entries-tree-and-go", "human/uniprot-docs-and-terms"].every((folder) => existsSync(path.join(DATASETS, folder, "MANIFEST.json")));
const SIDES = ["outside", "in", "inside", "not known"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
// Scratch for the tool's runs: on disk under out/, as the project keeps it (/tmp is memory on its machine).
const SCRATCH = path.join(ROOT, "out", "tests");

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const species = await json(SPECIES);
const shapes = await json(SHAPES);
const atlas = await json(ATLAS);
const planarian = await json(path.join(ROOT, "data", "species", "planarian.json"));
const shelvesText = await readFile(path.join(FOLDER, "shelves.json"), "utf8");
const shelves = JSON.parse(shelvesText);
const tableText = await readFile(path.join(FOLDER, "proteins.tsv"), "utf8");
const readme = await readFile(path.join(FOLDER, "README.md"), "utf8");
const note = await readFile(path.join(ROOT, "docs", "MOUSE.md"), "utf8");
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
const level = (id) => species.levels.find((item) => item.id === id);
const along = (stations) => sum(stations.slice(1).map((station, index) => Math.hypot(station[0] - stations[index][0], station[1] - stations[index][1], station[2] - stations[index][2])));
const part = (name) => shapes.parts.find((item) => item.name === name);
// The numbers as built on 16 November 2026 from UniProt's release 2026_04 (docs/MOUSE.md).
const FROM_COUNTS = [228903, 17279, 211624, 21872, 21872, 17221, 4651, 207031]; // entries, reviewed, unreviewed, genes, shown, shown reviewed, shown unreviewed, further
const FINDINGS = [43, 0, 0, 6]; // found, different family, none found, nothing to look for
const SHELF_SOURCES = [
  ["UniProt", "permissive", null], ["InterPro", "permissive", null], ["Gene Ontology", "permissive", null],
  ["PROSITE", "non-commercial", "UniProt"], ["HAMAP", "permissive", "UniProt"], ["TMHMM", "non-commercial", "UniProt"], ["Phobius", "non-commercial", "UniProt"],
  ["SignalP", "non-commercial", "UniProt"], ["TargetP", "non-commercial", "UniProt"], ["Memsat", "no stated terms", "UniProt"], ["Predotar", "no stated terms", "UniProt"], ["big-PI", "no stated terms", "UniProt"],
];

test("the species file says what it is: an animal whose generic cell and sheet Cells models, with placeholder outlines, and the record's one line on the mouse", async () => {
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "cell", "sources"]);
  assert.deepEqual([species.format, species.id, species.label, species.organism, species.taxon, species.group, species.default], ["cells.visualizer.species@1", "mouse", "Mouse", "Mus musculus", 10090, "Animals", false]);
  // In the switch after the human and before the planarian.
  const human = await json(path.join(ROOT, "data", "species", "human.json"));
  assert.ok(human.order < species.order && species.order < planarian.order, `order ${species.order}`);
  assert.equal(species.modelled.state, "generic");
  assert.match(species.modelled.text, /not this animal/);
  assert.match(species.modelled.text, /placeholder outlines: nothing at those scales is simulated/);
  // What the record says, and no more: D155's point 5, for a comparison of heart cells that is not built.
  assert.match(species.modelled.text, /decision D155, 14 November 2026\)\. That comparison concerns heart muscle cells, and nothing of it is built yet\.$/);
  assert.deepEqual(species.levels.map((item) => item.id), ["molecules", "cell", "tissue", "organ", "organism"]);
  // The cell and the sheet are the planarian's: one cell of a sheet that stands for skin-like tissue.
  const theirs = Object.fromEntries(planarian.levels.map((item) => [item.id, item]));
  assert.deepEqual(level("cell").shape, theirs.cell.shape);
  assert.deepEqual(level("tissue").shape, theirs.tissue.shape);
  assert.match(level("cell").note, /^The cell drawn is one cell of the sheet, which stands for skin-like tissue; it is not a model of a mouse's skin cell\. Its shape and its sizes are the picture's choice/);
  assert.match(level("tissue").note, /^The sheet stands for skin-like tissue: a single layer of cells\./);
  assert.deepEqual([level("cell").notes[0].text, level("tissue").notes[0].text], [theirs.cell.notes[0].text, theirs.tissue.notes[0].text]);
  // Nothing of a flatworm's skin is said of the mouse.
  assert.ok(!/flatworm|basement membrane/.test(JSON.stringify(species)));
  const [, , , organ, organism] = species.levels;
  assert.deepEqual([organ.label, organ.shape, organism.label, organism.shape], ["Ear", { kind: "outline", ref: "mouse", parts: ["left ear"], context: ["head and body", "right ear"] }, "Whole mouse", { kind: "outline", ref: "mouse" }]);
  for (const item of [organ, organism]) {
    assert.match(item.note, /the picture's choice/);
    assert.match(item.note, /four house mice trapped in Qatar/);
    assert.deepEqual(item.sources, ["islam2021"]);
  }
  assert.match(organ.note, /no ear is modelled, and the ear's own cells are not modelled/);
  // Beside the whole mouse the sheet could not be seen: its ring says it is not to scale.
  assert.match(organism.sheet_mark.note, /not to scale/);
  // `shelf`: an organelle the Cell view does not draw, on the Machines view's shelf alone (20 November 2026, step D).
  assert.deepEqual(species.cell.parts, { membranes: 1, wall: false, nucleus: true, organelles: ["er", "golgi", "mitochondria"], shelf: ["autophagosome"] });
  for (const fact of species.cell.facts) assert.ok(fact.sources.every((key) => species.sources[key]?.class === "permissive"), fact.label);
  for (const text of [JSON.stringify(species), JSON.stringify(atlas), shelvesText, readme]) assert.ok(!/\b(is|are|was|were) modelled\b(?! \.)|Cells models (the mouse|this animal|Mus\b)/i.test(text.replace(/no ear is modelled/g, "").replace(/own cells are not modelled/g, "")));
});

test("the outlines: a mouse and its ears, their lengths the paper's, with the sheet on the left ear", () => {
  assert.deepEqual([shapes.format, shapes.parts.map((item) => [item.name, item.group ?? null, item.kind])], ["cells.visualizer.outline@1", [["head and body", "body", "loft"], ["tail", "body", "loft"], ["left ear", "ears", "loft"], ["right ear", "ears", "loft"]]]);
  assert.match(shapes.note, /the picture's choice/);
  // The head and body, the tail and the ear are drawn as long as the paper's means: 78.5, 85.3 and 13.3 mm.
  const body = part("head and body").stations;
  assert.equal(body.at(-1)[0] - body[0][0], 78500);
  assert.ok(Math.abs(along(part("tail").stations) - 85300) < 853, `tail ${along(part("tail").stations)}`);
  for (const name of ["left ear", "right ear"]) assert.ok(Math.abs(along(part(name).stations) - 13300) < 133, `${name} ${along(part(name).stations)}`);
  for (const value of ["78.5 ± 2.4 mm", "85.3 ± 4.1 mm", "13.3 ± 1.7 mm"]) assert.ok(species.sources.islam2021.text.includes(value), value);
  assert.equal(species.sources.islam2021.class, "permissive");
  // The sheet lies on the upper face of the left ear, half-way along it.
  const ear = part("left ear").stations, middle = ear[10];
  assert.deepEqual(shapes.tissue_on.at_um, [middle[0], middle[1] + middle[4], middle[2]]);
  assert.ok(middle[2] < 0, "the left ear is on the side of negative z");
});

test("the catalogue is the whole reference proteome: one protein for each gene, reviewed or not, with its gene's further entries counted", () => {
  const from = shelves.from_counts;
  assert.deepEqual([from.entries, from.reviewed, from.unreviewed, from.genes, from.shown, from.shown_reviewed, from.shown_unreviewed, from.further], FROM_COUNTS);
  assert.equal(table.length, from.shown);
  assert.equal(new Set(table.map((row) => row.id)).size, table.length);
  assert.deepEqual([count(table, (row) => row.reviewed === "1"), count(table, (row) => row.reviewed === "0")], [from.shown_reviewed, from.shown_unreviewed]);
  assert.ok(table.every((row) => Number(row.entries) >= 1) && sum(table.map((row) => Number(row.entries) - 1)) >= from.further_tied_to_a_shown_gene);
  assert.deepEqual([shelves.predicted, shelves.marks.reviewed.values, shelves.marks.entries.values], [false, [true, false], "number"]);
  assert.match(shelves.marks.entries.note, /by the MGI gene that UniProt gives each entry/);
  // What stands behind each place, for curated and for automatic entries, adds up to the catalogue.
  const curated = shelves.curated.rows;
  assert.deepEqual([sum(curated.map((row) => row[1])), sum(curated.map((row) => row[2]))], [from.shown_reviewed, from.shown_unreviewed]);
  const kind = (row) => (row.basis === "p" ? "predicted from a segment or a signal" : row.basis === "n" ? "not known" : { e: "stated, on an experiment", s: "stated, by likeness", c: "stated, by a curator's inference", r: "stated, by a rule", n: "stated, with no evidence given" }[row.evidence]);
  for (const [what, reviewed, unreviewed] of curated) assert.deepEqual([count(table, (row) => row.reviewed === "1" && kind(row) === what), count(table, (row) => row.reviewed === "0" && kind(row) === what)], [reviewed, unreviewed], what);
  // No curator wrote an unreviewed entry: what it states is stated by a rule.
  assert.ok(table.every((row) => row.reviewed === "1" || row.basis !== "s" || row.evidence === "r"));
});

test("the shelves are an animal cell's six; every protein is in exactly one line and the counts add up", () => {
  assert.deepEqual([shelves.format, shelves.species], ["cells.visualizer.species_proteins@1", "mouse"]);
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

test("the atlas holds found to a family that makes the machine itself; its products are the proteins that carry the signature, named by no symbol", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  const findings = Object.values(atlas.units).map((unit) => unit.finding);
  assert.deepEqual(["found", "different family", "none found", "nothing to look for"].map((word) => count(findings, (f) => f === word)), FINDINGS);
  for (const [id, unit] of Object.entries(atlas.units)) {
    assert.equal(unit.products.length > 0, ["found", "different family"].includes(unit.finding), id);
    for (const product of unit.products) {
      const row = byId.get(product.ids[0].id);
      assert.ok(row && row.units.split(";").includes(id), `${id}: ${product.gene}`);
      // Two facts, apart: its record is its entry's, from the table; how it was found is its family's part in the machine, never its entry's.
      assert.equal(product.entry, row.reviewed === "1" ? "reviewed" : "unreviewed", `${id}: ${product.gene}`);
      assert.equal(product.found_by, ACCESSORY.has(product.role) ? "accessory signature" : "family signature", `${id}: ${product.gene}`);
      assert.ok(!("evidence" in product), `${id}: ${product.gene} carries the older word`);
      // Each product is there by its own entry's signature, which its note names.
      assert.match(product.evidence_note, /UniProtKB entry carries IPR\d{6}/, `${id}: ${product.gene}`);
    }
  }
  for (const row of table) for (const id of row.units ? row.units.split(";") : []) assert.ok(atlas.units[id].products.some((product) => product.ids[0].id === row.id), `${row.gene}: ${id}`);
  // The unit's candidates are by family, never by a look-alike symbol, and nothing is called an ortholog.
  assert.ok(atlas.method.some((line) => /never because its gene's symbol looks like that of a human candidate/.test(line)));
  assert.ok(atlas.method.some((line) => /no source of orthology was read, and nothing is called an ortholog/.test(line)));
  assert.ok(!/\borthologu?e?s?\b(?! was read| is called)/i.test(JSON.stringify(atlas.units)));
  // The sodium channels, the Kv1 channels and the connexins, by name.
  assert.ok(atlas.units.U01.products.some((product) => product.gene === "Scn2a") && atlas.units.U05.products.some((product) => product.gene === "Kcna1"));
  for (const id of ["U36", "U37", "U38"]) assert.ok(atlas.units[id].finding === "found" && atlas.units[id].products.every((product) => product.role === "connexins") && atlas.units[id].products.some((product) => product.gene === "Gja1"), id);
  // Where the protein shown for a gene lacks the family that another entry of the gene carries, the note says so (Atp2b3, a calcium pump).
  assert.ok(!atlas.units.U40.products.some((product) => product.gene === "Atp2b3"));
  assert.match(atlas.units.U40.note, /The mouse's Atp2b3 is shown by its entry A0ACP0BMC4, the one UniProt's gene-by-gene set names, which carries no InterPro entry yet; 3 other entries of the same gene \(A2ALL9, F6SDZ9, F6ZUK9\) carry the signature of plasma-membrane calcium pumps/);
  assert.equal(byId.get("A0ACP0BMC4")?.gene, "Atp2b3");
  for (const source of atlas.sources) assert.equal(source.class, "permissive", source.name);
  assert.ok(!MACHINE.test(JSON.stringify(atlas)));
});

test("every source states its terms and its class; the tools behind UniProt's statements are named, read through UniProt and counted", () => {
  assert.deepEqual(shelves.sources.map((source) => [source.name, source.class, source.through ?? null]), SHELF_SOURCES);
  for (const source of shelves.sources.filter((item) => item.through)) assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
  assert.deepEqual(Object.entries(species.sources).map(([key, source]) => [key, source.class]), [["uniprot", "permissive"], ["islam2021", "permissive"], ["muller2020", "permissive"], ["martinezalonso2013", "permissive"], ["wikipedia-autophagosome", "permissive"]]);
  const section = note.slice(note.indexOf("## What rests on non-commercial or unlicensed sources"));
  for (const name of ["PROSITE", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI", "MGI"]) assert.ok(section.includes(name), name);
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
  const from = shelves.from_counts;
  for (const n of [from.entries, from.reviewed, from.unreviewed, from.genes, from.shown_reviewed, from.shown_unreviewed]) assert.ok(note.includes(said(n)), `${said(n)} is not in the note`);
  for (const n of [from.shown, sum(Object.values(shelves.shelf_counts.cell)), shelves.families_in_all]) assert.ok(readme.includes(said(n)) && note.includes(said(n)), `${said(n)} is not in the notes`);
});

test("the tool cuts the members' files as the lines say, and every member carries the declared marks", async () => {
  await mkdir(SCRATCH, { recursive: true });
  const folder = await mkdtemp(path.join(SCRATCH, "mouse-members-"));
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
    const scn2a = members.find((member) => member.gene === "Scn2a");
    assert.deepEqual([scn2a.marks.reviewed, scn2a.side, scn2a.unit], [true, "in", ["U01", "U02", "U03", "U04"]]);
    assert.ok(scn2a.marks.entries > 1);
    for (const member of members) for (const name of Object.keys(member.marks)) assert.ok(name in shelves.marks, `${member.id}: the mark ${name} is not declared`);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("the build tool reproduces the six files from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set MOUSE_DATASETS)" }, async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: [path.join(DATASETS, "*", "*")], env: ["MOUSE_DATASETS"] })) return;
  await mkdir(SCRATCH, { recursive: true });
  const folder = await mkdtemp(path.join(SCRATCH, "mouse-build-"));
  try {
    const built = spawnSync("python3", ["-I", TOOL, "build", "--datasets", DATASETS, "--out-dir", path.join(folder, "mouse"), "--out-species", path.join(folder, "species.json"), "--out-shapes", path.join(folder, "shapes.json"), "--out-atlas", path.join(folder, "atlas.json")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    assert.equal(built.status, 0, built.stderr);
    for (const [made, kept] of [["mouse/shelves.json", path.join(FOLDER, "shelves.json")], ["mouse/proteins.tsv", path.join(FOLDER, "proteins.tsv")], ["mouse/README.md", path.join(FOLDER, "README.md")], ["species.json", SPECIES], ["shapes.json", SHAPES], ["atlas.json", ATLAS]]) {
      assert.equal(await readFile(path.join(folder, made), "utf8"), await readFile(kept, "utf8"), `${made} is not what the tool builds`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
