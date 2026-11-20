// The planarian side of the protein atlas (data/proteins/atlases/planarian.json) is held
// to its contract, schema/SPECIES_ATLAS.md, and to what it may and may not claim. The
// tables beside it (data/proteins/planarian/) are checked against it: the proteins it
// names, and the whole open set of the species' proteins they were drawn from. The
// shelves' two files (schema/SPECIES_PROTEINS.md) are held to their contract: every
// protein in one family or under "no family", a side and how it is known. Where
// the folders of saved downloads are on this machine, the build tool must reproduce the
// files from them, byte for byte; elsewhere that one check is skipped.
//
//   node --test tests/planarian_atlas.test.mjs
//   PLANARIAN_EVIDENCE=DIR PLANARIAN_DATASETS=DATA node --test tests/planarian_atlas.test.mjs

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
const DATASETS = process.env.PLANARIAN_DATASETS || "/mnt/datasets/Cells/planarian";
const SHELVES = path.join(FOLDER, "shelves.json");
const MEMBERS = path.join(FOLDER, "shelf_members.tsv");
const SIDES = ["outside", "in", "inside", "not known"];
const BASES = ["stated", "predicted", "by function", "none"];

const FINDINGS = ["found", "different family", "none found", "nothing to look for"];
// The two facts of a product (schema/SPECIES_ATLAS.md, format @2): how it was found, and what its record is.
const FOUND_BY = ["family signature", "accessory signature", "named in a publication", "similarity search"];
const ENTRIES = ["reviewed", "unreviewed", "genome annotation"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
// How a source may be used (the project's rule of 15 November 2026): only a permissive one
// may stand behind a value or a statement; the others are pointers.
const CLASSES = ["permissive", "non-commercial", "no stated terms"];
const key = (text) => String(text).toLowerCase().replace(/[^a-z0-9]/g, "");

const text = await readFile(ATLAS, "utf8");
const atlas = JSON.parse(text);
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const table = await readFile(TABLE, "utf8");
const whole = await readFile(WHOLE, "utf8");
const readme = await readFile(README, "utf8");
const shelvesText = await readFile(SHELVES, "utf8");
const shelves = JSON.parse(shelvesText);
const membersText = await readFile(MEMBERS, "utf8");
const rowsOf = (tsv) => {
  // Only the last line's end is taken off: a line may end with an empty column.
  const [head, ...lines] = tsv.replace(/\n$/, "").split("\n");
  const names = head.split("\t");
  return lines.map((line) => Object.fromEntries(line.split("\t").map((value, index) => [names[index], value])));
};
const catalogue = rowsOf(whole);
const placed = rowsOf(membersText);
const named = (columns, row) => Object.fromEntries(columns.map((name, index) => [name, row[index]]));
const families = shelves.families.map((row) => named(shelves.family_columns, row));
const parts = shelves.no_family.parts.map((row) => named(shelves.no_family.part_columns, row));
const units = Object.entries(atlas.units);
// The species' own scan (docs/PLANARIAN_ATLAS.md, "The planarian's own scan"): since 19 November 2026 the filing reads the
// entries it added beside the table's own column. A member filed by what it added is one whose `under` is an entry the
// scan added to its line, or one with only a domain, repeat or site signature whose own column holds none; its ground is
// the databases whose signatures reached that (tools/build_planarian_atlas.py, scan_ground).
const RECORD = JSON.parse(await readFile(path.join(FOLDER, "interproscan.json"), "utf8"));
const ADDED = new Map((await readFile(path.join(FOLDER, "interproscan_added.tsv"), "utf8")).trimEnd().split("\n").slice(1).map((line) => {
  const [id, field] = line.split("\t");
  return [id, Object.fromEntries(field.split(";").map((item) => [item.split(":")[0], item.split(":")[1].split(",")]))];
}));
const ownColumn = new Map(catalogue.map((row) => [row.id, row.interpro.split(";").filter(Boolean)]));
function groundOf(row) {
  const gained = ADDED.get(row.id) || {};
  if (gained[row.under]) return gained[row.under];
  if (row.under === "other-signature" && Object.keys(gained).length && !ownColumn.get(row.id).length) return [...new Set(Object.values(gained).flat())].sort();
  return null;
}
const products = [...units.flatMap(([id, unit]) => unit.products.map((product) => [id, product])), ...atlas.extra.map((product) => ["extra", product])];

test("the file says what it is: format, species, date, method, and what was not copied", () => {
  assert.equal(atlas.format, "cells.visualizer.species_atlas@2");
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
    assert.equal(source.class, "permissive", `${source.name}: the atlas takes something from a source that is ${source.class}`);
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
    assert.ok(FOUND_BY.includes(product.found_by) && ENTRIES.includes(product.entry) && !("evidence" in product), `${label}: ${product.found_by}, ${product.entry}`);
    // Its record is the database it was read from: a UniProtKB entry, or a gene model of the genome annotation.
    assert.equal(product.entry === "genome annotation", product.ids[0].db === "wormbase_parasite", `${label}: ${product.entry}`);
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
  const named = products.filter(([, product]) => product.found_by === "named in a publication");
  assert.ok(named.length);
  for (const [where, product] of products) {
    if (product.found_by === "named in a publication") {
      assert.ok(product.citation?.text?.trim(), `${where}: ${product.name} has no citation`);
      assert.ok(product.citation.doi || product.citation.pmid, `${where}: ${product.name}: no doi or pmid`);
    } else {
      assert.equal(product.citation, null, `${where}: ${product.name}`);
    }
    if (product.citation) {
      assert.deepEqual(Object.keys(product.citation), ["text", "doi", "pmid", "class"]);
      assert.ok(CLASSES.includes(product.citation.class), `${where}: ${product.name}: ${product.citation.class}`);
    }
    // A paper whose terms do not allow a copy may be cited for a name only where a
    // permissive record carries the name too, and the product says which.
    const pointer = Boolean(product.citation) && product.citation.class !== "permissive";
    assert.equal("name_record" in product, pointer, `${where}: ${product.name}`);
    if (pointer) {
      assert.equal(atlas.sources.find((source) => source.name === product.name_record.source)?.class, "permissive", `${where}: ${product.name}`);
      assert.ok(product.name_record.id?.trim(), `${where}: ${product.name}`);
      assert.ok(product.evidence_note.includes(product.name_record.id) || product.ids.some((id) => id.id === product.name_record.id), `${where}: ${product.name} does not show the record that carries its name`);
    }
  }
});

test("a different family is named with the one it replaces, on the search of signatures; the papers are pointers", () => {
  const other = units.filter(([, unit]) => unit.finding === "different family");
  assert.deepEqual(other.map(([id]) => id), ["U36", "U37", "U38"]);
  for (const [id, unit] of other) {
    assert.match(unit.note, /innexin/i, id);
    assert.match(unit.note, /connexin/i, id);
    // What the note says rests on the signatures. The two papers state no open licence:
    // they are named as places to read, and nothing is said from them.
    assert.match(unit.note, /[Bb]y (its|their) signatures/, id);
    assert.match(unit.note, /gene models carry the innexin signature and none the connexin one/, id);
    assert.match(unit.note, /More is to be read in \D+ \d{4}, on which animals have each family, and in \D+ \d{4}, on that innexin; neither states an open licence, so nothing is taken from them\./, id);
    assert.ok(unit.products.some((product) => product.found_by === "named in a publication"), id);
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
  assert.ok(atlas.method.some((line) => /no candidate for the machine's own work/.test(line)));
  const kinds = new Set(products.map(([, product]) => product.found_by));
  assert.ok(!kinds.has("similarity search") || atlas.method.some((line) => /similarity/.test(line)));
});

test("extra products each say why they are there, and are few", () => {
  assert.ok(atlas.extra.length > 0 && atlas.extra.length <= 12, "extra is a handful, not a proteome");
  for (const product of atlas.extra) assert.ok(product.why?.trim(), product.name);
});

test("no machine path, no host name, and no web address on a unit or a product", () => {
  for (const [name, content] of [["atlas", text], ["reference table", table], ["whole table", whole], ["README", readme], ["shelves", shelvesText], ["members' table", membersText]]) {
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

test("the README says plainly that the mass-spectrometry library was not imported, and repeats nothing of its paper", () => {
  const said = readme.replace(/\s+/g, " ");
  assert.match(said, /The mass-spectrometry library of planarian proteins was not imported/);
  assert.match(said, /It is not the library and does not stand in for it/);
  assert.match(readme, /doi:10\.1016\/j\.devcel\.2025\.08\.015/);
  // The paper reserves all rights: how many proteins its library covers is to be read there.
  assert.match(said, /How many proteins it covers is in its abstract; the paper reserves all rights, so the number is not repeated here/);
  assert.match(atlas.not_copied, /The catalogue of planarian proteins detected by mass spectrometry \(Ying and others 2025, doi:10\.1016\/j\.devcel\.2025\.08\.015\) was not copied/);
  assert.match(atlas.not_copied, /state no open licence: each is cited for a name, which a sequence record or a UniProtKB entry carries too, and none of their findings is repeated/);
  assert.ok(!/engine (uses|reads) (it|this)/i.test(readme.replace(/nothing in the\s+engine reads it/g, "")));
});

// ---------------------------------------------------------------- the shelves

test("the shelves file keeps its contract: format, one shelf, declared districts, sources with their terms", () => {
  assert.equal(shelves.format, "cells.visualizer.species_proteins@1");
  assert.equal(shelves.species, "planarian");
  assert.match(shelves.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(shelves.shelves.length, 1);
  for (const field of ["id", "label", "outside", "inside"]) assert.ok(shelves.shelves[0][field]?.trim(), `shelf.${field}`);
  // The contract's columns come first and in its order; what is added is declared after them.
  assert.deepEqual(shelves.family_columns.slice(0, 9), ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at"]);
  assert.deepEqual(shelves.member_columns, ["id", "label", "gene", "side", "basis", "length", "unit", "marks"]);
  assert.ok(!("proteins" in shelves), "a catalogue this large is given by family, not protein by protein");
  assert.ok(shelves.family_from.trim() && shelves.groups_from.trim() && shelves.no_family.parts_from.trim());
  const groups = shelves.groups.map((group) => group.id);
  assert.equal(new Set(groups).size, groups.length);
  for (const group of shelves.groups) assert.ok(group.label.trim() && group.from.trim(), group.id);
  for (const family of families) {
    assert.equal(family.shelf, shelves.shelves[0].id, family.id);
    assert.ok(groups.includes(family.group), `${family.id} stands in an undeclared district`);
    assert.ok(SIDES.includes(family.side), `${family.id}: ${family.side}`);
    assert.match(family.id, /^IPR\d{6}$/);
    assert.ok(family.label.trim(), family.id);
  }
  for (const part of parts) {
    assert.ok(groups.includes(part.group) && SIDES.includes(part.side), part.id);
    assert.ok(["superfamily", "other signature", "no signature"].includes(part.kind), part.id);
  }
  // What the shelves take, they take from permissive sources. A tool or rule system whose
  // results one of those gives out is a source of its own (below): it has `through`. A
  // database of the species' own scan is a copy of the scan record's source (`scan`), held
  // below and by tests/licence_classes.test.mjs.
  const taken = shelves.sources.filter((source) => !source.through && !("scan" in source));
  assert.ok(taken.length >= 4);
  for (const source of taken) {
    for (const field of ["name", "licence", "holds", "accessed", "cite"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), source.name);
    assert.ok(!/non-?commercial|\bNC\b|academic/i.test(source.licence), `${source.name}: ${source.licence}`);
    assert.equal(source.class, "permissive", `${source.name}: the shelves take something from a source that is ${source.class}`);
  }
  // A source with no plain licence must have stated that it places no restriction; and what
  // it says of third parties is quoted with it.
  const wbps = shelves.sources.find((source) => source.name === "WormBase ParaSite").licence;
  assert.match(wbps, /Ensembl imposes no restrictions on access to, or use of, the data provided/);
  assert.match(wbps, /Some of the data and software included in the distribution may be subject to third-party constraints\. Users of the data and software are solely responsible for establishing the nature of and complying with any such restrictions\./);
  for (const mark of Object.values(shelves.marks)) assert.ok(mark.label && mark.source && mark.measured === false, "nothing here is measured");
});

test("the tools behind the predictions are sources of their own: their terms, through which database, and how many sides rest on each", () => {
  // The helices and signal peptides are the output of programs given out for academic use,
  // as two permissive databases ran them and give them out. Each program, and each rule
  // system of another owner, is named with its own terms and with `through`, the
  // database or databases its results were read in (joined by " and "). By the user's
  // ruling of 15 November 2026 a value stands on the terms of the database it was read
  // from, and the tool behind it is named and counted: this list is the count, and it may
  // not grow unseen.
  const byName = new Map(shelves.sources.map((source) => [source.name, source]));
  const upstream = shelves.sources.filter((source) => source.through);
  assert.deepEqual(upstream.map((source) => [source.name, source.class, source.through]), [
    ["TMHMM", "non-commercial", "WormBase ParaSite and UniProt"], ["SignalP", "non-commercial", "WormBase ParaSite and UniProt"],
    ["Phobius", "non-commercial", "UniProt"], ["PROSITE", "non-commercial", "UniProt"], ["HAMAP", "permissive", "UniProt"],
  ]);
  for (const source of upstream) {
    for (const field of ["name", "licence", "holds", "accessed"]) assert.ok(source[field]?.trim(), `${source.name}: ${field}`);
    assert.ok(source.url.startsWith("https://"), source.name);
    for (const name of source.through.split(" and ")) assert.ok(byName.get(name)?.class === "permissive" && !byName.get(name).through, `${source.name} is read through ${name}`);
    assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
  }
  for (const name of ["TMHMM", "SignalP"]) assert.match(byName.get(name).licence, /^Academic licence of DTU Health Tech: .*It is a licence of the program: no clause speaks of predictions made with it$/, name);
  assert.match(byName.get("Phobius").licence, /^For academic users only: /);
  assert.match(byName.get("PROSITE").licence, /^CC BY-NC-ND 4\.0/);
  // The counts are those of the members' table.
  const kind = new Map(catalogue.map((row) => [row.id, row.kind]));
  const rows = (isModel, want) => placed.filter((row) => (kind.get(row.id) === "gene model") === isModel && want(row)).length;
  const { "gene models": models, entries } = shelves.rests_on;
  assert.equal(models.predicted, rows(true, (row) => row.basis === "predicted"));
  assert.equal(models["in a membrane, by helices"] + models["one helix and a signal peptide, settled by this tool"] + models["outside, by a signal peptide"] + models["inside, nothing found"], models.predicted);
  assert.equal(models["inside, nothing found"], rows(true, (row) => row.basis === "predicted" && row.side === "inside"));
  assert.equal(models["one helix and a signal peptide, settled by this tool"], rows(true, (row) => row.basis === "predicted" && row.helices === "1" && row.signal === "1"));
  assert.equal(entries.predicted, rows(false, (row) => row.basis === "predicted"));
  assert.equal(entries["inside, nothing found"], rows(false, (row) => row.basis === "predicted" && row.side === "inside"));
  assert.equal(entries["in a membrane, by segments of the sequence analysis"] + entries["in a membrane, by segments that carry a PROSITE rule"] + entries["in a membrane, by segments of UniProt's own rules"], rows(false, (row) => row.basis === "predicted" && row.side === "in"));
  assert.equal(entries["outside, by a signal peptide of the sequence analysis"] + entries["outside, by a signal peptide of UniProt's own rules"], rows(false, (row) => row.basis === "predicted" && row.side === "outside"));
  assert.equal(entries["by function, on a place that names a PROSITE rule"] + entries["by function, on a place that names a HAMAP rule"] + entries["by function, on a place of UniProt's own rules alone"], entries["by function"]);
  assert.ok(entries["of which on no other rule"] <= entries["by function, on a place that names a PROSITE rule"] && entries["by function"] <= rows(false, (row) => row.basis === "by function"));
  // The notes and the sources give the same numbers.
  const all = models.predicted + entries.predicted;
  const byPrograms = models.predicted + entries["in a membrane, by segments of the sequence analysis"] + entries["outside, by a signal peptide of the sequence analysis"] + entries["inside, nothing found"];
  assert.ok(shelves.side_notes.predicted.includes(`So ${byPrograms.toLocaleString("en-US")} of the ${all.toLocaleString("en-US")} predicted sides rest on what TMHMM, SignalP and Phobius found or did not find.`));
  assert.match(shelves.side_notes.predicted, /The three programs are given out for academic use, and WormBase ParaSite says that third-party constraints may apply to what it gives out\. By the project's rule \(the user, 15 November 2026\), a value stands on the terms of the database it was read from, and the tool behind it is named and counted: each program is named among the sources/);
  assert.ok(byName.get("TMHMM").holds.includes(`${models.predicted.toLocaleString("en-US")} predicted sides rest on what the two found or did not find`));
  assert.ok(byName.get("PROSITE").holds.includes(`${entries["by function, on a place that names a PROSITE rule"].toLocaleString("en-US")} are placed by function on a stated place that names one`));
  // The README lists each with its terms, quotes what the two databases say of third
  // parties, and states the rule the values stand on, as the project's rule and not as law.
  const said = readme.replace(/\s+/g, " ");
  for (const source of upstream) assert.ok(readme.includes(`| ${source.name} | ${source.through} | ${source.licence} | ${source.class} | `), `the README's table does not list ${source.name}`);
  assert.match(said, /"Some of the data and software included in the distribution may be subject to third-party constraints\. Users of the data and software are solely responsible for establishing the nature of and complying with any such restrictions\."/);
  assert.match(said, /"We cannot provide unrestricted permission regarding the use of the data, as some data may be covered by patents or other rights\."/);
  assert.match(said, /commercial users pay a licence fee "irrespective of the method by which they access the database"/);
  assert.match(said, /\*\*The project's rule \(the user, 15 November 2026\): a value stands on the terms of the database it was read from, and the tool behind it is named and counted\.\*\*/);
  assert.match(said, /Every side counted above was read in WormBase ParaSite's or UniProt's records, which the two databases give out under their own open terms, so each stands as its database gives it\./);
  assert.match(said, /This is the project's rule, and not a legal opinion\./);
  assert.ok(!/not settled here|to decide/.test(said), "the README still says the question is open");
});

test("every protein of the table is in exactly one family or under no family, and the counts add up", () => {
  assert.equal(catalogue.length, 18882);
  assert.equal(placed.length, catalogue.length);
  assert.deepEqual(Object.keys(placed[0]), ["id", "under", "side", "basis", "helices", "signal", "units"]);
  const ids = new Set(catalogue.map((row) => row.id));
  assert.equal(ids.size, catalogue.length, "the catalogue's identifiers are not unique");
  const seen = new Set();
  for (const row of placed) {
    assert.ok(ids.has(row.id), `${row.id} is not in the catalogue`);
    assert.ok(!seen.has(row.id), `${row.id} is filed twice`);
    seen.add(row.id);
  }
  const count = new Map();
  for (const row of placed) count.set(row.under, (count.get(row.under) || 0) + 1);
  const known = new Set([...families.map((family) => family.id), ...parts.map((part) => part.id)]);
  assert.equal(known.size, families.length + parts.length, "a family and a part share an identifier");
  for (const under of count.keys()) assert.ok(known.has(under), `${under} is neither a family nor a part`);
  for (const group of [...families, ...parts]) assert.equal(count.get(group.id), group.count, `${group.id}: its count`);
  const inFamilies = families.reduce((sum, family) => sum + family.count, 0);
  const inParts = parts.reduce((sum, part) => sum + part.count, 0);
  assert.equal(shelves.no_family.count, inParts);
  assert.equal(inFamilies + shelves.no_family.count, 18882);
  assert.equal(Object.values(shelves.counts).reduce((sum, n) => sum + n, 0), 18882);
  // A superfamily's accession is a part's id only; a family's id is an InterPro family.
  assert.deepEqual(parts.filter((part) => part.kind !== "superfamily").map((part) => part.id).sort(), ["no-signature", "other-signature"]);
});

test("sides and bases use the fixed words, and a family stands where most of its members sit", () => {
  const bySide = Object.fromEntries(SIDES.map((side) => [side, 0]));
  const sides = new Map();
  for (const row of placed) {
    assert.ok(SIDES.includes(row.side), `${row.id}: ${row.side}`);
    assert.ok(BASES.includes(row.basis), `${row.id}: ${row.basis}`);
    assert.equal(row.side === "not known", row.basis === "none", `${row.id}: a side that is not known has no basis, and no other`);
    assert.match(row.helices, /^\d+$/);
    assert.ok(row.signal === "0" || row.signal === "1");
    bySide[row.side] += 1;
    if (!sides.has(row.under)) sides.set(row.under, {});
    sides.get(row.under)[row.side] = (sides.get(row.under)[row.side] || 0) + 1;
  }
  assert.deepEqual(shelves.counts, bySide);
  const order = ["in", "outside", "inside", "not known"];
  for (const group of [...families, ...parts]) {
    assert.deepEqual(group.sides, Object.fromEntries(SIDES.filter((side) => sides.get(group.id)[side]).map((side) => [side, sides.get(group.id)[side]])), group.id);
    const most = Math.max(...Object.values(group.sides));
    assert.equal(group.side, order.find((side) => group.sides[side] === most), `${group.id} does not stand where most of its members sit`);
  }
  // A protein with a helix is never placed inside or outside by prediction alone, except the
  // one case the notes describe: one helix and a signal peptide.
  for (const row of placed) {
    if (row.basis === "predicted" && Number(row.helices) >= 2) assert.equal(row.side, "in", row.id);
    if (row.basis === "predicted" && row.side === "outside") assert.ok(row.signal === "1", `${row.id} is outside without a signal peptide`);
  }
  for (const note of ["predicted", "by function", "stated", "not known"]) assert.ok(shelves.side_notes[note]?.trim(), `side_notes.${note}`);
  assert.match(shelves.side_notes.predicted, /TMHMM/);
  assert.match(shelves.side_notes.predicted, /SignalP/);
  assert.match(shelves.side_notes.predicted, /this tool's own reading/);
  assert.match(shelves.side_notes.predicted, /Which membrane a protein spans is not predicted/);
});

test("the members' files are planned without splitting a family, and the tool cuts them as planned", async () => {
  // In the order listed, each family's place follows the one before it in the same file.
  const filled = new Map();
  let last = "";
  for (const group of [...families, ...parts]) {
    assert.match(group.file, /^members-\d\d\.json$/);
    assert.ok(group.file >= last, `${group.id}: the files are not in order`);
    last = group.file;
    assert.equal(group.at[0], filled.get(group.file) || 0, `${group.id}: its place in ${group.file}`);
    assert.equal(group.at[1] - group.at[0], group.count, group.id);
    filled.set(group.file, group.at[1]);
  }
  // A file is over its size only where one family or part alone is.
  for (const [file, size] of filled) {
    const alone = [...families, ...parts].filter((group) => group.file === file).length === 1;
    assert.ok(size <= 2000 || alone, `${file} holds ${size} members`);
  }
  // The table is in the members' order: each family's lines are together, in the files' order.
  let at = 0;
  for (const group of [...families, ...parts]) {
    for (let index = 0; index < group.count; index++) assert.equal(placed[at + index].under, group.id, `line ${at + index + 2} of the members' table`);
    at += group.count;
  }
  const out = await mkdtemp(path.join(os.tmpdir(), "planarian-members-"));
  try {
    const run = spawnSync("python3", [TOOL, "members", "--out", out], { encoding: "utf8", timeout: 300000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    const byId = new Map(catalogue.map((row) => [row.id, row]));
    let total = 0;
    at = 0;
    for (const [file, size] of [...filled].sort()) {
      const cut = JSON.parse(await readFile(path.join(out, file), "utf8"));
      assert.equal(cut.format, "cells.visualizer.species_protein_members@1");
      assert.deepEqual(cut.columns, shelves.member_columns);
      assert.equal(cut.members.length, size, file);
      cut.members.forEach((row, index) => {
        const member = named(cut.columns, row);
        const line = placed[at + index];
        assert.equal(member.id, line.id, `${file}, member ${index}`);
        assert.equal(member.side, line.side);
        assert.equal(member.basis, line.basis);
        assert.equal(member.length, Number(byId.get(member.id).length));
        assert.deepEqual(member.unit, line.units ? line.units.split(";") : null);
        assert.ok(member.label !== undefined && member.marks.kind === byId.get(member.id).kind);
        // A member filed by what the species' own scan added carries the databases behind it; no other carries the mark.
        assert.deepEqual(member.marks.scan ?? null, groundOf(line), `${member.id}: the scan's mark`);
      });
      at += size;
      total += size;
    }
    assert.equal(total, 18882);
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});

test("the filing reads the species' own scan: its sources are the record's own, exactly the databases behind the members it files, and each such member says so", () => {
  const scan = shelves.scan;
  assert.deepEqual([scan.record, scan.added, scan.tool, scan.licence], ["interproscan.json", "interproscan_added.tsv", `${RECORD.tool.name} ${RECORD.tool.release}`, RECORD.tool.licence]);
  assert.match(scan.decided, /^On 19 November 2026 it was decided that the shelves take the scan's added entries\./);
  assert.match(shelves.family_from, new RegExp(`the InterPro entries that the species' own scan \\(${scan.tool.replace(/\./g, "\\.")}, ${scan.days}\\) found on it and the column lacks`));
  const behind = new Map();
  let filed = 0;
  for (const row of placed) {
    const ground = groundOf(row);
    if (!ground) continue;
    filed += 1;
    for (const name of ground) behind.set(name, (behind.get(name) || 0) + 1);
  }
  assert.ok(filed > 3000, `${filed} members filed by what the scan added`);
  // The copies: the record's source for each database behind a member it files, with the record's terms, and no other.
  const copies = shelves.sources.filter((source) => "scan" in source);
  assert.deepEqual(copies.map((source) => source.name).sort(), [...behind.keys()].sort(), "the scan's sources are the databases behind the members it files");
  for (const source of copies) {
    const name = Object.keys(RECORD.databases).find((key) => RECORD.databases[key].source === source.scan);
    const own = RECORD.sources[source.scan];
    assert.deepEqual([source.name, source.url, source.licence, source.class, source.release], [own.name, own.url, own.licence, own.class, RECORD.databases[name].release], source.name);
    assert.equal(source.cite, own.citation ?? null, `${source.name}: its citation is the record's, or none where the record has none`);
    assert.ok(source.holds.includes(`${behind.get(source.name).toLocaleString("en-US")} proteins are filed by them`), source.name);
  }
  // The mark says what filed it, with the tool's release and the days of the run, and names a database that is not plainly permissive with its terms.
  const mark = shelves.marks.scan;
  assert.ok(mark.says.includes(`(${scan.tool}, ${scan.days})`) && mark.says.includes("{value}") && mark.measured === false, mark.says);
  const notPlain = copies.filter((source) => source.class !== "permissive" || /share-alike/.test(source.licence)).map((source) => source.name).sort();
  assert.deepEqual(Object.keys(mark.words).sort(), notPlain);
  assert.match(mark.words.CDD, /^CDD, which states no terms \(used by the decision of 18 November 2026\)$/);
  assert.match(mark.words.NCBIfam, /^NCBIfam, under CC BY-SA 4\.0 \(share-alike\)$/);
  for (const source of copies) assert.ok(mark.source.includes(source.name), `the mark's source names ${source.name}`);
});

test("the shelves are tied to the atlas: a unit's products carry its id, and their families sit in a membrane", () => {
  const spanning = ["alpha", "alpha1", "innexin", "alpha (BK)", "alpha (SK)", "beta (BK)", "catalytic", "exchanger", "IP3R", "RyR", "KCC", "MCU"];
  const unitsOf = new Map();
  const spans = new Set();
  for (const [unit, entry] of units) {
    for (const product of entry.products) {
      for (const { id } of product.ids) {
        if (!unitsOf.has(id)) unitsOf.set(id, new Set());
        unitsOf.get(id).add(unit);
        if (spanning.includes(product.role)) spans.add(id);
      }
    }
  }
  const number = (unit) => Number(unit.slice(1));
  const familyUnits = new Map();
  for (const row of placed) {
    const expected = [...(unitsOf.get(row.id) || [])].sort((a, b) => number(a) - number(b)).join(";");
    assert.equal(row.units, expected, `${row.id}: its units`);
    if (expected && row.under.startsWith("IPR")) {
      if (!familyUnits.has(row.under)) familyUnits.set(row.under, new Set());
      for (const unit of expected.split(";")) familyUnits.get(row.under).add(unit);
    }
  }
  assert.equal(placed.filter((row) => row.units).length, unitsOf.size, "a product of the atlas is not in the members' table");
  for (const family of families) {
    assert.deepEqual(family.units, [...(familyUnits.get(family.id) || [])].sort((a, b) => number(a) - number(b)), `${family.id}: its units`);
  }
  const holding = new Set(placed.filter((row) => spans.has(row.id) && families.some((family) => family.id === row.under)).map((row) => row.under));
  assert.ok(holding.size >= 20, "the families of the atlas's membrane-spanning products");
  for (const family of families.filter((family) => holding.has(family.id))) assert.equal(family.side, "in", `${family.id} (${family.label}) holds a membrane-spanning product`);
  // The gap junctions' family is the innexins, in a membrane, among the channels.
  const innexin = families.find((family) => family.label === "Innexin");
  assert.deepEqual([innexin.side, innexin.group, innexin.units], ["in", "channels", ["U36", "U37", "U38"]]);
});

test("the shelves' files keep their size limits, and say that everything in them is predicted", () => {
  assert.ok(shelvesText.length < 1_000_000, "the families' file has grown past 1 MB");
  assert.ok(shelvesText.length + membersText.length < 1_500_000, "the shelves add more than 1.5 MB");
  for (const content of [whole, membersText, shelvesText]) assert.ok(content.length < 3_000_000, "a file has grown past 3 MB");
  assert.match(shelves.from, /Every one is predicted, from the genome or from transcripts; none was measured/);
  const said = readme.replace(/\s+/g, " ");
  assert.match(said, /Everything here is a prediction on a predicted protein/);
  assert.match(said, /Nothing says that the animal makes a protein, where it was seen, or which membrane it is in/);
  assert.ok(!/engine (models|uses|reads) (it|this|these)/i.test(shelvesText));
  // What the README says of the shelves is what the files hold.
  const stated = said.match(/([\d,]+) families hold ([\d,]+) proteins/);
  assert.deepEqual(stated.slice(1).map((n) => Number(n.replace(/,/g, ""))), [families.length, families.reduce((sum, family) => sum + family.count, 0)]);
  assert.ok(said.includes(`${shelves.no_family.count.toLocaleString("en-US")} proteins carry no family signature`));
});

const SAVED = existsSync(path.join(EVIDENCE, "requests.json")) && ["interpro-hierarchy-and-go", "terms-upstream-tools"].every((source) => existsSync(path.join(DATASETS, source, "MANIFEST.json")));

test("the build tool reproduces the atlas, the tables, the shelves and the README from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set PLANARIAN_EVIDENCE and PLANARIAN_DATASETS)" }, async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: [path.join(DATASETS, "*"), path.join(DATASETS, "..", "*", "*")], evidence: [EVIDENCE], env: ["PLANARIAN_DATASETS", "PLANARIAN_EVIDENCE"] })) return;
  const out = await mkdtemp(path.join(os.tmpdir(), "planarian-atlas-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--evidence", EVIDENCE, "--datasets", DATASETS, "--out-atlas", path.join(out, "planarian.json"), "--out-reference", path.join(out, "planarian")], { encoding: "utf8", timeout: 900000 });
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(await readFile(path.join(out, "planarian.json"), "utf8"), text, "the atlas differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "predicted_proteins.tsv"), "utf8"), whole, "the whole table differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "reference_proteins.tsv"), "utf8"), table, "the reference table differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "README.md"), "utf8"), readme, "the README differs from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "shelves.json"), "utf8"), shelvesText, "the shelves differ from what the tool builds");
    assert.equal(await readFile(path.join(out, "planarian", "shelf_members.tsv"), "utf8"), membersText, "the members' table differs from what the tool builds");
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
