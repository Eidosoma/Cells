// The viewer's data on the minimal cell JCVI-syn3A is held to its contracts and to what it
// may and may not claim: the species file (schema/SPECIES.md), its side of the protein atlas
// (schema/SPECIES_ATLAS.md) and the start of its protein catalogue (data/proteins/syn3a/).
// Where the downloads and the request log are on this machine, the build tool must
// reproduce the files from them, byte for byte; where either is absent that one check is
// skipped.
//
//   node --test tests/syn3a_atlas.test.mjs
//   SYN3A_DATASETS=DATA SYN3A_EVIDENCE=DIR node --test tests/syn3a_atlas.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const SPECIES = path.join(ROOT, "data", "species", "syn3a.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "syn3a.json");
const FOLDER = path.join(ROOT, "data", "proteins", "syn3a");
const TABLE = path.join(FOLDER, "proteins.tsv");
const README = path.join(FOLDER, "README.md");
const TOOL = path.join(ROOT, "tools", "build_syn3a_atlas.py");
// The analysis folder (the log of what was asked) and the folder of downloads (one folder
// per source, each with its MANIFEST.json).
const EVIDENCE = process.env.SYN3A_EVIDENCE || "/mnt/workspaces/Cells/visualizer-syn3a-proteins-20261114-01";
const DATASETS = process.env.SYN3A_DATASETS || "/mnt/datasets/Cells/syn3a";
const SOURCES_READ = ["ncbi-CP016816.2", "breuer2019-elife", "ncbi-CP016816-proteins", "uniprot-syn3a"];
const absent = !existsSync(path.join(EVIDENCE, "requests.json"))
  ? "the request log is not on this machine (set SYN3A_EVIDENCE)"
  : SOURCES_READ.some((source) => !existsSync(path.join(DATASETS, source, "MANIFEST.json")))
    ? "the downloads are not on this machine (set SYN3A_DATASETS)"
    : false;

const LEVELS = ["molecules", "cell", "tissue", "organ", "organism"];
const STATES = ["generic", "proposed", "modelled"];
const CELL_KINDS = { sphere: ["across_um"], capsule: ["length_um", "across_um"], prism: ["sides", "across_um", "radius_um", "height_um", "corner_um", "edge_um"] };
const PARTS = ["membranes", "wall", "nucleus", "organelles", "chromosome_kbp", "ribosomes"];
const FINDINGS = ["found", "different family", "none found", "nothing to look for"];
const EVIDENCE_WORDS = ["reviewed entry", "named in a publication", "family signature", "similarity search"];
const COLUMNS = ["locus_tag", "gene", "product", "length", "protein_id", "origin", "functional_class", "essentiality", "detected", "copies_per_cell", "proteomics_id", "uniparc", "uniprotkb_identical", "interpro"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const key = (text) => String(text).toLowerCase().replace(/[^a-z0-9]/g, "");

const speciesText = await readFile(SPECIES, "utf8");
const species = JSON.parse(speciesText);
const atlasText = await readFile(ATLAS, "utf8");
const atlas = JSON.parse(atlasText);
const table = await readFile(TABLE, "utf8");
const readme = await readFile(README, "utf8");
const said = readme.replace(/\s+/g, " ");
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const map = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const capabilities = map.capabilities.map((item) => item.id);
const rows = table.trimEnd().split("\n").slice(1).map((line) => line.split("\t"));

// ---------------------------------------------------------------- the species file

test("the species file says what it is, as the contract sets out", () => {
  assert.equal(species.format, "cells.visualizer.species@1");
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "order", "default", "made", "modelled", "levels", "no_further_levels", "cell", "sources"]);
  assert.equal(species.id, "syn3a");
  assert.equal(path.basename(SPECIES), `${species.id}.json`);
  assert.equal(species.label, "Syn3A");
  assert.equal(species.organism, "JCVI-syn3A");
  assert.equal(species.taxon, 2144189);
  assert.equal(species.order, 30);
  assert.equal(species.default, false);
  assert.match(species.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(species.plain.trim());
});

test("it is a single cell: molecules and one cell, with a sentence where the other levels would be", () => {
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell"]);
  for (const level of species.levels) assert.ok(LEVELS.includes(level.id));
  assert.ok(species.no_further_levels.trim());
  assert.equal(species.levels[0].shape, undefined, "the molecules level needs no shape");
  const cell = species.levels[1];
  assert.ok(Object.keys(CELL_KINDS).includes(cell.shape.kind), cell.shape.kind);
  for (const [name, value] of Object.entries(cell.shape)) {
    if (name === "kind") continue;
    assert.ok(CELL_KINDS[cell.shape.kind].includes(name), `${name} is not a parameter of a ${cell.shape.kind}`);
    assert.ok(Number.isFinite(value) && value > 0, `${name}: ${value}`);
  }
  assert.ok(cell.shape.across_um < 1, "a cell well under a micrometre across");
  assert.ok(cell.note.trim());
  for (const source of cell.sources) assert.ok(species.sources[source], `the level cites ${source}, which is not a source`);
});

test("what Cells models of it is said plainly: the minimal-cell track by the record's decision, and nothing in the engine", () => {
  assert.ok(STATES.includes(species.modelled.state));
  assert.equal(species.modelled.state, "proposed");
  assert.match(species.modelled.text, /minimal-cell track \(decision D173, 14 November 2026\)/);
  assert.match(species.modelled.text, /a note that proposes it as the first whole-cell validation organism/);
  assert.match(species.modelled.text, /Nothing of it is in the engine yet: the project's record holds an evidence audit and a proposal, in which no engine model ran/);
  // The note that proposes it is not in the repository, so no file of it is cited.
  assert.ok(!/SOTA_SYN3A|docs\//.test(speciesText), "the species file cites a path of the repository");
});

test("every fact has a source, and every number drawn has a fact or is called the picture's choice", () => {
  const facts = species.cell.facts;
  assert.ok(facts.length >= 8);
  for (const fact of facts) {
    assert.deepEqual(Object.keys(fact), ["label", "value", "sources"]);
    assert.ok(fact.label.trim() && fact.value.trim());
    assert.ok(fact.sources.length, `${fact.label} has no source`);
    for (const source of fact.sources) assert.ok(species.sources[source], `${fact.label} cites ${source}, which is not a source`);
  }
  const fact = (label) => facts.find((item) => item.label === label)?.value || "";
  const cell = species.levels[1];
  const parts = species.cell.parts;
  for (const name of Object.keys(parts)) assert.ok(PARTS.includes(name), `${name} is not a part the viewer can draw`);
  // The sphere's width, the chromosome's length and the one membrane are facts.
  assert.ok(fact("Shape and size").includes(`${cell.shape.across_um * 1000} nm`));
  assert.equal(parts.chromosome_kbp, Math.round(Number(fact("Chromosome").match(/([\d,]+) base pairs/)[1].replace(/,/g, "")) / 1000));
  assert.equal(parts.membranes, 1);
  assert.match(fact("Envelope"), /one membrane; no cell wall/);
  assert.equal(parts.wall, false);
  assert.equal(parts.nucleus, false);
  assert.match(fact("Inside"), /no nucleus/);
  // The count of ribosomes is a round number for the measured ones, and the note says so.
  assert.equal(parts.ribosomes, 500);
  assert.match(fact("Ribosomes"), /about 500 in a small cell: 503 or 684 counted/);
  assert.match(cell.note, /round numbers/);
});

test("each of the map's capabilities has a place or is said to be absent, with why", () => {
  const stated = species.cell.capabilities;
  for (const id of Object.keys(stated)) assert.ok(capabilities.includes(id), `${id} is not a capability of the map`);
  // Left out means it has a place as in any cell: only the cell's chemistry is left out.
  assert.deepEqual(capabilities.filter((id) => !(id in stated)), ["cap.reactions"]);
  for (const [id, item] of Object.entries(stated)) {
    assert.ok(["absent", "present"].includes(item.place), `${id}: ${item.place}`);
    if (item.place === "absent") assert.deepEqual(Object.keys(item), ["place", "why"], id);
    else assert.deepEqual(Object.keys(item), ["place", "note"], id);
    assert.ok((item.why || item.note).trim(), id);
  }
  // A single cell has no tissue: every capability of tissues is absent.
  for (const id of ["cap.junctions", "cap.grn", "cap.replacement", "cap.mechanics", "cap.sheet"]) assert.equal(stated[id].place, "absent", id);
  // A bacterium has no internal compartments.
  for (const id of ["cap.calcium", "cap.mitochondria", "cap.trafficking"]) assert.equal(stated[id].place, "absent", id);
  assert.equal(stated["cap.channels"].place, "absent");
  assert.equal(stated["cap.division"].place, "present");
  // A place is not a model: no line says that Cells models, simulates or has this organism.
  const words = JSON.stringify(stated);
  assert.ok(!/Cells (models|simulates|has a model)|the engine (models|simulates)/i.test(words.replace(/that Cells models is not one of its proteins/g, "")), "a capability speaks of a model of this organism");
});

test("sources are keyed, each with its text, where to find it and the day it was read", () => {
  const used = new Set([...species.cell.facts.flatMap((fact) => fact.sources), ...species.levels.flatMap((level) => level.sources || [])]);
  for (const [name, source] of Object.entries(species.sources)) {
    assert.ok(source.text.trim(), name);
    assert.ok(source.doi || source.url, `${name} has neither a doi nor a url`);
    if (source.url) assert.ok(source.url.startsWith("https://"), `${name}: ${source.url}`);
    assert.match(source.accessed, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(used.has(name), `${name} is a source that nothing cites`);
  }
  assert.match(species.sources.thornburg2022.licence, /NC-ND/, "the terms that allow numbers only are stated");
});

// ---------------------------------------------------------------- its side of the protein atlas

const units = Object.entries(atlas.units);
const products = [...units.flatMap(([id, unit]) => unit.products.map((product) => [id, product])), ...atlas.extra.map((product) => ["extra", product])];

test("the atlas says what it is: format, species, date, method, and what was not copied", () => {
  assert.equal(atlas.format, "cells.visualizer.species_atlas@1");
  assert.deepEqual(Object.keys(atlas), ["format", "species", "made", "method", "sources", "not_copied", "units", "extra"]);
  assert.equal(atlas.species.id, species.id);
  assert.equal(atlas.species.taxon, species.taxon);
  assert.equal(atlas.species.organism, species.organism);
  assert.equal(path.basename(ATLAS), `${atlas.species.id}.json`);
  assert.match(atlas.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(atlas.method.length >= 5 && atlas.method.every((line) => typeof line === "string" && line.trim()));
  assert.ok(atlas.not_copied.trim());
});

test("every source of the atlas states its terms, and nothing forbidden is among them", () => {
  for (const source of atlas.sources) {
    for (const field of ["name", "licence", "holds", "accessed", "cite"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), `${source.name}: ${source.url}`);
    assert.ok(!/non-?commercial|research (and|or) education only|\bNC\b/i.test(source.licence), `${source.name}: ${source.licence}`);
  }
  assert.equal(atlas.sources.find((source) => source.name === "UniProt").licence, "CC BY 4.0");
  assert.match(atlas.sources.find((source) => source.name === "GenBank").licence, /NCBI places no restrictions/);
});

test("every unit of the inventory has an entry, in the contract's words", () => {
  assert.deepEqual(units.map(([id]) => id), snapshot.units.map((unit) => unit.id));
  for (const [id, unit] of units) {
    assert.deepEqual(Object.keys(unit), ["finding", "note", "products"], id);
    assert.ok(FINDINGS.includes(unit.finding), `${id}: ${unit.finding}`);
    assert.ok(unit.note?.trim(), `${id} has no note`);
    const listed = unit.finding === "found" || unit.finding === "different family";
    assert.equal(unit.products.length > 0, listed, `${id} is '${unit.finding}' with ${unit.products.length} products`);
  }
});

test("where the inventory names candidates a search was made and is described; where it names none, nothing was looked for", () => {
  for (const unit of snapshot.units) {
    const entry = atlas.units[unit.id];
    if (unit.products?.length) {
      assert.equal(entry.finding, "none found", unit.id);
      assert.match(entry.note, /^None of the 455 protein products of its genome carries the signature of .+ \(IPR\d{6}/, unit.id);
      assert.match(entry.note, /mollicute/, `${unit.id}: the control is not given`);
      assert.match(entry.note, /human candidates carry/, `${unit.id}: no word that the search finds the family where it exists`);
    } else {
      assert.equal(entry.finding, "nothing to look for", unit.id);
    }
  }
  const counts = Object.fromEntries(FINDINGS.map((finding) => [finding, units.filter(([, unit]) => unit.finding === finding).length]));
  assert.deepEqual(counts, { found: 0, "different family": 0, "none found": 43, "nothing to look for": 6 });
});

test("the extra proteins are few, each says why it is there, names a known database and how it was found", () => {
  assert.ok(atlas.extra.length > 0 && atlas.extra.length <= 12, "extra is a handful, not a proteome");
  const databases = new Set(["uniprot", "pdb", ...atlas.sources.map((source) => key(source.name))]);
  for (const product of atlas.extra) {
    assert.ok(product.name?.trim() && product.why?.trim(), product.name);
    assert.ok(Number.isInteger(product.length) && product.length > 0, product.name);
    assert.ok(product.ids.length, `${product.name}: no identifier`);
    for (const { db, id } of product.ids) {
      assert.ok(databases.has(key(db)), `${product.name}: ${db} is not a database the atlas names`);
      assert.ok(id && !/https?:|\//.test(id), `${product.name}: ${id}`);
    }
    assert.ok(EVIDENCE_WORDS.includes(product.evidence), `${product.name}: ${product.evidence}`);
    assert.ok(product.evidence_note?.trim(), `${product.name}: no evidence note`);
    if (product.evidence === "named in a publication") {
      assert.ok(product.citation?.text?.trim() && product.citation.doi, `${product.name}: no citation`);
    } else {
      assert.equal(product.citation, null, `${product.name}: a citation without a paper's naming`);
    }
    // Every extra protein is a line of the catalogue, with the same length.
    const row = rows.find((line) => line[4] === product.ids[0].id);
    assert.ok(row, `${product.name} is not in the catalogue`);
    assert.equal(Number(row[3]), product.length, product.name);
  }
});

test("a find by annotation is a candidate: no ortholog, no counterpart, no measured function claimed, and no word about the engine", () => {
  const words = [...units.map(([, unit]) => unit.note), ...products.flatMap(([, product]) => [product.name, product.evidence_note, product.why ?? ""]), ...atlas.method, atlas.species.plain].join("\n");
  assert.ok(!/ortholog(?!\.)/i.test(words.replace(/nothing is called an ortholog/g, "")), "something is called an ortholog");
  assert.ok(!/the engine|Cells models|is modelled/i.test(words), "the atlas speaks of the engine");
  for (const product of atlas.extra) assert.match(product.evidence_note, /not measured in this strain|not a measured function in this strain/, product.name);
});

test("no machine path, no host name, and no web address on a unit or a product", () => {
  for (const [name, content] of [["species file", speciesText], ["atlas", atlasText], ["catalogue", table], ["README", readme]]) {
    assert.ok(!MACHINE.test(content), `machine path in the ${name}`);
    assert.ok(!content.includes(os.hostname()) && !/localhost/.test(content), `host name in the ${name}`);
  }
  assert.ok(!/https?:\/\//.test(JSON.stringify([atlas.units, atlas.extra])), "a unit or a product holds a web address");
});

// ---------------------------------------------------------------- the start of its catalogue

test("the catalogue has the counts its README states: one line for each protein product of the frozen annotation", () => {
  assert.deepEqual(table.split("\n")[0].split("\t"), COLUMNS);
  for (const column of COLUMNS) assert.ok(readme.includes(`| \`${column}\` |`), `the README does not explain ${column}`);
  assert.ok(rows.every((row) => row.length === COLUMNS.length), "a line has another number of columns");
  const stated = said.match(/lists the ([\d,]+) protein products of one frozen genome annotation/);
  assert.equal(rows.length, Number(stated[1]));
  assert.match(said, /GenBank \*\*CP016816\.2\*\*/);
  const kept = rows.filter((row) => row[5] === "minimal genome").length;
  const added = rows.filter((row) => row[5] === "added for manipulation");
  assert.equal(kept + added.length, rows.length, "an origin that is neither of the two");
  assert.ok(said.includes(`| of which kept from *Mycoplasma mycoides* | ${kept} |`));
  assert.equal(kept, 452);
  assert.deepEqual(added.map((row) => row[0]).sort(), ["JCVISYN3A_0913", "JCVISYN3A_0918", "JCVISYN3A_0931"]);
  assert.equal(new Set(rows.map((row) => row[0])).size, rows.length, "a locus tag is listed twice");
  assert.equal(new Set(rows.map((row) => row[4])).size, rows.length, "a protein identifier is listed twice");
  for (const row of rows) {
    assert.match(row[0], /^JCVISYN3A_\d{4}$/);
    assert.ok(Number.isInteger(Number(row[3])) && Number(row[3]) > 0, `${row[0]}: length ${row[3]}`);
    assert.ok(["essential", "quasi-essential", "non-essential"].includes(row[7]), `${row[0]}: ${row[7]}`);
    assert.ok(["yes", "no"].includes(row[8]));
    assert.equal(row[8] === "yes", row[9] !== "" && row[10] !== "", `${row[0]}: detection and copies disagree`);
    assert.match(row[11], /^UPI[0-9A-F]{10}$/);
  }
});

test("what was measured, what is an estimate and what is annotation are told apart", () => {
  const detected = rows.filter((row) => row[8] === "yes");
  const keptSeen = detected.filter((row) => row[5] === "minimal genome").length;
  assert.ok(said.includes(`**Detected:** ${detected.length} of the ${rows.length}: ${keptSeen} of the 452 kept and ${detected.length - keptSeen} of the 3 added`));
  // The species file gives the same count of the kept kinds that were seen.
  assert.ok(species.cell.facts.find((fact) => fact.label === "Proteins").value.includes(`${keptSeen} of the 452 kinds were detected`));
  const total = detected.reduce((sum, row) => sum + Number(row[9]), 0);
  const statedTotal = Number(said.match(/sum to ([\d,]+)\./)[1].replace(/,/g, ""));
  assert.ok(Math.abs(total - statedTotal) / statedTotal < 0.005, `the copies sum to ${total}, the README says ${statedTotal}`);
  assert.match(said, /\*\*An estimate\*\*: the measured share of the protein signal, scaled to the paper's estimate/);
  assert.match(said, /\*\*Measured\*\* by transposon mutagenesis in this strain/);
  assert.match(said, /simulated counts from any model/, "the README says no simulated count is in the table");
  assert.match(said, /UniProtKB holds no entry of this organism/);
  // An entry of another organism is named as such, never as this organism's.
  for (const row of rows.filter((line) => line[12])) assert.match(row[12], /^[A-Z0-9]+ \[(reviewed|unreviewed)\] \S/, row[0]);
  assert.match(said, /such an entry is not an entry of this organism/);
});

test("the catalogue stays small and holds no sequence", () => {
  assert.ok(table.length < 1_000_000, "the catalogue has grown past 1 MB");
  assert.ok(!/\t[ACDEFGHIKLMNPQRSTVWY]{60,}(\t|$)/m.test(table), "the table holds a protein sequence");
});

test("the README names each file the catalogue was built from, with its SHA-256", () => {
  const lines = readme.split("\n").filter((line) => /^\| .+ \| `[^`]+` \| `[^`]+` \| `[0-9a-f]{64}` \|$/.test(line));
  assert.equal(lines.length, 8, "eight files, each with its dataset folder, its name and its hash");
  for (const source of SOURCES_READ) assert.ok(lines.some((line) => line.includes(`\`${source}\``)), `${source} is not named`);
});

test("the build tool reproduces the species file, the atlas, the catalogue and its README from the downloads", { skip: absent }, async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "syn3a-atlas-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--evidence", EVIDENCE, "--datasets", DATASETS, "--out-species", path.join(out, "syn3a.species.json"), "--out-atlas", path.join(out, "syn3a.json"), "--out-catalogue", path.join(out, "syn3a")], { encoding: "utf8", timeout: 600000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(await readFile(path.join(out, "syn3a.species.json"), "utf8"), speciesText, "the species file differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a.json"), "utf8"), atlasText, "the atlas differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a", "proteins.tsv"), "utf8"), table, "the catalogue differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a", "README.md"), "utf8"), readme, "the README differs from what the tool builds");
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
