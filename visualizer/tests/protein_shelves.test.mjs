// A species' own proteins on the atlas's shelves (schema/SPECIES_PROTEINS.md): how the page
// reads a species' file, where each marker stands, what is said of a protein and a family,
// which of the two the atlas opens on, what the scene carries, and how the files get beside
// the page.
//
// The species used here are made up, in temporary folders: no behaviour is checked against a
// species file of the repository. The repository's own files are held to the contract at
// the end, whichever they are. Nothing needs a browser.
//
//   node --test tests/protein_shelves.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT, buildPage, proteinFiles } from "../tools/lib/build_page.mjs";
import { createServer } from "../tools/serve.mjs";
import { validate } from "../src/scene/model.js";
import { css } from "../src/ui/styles.js";
import { firstMode, shelvesOf } from "../src/lenses/proteins.js";
import { freeOf, shapeFor } from "../src/lenses/shelves_view.js";
import {
  BASES,
  MEMBERS_FORMAT,
  OWN_FAMILY,
  OWN_PART,
  PITCH,
  SHELVES_FORMAT,
  SIDES,
  Shelves,
  familyRadius,
  keyOf,
  layoutDish,
  layoutShelves,
  licenceClass,
  loadBeside,
  parseKey,
  validateShelves,
} from "../src/lenses/protein_shelves.js";

const PROTEINS = path.join(ROOT, "data", "proteins");
const OVERLAY = JSON.parse(await readFile(path.join(PROTEINS, "overlay.json"), "utf8"));
const SNAPSHOT = JSON.parse(await readFile(path.join(PROTEINS, "inventory.snapshot.json"), "utf8"));
const contract = await readFile(path.join(ROOT, "schema", "SPECIES_PROTEINS.md"), "utf8");
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const UNITS = new Map(SNAPSHOT.units.map((unit) => [unit.id, `unit.${unit.id}`]));
const distance = (a, b) => Math.hypot(a.dx - b.dx, a.dz - b.dz);

// ---------------------------------------------------------------- two made-up species

const SOURCES = [
  { name: "Made-up catalogue", url: "https://www.uniprot.org/", licence: "CC BY 4.0", holds: "the proteins and their names" },
  { name: "Closed paper", url: "https://doi.org/10.1000/closed", licence: "CC BY-NC-ND 4.0; read for one number", holds: "one number, for comparison" },
  { name: "Old paper", licence: "Read for one sentence of its abstract", holds: "one sentence" },
];

/** A small catalogue: one line for each protein. `more` adds that many plain proteins inside the cell. */
function madeUpSmall({ more = 0, change = () => {} } = {}) {
  const proteins = [
    ["TB_001", "Sodium channel", "nach", "cell", "in", "predicted", "transport", 1800, "U01", { essential: "essential", seen: true }],
    ["TB_002", "Sugar pump", "", "cell", "in", "predicted", "transport", 640, null, { essential: "non-essential", seen: false }],
    ["TB_003", "Surface lipoprotein", "slp", "cell", "outside", "predicted", "transport", 210, null, { essential: "non-essential", anchor: true }],
    ["TB_004", "Ribosomal protein L1", "rplA", "cell", "inside", "by function", "making", 230, null, { essential: "essential", complex: "ribosome", amount: 1500, seen: true }],
    ["TB_005", "Ribosomal protein L2", "rplB", "cell", "inside", "by function", "making", 270, null, { essential: "essential", complex: "ribosome", seen: true }],
    ["TB_006", "Ribosomal protein L3", "rplC", "cell", "inside", "by function", "making", 210, null, { essential: "essential", complex: "ribosome", seen: true }],
    ["TB_007", "Initiation factor", "infA", "cell", "inside", "stated", "making", 72, null, { essential: "essential" }],
    ["TB_008", "Unnamed protein", "", "cell", "not known", "none", "odd", 120, null, {}],
    ["TB_009", "Another unnamed protein", "", "cell", "not known", "none", "odd", 95, null, {}],
  ];
  for (let index = 0; index < more; index++) proteins.push([`TB_1${String(index).padStart(3, "0")}`, `Enzyme ${index}`, "", "cell", index % 7 === 0 ? "in" : "inside", "predicted", index % 3 ? "making" : "transport", 300, null, { essential: index % 2 ? "essential" : "non-essential" }]);
  const data = {
    format: SHELVES_FORMAT,
    species: "testbug",
    made: "2026-11-15",
    from: "A made-up record: every protein product",
    shelves: [{ id: "cell", label: "Cell membrane", outside: "Outside the cell", inside: "Inside the cell" }],
    groups: [
      { id: "transport", label: "Transport", from: "made up" },
      { id: "making", label: "Making proteins", within: "Information", from: "made up" },
      { id: "odd", label: "No class", within: "Unclear", from: "made up" },
    ],
    columns: ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"],
    proteins,
    side_notes: {
      stated: "A curated entry states it.",
      predicted: "Read from the sequence by a made-up predictor. It rests on Closed paper, which is under a non-commercial licence.",
      "by function": "Taken from the protein's name.",
      none: "Nothing says where it is.",
    },
    marks: {
      essential: { label: "Essentiality", values: ["essential", "non-essential"], measured: true, source: "Made-up catalogue" },
      seen: { label: "Seen in the proteomics", values: [true, false], measured: true, source: "Made-up catalogue" },
      anchor: { label: "Lipid anchor read from the sequence", values: [true], measured: false, note: "The lipoprotein signature.", source: "Made-up catalogue" },
      complex: { label: "Assembly", values: ["ribosome"], measured: false, source: "Made-up catalogue" },
      amount: { label: "Estimated copies in a cell", values: "number", measured: false, note: "An estimate.", source: "Made-up catalogue" },
    },
    sources: SOURCES,
  };
  data.counts = Object.fromEntries(SIDES.map((side) => [side, proteins.filter((line) => line[4] === side).length]));
  change(data);
  return data;
}

/**
 * A large catalogue: families that open, and "no family" in parts. Returns the shelves file
 * and the two files of members, as the page builder would write them.
 */
function madeUpFamilies() {
  // id, label, group, sides of its members, units
  const families = [
    ["IPR000001", "Innexin-like", "channels", { in: 7, inside: 1 }, ["U37"]],
    ["IPR000002", "Kinase", "signalling", { inside: 5 }, []],
    ["IPR000003", "Small channel", "channels", { in: 3 }, ["U01", "U02"]],
    ["IPR000004", "Tiny channel", "channels", { in: 2 }, []],
    ["IPR000005", "Lone receptor", "signalling", { inside: 1 }, []],
    ["IPR000006", "Receptor four", "signalling", { inside: 3, "not known": 1 }, []],
    ["IPR000007", "Secreted pair", "signalling", { outside: 2 }, []],
  ];
  const parts = [
    ["IPR100001", "Wide superfamily", "superfamily", "signalling", { inside: 11, in: 1 }],
    ["IPR100002", "Small superfamily", "superfamily", "signalling", { inside: 4 }],
    ["IPR100003", "Smaller superfamily", "superfamily", "signalling", { inside: 3 }],
    ["none", "No signature of any kind", "no signature", null, { inside: 3, outside: 1, in: 1, "not known": 1 }],
  ];
  const majority = (sides) => ["in", "outside", "inside", "not known"].reduce((best, side) => ((sides[side] || 0) > (sides[best] || 0) ? side : best), "in");
  const files = { "members-00.json": [], "members-01.json": [] };
  let serial = 0;
  const members = (file, label, sides, units) => {
    const from = files[file].length;
    for (const [side, count] of Object.entries(sides)) {
      for (let index = 0; index < count; index++) {
        serial += 1;
        const carries = units.length && side === "in" ? units : null;
        files[file].push([`tgM${String(serial).padStart(4, "0")}`, serial % 4 ? label : "", "", side, side === "not known" ? "none" : "predicted", 200 + serial, carries, { helices: side === "in" ? 4 : 0, kind: serial % 5 ? "gene model" : "unreviewed entry" }]);
      }
    }
    return [from, files[file].length];
  };
  const count = (sides) => Object.values(sides).reduce((sum, n) => sum + n, 0);
  const familyRows = families.map(([id, label, group, sides, units]) => [id, label, "cell", majority(sides), group, count(sides), sides, "members-00.json", members("members-00.json", label, sides, units), units, group === "channels" ? ["plasma membrane"] : []]);
  const partRows = parts.map(([id, label, kind, group, sides]) => [id, label, kind, majority(sides), group, count(sides), sides, "members-01.json", members("members-01.json", label, sides, [])]);
  const all = [...families.map((item) => item[3]), ...parts.map((item) => item[4])];
  const data = {
    format: SHELVES_FORMAT,
    species: "testworm",
    made: "2026-11-15",
    from: "A made-up table of gene models.",
    predicted: true,
    shelves: [{ id: "cell", label: "The cell's membranes, not told apart", outside: "Beyond a membrane: outside the cell, or within one of its compartments", inside: "Inside the cell: in the cytoplasm or the nucleus" }],
    groups: [
      { id: "channels", label: "Channels", from: "made up" },
      { id: "signalling", label: "Receptors and signalling", from: "made up" },
    ],
    family_from: "A family is a made-up entry.",
    family_columns: ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units", "where"],
    families: familyRows,
    no_family: {
      label: "No family assigned",
      count: partRows.reduce((sum, row) => sum + row[5], 0),
      sides: Object.fromEntries(SIDES.map((side) => [side, parts.reduce((sum, part) => sum + (part[4][side] || 0), 0)]).filter(([, n]) => n)),
      parts_from: "A protein with no family is filed under a superfamily, or under no signature.",
      part_columns: ["id", "label", "kind", "side", "group", "count", "sides", "file", "at"],
      parts: partRows,
    },
    member_columns: ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
    side_notes: { predicted: "A made-up predictor, run on predicted proteins.", "not known": "Nothing was predicted." },
    marks: { helices: { label: "Helices predicted", measured: false, source: "Made-up catalogue" }, kind: { label: "What the line is", values: ["gene model", "unreviewed entry"], measured: false, source: "Made-up catalogue" } },
    counts: Object.fromEntries(SIDES.map((side) => [side, all.reduce((sum, sides) => sum + (sides[side] || 0), 0)])),
    sources: SOURCES.slice(0, 1),
  };
  const memberFiles = Object.fromEntries(Object.entries(files).map(([name, lines]) => [name, { format: MEMBERS_FORMAT, species: "testworm", file: name, columns: data.member_columns, members: lines }]));
  return { data, memberFiles };
}

const LINKS = {
  testbug: [{ text: "Look up {id}", url: "https://www.ncbi.nlm.nih.gov/protein/?term={id}" }],
  testworm: [
    { kind: "gene model", text: "Gene model {id}", url: "https://parasite.wormbase.org/Gene/Summary?g={id}" },
    { kind: "unreviewed entry", text: "UniProt {id}", url: "https://www.uniprot.org/uniprotkb/{id}/entry" },
  ],
  family: { text: "InterPro {id}", url: "https://www.ebi.ac.uk/interpro/entry/InterPro/{id}/" },
};
const small = () => new Shelves(madeUpSmall(), { label: "Test bug", organism: "Bacillus probatus", links: LINKS, units: UNITS });
function large({ loaded = true } = {}) {
  const { data, memberFiles } = madeUpFamilies();
  const shelves = new Shelves(data, { label: "Test worm", links: LINKS, units: UNITS });
  if (loaded) for (const [name, file] of Object.entries(memberFiles)) shelves.addMembers(name, file);
  return shelves;
}

// ---------------------------------------------------------------- the file, as the page reads it

test("the contract's words are the reader's", () => {
  for (const side of SIDES) assert.ok(contract.includes(`\`${side}\``), `the contract does not name the side ${side}`);
  for (const basis of BASES) assert.ok(contract.includes(`\`${basis}\``), `the contract does not name the basis ${basis}`);
  assert.ok(contract.includes(SHELVES_FORMAT) || contract.includes("species_proteins@1"));
  assert.ok(contract.includes(MEMBERS_FORMAT));
});

test("a small catalogue is one marker for each protein, each on its side", () => {
  const shelves = small();
  assert.equal(shelves.kind, "proteins");
  assert.equal(shelves.total, 9);
  assert.equal(shelves.markers.length, 9);
  assert.deepEqual(shelves.counts, { outside: 1, in: 2, inside: 4, "not known": 2 });
  assert.deepEqual(shelves.byBasis(), { stated: 1, predicted: 3, "by function": 3, none: 2 });
  const first = shelves.get(keyOf("testbug", "p", "TB_001"));
  assert.deepEqual([first.label, first.gene, first.side, first.basis, first.units], ["Sodium channel", "nach", "in", "predicted", ["U01"]]);
  assert.deepEqual(parseKey(first.key), { species: "testbug", type: "p", id: "TB_001" });
  assert.equal(parseKey("unit.U01"), null);
  assert.equal(shelves.get("own:testbug:p:nobody"), null);
});

test("what breaks the contract is said, and such a file is not read", () => {
  assert.deepEqual(validateShelves(madeUpSmall()), []);
  assert.match(validateShelves({ format: "something else" })[0], /its format is something else/);
  const badSide = madeUpSmall({ change: (data) => (data.proteins[0][4] = "nearby") });
  assert.match(validateShelves(badSide).join(" "), /TB_001: the side nearby/);
  const badGroup = madeUpSmall({ change: (data) => (data.proteins[1][6] = "nowhere") });
  assert.match(validateShelves(badGroup).join(" "), /TB_002: the group nowhere is not declared/);
  assert.throws(() => new Shelves(badSide), /does not follow its format/);
  const { data } = madeUpFamilies();
  delete data.no_family;
  assert.match(validateShelves(data).join(" "), /where the proteins with no family are/);
});

test("a large catalogue is families that open: one of five or more has its own marker, smaller ones are gathered by district and side", () => {
  const shelves = large({ loaded: false });
  assert.equal(shelves.kind, "families");
  assert.equal(shelves.total, 25 + 25, "every protein counts: those in families and those with none");
  assert.equal(OWN_FAMILY, 5);
  assert.equal(OWN_PART, 10);
  const marker = (type, id) => shelves.markers.find((item) => item.key === keyOf("testworm", type, id));
  // Families of five or more stand alone.
  assert.ok(marker("f", "IPR000001") && marker("f", "IPR000002"));
  assert.equal(marker("f", "IPR000003"), undefined, "a family of three has no marker of its own");
  // The smaller ones: one marker for a district and a side, which holds them.
  const channels = marker("m", "channels|in");
  assert.deepEqual(channels.holds.map((family) => family.id), ["IPR000003", "IPR000004"]);
  assert.equal(channels.count, 5);
  assert.equal(channels.label, "2 smaller families");
  assert.deepEqual(channels.units, ["U01", "U02"], "a gathering holds what its families hold");
  assert.deepEqual(marker("m", "signalling|inside").holds.map((family) => family.id), ["IPR000005", "IPR000006"]);
  assert.equal(marker("m", "signalling|outside").label, "1 smaller family");
  // "No family": a part of ten or more alone, one that is not a superfamily alone whatever its size, the rest gathered.
  assert.ok(marker("g", "IPR100001"));
  assert.ok(marker("g", "none"), "the proteins with no signature are one marker of their own");
  assert.deepEqual(marker("n", "no-family|inside").holds.map((part) => part.id), ["IPR100002", "IPR100003"]);
  assert.equal(marker("n", "no-family|inside").label, "2 smaller groups");
  // Every protein is behind exactly one marker.
  assert.equal(shelves.markers.reduce((sum, item) => sum + item.count, 0), shelves.total);
  assert.equal(shelves.districtLabel(marker("g", "none")), "No family assigned");
});

test("a family opens to its members once their file is in, and a gathering to the members of all its families", () => {
  const { data, memberFiles } = madeUpFamilies();
  const shelves = new Shelves(data, { label: "Test worm", units: UNITS });
  const innexin = shelves.get(keyOf("testworm", "f", "IPR000001"));
  const gathering = shelves.get(keyOf("testworm", "m", "channels|in"));
  assert.deepEqual(shelves.filesOf(innexin), ["members-00.json"]);
  assert.equal(shelves.membersOf(innexin), null, "nothing before the file is in");
  assert.throws(() => shelves.addMembers("members-00.json", { format: "other" }), /not a file of members/);
  shelves.addMembers("members-00.json", memberFiles["members-00.json"]);
  const members = shelves.membersOf(innexin);
  assert.equal(members.length, 8);
  assert.deepEqual(members.map((member) => member.side).sort(), ["in", "in", "in", "in", "in", "in", "in", "inside"]);
  assert.ok(members.every((member) => member.under === innexin && shelves.get(member.key) === member));
  assert.equal(members.find((member) => !member.label), undefined, "a member with no name of its own takes its family's");
  assert.deepEqual(members[0].units, ["U37"]);
  const held = shelves.membersOf(gathering);
  assert.equal(held.length, 5);
  assert.deepEqual([...new Set(held.map((member) => member.under.id))], ["IPR000003", "IPR000004"], "family by family");
  // A file of another catalogue is refused, not shown.
  const other = new Shelves(madeUpFamilies().data, {});
  other.addMembers("members-00.json", { ...memberFiles["members-00.json"], members: memberFiles["members-00.json"].members.slice(3) });
  assert.throws(() => other.membersOf(other.get(keyOf("testworm", "f", "IPR000007"))), /not the 2 stated/);
});

// ---------------------------------------------------------------- the words

test("a protein's panel gives its name, gene, identifier, side and how that is known, its marks, a link out and the sources", () => {
  const shelves = small();
  const said = shelves.describe(keyOf("testbug", "p", "TB_004"));
  assert.equal(said.label, "Ribosomal protein L1");
  assert.equal(said.eyebrow, "Test bug protein");
  assert.match(said.plain, /^It is inside the cell\. That is taken from what the protein is annotated to do, not measured\.$/);
  const facts = Object.fromEntries(said.facts);
  assert.equal(facts.Identifier, "TB_004");
  assert.equal(facts.Gene, "rplA");
  assert.equal(facts.District, "Information: Making proteins", "with the wider class the file names");
  assert.equal(facts.Essentiality, "essential (measured)");
  assert.equal(facts["Estimated copies in a cell"], "1,500", "an estimate is not called measured");
  assert.equal(facts.Assembly, "ribosome");
  assert.deepEqual(said.chips.map((chip) => chip.label), ["No law in Cells", "Inside the cell", "By function"]);
  assert.deepEqual(said.sections.map((section) => section.title), ["Look it up", "Sources and licences"]);
  assert.deepEqual(said.sections[0].items[0].links, [{ text: "Look up TB_004", url: "https://www.ncbi.nlm.nih.gov/protein/?term=TB_004" }]);
  assert.match(said.disclosures[0].title, /taken from function/);
  assert.deepEqual(said.related, []);
  // A side that is predicted says so; one that is not known is never given a place in words either.
  assert.match(shelves.describe(keyOf("testbug", "p", "TB_002")).plain, /^It spans the cell membrane\. That is predicted from its sequence; it was not measured\.$/);
  assert.match(shelves.describe(keyOf("testbug", "p", "TB_003")).plain, /^It is outside the cell\./);
  const unknown = shelves.describe(keyOf("testbug", "p", "TB_008"));
  assert.match(unknown.plain, /^Its side of the membrane is not known\. .* set apart and not placed by guess\.$/);
  assert.deepEqual(unknown.chips.map((chip) => chip.label), ["No law in Cells", "Side not known", "Not known"]);
  // A mark that can be either says "no"; one that is only ever set is left out when it is not.
  assert.equal(Object.fromEntries(shelves.describe(keyOf("testbug", "p", "TB_002")).facts)["Seen in the proteomics"], "no (measured)");
  assert.equal(Object.fromEntries(shelves.describe(keyOf("testbug", "p", "TB_002")).facts)["Lipid anchor read from the sequence"], undefined);
  assert.equal(shelves.describe("own:testbug:p:nobody"), null);
});

test("only a protein with a unit is tied to a machine Cells has a law for, and the words stop there", () => {
  const shelves = small();
  const channel = shelves.describe(keyOf("testbug", "p", "TB_001"));
  assert.equal(channel.chips[0].label, "Would make a machine Cells has a law for");
  assert.match(channel.chips[0].title, /the engine does not model this protein/);
  assert.deepEqual(channel.related, [{ title: "Drawn in the atlas as", ids: ["unit.U01"] }]);
  assert.equal(channel.swatch, "map-assigned");
  const plain = shelves.describe(keyOf("testbug", "p", "TB_002"));
  assert.equal(plain.chips[0].label, "No law in Cells");
  assert.match(plain.chips[0].title, /Cells has no law for this protein/);
  assert.equal(plain.swatch, "own-plain");
  // Nowhere do the words say that the engine models, simulates or runs one of these proteins.
  const words = JSON.stringify([...shelves.proteins.map((protein) => shelves.describe(protein.key)), ...large().markers.map((item) => large().describe(item.key))]);
  assert.ok(!/(engine|Cells) (models|simulates|runs) (this|these|the|a) (protein|proteins|family)/i.test(words));
});

test("a family's panel says what opening it shows, where its members sit, and that their sides are predictions on predicted proteins", () => {
  const shelves = large();
  const family = shelves.describe(keyOf("testworm", "f", "IPR000001"));
  assert.equal(family.eyebrow, "Test worm protein family");
  assert.match(family.plain, /^A family of 8 proteins\. Opening it shows every member\. Each member's side is predicted from the sequence of a protein that is itself predicted; it was not measured\.$/);
  const facts = Object.fromEntries(family.facts);
  assert.equal(facts["Where its members sit"], "7 proteins spanning a membrane; 1 protein inside the cell");
  assert.match(facts["Named place"], /^plasma membrane \(an annotation carried by signatures, not a prediction for these proteins\)$/);
  assert.equal(family.chips[0].label, "Holds parts of a machine Cells has a law for");
  assert.deepEqual(family.related, [{ title: "Holds candidate products of", ids: ["unit.U37"] }]);
  assert.deepEqual(family.sections[0].items[0].links, [{ text: "InterPro IPR000001", url: "https://www.ebi.ac.uk/interpro/entry/InterPro/IPR000001/" }]);
  assert.deepEqual([family.opens[0].title, family.opens[0].count, family.opens[0].items.length], ["Its proteins", 8, 8]);
  // A gathering lists its families, then every protein of them.
  const gathering = shelves.describe(keyOf("testworm", "m", "channels|in"));
  assert.match(gathering.plain, /^2 smaller families of Channels, gathered so that they do not swamp the shelf: 5 proteins in all\. Opening it shows every one of them\./);
  assert.deepEqual(gathering.opens.map((group) => [group.title, group.count]), [["Its families", 2], ["Its proteins", 5]]);
  assert.match(gathering.keywords, /Small channel/, "found by the names of the families it holds");
  // A part of "no family" is never called a family.
  const part = shelves.describe(keyOf("testworm", "g", "IPR100001"));
  assert.equal(part.eyebrow, "Test worm proteins with no family");
  assert.match(part.plain, /^12 proteins with no family signature, filed here by the superfamily they share, a wider grouping than a family\. This is not a family\./);
  assert.match(shelves.describe(keyOf("testworm", "g", "none")).plain, /because they carry no signature of any kind\. This is not a family\./);
  // A member leads back to its family; one of a gathered family, to the marker that holds it.
  const member = shelves.membersOf(shelves.get(keyOf("testworm", "f", "IPR000001")))[0];
  const said = shelves.describe(member.key);
  assert.match(said.plain, /^A predicted protein\. It spans a membrane\. That is predicted from the sequence of a protein that is itself predicted; it was not measured\.$/);
  assert.deepEqual(said.opens, [{ title: "Its family", items: [{ id: keyOf("testworm", "f", "IPR000001"), label: "Innexin-like", swatch: "map-assigned" }] }]);
  assert.equal(Object.fromEntries(said.facts).Family, "Innexin-like (IPR000001)");
  const kind = member.marks.kind;
  assert.equal(said.sections[0].items[0].links[0].url.startsWith(kind === "gene model" ? "https://parasite.wormbase.org/" : "https://www.uniprot.org/"), true, "the address is the one for that kind of line");
});

test("a machine finds what holds its products, and the list tells a family's members apart", () => {
  // From a unit of the atlas to the species' own proteins: its proteins in a small catalogue, its families in a large one.
  assert.deepEqual(small().holdersOf("U01").map((item) => item.id), ["TB_001"]);
  assert.deepEqual(small().holdersOf("U99"), []);
  const shelves = large();
  assert.deepEqual(shelves.holdersOf("U37").map((item) => item.label), ["Innexin-like"]);
  assert.deepEqual(shelves.holdersOf("U01").map((item) => item.label), ["Small channel"], "also a family that stands gathered");
  // The list: a marker with its number of proteins; a member named only after its family, with its identifier.
  const family = shelves.get(keyOf("testworm", "f", "IPR000001"));
  assert.deepEqual(shelves.listed(family), { id: family.key, label: "Innexin-like · 8", short: null, keywords: "IPR000001", swatch: "map-assigned" });
  const members = shelves.membersOf(family);
  const named = members.find((member) => member.label === family.label);
  assert.equal(shelves.listed(named).label, `Innexin-like · ${named.id}`);
  assert.match(shelves.listed(named).keywords, new RegExp(`^${named.id} Innexin-like$`), "found by its identifier and by its family");
  assert.equal(small().listed(small().get(keyOf("testbug", "p", "TB_004"))).label, "Ribosomal protein L1");
  assert.equal(small().listed(small().get(keyOf("testbug", "p", "TB_004"))).short, "rplA", "and by its gene");
});

test("a protein is called predicted only where the file says every one of its proteins is", () => {
  // The made-up large catalogue says so with a key of its own; a file may also say it in the words of its `from`.
  assert.equal(large().predicted, true);
  assert.equal(small().predicted, false);
  const { data, memberFiles } = madeUpFamilies();
  delete data.predicted;
  data.from = "A table of 50 proteins. Every one is predicted, from the genome or from transcripts; none was measured.";
  assert.equal(new Shelves(data, {}).predicted, true);
  // A large catalogue of proteins that are not predictions: the same families, and no such word.
  data.from = "A curated table: every protein has an entry of its own.";
  const measured = new Shelves(data, { label: "Test worm" });
  assert.equal(measured.predicted, false);
  for (const [name, file] of Object.entries(memberFiles)) measured.addMembers(name, file);
  const member = measured.membersOf(measured.get(keyOf("testworm", "f", "IPR000001")))[0];
  assert.match(measured.describe(member.key).plain, /^It spans a membrane\. That is predicted from its sequence; it was not measured\.$/);
  assert.match(measured.describe(keyOf("testworm", "f", "IPR000001")).plain, /Each member's side is predicted from its sequence; it was not measured\.$/);
  assert.ok(!/itself predicted|A predicted protein/.test(JSON.stringify(measured.markers.map((item) => measured.describe(item.key)))));
});

test("one shelf may stand for several membranes, and the page says so in the file's own words", () => {
  const words = large().sideWords();
  assert.equal(words.outside.short, "Beyond a membrane");
  assert.equal(words.outside.long, "Beyond a membrane: outside the cell, or within one of its compartments");
  assert.equal(words.in.short, "In a membrane");
  assert.equal(words.inside.short, "Inside the cell");
  assert.match(words["not known"].long, /set apart, not placed by guess/);
  const one = small().sideWords();
  assert.deepEqual([one.outside.short, one.in.short, one.in.long, one.inside.short], ["Outside the cell", "In the cell membrane", "Spans the cell membrane", "Inside the cell"]);
});

test("every source is shown with its terms and its class", () => {
  assert.equal(licenceClass({ licence: "CC BY 4.0" }), "permissive");
  assert.equal(licenceClass({ licence: "CC0 1.0" }), "permissive");
  assert.equal(licenceClass({ licence: "NCBI places no restrictions on the use or distribution of GenBank data" }), "permissive");
  assert.equal(licenceClass({ licence: "Biopython License Agreement or BSD 3-Clause License" }), "permissive");
  assert.equal(licenceClass({ licence: "CC BY-NC-SA 4.0" }), "non-commercial");
  assert.equal(licenceClass({ licence: "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee" }), "non-commercial");
  assert.equal(licenceClass({ licence: "Read for one sentence of its abstract" }), "no stated terms");
  assert.equal(licenceClass({}), "no stated terms");
  // A source that says which it is, is taken at its word.
  assert.equal(licenceClass({ licence: "CC BY 4.0", class: "non-commercial" }), "non-commercial");
  assert.equal(licenceClass({ licence: "No open licence stated: the paper is not open", class: "no stated terms" }), "no stated terms");
  assert.equal(licenceClass({ licence: "an odd wording", class: "permissive" }), "permissive");
  const items = small().sourceItems();
  assert.deepEqual(items.map((item) => item.tag), ["Permissive", "Non-commercial", "No stated terms"], "every source with its class");
  assert.deepEqual(items[1].lines, ["Terms: CC BY-NC-ND 4.0; read for one number"]);
  assert.equal(items[1].detail, "One number, for comparison");
  assert.equal(items[2].links.length, 0, "no address, no link");
  // The page claims nothing of a source that the file does not say.
  assert.ok(!/nothing of it is copied/i.test(JSON.stringify(items)));
});

test("the legend can show a mark's values alone: those with a short list of values, with their counts", () => {
  const marks = small().filterable();
  assert.deepEqual(marks.map((mark) => mark.id), ["essential", "seen", "anchor", "complex"], "a number is not listed");
  assert.deepEqual(marks[0].items, [{ id: "essential", label: "Essential", count: 5 }, { id: "non-essential", label: "Non-essential", count: 2 }]);
  assert.equal(marks[0].measured, true);
  // A mark that can be either, and one that is only ever set: "no" counts those without it.
  assert.deepEqual(marks[1].items.map((item) => [item.label, item.count]), [["Yes", 4], ["No", 5]]);
  assert.deepEqual(marks[2].items.map((item) => [item.label, item.count]), [["Yes", 1], ["No", 8]]);
  assert.deepEqual(large().filterable(), [], "the members of a family are not there at rest");
});

// ---------------------------------------------------------------- where the markers stand

test("at rest every marker stands once: on the membrane, on the glass below, or set apart", () => {
  const shelves = new Shelves(madeUpSmall({ more: 180 }), {});
  const layout = layoutShelves(shelves);
  const places = (area) => area.blocks.flatMap((block) => block.places);
  assert.deepEqual([...new Set(places(layout.plate).map((place) => place.item.side))].sort(), ["in", "outside"]);
  assert.deepEqual([...new Set(places(layout.tray).map((place) => place.item.side))], ["inside"]);
  assert.deepEqual([...new Set(places(layout.apart).map((place) => place.item.side))], ["not known"], "no known side: set apart, never placed by guess");
  const all = [layout.plate, layout.tray, layout.apart].flatMap(places);
  assert.equal(all.length, shelves.total);
  assert.equal(new Set(all.map((place) => place.item.key)).size, shelves.total);
  // Districts are blocks, each named, none over another; markers keep their distance.
  for (const area of [layout.plate, layout.tray, layout.apart]) {
    for (const block of area.blocks) {
      assert.ok(block.label && block.count === block.places.length);
      for (const [index, a] of block.places.entries()) for (const b of block.places.slice(index + 1)) assert.ok(distance(a, b) >= PITCH - 1e-6, `${a.item.id} and ${b.item.id} stand on each other`);
      assert.ok(Math.abs(block.x) + block.width / 2 <= area.width / 2 + 1e-6 && Math.abs(block.z) + block.depth / 2 <= area.depth / 2 + 1e-6, "a block lies within its shelf");
    }
    for (const [index, a] of area.blocks.entries()) {
      for (const b of area.blocks.slice(index + 1)) assert.ok(Math.abs(a.x - b.x) >= (a.width + b.width) / 2 - 1e-6 || Math.abs(a.z - b.z) >= (a.depth + b.depth) / 2 - 1e-6, `${a.label} lies over ${b.label}`);
    }
  }
  // The members of one assembly stand together.
  const ribosome = places(layout.tray).filter((place) => place.item.marks.complex === "ribosome");
  assert.equal(ribosome.length, 3);
  assert.ok(Math.max(...ribosome.map((a) => Math.max(...ribosome.map((b) => distance(a, b))))) <= 2 * PITCH + 1e-6);
});

test("the stack is laid out for the shape of the screen: wide for a wide one, deep for a tall one", () => {
  const shelves = new Shelves(madeUpSmall({ more: 400 }), {});
  const wide = layoutShelves(shelves, { shape: 0.65 }), deep = layoutShelves(shelves, { shape: 2.4 });
  assert.ok(wide.width > deep.width && wide.depth < deep.depth, `${wide.width}x${wide.depth} against ${deep.width}x${deep.depth}`);
  assert.ok(wide.depth <= wide.width * 0.65 + 1e-6 && deep.depth <= deep.width * 2.4 + 1e-6, "no deeper than its shape allows");
  // The shape follows what the window leaves free: the card stands at the left on a wide window, above on a narrow one.
  assert.equal(shapeFor({ width: 1920, height: 1080 }), 0.65);
  assert.equal(shapeFor({ width: 1400, height: 900 }), 0.8);
  assert.equal(shapeFor({ width: 1280, height: 800 }), 0.8);
  assert.equal(shapeFor({ width: 400, height: 800 }), 1.25);
  assert.equal(shapeFor({ width: 768, height: 1024 }), 2.4);
  const free = freeOf({ width: 1400, height: 900, insets: { right: 376 } }, { panel: true });
  assert.ok(free.left > freeOf({ width: 1400, height: 900 }).left && free.right > freeOf({ width: 1400, height: 900 }).right, "an open panel takes from both sides: the stage shifts its picture by half of it");
});

test("a family's marker grows with its members, and no two markers overlap", () => {
  assert.ok(familyRadius(5) < familyRadius(50) && familyRadius(50) < familyRadius(5000));
  assert.ok(familyRadius(5000) < 8 * familyRadius(5), "slowly, so that the largest stays on the shelf");
  const shelves = large({ loaded: false });
  const layout = layoutShelves(shelves);
  const all = [layout.plate, layout.tray, layout.apart].flatMap((area) => area.blocks.flatMap((block) => block.places));
  assert.equal(all.length, shelves.markers.length);
  for (const area of [layout.plate, layout.tray, layout.apart]) {
    for (const block of area.blocks) {
      for (const place of block.places) assert.equal(place.radius, familyRadius(place.item.count));
      for (const [index, a] of block.places.entries()) for (const b of block.places.slice(index + 1)) assert.ok(distance(a, b) >= a.radius + b.radius, `${a.item.label} and ${b.item.label} overlap`);
    }
  }
  // "No family" has a district of its own, after the others.
  assert.equal(layout.tray.blocks.at(-1).label, "No family assigned");
  // A family stands where most of its members sit.
  assert.ok(layout.plate.blocks.flatMap((block) => block.places).some((place) => place.item.id === "IPR000001"));
});

test("an open family is a small set of shelves of its own: membrane in the middle, glass around it, the unknown beyond the rim", () => {
  const sides = ["in", "outside", "inside", "not known"];
  const members = Array.from({ length: 140 }, (_, index) => ({ id: `m${index}`, side: sides[index % 7 === 0 ? 3 : index % 3], wide: index % 20 === 1, under: `family ${Math.floor(index / 10)}` }));
  const layout = layoutDish(members, PITCH, (member) => member.wide);
  assert.equal(layout.places.length, members.length);
  assert.equal(new Set(layout.places.map((place) => place.item.id)).size, members.length, "every member stands once");
  const reach = (place) => Math.hypot(place.dx, place.dz);
  for (const place of layout.places) {
    const side = place.item.side;
    assert.equal(place.zone, side === "inside" ? "tray" : side === "not known" ? "apart" : "plate");
    if (place.zone === "plate") assert.ok(reach(place) <= layout.plate, "what is in the membrane or on it stands on the piece of membrane");
    if (place.zone === "tray") assert.ok(reach(place) > layout.plate && reach(place) <= layout.tray, "what is inside stands on the glass around it");
    if (place.zone === "apart") assert.ok(reach(place) > layout.tray && reach(place) <= layout.reach, "what has no known side stands beyond the rim");
    assert.equal(place.size, place.item.wide ? 2 : 1);
  }
  for (const [index, a] of layout.places.entries()) {
    for (const b of layout.places.slice(index + 1)) assert.ok(distance(a, b) >= (PITCH * (a.size + b.size)) / 2 - 0.3, `${a.item.id} and ${b.item.id} stand on each other`);
  }
  // Members that follow one another stand side by side, so a family of a gathering stays together.
  const plain = layout.places.filter((place) => place.zone === "tray");
  const beside = plain.slice(1).filter((place, index) => distance(place, plain[index]) <= PITCH * 2.2).length;
  assert.ok(beside >= (plain.length - 1) * 0.85, `${beside} of ${plain.length - 1} stand beside the one before`);
  // A family with nothing in a membrane has no piece of membrane; one alone stands in the middle.
  const inside = layoutDish([{ id: "a", side: "inside" }, { id: "b", side: "inside" }, { id: "c", side: "inside" }]);
  assert.equal(inside.plate, 0);
  assert.ok(inside.tray > 0);
  const lone = layoutDish([{ id: "a", side: "in" }]);
  assert.deepEqual([lone.places[0].dx, lone.places[0].dz, lone.tray], [0, 0, 0]);
});

// ---------------------------------------------------------------- which of the two the atlas opens on

test("the atlas opens on the species' own proteins where it found almost none of Cells' machines, and on the machines otherwise", () => {
  const proteins = {
    findings: [{ id: "found" }, { id: "none found", mark: "dashes" }],
    atlases: [
      { id: "reference", reference: true },
      { id: "quietbug", counts: { units: 8 }, findings: [{ id: "found", count: 1 }, { id: "none found", count: 7 }] },
      { id: "richworm", counts: { units: 8 }, findings: [{ id: "found", count: 7 }, { id: "none found", count: 1 }] },
    ],
    shelves: [{ id: "quietbug", file: "proteins/quietbug/shelves.json" }, { id: "richworm", file: "proteins/richworm/shelves.json" }, { id: "newcomer", file: "proteins/newcomer/shelves.json" }],
  };
  assert.equal(shelvesOf(proteins, "quietbug").file, "proteins/quietbug/shelves.json");
  assert.equal(shelvesOf(proteins, "reference"), null);
  assert.equal(shelvesOf({}, "quietbug"), null);
  assert.equal(firstMode(proteins, "quietbug"), "own", "its own proteins say most");
  assert.equal(firstMode(proteins, "richworm"), "units", "the machines Cells has laws for, with the switch to its own proteins");
  assert.equal(firstMode(proteins, "newcomer"), "own", "no side of the atlas at all");
  assert.equal(firstMode(proteins, "reference"), "units", "no catalogue of its own: the atlas as it is");
  assert.equal(firstMode({ atlases: proteins.atlases }, "quietbug"), "units", "a scene from before the shelves");
});

// ---------------------------------------------------------------- getting the files to the page

test("a file beside the page is taken from the page if it is there, and fetched otherwise", async () => {
  const inline = { querySelector: (selector) => (selector.includes('data-file="proteins/testbug/shelves.json"') ? { textContent: '{"inline":true}' } : null) };
  const asked = [];
  const fetcher = async (address) => {
    asked.push(address);
    return address.endsWith("gone.json") ? { ok: false, status: 404 } : { ok: true, json: async () => ({ fetched: address }) };
  };
  assert.deepEqual(await loadBeside("proteins/testbug/shelves.json", { root: inline, fetcher }), { inline: true });
  assert.deepEqual(asked, [], "nothing is fetched for a file the page carries");
  assert.deepEqual(await loadBeside("proteins/testworm/members-00.json", { root: inline, fetcher }), { fetched: "proteins/testworm/members-00.json" });
  await assert.rejects(loadBeside("proteins/gone.json", { root: inline, fetcher }), /proteins\/gone\.json answered 404/);
  await assert.rejects(loadBeside("proteins/x.json", { root: null, fetcher: async () => Promise.reject(new Error("offline")) }), /could not be fetched/);
  await assert.rejects(loadBeside("proteins/x.json", { root: null, fetcher: null }), /cannot fetch/);
});

// The builder's reader of the shelves runs on its own, without reading a checkout.
const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib.protein_atlas import read_shelves, shelf_links
summaries, warnings = read_shelves(sys.argv[2])
print(json.dumps({"summaries": summaries, "warnings": warnings, "links": shelf_links(json.load(open(sys.argv[3], encoding="utf-8"))["shelves"])}))
`;
function readShelves(folder) {
  const run = spawnSync("python3", ["-c", READER, path.join(ROOT, "tools"), folder, path.join(PROTEINS, "overlay.json")], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  return JSON.parse(run.stdout);
}

const folder = await mkdtemp(path.join(os.tmpdir(), "cells-shelves-"));
test.after(() => rm(folder, { recursive: true, force: true }));
const place = async (root, name, data) => {
  await mkdir(path.join(root, name), { recursive: true });
  await writeFile(path.join(root, name, "shelves.json"), typeof data === "string" ? data : JSON.stringify(data));
};

test("the scene carries, for each species, the file's name, its counts and its sources, and nothing of a file that breaks the contract", async () => {
  const sound = path.join(folder, "sound");
  await place(sound, "testbug", madeUpSmall());
  await place(sound, "testworm", madeUpFamilies().data);
  const { summaries, warnings, links } = readShelves(sound);
  assert.deepEqual(warnings, []);
  assert.deepEqual(summaries.map((item) => item.id), ["testbug", "testworm"]);
  const [bug, worm] = summaries;
  assert.deepEqual([bug.file, bug.kind, bug.proteins, bug.made, bug.from], ["proteins/testbug/shelves.json", "proteins", 9, "2026-11-15", "A made-up record: every protein product"]);
  assert.deepEqual(bug.counts, { outside: 1, in: 2, inside: 4, "not known": 2 });
  assert.deepEqual(bug.sources.map((source) => [source.name, source.licence]), SOURCES.map((source) => [source.name, source.licence]));
  assert.equal(bug.members, undefined);
  assert.deepEqual([worm.kind, worm.proteins, worm.families, worm.no_family, worm.parts], ["families", 50, 7, 25, 4]);
  assert.deepEqual(worm.members, ["members-00.json", "members-01.json"], "the files of members the page will ask for");
  assert.deepEqual(Object.keys(worm).sort(), ["bytes", "counts", "families", "file", "from", "id", "kind", "made", "members", "no_family", "parts", "proteins", "sources"], "names, counts and sources: no protein, no family");
  // The patterns of the addresses come without the notes on when they were checked.
  assert.ok(!JSON.stringify(links).includes("checked"));
  assert.match(links.family.url, /^https:\/\/www\.ebi\.ac\.uk\/interpro\/entry\/InterPro\/\{id\}\/$/);

  const broken = path.join(folder, "broken");
  await place(broken, "testbug", madeUpSmall());
  await place(broken, "wrongname", madeUpSmall());
  await place(broken, "badside", madeUpSmall({ change: (data) => ((data.species = "badside"), (data.proteins[0][4] = "nearby")) }));
  await place(broken, "guessed", madeUpSmall({ change: (data) => ((data.species = "guessed"), (data.proteins[7][5] = "predicted")) }));
  await place(broken, "miscounted", madeUpSmall({ change: (data) => ((data.species = "miscounted"), (data.counts.inside = 99)) }));
  await place(broken, "machine", madeUpSmall({ change: (data) => ((data.species = "machine"), (data.from = "/home/someone/catalogue.tsv")) }));
  await place(broken, "unlicensed", madeUpSmall({ change: (data) => ((data.species = "unlicensed"), delete data.sources[0].licence) }));
  await place(broken, "notjson", "{ this is not JSON");
  const families = madeUpFamilies().data;
  families.species = "badslice";
  families.families[0][8] = [0, 3];
  await place(broken, "badslice", families);
  const read = readShelves(broken);
  assert.deepEqual(read.summaries.map((item) => item.id), ["testbug"], "only the sound one is in the scene");
  const said = (name) => read.warnings.find((warning) => warning.startsWith(`species proteins ${name}:`)) || "";
  assert.match(said("wrongname"), /it says it holds the proteins of 'testbug'/);
  assert.match(said("badside"), /TB_001: its side or its basis is not one of the contract's words/);
  assert.match(said("guessed"), /TB_008: a side that is not known has the basis none, and no other has/);
  assert.match(said("miscounted"), /its counts by side are not those of its lines/);
  assert.match(said("machine"), /it holds a machine path/);
  assert.match(said("unlicensed"), /every source needs a name and its licence/);
  assert.match(said("notjson"), /could not be read as JSON/);
  assert.match(said("badslice"), /IPR000001: its file and its place in it do not hold its 8 members/);
  assert.equal(read.warnings.length, 8);
  assert.ok(read.warnings.every((warning) => warning.endsWith("left out")));
  assert.deepEqual(readShelves(path.join(folder, "no-such-folder")).summaries, [], "no folder, no proteins");
});

test("the page builder lists the files to publish beside the page, and leaves out a species whose files are not there", async () => {
  const proteinsDir = path.join(folder, "sound"), membersDir = path.join(folder, "members");
  const { summaries } = readShelves(proteinsDir);
  const scene = { proteins: { shelves: summaries } };
  // The small catalogue has one file. The large one's members are not written yet, and nothing here can write them.
  let found = await proteinFiles(scene, { proteinsDir, membersDir, make: false });
  assert.deepEqual(found.files.map((file) => file.path), ["proteins/testbug/shelves.json"]);
  assert.equal(found.files[0].source, path.join(proteinsDir, "testbug", "shelves.json"));
  assert.match(found.problems.join(" "), /testworm: the files of its families' members are not in /);
  // A catalogue that does not say how its members are written is reported, not guessed at.
  found = await proteinFiles(scene, { proteinsDir, membersDir });
  assert.match(found.problems.join(" "), /testworm: its shelves do not say how the files of members are written/);
  // Once they are there, every one is listed under the address the page fetches.
  const { memberFiles } = madeUpFamilies();
  await mkdir(path.join(membersDir, "testworm"), { recursive: true });
  for (const [name, file] of Object.entries(memberFiles)) await writeFile(path.join(membersDir, "testworm", name), JSON.stringify(file));
  found = await proteinFiles(scene, { proteinsDir, membersDir, make: false });
  assert.deepEqual(found.problems, []);
  assert.deepEqual(found.files.map((file) => file.path), ["proteins/testbug/shelves.json", "proteins/testworm/shelves.json", "proteins/testworm/members-00.json", "proteins/testworm/members-01.json"]);
  // A scene that names a file outside its own folder, or a species with no file, gets nothing.
  const odd = await proteinFiles({ proteins: { shelves: [{ id: "testbug", file: "proteins/../secrets/shelves.json" }, { id: "nobody", file: "proteins/nobody/shelves.json" }, { ...summaries[1], members: ["../../etc/passwd"] }] } }, { proteinsDir, membersDir, make: false });
  assert.deepEqual(odd.files, []);
  assert.equal(odd.problems.length, 3);
  assert.deepEqual(await proteinFiles({}, { proteinsDir, membersDir }), { files: [], problems: [] }, "a scene from before the shelves");

  // The page: beside it by default, inside it for a file opened from disk.
  const scenePath = path.join(folder, "scene.json");
  await writeFile(scenePath, JSON.stringify(scene));
  const empty = path.join(folder, "no-runs");
  await mkdir(empty, { recursive: true });
  const linked = await buildPage({ scenePath, runsDir: empty, proteinsDir, membersDir });
  assert.ok(!linked.includes('<script type="application/json" data-file='), "by default the proteins stay in their own files beside the page");
  const inline = await buildPage({ scenePath, runsDir: empty, proteinsDir, membersDir, inlineRuns: true });
  for (const name of found.files.map((file) => file.path)) assert.ok(inline.includes(`<script type="application/json" data-file="${name}">`), `${name} is inside a standalone page`);

  // The preview server serves them at the same addresses, and nothing else from there.
  const server = createServer({ scene: scenePath, proteins: proteinsDir, members: membersDir, log: () => {} });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const reply = await fetch(`${base}/proteins/testbug/shelves.json`);
    assert.equal(reply.status, 200);
    assert.equal((await reply.json()).species, "testbug");
    assert.equal((await (await fetch(`${base}/proteins/testworm/members-01.json`)).json()).format, MEMBERS_FORMAT);
    assert.equal((await fetch(`${base}/proteins/nobody/shelves.json`)).status, 404);
    assert.equal((await fetch(`${base}/proteins/testbug/%2e%2e/%2e%2e/scene.json`)).status, 404);
  } finally {
    server.close();
  }
  // A page published without the files: every address answers that it is not there.
  const bare = createServer({ scene: scenePath, proteins: null, log: () => {} });
  await new Promise((resolve) => bare.listen(0, "127.0.0.1", resolve));
  try {
    assert.equal((await fetch(`http://127.0.0.1:${bare.address().port}/proteins/testbug/shelves.json`)).status, 404);
  } finally {
    bare.close();
  }
});

test("the page has styles for the shelves' card rows, swatches and names", () => {
  for (const selector of [".seg-wide", ".card-notice", ".card-open", ".card-marks", ".index-more", ".swatch-own-outside", ".swatch-own-in", ".swatch-own-inside", ".swatch-own-unknown", ".swatch-own-plain", ".swatch-own-family", ".label-shelf", ".label-hot"]) {
    assert.ok(css.includes(selector), selector);
  }
});

// ---------------------------------------------------------------- the repository's own files

const own = existsSync(PROTEINS) ? (await readdir(PROTEINS, { withFileTypes: true })).filter((entry) => entry.isDirectory() && existsSync(path.join(PROTEINS, entry.name, "shelves.json"))).map((entry) => entry.name) : [];

test("every shelves file of the repository holds to the contract, as the builder and the page read it", async (t) => {
  if (!own.length) return t.skip("no species has proteins of its own yet");
  const { summaries, warnings } = readShelves(PROTEINS);
  assert.deepEqual(warnings, []);
  assert.deepEqual(summaries.map((item) => item.id), [...own].sort());
  for (const summary of summaries) {
    const text = await readFile(path.join(PROTEINS, summary.id, "shelves.json"), "utf8");
    const data = JSON.parse(text);
    assert.ok(Buffer.byteLength(text) < 1024 * 1024, `${summary.id}: a species' file stays under 1 MB`);
    assert.ok(!MACHINE.test(text), `${summary.id}: a machine path`);
    assert.deepEqual(validateShelves(data), [], summary.id);
    const shelves = new Shelves(data, { label: summary.id, links: OVERLAY.shelves.links, units: UNITS });
    assert.equal(shelves.total, summary.proteins, `${summary.id}: the page counts what the scene says`);
    assert.deepEqual(shelves.counts, summary.counts, summary.id);
    assert.equal(SIDES.reduce((sum, side) => sum + shelves.counts[side], 0), shelves.total, `${summary.id}: every protein has one of the four sides`);
    assert.equal(shelves.markers.reduce((sum, item) => sum + item.count, 0), shelves.total, `${summary.id}: every protein is behind one marker`);
    const layout = layoutShelves(shelves);
    assert.equal([layout.plate, layout.tray, layout.apart].reduce((sum, area) => sum + area.blocks.reduce((total, block) => total + block.places.length, 0), 0), shelves.markers.length, `${summary.id}: every marker stands once`);
    // Whether every protein is itself a prediction is the file's to say. A file whose `from` speaks of
    // prediction must be read so by the page, or say with a `predicted` key that it is not: a reworded
    // sentence would otherwise drop the page's words on predicted proteins without a sound.
    if (/predict/i.test(String(data.from || "")) && typeof data.predicted !== "boolean") {
      assert.equal(shelves.predicted, true, `${summary.id}: its "from" speaks of prediction, but the page does not read "Every one is predicted" in it: give the file a "predicted" key`);
    }
    // A unit named there is one of the law inventory's, so the page can tie it to the unit drawn.
    const named = shelves.kind === "proteins" ? shelves.proteins.flatMap((protein) => protein.units) : [...shelves.families, ...shelves.parts].flatMap((family) => family.units);
    for (const unit of new Set(named)) assert.ok(UNITS.has(unit), `${summary.id}: ${unit} is not a unit of the inventory`);
    // Every source states its terms, and the page can say which kind they are.
    for (const source of data.sources) assert.ok(source.name && source.licence && ["permissive", "non-commercial", "no stated terms"].includes(licenceClass(source)), `${summary.id}: ${source.name}`);
    // Where a protein or a family is looked up: only the named databases, over https.
    const allowed = ["www.uniprot.org", "parasite.wormbase.org", "www.ebi.ac.uk", "www.ncbi.nlm.nih.gov"];
    const sample = shelves.kind === "proteins" ? shelves.proteins.slice(0, 40) : shelves.markers.filter((item) => !item.holds).slice(0, 40);
    let links = 0;
    for (const item of sample) {
      for (const link of shelves.linksFor(item)) {
        links += 1;
        const url = new URL(link.url);
        assert.equal(url.protocol, "https:");
        assert.ok(allowed.includes(url.hostname), `${summary.id}: ${link.url}`);
        assert.ok(!link.url.includes("{id}") && !link.text.includes("{id}"));
      }
    }
    assert.ok(links > 0, `${summary.id}: nothing to look a protein up at`);
    t.diagnostic(`${summary.id}: ${shelves.total} proteins, ${shelves.markers.length} markers (${shelves.kind}), ${layout.width.toFixed(0)} by ${layout.depth.toFixed(0)}`);
  }
});

test("a large catalogue's members are cut into files by the step it names, and every family finds its own", async (t) => {
  const { summaries } = readShelves(PROTEINS);
  const big = summaries.filter((item) => item.kind === "families");
  if (!big.length) return t.skip("no species has families yet");
  const membersDir = path.join(folder, "cut");
  const found = await proteinFiles({ proteins: { shelves: big } }, { membersDir });
  assert.deepEqual(found.problems, []);
  for (const summary of big) {
    const shelves = new Shelves(JSON.parse(await readFile(path.join(PROTEINS, summary.id, "shelves.json"), "utf8")), { units: UNITS });
    const files = found.files.filter((file) => file.species === summary.id && !file.path.endsWith("shelves.json"));
    assert.deepEqual(files.map((file) => path.basename(file.path)), summary.members);
    assert.ok(files.length <= 40, "a few files, of a few thousand proteins each");
    let bytes = 0;
    for (const file of files) {
      const text = await readFile(file.source, "utf8");
      bytes += Buffer.byteLength(text);
      assert.ok(Buffer.byteLength(text) < 1024 * 1024, `${file.path} is over 1 MB`);
      shelves.addMembers(path.basename(file.path), JSON.parse(text));
    }
    // Every family, part and gathering opens to as many members as it says, each a protein of its own.
    const seen = new Set();
    for (const marker of shelves.markers) {
      const members = shelves.membersOf(marker);
      assert.equal(members.length, marker.count, `${summary.id}: ${marker.label}`);
      for (const member of members) seen.add(member.id);
    }
    assert.equal(seen.size, shelves.total, `${summary.id}: every protein is reached, once`);
    // The largest thing that opens still stands as rings on its own shelves.
    const largest = shelves.markers.reduce((best, item) => (item.count > best.count ? item : best));
    const dish = layoutDish(shelves.membersOf(largest));
    assert.equal(dish.places.length, largest.count);
    // A member that would make one of Cells' machines names a unit of the inventory.
    const withUnit = [...seen].length && shelves.markers.flatMap((marker) => shelves.membersOf(marker)).filter((member) => member.units.length);
    for (const member of withUnit) for (const unit of member.units) assert.ok(UNITS.has(unit), `${member.id}: ${unit}`);
    t.diagnostic(`${summary.id}: ${files.length} files of members, ${(bytes / 1024 / 1024).toFixed(2)} MB; the largest that opens is ${largest.label} with ${largest.count}; ${withUnit.length} members would make one of Cells' machines`);
  }
});

// The whole build, once, with the repository's own shelves. It reads a checkout: where there
// is none, or the build declines it for a reason of its own, the check on it is skipped.
const built = new Promise((resolve) => {
  const out = path.join(folder, "scene.out");
  const child = spawn("python3", [path.join(ROOT, "tools", "extract_architecture.py"), "--out", out], { stdio: ["ignore", "pipe", "pipe"] });
  let said = "";
  child.stdout.on("data", (chunk) => (said += chunk));
  child.stderr.on("data", (chunk) => (said += chunk));
  child.on("close", async (code) => resolve({ code, said, scene: code === 0 ? JSON.parse(await readFile(out, "utf8")) : null }));
});

test("the build puts each species' summary and the patterns of the addresses in the scene, and no protein", async (t) => {
  const { code, said, scene } = await built;
  const declined = code !== 0 && !/Traceback/.test(said) ? said.trim().split("\n").at(-1) : null;
  if (declined) return t.skip(`the build did not run: ${declined}`);
  assert.equal(code, 0, said);
  assert.deepEqual(validate(scene), []);
  assert.deepEqual(scene.meta.warnings.filter((warning) => warning.startsWith("species proteins")), []);
  assert.deepEqual(scene.proteins.shelves.map((item) => item.id), [...own].sort());
  for (const item of scene.proteins.shelves) {
    assert.match(said, new RegExp(`species proteins ${item.id} of \\d{4}-\\d{2}-\\d{2}: [\\d,]+ proteins`));
    assert.equal(item.file, `proteins/${item.id}/shelves.json`);
    assert.ok(item.sources.length > 0 && item.sources.every((source) => source.name && source.licence));
  }
  assert.ok(JSON.stringify(scene.proteins.shelves).length < 40000, "names, counts and sources only: the proteins are beside the page");
  assert.ok(!MACHINE.test(JSON.stringify([scene.proteins.shelves, scene.proteins.shelf_links])), "a machine path leaked into the scene");
  assert.ok(!JSON.stringify(scene.proteins.shelf_links).includes("checked"));
  for (const [key, patterns] of Object.entries(scene.proteins.shelf_links)) {
    for (const pattern of [].concat(patterns)) {
      assert.equal(new URL(pattern.url.replaceAll("{id}", "X")).protocol, "https:", key);
      assert.ok(pattern.text.includes("{id}") && pattern.url.includes("{id}"), key);
    }
  }
  // The page then finds, for each species, which of the two it opens on.
  for (const item of scene.proteins.shelves) assert.ok(["own", "units"].includes(firstMode(scene.proteins, item.id)));
  const files = await proteinFiles(scene, { membersDir: path.join(folder, "cut") });
  assert.deepEqual(files.problems, []);
  assert.ok(files.files.length <= 60, `${files.files.length} files beside the page: the page may publish 255 in all, and the runs need theirs`);
});
