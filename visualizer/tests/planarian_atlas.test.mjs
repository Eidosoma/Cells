// The planarian side of the protein atlas (data/proteins/atlases/planarian.json) is held
// to its contract, schema/SPECIES_ATLAS.md, and to what it may and may not claim. The
// tables beside it (data/proteins/planarian/) are checked against it: the proteins it
// names, and the whole open set of the species' proteins they were drawn from. Where
// the folder of saved responses is on this machine, the build tool must reproduce the
// files from it, byte for byte; elsewhere that one check is skipped.
//
//   node --test tests/planarian_atlas.test.mjs
//   PLANARIAN_EVIDENCE=DIR node --test tests/planarian_atlas.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "planarian.json");
const FOLDER = path.join(ROOT, "data", "proteins", "planarian");
const TABLE = path.join(FOLDER, "reference_proteins.tsv");
const WHOLE = path.join(FOLDER, "predicted_proteins.tsv");
const README = path.join(FOLDER, "README.md");
const TOOL = path.join(ROOT, "tools", "build_planarian_atlas.py");
const EVIDENCE = process.env.PLANARIAN_EVIDENCE || "/mnt/workspaces/Cells/visualizer-planarian-proteins-20261114-01";

const FINDINGS = ["found", "different family", "none found", "nothing to look for"];
const EVIDENCE_WORDS = ["reviewed entry", "named in a publication", "family signature", "similarity search"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const key = (text) => String(text).toLowerCase().replace(/[^a-z0-9]/g, "");

const text = await readFile(ATLAS, "utf8");
const atlas = JSON.parse(text);
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const table = await readFile(TABLE, "utf8");
const whole = await readFile(WHOLE, "utf8");
const readme = await readFile(README, "utf8");
const units = Object.entries(atlas.units);
const products = [...units.flatMap(([id, unit]) => unit.products.map((product) => [id, product])), ...atlas.extra.map((product) => ["extra", product])];

test("the file says what it is: format, species, date, method, and what was not copied", () => {
  assert.equal(atlas.format, "cells.visualizer.species_atlas@1");
  assert.deepEqual(Object.keys(atlas), ["format", "species", "made", "method", "sources", "not_copied", "units", "extra"]);
  assert.equal(atlas.species.id, "planarian");
  assert.equal(path.basename(ATLAS), `${atlas.species.id}.json`);
  for (const field of ["label", "organism", "plain"]) assert.ok(atlas.species[field]?.trim(), `species.${field}`);
  assert.ok(Number.isInteger(atlas.species.taxon));
  assert.match(atlas.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(atlas.method.length >= 5 && atlas.method.every((line) => typeof line === "string" && line.trim()));
  assert.ok(atlas.not_copied.trim());
});

test("every source states its licence, and nothing forbidden is among them", () => {
  assert.ok(atlas.sources.length);
  for (const source of atlas.sources) {
    for (const field of ["name", "licence", "holds", "accessed", "cite"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), `${source.name}: ${source.url}`);
    assert.ok(!/non-?commercial|research (and|or) education only|\bNC\b/i.test(source.licence), `${source.name}: ${source.licence}`);
  }
  assert.equal(atlas.sources.find((source) => source.name === "UniProt").licence, "CC BY 4.0");
  assert.ok(!/xenbase/i.test(text), "Xenbase is not a source of this file");
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

test("a unit with no gene product in the inventory is not given one", () => {
  for (const unit of snapshot.units) {
    if (unit.products?.length) continue;
    assert.equal(atlas.units[unit.id].finding, "nothing to look for", unit.id);
  }
});

test("each product names entries of known databases and says how it was found", () => {
  const species = new Map(atlas.sources.filter((source) => source.db).map((source) => [source.db, source]));
  const patterns = { uniprot: /^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$/, wormbase_parasite: /^h1SMcG\d{7}$/ };
  for (const [where, product] of products) {
    const label = `${where}: ${product.name}`;
    assert.ok(product.name?.trim(), label);
    assert.ok(product.gene === null || product.gene.trim(), label);
    assert.ok(product.role === null || product.role.trim(), label);
    assert.ok(Number.isInteger(product.length) && product.length > 0, `${label}: length`);
    assert.ok(EVIDENCE_WORDS.includes(product.evidence), `${label}: ${product.evidence}`);
    assert.ok(product.evidence_note?.trim(), `${label}: no evidence note`);
    assert.ok(product.ids.length, `${label}: no id`);
    for (const { db, id } of product.ids) {
      assert.ok(db === "uniprot" || db === "pdb" || species.has(db), `${label}: database ${db}`);
      // The viewer finds a species database by its name among the sources.
      if (db !== "uniprot" && db !== "pdb") assert.equal(key(db), key(species.get(db).name), `${label}: ${db}`);
      assert.match(id, patterns[db], `${label}: ${id}`);
    }
  }
});

test("a product named in a publication carries its citation, and no other product carries one", () => {
  const named = products.filter(([, product]) => product.evidence === "named in a publication");
  assert.ok(named.length);
  for (const [where, product] of products) {
    if (product.evidence === "named in a publication") {
      assert.ok(product.citation?.text?.trim(), `${where}: ${product.name} has no citation`);
      assert.ok(product.citation.doi || product.citation.pmid, `${where}: ${product.name}: no doi or pmid`);
    } else {
      assert.equal(product.citation, null, `${where}: ${product.name}`);
    }
    if (product.citation) assert.deepEqual(Object.keys(product.citation), ["text", "doi", "pmid"]);
  }
});

test("a different family is named with the one it replaces, on the word of a paper", () => {
  const other = units.filter(([, unit]) => unit.finding === "different family");
  assert.deepEqual(other.map(([id]) => id), ["U36", "U37", "U38"]);
  for (const [id, unit] of other) {
    assert.match(unit.note, /innexin/i, id);
    assert.match(unit.note, /connexin/i, id);
    assert.match(unit.note, /\(\D+ \d{4}\)/, `${id}: the note cites no paper`);
    assert.ok(unit.products.some((product) => product.evidence === "named in a publication"), id);
  }
});

test("nothing found says what was searched, and how the search fares where the family exists", () => {
  for (const [id, unit] of units.filter(([, unit]) => unit.finding === "none found")) {
    assert.match(unit.note, /signature|nothing was searched/, `${id}: ${unit.note}`);
  }
  assert.match(atlas.units.U19.note, /\d+ UniProtKB entries of other flatworms/);
});

test("a find by signature is a candidate: no ortholog, no counterpart claimed, and no word about the engine", () => {
  const said = [...units.map(([, unit]) => unit.note), ...products.flatMap(([, product]) => [product.name, product.evidence_note, product.why ?? ""])].join("\n");
  assert.ok(!/ortholog/i.test(said), "something is called an ortholog");
  assert.ok(!/\b(engine|Cells models|is modelled|simulat)/i.test(said), "the units say something of the engine");
  assert.ok(!/\bis the counterpart\b|\bare the counterparts\b/i.test(said.replace(/says that it is the counterpart/g, "")), "a counterpart is claimed");
  assert.ok(atlas.method.some((line) => /candidate, never an established counterpart/.test(line)));
  const kinds = new Set(products.map(([, product]) => product.evidence));
  assert.ok(!kinds.has("similarity search") || atlas.method.some((line) => /similarity/.test(line)));
});

test("extra products each say why they are there, and are few", () => {
  assert.ok(atlas.extra.length > 0 && atlas.extra.length <= 12, "extra is a handful, not a proteome");
  for (const product of atlas.extra) assert.ok(product.why?.trim(), product.name);
});

test("no machine path, no host name, and no web address on a unit or a product", () => {
  for (const [name, content] of [["atlas", text], ["reference table", table], ["whole table", whole], ["README", readme]]) {
    assert.ok(!MACHINE.test(content), `machine path in the ${name}`);
    assert.ok(!content.includes(os.hostname()) && !/localhost/.test(content), `host name in the ${name}`);
  }
  assert.ok(!/https?:\/\//.test(JSON.stringify([atlas.units, atlas.extra])), "a unit or a product holds a web address");
});

test("the reference table has the count its README states, and holds every identifier the atlas uses and no other", () => {
  const lines = table.trimEnd().split("\n");
  const header = lines.shift().split("\t");
  assert.deepEqual(header, ["db", "id", "length", "kind", "name", "gene", "interpro", "match", "note"]);
  for (const column of header) assert.ok(readme.includes(`| \`${column}\` |`), `the README does not explain ${column}`);
  const rows = lines.map((line) => line.split("\t"));
  assert.ok(rows.every((row) => row.length === header.length), "a line has another number of columns");
  const stated = readme.match(/([\d,]+) proteins, one per line: ([\d,]+) gene models and ([\d,]+) UniProtKB entries\.\s+([\d,]+) are named by/);
  assert.ok(stated, "the README does not state the counts");
  const [all, models, entries, named] = stated.slice(1).map((count) => Number(count.replace(/,/g, "")));
  assert.equal(rows.length, all);
  assert.equal(rows.filter((row) => row[0] === "wormbase_parasite" && row[3] === "gene model").length, models);
  assert.equal(rows.filter((row) => row[0] === "uniprot").length, entries);
  const held = new Set(rows.map((row) => `${row[0]}:${row[1]}`));
  assert.equal(held.size, rows.length, "an identifier is listed twice");
  const used = new Set(products.flatMap(([, product]) => product.ids.map(({ db, id }) => `${db}:${id}`)));
  for (const id of used) assert.ok(held.has(id), `${id} is in the atlas but not in the reference table`);
  assert.equal(used.size, named, "the README's count of the proteins the atlas names");
  // A line is there because the atlas names it, or because it is joined to one the atlas names.
  const other = { uniprot: "wormbase_parasite", wormbase_parasite: "uniprot" };
  for (const row of rows) {
    const joined = row[7].split(";").filter(Boolean).map((id) => `${other[row[0]]}:${id}`);
    assert.ok(used.has(`${row[0]}:${row[1]}`) || joined.some((id) => used.has(id)), `${row[1]} is in the table but the atlas does not use it`);
    // A joined pair says the same thing from both sides.
    for (const id of joined) assert.ok(byId(rows).get(id)[7].split(";").includes(row[1]), `${row[1]} and ${id}`);
  }
  assert.ok(table.length < 200000, "the table in the repository holds only what the atlas uses");
});

function byId(rows) {
  return new Map(rows.map((row) => [`${row[0]}:${row[1]}`, row]));
}

test("the whole open set has the counts its README states, and holds every line of the reference table", () => {
  const lines = whole.trimEnd().split("\n");
  assert.equal(lines.shift(), table.split("\n")[0], "the two tables have the same columns");
  const rows = lines.map((line) => line.split("\t"));
  assert.ok(rows.every((row) => row.length === 9), "a line has another number of columns");
  const stated = readme.match(/([\d,]+) lines, each one protein, tab-separated under a header line: ([\d,]+) gene models\s+with a predicted protein, then ([\d,]+) UniProtKB entries/);
  assert.ok(stated, "the README does not state the whole table's counts");
  const [all, models, entries] = stated.slice(1).map((count) => Number(count.replace(/,/g, "")));
  assert.equal(rows.length, all);
  assert.equal(rows.filter((row) => row[0] === "wormbase_parasite" && row[3] === "gene model").length, models);
  assert.equal(rows.filter((row) => row[0] === "uniprot").length, entries);
  assert.equal(new Set(rows.map((row) => `${row[0]}:${row[1]}`)).size, rows.length, "an identifier is listed twice");
  const held = new Set(lines);
  for (const line of table.trimEnd().split("\n").slice(1)) assert.ok(held.has(line), `not in the whole table: ${line.slice(0, 60)}`);
  // What the README says of how each entry is known is what the table holds.
  const levels = new Map();
  for (const row of rows.filter((row) => row[0] === "uniprot")) levels.set(row[8], (levels.get(row[8]) || 0) + 1);
  for (const [level, count] of levels) assert.ok(readme.includes(`${count.toLocaleString("en-US")} "${level}"`), `the README does not give ${count} for ${level}`);
  // The user's bound for data in git: no file of several megabytes, and no sequences.
  assert.ok(whole.length < 3_000_000, "the whole table has grown past 3 MB");
  assert.ok(!/\t[ACDEFGHIKLMNPQRSTVWY]{60,}(\t|$)/m.test(whole), "the table holds a protein sequence");
});

test("the open set is said to be predicted and not measured, and not to stand in for the library", () => {
  const said = readme.replace(/\s+/g, " ");
  assert.match(said, /predicted from the genome and from transcripts, not measured/);
  assert.match(said, /Nothing here says which of these proteins the animal makes/);
  // The count given where the README first names the table is the table's own.
  const lines = whole.trimEnd().split("\n").length - 1;
  assert.ok(said.includes(`the ${lines.toLocaleString("en-US")} proteins on open record for the species`), "the opening count is not the table's");
});

test("the README says plainly that the library of about 10,000 proteins was not imported", () => {
  const said = readme.replace(/\s+/g, " ");
  assert.match(said, /library of about 10,000 proteins was not imported/);
  assert.match(said, /It is not the library and does not stand in for it/);
  assert.match(readme, /doi:10\.1016\/j\.devcel\.2025\.08\.015/);
  assert.match(atlas.not_copied, /10,000/);
  assert.ok(!/engine (uses|reads) (it|this)/i.test(readme.replace(/nothing in the\s+engine reads it/g, "")));
});

test("the build tool reproduces the atlas, both tables and the README from the saved responses", { skip: existsSync(path.join(EVIDENCE, "requests.json")) ? false : "the folder of saved responses is not on this machine (set PLANARIAN_EVIDENCE)" }, async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "planarian-atlas-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--evidence", EVIDENCE, "--out-atlas", path.join(out, "planarian.json"), "--out-reference", path.join(out, "planarian")], { encoding: "utf8", timeout: 600000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(await readFile(path.join(out, "planarian.json"), "utf8"), text, "the atlas differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "predicted_proteins.tsv"), "utf8"), whole, "the whole table differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "reference_proteins.tsv"), "utf8"), table, "the reference table differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "README.md"), "utf8"), readme, "the README differs from what the tool builds");
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
