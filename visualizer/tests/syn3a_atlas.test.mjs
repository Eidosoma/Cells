// The viewer's data on the minimal cell JCVI-syn3A is held to its contracts and to what it
// may and may not claim: the species file (schema/SPECIES.md), its side of the protein atlas
// (schema/SPECIES_ATLAS.md), the start of its protein catalogue (data/proteins/syn3a/) and
// where each of its proteins sits against the cell membrane (schema/SPECIES_PROTEINS.md).
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
const SHELVES = path.join(FOLDER, "shelves.json");
const README = path.join(FOLDER, "README.md");
const TOOL = path.join(ROOT, "tools", "build_syn3a_atlas.py");
// The analysis folder (the log of what was asked) and the folder of downloads (one folder
// per source, each with its MANIFEST.json).
const EVIDENCE = process.env.SYN3A_EVIDENCE || "/mnt/workspaces/Cells/visualizer-syn3a-proteins-20261114-01";
const DATASETS = process.env.SYN3A_DATASETS || "/mnt/datasets/Cells/syn3a";
// The last was added on 15 November 2026: the terms of a rule system whose results UniProt
// gives out (HAMAP), as its own page states them.
const SOURCES_READ = ["ncbi-CP016816.2", "breuer2019-elife", "ncbi-CP016816-proteins", "uniprot-syn3a", "biopython-185-protparam", "pmc-open-syn3a-licence-pass", "terms-upstream-tools"];
// Read for their terms alone; the README's table of files does not list them.
const TERMS_READ = ["terms-prosite"];
const absent = !existsSync(path.join(EVIDENCE, "requests.json"))
  ? "the request log is not on this machine (set SYN3A_EVIDENCE)"
  : [...SOURCES_READ, ...TERMS_READ].some((source) => !existsSync(path.join(DATASETS, source, "MANIFEST.json")))
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
// How a source may be used (the project's rule of 15 November 2026): only a permissive one
// may stand behind a value or a statement; the others are pointers.
const CLASSES = ["permissive", "non-commercial", "no stated terms"];
const key = (text) => String(text).toLowerCase().replace(/[^a-z0-9]/g, "");

const speciesText = await readFile(SPECIES, "utf8");
const species = JSON.parse(speciesText);
const atlasText = await readFile(ATLAS, "utf8");
const atlas = JSON.parse(atlasText);
const table = await readFile(TABLE, "utf8");
const readme = await readFile(README, "utf8");
const shelvesText = await readFile(SHELVES, "utf8");
const shelves = JSON.parse(shelvesText);
const SIDES = ["outside", "in", "inside", "not known"];
const BASES = ["stated", "predicted", "by function", "none"];
const SHELF_COLUMNS = ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"];
const said = readme.replace(/\s+/g, " ");
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const map = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const capabilities = map.capabilities.map((item) => item.id);
const rows = table.trimEnd().split("\n").slice(1).map((line) => line.split("\t"));

// ---------------------------------------------------------------- the species file

test("the species file says what it is, as the contract sets out", () => {
  assert.equal(species.format, "cells.visualizer.species@1");
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "no_further_levels", "cell", "capability_sources", "sources"]);
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
  assert.match(species.modelled.text, /Nothing of it is in the engine yet: the project's record holds an evidence audit, capability probes of the engine as it stands, and a proposed first milestone, with no engine code written for it and nothing accepted/);
  // The note that proposes it is not in the repository, so no file of it is cited.
  assert.ok(!/SOTA_SYN3A|docs\//.test(speciesText), "the species file cites a path of the repository");
});

test("every fact has a source, and every number drawn has a fact or is called the picture's choice", () => {
  const facts = species.cell.facts;
  assert.ok(facts.length >= 8);
  for (const fact of facts) {
    // A fact rests on its sources, all permissive; "see" names where more is to be read.
    assert.deepEqual(Object.keys(fact).filter((name) => name !== "see"), ["label", "value", "sources"]);
    assert.ok(fact.label.trim() && fact.value.trim());
    assert.ok(fact.sources.length, `${fact.label} has no source`);
    for (const source of fact.sources) assert.equal(species.sources[source]?.class, "permissive", `${fact.label} rests on ${source}`);
    for (const source of fact.see || []) assert.ok(species.sources[source], `${fact.label} points to ${source}, which is not a source`);
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
  // Three more are left out since 16 November 2026: the nucleus, the Golgi and the ribosomes are parts whose place
  // the viewer reads from `cell.parts` (schema/SPECIES.md): this cell has no nucleus and no Golgi, and has ribosomes.
  assert.deepEqual(capabilities.filter((id) => !(id in stated)).sort(), ["cap.golgi", "cap.nucleus", "cap.reactions", "cap.ribosomes"]);
  assert.equal(species.cell.parts.nucleus, false);
  assert.ok(!(species.cell.parts.organelles || []).includes("golgi"));
  assert.ok(species.cell.parts.ribosomes > 0);
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
  // What a capability's words rest on is named, and is permissive.
  for (const [id, sources] of Object.entries(species.capability_sources)) {
    assert.ok(id in stated, `${id} has sources and no entry`);
    assert.ok(sources.length, id);
    for (const source of sources) assert.equal(species.sources[source]?.class, "permissive", `${id} rests on ${source}`);
  }
  // Nothing is said from the whole-cell model or the division paper: what is said of
  // energy, of the proton pump and of division is said from the 2019 paper and a review.
  assert.match(stated["cap.energy"].note, /in the 2019 reconstruction of its metabolism, central metabolism is the only source of ATP/);
  assert.match(stated["cap.membrane"].note, /that is a model's reading, and no source read for this file measured the voltage of this strain/);
  assert.match(stated["cap.division"].note, /a review reports that seven of the 19 are needed together for normal division/);
  // A capability's words carry no number of their own: each number in them is a number of
  // a fact, or stands in the citation of a permissive source (the year of a paper).
  const backed = [...species.cell.facts.map((fact) => fact.value), ...Object.values(species.sources).filter((source) => source.class === "permissive").map((source) => source.text)].join(" ").replace(/,/g, "");
  for (const [id, item] of Object.entries(stated)) {
    for (const found of (item.why || item.note).replace(/,/g, "").replace(/JCVI-syn3\.0/g, "").match(/\d+(\.\d+)?/g) || []) assert.ok(new RegExp(`(^|[^\\d.])${found.replace(".", "\\.")}([^\\d]|$)`).test(backed), `${id} gives ${found}, which no fact and no permissive source's citation holds`);
  }
});

test("sources are keyed, each with its text, its licence, its class, where to find it and the day it was read", () => {
  const basis = new Set([...species.cell.facts.flatMap((fact) => fact.sources), ...species.levels.flatMap((level) => level.sources || []), ...Object.values(species.capability_sources).flat()]);
  const pointed = new Set(species.cell.facts.flatMap((fact) => fact.see || []));
  for (const [name, source] of Object.entries(species.sources)) {
    assert.ok(source.text.trim(), name);
    assert.ok(source.doi || source.url, `${name} has neither a doi nor a url`);
    if (source.url) assert.ok(source.url.startsWith("https://"), `${name}: ${source.url}`);
    assert.match(source.accessed, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(source.licence?.trim(), `${name} states no licence, and does not say that none is stated`);
    assert.ok(CLASSES.includes(source.class), `${name}: ${source.class}`);
    assert.ok(basis.has(name) || pointed.has(name), `${name} is a source that nothing cites`);
    // A source whose terms do not allow a copy is a pointer and nothing else.
    if (source.class !== "permissive") {
      assert.ok(!basis.has(name), `${name} is ${source.class} and something rests on it`);
      assert.match(source.licence, /nothing is taken from it/, name);
    }
  }
  assert.equal(species.sources.thornburg2022.class, "non-commercial");
  assert.match(species.sources.thornburg2022.licence, /NC-ND/);
  assert.equal(species.sources.pelletier2021.class, "no stated terms");
  assert.equal(species.sources.zhang2023.class, "permissive");
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
    assert.equal(source.class, "permissive", `${source.name}: the atlas takes something from a source that is ${source.class}`);
  }
  // The two papers whose terms do not allow a copy are named as places to read, and nothing more.
  assert.match(atlas.not_copied, /Nothing is taken from the 2022 whole-cell paper, which is under a non-commercial licence \(CC BY-NC-ND\), or from the 2021 paper on the genes needed for division, which states no open licence/);
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
      assert.equal(product.citation.class, "permissive", `${product.name}: named by a paper whose terms do not allow it`);
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
  assert.equal(lines.length, 15, "fifteen files, each with its dataset folder, its name and its hash");
  for (const source of SOURCES_READ) assert.ok(lines.some((line) => line.includes(`\`${source}\``)), `${source} is not named`);
});

// ---------------------------------------------------------------- the shelves: where each protein sits

test("the shelves keep their contract: one line for each protein of the catalogue, in its order", () => {
  assert.equal(shelves.format, "cells.visualizer.species_proteins@1");
  assert.equal(shelves.species, "syn3a");
  assert.match(shelves.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(shelves.from, `GenBank CP016816.2: ${rows.length} protein products`);
  assert.deepEqual(shelves.columns, SHELF_COLUMNS);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["cell"], "one membrane, so one shelf");
  for (const field of ["label", "outside", "inside"]) assert.ok(shelves.shelves[0][field]?.trim(), `the shelf's ${field}`);
  assert.deepEqual(shelves.proteins.map((row) => row[0]), rows.map((row) => row[0]), "the catalogue's proteins, in the catalogue's order");
  const groups = new Set(shelves.groups.map((group) => group.id));
  assert.equal(groups.size, shelves.groups.length, "a district is declared twice");
  for (const [index, row] of shelves.proteins.entries()) {
    assert.equal(row.length, SHELF_COLUMNS.length, row[0]);
    const [id, label, gene, shelf, side, basis, group, length, unit, marks] = row;
    const line = rows[index];
    assert.equal(label, line[2], `${id}: its name`);
    assert.equal(gene, line[1], `${id}: its gene`);
    assert.equal(length, Number(line[3]), `${id}: its length`);
    assert.equal(shelf, "cell");
    assert.ok(SIDES.includes(side), `${id}: ${side}`);
    assert.ok(BASES.includes(basis), `${id}: ${basis}`);
    assert.equal(side === "not known", basis === "none", `${id}: a protein is not placed exactly when nothing settles its side`);
    assert.ok(groups.has(group), `${id}: the district ${group} is not declared`);
    assert.equal(unit, null, `${id}: the atlas found none of its units in this organism`);
    for (const mark of Object.keys(marks)) assert.ok(shelves.marks[mark], `${id}: the mark ${mark} is not declared`);
  }
  assert.match(shelves.unit_note, /none of the law inventory's units/);
});

test("the shelves' counts add up, by side, by basis and by district, and the districts are the paper's classes", () => {
  const count = (test) => shelves.proteins.filter(test).length;
  assert.deepEqual(shelves.counts, Object.fromEntries(SIDES.map((side) => [side, count((row) => row[4] === side)])));
  assert.equal(Object.values(shelves.counts).reduce((sum, n) => sum + n, 0), rows.length);
  for (const side of SIDES) {
    for (const basis of BASES) assert.equal(shelves.by_basis[side]?.[basis] ?? 0, count((row) => row[4] === side && row[5] === basis), `${side}, ${basis}`);
  }
  const classOf = new Map(rows.map((row) => [row[0], row[6].split(" > ")]));
  for (const group of shelves.groups) {
    for (const field of ["label", "within", "from"]) assert.ok(group[field]?.trim(), `${group.id}: ${field}`);
    const members = shelves.proteins.filter((row) => row[6] === group.id);
    assert.equal(group.count, members.length, group.id);
    assert.ok(members.length > 0, `${group.id} is empty`);
    for (const side of SIDES) assert.equal(group.sides[side] ?? 0, members.filter((row) => row[4] === side).length, `${group.id}, ${side}`);
    // A district is the 2019 paper's secondary class, in its own words, under its primary class.
    for (const row of members) assert.deepEqual(classOf.get(row[0]).slice(0, 2), [group.within, group.label], row[0]);
  }
  assert.ok(shelves.groups.length >= 8 && shelves.groups.length <= 20, "a readable number of districts");
});

test("each mark is declared once, with its values, whether it is measured and its source, and agrees with the catalogue", () => {
  // A mark names its source by the name of an entry in sources, as the contract says.
  const sources = new Set(shelves.sources.map((source) => source.name));
  for (const [name, mark] of Object.entries(shelves.marks)) {
    assert.ok(mark.label?.trim(), `${name}: label`);
    assert.ok(Array.isArray(mark.values) || ["number", "text"].includes(mark.values), `${name}: values`);
    assert.equal(typeof mark.measured, "boolean", `${name}: measured`);
    assert.ok(sources.has(mark.source), `${name}: its source ${mark.source} is not among the sources`);
  }
  // The marks with a fixed meaning in the contract carry its names.
  for (const name of ["essential", "seen", "amount", "evidence", "where", "complex"]) assert.ok(shelves.marks[name], `the mark ${name}`);
  assert.deepEqual(shelves.marks.evidence.values, ["experiment", "curator", "similarity", "rule"]);
  // Measured, estimated and read from the sequence are told apart.
  assert.equal(shelves.marks.essential.measured, true);
  assert.equal(shelves.marks.seen.measured, true);
  assert.equal(shelves.marks.amount.measured, false);
  assert.match(shelves.marks.amount.note, /^An estimate/);
  assert.equal(shelves.marks.segments.measured, false);
  assert.match(shelves.marks.segments.note, /This tool's reading/);
  for (const [index, row] of shelves.proteins.entries()) {
    const line = rows[index];
    const [id, , , , side, basis, , , , marks] = row;
    assert.equal(marks.essential, line[7], `${id}: essentiality`);
    assert.equal(marks.seen, line[8] === "yes", `${id}: seen`);
    assert.equal("amount" in marks, line[8] === "yes", `${id}: an amount only where it was seen`);
    if ("amount" in marks) assert.equal(marks.amount, Number(line[9]), `${id}: its estimated copies`);
    assert.equal(marks.added === true, line[5] === "added for manipulation", `${id}: added`);
    if (marks.class) assert.equal(marks.class, line[6].split(" > ")[2], `${id}: finer class`);
    assert.equal("segments" in marks, side === "in", `${id}: stretches are counted for a protein in the membrane, and for no other`);
    if (side === "outside") assert.equal(marks.lipid_anchor, true, `${id}: outside by its lipid anchor`);
    assert.equal("stated_in" in marks, basis === "stated" || marks.where === "at the membrane", `${id}: what a reviewed entry states names the entry`);
    assert.equal("evidence" in marks, basis === "stated", `${id}: a stated side says what stands behind it`);
    if (marks.where) assert.ok(side === "inside" && basis === "predicted" && / \(by (experiment|curator|similarity|rule)\)$/.test(marks.stated_in), `${id}: at the membrane, by a reviewed entry's word, with its side read by the tool`);
    if (marks.at_start_only) assert.ok(side === "in" && marks.segments === 1, `${id}: only a single stretch at the start is marked so`);
    for (const [name, value] of Object.entries(marks)) {
      const declared = shelves.marks[name].values;
      if (Array.isArray(declared)) assert.ok(declared.includes(value), `${id}: ${name} is ${value}`);
      else assert.equal(typeof value, declared === "number" ? "number" : "string", `${id}: ${name}`);
    }
  }
  // An assembly is marked only where the record's product name gives it outright.
  for (const row of shelves.proteins) {
    const named = /^(30S|50S) ribosomal protein /.test(row[1]) ? "ribosome" : /^F0F1 ATP synthase subunit /.test(row[1]) ? "ATP synthase" : /RNA polymerase subunit /.test(row[1]) ? "RNA polymerase" : undefined;
    assert.equal(row[9].complex, named, `${row[0]}: ${row[1]}`);
  }
});

test("a side that is predicted or taken from function says so; a stated one names the other organism; nothing is placed by guess", () => {
  for (const basis of BASES) assert.ok(shelves.side_notes[basis]?.trim(), `no note for ${basis}`);
  assert.match(shelves.side_notes.predicted, /This tool's own reading of the sequence, not the output of an established predictor/);
  assert.match(shelves.side_notes.predicted, /said of mycoplasmas in general and not measured in this strain/);
  assert.match(shelves.side_notes.stated, /of another organism/);
  // A stated side that rests on no experiment says so.
  const experiments = shelves.proteins.filter((row) => row[9].evidence === "experiment").length;
  assert.equal(/None of these statements rests on an experiment/.test(shelves.side_notes.stated), experiments === 0);
  assert.match(shelves.side_notes["by function"], /never used to place a transport protein/);
  assert.match(shelves.side_notes.none, /it is not placed/);
  for (const row of shelves.proteins) {
    const [id, label, , , side, basis, group, , , marks] = row;
    // Function places a protein inside only, and never a transport protein.
    if (basis === "by function") {
      assert.equal(side, "inside", id);
      assert.notEqual(group, "membrane-transport", `${id}: function was used to place a transport protein`);
    }
    if ("stated_in" in marks) assert.match(marks.stated_in, /^[A-Z0-9]{6,10}, \S.+: \S/, id);
    // What the annotation names plainly comes out where it should.
    if (/^(30S|50S) ribosomal protein /.test(label)) assert.equal(side, "inside", `${id}: a ribosomal protein`);
    if (/permease/i.test(label)) assert.equal(side, "in", `${id}: a permease`);
    if (/ATP-binding protein/.test(label)) assert.equal(side, "inside", `${id}: an ATP-binding part of a transporter`);
  }
  assert.ok(shelves.counts["not known"] > 0, "the count of proteins that are not placed is a result");
  // No word that the engine models any of it.
  assert.ok(!/engine (models|runs|uses|reads)|modelled in the engine/i.test(JSON.stringify([shelves.side_notes, shelves.marks, shelves.unit_note])));
});

test("the reading of the sequences fares against what is known as the files say", () => {
  const { inside_by_class: inside, permeases, stated, lipoprotein_profile: profile, membrane } = shelves.checks;
  assert.equal(stated.reading_agrees, stated.proteins, "a stated place the reading disagrees with");
  assert.equal(stated.proteins, shelves.proteins.filter((row) => row[5] === "stated").length);
  assert.equal(Object.values(stated.by_evidence).reduce((sum, n) => sum + n, 0), stated.proteins);
  assert.equal(stated.said_to_be_at_the_membrane.length, shelves.proteins.filter((row) => row[9].where === "at the membrane").length);
  assert.equal(permeases.read_as_spanning, permeases.proteins, "a permease the reading misses");
  assert.equal(permeases.proteins, shelves.proteins.filter((row) => /permease/i.test(row[1])).length);
  assert.ok(inside.proteins > 150, "the proteins whose class places them inside are many");
  assert.ok(inside.read_as_spanning.length <= 2, "more than two of the proteins that work inside the cell are read as membrane-spanning");
  assert.ok(inside.with_a_hydrophobic_stretch > inside.read_as_spanning.length, "the condition on charged residues does its work");
  assert.equal(inside.with_a_hydrophobic_stretch, shelves.proteins.filter((row) => row[5] === "by function").length, "each of them is placed by its function");
  assert.equal(profile.sequences, profile.kept + profile.set_aside.length);
  assert.equal(profile.kept, profile.placed_outside + profile.placed_in);
  assert.equal(profile.placed_outside, shelves.counts.outside);
  assert.equal(profile.kept, shelves.proteins.filter((row) => row[9].lipid_anchor).length);
  // Whose rules stand behind the stated places: counted, and each system is a source of the file.
  const systems = stated.by_rule_system;
  assert.equal(Object.values(systems).reduce((sum, item) => sum + item.sides, 0), shelves.proteins.filter((row) => row[5] === "stated" && row[9].evidence === "rule").length, "a stated side by a rule names no rule system");
  for (const [system, item] of Object.entries(systems)) {
    const source = shelves.sources.find((entry) => entry.name === system);
    assert.ok(source?.through, `${system} stands behind ${item.sides} stated sides and is not a source read through another`);
  }
  assert.equal(membrane.in_or_on, shelves.counts.in + shelves.counts.outside);
  // The whole-cell model's own count is under a non-commercial licence: it is pointed to, not repeated.
  assert.deepEqual(Object.keys(membrane), ["in_or_on", "seen", "estimated_copies", "all_estimated_copies"]);
  assert.match(said, /That paper is under a non-commercial licence, so its numbers are not repeated here/);
  assert.ok(membrane.estimated_copies < membrane.all_estimated_copies);
  const spanning = shelves.checks.in_the_membrane;
  assert.equal(spanning.proteins, shelves.counts.in);
  assert.equal(spanning.one_stretch, shelves.proteins.filter((row) => row[4] === "in" && row[9].segments === 1).length);
  assert.equal(spanning.one_stretch_at_the_start, shelves.proteins.filter((row) => row[9].at_start_only).length);
  assert.ok(said.includes(`${spanning.one_stretch} have one stretch only, and for ${spanning.one_stretch_at_the_start} of those it is at the very start`), "the README does not say how many membrane calls rest on one stretch at the start");
  const copies = shelves.proteins.filter((row) => row[4] === "in" || row[4] === "outside").reduce((sum, row) => sum + (row[9].amount ?? 0), 0);
  assert.ok(Math.abs(copies - membrane.estimated_copies) / membrane.estimated_copies < 0.01, `the membrane proteins' copies sum to ${copies}, the file says ${membrane.estimated_copies}`);
  // The README gives the same numbers.
  for (const [words, n] of [["Outside the cell, anchored to the membrane's outer face", shelves.counts.outside], ["In the membrane, spanning it", shelves.counts.in], ["Inside the cell, free or attached to the membrane's inner face", shelves.counts.inside], ["Not known", shelves.counts["not known"]]]) {
    assert.ok(said.includes(`| ${words} | ${n} |`), `the README does not give ${n} for: ${words}`);
  }
  assert.ok(said.includes(`Here ${shelves.counts.in} proteins span the membrane and ${shelves.counts.outside} are anchored on it, ${membrane.in_or_on} together.`));
  assert.ok(said.includes(`All ${permeases.proteins} proteins that the annotation calls a permease are read as membrane-spanning`));
  assert.match(said, /no list of the model's was copied or compared/);
  assert.match(said, /It gives no topology/);
});

test("the shelves name their sources with their terms, copy from none that forbids it, hold no machine path and stay small", () => {
  for (const source of shelves.sources) {
    for (const field of ["name", "cite", "url", "licence", "accessed", "holds"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), `${source.name}: ${source.url}`);
    assert.match(source.accessed, /^\d{4}-\d{2}-\d{2}$/);
  }
  assert.equal(new Set(shelves.sources.map((source) => source.name)).size, shelves.sources.length);
  // What the file holds was taken from permissive sources. A paper under a non-commercial
  // licence, or with no stated terms, is a pointer: it says that nothing is taken from it.
  // A rule system of another owner whose results UniProt gives out is a source of its
  // own, with its own terms and class, and `through` names the source of this file in
  // whose records its results were read: PROSITE, whose lipoprotein profile's matches
  // UniProt's archive records, and HAMAP, whose family rules stand behind stated places.
  // By the user's ruling of 15 November 2026 a value stands on the terms of the database
  // it was read from, and the tool behind it is named and counted.
  for (const source of shelves.sources) {
    assert.ok(CLASSES.includes(source.class), `${source.name}: ${source.class}`);
    const open = /^CC BY [24]\.0$|BSD 3-Clause|no restrictions on the use or distribution/.test(source.licence);
    if (source.class === "permissive") assert.ok(open, `${source.name}: ${source.licence}`);
    else assert.ok(!open && /^(CC BY-NC|No open licence stated)/.test(source.licence), `${source.name}: ${source.licence}`);
    if (source.through) {
      const database = shelves.sources.find((item) => item.name === source.through);
      assert.ok(database?.class === "permissive" && !database.through, `${source.name} is read through ${source.through}`);
      assert.match(source.holds, /^Nothing was downloaded from it but its statement of terms/, source.name);
    } else if (source.class !== "permissive") assert.match(source.holds, /^Nothing is taken from it: a pointer to /, source.name);
  }
  assert.deepEqual(shelves.sources.filter((source) => source.class !== "permissive").map((source) => source.name), ["PROSITE", "Kyte and Doolittle 1982", "L'Hernault and Arduengo 1992", "Chambaud and others 1999", "Thornburg and others 2022"]);
  assert.deepEqual(shelves.sources.filter((source) => source.through).map((source) => [source.name, source.class, source.through]), [["PROSITE", "non-commercial", "UniParc"], ["HAMAP", "permissive", "UniProtKB"]]);
  // What rests on PROSITE's profile is counted in its entry, and the counts are the lines'.
  const anchored = shelves.proteins.filter((row) => row[9].lipid_anchor);
  const prosite = shelves.sources.find((source) => source.name === "PROSITE");
  assert.ok(prosite.holds.includes(`the mark lipid_anchor of ${anchored.length} proteins rests on those matches, ${anchored.filter((row) => row[4] === "outside").length} of them placed outside and ${anchored.filter((row) => row[4] === "in").length} in the membrane`), prosite.holds);
  assert.equal(shelves.marks.lipid_anchor.source, "UniParc");
  assert.match(shelves.marks.lipid_anchor.note, /a profile of PROSITE, whose own terms are non-commercial \(CC BY-NC-ND 4\.0\)/);
  // The rule the values stand on is said with them, as the project's rule and not as law.
  assert.match(shelves.marks.lipid_anchor.note, /By the project's rule \(the user, 15 November 2026\), a value stands on the terms of the database it was read from, and the tool behind it is named and counted\.$/);
  assert.match(said, /\*\*The project's rule \(the user, 15 November 2026\): a value stands on the terms of the database it was read from, and the tool behind it is named and counted\.\*\*/);
  assert.match(said, /This is the project's rule, and not a legal opinion\./);
  assert.ok(!/not settled here/.test(said), "the README still says the question is open");
  for (const source of shelves.sources.filter((item) => item.through)) assert.ok(readme.includes(`| ${source.name} | ${source.licence} | ${source.class} | ${source.through} | `), `the README's table does not list ${source.name}`);
  for (const mark of Object.values(shelves.marks)) {
    const source = shelves.sources.find((item) => item.name === mark.source);
    assert.equal(source.class, "permissive", `a mark rests on ${source.name}, whose terms do not allow a copy`);
  }
  // The window and the level of the reading, and where lipoproteins sit, are said from open papers.
  assert.match(shelves.side_notes.predicted, /\(Paulet and others 2011 state it\)/);
  assert.match(shelves.side_notes.predicted, /\(Christodoulides and others 2018, said of mycoplasmas in general and not measured in this strain\)/);
  assert.ok(!MACHINE.test(shelvesText), "machine path in the shelves");
  assert.ok(!shelvesText.includes(os.hostname()) && !/localhost/.test(shelvesText), "host name in the shelves");
  assert.ok(shelvesText.length < 1_000_000, "the shelves have grown past 1 MB");
  assert.ok(!/[ACDEFGHIKLMNPQRSTVWY]{40,}/.test(shelvesText), "the shelves hold a protein sequence");
  // One protein to a line, so that a change shows as the lines it touches.
  assert.equal(shelvesText.split("\n").filter((line) => line.startsWith('  ["JCVISYN3A_')).length, rows.length);
});

test("the build tool reproduces the species file, the atlas, the catalogue, the shelves and the README from the downloads", { skip: absent }, async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "syn3a-atlas-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--evidence", EVIDENCE, "--datasets", DATASETS, "--out-species", path.join(out, "syn3a.species.json"), "--out-atlas", path.join(out, "syn3a.json"), "--out-catalogue", path.join(out, "syn3a")], { encoding: "utf8", timeout: 600000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(await readFile(path.join(out, "syn3a.species.json"), "utf8"), speciesText, "the species file differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a.json"), "utf8"), atlasText, "the atlas differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a", "proteins.tsv"), "utf8"), table, "the catalogue differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a", "shelves.json"), "utf8"), shelvesText, "the shelves differ from what the tool builds");
    assert.equal(await readFile(path.join(out, "syn3a", "README.md"), "utf8"), readme, "the README differs from what the tool builds");
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
