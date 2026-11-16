// The human's own proteins for the atlas's shelves (data/proteins/human/) are held to their
// contract, schema/SPECIES_PROTEINS.md: several shelves, places as stated, every protein in
// exactly one line. shelves.json holds the lines; proteins.tsv holds one line for each
// protein, in the order the lines read them. The inventory's own human entries must be
// among them with their units. Where the folder of saved downloads is on this machine, the
// build tool must reproduce the three files from it, byte for byte; elsewhere that one
// check is skipped. The build also reads the pages of terms that the other species' tools
// saved, in the folder above the human's (HUMAN_TERMS names another).
//
//   node --test tests/human_atlas.test.mjs
//   HUMAN_DATASETS=DATA node --test tests/human_atlas.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const FOLDER = path.join(ROOT, "data", "proteins", "human");
const TOOL = path.join(ROOT, "tools", "build_human_atlas.py");
const NOTE = path.join(ROOT, "docs", "HUMAN_PROTEOME.md");
const DATASETS = process.env.HUMAN_DATASETS || "/mnt/datasets/Cells/human";
const TERMS = process.env.HUMAN_TERMS || path.join(DATASETS, "..");
const SIDES = ["outside", "in", "inside", "not known"];
const SIDE_TIE = ["in", "outside", "inside", "not known"];
const SHELVES = ["cell", "er", "mito", "nucleus", "other", "membrane"];
const CLASSES = ["permissive", "non-commercial", "no stated terms"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1";

const shelvesText = await readFile(path.join(FOLDER, "shelves.json"), "utf8");
const shelves = JSON.parse(shelvesText);
const tableText = await readFile(path.join(FOLDER, "proteins.tsv"), "utf8");
const readme = await readFile(path.join(FOLDER, "README.md"), "utf8");
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const [head, ...tableLines] = tableText.replace(/\n$/, "").split("\n");
const columns = head.split("\t");
const table = tableLines.map((line) => Object.fromEntries(line.split("\t").map((value, index) => [columns[index], value])));
const named = (names, row) => Object.fromEntries(names.map((name, index) => [name, row[index]]));
const families = shelves.families.map((row) => named(shelves.family_columns, row));
const lone = shelves.lone.parts.map((row) => named(shelves.lone.part_columns, row));
const parts = shelves.no_family.parts.map((row) => named(shelves.no_family.part_columns, row));
const lines = [...families.map((line) => ["family", line]), ...lone.map((line) => ["lone", line]), ...parts.map((line) => ["part", line])];
const letters = shelves.members_from.letters;
const places = new Map(shelves.places.map((row) => named(shelves.place_columns, row)).map((place) => [place.id.slice(3), place]));
const tally = (items, key) => {
  const counts = new Map();
  for (const item of items) counts.set(key(item), (counts.get(key(item)) || 0) + 1);
  return counts;
};
const sum = (numbers) => numbers.reduce((total, number) => total + number, 0);
const sideCounts = (rows) => Object.fromEntries(SIDES.map((side) => [side, rows.filter((row) => row.side === side).length]));
const majority = (sides) => SIDE_TIE.reduce((best, side) => ((sides[side] || 0) > (sides[best] || 0) ? side : best), SIDE_TIE[0]);

// The members of each line: the next `count` lines of the table.
const membersOf = new Map();
{
  let cursor = 0;
  for (const [, line] of lines) {
    membersOf.set(line, table.slice(cursor, cursor + line.count));
    cursor += line.count;
  }
}

test("the file says what it is: the reviewed human proteome, with what is in and what is out in numbers", () => {
  assert.equal(shelves.format, "cells.visualizer.species_proteins@1");
  assert.equal(shelves.species, "human");
  assert.match(shelves.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(shelves.predicted, false, "the proteins are curated entries, not predictions");
  assert.ok(!("proteins" in shelves) && Array.isArray(shelves.families), "a large catalogue: families, not one marker each");
  const counts = shelves.from_counts;
  assert.equal(counts.reviewed, table.length, "one line of the table for each reviewed entry");
  assert.equal(counts.sequences, counts.reviewed + counts.isoforms);
  assert.equal(counts.entries, counts.reviewed + counts.unreviewed);
  assert.equal(sum(table.map((row) => Number(row.isoforms))), counts.sequences, "the isoforms add up to the sequences the entries describe");
  // What is in and what is out is said in the file's own words, with the numbers.
  for (const number of [counts.reviewed, counts.isoforms, counts.sequences, counts.unreviewed, counts.entries, counts.genes]) assert.ok(shelves.from.includes(number.toLocaleString("en-US")), `'from' does not give ${number}`);
  assert.match(shelves.from, /unreviewed entries are not listed/);
  assert.ok(counts.reviewed > 20000 && counts.reviewed < 21000 && counts.unreviewed > 10 * counts.reviewed, "the catalogue is the reviewed proteome, a small part of the entries");
});

test("the shelves are the contract's six, the unnamed membrane last, each with the names of its two sides", () => {
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), SHELVES);
  for (const shelf of shelves.shelves) for (const key of ["label", "outside", "inside"]) assert.ok(shelf[key]?.trim(), `${shelf.id}.${key}`);
  assert.equal(shelves.shelves.at(-1).label, "A membrane, not told which");
  assert.match(shelves.shelves.at(-1).outside, /outside the cell, or within a compartment/);
  assert.match(shelves.shelves.find((shelf) => shelf.id === "other").note, /Golgi apparatus.*endosomes.*lysosomes.*peroxisomes.*vesicles.*mitochondrion's outer membrane/);
  assert.deepEqual(Object.keys(shelves.shelf_counts), [...SHELVES, "no shelf"]);
});

test("every source states its terms and its class; what was taken is from UniProt, InterPro and the Gene Ontology; the rule systems and predictors behind UniProt's statements are named, read through it", () => {
  const byName = new Map(shelves.sources.map((source) => [source.name, source]));
  assert.equal(byName.size, shelves.sources.length);
  for (const source of shelves.sources) {
    assert.ok(source.licence?.trim() && source.holds?.trim() && /^https:\/\//.test(source.url), source.name);
    assert.ok(CLASSES.includes(source.class), `${source.name}: ${source.class}`);
  }
  const standing = shelves.sources.filter((source) => !source.through);
  assert.deepEqual(standing.map((source) => source.name), ["UniProt", "InterPro", "Gene Ontology"]);
  assert.deepEqual(standing.map((source) => [source.class, source.licence]), [["permissive", "CC BY 4.0"], ["permissive", "CC0 1.0"], ["permissive", "CC BY 4.0"]]);
  const upstream = shelves.sources.filter((source) => source.through);
  assert.deepEqual(upstream.map((source) => source.name), ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI"]);
  for (const source of upstream) {
    // The tool's own entry names the database its results were read in, and says what rests on it, with counts.
    assert.equal(source.through, "UniProt", source.name);
    assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
    assert.match(source.holds, /\d/, `${source.name}: what rests on it is counted`);
  }
  assert.deepEqual(upstream.map((source) => source.class), ["non-commercial", "permissive", "non-commercial", "non-commercial", "non-commercial", "non-commercial", "no stated terms", "no stated terms", "no stated terms"]);
  // Nothing is taken from the Human Protein Atlas: it is not a source, and the notes say so.
  assert.ok(!shelves.sources.some((source) => /protein atlas/i.test(source.name)));
  assert.match(readme, /nothing is taken from the Human Protein Atlas/i);
  // Every mark is declared, with its values and a source that stands for itself.
  assert.deepEqual(Object.keys(shelves.marks), ["isoforms", "seen", "evidence", "where", "also", "family", "of"]);
  for (const [name, mark] of Object.entries(shelves.marks)) {
    assert.ok(mark.label?.trim() && mark.values && mark.measured === false, name);
    assert.ok(standing.some((source) => source.name === mark.source), `${name}: its source ${mark.source}`);
  }
  for (const basis of ["stated", "predicted", "none"]) assert.ok(shelves.side_notes[basis]?.trim(), `side_notes.${basis}`);
  assert.match(shelves.side_notes.predicted, /TMHMM, Memsat, Phobius/);
});

test("a family has one line for each shelf that holds members of it, and the numbers of families and lines are given", () => {
  assert.deepEqual(shelves.family_columns.slice(0, 9), ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at"]);
  assert.ok(shelves.family_columns.includes("units") && shelves.family_columns.includes("total"));
  const groups = new Set(shelves.groups.map((group) => group.id));
  const seen = new Set();
  const labels = new Map(), totals = new Map(), held = new Map();
  for (const line of families) {
    const key = `${line.id}|${line.shelf}`;
    assert.ok(!seen.has(key), `${key}: a family has two lines on one shelf`);
    seen.add(key);
    assert.match(line.id, /^IPR\d{6}$/);
    assert.ok(line.shelf === null || SHELVES.includes(line.shelf), key);
    assert.ok(SIDES.includes(line.side) && groups.has(line.group), key);
    assert.equal(sum(Object.values(line.sides)), line.count, key);
    assert.ok(Object.keys(line.sides).every((side) => SIDES.includes(side)), key);
    assert.equal(line.side, majority(line.sides), `${key}: it stands where most of its members sit; of equals, a membrane first`);
    if (line.shelf === null) assert.deepEqual(Object.keys(line.sides), ["not known"], `${key}: no shelf, yet a side is known`);
    assert.ok((labels.get(line.id) ?? line.label) === line.label, `${line.id}: its label is the same on every shelf`);
    labels.set(line.id, line.label);
    assert.ok((totals.get(line.id) ?? line.total) === line.total, `${line.id}: its total is the same on every line`);
    totals.set(line.id, line.total);
    held.set(line.id, (held.get(line.id) || 0) + line.count);
  }
  for (const [id, total] of totals) {
    assert.equal(held.get(id), total, `${id}: its lines hold its members in all`);
    assert.ok(total >= 2, `${id}: a family of one has no line`);
  }
  assert.equal(shelves.distinct_families, totals.size);
  assert.equal(shelves.family_lines, families.length);
  assert.equal(shelves.families_in_all, totals.size + shelves.lone.families);
  assert.ok(families.length > totals.size, "the families list has more lines than families");
  // The lines are in order: by shelf, the proteins on no shelf last.
  const rank = (shelf) => (shelf === null ? SHELVES.length : SHELVES.indexOf(shelf));
  for (const list of [families, lone, parts]) for (let index = 1; index < list.length; index += 1) assert.ok(rank(list[index - 1].shelf) <= rank(list[index].shelf), "a list of lines is not in the order of the shelves");
});

test("a family of one does not open: its protein is listed under lone, by shelf, district and side, and names its family", () => {
  assert.deepEqual(shelves.lone.part_columns.slice(0, 10), ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at"]);
  const seen = new Set();
  for (const part of lone) {
    const key = `${part.id}|${part.shelf}`;
    assert.ok(!seen.has(key), key);
    seen.add(key);
    assert.equal(part.kind, "lone");
    assert.equal(part.id, `lone-${part.group}-${part.side.replace(" ", "-")}`);
    assert.deepEqual(part.sides, { [part.side]: part.count }, `${key}: every member of a lone part sits on its side`);
    if (part.shelf === null) assert.equal(part.side, "not known", key);
  }
  assert.equal(sum(lone.map((part) => part.count)), shelves.lone.count);
  assert.equal(shelves.lone.families, shelves.lone.count, "each is the only member of its family");
  // In the table: a lone protein's family is no other protein's, and its name is given.
  const loneRows = new Set(lone.flatMap((part) => membersOf.get(part)));
  const under = tally(table, (row) => row.under);
  for (const row of loneRows) {
    assert.match(row.under, /^IPR\d{6}$/, row.id);
    assert.equal(under.get(row.under), 1, `${row.id}: its family ${row.under} has another member`);
    assert.ok(row.family, `${row.id}: its family's name`);
  }
  for (const row of table) if (!loneRows.has(row)) assert.equal(row.family, "", `${row.id}: only a lone protein carries its family's name`);
  assert.match(shelves.lone.parts_from, /does not open/);
});

test("no protein is dropped: those with no family are in parts, each with a line for each shelf", () => {
  const seen = new Set();
  for (const part of parts) {
    const key = `${part.id}|${part.shelf}`;
    assert.ok(!seen.has(key), key);
    seen.add(key);
    assert.ok(["superfamily", "other signature", "no signature"].includes(part.kind), key);
    assert.equal(part.kind === "superfamily", /^IPR\d{6}$/.test(part.id), key);
    assert.equal(sum(Object.values(part.sides)), part.count, key);
    assert.equal(part.side, majority(part.sides), key);
    if (part.shelf === null) assert.deepEqual(Object.keys(part.sides), ["not known"], key);
  }
  assert.equal(sum(parts.map((part) => part.count)), shelves.no_family.count);
  assert.equal(sum(families.map((line) => line.count)) + shelves.lone.count + shelves.no_family.count, table.length, "every protein is in one line");
});

test("every protein of the table is in exactly one line, in the lines' order, and the counts add up", () => {
  assert.deepEqual(columns, ["id", "gene", "name", "length", "isoforms", "seen", "under", "shelf", "side", "basis", "evidence", "place", "also", "units", "family", "of"]);
  assert.equal(new Set(table.map((row) => row.id)).size, table.length, "two lines share an accession");
  assert.equal(sum(lines.map(([, line]) => line.count)), table.length);
  for (const [what, line] of lines) {
    const members = membersOf.get(line);
    assert.equal(members.length, line.count);
    for (const row of members) {
      assert.equal(row.shelf, line.shelf ?? "", `${row.id}: its shelf is its line's`);
      if (what !== "lone") assert.equal(row.under, line.id, `${row.id}: it is filed under its line`);
    }
    assert.deepEqual(Object.fromEntries(SIDES.filter((side) => line.sides[side]).map((side) => [side, line.sides[side]])), Object.fromEntries(Object.entries(sideCounts(members)).filter(([, count]) => count)), `${line.id} on ${line.shelf}: its sides are its members'`);
  }
  // The file's counts are those of the table: by side, by shelf and by basis.
  assert.deepEqual(shelves.counts, sideCounts(table));
  for (const shelf of [...SHELVES, "no shelf"]) assert.deepEqual(shelves.shelf_counts[shelf], sideCounts(table.filter((row) => (row.shelf || "no shelf") === shelf)), shelf);
  for (const side of SIDES) for (const [basis, count] of Object.entries(shelves.by_basis[side])) assert.equal(count, table.filter((row) => row.side === side && letters.basis[row.basis] === basis).length, `${side} by ${basis}`);
  for (const shelf of shelves.shelves) {
    assert.equal(shelf.proteins, sum(Object.values(shelves.shelf_counts[shelf.id])), shelf.id);
    assert.equal(shelf.lines, families.filter((line) => line.shelf === shelf.id).length, shelf.id);
    assert.equal(shelf.lone, sum(lone.filter((part) => part.shelf === shelf.id).map((part) => part.count)), shelf.id);
    assert.equal(shelf.families, shelf.lines + shelf.lone, shelf.id);
  }
  assert.equal(shelves.no_shelf.proteins, sum(Object.values(shelves.shelf_counts["no shelf"])));
  assert.equal(sum(shelves.placed_by.map((rule) => rule.proteins)), table.length, "every protein came to its side by one rule");
});

test("sides, bases and marks use the fixed words: a side that is not known has no basis, a protein on no shelf has no side", () => {
  assert.deepEqual(letters.basis, { s: "stated", p: "predicted", n: "none" });
  assert.deepEqual(Object.values(letters.evidence), shelves.marks.evidence.values);
  assert.deepEqual(Object.values(letters.seen), shelves.marks.seen.values);
  for (const row of table) {
    assert.ok(SIDES.includes(row.side) && row.basis in letters.basis && row.seen in letters.seen, row.id);
    assert.ok(row.shelf === "" || SHELVES.includes(row.shelf), row.id);
    assert.equal(row.side === "not known", row.basis === "n", `${row.id}: a side that is not known has the basis none, and no other has`);
    if (row.shelf === "") assert.ok(row.side === "not known" && row.place === "" && row.evidence === "", `${row.id}: on no shelf, yet something is said of its place`);
    if (row.basis === "s") assert.ok(row.place && row.evidence in letters.evidence, `${row.id}: a stated side names the statement and what stands behind it`);
    if (row.place === "") assert.ok(row.evidence === "" && (row.shelf === "" || (row.shelf === "membrane" && row.basis === "p")), `${row.id}: no stated place, so no shelf or a membrane that is not named`);
    assert.ok(Number(row.length) > 0 && Number(row.isoforms) >= 1 && row.name, row.id);
  }
});

test("the placement table is in the file: every stated place has its shelf, and the deciding statement puts the protein where it stands", () => {
  assert.deepEqual(shelves.place_columns, ["id", "words", "shelf", "names", "resolved", "under", "first"]);
  for (const place of places.values()) {
    assert.ok(place.names in shelves.place_kinds, place.words);
    assert.ok(place.shelf === null ? place.names === "elsewhere" : SHELVES.includes(place.shelf), place.words);
    assert.equal(shelves.place_words[place.id.slice(3)], place.words);
  }
  const first = {};
  for (const row of table) {
    for (const written of [row.place, ...row.also.split(",")].filter(Boolean)) for (const part of written.split(".")) assert.ok(part in shelves.place_words, `${row.id}: ${part} has no words`);
    if (!row.place) continue;
    const place = places.get(row.place.split(".")[0]);
    first[place.words] = (first[place.words] || 0) + 1;
    assert.equal(place.shelf, row.shelf, `${row.id}: ${place.words} is on the shelf ${place.shelf}`);
    if (place.names === "inside" || place.names === "outside") assert.deepEqual([row.side, row.basis], [place.names, "s"], `${row.id}: ${place.words} is itself on one side`);
    if (place.names === "region") assert.ok(row.side === "not known" || row.basis === "s", `${row.id}: in a region no feature settles the side`);
  }
  for (const place of places.values()) assert.equal(place.first, first[place.words] || 0, `${place.words}: how many proteins it places`);
  // The lines of the table that the vocabulary's links could move, pinned.
  const at = (words) => {
    const place = [...places.values()].find((item) => item.words === words);
    return place ? [place.shelf, place.names] : null;
  };
  for (const [words, shelf, names] of [
    ["Cell membrane", "cell", "membrane"], ["Cytoplasm, cytoskeleton, cilium basal body", "cell", "inside"], ["Cell projection, cilium membrane", "cell", "membrane"],
    ["Cell projection, cilium", "cell", "region"], ["Cell surface", "cell", "whole"], ["Cell junction, tight junction", "cell", "whole"], ["Synaptic cleft", "cell", "outside"],
    ["Secreted, extracellular space, extracellular matrix, basement membrane", "cell", "outside"], ["Cell membrane, sarcolemma, T-tubule", "cell", "membrane"],
    ["Nucleus, nuclear pore complex", "nucleus", "whole"], ["Chromosome, centromere, kinetochore", "nucleus", "inside"], ["Nucleus inner membrane", "nucleus", "membrane"],
    ["Endoplasmic reticulum", "er", "whole"], ["Microsome membrane", "er", "membrane"], ["Sarcoplasmic reticulum lumen", "er", "inside"],
    ["Mitochondrion", "mito", "region"], ["Mitochondrion membrane", "mito", "region"], ["Mitochondrion intermembrane space", "mito", "outside"], ["Mitochondrion matrix, mitochondrion nucleoid", "mito", "inside"],
    ["Mitochondrion outer membrane", "other", "membrane"], ["Cytoplasmic vesicle, secretory vesicle, synaptic vesicle membrane", "other", "membrane"], ["Postsynaptic recycling endosome membrane", "other", "membrane"],
    ["Cytoplasmic vesicle, secretory vesicle, chromaffin granule lumen", "other", "inside"], ["Golgi apparatus", "other", "whole"], ["Lipid droplet", "other", "region"],
    ["Membrane", "membrane", "membrane"], ["Endomembrane system", "membrane", "membrane"], ["Membrane raft", "membrane", "membrane"], ["Virion", null, "elsewhere"], ["Target cell membrane", null, "elsewhere"],
  ]) assert.deepEqual(at(words), [shelf, names], words);
  // The proteins on the shelf of a membrane that is not named: stated so, or predicted with no stated place.
  for (const row of table.filter((item) => item.shelf === "membrane")) assert.ok(row.place ? places.get(row.place.split(".")[0]).shelf === "membrane" : row.basis === "p", row.id);
});

test("the shelves are tied to the inventory: each of its human entries is a protein here with its units, and so is its line", () => {
  const wanted = new Map();
  for (const unit of snapshot.units) for (const product of unit.products || []) if (product.human_uniprot) wanted.set(product.human_uniprot, [...(wanted.get(product.human_uniprot) || []), unit.id]);
  const byId = new Map(table.map((row) => [row.id, row]));
  const natural = (a, b) => a.localeCompare(b, "en", { numeric: true });
  assert.ok(wanted.size >= 90, "the inventory names its human entries");
  for (const [accession, units] of wanted) {
    const row = byId.get(accession);
    assert.ok(row, `${accession} of the inventory is not a protein of the catalogue`);
    assert.equal(row.units, [...new Set(units)].sort(natural).join(";"), accession);
  }
  for (const row of table) if (!wanted.has(row.id)) assert.equal(row.units, "", `${row.id} carries a unit the inventory does not give it`);
  for (const [, line] of lines) {
    const units = [...new Set(membersOf.get(line).flatMap((row) => (row.units ? row.units.split(";") : [])))].sort(natural);
    assert.deepEqual(line.units, units, `${line.id} on ${line.shelf}: its units are its members'`);
  }
});

test("families and districts are chosen as in the planarian's file, so that a family has the same id and name in both", async () => {
  const planarian = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "planarian", "shelves.json"), "utf8"));
  assert.deepEqual(shelves.groups.map((group) => [group.id, group.label]), planarian.groups.map((group) => [group.id, group.label]));
  for (const group of shelves.groups.slice(0, 7)) assert.equal(group.from, planarian.groups.find((other) => other.id === group.id).from, group.id);
  const release = (data) => data.sources.find((source) => source.name === "InterPro").release;
  const theirs = new Map(planarian.families.map((row) => [row[0], row[1]]));
  const shared = [...new Set(families.map((line) => line.id))].filter((id) => theirs.has(id));
  assert.ok(shared.length > 500, "the two species share families");
  if (release(shelves) === release(planarian)) for (const id of shared) assert.equal(families.find((line) => line.id === id).label, theirs.get(id), id);
  assert.match(shelves.family_from, /narrowest family/);
});

test("the files keep their size limits, hold no machine path, and the notes give the file's own numbers", async () => {
  const sizes = Object.fromEntries(await Promise.all((await readdir(FOLDER)).map(async (name) => [name, (await readFile(path.join(FOLDER, name))).length])));
  assert.deepEqual(Object.keys(sizes).sort(), ["README.md", "proteins.tsv", "shelves.json"]);
  assert.ok(sizes["shelves.json"] < 1_000_000, `shelves.json is ${sizes["shelves.json"]} bytes; a species' file stays under 1 MB`);
  for (const [name, size] of Object.entries(sizes)) assert.ok(size < 3_000_000, `${name} is ${size} bytes`);
  assert.ok(sum(Object.values(sizes)) < 3_000_000, `the folder is ${sum(Object.values(sizes))} bytes`);
  for (const [name, text] of [["shelves.json", shelvesText], ["proteins.tsv", tableText], ["README.md", readme]]) assert.ok(!MACHINE.test(text), `${name} holds a machine path`);
  assert.ok(!/\b[ACDEFGHIKLMNPQRSTVWY]{40,}\b/.test(tableText), "the table holds a sequence");
  const said = (number) => number.toLocaleString("en-US");
  const note = await readFile(NOTE, "utf8");
  for (const text of [readme, note]) {
    for (const number of [shelves.from_counts.reviewed, shelves.from_counts.isoforms, shelves.from_counts.unreviewed, shelves.from_counts.entries, shelves.families_in_all, shelves.distinct_families, shelves.family_lines, shelves.lone.count, shelves.no_family.count, shelves.no_shelf.proteins]) assert.ok(text.includes(said(number)), `a note does not give ${said(number)}`);
    for (const shelf of shelves.shelves) assert.ok(text.includes(said(shelf.proteins)), `a note does not give the ${said(shelf.proteins)} proteins of the shelf ${shelf.id}`);
    assert.ok(!MACHINE.test(text.replace(/`\/mnt\/(datasets|workspaces)\/Cells\/[\w./-]*`/g, "")), "a note holds a machine path");
  }
  // The note says what rests on sources that are not permissive, and names each.
  const from = note.indexOf("\n## What rests on non-commercial or unlicensed sources\n");
  assert.ok(from >= 0, "the note has no section on non-commercial or unlicensed sources");
  const section = note.slice(from, note.indexOf("\n## ", from + 10) < 0 ? undefined : note.indexOf("\n## ", from + 10));
  for (const source of shelves.sources.filter((item) => item.class !== "permissive")) assert.ok(section.includes(source.name), `the section does not name ${source.name}`);
});

test("the tool cuts the members' files as the lines say, and every member is a protein with the declared marks", async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "human-members-"));
  try {
    const run = spawnSync("python3", [TOOL, "members", "--out", out], { encoding: "utf8", timeout: 300000 });
    assert.equal(run.status, 0, run.stderr);
    const wanted = [...new Set(lines.map(([, line]) => line.file))].sort();
    assert.deepEqual((await readdir(out)).sort(), wanted);
    assert.ok(wanted.every((name) => /^members-\d+\.json$/.test(name)));
    const marks = new Set(Object.keys(shelves.marks));
    let total = 0;
    for (const name of wanted) {
      const file = JSON.parse(await readFile(path.join(out, name), "utf8"));
      assert.deepEqual([file.format, file.species, file.file], [MEMBERS_FORMAT, "human", name]);
      assert.deepEqual(file.columns, shelves.member_columns);
      const here = lines.filter(([, line]) => line.file === name);
      assert.equal(file.members.length, sum(here.map(([, line]) => line.count)), name);
      assert.ok(file.members.length <= 2000 || here.length === 1, `${name}: a file holds at most 2,000 members, or one line alone`);
      let cursor = 0;
      for (const [what, line] of here) {
        assert.deepEqual(line.at, [cursor, cursor + line.count], `${line.id} on ${line.shelf}: its place in ${name}`);
        const rows = membersOf.get(line);
        file.members.slice(cursor, cursor + line.count).forEach((member, index) => {
          const [id, label, gene, side, basis, length, unit, given] = member;
          const row = rows[index];
          assert.deepEqual([id, label, gene, side, basis, length], [row.id, row.name, row.gene, row.side, letters.basis[row.basis], Number(row.length)], id);
          assert.deepEqual(unit, row.units ? row.units.split(";") : null, id);
          assert.ok(Object.keys(given).every((mark) => marks.has(mark)), `${id}: a mark that is not declared`);
          assert.equal(given.seen, letters.seen[row.seen], id);
          assert.equal(given.evidence, row.evidence ? letters.evidence[row.evidence] : undefined, id);
          assert.equal("where" in given, row.place !== "", id);
          assert.equal("family" in given, what === "lone", id);
          if (what === "lone") assert.deepEqual(given.family, [row.under, row.family], id);
        });
        cursor += line.count;
      }
      total += file.members.length;
    }
    assert.equal(total, table.length);
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});

const SAVED = [path.join(DATASETS, "uniprot-human-reviewed-proteome"), path.join(TERMS, "mpneumoniae", "terms-upstream-tools"), path.join(TERMS, "syn3a", "terms-prosite"), path.join(TERMS, "planarian", "terms-upstream-tools")].every((folder) => existsSync(path.join(folder, "MANIFEST.json")));

test("the build tool reproduces the shelves, the table and the note beside them from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set HUMAN_DATASETS, and HUMAN_TERMS for the other species' pages of terms)" }, async () => {
  const out = await mkdtemp(path.join(os.tmpdir(), "human-build-"));
  try {
    const run = spawnSync("python3", [TOOL, "build", "--datasets", DATASETS, "--terms", TERMS, "--out-dir", out], { encoding: "utf8", timeout: 900000, maxBuffer: 1 << 26 });
    assert.equal(run.status, 0, run.stderr);
    for (const [name, text] of [["shelves.json", shelvesText], ["proteins.tsv", tableText], ["README.md", readme]]) assert.ok((await readFile(path.join(out, name), "utf8")) === text, `${name} is not what the tool builds from the saved downloads`);
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
