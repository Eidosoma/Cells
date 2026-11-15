// The viewer's data on the bacterium Mycoplasma pneumoniae M129 is held to its contracts
// and to what it may and may not claim: the species file (schema/SPECIES.md), its side of
// the protein atlas (schema/SPECIES_ATLAS.md), its protein catalogue and the shelves made
// from it (schema/SPECIES_PROTEINS.md), both in data/proteins/mpneumoniae/. Where the
// downloads and the request log are on this machine, the build tool must reproduce the
// files from them, byte for byte; where either is absent that one check is skipped.
//
//   node --test tests/mpneumoniae_atlas.test.mjs
//   MPNEUMONIAE_DATASETS=DATA MPNEUMONIAE_EVIDENCE=DIR node --test tests/mpneumoniae_atlas.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const SPECIES = path.join(ROOT, "data", "species", "mpneumoniae.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "mpneumoniae.json");
const FOLDER = path.join(ROOT, "data", "proteins", "mpneumoniae");
const TABLE = path.join(FOLDER, "proteins.tsv");
const SHELVES = path.join(FOLDER, "shelves.json");
const README = path.join(FOLDER, "README.md");
const TOOL = path.join(ROOT, "tools", "build_mpneumoniae_atlas.py");
// The analysis folder (the log of what was asked) and the folder of downloads (one folder
// per source, each with its MANIFEST.json).
const EVIDENCE = process.env.MPNEUMONIAE_EVIDENCE || "/mnt/workspaces/Cells/visualizer-mpneumoniae-proteins-20261115-01";
const DATASETS = process.env.MPNEUMONIAE_DATASETS || "/mnt/datasets/Cells/mpneumoniae";
const SOURCES_READ = ["ncbi-U00089.2", "ncbi-NC_000912.1", "uniprot-mpneumoniae", "lluchsenar2015-msb", "pmc-open-mpneumoniae-papers", "pubmed-mpneumoniae-papers", "emdb-EMD-53631", "terms-mpneumoniae-sources"];
const absent = !existsSync(path.join(EVIDENCE, "requests.json"))
  ? "the request log is not on this machine (set MPNEUMONIAE_EVIDENCE)"
  : SOURCES_READ.some((source) => !existsSync(path.join(DATASETS, source, "MANIFEST.json")))
    ? "the downloads are not on this machine (set MPNEUMONIAE_DATASETS)"
    : false;

const LEVELS = ["molecules", "cell", "tissue", "organ", "organism"];
const STATES = ["generic", "proposed", "modelled"];
const CELL_KINDS = { sphere: ["across_um"], capsule: ["length_um", "across_um"], prism: ["sides", "across_um", "radius_um", "height_um", "corner_um", "edge_um"] };
const PARTS = ["membranes", "wall", "nucleus", "organelles", "chromosome_kbp", "ribosomes"];
const FINDINGS = ["found", "different family", "none found", "nothing to look for"];
const EVIDENCE_WORDS = ["reviewed entry", "named in a publication", "family signature", "similarity search"];
const COLUMNS = ["locus_tag", "gene", "product", "length", "protein_id", "uniprotkb", "uniprotkb_name", "uniprotkb_length", "protein_existence", "functional_class", "essentiality", "essentiality_relaxed", "uniparc", "interpro"];
const ESSENTIALITY = ["essential", "fitness", "non-essential", "non-essential (repeats)"];
const EXISTENCE = ["evidence at protein level", "evidence at transcript level", "inferred from homology", "predicted", "uncertain"];
const SHELF_COLUMNS = ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"];
const SIDES = ["outside", "in", "inside", "not known"];
const BASES = ["stated", "predicted", "by function", "none"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const number = (text) => Number(String(text).replace(/,/g, ""));

const speciesText = await readFile(SPECIES, "utf8");
const species = JSON.parse(speciesText);
const atlasText = await readFile(ATLAS, "utf8");
const atlas = JSON.parse(atlasText);
const table = await readFile(TABLE, "utf8");
const shelvesText = await readFile(SHELVES, "utf8");
const shelves = JSON.parse(shelvesText);
const readme = await readFile(README, "utf8");
const said = readme.replace(/\s+/g, " ");
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const map = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const capabilities = map.capabilities.map((item) => item.id);
const rows = table.trimEnd().split("\n").slice(1).map((line) => line.split("\t"));
const column = (name) => COLUMNS.indexOf(name);

// ---------------------------------------------------------------- the species file

test("the species file says what it is, as the contract sets out", () => {
  assert.equal(species.format, "cells.visualizer.species@1");
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "order", "default", "made", "modelled", "levels", "no_further_levels", "cell", "sources"]);
  assert.equal(species.id, "mpneumoniae");
  assert.equal(path.basename(SPECIES), `${species.id}.json`);
  assert.equal(species.label, "M. pneumoniae");
  assert.equal(species.order, 40);
  assert.equal(species.default, false);
  assert.ok(Number.isInteger(species.taxon));
  assert.match(species.made, /^\d{4}-\d{2}-\d{2}$/);
  for (const field of ["organism", "plain"]) assert.ok(species[field].trim(), field);
});

test("it is a single cell: molecules and one cell, with a sentence where the other levels would be", () => {
  assert.deepEqual(species.levels.map((level) => level.id), ["molecules", "cell"]);
  for (const level of species.levels) assert.ok(LEVELS.includes(level.id));
  assert.ok(species.no_further_levels.trim());
  const cell = species.levels[1];
  assert.ok(Object.keys(CELL_KINDS).includes(cell.shape.kind), cell.shape.kind);
  for (const [name, value] of Object.entries(cell.shape)) {
    if (name === "kind") continue;
    assert.ok(CELL_KINDS[cell.shape.kind].includes(name), `${name} is not a parameter of a ${cell.shape.kind}`);
    assert.ok(typeof value === "number" && value > 0, name);
  }
  // The shape cannot show the cell's tip, and the note says so.
  assert.equal(cell.shape.kind, "capsule");
  assert.match(cell.note, /attachment organelle/);
  assert.match(cell.note, /cannot show/);
});

test("what Cells models of it is said plainly: audited by the record's decision, and nothing in the engine", () => {
  assert.ok(STATES.includes(species.modelled.state));
  assert.equal(species.modelled.state, "proposed");
  assert.match(species.modelled.text, /audited beside the minimal-cell track on JCVI-syn3A \(decision D173/);
  assert.match(species.modelled.text, /Nothing of it is in the engine, and no model of it has run/);
  // The user's note is not in the repository, so no file of it is cited.
  assert.ok(!/SOTA_SYN3A|docs\//.test(speciesText), "the species file cites a path of the repository");
});

test("every fact has a source, and every number drawn has a fact or is called the picture's choice", () => {
  const facts = species.cell.facts;
  assert.ok(facts.length >= 8);
  for (const fact of facts) {
    assert.deepEqual(Object.keys(fact), ["label", "value", "sources"]);
    assert.ok(fact.value.trim() && fact.sources.length, fact.label);
    for (const source of fact.sources) assert.ok(species.sources[source], `${fact.label} names a source that is not listed: ${source}`);
  }
  const value = (label) => facts.find((fact) => fact.label === label).value;
  for (const part of Object.keys(species.cell.parts)) assert.ok(PARTS.includes(part), `${part} is not a part the viewer can draw`);
  assert.deepEqual(species.cell.parts, { membranes: 1, wall: false, nucleus: false, chromosome_kbp: 816, ribosomes: 150 });
  // The drawn numbers against the facts: the length and width are the upper ends of the
  // ranges, the ribosome count the upper of the two counts, and the note says so.
  const cell = species.levels[1];
  assert.deepEqual(cell.shape, { kind: "capsule", length_um: 2, across_um: 0.2 });
  assert.match(value("Shape and size"), /1 to 2 µm long and 0\.1 to 0\.2 µm wide/);
  assert.match(cell.note, /2 µm long and 0\.2 µm across, the upper ends of the ranges/);
  assert.match(value("Ribosomes"), /about 140 to 150/);
  assert.match(cell.note, /150 ribosomes/);
  assert.match(value("Chromosome"), /816,394 base pairs/);
  assert.match(value("Envelope"), /one membrane.*no cell wall/);
  for (const source of cell.sources) assert.ok(species.sources[source], source);
});

test("each of the map's capabilities has a place or is said to be absent, with why", () => {
  const stated = species.cell.capabilities;
  for (const id of Object.keys(stated)) assert.ok(capabilities.includes(id), `${id} is not a capability of the map`);
  for (const [id, item] of Object.entries(stated)) {
    assert.ok(["present", "absent"].includes(item.place), `${id}: ${item.place}`);
    if (item.place === "absent") assert.ok(item.why?.trim() && !("note" in item), `${id} is absent without a why`);
    else assert.ok(item.note?.trim() && !("why" in item), `${id} is present without a note`);
  }
  const absentOnes = Object.entries(stated).filter(([, item]) => item.place === "absent").map(([id]) => id).sort();
  assert.deepEqual(absentOnes, ["cap.calcium", "cap.channels", "cap.grn", "cap.junctions", "cap.mechanics", "cap.mitochondria", "cap.replacement", "cap.sheet", "cap.trafficking"]);
  // Left out, a capability has a place: only cell chemistry is.
  assert.deepEqual(capabilities.filter((id) => !(id in stated)), ["cap.reactions"]);
  // Where a placement is judgement and not a source's word, the note says so.
  assert.match(stated["cap.repair"].note, /No source read for this file/);
  assert.match(stated["cap.membrane"].note, /the model's estimate, and no source read for this file measured the voltage/);
  // The one channel-like protein is named, and is not called an ion channel.
  assert.match(stated["cap.channels"].why, /GlpF.*it is not an ion channel/);
});

test("sources are keyed, each with its text, where to find it and the day it was read", () => {
  const keys = Object.keys(species.sources);
  assert.ok(keys.length >= 8);
  for (const [key, source] of Object.entries(species.sources)) {
    assert.ok(source.text?.trim(), key);
    assert.ok(source.doi || source.url, `${key} gives no doi and no url`);
    assert.match(source.accessed, /^\d{4}-\d{2}-\d{2}$/, key);
    if (source.url) assert.ok(source.url.startsWith("https://"), key);
  }
  // The papers under non-commercial terms say that only numbers were taken from them.
  for (const key of ["maier2011", "wodke2013"]) assert.match(species.sources[key].licence, /CC BY-NC-SA 3\.0.*tables are not copied/);
  assert.ok(!MACHINE.test(speciesText) && !speciesText.includes(os.hostname()), "a machine path or host name in the species file");
});

// ---------------------------------------------------------------- its side of the atlas

test("the atlas says what it is: format, species, date, method, and what was not copied", () => {
  assert.equal(atlas.format, "cells.visualizer.species_atlas@1");
  assert.deepEqual(Object.keys(atlas), ["format", "species", "made", "method", "sources", "not_copied", "units", "extra"]);
  assert.equal(atlas.species.id, species.id);
  assert.equal(atlas.species.taxon, species.taxon);
  assert.equal(path.basename(ATLAS), `${atlas.species.id}.json`);
  assert.match(atlas.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(atlas.method.length >= 5 && atlas.method.every((line) => typeof line === "string" && line.trim()));
  assert.match(atlas.not_copied, /non-commercial licences/);
});

test("every source of the atlas states its terms, and nothing forbidden is among them", () => {
  for (const source of atlas.sources) {
    for (const field of ["name", "licence", "holds", "accessed", "cite"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), source.name);
    assert.ok(!/non-?commercial|\bNC\b/i.test(source.licence), `${source.name}: ${source.licence}`);
  }
  assert.equal(atlas.sources.find((source) => source.name === "UniProt").licence, "CC BY 4.0");
  assert.match(atlas.sources.find((source) => source.name === "GenBank").licence, /NCBI places no restrictions on the use or distribution of the GenBank data/);
});

test("every unit of the inventory has an entry, in the contract's words", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  for (const [id, unit] of Object.entries(atlas.units)) {
    assert.deepEqual(Object.keys(unit), ["finding", "note", "products"], id);
    assert.ok(FINDINGS.includes(unit.finding), `${id}: ${unit.finding}`);
    assert.ok(unit.note.trim(), id);
    assert.equal(unit.products.length > 0, ["found", "different family"].includes(unit.finding), id);
  }
});

test("where the inventory names candidates a search was made and is described; where it names none, nothing was looked for", () => {
  for (const unit of snapshot.units) {
    const entry = atlas.units[unit.id];
    if (unit.products?.length) {
      assert.equal(entry.finding, "none found", unit.id);
      assert.match(entry.note, /^None of the 688 protein products of its genome carries the signature of .+ \(IPR\d{6}/, unit.id);
      // The zero has a control: what the same search finds in the organism's class of bacteria.
      assert.match(entry.note, /UniProtKB (holds \d+ entr(y|ies)|entry) of (any )?mollicutes?/, unit.id);
    } else {
      assert.equal(entry.finding, "nothing to look for", unit.id);
    }
  }
});

test("the extra proteins are few, each says why it is there, names a known database and how it was found", () => {
  assert.ok(atlas.extra.length > 0 && atlas.extra.length <= 12, "extra is a handful, not a proteome");
  const known = ["uniprot", "pdb"];
  for (const product of atlas.extra) {
    assert.ok(product.why?.trim() && product.name.trim(), product.name);
    assert.ok(EVIDENCE_WORDS.includes(product.evidence), `${product.name}: ${product.evidence}`);
    assert.ok(product.evidence_note.trim(), product.name);
    assert.ok(product.ids.length && product.ids.every((id) => known.includes(id.db) && /^[A-Z0-9]+$/.test(id.id)), product.name);
    assert.equal(Boolean(product.citation), product.evidence === "named in a publication", product.name);
    // A reviewed entry is a curated one, and the note says its function was not measured here.
    if (product.evidence === "reviewed entry") assert.match(product.evidence_note, /reviewed UniProtKB entry.*not measured in this organism/, product.name);
    // Each is a line of the catalogue, with the same accession.
    const locus = /Locus (MPN_\d{3})/.exec(product.evidence_note)[1];
    const row = rows.find((line) => line[0] === locus);
    assert.equal(row[column("uniprotkb")], product.ids[0].id, product.name);
  }
});

test("a find by annotation is a candidate: no ortholog, no counterpart, no measured function claimed, and no word about the engine", () => {
  const words = JSON.stringify([atlas.units, atlas.extra, atlas.method, atlas.species]);
  assert.ok(!/ortholog/i.test(words.replace(/nothing is called an ortholog/gi, "")), "an ortholog is claimed");
  assert.ok(!/established counterpart|is the counterpart/i.test(words));
  assert.ok(!/the engine (models|uses|reads)|Cells models (this|its)/i.test(words), "a claim about the engine");
});

test("no machine path, no host name, and no web address on a unit or a product", () => {
  for (const [name, content] of [["atlas", atlasText], ["catalogue", table], ["shelves", shelvesText], ["README", readme]]) {
    assert.ok(!MACHINE.test(content), `machine path in the ${name}`);
    assert.ok(!content.includes(os.hostname()) && !/localhost/.test(content), `host name in the ${name}`);
  }
  assert.ok(!/https?:\/\//.test(JSON.stringify([atlas.units, atlas.extra])), "a unit or a product holds a web address");
});

// ---------------------------------------------------------------- the catalogue

test("the catalogue has the counts its README states: one line for each protein product of the frozen annotation", () => {
  assert.deepEqual(table.split("\n")[0].split("\t"), COLUMNS);
  assert.ok(rows.every((row) => row.length === COLUMNS.length), "a line has another number of columns");
  for (const name of COLUMNS) assert.ok(readme.includes(`| \`${name}\` |`), `the README does not explain ${name}`);
  const stated = said.match(/lists the ([\d,]+) protein products of one frozen genome annotation/);
  assert.equal(rows.length, number(stated[1]));
  assert.equal(rows.length, 688);
  // The locus tags are the record's, MPN_001 to MPN_688, each once and in order.
  assert.deepEqual(rows.map((row) => row[0]), Array.from({ length: 688 }, (_, index) => `MPN_${String(index + 1).padStart(3, "0")}`));
  assert.match(said, /GenBank \*\*U00089\.2\*\*/);
  for (const row of rows) {
    assert.ok(Number(row[column("length")]) > 0, row[0]);
    assert.match(row[column("protein_id")], /^[A-Z]{3}\d{5}\.\d$/, row[0]);
    assert.match(row[column("uniparc")], /^UPI[0-9A-F]{10}$/, row[0]);
    assert.ok(ESSENTIALITY.includes(row[column("essentiality")]) && ESSENTIALITY.includes(row[column("essentiality_relaxed")]), row[0]);
    assert.match(row[column("functional_class")], /^[A-Z]: \S/, row[0]);
    if (row[column("uniprotkb")]) {
      assert.match(row[column("uniprotkb")], /^[A-Z][0-9][A-Z0-9]{3}[0-9]$/, row[0]);
      assert.ok(EXISTENCE.includes(row[column("protein_existence")]) && row[column("uniprotkb_name")] && Number(row[column("uniprotkb_length")]) > 0, row[0]);
    } else {
      assert.ok(!row[column("protein_existence")] && !row[column("uniprotkb_name")], row[0]);
    }
  }
  // One protein has no curated entry, and two fragments of one gene share theirs.
  assert.deepEqual(rows.filter((row) => !row[column("uniprotkb")]).map((row) => row[0]), ["MPN_441"]);
  assert.equal(rows[303][column("uniprotkb")], rows[304][column("uniprotkb")]);
  assert.equal(new Set(rows.map((row) => row[column("uniprotkb")]).filter(Boolean)).size, 686);
  assert.match(said, /A UniProtKB entry:\*\* 687 of the 688, all reviewed/);
});

test("the counts of the literature are set side by side, and the README says which one is frozen", () => {
  for (const count of ["677", "688", "689", "694", "686"]) assert.ok(readme.includes(`| ${count} |`), `the README does not give ${count}`);
  assert.match(said, /The user expected about 700 proteins; this record has 688/);
});

test("what was measured, what is a judgement and what is annotation are told apart", () => {
  const line = (name) => readme.split("\n").find((text) => text.startsWith(`| \`${name}\` |`));
  assert.match(line("essentiality"), /\*\*Measured\*\* by transposon mutagenesis in this strain/);
  assert.match(line("protein_existence"), /UniProt's judgement of the published evidence/);
  assert.match(line("product"), /Annotation/);
  // The table of essentiality in the README is the catalogue's own tally, at both thresholds.
  const tally = (name) => ESSENTIALITY.map((word) => rows.filter((row) => row[column(name)] === word).length);
  assert.ok(readme.includes(`| stringent | ${tally("essentiality").join(" | ")} |`), "the stringent counts");
  assert.ok(readme.includes(`| relaxed | ${tally("essentiality_relaxed").join(" | ")} |`), "the relaxed counts");
  assert.deepEqual(tally("essentiality"), [342, 91, 159, 96]);
  // Measured amounts exist under non-commercial terms: the README says they are not copied.
  assert.match(said, /Both papers are under non-commercial licences, so their tables are not copied/);
  assert.ok(!COLUMNS.some((name) => /copies|abundance/.test(name)), "the catalogue carries an amount");
});

test("the catalogue stays small and holds no sequence", () => {
  assert.ok(table.length < 1_000_000);
  assert.ok(!/\t[ACDEFGHIKLMNPQRSTVWY]{60,}(\t|$)/m.test(table), "the catalogue holds a protein sequence");
});

test("the README names each file the catalogue was built from, with its SHA-256", () => {
  const listed = readme.split("\n").filter((text) => /\| `[0-9a-f]{64}` \|$/.test(text));
  assert.equal(listed.length, 8);
  for (const source of ["ncbi-U00089.2", "ncbi-NC_000912.1", "uniprot-mpneumoniae", "lluchsenar2015-msb"]) assert.ok(listed.some((text) => text.includes(`\`${source}\``)), source);
});

// ---------------------------------------------------------------- the shelves

test("the shelves say what they are, as the contract sets out", () => {
  assert.equal(shelves.format, "cells.visualizer.species_proteins@1");
  assert.deepEqual(Object.keys(shelves), ["format", "species", "made", "from", "shelves", "groups", "columns", "proteins", "side_notes", "marks", "counts", "sources"]);
  assert.equal(shelves.species, species.id);
  assert.match(shelves.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(shelves.from, "GenBank U00089.2: 688 protein products");
  // A bacterium has one shelf, its cell membrane.
  assert.deepEqual(shelves.shelves, [{ id: "cell", label: "Cell membrane", outside: "Outside the cell", inside: "Inside the cell" }]);
  assert.deepEqual(shelves.columns, SHELF_COLUMNS);
  assert.ok(shelvesText.length < 1_000_000);
});

test("one line for every protein of the catalogue, in its order, with its length", () => {
  assert.equal(shelves.proteins.length, rows.length);
  shelves.proteins.forEach((line, index) => {
    assert.equal(line.length, SHELF_COLUMNS.length);
    const [id, label, gene, shelf, side, basis, group, length, unit, marks] = line;
    assert.equal(id, rows[index][0]);
    assert.ok(label.trim(), id);
    assert.ok(gene === null || gene.trim(), id);
    assert.equal(shelf, "cell", id);
    assert.ok(SIDES.includes(side) && BASES.includes(basis), `${id}: ${side}, ${basis}`);
    // Not known and no basis go together: nothing is placed by guess.
    assert.equal(side === "not known", basis === "none", id);
    assert.ok(shelves.groups.some((item) => item.id === group), `${id}: ${group}`);
    assert.equal(length, Number(rows[index][column("length")]), id);
    // The atlas found none of the inventory's machines here, so no line has a unit.
    assert.equal(unit, null, id);
    assert.ok(marks && typeof marks === "object", id);
  });
  // The label is the curated name where there is one, and the record's product otherwise.
  shelves.proteins.forEach((line, index) => assert.equal(line[1], rows[index][column("uniprotkb_name")] || rows[index][column("product")], line[0]));
});

test("the counts are the lines' own, and the README gives the same", () => {
  const tally = Object.fromEntries(SIDES.map((side) => [side, shelves.proteins.filter((line) => line[4] === side).length]));
  assert.deepEqual(shelves.counts, tally);
  for (const side of SIDES) assert.ok(readme.includes(`| ${side} | ${tally[side]} |`), `the README's count for ${side}`);
  const bases = Object.fromEntries(BASES.map((basis) => [basis, shelves.proteins.filter((line) => line[5] === basis).length]));
  assert.match(said, new RegExp(`${bases.stated} stated by the protein's reviewed UniProtKB entry, ${bases.predicted} predicted from the sequence, ${bases["by function"]} by function, ${bases.none} not known`));
  // The count of what is not known is a result, and a large one.
  assert.ok(tally["not known"] > 200 && tally["not known"] === bases.none);
});

test("every district is a class of the 2015 paper, by its letter and the paper's name", () => {
  const letters = new Set(rows.map((row) => row[column("functional_class")].split(":")[0]));
  assert.deepEqual(shelves.groups.map((group) => group.id).sort(), [...letters].sort());
  for (const group of shelves.groups) {
    assert.ok(readme.includes(`| \`${group.id}\` | ${group.label} |`), `the README does not name class ${group.id} as the shelves do`);
    assert.match(group.from, /the 2015 essentiality paper/);
  }
  shelves.proteins.forEach((line, index) => assert.equal(line[6], rows[index][column("functional_class")].split(":")[0], line[0]));
});

test("every mark is declared, with its values, whether it is measured and its source", () => {
  const declared = shelves.marks;
  const sources = shelves.sources.map((source) => source.name);
  for (const [name, mark] of Object.entries(declared)) {
    assert.deepEqual(Object.keys(mark), ["label", "values", "measured", "source"], name);
    assert.ok(mark.label.trim() && mark.values.length && typeof mark.measured === "boolean", name);
    assert.ok(sources.includes(mark.source), `${name} names a source that is not listed: ${mark.source}`);
  }
  for (const line of shelves.proteins) {
    for (const [name, value] of Object.entries(line[9])) assert.ok(declared[name]?.values.includes(value), `${line[0]}: ${name} = ${value}`);
  }
  // Essentiality is the catalogue's, and "seen" is UniProt's evidence at protein level.
  shelves.proteins.forEach((line, index) => {
    assert.equal(line[9].essential, rows[index][column("essentiality")], line[0]);
    assert.equal(line[9].seen === true, rows[index][column("protein_existence")] === "evidence at protein level", line[0]);
  });
  // No amount is given: the measured amounts are under non-commercial terms.
  assert.ok(!Object.keys(declared).some((name) => /amount|copies|abundance/.test(name)));
});

test("how a side is known is said: the predictors are named, and the reading of lipoproteins is called this file's", () => {
  const notes = shelves.side_notes;
  assert.match(notes.predicted, /TMHMM, Memsat, Phobius/);
  assert.match(notes.predicted, /Phobius, Predotar, SignalP and TargetP/);
  assert.match(notes.predicted, /lipoprotein signal.*outer face of the membrane.*that reading is this file's/);
  assert.match(notes["by function"], /no real doubt/);
  // A stated or predicted side says what kind of evidence it rests on; the others do not.
  for (const line of shelves.proteins) assert.equal("evidence" in line[9], ["stated", "predicted"].includes(line[5]), line[0]);
  // A lipoprotein is on the outer face; a protein whose entry counts membrane-spanning segments is in the membrane.
  const outside = shelves.proteins.filter((line) => line[4] === "outside");
  assert.ok(outside.filter((line) => /lipoprotein/i.test(line[1])).length > 30, "the lipoproteins are not outside");
  assert.ok(!shelves.proteins.some((line) => /lipoprotein/i.test(line[1]) && line[4] === "inside"), "a lipoprotein is placed inside");
});

test("the attachment organelle is a mark and not a shelf; a second stated side is kept as a mark", () => {
  const tip = shelves.proteins.filter((line) => line[9].where === "attachment organelle");
  assert.ok(tip.length >= 10);
  assert.match(said, new RegExp(`The ${tip.length} proteins whose entry states that location carry the mark \`where: attachment organelle\``));
  // The adhesin P1 spans the membrane of the attachment organelle.
  const p1 = shelves.proteins.find((line) => line[0] === "MPN_141");
  assert.deepEqual([p1[4], p1[5], p1[9].where], ["in", "stated", "attachment organelle"]);
  for (const line of shelves.proteins.filter((item) => item[9].also)) {
    assert.ok(["inside", "outside"].includes(line[4]) && line[9].also !== line[4], line[0]);
  }
});

test("every source of the shelves states its terms, and the file makes no claim about the engine", () => {
  for (const source of shelves.sources) {
    for (const field of ["name", "url", "licence", "accessed", "holds"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), source.name);
    assert.ok(!/non-?commercial|\bNC\b/i.test(source.licence), `${source.name}: ${source.licence}`);
  }
  assert.ok(!/engine/i.test(shelvesText), "the shelves speak of the engine");
});

// ---------------------------------------------------------------- rebuilding

test("the build tool reproduces the species file, the atlas, the catalogue, the shelves and the README from the downloads", { skip: absent }, async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "mpneumoniae-atlas-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--evidence", EVIDENCE, "--datasets", DATASETS, "--out-species", path.join(out, "species.json"), "--out-atlas", path.join(out, "atlas.json"), "--out-catalogue", path.join(out, "catalogue")], { encoding: "utf8", timeout: 600000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(await readFile(path.join(out, "species.json"), "utf8"), speciesText, "the species file differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "atlas.json"), "utf8"), atlasText, "the atlas differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "catalogue", "proteins.tsv"), "utf8"), table, "the catalogue differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "catalogue", "shelves.json"), "utf8"), shelvesText, "the shelves differ from what the tool builds");
    assert.equal(await readFile(path.join(out, "catalogue", "README.md"), "utf8"), readme, "the README differs from what the tool builds");
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
