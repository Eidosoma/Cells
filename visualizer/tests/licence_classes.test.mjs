// Every data record of the viewer is held to the project's rule on sources (decision D173,
// 15 November 2026: "lets use them for analysis but ours is a commerical project bvut open
// source"). A source is of one of three classes:
//
//   permissive        CC BY, CC0, or a plain statement that no restriction is placed on use:
//                     values, tables and derived data may enter, with attribution;
//   non-commercial    a CC BY-NC licence of any kind, or a program given out for academic
//                     use only: analysis only. Nothing of it enters a record; a note may
//                     cite a single value, with the class beside it;
//   no stated terms   no open licence is stated, or its terms could not be read: nothing
//                     of it enters a record.
//
// What this file holds, for every record it finds under data/:
//
//   1. every source has a class and a licence text, and the two agree;
//   2. whatever stands behind a value (a fact's or a level's sources, a capability's, a
//      mark's source, a product's citation, a record's values_from) is permissive;
//   3. a source that is not permissive stands only where a pointer may stand, and says
//      that nothing is taken from it;
//   4. the note of each record has a section that names every such source;
//   5. a tool or rule system whose results a permissive database gives out is a source of
//      its own, with its own terms and `through`, the database its results were read in.
//      By the user's ruling of 15 November 2026 such a value stands on the terms of the
//      database it was read from, and the tool behind it is named and counted. Where the
//      tool is not permissive, it is in the register NAMED below, by species, so that a
//      new one is noticed and put to the user.
//
// It finds the records by their folders, so a record added later is held too. What it
// cannot see is a value written into a sentence with no source named: the tools that
// build the records check their sentences against saved texts of permissive sources.
// A paper cited in a note alone is held by the short list NOTE_ONLY below.
//
//   node --test tests/licence_classes.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const CLASSES = ["permissive", "non-commercial", "no stated terms"];
const SECTION = "## What rests on non-commercial or unlicensed sources";

// The class that a licence text gives. A text that names a non-commercial licence is
// never permissive, whatever else it says.
// A program given out under an academic licence, or for academic users only, is of the same
// class: its terms do not allow a commercial project to run it. A tool whose terms could not
// be read is held as one that states none.
const NON_COMMERCIAL = /CC BY-NC|^Academic licence\b|^For academic users only\b/;
const NO_TERMS = /^(No open licence stated|no licence stated|no open licence|Terms not read\b)/;
const PERMISSIVE = /^CC BY\b(?!-NC)|^CC0\b|[Nn]o restrictions?\b|places no restriction|[Ii]mposes no restrictions|no use restrictions|^Public domain|BSD 3-Clause|^Bibliographic facts only/;
function classOf(licence) {
  if (NON_COMMERCIAL.test(licence)) return "non-commercial";
  if (NO_TERMS.test(licence)) return "no stated terms";
  return PERMISSIVE.test(licence) ? "permissive" : null;
}

// Which note speaks for which record: by the species or the subject the record is of.
const NOTES = { syn3a: "docs/SYN3A.md", mpneumoniae: "docs/MPNEUMONIAE.md", planarian: "docs/PLANARIAN_ATLAS.md", planarian_bioelectric: "docs/PLANARIAN_BIOELECTRIC_EVIDENCE.md", human: "docs/HUMAN_PROTEOME.md", ecoli: "docs/ECOLI.md", fruitfly: "docs/FRUITFLY.md", thalecress: "docs/THALECRESS.md", mouse: "docs/MOUSE.md" };
// The register of the dependences that the user's ruling covers, by species: a tool or a
// rule system that is not permissive, whose results a permissive database gives out and a
// record rests on. The user ruled on 15 November 2026 that such a value stands on the
// terms of the database it was read from, and that the tool behind it is named and
// counted. So each is a source of its record with `through`, the database (or the
// databases, joined by " and ") its results were read in, and each is said in the
// record's note with its terms and its counts. The ruling is the project's rule and not a
// legal opinion, so the register is kept: a dependence that is not listed fails this
// file, so that a new one is noticed and put to the user before it is listed; one that
// is listed and no longer in its record fails it too, so the register does not outlive
// what it lists.
//
// JCVI-syn3A's lipid anchors rest on the matches of PROSITE's lipoprotein profile, as
// UniProt's archive records them. The human shelves' line is added with the human data.
const NAMED = {
  syn3a: { PROSITE: "UniParc" },
  mpneumoniae: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt" },
  planarian: { TMHMM: "WormBase ParaSite and UniProt", SignalP: "WormBase ParaSite and UniProt", Phobius: "UniProt", PROSITE: "UniProt" },
  human: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt", "big-PI": "UniProt" },
  // E. coli's line, added with its data on 15 November 2026: the tools M. pneumoniae's line names, by the user's word that the rule holds for every species.
  ecoli: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt" },
  // The fruit fly's line, added with its data on 15 November 2026: the eight tools the human's line names.
  fruitfly: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt", "big-PI": "UniProt" },
  // Thale cress's line, added with its data on 15 November 2026: the same eight tools.
  thalecress: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt", "big-PI": "UniProt" },
  // The mouse's line, added with its data on 16 November 2026: the same eight tools, none new.
  mouse: { PROSITE: "UniProt", TMHMM: "UniProt", Phobius: "UniProt", SignalP: "UniProt", TargetP: "UniProt", Memsat: "UniProt", Predotar: "UniProt", "big-PI": "UniProt" },
};
// Papers that only a note cites, and that are not permissive: its section names them too.
const NOTE_ONLY = {
  "docs/SYN3A.md": [["Hutchison", "2016"]],
  "docs/MPNEUMONIAE.md": [["Chen", "2016"], ["Dobbs", "2026"]],
  "docs/PLANARIAN_ATLAS.md": [["Ying", "2025"], ["Howe", "2017"], ["Rozanski", "2019"]],
};

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const listed = async (folder, keep) => (existsSync(folder) ? (await readdir(folder, { withFileTypes: true })).filter(keep).map((entry) => path.join(folder, entry.name)).sort() : []);
const isJson = (entry) => entry.isFile() && entry.name.endsWith(".json");

const DATA = path.join(ROOT, "data");
const speciesFiles = await listed(path.join(DATA, "species"), isJson);
const shapeFiles = await listed(path.join(DATA, "species", "shapes"), isJson);
const atlasFiles = await listed(path.join(DATA, "proteins", "atlases"), isJson);
const shelfFiles = (await listed(path.join(DATA, "proteins"), (entry) => entry.isDirectory())).map((folder) => path.join(folder, "shelves.json")).filter((file) => existsSync(file));
const evidenceFiles = await listed(path.join(DATA, "evidence"), isJson);
const machineFiles = await listed(path.join(DATA, "machines"), isJson);
// The switch's other entries (schema/ENTRIES.md): cell types of their own files, and model systems.
const entryFiles = [...(await listed(path.join(DATA, "cells"), isJson)), ...(await listed(path.join(DATA, "models"), isJson))];
const rel = (file) => path.relative(ROOT, file);

/** A source's class and licence, checked: both there, the class one of three, and the two in agreement. */
function held(source, where) {
  assert.ok(typeof source.licence === "string" && source.licence.trim(), `${where}: no licence text, and no word that none is stated`);
  assert.ok(CLASSES.includes(source.class), `${where}: its class is ${JSON.stringify(source.class)}, not one of ${CLASSES.join(", ")}`);
  assert.equal(source.class, classOf(source.licence), `${where}: the class does not follow from the licence "${source.licence}"`);
  return source.class;
}

/** What a note's section must hold for a paper: its first author's name, then its year. */
const named = (surname, year) => new RegExp(`${surname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^\\n|]{0,60}${year}`);
/** The first author's name and the year of a citation that begins "Name and others (2020)" or "Name and others 2020". */
function paperOf(text) {
  const found = /^([^\s,(]+)[^()\d]*\(?(\d{4})\)?/.exec(text);
  return found ? [found[1], found[2]] : null;
}

// What each note's section must name, gathered as the records are read: note -> [[label, pattern], ...].
const toName = new Map();
const mustName = (note, label, pattern) => toName.set(note, [...(toName.get(note) || []), [label, pattern]]);

test("the records are found: species, shapes, atlases, shelves, the evidence inventory and the machines", () => {
  assert.ok(speciesFiles.length >= 4 && atlasFiles.length >= 3 && shelfFiles.length >= 3 && evidenceFiles.length >= 1 && machineFiles.length >= 1, "a folder of records is missing or empty");
  for (const file of [...speciesFiles, ...atlasFiles, ...shelfFiles, ...evidenceFiles, ...machineFiles]) assert.ok(existsSync(file), rel(file));
});

test("a species file: every source has its class; facts, levels and capabilities rest on permissive sources; any other source is a pointer", async () => {
  for (const file of speciesFiles) {
    const species = await json(file);
    const where = rel(file);
    const sources = species.sources || {};
    for (const [key, source] of Object.entries(sources)) held(source, `${where}: source ${key}`);
    const permissive = (key) => sources[key]?.class === "permissive";
    // An open paper whose numbers alone the file takes (D186): only in the register below, and only behind a number.
    const register = NUMBERS_ONLY[path.basename(file)] || [];
    const numbersOnly = (key) => sources[key]?.standing === "open paper, numbers only" && register.includes(key);
    const basis = new Set();
    const pointed = new Set();
    for (const level of species.levels) {
      for (const key of level.sources || []) {
        assert.ok(permissive(key), `${where}: the ${level.id} level rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
        basis.add(key);
      }
    }
    for (const fact of species.cell.facts || []) {
      assert.ok(Array.isArray(fact.sources) && fact.sources.length, `${where}: the fact "${fact.label}" names no source`);
      for (const key of fact.sources) {
        assert.ok(permissive(key) || (numbersOnly(key) && /\d/.test(fact.value)), `${where}: the fact "${fact.label}" rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
        basis.add(key);
      }
      for (const key of fact.see || []) {
        assert.ok(sources[key], `${where}: the fact "${fact.label}" points to ${key}, which is not a source`);
        pointed.add(key);
      }
    }
    for (const [id, keys] of Object.entries(species.capability_sources || {})) {
      assert.ok(id in (species.cell.capabilities || {}), `${where}: ${id} has sources and no entry`);
      assert.ok(keys.length, `${where}: ${id} names no source`);
      for (const key of keys) {
        assert.ok(permissive(key), `${where}: ${id} rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
        basis.add(key);
      }
    }
    // A capability's words carry no number of their own: each number in them is a number
    // of a fact or of the cell's parts, or stands in a permissive source's citation.
    const backed = [...(species.cell.facts || []).map((fact) => fact.value), ...Object.values(sources).filter((source) => source.class === "permissive").map((source) => source.text), JSON.stringify(species.cell.parts || {})].join(" ").replace(/(\d),(\d)/g, "$1$2");
    for (const [id, item] of Object.entries(species.cell.capabilities || {})) {
      const words = `${item.why || ""} ${item.note || ""}`.replace(/(\d),(\d)/g, "$1$2").replace(/[A-Za-z]+-?[A-Za-z]*\d[\w.]*/g, " ");
      for (const number of words.match(/\d+(\.\d+)?/g) || []) assert.ok(new RegExp(`(^|[^\\d.])${number.replace(".", "\\.")}([^\\d]|$)`).test(backed), `${where}: ${id} gives ${number}, which no fact and no permissive source's citation holds`);
    }
    // A source that is not permissive: pointed to by a fact, behind nothing, and it says so.
    // The cell's parts give numbers too: each block's sources are permissive, or an open paper of the register with the place of its numbers.
    for (const [name, block] of Object.entries(species.cell.parts || {})) {
      if (!block || Array.isArray(block) || typeof block !== "object" || !block.sources) continue;
      for (const key of block.sources) {
        assert.ok(permissive(key) || numbersOnly(key), `${where}: cell.parts.${name} rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
        if (numbersOnly(key)) assert.ok(block.read?.source === key && block.read.where, `${where}: cell.parts.${name} takes numbers from ${key} and does not say where in it they stand`);
      }
    }
    const note = NOTES[species.id];
    for (const [key, source] of Object.entries(sources)) {
      if (source.class === "permissive") continue;
      if (numbersOnly(key)) {
        // Numbers alone: the citation, its DOI and where they stand; the note names it.
        assert.equal(source.class, "no stated terms", `${where}: ${key}`);
        assert.ok(source.doi && source.where, `${where}: ${key} has no DOI or no place for its numbers`);
        const paper = paperOf(source.text);
        assert.ok(paper, `${where}: the citation of ${key} does not begin with an author and a year`);
        if (note) mustName(note, `${key} (${where})`, named(...paper));
        continue;
      }
      assert.ok(source.standing !== "open paper, numbers only", `${where}: ${key} gives numbers with no licence declared and is not in the register NUMBERS_ONLY: put it to the user`);
      assert.ok(!basis.has(key), `${where}: ${key} is ${source.class} and something rests on it`);
      assert.ok(pointed.has(key), `${where}: ${key} is ${source.class} and no fact points to it: take it out, or point to it`);
      assert.match(source.licence, /nothing is taken from it/, `${where}: ${key} does not say that nothing is taken from it`);
      assert.ok(!/\d\s*(%|µm|nm|µM|mM|nM|mV|hours?|minutes?|copies|ribosomes|proteins|genes|nutrients|complexes)\b/.test(source.text.replace(/\(\d{4}\)/g, "").replace(/\d+:[\w.-]+\.?/g, "")), `${where}: the pointer ${key} gives a value in its text: ${source.text}`);
      assert.ok(note, `${where}: ${key} is ${source.class}, and no note is known for this species: add one to NOTES`);
      const paper = paperOf(source.text);
      assert.ok(paper, `${where}: the citation of ${key} does not begin with an author and a year`);
      mustName(note, `${key} (${where})`, named(...paper));
    }
  }
});

test("a cell type's or a model system's file: every source has its class; its facts and levels rest on permissive sources, a number alone on an open paper's; any other source is a pointer", async () => {
  for (const file of entryFiles) {
    const entry = await json(file);
    const where = rel(file);
    const sources = entry.sources || {};
    for (const [key, source] of Object.entries(sources)) held(source, `${where}: source ${key}`);
    const basis = new Set();
    const stands = (key, numbersOnly) => sources[key]?.class === "permissive" || (numbersOnly && sources[key]?.standing === "open paper, numbers only");
    for (const level of entry.levels || []) for (const key of level.sources || []) {
      assert.ok(stands(key, false), `${where}: the ${level.id} level rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
      basis.add(key);
    }
    for (const fact of entry.facts || []) {
      assert.ok(Array.isArray(fact.sources) && fact.sources.length, `${where}: the fact "${fact.label}" names no source`);
      for (const key of fact.sources) {
        assert.ok(stands(key, /\d/.test(fact.value)), `${where}: the fact "${fact.label}" rests on ${key}, which is ${sources[key]?.class ?? "not a source"}`);
        basis.add(key);
      }
    }
    for (const [key, source] of Object.entries(sources)) {
      if (source.class === "permissive" || source.standing === "open paper, numbers only") continue;
      assert.ok(!basis.has(key), `${where}: ${key} is ${source.class} and something rests on it`);
      assert.match(source.licence, /nothing is taken from it/, `${where}: ${key} does not say that nothing is taken from it`);
    }
  }
});

// The open papers whose numbers alone a machine file may take, with no licence declared: the
// user's ruling of 16 November 2026 ("you can use any numbers from open papers even if no
// licence is decrlared"). Each is named here, by machine file and key, so that a new one is
// seen; the file holds the number, the citation and the place in the paper, and none of its text.
// Deme and others 2020 was taken out on 16 November 2026, because its manuscript's own text
// states terms for academic research, and the ruling is for papers with none. A species file
// is named by its file too: E. coli's envelope (17 November 2026), each paper read at PubMed
// Central for a limit on use in its own text, and stating none.
// By the user's ruling of 17 November 2026, numbers from papers that are free to read but not open access may be used, each with its citation.
const NUMBERS_ONLY = { "ecoli.json": ["matias2003", "berry2010"] };

// The Machines catalogue (schema/MACHINE_CATALOGUE.md): its sources are copied with their terms from the species files
// it reads, and whatever it gives (the words that name a machine, a count, a size) rests on a permissive one.
const catalogueFiles = await listed(path.join(DATA, "catalogue"), (entry) => isJson(entry) && entry.name !== "overlay.json");

test("the Machines catalogue: every source has its class, and what names a machine, counts it or sizes it rests on a permissive source", async () => {
  assert.equal(catalogueFiles.length, 1, "data/catalogue/ holds the catalogue and its overlay");
  for (const file of catalogueFiles) {
    const catalogue = await json(file);
    const where = rel(file);
    for (const [key, source] of Object.entries(catalogue.sources || {})) held(source, `${where}: source ${key}`);
    for (const entry of catalogue.entries) {
      for (const [name, block] of Object.entries({ named: entry.named, count: entry.count, size: entry.size })) {
        for (const key of block?.sources || []) assert.equal(catalogue.sources[key]?.class, "permissive", `${where}: ${entry.species} ${entry.id}'s ${name} rests on ${key}, which is ${catalogue.sources[key]?.class ?? "not a source"}`);
      }
    }
  }
});

test("a machine file: every source has its class; its sentences are of permissive sources; an open paper with no licence gives numbers alone, and is in the register", async () => {
  assert.ok(machineFiles.length >= 1, "no machine file was found");
  for (const file of machineFiles) {
    const machine = await json(file);
    const where = rel(file), name = path.basename(file);
    const sources = machine.sources || {};
    for (const [key, source] of Object.entries(sources)) held(source, `${where}: source ${key}`);
    const register = NUMBERS_ONLY[name] || [];
    for (const [key, source] of Object.entries(sources)) {
      if (source.class === "permissive") continue;
      assert.equal(source.standing, "open paper, numbers only", `${where}: ${key} is ${source.class} and is not an open paper whose numbers alone are taken`);
      assert.ok(register.includes(key), `${where}: ${key} gives numbers with no licence declared and is not in the register NUMBERS_ONLY: put it to the user`);
      assert.equal(source.class, "no stated terms", `${where}: ${key}`);
      assert.ok(source.doi, `${where}: ${key} has no DOI`);
    }
    for (const key of register) assert.equal(sources[key]?.standing, "open paper, numbers only", `${where}: the register names ${key}, which the file does not take numbers from`);
    // A sentence quoted in the file is of a permissive source; a number from another rests on its place in the paper.
    for (const [key, sentence] of Object.entries(machine.sentences || {})) assert.equal(sources[sentence.source]?.class, "permissive", `${where}: the sentence ${key} is of ${sentence.source}`);
    const reads = [];
    JSON.stringify(machine, (field, value) => (field === "read" && value && !Array.isArray(value) && typeof value === "object" ? (reads.push(value), value) : value));
    for (const read of reads) assert.ok(register.includes(read.source) && read.where, `${where}: a number read from ${read.source} with ${read.where ? "" : "no place, and "}${register.includes(read.source) ? "" : "no entry in the register"}`);
  }
});

test("a shape file holds no source of its own: what its sizes rest on is in the species file", async () => {
  for (const file of shapeFiles) {
    const text = await readFile(file, "utf8");
    assert.ok(!/"sources?"\s*:/.test(text), `${rel(file)} names a source: give it in the species file, with its class`);
    assert.ok(!/preprint|search digest|web search/i.test(JSON.parse(text).note || ""), `${rel(file)}: its note rests a size on something that was not read at its source`);
  }
});

test("a species atlas: everything it takes is from a permissive source; a paper of any other class is cited for a name that a permissive record carries", async () => {
  for (const file of atlasFiles) {
    const atlas = await json(file);
    const where = rel(file);
    assert.ok(atlas.sources.length, where);
    for (const source of atlas.sources) assert.equal(held(source, `${where}: source ${source.name}`), "permissive", `${where}: the atlas takes something from ${source.name}`);
    const byName = new Map(atlas.sources.map((source) => [source.name, source]));
    const products = [...Object.entries(atlas.units).flatMap(([id, unit]) => unit.products.map((product) => [id, product])), ...(atlas.extra || []).map((product) => ["extra", product])];
    for (const [unit, product] of products) {
      const label = `${where}: ${unit}, ${product.gene || product.name}`;
      if (!product.citation) {
        assert.ok(!("name_record" in product), label);
        continue;
      }
      assert.ok(CLASSES.includes(product.citation.class), `${label}: its citation has no class`);
      if (product.citation.class === "permissive") continue;
      // The paper may not stand behind anything: the name it is cited for stands in a permissive record.
      assert.ok(product.name_record?.id && byName.get(product.name_record.source)?.class === "permissive", `${label}: cited from a paper that is ${product.citation.class}, with no permissive record of the name`);
      assert.ok(product.evidence_note.includes(product.name_record.id) || product.ids.some((id) => id.id === product.name_record.id), `${label}: the record that carries the name is not shown`);
      const paper = paperOf(product.citation.text);
      assert.ok(paper && NOTES[atlas.species.id], `${label}: no note is known for this species`);
      mustName(NOTES[atlas.species.id], `${product.citation.text.slice(0, 40)} (${where})`, named(...paper));
    }
  }
});

test("a species' shelves: every mark rests on a permissive source; any other source is a pointer, or a named dependence that says through which permissive source it was read", async () => {
  const seen = new Set();
  for (const file of shelfFiles) {
    const shelves = await json(file);
    const where = rel(file);
    seen.add(shelves.species);
    const known = NAMED[shelves.species] || {};
    const byName = new Map(shelves.sources.map((source) => [source.name, source]));
    assert.equal(byName.size, shelves.sources.length, `${where}: two sources share a name`);
    for (const source of shelves.sources) held(source, `${where}: source ${source.name}`);
    // What was taken is taken from a permissive source that stands for itself.
    const taken = (source) => source.class === "permissive" && !source.through;
    for (const [name, mark] of Object.entries(shelves.marks || {})) {
      // A mark names what it rests on: one or more of the file's sources, or a table of
      // the same folder, which is built from them. It names at least one source that the
      // value was taken from, and that one is permissive. Where it also names the tool
      // behind the value, that tool is a source read through another (below).
      const rests = shelves.sources.filter((source) => String(mark.source).includes(source.name));
      const ownTable = /^[\w.-]+\.tsv$/.test(String(mark.source)) && existsSync(path.join(path.dirname(file), mark.source));
      assert.ok(rests.length || ownTable, `${where}: the mark ${name} rests on "${mark.source}", which names no source of the file`);
      assert.ok(ownTable || rests.some(taken), `${where}: the mark ${name} names no permissive source that its values were taken from`);
      for (const source of rests) assert.ok(taken(source) || source.through, `${where}: the mark ${name} rests on ${source.name}, which is ${source.class}`);
    }
    for (const source of shelves.sources) {
      if (source.through) {
        // A tool or rule system whose results were read in a permissive database: the
        // database is named, it is a source of the file that stands for itself, and
        // nothing of the tool's own was taken. The value stands on that database's terms
        // (the user's ruling of 15 November 2026); the tool is named and counted, and one
        // that is not permissive is in the register.
        assert.equal(typeof source.through, "string", `${where}: ${source.name}: through is the name of a source, or names joined by " and "`);
        for (const database of byName.has(source.through) ? [source.through] : source.through.split(" and ")) assert.ok(byName.has(database) && taken(byName.get(database)), `${where}: ${source.name} is read through ${database}, which is not a permissive source of the file that stands for itself`);
        assert.match(source.holds, /^Nothing was downloaded from it/, `${where}: ${source.name}`);
        if (source.class !== "permissive") assert.equal(known[source.name], source.through, `${where}: ${source.name} is ${source.class} and is read through ${source.through}. It is not in the register NAMED for ${shelves.species}: a new dependence is put to the user before it is listed there`);
      } else if (source.class !== "permissive") {
        assert.match(source.holds, /^Nothing is taken from it: a pointer to /, `${where}: ${source.name} is ${source.class} and is not said to be a pointer`);
        assert.ok(!/\d/.test(source.holds), `${where}: the pointer ${source.name} gives a number: ${source.holds}`);
      }
      if (source.class === "permissive") continue;
      const note = NOTES[shelves.species];
      assert.ok(note, `${where}: ${source.name} is ${source.class}, and no note is known for this species`);
      const paper = /\d{4}$/.test(source.name) ? paperOf(source.name) : null;
      mustName(note, `${source.name} (${where})`, paper ? named(...paper) : new RegExp(source.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    }
    // The list does not outlive the dependences: each one named is in the record.
    for (const [name, through] of Object.entries(known)) assert.equal(byName.get(name)?.through, through, `${where}: NAMED lists ${name} through ${through}, and the record does not`);
  }
  for (const species of Object.keys(NAMED)) assert.ok(seen.has(species), `NAMED lists dependences for ${species}, and no shelves of it were found`);
});

// A quantity: a number with a unit, a span of residues, or a number in words before a unit of time.
const QUANTITY = /\d+(?:\.\d+)?\s*(?:±\s*\d+(?:\.\d+)?\s*)?-?(?:nM|µM|mM|mV|µV|kHz|Hz|ms|min\b|minutes?|hours?|days?|weeks?|months?|%|µm|mm\b|cm\b|nm\b|°C|residues|fold|V\b|M\b|s\b|h\b)|residues \d+|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|ninety|hundred|thousand)[- ](?:seconds?|minutes?|hours?|days?|weeks?|months?|fold|percent|per cent)\b/i;

test("an evidence inventory: every paper, sequence record and deposit has its class, and a value is given only from a permissive paper", async () => {
  for (const file of evidenceFiles) {
    const inventory = await json(file);
    const where = rel(file);
    assert.match(inventory.format || "", /^cells\.visualizer\.\w+_evidence@\d+$/, `${where}: a record this test does not know how to hold`);
    assert.deepEqual(Object.keys(inventory.licence_classes || {}), CLASSES, `${where}: the classes are not declared`);
    const papers = new Map();
    for (const paper of [...inventory.papers, ...(inventory.context || []), ...(inventory.leads_not_audited || [])]) {
      held(paper, `${where}: paper ${paper.id}`);
      papers.set(paper.id, paper);
    }
    const note = NOTES[path.basename(file, ".json")];
    assert.ok(note, `${where}: no note is known for this inventory`);
    for (const paper of papers.values()) {
      // The first author's family name: the authors are written "Name AB, Other CD".
      if (paper.class !== "permissive") mustName(note, `${paper.id} (${where})`, named(paper.authors.split(",")[0].replace(/\.$/, "").replace(/ [A-Z]+$/, ""), paper.year));
    }
    for (const record of inventory.records) {
      const label = `${where}: ${record.id}`;
      const permissive = record.papers.filter((id) => papers.get(id)?.class === "permissive");
      assert.deepEqual(record.values_from, permissive, `${label}: values_from is not the record's permissive papers`);
      for (const sequence of record.sequences || []) assert.equal(held(sequence, `${label}: sequence ${sequence.accession}`), "permissive", label);
      if (record.deposit?.licence) held(record.deposit, `${label}: its deposit`);
      if (permissive.length === record.papers.length) continue;
      // A paper of the record is not permissive: no quantity is given, since nothing says
      // which paper it would be from. (A record of several papers may give one once it
      // names the permissive paper it is from; today none does.)
      const words = [record.measured, record.how, record.values, record.could_test, record.note || "", record.deposit?.note || "", ...(record.genes || []).map((gene) => gene.note || "")];
      for (const text of words) assert.ok(!QUANTITY.test(text), `${label} gives a quantity, and a paper of the record has terms that do not allow it: "${QUANTITY.exec(text)?.[0]}" in "${text}"`);
      if (permissive.length) continue;
      // None of its papers is permissive: what was measured and how stay, in words, and no quotation does.
      assert.match(record.values, /The values are in the papers?, [^.]*: none is given here\.$/, `${label}: it does not say where its values are`);
      for (const text of [record.measured, record.how, record.values]) assert.ok(!/'[^']{12,}'|"[^"]{12,}"|‘[^’]{12,}’|“[^”]{12,}”/.test(text), `${label} quotes a paper whose terms do not allow it: ${text}`);
    }
    for (const entry of inventory.family_summary || []) for (const [field, text] of Object.entries(entry)) assert.ok(!QUANTITY.test(text), `${where}: family_summary.${entry.family}.${field} gives a quantity: ${text}`);
  }
});

test("each note says what rests on non-commercial or unlicensed sources, and names every such source its records cite", async () => {
  for (const [note, papers] of Object.entries(NOTE_ONLY)) for (const [surname, year] of papers) mustName(note, `${surname} ${year}, cited in the note alone`, named(surname, year));
  assert.ok(toName.size >= 4, "the tests above gather what the notes must name; run the whole file");
  for (const [note, wanted] of toName) {
    const text = await readFile(path.join(ROOT, note), "utf8");
    const from = text.indexOf(`\n${SECTION}\n`);
    assert.ok(from >= 0, `${note} has no section "${SECTION.slice(3)}"`);
    const next = text.indexOf("\n## ", from + SECTION.length);
    const section = text.slice(from, next < 0 ? undefined : next);
    // The section states the rule: the three classes, by name.
    for (const word of ["Permissive", "Non-commercial", "No stated terms"]) assert.ok(section.includes(word), `${note}: the section does not name the class "${word}"`);
    for (const [label, pattern] of wanted) assert.ok(pattern.test(section), `${note}: the section does not name ${label}`);
  }
});
