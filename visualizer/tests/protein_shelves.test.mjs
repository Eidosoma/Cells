// A species' own proteins on the atlas's shelves (schema/SPECIES_PROTEINS.md): how the page
// reads a species' file, where each marker stands, what is said of a protein and a family,
// which of the two the atlas opens on, what the scene carries, and how the files get beside
// the page. A species may have one shelf or several; both are read here.
//
// The species used here are made up, in temporary folders: no behaviour is checked against a
// species file of the repository. The one with several shelves is also kept as a file, under
// tests/shelves-several/, for whatever needs it on disk (tests/fixtures/ is the run adapter's:
// its test holds every file there to its own tool); this file writes it:
//
//   WRITE_SHELVES_FIXTURE=1 node --test tests/protein_shelves.test.mjs
//
// The repository's own files are held to the contract at the end, whichever they are.
// Nothing needs a browser.
//
//   node --test tests/protein_shelves.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT, buildPage, proteinFiles } from "../tools/lib/build_page.mjs";
import { createServer } from "../tools/serve.mjs";
import { validate } from "../src/scene/model.js";
import { css } from "../src/ui/styles.js";
import { firstMode, shelvesOf } from "../src/lenses/proteins.js";
import { columnsFor, freeOf, opensFor, shapeFor } from "../src/lenses/shelves_view.js";
import {
  BASES,
  MEMBERS_FORMAT,
  NAMES_FILE,
  NO_SHELF,
  OWN_FAMILY,
  OWN_PART,
  PITCH,
  SHELVES_FORMAT,
  SIDES,
  Shelves,
  arrangeStack,
  familyRadius,
  keyOf,
  layoutDish,
  layoutShelves,
  layoutStack,
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
    sources: structuredClone(SOURCES),
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
    sources: structuredClone(SOURCES.slice(0, 1)),
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
  assert.deepEqual(said.chips.map((chip) => chip.label), ["Not in the law inventory", "Inside the cell", "By function"]);
  assert.deepEqual(said.sections.map((section) => section.title), ["Look it up", "Sources and licences"]);
  assert.deepEqual(said.sections[0].items[0].links, [{ text: "Look up TB_004", url: "https://www.ncbi.nlm.nih.gov/protein/?term=TB_004" }]);
  assert.match(said.disclosures[0].title, /taken from function/);
  assert.deepEqual(said.related, []);
  // A side that is predicted says so; one that is not known is never given a place in words either.
  assert.match(shelves.describe(keyOf("testbug", "p", "TB_002")).plain, /^It spans the cell membrane\. That is predicted from its sequence; it was not measured\.$/);
  assert.match(shelves.describe(keyOf("testbug", "p", "TB_003")).plain, /^It is outside the cell\./);
  const unknown = shelves.describe(keyOf("testbug", "p", "TB_008"));
  assert.match(unknown.plain, /^Its side of the membrane is not known\. .* set apart and not placed by guess\.$/);
  assert.deepEqual(unknown.chips.map((chip) => chip.label), ["Not in the law inventory", "Side not known", "Not known"]);
  // A mark that can be either says "no"; one that is only ever set is left out when it is not.
  assert.equal(Object.fromEntries(shelves.describe(keyOf("testbug", "p", "TB_002")).facts)["Seen in the proteomics"], "no (measured)");
  assert.equal(Object.fromEntries(shelves.describe(keyOf("testbug", "p", "TB_002")).facts)["Lipid anchor read from the sequence"], undefined);
  assert.equal(shelves.describe("own:testbug:p:nobody"), null);
});

test("a protein the atlas lists with a unit only as going with its machine says so, in the atlas's words, and is drawn plain", async () => {
  // The made-up bug's sodium channel (TB_001, U01) and a regulator listed with the same unit only by an accessory family's signature.
  const data = madeUpSmall({
    change: (made) => {
      made.proteins.push(["TB_010", "Channel regulator", "nacr", "cell", "inside", "predicted", "transport", 190, "U01", {}]);
      made.counts.inside += 1;
      made.found_by = { note: "made up", default: "family signature", proteins: { "accessory signature": ["TB_010"] }, families: {} };
    },
  });
  const words = OVERLAY.species.found_by;
  const shelves = new Shelves(data, { label: "Test bug", links: LINKS, units: UNITS, found: words });
  const channel = shelves.describe(keyOf("testbug", "p", "TB_001"));
  const regulator = shelves.describe(keyOf("testbug", "p", "TB_010"));
  assert.equal(channel.chips[0].label, "Would make a unit of the law inventory");
  assert.deepEqual(channel.related, [{ title: "Drawn in the atlas as", ids: ["unit.U01"] }]);
  assert.deepEqual([Object.fromEntries(channel.facts)["How the atlas found it"], Object.fromEntries(channel.facts)["In the atlas"]], ["Family signature", "Candidate by family, not an established counterpart"]);
  assert.equal(regulator.chips[0].label, "Goes with a unit of the law inventory");
  assert.match(regulator.chips[0].title, /no candidate for the machine's own work, and is drawn as a plain marker/);
  assert.deepEqual(regulator.related, [{ title: "Listed in the atlas with", ids: ["unit.U01"] }]);
  assert.deepEqual([Object.fromEntries(regulator.facts)["How the atlas found it"], Object.fromEntries(regulator.facts)["In the atlas"]], ["Accessory family", "Goes with the machine, no candidate for its own work"]);
  assert.ok(!regulator.chips.some((chip) => /Would make/.test(chip.label)));
  assert.deepEqual([channel.chips[0].swatch, regulator.chips[0].swatch], ["map-assigned", "own-plain"]);
  // Drawn plain: the view gives it no unit's form and the plain grey tone, while the channel keeps its own form and the units' tone.
  const { ShelvesView } = await import("../src/lenses/shelves_view.js");
  const view = Object.assign(Object.create(ShelvesView.prototype), { shelves, lens: { model: { get: (id) => (id === "unit.U01" ? { id, form: {} } : null) } } });
  const byId = (id) => shelves.byKey.get(keyOf("testbug", "p", id));
  assert.equal(view.unitOf(byId("TB_010")), null);
  assert.equal(view.unitOf(byId("TB_001"))?.id, "unit.U01");
  assert.deepEqual([view.toneOf(byId("TB_010")), view.toneOf(byId("TB_001")), view.toneOf(byId("TB_001"), true)], ["plain", "unit", "more"]);
  // A file without the block says nothing of how its proteins were found, and draws them as before.
  const older = new Shelves(madeUpSmall(), { label: "Test bug", links: LINKS, units: UNITS, found: words });
  assert.equal(Object.fromEntries(older.describe(keyOf("testbug", "p", "TB_001")).facts)["How the atlas found it"], undefined);
  assert.equal(older.goesWithOnly(older.byKey.get(keyOf("testbug", "p", "TB_001"))), false);
});

test("every species' shelves name the proteins their atlas lists with a unit only as going with its machine, and the families all of whose such proteins are so", async () => {
  for (const id of ["fruitfly", "mouse", "thalecress", "planarian"]) {
    const shelves = JSON.parse(await readFile(path.join(PROTEINS, id, "shelves.json"), "utf8"));
    const atlas = JSON.parse(await readFile(path.join(PROTEINS, "atlases", `${id}.json`), "utf8"));
    const found = new Map();
    for (const unit of Object.values(atlas.units)) for (const product of unit.products) for (const item of product.ids) found.set(item.id, product.found_by);
    const going = [...found].filter(([, how]) => how === "accessory signature").map(([key]) => key).sort();
    assert.deepEqual([...(shelves.found_by?.proteins?.["accessory signature"] || [])].sort(), going, `${id}: the accessory proteins`);
    assert.equal(shelves.found_by.default, "family signature", id);
    assert.ok(!/candidates by family alone/.test(JSON.stringify(shelves.family_notes || {})), `${id}: the family note's older words`);
  }
  // E. coli lists no protein with a unit: its shelves carry no block.
  assert.equal(JSON.parse(await readFile(path.join(PROTEINS, "ecoli", "shelves.json"), "utf8")).found_by, undefined);
});

test("the atlas's words stand on the law inventory: a unit, protein or family is listed in it or with one of its units, never one Cells has a law for", async () => {
  // Since 18 November 2026 (D211's inventory): what Cells has laws for is not said, for the laws of 38 of the 48 units are
  // implemented in older code only. The sources of the atlas's words, and the species files they read.
  const files = ["src/lenses/proteins.js", "src/lenses/protein_shelves.js", "src/ui/viewer.js", ...["ecoli", "fruitfly", "mouse", "thalecress", "human", "planarian", "syn3a", "mpneumoniae"].map((id) => `data/species/${id}.json`)];
  for (const file of files) {
    if (!existsSync(path.join(ROOT, file))) continue;
    const text = await readFile(path.join(ROOT, file), "utf8");
    assert.ok(!/Cells ha(s|ve) (a |no )?laws? for|units Cells has|No law in Cells|with a law in Cells|"Cells' laws"/.test(text), `${file} says what Cells has a law for`);
  }
});

test("only a protein with a unit is tied to a unit of the law inventory, and the words stop there", () => {
  const shelves = small();
  const channel = shelves.describe(keyOf("testbug", "p", "TB_001"));
  assert.equal(channel.chips[0].label, "Would make a unit of the law inventory");
  assert.match(channel.chips[0].title, /the engine does not model this protein/);
  assert.deepEqual(channel.related, [{ title: "Drawn in the atlas as", ids: ["unit.U01"] }]);
  assert.equal(channel.swatch, "map-assigned");
  const plain = shelves.describe(keyOf("testbug", "p", "TB_002"));
  assert.equal(plain.chips[0].label, "Not in the law inventory");
  assert.match(plain.chips[0].title, /This protein is listed with no unit of Cells' law inventory/);
  assert.equal(plain.swatch, "own-plain");
  // Nowhere do the words say that the engine models, simulates or runs one of these proteins.
  const words = JSON.stringify([...shelves.proteins.map((protein) => shelves.describe(protein.key)), ...large().markers.map((item) => large().describe(item.key))]);
  assert.ok(!/(engine|Cells) (models|simulates|runs) (this|these|the|a) (protein|proteins|family)/i.test(words));
  // Nor what Cells has a law for: a protein is listed with a unit of Cells' law inventory, or it is not.
  assert.ok(!/Cells has (a |no )?laws? |law in Cells/.test(words), "the words stand on the law inventory");
});

test("a family's panel says what opening it shows, where its members sit, and that their sides are predictions on predicted proteins", () => {
  const shelves = large();
  const family = shelves.describe(keyOf("testworm", "f", "IPR000001"));
  assert.equal(family.eyebrow, "Test worm protein family");
  assert.match(family.plain, /^A family of 8 proteins\. Opening it shows every member\. Each member's side is predicted from the sequence of a protein that is itself predicted; it was not measured\.$/);
  const facts = Object.fromEntries(family.facts);
  assert.equal(facts["Where its members sit"], "7 proteins spanning a membrane; 1 protein inside the cell");
  assert.match(facts["Named place"], /^plasma membrane \(an annotation carried by signatures, not a prediction for these proteins\)$/);
  assert.equal(family.chips[0].label, "Holds parts of a unit of the law inventory");
  // Proteins listed with a unit: candidates for its unit, or parts that go with it (an accessory family's carry `unit` too).
  assert.deepEqual(family.related, [{ title: "Holds proteins listed with", ids: ["unit.U37"] }]);
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

test("the atlas opens on the species' own proteins where it found almost none of Cells' units, and on the machines otherwise", () => {
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
  assert.equal(firstMode(proteins, "richworm"), "units", "the units of Cells' law inventory, with the switch to its own proteins");
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
  // A request that gets no answer is made again, twice, before it is given up; one that then gets an answer is read.
  let tried = 0;
  await assert.rejects(loadBeside("proteins/x.json", { root: null, waits: [1, 1], fetcher: async () => ((tried += 1), Promise.reject(new Error("offline"))) }), /could not be fetched/);
  assert.equal(tried, 3);
  tried = 0;
  const late = async (address) => ((tried += 1) < 3 ? Promise.reject(new Error("reset")) : { ok: true, json: async () => ({ fetched: address }) });
  assert.deepEqual(await loadBeside("proteins/y.json", { root: null, waits: [1, 1], fetcher: late }), { fetched: "proteins/y.json" });
  // An answer is taken at its word: "not there" is not asked for again.
  tried = 0;
  await assert.rejects(loadBeside("proteins/gone.json", { root: null, waits: [1, 1], fetcher: async () => ((tried += 1), { ok: false, status: 404 }) }), /answered 404/);
  assert.equal(tried, 1);
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
  // Of a source the scene keeps its name and how it may be used, as the page reads it; its licence in full stays in the species' file.
  assert.deepEqual(bug.sources, SOURCES.map((source) => ({ name: source.name, class: licenceClass(source) })));
  assert.deepEqual(bug.sources.map((source) => source.class), ["permissive", "non-commercial", "no stated terms"]);
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

// ---------------------------------------------------------------- a made-up species with several shelves

const SEVERAL = path.join(ROOT, "tests", "shelves-several");
const SIX = [
  { id: "cell", label: "Cell membrane", outside: "Outside the cell", inside: "Inside the cell: in the cytoplasm" },
  { id: "er", label: "Endoplasmic reticulum membrane", outside: "On the cytoplasmic face of the endoplasmic reticulum", inside: "In the endoplasmic reticulum's lumen" },
  { id: "mito", label: "Mitochondrial inner membrane", outside: "Between the mitochondrion's two membranes", inside: "In the mitochondrial matrix" },
  { id: "nucleus", label: "Nuclear envelope", outside: "On the cytoplasmic face of the nuclear envelope", inside: "In the nucleus" },
  { id: "other", label: "Other membranes", outside: "On the cytoplasmic face of one of the other membranes", inside: "Within one of the other compartments" },
  { id: "membrane", label: "A membrane, not told which", outside: "Beyond a membrane: outside the cell, or within a compartment", inside: "On the cytoplasmic side of a membrane" },
];

/**
 * A made-up curated catalogue on six shelves, kept as tests/shelves-several/testcell: families that stand on two and three shelves,
 * lines on no shelf, proteins with a shelf and no known side, "no family" in parts that
 * have a shelf, proteins that are the only member of their family (`lone`), and a few units
 * of the inventory. 131 proteins: 18 lines of families, 5 parts of lone, 9 lines of parts of
 * no family. Every name and number is invented. Returns the shelves file and the three
 * files of members.
 */
function madeUpSeveral({ change = () => {} } = {}) {
  // A family: id, label, district, then its lines: [its shelf or null, the sides of its members there, the units they would make]
  const families = [
    ["IPR900001", "Glimmer channel", "channels", [["cell", { in: 6, inside: 1 }, ["U01"]], ["er", { in: 3 }], ["mito", { in: 2, "not known": 1 }]]],
    ["IPR900002", "Lantern kinase", "signalling", [["cell", { inside: 8 }], ["nucleus", { inside: 5, outside: 1 }]]],
    ["IPR900003", "Quill receptor", "signalling", [["cell", { in: 4, outside: 1 }, ["U37"]], ["membrane", { in: 2 }], [null, { "not known": 3 }]]],
    ["IPR900004", "Ember oxidase", "enzymes", [["mito", { inside: 6, outside: 1, in: 2 }], ["other", { inside: 2 }]]],
    ["IPR900005", "Tally transferase", "enzymes", [["er", { inside: 2, in: 1 }], ["other", { in: 3, "not known": 1 }]]],
    ["IPR900006", "Harbour pore", "channels", [["nucleus", { in: 5 }, ["U02"]]]],
    ["IPR900007", "Drift factor", "signalling", [["nucleus", { inside: 2, "not known": 4 }]]],
    ["IPR900008", "Veil protein", "signalling", [["membrane", { in: 5, outside: 1, "not known": 1 }]]],
    ["IPR900009", "Lone cap", "enzymes", [["er", { in: 1 }]]],
    ["IPR900010", "Mist binder", "signalling", [["cell", { inside: 1 }], [null, { "not known": 6 }]]],
  ];
  // A part of "no family": id, label, kind, district, then its lines
  const parts = [
    ["IPR910001", "Wide fold superfamily", "superfamily", "signalling", [["cell", { inside: 11, in: 1 }], ["nucleus", { inside: 4 }]]],
    ["IPR910002", "Narrow fold superfamily", "superfamily", "enzymes", [["cell", { inside: 3 }], ["mito", { inside: 2, "not known": 1 }]]],
    ["other-signature", "A domain, repeat or site signature, and no family", "other signature", "unclassed", [["cell", { inside: 2, outside: 1 }], ["other", { in: 2 }]]],
    ["no-signature", "No signature of any kind", "no signature", "unclassed", [["cell", { inside: 2 }], ["membrane", { in: 1, outside: 1 }], [null, { "not known": 5 }]]],
  ];
  const total = (sides) => Object.values(sides).reduce((sum, n) => sum + n, 0);
  const most = (sides) => ["in", "outside", "inside", "not known"].reduce((best, side) => ((sides[side] || 0) > (sides[best] || 0) ? side : best), "in");
  const PLACES = { cell: "At the cell membrane", er: "Endoplasmic reticulum", mito: "Mitochondrion", nucleus: "Nuclear envelope", other: "Golgi apparatus", membrane: "At a membrane" };
  // The only members of their families, in parts by shelf, district and side: id, shelf, side, district, how many, the units they would make
  const lone = [
    ["lone-channels-in", "cell", "in", "channels", 4, ["U03"]],
    ["lone-signalling-inside", "cell", "inside", "signalling", 3, []],
    ["lone-signalling-inside", "nucleus", "inside", "signalling", 2, []],
    ["lone-enzymes-not-known", "mito", "not known", "enzymes", 2, []],
    ["lone-enzymes-not-known", null, "not known", "enzymes", 3, []],
  ];
  const files = { "members-00.json": [], "members-01.json": [], "members-02.json": [] };
  let serial = 0;
  const members = (file, label, shelf, sides, units = [], alone = false) => {
    const from = files[file].length;
    for (const [side, n] of Object.entries(sides)) {
      for (let index = 0; index < n; index++) {
        serial += 1;
        const unknown = side === "not known";
        // As a curated proteome has them: stated, but for the membrane that is not named, where a segment is predicted.
        const basis = unknown ? "none" : shelf === "membrane" ? "predicted" : "stated";
        const marks = { isoforms: 1 + (serial % 3) };
        if (basis === "stated" || (unknown && shelf)) marks.evidence = ["experiment", "curator", "similarity"][serial % 3];
        if (shelf === "other") marks.where = ["Golgi apparatus", "Lysosome", "Peroxisome"][serial % 3];
        else if (unknown && shelf) marks.where = PLACES[shelf];
        // One that is the only member of its family names that family: its accession and its name.
        if (alone) marks.family = [`IPR92${String(serial).padStart(4, "0")}`, `Solo family ${serial}`];
        files[file].push([`TC${String(serial).padStart(5, "0")}`, alone ? `Solo protein ${serial}` : serial % 4 ? `${label} ${serial}` : "", serial % 2 ? `MADE${serial}` : "", side, basis, 150 + 3 * serial, units.length && side === "in" ? units : null, marks]);
      }
    }
    return [from, files[file].length];
  };
  // A family's line carries, last, its family's members on every shelf and on none.
  const familyRows = families.flatMap(([id, label, group, lines]) => lines.map(([shelf, sides, units = []]) => [id, label, shelf, most(sides), group, total(sides), sides, "members-00.json", members("members-00.json", label, shelf, sides, units), units, lines.reduce((sum, [, all]) => sum + total(all), 0)]));
  const loneRows = lone.map(([id, shelf, side, group, n, units]) => [id, "The only member of its family", "lone", shelf, side, group, n, { [side]: n }, "members-01.json", members("members-01.json", "", shelf, { [side]: n }, units, true), units]);
  const partRows = parts.flatMap(([id, label, kind, group, lines]) => lines.map(([shelf, sides]) => [id, label, kind, shelf, most(sides), group, total(sides), sides, "members-02.json", members("members-02.json", label, shelf, sides)]));
  const lines = [...families.flatMap((item) => item[3]), ...lone.map(([, shelf, side, , n]) => [shelf, { [side]: n }]), ...parts.flatMap((item) => item[4])];
  const sidesOf = (some) => Object.fromEntries(SIDES.map((side) => [side, some.reduce((sum, [, sides]) => sum + (sides[side] || 0), 0)]));
  const found = {};
  for (const row of Object.values(files).flat()) (found[row[3]] ??= {})[row[4]] = (found[row[3]][row[4]] || 0) + 1;
  const data = {
    format: SHELVES_FORMAT,
    species: "testcell",
    made: "2026-11-15",
    made_up: true,
    from: `A made-up catalogue for the tests of several shelves: ${total(sidesOf(lines))} invented proteins. Every name and number is made up; nothing here is real.`,
    shelves: structuredClone(SIX),
    groups: [
      { id: "channels", label: "Channels", from: "made up" },
      { id: "signalling", label: "Receptors and signalling", from: "made up" },
      { id: "enzymes", label: "Enzymes", from: "made up" },
      { id: "unclassed", label: "Not classed by function", from: "made up" },
    ],
    family_from: "A family is a made-up entry; a protein is filed under one, and a family has a line for each shelf that holds members of it.",
    family_columns: ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units", "total"],
    families: familyRows,
    distinct_families: families.length,
    families_in_all: families.length + lone.reduce((sum, part) => sum + part[4], 0),
    lone: {
      label: "The only member of its family",
      count: lone.reduce((sum, part) => sum + part[4], 0),
      parts_from: "A made-up family with one member has no line: its protein is listed here, in parts by shelf, district and side, and names its family in its mark 'family'.",
      part_columns: ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at", "units"],
      parts: loneRows,
    },
    no_family: {
      label: "No family assigned",
      count: partRows.reduce((sum, row) => sum + row[6], 0),
      sides: Object.fromEntries(Object.entries(sidesOf(parts.flatMap((item) => item[4]))).filter(([, n]) => n)),
      parts_from: "A protein with no family is filed under a made-up superfamily, under its other signatures, or under none; each part has a line for each shelf.",
      part_columns: ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at"],
      parts: partRows,
    },
    member_columns: ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
    members_from: { format: MEMBERS_FORMAT, order: "The members follow the lines in order: every line of the families as listed, then every part of lone, then every line of the parts of no family.", files: "Three files, kept beside this one: the members of the families, the only members of their families, and those with no family." },
    side_notes: {
      stated: "As a made-up curated entry states it.",
      predicted: "A made-up predictor read a membrane segment in the sequence; no source names the membrane.",
      none: "No entry states the side and nothing predicts it.",
    },
    marks: {
      isoforms: { label: "Isoforms described", values: "number", measured: false, source: "Made-up catalogue" },
      evidence: { label: "What stands behind the stated place", values: ["experiment", "curator", "similarity"], measured: false, source: "Made-up catalogue" },
      where: { label: "Place named", values: "text", measured: false, source: "Made-up catalogue" },
      family: { label: "Family, of which it is the only member here", values: "text", measured: false, source: "Made-up catalogue" },
    },
    counts: sidesOf(lines),
    shelf_counts: Object.fromEntries([...SIX.map((shelf) => [shelf.id, sidesOf(lines.filter(([at]) => at === shelf.id))]), [NO_SHELF, sidesOf(lines.filter(([at]) => at === null))]]),
    by_basis: Object.fromEntries(SIDES.filter((side) => found[side]).map((side) => [side, Object.fromEntries(BASES.filter((basis) => found[side][basis]).map((basis) => [basis, found[side][basis]]))])),
    sources: [{ name: "Made-up catalogue", licence: "None needed: every name and number here is invented for the tests", class: "permissive", holds: "nothing real" }],
  };
  change(data);
  const memberFiles = Object.fromEntries(Object.entries(files).map(([name, rows]) => [name, { format: MEMBERS_FORMAT, species: "testcell", file: name, made_up: true, columns: data.member_columns, members: rows }]));
  return { data, memberFiles };
}

/** A fixture's text: indented, with each line of a table on one line of the file. */
function fixtureText(value) {
  const kept = [];
  const text = JSON.stringify(value, (key, item) => (["families", "parts", "members"].includes(key) && Array.isArray(item) ? item.map((row) => `@row${kept.push(JSON.stringify(row)) - 1}@`) : item), 2);
  return `${text.replace(/"@row(\d+)@"/g, (_, index) => kept[Number(index)])}\n`;
}

function several({ loaded = true, change } = {}) {
  const { data, memberFiles } = madeUpSeveral({ change });
  const shelves = new Shelves(data, { label: "Test cell", links: LINKS, units: UNITS });
  if (loaded) for (const [name, file] of Object.entries(memberFiles)) shelves.addMembers(name, file);
  return shelves;
}
const line = (shelves, type, id, shelf) => shelves.get(keyOf("testcell", type, id, shelf));

test("the made-up species with several shelves is kept as a file, and the file is the one described here", async () => {
  const { data, memberFiles } = madeUpSeveral();
  const folder = path.join(SEVERAL, "testcell");
  if (process.env.WRITE_SHELVES_FIXTURE) {
    await mkdir(folder, { recursive: true });
    await writeFile(path.join(folder, "shelves.json"), fixtureText(data));
    for (const [name, file] of Object.entries(memberFiles)) await writeFile(path.join(folder, name), fixtureText(file));
  }
  assert.deepEqual(JSON.parse(await readFile(path.join(folder, "shelves.json"), "utf8")), data, "run with WRITE_SHELVES_FIXTURE=1 to write it again");
  for (const [name, file] of Object.entries(memberFiles)) assert.deepEqual(JSON.parse(await readFile(path.join(folder, name), "utf8")), file, name);
  assert.deepEqual((await readdir(folder)).sort(), ["members-00.json", "members-01.json", "members-02.json", "shelves.json"]);
  // It says of itself that it is made up, and holds no machine path.
  const written = await readFile(path.join(folder, "shelves.json"), "utf8");
  assert.equal(data.made_up, true);
  assert.match(data.from, /made up; nothing here is real/);
  assert.ok(!MACHINE.test(written));
  assert.deepEqual(validateShelves(data), []);
});

test("several shelves: every line is on one shelf or on none, and each shelf is counted on its own", () => {
  const shelves = several({ loaded: false });
  assert.equal(shelves.several, true);
  assert.equal(small().several, false);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["cell", "er", "mito", "nucleus", "other", "membrane"], "in the file's order");
  assert.equal(shelves.kind, "families");
  assert.equal(shelves.total, 131, "the families' lines, the only members of their families and those with no family, together");
  assert.deepEqual(shelves.counts, { outside: 6, in: 42, inside: 56, "not known": 27 });
  // A family split over shelves is one family: ten families in eighteen lines; four parts in nine.
  assert.equal(shelves.familyCount, 10);
  assert.equal(shelves.families.length, 18);
  assert.equal(shelves.parts.length, 9);
  // A family of one has no line: its protein is under `lone`. Fourteen such, in five parts; twenty-four families in all.
  assert.deepEqual([shelves.lone.length, shelves.loneAll.count, shelves.familiesInAll], [5, 14, 24]);
  // What stands on each shelf, and on none, as the lines have it and as the file says.
  assert.deepEqual(shelves.byShelf.map((entry) => [entry.id, entry.proteins, entry.lines, entry.families, entry.lone]), [["cell", 48, 10, 4, 7], ["er", 7, 3, 3, 0], ["mito", 17, 4, 2, 2], ["nucleus", 23, 5, 3, 2], ["other", 8, 3, 2, 0], ["membrane", 11, 3, 2, 0], [null, 17, 4, 2, 3]]);
  assert.deepEqual(shelves.byShelf.map((entry) => entry.label), [...SIX.map((shelf) => shelf.label), null]);
  for (const entry of shelves.byShelf) assert.deepEqual(entry.counts, shelves.data.shelf_counts[entry.id ?? NO_SHELF], `${entry.id}: the file's counts are those of its lines`);
  assert.equal(shelves.byShelf.reduce((sum, entry) => sum + entry.proteins, 0), shelves.total, "every protein is on one shelf or on none");
  assert.deepEqual(shelves.byShelf.at(-1).counts, { outside: 0, in: 0, inside: 0, "not known": 17 }, "what is on no shelf has no known side");
  // Each line knows its shelf; a line on no shelf has none.
  assert.equal(line(shelves, "f", "IPR900001", "mito").shelf, "mito");
  assert.equal(shelves.shelfOf(line(shelves, "f", "IPR900001", "mito")).label, "Mitochondrial inner membrane");
  assert.equal(line(shelves, "f", "IPR900003", null).shelf, null);
  assert.equal(shelves.shelfOf(line(shelves, "f", "IPR900003", null)), null);
  // A species with one shelf counts everything on it.
  assert.deepEqual(small().byShelf.map((entry) => [entry.id, entry.proteins, entry.counts]), [["cell", 9, { outside: 1, in: 2, inside: 4, "not known": 2 }]]);
  assert.deepEqual(large({ loaded: false }).byShelf.map((entry) => [entry.id, entry.proteins, entry.lines, entry.families, entry.lone]), [["cell", 50, 11, 7, 0]]);
});

test("several shelves: a line is identified by its id and its shelf together, and one shelf's keys stay as they were", () => {
  const shelves = several({ loaded: false });
  // The same family on three shelves: three lines, three keys.
  const lines = ["cell", "er", "mito"].map((shelf) => line(shelves, "f", "IPR900001", shelf));
  assert.deepEqual(lines.map((item) => item.key), ["own:testcell:f@cell:IPR900001", "own:testcell:f@er:IPR900001", "own:testcell:f@mito:IPR900001"]);
  assert.deepEqual(lines.map((item) => [item.shelf, item.count, item.side]), [["cell", 7, "in"], ["er", 3, "in"], ["mito", 3, "in"]]);
  assert.equal(line(shelves, "f", "IPR900003", null).key, "own:testcell:f@:IPR900003", "nothing after the @: on no shelf");
  assert.equal(line(shelves, "g", "no-signature", "membrane").key, "own:testcell:g@membrane:no-signature");
  // The key reads back, with its shelf; a key with none says nothing of a shelf.
  assert.deepEqual(parseKey("own:testcell:f@mito:IPR900001"), { species: "testcell", type: "f", id: "IPR900001", shelf: "mito" });
  assert.deepEqual(parseKey("own:testcell:f@:IPR900003"), { species: "testcell", type: "f", id: "IPR900003", shelf: null });
  assert.deepEqual(parseKey("own:testcell:m@er:channels|in"), { species: "testcell", type: "m", id: "channels|in", shelf: "er" });
  assert.deepEqual(parseKey("own:testworm:f:IPR000001"), { species: "testworm", type: "f", id: "IPR000001" });
  assert.deepEqual(parseKey("own:testbug:p:with:colons@and-an-at"), { species: "testbug", type: "p", id: "with:colons@and-an-at" }, "whatever an id holds, it is the id");
  assert.equal(parseKey("own:testcell:family@cell:IPR900001"), null);
  // Every key is one line's alone.
  const all = [...shelves.families, ...shelves.parts, ...shelves.markers.filter((item) => item.holds)];
  assert.equal(new Set(all.map((item) => item.key)).size, all.length);
  for (const item of all) {
    assert.equal(shelves.get(item.key), item);
    assert.deepEqual(parseKey(item.key), { species: "testcell", type: item.type, id: item.id, shelf: item.shelf });
  }
  assert.equal(shelves.get("own:testcell:f:IPR900001"), null, "a key that names no shelf is no line's, where there are several");
  // With one shelf the keys are what they always were: no shelf in them, whatever the kind.
  assert.equal(keyOf("testworm", "f", "IPR000001"), "own:testworm:f:IPR000001");
  for (const one of [small(), large({ loaded: false })]) {
    for (const key of one.byKey.keys()) assert.match(key, /^own:test(bug|worm):[a-z]:[^@]*$/, key);
  }
  assert.deepEqual(large({ loaded: false }).markers.filter((item) => item.holds).map((item) => item.key), ["own:testworm:m:channels|in", "own:testworm:m:signalling|inside", "own:testworm:m:signalling|outside", "own:testworm:n:no-family|inside"]);
});

test("several shelves: the smaller families are gathered by shelf, district and side, and a member's shelf is its line's", () => {
  // Two small families beside the made-up ones, each on two shelves and of fewer than five in all: they stand gathered, shelf by shelf.
  const more = (data) => {
    const rows = [
      ["IPR900011", "Petty pump", "cell", "in", "channels", 2, { in: 2 }, "members-00.json", [0, 2], [], 3],
      ["IPR900011", "Petty pump", "er", "in", "channels", 1, { in: 1 }, "members-00.json", [2, 3], [], 3],
      ["IPR900012", "Minor relay", "cell", "in", "channels", 2, { in: 2 }, "members-00.json", [3, 5], [], 4],
      ["IPR900012", "Minor relay", "er", "in", "channels", 2, { in: 2 }, "members-00.json", [5, 7], [], 4],
    ];
    data.families.push(...rows);
    delete data.shelf_counts; delete data.counts; delete data.distinct_families; delete data.families_in_all; delete data.by_basis;
  };
  const small = several({ loaded: false, change: more });
  const held = (shelf) => small.markers.find((item) => item.key === keyOf("testcell", "m", "channels|in", shelf)).holds.map((family) => [family.id, family.shelf, family.count]);
  assert.deepEqual(held("cell"), [["IPR900011", "cell", 2], ["IPR900012", "cell", 2]]);
  assert.deepEqual(held("er"), [["IPR900011", "er", 1], ["IPR900012", "er", 2]], "the same district and side on another shelf is another gathering");
  assert.equal(small.get("own:testcell:f@er:IPR900011").within, small.get("own:testcell:m@er:channels|in"));
  assert.deepEqual([small.get("own:testcell:m@cell:channels|in").count, small.get("own:testcell:m@cell:channels|in").label], [4, "2 smaller families"]);
  const shelves = several();
  const marker = (type, id, shelf) => shelves.markers.find((item) => item.key === keyOf("testcell", type, id, shelf));
  // A family of five or more in all has a marker on every shelf it is on, however few it holds there.
  assert.ok(marker("f", "IPR900001", "cell") && marker("f", "IPR900001", "er") && marker("f", "IPR900001", "mito"), "seven, three and three");
  assert.equal(shelves.familyTotal(line(shelves, "f", "IPR900005", "er")), 7);
  assert.deepEqual(shelves.markers.filter((item) => item.id === "IPR900005").map((item) => [item.shelf, item.count]), [["er", 3], ["other", 4]]);
  // A family of fewer is gathered on its shelf; what is on no shelf stands apart from every shelf, whichever it is.
  assert.deepEqual(marker("m", "enzymes|in", "er").holds.map((family) => [family.id, family.shelf]), [["IPR900009", "er"]]);
  assert.equal(line(shelves, "f", "IPR900009", "er").within, marker("m", "enzymes|in", "er"));
  assert.ok(marker("f", "IPR900003", null) && marker("f", "IPR900010", null), "three and six with no place known: markers of their own");
  // The parts of "no family" likewise: a superfamily of ten or more in all stands on each of its shelves, one of fewer is gathered there, the other parts stand alone.
  assert.ok(marker("g", "IPR910001", "cell") && marker("g", "IPR910001", "nucleus"));
  assert.deepEqual(marker("n", "no-family|inside", "mito").holds.map((part) => part.id), ["IPR910002"]);
  assert.ok(marker("g", "no-signature", null) && marker("g", "no-signature", "cell") && marker("g", "other-signature", "other"));
  // Every protein is behind exactly one marker, and every marker is on one shelf or on none.
  assert.equal(shelves.markers.reduce((sum, item) => sum + item.count, 0), 131);
  for (const item of shelves.markers) assert.ok(item.shelf === null || shelves.shelfById.has(item.shelf), item.key);
  for (const entry of shelves.byShelf) assert.equal(shelves.markers.filter((item) => item.shelf === entry.id).reduce((sum, item) => sum + item.count, 0), entry.proteins, `${entry.id}: what stands on it is its count`);
  // Opening a line shows its members on that shelf alone, and each is a protein with a key of its own, without a shelf.
  const onCell = shelves.membersOf(line(shelves, "f", "IPR900001", "cell")), onMito = shelves.membersOf(line(shelves, "f", "IPR900001", "mito"));
  assert.deepEqual([onCell.length, onMito.length], [7, 3]);
  assert.ok(onCell.every((member) => member.shelf === "cell") && onMito.every((member) => member.shelf === "mito"));
  assert.deepEqual(onMito.map((member) => member.side).sort(), ["in", "in", "not known"]);
  assert.match(onCell[0].key, /^own:testcell:p:TC\d{5}$/);
  assert.deepEqual(parseKey(onCell[0].key), { species: "testcell", type: "p", id: onCell[0].id });
  assert.ok(shelves.membersOf(line(shelves, "f", "IPR900003", null)).every((member) => member.shelf === null && member.side === "not known" && member.basis === "none"));
  const seen = new Set(shelves.markers.flatMap((item) => shelves.membersOf(item).map((member) => member.id)));
  assert.equal(seen.size, 131, "every protein is reached, once");
  // A machine finds the lines that hold its products: on their shelves, the largest first.
  assert.deepEqual(shelves.holdersOf("U01").map((item) => item.key), ["own:testcell:f@cell:IPR900001"]);
  assert.deepEqual(shelves.holdersOf("U02").map((item) => [item.label, item.shelf]), [["Harbour pore", "nucleus"]]);
});

test("several shelves: a family split over shelves is still one family", () => {
  const shelves = several();
  const onCell = line(shelves, "f", "IPR900001", "cell");
  assert.deepEqual(shelves.sameFamily(onCell).map((other) => [other.shelf, other.count]), [["er", 3], ["mito", 3]], "its lines on the other shelves, in the file's order");
  assert.equal(shelves.familyTotal(onCell), 13);
  assert.deepEqual(shelves.sameFamily(line(shelves, "f", "IPR900006", "nucleus")), [], "a family on one shelf has no other line");
  assert.deepEqual(shelves.sameFamily(line(shelves, "g", "no-signature", "cell")).map((other) => other.shelf), ["membrane", null], "a part likewise, and a line on no shelf counts");
  // A key from elsewhere that names the family and no shelf leads to its line with the most members.
  assert.equal(shelves.resolve("own:testcell:f:IPR900001"), "own:testcell:f@cell:IPR900001");
  assert.equal(shelves.resolve("own:testcell:f:IPR900004"), "own:testcell:f@mito:IPR900004");
  assert.equal(shelves.resolve("own:testcell:f@er:IPR900001"), "own:testcell:f@er:IPR900001");
  assert.equal(shelves.resolve("own:testcell:f@nucleus:IPR900001"), null, "a shelf it is not on");
  assert.equal(shelves.resolve("own:testworm:f:IPR900001"), null, "another species");
  assert.equal(shelves.resolve("own:testcell:f:IPR999999"), null);
  // With one shelf a family is one line, and a key is itself.
  const one = large();
  const innexin = one.get(keyOf("testworm", "f", "IPR000001"));
  assert.deepEqual(one.sameFamily(innexin), []);
  assert.equal(one.familyTotal(innexin), 8);
  assert.equal(one.resolve(innexin.key), innexin.key);
  assert.equal(one.familyCount, one.families.length);
});

test("several shelves: each shelf has its own words for its sides, and they read in a sentence", () => {
  const shelves = several();
  const said = (id) => {
    const words = shelves.sideWords(id);
    return [words.outside.short, words.in.short, words.in.long, words.inside.short];
  };
  assert.deepEqual(said("cell"), ["Outside the cell", "In the cell membrane", "Spans the cell membrane", "Inside the cell"]);
  assert.deepEqual(said("er"), ["On the cytoplasmic face of the endoplasmic reticulum", "In the endoplasmic reticulum membrane", "Spans the endoplasmic reticulum membrane", "In the endoplasmic reticulum's lumen"]);
  assert.deepEqual(said("mito"), ["Between the mitochondrion's two membranes", "In the mitochondrial inner membrane", "Spans the mitochondrial inner membrane", "In the mitochondrial matrix"]);
  assert.deepEqual(said("nucleus"), ["On the cytoplasmic face of the nuclear envelope", "In the nuclear envelope", "Spans the nuclear envelope", "In the nucleus"]);
  assert.deepEqual(said("other"), ["On the cytoplasmic face of one of the other membranes", "In one of the other membranes", "Spans one of the other membranes", "Within one of the other compartments"]);
  assert.deepEqual(said("membrane"), ["Beyond a membrane", "In a membrane, not told which", "Spans a membrane, not told which", "On the cytoplasmic side of a membrane"]);
  assert.equal(shelves.sideWords("membrane").outside.long, "Beyond a membrane: outside the cell, or within a compartment", "the long words say what lies beyond a membrane there");
  // With no shelf named, the words are the first shelf's: what a species with one shelf has always had.
  assert.deepEqual(shelves.sideWords(), shelves.sideWords("cell"));
  assert.deepEqual(shelves.sideWords(SIX[3]), shelves.sideWords("nucleus"), "a shelf may be given itself");
  // A side that is not known: of a shelf, or with no shelf at all.
  assert.match(shelves.sideWords("mito")["not known"].long, /^No source states its side of the mitochondrial inner membrane and nothing predicts it: set apart beside its shelf, not placed by guess$/);
  assert.match(shelves.sideWords("membrane")["not known"].long, /^No source states its side of a membrane and nothing predicts it: /, "the shelf's own afterthought is left out of the sentence");
  assert.deepEqual([shelves.sideWords(null)["not known"].short, shelves.sideWords(null)["not known"].swatch], ["No place known", "own-unknown"]);
  assert.match(shelves.sideWords(null)["not known"].long, /it stands apart from every shelf, not placed by guess$/);
  // The labels the contract names for the six shelves, and others a file may choose, as they read in a sentence.
  const within = (label, more = {}) => new Shelves(madeUpSeveral({ change: (data) => Object.assign(data.shelves[0], { label, ...more }) }).data, {}).sideWords("cell").in;
  for (const [label, one] of [
    ["Cell membrane", "the cell membrane"],
    ["The cell membrane", "the cell membrane"],
    ["Endoplasmic reticulum membrane", "the endoplasmic reticulum membrane"],
    ["The endoplasmic reticulum's membrane", "the endoplasmic reticulum's membrane"],
    ["ER membrane", "the ER membrane"],
    ["Mitochondrial inner membrane", "the mitochondrial inner membrane"],
    ["The mitochondrion's inner membrane", "the mitochondrion's inner membrane"],
    ["Nuclear envelope", "the nuclear envelope"],
    ["Other membranes", "one of the other membranes"],
    ["The cell's remaining membranes", "one of the cell's remaining membranes"],
    ["Other membranes: Golgi, endosomes, lysosomes, peroxisomes and vesicles", "one of the other membranes"],
    ["A membrane, not told which", "a membrane, not told which"],
    ["The cell's membranes, not told apart", "a membrane"],
  ]) {
    assert.deepEqual(within(label), { short: `In ${one}`, long: `Spans ${one}`, swatch: "own-in" }, label);
  }
  // A shelf whose label does not read so may say it itself.
  assert.deepEqual(within("Golgi and vesicles", { in: "In a membrane of the Golgi or of a vesicle" }), { short: "In a membrane of the Golgi or of a vesicle", long: "Spans a membrane of the Golgi or of a vesicle", swatch: "own-in" });
  assert.equal(shelves.membraneOf("nucleus"), "the nuclear envelope");
  assert.equal(shelves.membraneOf(null), "a membrane");
  // One shelf: as it was.
  assert.deepEqual(small().sideWords("cell"), small().sideWords());
  assert.equal(small().sideWords()["not known"].long, "No source states the side and nothing predicts it: set apart, not placed by guess");
});

test("several shelves: a protein's panel says where it is against its own shelf, and tells a side not known from no place known", () => {
  const shelves = several();
  const member = (id, shelf, side) => shelves.membersOf(line(shelves, "f", id, shelf)).find((protein) => protein.side === side);
  const text = (protein) => shelves.describe(protein.key);
  assert.match(text(member("IPR900006", "nucleus", "in")).plain, /^It spans the nuclear envelope\. A curated entry or a paper states it\.$/);
  assert.match(text(member("IPR900002", "nucleus", "inside")).plain, /^It is in the nucleus\. /);
  assert.match(text(member("IPR900002", "nucleus", "outside")).plain, /^It is on the cytoplasmic face of the nuclear envelope\. /);
  assert.match(text(member("IPR900004", "mito", "outside")).plain, /^It is between the mitochondrion's two membranes\. /);
  assert.match(text(member("IPR900004", "mito", "inside")).plain, /^It is in the mitochondrial matrix\. /);
  assert.match(text(member("IPR900005", "er", "inside")).plain, /^It is in the endoplasmic reticulum's lumen\. /);
  assert.match(text(member("IPR900005", "other", "in")).plain, /^It spans one of the other membranes\. /);
  assert.match(text(member("IPR900008", "membrane", "in")).plain, /^It spans a membrane, not told which\. That is predicted from its sequence; it was not measured\.$/);
  assert.match(text(member("IPR900008", "membrane", "outside")).plain, /^It is beyond a membrane\. That is predicted/);
  assert.match(text(member("IPR900001", "cell", "inside")).plain, /^It is inside the cell\. /);
  // The shelf is known and the side is not: set apart beside its shelf. No place at all: apart from every shelf.
  const beside = text(member("IPR900007", "nucleus", "not known"));
  assert.equal(beside.plain, "Its side of the nuclear envelope is not known. No source states it and nothing predicts it, so it is set apart beside its shelf and not placed by guess.");
  assert.deepEqual(beside.chips.map((chip) => chip.label), ["Not in the law inventory", "Side not known", "Not known"]);
  const facts = Object.fromEntries(beside.facts);
  assert.equal(facts.Shelf, "Nuclear envelope");
  assert.equal(facts["Place named"], "Nuclear envelope", "the place a source names is among its marks");
  assert.equal(facts.Family, "Drift factor (IPR900007)");
  const nowhere = text(member("IPR900010", null, "not known"));
  assert.equal(nowhere.plain, "No place is known for it: no source states where it is and nothing predicts it, so it stands apart from every shelf and is not placed by guess.");
  assert.deepEqual(nowhere.chips.map((chip) => chip.label), ["Not in the law inventory", "No place known", "Not known"]);
  assert.equal(Object.fromEntries(nowhere.facts).Shelf, "None: no place is known");
  // The chip names the membrane, and a member leads back to its own line.
  const pore = text(member("IPR900006", "nucleus", "in"));
  assert.deepEqual(pore.chips.map((chip) => chip.label), ["Would make a unit of the law inventory", "In the nuclear envelope", "Stated"]);
  assert.deepEqual(pore.opens, [{ title: "Its family", items: [{ id: "own:testcell:f@nucleus:IPR900006", label: "Harbour pore", swatch: "map-assigned" }] }]);
  assert.equal(Object.fromEntries(pore.facts).Shelf, "Nuclear envelope");
  // A member of a line that stands gathered leads back to that line itself, once the gathering has been opened.
  const fresh = several();
  const gathered = fresh.membersOf(line(fresh, "m", "enzymes|in", "er"))[0];
  assert.equal(fresh.describe(gathered.key).opens[0].items[0].id, "own:testcell:f@er:IPR900009");
  // One shelf: the words of before, with no shelf among the facts.
  assert.match(small().describe(keyOf("testbug", "p", "TB_008")).plain, /^Its side of the membrane is not known\. /);
  assert.equal(Object.fromEntries(small().describe(keyOf("testbug", "p", "TB_004")).facts).Shelf, undefined);
});

test("several shelves: a family's panel speaks of its line on one shelf and leads to its lines on the others", () => {
  const shelves = several();
  const onCell = shelves.describe("own:testcell:f@cell:IPR900001");
  assert.equal(onCell.eyebrow, "Test cell protein family");
  assert.equal(onCell.plain, "A family of 13 proteins, 7 of them on this shelf, the cell membrane. Opening it shows those 7. Most members' sides are as curated entries state them; each member's card says how its own is known.");
  const facts = Object.fromEntries(onCell.facts);
  assert.equal(facts.Proteins, "7");
  assert.equal(facts.Shelf, "Cell membrane");
  assert.equal(facts["Where its members sit"], "6 proteins spanning the cell membrane; 1 protein inside the cell");
  assert.equal(facts.Elsewhere, "3 proteins at the endoplasmic reticulum membrane; 3 proteins at the mitochondrial inner membrane");
  assert.deepEqual(onCell.opens.map((group) => [group.title, group.count]), [["The same family on other shelves", 2], ["Its proteins", 7]]);
  // Its lines elsewhere stand on their own there (three and three, of a family of thirteen): the links lead to them.
  assert.deepEqual(onCell.opens[0].items, [
    { id: "own:testcell:f@er:IPR900001", label: "Endoplasmic reticulum membrane · 3", swatch: "own-family" },
    { id: "own:testcell:f@mito:IPR900001", label: "Mitochondrial inner membrane · 3", swatch: "own-family" },
  ]);
  // A line that stands gathered (a part of fewer than ten in all) is led to by the marker that holds it, until it is open.
  const narrow = shelves.describe("own:testcell:g@cell:IPR910002");
  assert.deepEqual(several({ loaded: false }).describe("own:testcell:g@cell:IPR910002").opens[0].items, [{ id: "own:testcell:n@mito:no-family|inside", label: "Mitochondrial inner membrane · 3", swatch: "own-family" }]);
  assert.equal(narrow.opens[0].title, "The same grouping on other shelves");
  assert.deepEqual(onCell.chips.map((chip) => chip.label), ["Holds parts of a unit of the law inventory", "Most in the cell membrane"]);
  assert.deepEqual(onCell.disclosures.map((item) => item.title), ["How a side is stated", "How a side is predicted"]);
  // A line that has a marker of its own is linked to directly; a line on no shelf says so.
  const kinase = shelves.describe("own:testcell:f@nucleus:IPR900002");
  assert.deepEqual(kinase.opens[0].items, [{ id: "own:testcell:f@cell:IPR900002", label: "Cell membrane · 8", swatch: "own-family" }]);
  assert.match(kinase.plain, /^A family of 14 proteins, 6 of them on this shelf, the nuclear envelope\. Opening it shows those 6\./);
  assert.equal(Object.fromEntries(kinase.facts)["Where its members sit"], "1 protein on the cytoplasmic face of the nuclear envelope; 5 proteins in the nucleus");
  const mist = shelves.describe("own:testcell:f@:IPR900010");
  assert.match(mist.plain, /^A family of 7 proteins, 6 of them on no shelf, since no place is known for them\. Opening it shows those 6\./);
  assert.deepEqual(mist.chips.map((chip) => chip.label), ["Not in the law inventory", "No place known"]);
  const mistFacts = Object.fromEntries(mist.facts);
  assert.deepEqual([mistFacts.Shelf, mistFacts["Where its members sit"], mistFacts.Elsewhere], ["None: no place is known", "6 proteins with no place known", "1 protein at the cell membrane"]);
  assert.equal(Object.fromEntries(shelves.describe("own:testcell:f@cell:IPR900010").facts).Elsewhere, "6 proteins on no shelf");
  // A family on one shelf only is said as it always was; a line whose side is mostly not known stands apart beside its shelf.
  const pore = shelves.describe("own:testcell:f@nucleus:IPR900006");
  assert.match(pore.plain, /^A family of 5 proteins\. Opening it shows every member\./);
  assert.equal(pore.opens.find((group) => /other shelves/.test(group.title)), undefined);
  const drift = shelves.describe("own:testcell:f@nucleus:IPR900007");
  assert.deepEqual(drift.chips.map((chip) => chip.label), ["Not in the law inventory", "Most side not known"]);
  assert.equal(Object.fromEntries(drift.facts)["Where its members sit"], "2 proteins in the nucleus; 4 proteins with no side known");
  // A part of "no family" on several shelves is still not a family; a gathering is of one shelf.
  const part = shelves.describe("own:testcell:g@cell:IPR910001");
  assert.match(part.plain, /^12 proteins with no family signature, filed here by the superfamily they share, a wider grouping than a family\. This is not a family\. These are the ones on this shelf, the cell membrane; 4 more stand elsewhere\./);
  assert.deepEqual(part.opens.map((group) => group.title), ["The same grouping on other shelves", "Its proteins"]);
  const gathering = shelves.describe("own:testcell:m@er:enzymes|in");
  assert.match(gathering.plain, /^1 smaller family of Enzymes, gathered so that they do not swamp the shelf: 1 protein in all\./);
  assert.equal(Object.fromEntries(gathering.facts).Shelf, "Endoplasmic reticulum membrane");
  // The list has one row for each line of a family, with that line's key: the list's headings
  // say the shelf, and no row carries a shelf's name among the words a search looks through.
  assert.deepEqual(shelves.listed(line(shelves, "f", "IPR900001", "cell")), { id: "own:testcell:f@cell:IPR900001", label: "Glimmer channel · 7", short: null, keywords: "IPR900001", swatch: "map-assigned" });
  assert.deepEqual(["er", "mito"].map((shelf) => shelves.listed(line(shelves, "f", "IPR900001", shelf)).id), ["own:testcell:f@er:IPR900001", "own:testcell:f@mito:IPR900001"], "the same family on three shelves: three rows, each its own line");
  assert.equal(shelves.listed(line(shelves, "f", "IPR900010", null)).id, "own:testcell:f@:IPR900010");
  for (const item of shelves.markers) assert.ok(!/membrane|envelope|place known/i.test([shelves.listed(item).short, shelves.listed(item).keywords].join(" ")), item.key);
  // A protein's row keeps its gene; a shelf has a row of its own.
  const anyMember = shelves.membersOf(line(shelves, "f", "IPR900001", "cell")).find((member) => member.gene);
  assert.equal(shelves.listed(anyMember).short, anyMember.gene);
  assert.deepEqual(shelves.listed(shelves.get("own:testcell:s@nucleus:shelf")), { id: "own:testcell:s@nucleus:shelf", label: "Nuclear envelope · 23", short: null, keywords: "shelf", swatch: "own-family" });
  // How the sides are known: mostly stated here, so the page does not call them predictions.
  assert.deepEqual(shelves.byBasis(), { stated: 94, predicted: 10, "by function": 0, none: 27 });
  assert.match(large().describe(keyOf("testworm", "f", "IPR000001")).plain, /Each member's side is predicted from the sequence of a protein that is itself predicted; it was not measured\.$/, "a catalogue of predictions says so as before");
  // A file of several shelves that does not count its sides by how they are known: the page claims neither.
  const uncounted = several({ change: (data) => delete data.by_basis });
  assert.match(uncounted.describe("own:testcell:f@nucleus:IPR900006").plain, /^A family of 5 proteins\. Opening it shows every member\. Each member's card says how its side is known\.$/);
  // Nowhere do the words say that the engine models one of these proteins.
  const words = JSON.stringify([...shelves.markers.map((item) => shelves.describe(item.key)), ...shelves.markers.flatMap((item) => shelves.membersOf(item).map((protein) => shelves.describe(protein.key)))]);
  assert.ok(!/(engine|Cells) (models|simulates|runs) (this|these|the|a) (protein|proteins|family)/i.test(words));
  assert.ok(!/Cells has (a |no )?laws? |law in Cells/.test(words), "the words stand on the law inventory");
  assert.ok(!/undefined|\bNaN\b|\[object/.test(words), "no word is missing from any panel");
});

test("what holds a machine's candidate products: a family, or a group of no family, counts once on however many shelves it stands", () => {
  // Three families have a line with a unit, and one gathering of families of one has; no group of "no family" has. Four markers are lit.
  assert.deepEqual(several().lawHolders(), { families: 3, lone: 1, parts: 0, markers: 4 });
  // A family with a unit on two of its shelves is still one family, and a group of "no family" with one on its two shelves is one group.
  const more = several({
    loaded: false,
    change: (data) => {
      const at = Object.fromEntries(data.family_columns.map((name, index) => [name, index]));
      data.families.find((row) => row[at.id] === "IPR900001" && row[at.shelf] === "er")[at.units] = ["U01"];
      data.no_family.part_columns.push("units");
      for (const row of data.no_family.parts) row.push(row[0] === "IPR910001" ? ["U02"] : []);
    },
  });
  assert.deepEqual(more.lawHolders(), { families: 3, lone: 1, parts: 1, markers: 7 });
  assert.equal(more.parts.filter((item) => item.units.length).length, 2, "the group's two lines, counted as one group");
  // One shelf: each family has one line, so the count is that of its families; a catalogue that stands as proteins has none of these.
  assert.equal(large().lawHolders().families, large().families.filter((item) => item.units.length).length);
  assert.deepEqual(small().lawHolders(), { families: 0, lone: 0, parts: 0, markers: 0 });
});

test("a catalogue in families offers the sets its file lists the proteins of, and knows which markers hold them", () => {
  // Without `highlights` there is nothing to show by, as before.
  assert.deepEqual([several().filterable(), large().filterable()], [[], []]);
  const swim = (more = () => {}) => (data) => {
    data.marks.swim = { label: "Swimming", values: [true], measured: false, note: "Made up.", source: "Made-up catalogue" };
    data.marks.rig = { label: "Rig it is part of", values: ["motor", "rudder", "keel"], measured: false, source: "Made-up catalogue" };
    data.highlights = {
      columns: ["mark", "value", "id", "gene", "kind", "under", "shelf", "side"],
      rows: [
        ["swim", true, "TC00001", "swmA", "family", "IPR900001", "cell", "in"],
        ["swim", true, "TC00002", "swmB", "family", "IPR900001", "cell", "in"],
        ["swim", true, "X1", "swmC", "family", "IPR900009", "er", "in"], // a small family, which stands gathered
        ["swim", true, "X2", "swmD", "lone", "lone-channels-in", "cell", "in"],
        ["swim", true, "X3", null, "part", "no-signature", null, "not known"],
        ["rig", "motor", "TC00001", "swmA", "family", "IPR900001", "cell", "in"],
        ["rig", "rudder", "X2", "swmD", "lone", "lone-channels-in", "cell", "in"],
      ],
    };
    more(data);
  };
  const { data } = madeUpSeveral({ change: swim() });
  assert.deepEqual(validateShelves(data), []);
  const shelves = several({ change: swim() });
  // Each mark is a set, with the values that have proteins, counted from the list.
  assert.deepEqual(shelves.filterable().map((mark) => [mark.id, mark.label, mark.set, mark.items.map((item) => [item.id, item.label, item.count])]), [
    ["swim", "Swimming", true, [["true", "Yes", 5]]],
    ["rig", "Rig it is part of", true, [["motor", "Motor", 1], ["rudder", "Rudder", 1]]],
  ]);
  // A line holds its own; a gathering, those of the lines it holds; four markers hold the five.
  const holds = (item) => shelves.highlightOf(item, "swim", "true").map((protein) => protein.gene || protein.id);
  assert.deepEqual(holds(line(shelves, "f", "IPR900001", "cell")), ["swmA", "swmB"]);
  assert.deepEqual(holds(line(shelves, "f", "IPR900001", "er")), [], "the same family on another shelf holds none");
  assert.deepEqual(holds(line(shelves, "f", "IPR900009", "er").within), ["swmC"]);
  assert.deepEqual([holds(line(shelves, "l", "lone-channels-in", "cell")), holds(line(shelves, "g", "no-signature", null))], [["swmD"], ["X3"]]);
  assert.deepEqual(shelves.markers.filter((item) => holds(item).length).map((item) => item.key).sort(), ["own:testcell:f@cell:IPR900001", "own:testcell:g@:no-signature", "own:testcell:l@cell:lone-channels-in", line(shelves, "f", "IPR900009", "er").within.key].sort());
  // A member is of the set if the list names it; another value is another set.
  const members = shelves.membersOf(line(shelves, "f", "IPR900001", "cell"));
  assert.deepEqual(members.filter((member) => holds(member).length).map((member) => member.id), ["TC00001", "TC00002"]);
  assert.deepEqual(shelves.highlightOf(line(shelves, "f", "IPR900001", "cell"), "rig", "motor").map((protein) => protein.gene), ["swmA"]);
  assert.deepEqual(shelves.highlightOf(line(shelves, "f", "IPR900001", "cell"), "rig", "keel"), []);
  // What breaks the rule: a line the file does not have, a mark it does not declare, a column missing.
  const broken = (more) => validateShelves(madeUpSeveral({ change: swim(more) }).data).join("; ");
  assert.match(broken((file) => (file.highlights.rows[0][5] = "IPR999999")), /highlights, TC00001: no line IPR999999 on cell/);
  assert.match(broken((file) => delete file.marks.swim), /highlights, TC00001: the mark swim is not declared/);
  assert.match(broken((file) => file.highlights.columns.pop()), /its highlights lack side/);
});

test("a family of one has no line: its protein stands with the other only members of their families, in a part that is never called a family", () => {
  const shelves = several();
  const part = line(shelves, "l", "lone-channels-in", "cell");
  assert.deepEqual([part.key, part.type, part.count, part.shelf, part.side, part.district], ["own:testcell:l@cell:lone-channels-in", "l", 4, "cell", "in", "channels"]);
  assert.deepEqual(parseKey(part.key), { species: "testcell", type: "l", id: "lone-channels-in", shelf: "cell" });
  // A marker of its own, in its district among the families: never gathered with anything, however few it holds.
  for (const one of shelves.lone) assert.ok(shelves.markers.includes(one) && !one.within && !one.holds, one.key);
  assert.equal(shelves.districtLabel(part), "Channels");
  assert.equal(line(shelves, "l", "lone-enzymes-not-known", null).key, "own:testcell:l@:lone-enzymes-not-known");
  // The same id on another shelf is another part, and the two are not one grouping as a family's lines are.
  const onCell = line(shelves, "l", "lone-signalling-inside", "cell"), inNucleus = line(shelves, "l", "lone-signalling-inside", "nucleus");
  assert.deepEqual([onCell.count, inNucleus.count, shelves.sameFamily(onCell)], [3, 2, []]);
  assert.equal(shelves.resolve("own:testcell:l:lone-signalling-inside"), null, "a part of lone is of its own shelf: a key with no shelf is no part's");
  // Its panel says what it is, and never calls it a family.
  const said = shelves.describe(part.key);
  assert.equal(said.eyebrow, "Test cell proteins, each the only one of its family");
  assert.equal(said.plain, "The only member of its family: 4 proteins of Channels, each alone in its family in this catalogue. They stand together here so that they do not swamp the shelf; opening it shows every one of them, each with the name of its family. This is not a family. Most members' sides are as curated entries state them; each member's card says how its own is known.");
  assert.ok(!/A family of|protein family|same family/.test(JSON.stringify([said.plain, said.eyebrow, said.opens.map((group) => group.title)])));
  const facts = Object.fromEntries(said.facts);
  assert.deepEqual([facts.Proteins, facts.District, facts.Shelf, facts["Where its members sit"]], ["4", "Channels", "Cell membrane", "4 proteins spanning the cell membrane"]);
  assert.deepEqual(said.opens.map((group) => [group.title, group.count]), [["Its proteins", 4]]);
  assert.deepEqual(said.chips.map((chip) => chip.label), ["Holds parts of a unit of the law inventory", "Most in the cell membrane"]);
  assert.match(shelves.describe("own:testcell:l@:lone-enzymes-not-known").plain, /^The only member of its family: 3 proteins of Enzymes, each alone in its family in this catalogue\. No place is known for any of them, so they stand together apart from every shelf; opening it shows/);
  assert.deepEqual(shelves.listed(part), { id: part.key, label: "The only member of its family · 4", short: null, keywords: "lone-channels-in", swatch: "map-assigned" });
  // Each of its proteins names its own family, which is looked up where any family is; and leads back to the part it is listed with.
  const members = shelves.membersOf(part);
  assert.equal(members.length, 4);
  assert.ok(members.every((member) => member.under === part && member.shelf === "cell" && member.side === "in"));
  const one = shelves.describe(members[0].key), own = members[0].marks.family;
  assert.match(own[0], /^IPR92\d{4}$/);
  const about = Object.fromEntries(one.facts);
  assert.equal(about.Family, `${own[1]} (${own[0]}): its only member in this catalogue`);
  assert.equal(about["Family, of which it is the only member here"], undefined, "said once, not twice");
  assert.equal(about["Filed under"], undefined);
  assert.deepEqual(one.opens, [{ title: "Listed with", items: [{ id: part.key, label: "The only member of its family", swatch: "map-assigned" }] }]);
  assert.ok(one.sections[0].items[0].links.some((link) => link.url === `https://www.ebi.ac.uk/interpro/entry/InterPro/${own[0]}/`));
  assert.match(one.keywords, new RegExp(`${own[0]} ${own[1]}`), "found by its family's accession and name");
  assert.match(one.plain, /^It spans the cell membrane\. A curated entry or a paper states it\.$/);
  // One protein alone in such a part is said as one.
  const single = several({ change: (data) => ((data.lone.parts[1][6] = 1), (data.lone.parts[1][7] = { inside: 1 }), (data.lone.parts[1][9] = [4, 5]), (data.lone.count = 12), delete data.shelf_counts, delete data.counts, delete data.families_in_all, delete data.by_basis) });
  assert.match(single.describe("own:testcell:l@cell:lone-signalling-inside").plain, /^The only member of its family: 1 protein of Receptors and signalling, alone in its family in this catalogue\. It stands here among the families of its district; opening this shows it, with the name of its family\. This is not a family\./);
  // A machine finds the part that holds one of its products.
  assert.deepEqual(shelves.holdersOf("U03").map((item) => item.key), [part.key]);
  assert.deepEqual(members[0].units, ["U03"]);
  // A catalogue with no such part is read as before.
  assert.deepEqual([large().lone, large().loneAll.count, large().familiesInAll], [[], 0, 7]);
});

test("every line of a family of five or more stands on its own, however few it holds on its shelf; the parts of no family likewise, from ten", () => {
  const shelves = several({ loaded: false });
  const standing = (type) => shelves.markers.filter((item) => item.type === type).map((item) => `${item.id.slice(-2)}@${item.shelf ?? ""}`).sort();
  // Every line of the families that have five or more members on all their shelves together: all but the family of one line and one member (09).
  assert.deepEqual(standing("f"), ["01@cell", "01@er", "01@mito", "02@cell", "02@nucleus", "03@", "03@cell", "03@membrane", "04@mito", "04@other", "05@er", "05@other", "06@nucleus", "07@nucleus", "08@membrane", "10@", "10@cell"]);
  // So a family of seven with three on one shelf and four on another (05) is seen on both, and a line of one protein (10 on the cell membrane) stands too.
  assert.deepEqual([line(shelves, "f", "IPR900005", "er").count, line(shelves, "f", "IPR900005", "other").count, line(shelves, "f", "IPR900010", "cell").count], [3, 4, 1]);
  for (const item of shelves.families.filter((family) => family.id !== "IPR900009")) assert.equal(item.within, undefined, `${item.key} is not gathered`);
  // What is left is gathered on its shelf: the one family with fewer than five in all.
  assert.deepEqual(shelves.markers.filter((item) => item.type === "m").map((item) => [item.key, item.holds.map((family) => family.id)]), [["own:testcell:m@er:enzymes|in", ["IPR900009"]]]);
  // The parts of no family: a superfamily of ten or more in all stands on each of its shelves (16: twelve and four); one of fewer is gathered on each (6: three and three).
  assert.deepEqual(standing("g"), ["01@cell", "01@nucleus", "re@", "re@cell", "re@cell", "re@membrane", "re@other"]);
  assert.deepEqual(shelves.markers.filter((item) => item.type === "n").map((item) => [item.key, item.holds.map((part) => part.id)]), [["own:testcell:n@cell:no-family|inside", ["IPR910002"]], ["own:testcell:n@mito:no-family|inside", ["IPR910002"]]]);
  // A file whose lines do not carry their family's total: it is added up from the family's lines.
  const bare = several({ loaded: false, change: (data) => (data.family_columns.pop(), data.families.forEach((row) => row.pop())) });
  assert.deepEqual(bare.markers.map((item) => item.key), shelves.markers.map((item) => item.key));
  // Every protein is behind one marker, and every marker has a key of its own.
  assert.equal(shelves.markers.reduce((sum, item) => sum + item.count, 0), 131);
  assert.equal(new Set(shelves.markers.map((item) => item.key)).size, shelves.markers.length);
  // With one shelf a family's members in all are those of its one line: five or more stand, fewer are gathered, as ever.
  const one = large({ loaded: false });
  assert.deepEqual(one.markers.filter((item) => item.type === "f").map((item) => item.count), [8, 5]);
});

test("several shelves: what breaks their rules is said, and such a file is not read", () => {
  const broken = (change) => validateShelves(madeUpSeveral({ change }).data).join(" | ");
  const at = Object.fromEntries(madeUpSeveral().data.family_columns.map((name, index) => [name, index]));
  const partAt = Object.fromEntries(madeUpSeveral().data.no_family.part_columns.map((name, index) => [name, index]));
  assert.match(broken((data) => (data.families[0][at.shelf] = "vacuole")), /IPR900001 on vacuole: its shelf "vacuole" is not one of the file's/);
  // A line on no shelf holds only proteins with no known side.
  assert.match(broken((data) => ((data.families[0][at.shelf] = null), (data.families[0][at.side] = "not known"))), /IPR900001: it is on no shelf, yet a side of it is known/);
  assert.match(broken((data) => (data.families[7][at.side] = "in")), /IPR900003: it is on no shelf, yet it stands on a side/);
  // A family has one line on a shelf, not two; so has a part.
  assert.match(broken((data) => (data.families[1][at.shelf] = "cell")), /IPR900001 on cell: the family has two lines on one shelf/);
  assert.match(broken((data) => (data.no_family.parts[1][partAt.shelf] = "cell")), /IPR910001 on cell: the part has two lines on one shelf/);
  // The file's own counts are those of its lines.
  assert.match(broken((data) => (data.shelf_counts.er.in += 1)), /its counts for the shelf er are not those of its lines/);
  assert.match(broken((data) => (data.shelf_counts[NO_SHELF]["not known"] = 2)), /its counts for the proteins on no shelf are not those of its lines/);
  assert.match(broken((data) => (data.shelf_counts.vacuole = { in: 1 })), /it counts a shelf "vacuole" that it does not have/);
  assert.match(broken((data) => (data.distinct_families = 18)), /it says it has 18 families; its lines are of 10/);
  assert.match(broken((data) => (data.families[0][at.sides] = { in: 6 })), /IPR900001 on cell: its sides do not add up to its 7 members/);
  // Every shelf has an id of its own; the columns name the shelf; "no family" comes in parts.
  assert.match(broken((data) => (data.shelves[1].id = "cell")), /its shelves do not each have an id of their own/);
  assert.match(broken((data) => (data.shelves[1].id = NO_SHELF)), /its shelves do not each have an id of their own/);
  assert.match(broken((data) => (data.family_columns[at.shelf] = "place")), /its family columns lack shelf/);
  assert.match(broken((data) => (data.no_family.part_columns[partAt.shelf] = "place")), /the columns of its parts lack shelf/);
  assert.match(broken((data) => ((data.no_family.parts = []), (data.no_family.file = "members-02.json"), (data.no_family.at = [0, 36]))), /on several shelves the proteins with no family are given in parts, each on its shelf/);
  // The parts of lone are held to the same: their columns, their shelves, what they add up to, and the families in all.
  const loneAt = Object.fromEntries(madeUpSeveral().data.lone.part_columns.map((name, index) => [name, index]));
  assert.match(broken((data) => (data.lone.part_columns[loneAt.shelf] = "place")), /the columns of the parts of lone lack shelf/);
  assert.match(broken((data) => (data.lone.count = 99)), /the parts of lone do not add up to its count/);
  assert.match(broken((data) => (data.lone.parts[0][loneAt.shelf] = "vacuole")), /lone-channels-in on vacuole: its shelf "vacuole" is not one of the file's/);
  assert.match(broken((data) => (data.lone.parts[2][loneAt.shelf] = "cell")), /lone-signalling-inside on cell: the part of lone has two lines on one shelf/);
  assert.match(broken((data) => (data.families_in_all = 10)), /it says it has 10 families in all; its lines and its lone proteins are of 24/);
  assert.throws(() => new Shelves(madeUpSeveral({ change: (data) => (data.families[0][at.shelf] = "vacuole") }).data), /does not follow its format/);
  // A file that says nothing of its counts by shelf, or of the number of its families, is read: both are counted from the lines.
  const quiet = new Shelves(madeUpSeveral({ change: (data) => (delete data.shelf_counts, delete data.distinct_families, delete data.families_in_all, delete data.counts) }).data, {});
  assert.deepEqual([quiet.familyCount, quiet.familiesInAll, quiet.byShelf.map((entry) => entry.proteins), quiet.counts], [10, 24, [48, 7, 17, 23, 8, 11, 17], { outside: 6, in: 42, inside: 56, "not known": 27 }]);
  // A small catalogue with several shelves is held to the same rules.
  const few = (change = () => {}) => madeUpSmall({ change: (data) => (data.shelves.push({ id: "inner", label: "Inner membrane", outside: "Between the two membranes", inside: "In the inner space" }), change(data)) });
  assert.deepEqual(validateShelves(few()), []);
  assert.match(validateShelves(few((data) => (data.proteins[0][3] = "outer"))).join(" "), /TB_001: its shelf "outer" is not one of the file's/);
  assert.match(validateShelves(few((data) => (data.proteins[1][3] = null))).join(" "), /TB_002: it is on no shelf, yet a side of it is known/);
  const two = new Shelves(few((data) => ((data.proteins[3][3] = "inner"), (data.proteins[7][3] = null))), {});
  assert.deepEqual(two.byShelf.map((entry) => [entry.id, entry.proteins]), [["cell", 7], ["inner", 1], [null, 1]]);
  assert.equal(two.get(keyOf("testbug", "p", "TB_004")).shelf, "inner");
  assert.match(two.describe(keyOf("testbug", "p", "TB_004")).plain, /^It is in the inner space\./);
  assert.match(two.describe(keyOf("testbug", "p", "TB_008")).plain, /^No place is known for it/);
  assert.match(two.describe(keyOf("testbug", "p", "TB_009")).plain, /^Its side of the cell membrane is not known\./);
  // And it is laid out the same way: each protein on its own shelf, the one with no shelf apart from both.
  const stack = layoutStack(two);
  const on = (area) => area.blocks.flatMap((block) => block.places.map((place) => place.item.id)).sort();
  assert.deepEqual(stack.shelves.map((shelf) => [shelf.id, on(shelf.plate), on(shelf.tray), on(shelf.apart)]), [["cell", ["TB_001", "TB_002", "TB_003"], ["TB_005", "TB_006", "TB_007"], ["TB_009"]], ["inner", [], ["TB_004"], []]]);
  assert.deepEqual(on(stack.apart), ["TB_008"]);
  assert.match(two.get(keyOf("testbug", "p", "TB_004")).key, /^own:testbug:p:TB_004$/, "a protein's key never carries a shelf");
});

// ---------------------------------------------------------------- where the markers stand, on several shelves

const AREAS = [["plate", ["in", "outside"]], ["tray", ["inside"]], ["apart", ["not known"]]];
/** An area's blocks, with every place in them, as plain numbers: what two layouts are compared by. */
const flat = (area) => area.blocks.map((block) => [block.district, block.label, block.count, block.x, block.z, block.width, block.depth, block.places.map((place) => [place.item.key, place.dx, place.dz, place.radius])]);
const VIEWS = [{}, { shape: 0.65, margin: 6, step: 9 }, { shape: 0.8, margin: 6, step: 9 }, { shape: 1.25, margin: 6, step: 9 }, { shape: 2.4, margin: 6, step: 9 }, { limit: 150 }];

/** For a species with one shelf: the stack of shelves is the one-shelf layout, place for place. */
function sameAsOneShelf(shelves, name) {
  for (const options of VIEWS) {
    const one = layoutShelves(shelves, options), stack = layoutStack(shelves, options);
    const said = `${name}, ${JSON.stringify(options)}`;
    assert.equal(stack.shelves.length, 1, said);
    assert.equal(stack.apart, null, said);
    const shelf = stack.shelves[0];
    for (const [id] of AREAS) {
      assert.deepEqual(flat(shelf[id]), flat(one[id]), `${said}: ${id}`);
      assert.deepEqual([shelf[id].id, shelf[id].sides, shelf[id].width, shelf[id].depth], [one[id].id, one[id].sides, one[id].width, one[id].depth], `${said}: ${id}`);
    }
    assert.deepEqual([stack.limit, stack.width, stack.depth, shelf.width, shelf.depth, shelf.z], [one.limit, one.width, one.depth, one.width, one.depth, 0], said);
  }
}

test("one shelf: the stack of shelves puts every marker exactly where the one-shelf layout does", () => {
  sameAsOneShelf(small(), "a small catalogue");
  sameAsOneShelf(new Shelves(madeUpSmall({ more: 400 }), {}), "a small catalogue of 400");
  sameAsOneShelf(large({ loaded: false }), "families");
  // The shelf comes in its own frame, as the drawing has always built one: the membrane at the origin, each next area a step in front.
  const shelves = new Shelves(madeUpSmall({ more: 180 }), {});
  const stack = layoutStack(shelves, { margin: 6, step: 9 }), shelf = stack.shelves[0];
  assert.deepEqual([shelf.id, shelf.index, shelf.proteins, shelf.markers], ["cell", 0, 189, 189]);
  assert.deepEqual(shelf.areas.map((area) => area.id), ["plate", "tray", "apart"]);
  assert.equal(shelf.areas[0].z, 0);
  assert.equal(shelf.areas[0].width, Math.max(shelf.plate.width, shelf.tray.width) + 12, "the membrane and the glass are one width");
  assert.equal(shelf.areas[1].width, shelf.areas[0].width);
  assert.equal(shelf.areas[2].width, shelf.apart.width + 12, "what is set apart keeps its own width");
});

test("several shelves: a stack of shelves of one width, each in its own frame, with what is on no shelf apart in front", () => {
  const shelves = several({ loaded: false });
  const margin = 6, step = 9, between = 18;
  const stack = layoutStack(shelves, { margin, step });
  assert.deepEqual(stack.shelves.map((shelf) => shelf.id), ["cell", "er", "mito", "nucleus", "other", "membrane"], "in the file's order");
  assert.deepEqual(stack.shelves.map((shelf) => shelf.index), [0, 1, 2, 3, 4, 5]);
  // Every marker stands once: on its own shelf, on its side of it; or, with no shelf, in the page's one set-apart area.
  const placed = [];
  for (const shelf of stack.shelves) {
    for (const [id, sides] of AREAS) {
      assert.deepEqual([shelf[id].id, shelf[id].sides], [id, sides]);
      for (const block of shelf[id].blocks) {
        assert.ok(block.label && block.count === block.places.reduce((sum, place) => sum + place.item.count, 0));
        for (const place of block.places) {
          assert.equal(place.item.shelf, shelf.id, `${place.item.key} stands on the shelf ${shelf.id}`);
          assert.ok(sides.includes(place.item.side), `${place.item.key} stands in the ${id}`);
          placed.push(place.item.key);
        }
      }
    }
    const counted = shelves.byShelf.find((entry) => entry.id === shelf.id);
    assert.deepEqual([shelf.proteins, shelf.markers], [counted.proteins, shelves.markers.filter((item) => item.shelf === shelf.id).length], shelf.id);
    assert.equal(shelf.shelf, shelves.shelfById.get(shelf.id));
  }
  assert.deepEqual([stack.apart.id, stack.apart.sides, stack.apart.proteins], ["apart", ["not known"], 17]);
  for (const block of stack.apart.blocks) for (const place of block.places) {
    assert.equal(place.item.shelf, null);
    placed.push(place.item.key);
  }
  assert.equal(placed.length, shelves.markers.length);
  assert.deepEqual([...placed].sort(), shelves.markers.map((item) => item.key).sort(), "every marker, once");
  // A protein with a shelf and no known side is set apart beside that shelf; one with no shelf, apart from them all.
  const nucleus = stack.shelves.find((shelf) => shelf.id === "nucleus");
  assert.deepEqual(nucleus.apart.blocks.flatMap((block) => block.places.map((place) => place.item.key)), ["own:testcell:f@nucleus:IPR900007"]);
  assert.deepEqual(stack.apart.blocks.flatMap((block) => block.places.map((place) => place.item.key)).sort(), ["own:testcell:f@:IPR900003", "own:testcell:f@:IPR900010", "own:testcell:g@:no-signature", "own:testcell:l@:lone-enzymes-not-known"]);
  // One width: every membrane and every glass is as wide as the widest of them.
  const widest = Math.max(...stack.shelves.flatMap((shelf) => [shelf.plate, shelf.tray].filter((band) => band.blocks.length).map((band) => band.width)));
  assert.equal(stack.common, widest);
  for (const shelf of stack.shelves) for (const area of shelf.areas) assert.equal(area.width, (area.id === "apart" ? shelf.apart.width : stack.common) + 2 * margin, `${shelf.id}: ${area.id}`);
  // Each shelf in its own frame: the first area's middle is the origin, each next one a step in front of the one before.
  const near = (a, b) => Math.abs(a - b) < 1e-9;
  for (const shelf of stack.shelves) {
    assert.deepEqual(shelf.areas.map((area) => area.id), AREAS.map(([id]) => id).filter((id) => shelf[id].blocks.length), shelf.id);
    assert.equal(shelf.areas[0].z, 0);
    for (const [index, area] of shelf.areas.entries()) {
      assert.equal(area.depth, shelf[area.id].depth + 2 * margin);
      if (index) assert.ok(near(area.z - area.depth / 2, shelf.areas[index - 1].z + shelf.areas[index - 1].depth / 2 + step), `${shelf.id}: ${area.id} stands a step in front`);
      // A block lies within its area, clear of the margin; no block over another; no marker on another.
      const blocks = shelf[area.id].blocks;
      for (const block of blocks) {
        assert.ok(Math.abs(block.x) + block.width / 2 <= area.width / 2 - margin + 1e-6 && Math.abs(block.z) + block.depth / 2 <= area.depth / 2 - margin + 1e-6, `${shelf.id}: ${block.label} lies within its area`);
        for (const [at, a] of block.places.entries()) for (const b of block.places.slice(at + 1)) assert.ok(distance(a, b) >= a.radius + b.radius, `${a.item.key} and ${b.item.key} overlap`);
        for (const item of block.places) assert.equal(item.radius, familyRadius(item.item.count));
      }
      for (const [at, a] of blocks.entries()) for (const b of blocks.slice(at + 1)) assert.ok(Math.abs(a.x - b.x) >= (a.width + b.width) / 2 - 1e-6 || Math.abs(a.z - b.z) >= (a.depth + b.depth) / 2 - 1e-6, `${a.label} lies over ${b.label}`);
    }
    assert.equal(shelf.back, -shelf.areas[0].depth / 2);
    assert.ok(near(shelf.front, shelf.areas.at(-1).z + shelf.areas.at(-1).depth / 2));
    assert.ok(near(shelf.depth, shelf.front - shelf.back), `${shelf.id}: its depth is that of its own areas`);
    assert.equal(shelf.width, Math.max(...shelf.areas.map((area) => area.width)));
  }
  // The shelf's place in the stack is apart from its frame: each further to the front, with room between, and nothing over anything.
  assert.equal(stack.shelves[0].z, 0);
  for (const [index, shelf] of stack.shelves.entries()) {
    if (index) assert.ok(near(shelf.z + shelf.back, stack.shelves[index - 1].z + stack.shelves[index - 1].front + between), `${shelf.id} stands in front of the shelf before it`);
  }
  const last = stack.shelves.at(-1);
  assert.ok(near(stack.apart.z - stack.apart.size.depth / 2, last.z + last.front + between), "what is on no shelf stands in front of every shelf");
  assert.deepEqual(stack.apart.size, { width: stack.apart.width + 2 * margin, depth: stack.apart.depth + 2 * margin });
  assert.ok(near(stack.depth, stack.apart.z + stack.apart.size.depth / 2 - stack.shelves[0].back));
  assert.equal(stack.width, Math.max(...stack.shelves.map((shelf) => shelf.width), stack.apart.size.width));
  // The room between two shelves is the caller's to say.
  const close = layoutStack(shelves, { margin, step, between: 4 });
  assert.ok(near(close.depth, stack.depth - 6 * (between - 4)));
  assert.deepEqual(close.shelves.map((shelf) => flat(shelf.plate)), stack.shelves.map((shelf) => flat(shelf.plate)), "the shelves themselves do not change");
  // A shelf with nothing on it takes no place; a catalogue with a shelf for every protein has no set-apart area of the page.
  const fewer = new Shelves(madeUpSeveral({ change: (data) => {
    const at = data.family_columns.indexOf("shelf"), partAt = data.no_family.part_columns.indexOf("shelf");
    data.families = data.families.filter((row) => row[at] !== null && row[at] !== "other");
    data.no_family.parts = data.no_family.parts.filter((row) => row[partAt] !== null && row[partAt] !== "other");
    data.no_family.count = data.no_family.parts.reduce((sum, row) => sum + row[6], 0);
    data.lone.parts = data.lone.parts.filter((row) => row[3] !== null);
    data.lone.count = data.lone.parts.reduce((sum, row) => sum + row[6], 0);
    delete data.shelf_counts; delete data.distinct_families; delete data.families_in_all; delete data.counts;
  } }).data, {});
  const partial = layoutStack(fewer, { margin, step });
  assert.deepEqual(partial.shelves.map((shelf) => [shelf.id, shelf.index]), [["cell", 0], ["er", 1], ["mito", 2], ["nucleus", 3], ["membrane", 5]]);
  assert.equal(partial.apart, null);
  // These shelves hold a few markers each: no width makes the deepest of them keep to a wide screen's shape, and none is stretched for it.
  assert.equal(layoutStack(shelves, { shape: 0.65, margin, step }).limit, 60, "the narrowest stack that does as well as the widest");
});

/**
 * A larger made-up catalogue on six shelves: about `lines` family lines of many sizes, each
 * family on one to three shelves, spread as a curated proteome might be. No members' files.
 */
function madeUpMany(lines = 1400) {
  let state = 20261115;
  const next = () => ((state = (Math.imul(state, 1664525) + 1013904223) >>> 0) / 4294967296);
  const pick = (weights) => {
    let at = next() * weights.reduce((sum, [, weight]) => sum + weight, 0);
    for (const [value, weight] of weights) if ((at -= weight) < 0) return value;
    return weights.at(-1)[0];
  };
  const ON = [["cell", 46], ["nucleus", 28], ["mito", 6], ["er", 5], ["other", 8], ["membrane", 5], [null, 2]];
  const SIDE = { cell: [["in", 24], ["inside", 52], ["outside", 21], ["not known", 3]], nucleus: [["in", 3], ["inside", 94], ["outside", 1], ["not known", 2]], mito: [["in", 28], ["inside", 28], ["outside", 5], ["not known", 39]], er: [["in", 60], ["inside", 15], ["outside", 5], ["not known", 20]], other: [["in", 47], ["inside", 11], ["outside", 16], ["not known", 26]], membrane: [["in", 83], ["outside", 10], ["not known", 7]] };
  const groups = ["channels", "transport", "signalling", "genes", "proteins", "structure", "metabolism", "other"].map((id) => ({ id, label: `District ${id}`, from: "made up" }));
  const rows = [];
  let place = 0, family = 0;
  while (rows.length < lines) {
    family += 1;
    const id = `IPR8${String(family).padStart(5, "0")}`, group = groups[Math.floor(next() * groups.length)].id;
    const size = 1 + Math.floor(60 * next() ** 5 + 3 * next() ** 2);
    const home = pick(ON), onShelves = new Map();
    for (let index = 0; index < size; index++) {
      const shelf = next() < 0.75 ? home : pick(ON);
      const side = shelf === null ? "not known" : pick(SIDE[shelf]);
      if (!onShelves.has(shelf)) onShelves.set(shelf, {});
      onShelves.get(shelf)[side] = (onShelves.get(shelf)[side] || 0) + 1;
    }
    for (const shelf of [...SIX.map((item) => item.id), null]) {
      if (!onShelves.has(shelf)) continue;
      const sides = onShelves.get(shelf), count = Object.values(sides).reduce((sum, n) => sum + n, 0);
      const most = ["in", "outside", "inside", "not known"].reduce((best, side) => ((sides[side] || 0) > (sides[best] || 0) ? side : best), "in");
      rows.push([id, `Family ${family}`, shelf, most, group, count, sides, "members-00.json", [place, (place += count)], []]);
    }
  }
  return {
    format: SHELVES_FORMAT, species: "testcrowd", made: "2026-11-15", made_up: true, from: "A made-up catalogue of many families, for the tests of several shelves.",
    shelves: structuredClone(SIX), groups,
    family_columns: ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units"], families: rows,
    no_family: { label: "No family assigned", count: 0, part_columns: ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at"], parts: [] },
    member_columns: ["id", "label", "gene", "side", "basis", "length", "unit", "marks"], side_notes: {}, marks: {},
    sources: [{ name: "Made-up catalogue", licence: "None needed: invented for the tests", class: "permissive" }],
  };
}

test("several shelves: the stack is as wide as lets its largest shelf be framed alone, whatever the depth of the whole", (t) => {
  const data = madeUpMany();
  assert.deepEqual(validateShelves(data), []);
  const shelves = new Shelves(data, { label: "Test crowd" });
  assert.ok(shelves.total > 4000 && shelves.familyCount < shelves.families.length, `${shelves.total} proteins, ${shelves.familyCount} families in ${shelves.families.length} lines`);
  const stacks = new Map();
  for (const shape of [0.65, 0.8, 1.15, 1.25, 2.4]) {
    const began = performance.now();
    const stack = layoutStack(shelves, { shape, margin: 6, step: 9 });
    const took = performance.now() - began;
    stacks.set(shape, stack);
    // Each shelf, with its own three areas, is no deeper than the screen's shape allows for its width: it can be framed alone.
    for (const shelf of stack.shelves) assert.ok(shelf.depth <= shelf.width * shape + 1e-6, `shape ${shape}: the shelf ${shelf.id} is ${shelf.width.toFixed(0)} by ${shelf.depth.toFixed(0)}`);
    // The whole stack is far deeper than that: it is not what the width is chosen from.
    assert.ok(stack.depth > 2 * stack.width * shape, `shape ${shape}: the whole stack is ${stack.width.toFixed(0)} by ${stack.depth.toFixed(0)}`);
    // The narrowest such: one step narrower, and the deepest shelf would not fit.
    if (stack.limit > 60) {
      const narrower = layoutStack(shelves, { shape, margin: 6, step: 9, limit: stack.limit - 10 });
      assert.ok(narrower.shelves.some((shelf) => shelf.depth > shelf.width * shape), `shape ${shape}: ${stack.limit - 10} would have done`);
    }
    // Every marker once, none on another, every membrane and glass one width.
    const places = stack.shelves.flatMap((shelf) => AREAS.flatMap(([id]) => shelf[id].blocks.flatMap((block) => block.places))).concat(stack.apart.blocks.flatMap((block) => block.places));
    assert.equal(places.length, shelves.markers.length);
    assert.equal(new Set(places.map((place) => place.item.key)).size, places.length);
    for (const shelf of stack.shelves) {
      for (const area of shelf.areas) if (area.id !== "apart") assert.equal(area.width, stack.common + 12);
      for (const [id] of AREAS) for (const block of shelf[id].blocks) for (const [at, a] of block.places.entries()) for (const b of block.places.slice(at + 1)) assert.ok(distance(a, b) >= a.radius + b.radius, `${a.item.key} and ${b.item.key} overlap`);
    }
    const names = stack.shelves.reduce((sum, shelf) => sum + AREAS.reduce((n, [id]) => n + shelf[id].blocks.length, 0), 0) + stack.apart.blocks.length;
    t.diagnostic(`shape ${shape}: ${shelves.total} proteins, ${shelves.markers.length} markers; one width ${stack.common.toFixed(0)} (limit ${stack.limit}); shelves ${stack.shelves.map((shelf) => `${shelf.id} ${shelf.width.toFixed(0)}x${shelf.depth.toFixed(0)}`).join(", ")}; the whole stack ${stack.width.toFixed(0)} by ${stack.depth.toFixed(0)}, ${names} district names; ${took.toFixed(0)} ms`);
  }
  // Wide for a wide screen, narrow and deep for a tall one, as with one shelf.
  assert.ok(stacks.get(0.65).common > stacks.get(2.4).common && stacks.get(0.65).depth < stacks.get(2.4).depth);
  // With several shelves the search of widths goes past where the one-shelf search stops, when the largest shelf needs it.
  const crowd = new Shelves(madeUpMany(9000), {});
  const wide = layoutStack(crowd, { shape: 0.65, margin: 6, step: 9 });
  assert.ok(wide.limit > 320, `limit ${wide.limit} for ${crowd.total} proteins`);
  for (const shelf of wide.shelves) assert.ok(shelf.depth <= shelf.width * 0.65 + 1e-6, `the shelf ${shelf.id} is ${shelf.width.toFixed(0)} by ${shelf.depth.toFixed(0)}`);
  assert.ok(layoutStack(crowd, { shape: 0.65, margin: 6, step: 9, limit: 320 }).shelves.some((shelf) => shelf.depth > shelf.width * 0.65), "at 320, where the one-shelf search stops, its largest shelf would not fit");
  t.diagnostic(`${crowd.total} proteins, ${crowd.markers.length} markers, shape 0.65: limit ${wide.limit}; the largest shelf ${wide.shelves[0].width.toFixed(0)} by ${wide.shelves[0].depth.toFixed(0)}; the whole stack ${wide.width.toFixed(0)} by ${wide.depth.toFixed(0)}`);
});

test("several shelves: the stack stands as one staircase, or as several side by side for a wide screen", () => {
  const shelves = several({ loaded: false });
  const between = 30, gap = 34, drop = 28;
  const stack = layoutStack(shelves, { margin: 6, step: 9, between });
  const near = (a, b) => Math.abs(a - b) < 1e-9;
  // One staircase, in the file's order: each shelf where the layout has it and lower than the one before; what is on no shelf last and lowest.
  const one = arrangeStack(stack, { columns: 1, between, gap, drop });
  assert.equal(one.columns, 1);
  assert.deepEqual(one.shelves.map((at) => [at.id, at.column, at.row, at.x, at.y]), [["cell", 0, 0, 0, 0], ["er", 0, 1, 0, -28], ["mito", 0, 2, 0, -56], ["nucleus", 0, 3, 0, -84], ["other", 0, 4, 0, -112], ["membrane", 0, 5, 0, -140]]);
  for (const [index, at] of one.shelves.entries()) assert.ok(near(at.z, stack.shelves[index].z), at.id);
  assert.deepEqual([one.apart.x, one.apart.y], [0, -168]);
  assert.ok(near(one.apart.z, stack.apart.z) && near(one.depth, stack.depth) && one.width === stack.width);
  // Two staircases side by side: consecutive shelves share one, cut where the deeper of the two is shallowest.
  const two = arrangeStack(stack, { columns: 2, between, gap, drop });
  const deep = (from, to) => stack.shelves.slice(from, to).reduce((sum, shelf) => sum + shelf.depth, 0) + between * (to - from - 1);
  const cut = [1, 2, 3, 4, 5].reduce((best, at) => (Math.max(deep(0, at), deep(at, 6)) < Math.max(deep(0, best), deep(best, 6)) - 1e-9 ? at : best));
  assert.deepEqual(two.shelves.map((at) => at.column), stack.shelves.map((_, index) => (index < cut ? 0 : 1)));
  assert.deepEqual(two.shelves.map((at) => at.row), stack.shelves.map((_, index) => (index < cut ? index : index - cut)));
  for (const [index, at] of two.shelves.entries()) {
    const shelf = stack.shelves[index];
    assert.equal(at.x, (at.column - 0.5) * (stack.width + gap), "the staircases stand side by side");
    assert.ok(near(at.y, -at.row * drop), "each staircase starts at the top and goes down");
    if (at.row === 0) assert.ok(near(at.z + shelf.back, stack.shelves[0].back), "their first shelves share a back edge");
    else assert.ok(near(at.z + shelf.back, two.shelves[index - 1].z + stack.shelves[index - 1].front + between), `${at.id} stands in front of the shelf before it`);
  }
  // What is on no shelf stands in front of both staircases, in the middle, lower than any shelf.
  const fronts = two.shelves.map((at, index) => at.z + stack.shelves[index].front);
  assert.ok(near(two.apart.z - stack.apart.size.depth / 2, Math.max(...fronts) + between));
  assert.deepEqual([two.apart.x, two.apart.y], [0, -Math.max(cut, 6 - cut) * drop]);
  assert.equal(two.width, 2 * stack.width + gap);
  assert.ok(two.depth < one.depth * 0.75, `two staircases are ${two.depth.toFixed(0)} deep, one is ${one.depth.toFixed(0)}`);
  assert.ok(near(two.depth, Math.max(...fronts) + between + stack.apart.size.depth - stack.shelves[0].back));
  // No more staircases than shelves; and with one shelf, it stands where it always has.
  const many = arrangeStack(stack, { columns: 9, between, gap, drop });
  assert.equal(many.columns, 6);
  assert.deepEqual(many.shelves.map((at) => [at.column, at.row, at.y]), [0, 1, 2, 3, 4, 5].map((column) => [column, 0, 0]));
  // How many staircases suit a screen: two on a wide one, one on a narrow or a tall one.
  assert.deepEqual([{ width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 1024, height: 768 }, { width: 390, height: 844 }, { width: 1200, height: 1100 }].map(columnsFor), [2, 2, 1, 1, 1]);
  // What the page opens on: the whole stack, as a map to pick a shelf from; on a narrow window, where that does not read, the first shelf.
  assert.deepEqual([{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }].map(opensFor), ["stack", "stack", "shelf"]);
  const single = layoutStack(small(), { margin: 6, step: 9 });
  assert.deepEqual(arrangeStack(single, { columns: 3, between, gap, drop }), { columns: 1, shelves: [{ id: "cell", column: 0, row: 0, x: 0, y: 0, z: 0 }], apart: null, width: single.width, depth: single.depth, drop });
});

test("several shelves: a shelf is itself a thing that can be chosen", () => {
  const shelves = several();
  const nucleus = shelves.get("own:testcell:s@nucleus:shelf"), none = shelves.get("own:testcell:s@:shelf");
  assert.deepEqual([nucleus.type, nucleus.shelf, nucleus.label, nucleus.count], ["s", "nucleus", "Nuclear envelope", 23]);
  assert.deepEqual([none.type, none.shelf, none.label, none.count], ["s", null, "No place known", 17]);
  assert.deepEqual(parseKey(nucleus.key), { species: "testcell", type: "s", id: "shelf", shelf: "nucleus" });
  assert.deepEqual([...shelves.shelfItems.keys()], ["cell", "er", "mito", "nucleus", "other", "membrane", null]);
  const said = shelves.describe(nucleus.key);
  assert.equal(said.eyebrow, "Test cell proteins: one of 6 shelves");
  assert.equal(said.plain, "A shelf is a membrane: 23 proteins stand against the nuclear envelope, each outside it, in it or inside it, as far as the sources say.");
  assert.deepEqual(Object.fromEntries(said.facts), { Proteins: "23", "Where they sit": "1 protein on the cytoplasmic face of the nuclear envelope; 5 proteins spanning the nuclear envelope; 13 proteins in the nucleus; 4 proteins with no side known, set apart beside it", "Lines of families": "3", "The only member of its family": "2" });
  const apart = shelves.describe(none.key);
  assert.equal(apart.eyebrow, "Test cell proteins on no shelf");
  assert.equal(apart.plain, "17 proteins have no stated place and nothing predicts one. They stand apart from every shelf and are not placed by guess.");
  assert.equal(Object.fromEntries(apart.facts)["Where they sit"], "17 proteins with no place known");
  // A shelf is not a marker: it stands in no district and is behind no count.
  assert.ok(!shelves.markers.some((item) => item.type === "s"));
  // With one shelf there is nothing of the kind.
  assert.equal(small().shelfItems.size, 0);
  assert.equal(small().get("own:testbug:s:shelf"), null);
});

// ---------------------------------------------------------------- several shelves, in the scene

test("several shelves: the scene carries each shelf's id, label and counts, and nothing of a file that breaks their rules", async () => {
  // The made-up file, as it is kept on disk.
  const { summaries, warnings } = readShelves(SEVERAL);
  assert.deepEqual(warnings, []);
  assert.equal(summaries.length, 1);
  const [cell] = summaries;
  assert.deepEqual([cell.id, cell.file, cell.kind, cell.proteins, cell.no_family, cell.parts], ["testcell", "proteins/testcell/shelves.json", "families", 131, 36, 9]);
  assert.deepEqual([cell.families, cell.family_lines], [10, 18], "a family split over shelves is one family: the families, and their lines apart");
  assert.deepEqual([cell.lone, cell.lone_parts], [14, 5], "the proteins that are the only member of their family, and the parts they are listed in");
  assert.deepEqual(cell.counts, { outside: 6, in: 42, inside: 56, "not known": 27 });
  assert.deepEqual(cell.shelves, [
    { id: "cell", label: "Cell membrane", proteins: 48, counts: { outside: 2, in: 15, inside: 31, "not known": 0 } },
    { id: "er", label: "Endoplasmic reticulum membrane", proteins: 7, counts: { outside: 0, in: 5, inside: 2, "not known": 0 } },
    { id: "mito", label: "Mitochondrial inner membrane", proteins: 17, counts: { outside: 1, in: 4, inside: 8, "not known": 4 } },
    { id: "nucleus", label: "Nuclear envelope", proteins: 23, counts: { outside: 1, in: 5, inside: 13, "not known": 4 } },
    { id: "other", label: "Other membranes", proteins: 8, counts: { outside: 0, in: 5, inside: 2, "not known": 1 } },
    { id: "membrane", label: "A membrane, not told which", proteins: 11, counts: { outside: 2, in: 8, inside: 0, "not known": 1 } },
  ]);
  assert.equal(cell.no_shelf, 17);
  assert.deepEqual(cell.members, ["members-00.json", "members-01.json", "members-02.json"]);
  assert.deepEqual(Object.keys(cell).sort(), ["bytes", "counts", "families", "family_lines", "file", "from", "id", "kind", "lone", "lone_parts", "made", "members", "no_family", "no_shelf", "parts", "proteins", "shelves", "sources"], "names, counts and sources: no protein, no family");
  // The page counts the same from the file.
  const shelves = several({ loaded: false });
  assert.deepEqual(cell.shelves.map((shelf) => [shelf.id, shelf.label, shelf.proteins, shelf.counts]), shelves.byShelf.filter((entry) => entry.id !== null).map((entry) => [entry.id, entry.label, entry.proteins, entry.counts]));
  assert.deepEqual([cell.no_shelf, cell.families, cell.family_lines, cell.proteins, cell.counts], [shelves.byShelf.at(-1).proteins, shelves.familyCount, shelves.families.length, shelves.total, shelves.counts]);

  // Files that break the rules of several shelves: each is said, and left out.
  const broken = path.join(folder, "broken-several");
  const at = Object.fromEntries(madeUpSeveral().data.family_columns.map((name, index) => [name, index]));
  const partAt = Object.fromEntries(madeUpSeveral().data.no_family.part_columns.map((name, index) => [name, index]));
  const bad = (name, change) => place(broken, name, madeUpSeveral({ change: (data) => ((data.species = name), change(data)) }).data);
  await bad("sound", () => {});
  await bad("quiet", (data) => (delete data.shelf_counts, delete data.distinct_families));
  await bad("offshelf", (data) => (data.families[0][at.shelf] = "vacuole"));
  await bad("placed", (data) => ((data.families[0][at.shelf] = null), (data.families[0][at.side] = "not known")));
  await bad("onside", (data) => (data.families[7][at.side] = "in"));
  await bad("twice", (data) => (data.families[1][at.shelf] = "cell"));
  await bad("parttwice", (data) => (data.no_family.parts[1][partAt.shelf] = "cell"));
  await bad("miscounted", (data) => (data.shelf_counts.er.in += 1));
  await bad("nowhere", (data) => (data.shelf_counts[NO_SHELF]["not known"] = 2));
  await bad("extra", (data) => (data.shelf_counts.vacuole = { in: 1 }));
  await bad("recount", (data) => (data.distinct_families = 18));
  await bad("sameid", (data) => (data.shelves[1].id = "cell"));
  await bad("whole", (data) => ((data.no_family.parts = []), (data.no_family.file = "members-02.json"), (data.no_family.at = [0, 36])));
  await bad("lonecolumns", (data) => (data.lone.part_columns[3] = "place"));
  await bad("lonecount", (data) => (data.lone.count = 99));
  await bad("loneshelf", (data) => (data.lone.parts[0][3] = "vacuole"));
  await bad("inall", (data) => (data.families_in_all = 10));
  await bad("partcolumns", (data) => (data.no_family.part_columns[partAt.shelf] = "place"));
  // A small catalogue with two shelves: one marker for each protein, each on a shelf or on none.
  const few = (name, change = () => {}) => place(broken, name, madeUpSmall({ change: (data) => ((data.species = name), data.shelves.push({ id: "inner", label: "Inner membrane", outside: "Between the two membranes", inside: "In the inner space" }), change(data)) }));
  await few("twoshelves", (data) => ((data.proteins[3][3] = "inner"), (data.proteins[7][3] = null)));
  await few("outer", (data) => (data.proteins[0][3] = "outer"));
  await few("guessed", (data) => (data.proteins[1][3] = null));
  const read = readShelves(broken);
  assert.deepEqual(read.summaries.map((item) => item.id), ["quiet", "sound", "twoshelves"], "only the sound ones are in the scene");
  assert.deepEqual(read.summaries[0].shelves, read.summaries[1].shelves, "a file that does not state its counts by shelf is counted from its lines");
  const two = read.summaries[2];
  assert.deepEqual([two.kind, two.proteins, two.no_shelf, two.shelves.map((shelf) => [shelf.id, shelf.proteins])], ["proteins", 9, 1, [["cell", 7], ["inner", 1]]]);
  assert.equal(two.families, undefined);
  const said = (name) => read.warnings.find((warning) => warning.startsWith(`species proteins ${name}:`)) || "";
  assert.match(said("offshelf"), /IPR900001: its shelf 'vacuole' is not one of the file's/);
  assert.match(said("placed"), /IPR900001: it is on no shelf, yet a side of it is known/);
  assert.match(said("onside"), /IPR900003: it is on no shelf, yet it stands on a side/);
  assert.match(said("twice"), /IPR900001: the family has two lines on one shelf/);
  assert.match(said("parttwice"), /IPR910001: the part has two lines on one shelf/);
  assert.match(said("miscounted"), /its counts for the shelf er are not those of its lines/);
  assert.match(said("nowhere"), /its counts for the proteins on no shelf are not those of its lines/);
  assert.match(said("extra"), /it counts a shelf that it does not have/);
  assert.match(said("recount"), /it says it has 18 families; its lines are of 10/);
  assert.match(said("sameid"), /its shelves do not each have an id of their own/);
  assert.match(said("whole"), /on several shelves the proteins with no family are given in parts, each on its shelf/);
  assert.match(said("partcolumns"), /the parts of no_family lack a column/);
  assert.match(said("lonecolumns"), /the parts of lone lack a column/);
  assert.match(said("lonecount"), /the parts of lone do not add up to its count/);
  assert.match(said("loneshelf"), /lone-channels-in: its shelf 'vacuole' is not one of the file's/);
  assert.match(said("inall"), /it says it has 10 families in all; its lines and its lone proteins are of 24/);
  assert.match(said("outer"), /TB_001: its shelf 'outer' is not one of the file's/);
  assert.match(said("guessed"), /TB_002: it is on no shelf, yet a side of it is known/);
  assert.equal(read.warnings.length, 18);
  assert.ok(read.warnings.every((warning) => warning.endsWith("left out")));

  // A species with one shelf is summarised as it always was: nothing by shelf.
  const sound = readShelves(path.join(folder, "sound"));
  for (const item of sound.summaries) assert.ok(!("shelves" in item) && !("no_shelf" in item) && !("family_lines" in item), item.id);
  // With one shelf too, a line's shelf is the file's, and a family is listed once.
  const one = path.join(folder, "broken-one");
  await place(one, "stray", madeUpSmall({ change: (data) => ((data.species = "stray"), (data.proteins[0][3] = "elsewhere")) }));
  const doubled = madeUpFamilies().data;
  doubled.species = "doubled";
  doubled.families[1][0] = doubled.families[0][0];
  await place(one, "doubled", doubled);
  const ones = readShelves(one);
  assert.deepEqual(ones.summaries, []);
  assert.match(ones.warnings.join(" | "), /species proteins stray: TB_001: its shelf 'elsewhere' is not one of the file's/);
  assert.match(ones.warnings.join(" | "), /species proteins doubled: IPR000001: the family has two lines on one shelf/);

  // The page builder lists the species' files as for any other: its shelves, then its members.
  const proteinsDir = path.join(folder, "several"), membersDir = path.join(folder, "several-members");
  const { data, memberFiles } = madeUpSeveral();
  await place(proteinsDir, "testcell", data);
  await mkdir(path.join(membersDir, "testcell"), { recursive: true });
  for (const [name, file] of Object.entries(memberFiles)) await writeFile(path.join(membersDir, "testcell", name), JSON.stringify(file));
  const found = await proteinFiles({ proteins: { shelves: readShelves(proteinsDir).summaries } }, { proteinsDir, membersDir, make: false });
  assert.deepEqual(found.problems, []);
  assert.deepEqual(found.files.map((file) => file.path), ["proteins/testcell/shelves.json", "proteins/testcell/members-00.json", "proteins/testcell/members-01.json", "proteins/testcell/members-02.json"]);
});

// The whole build once more, with the made-up species of several shelves beside the inventory.
const builtSeveral = (async () => {
  const proteins = path.join(folder, "build-several");
  await mkdir(path.join(proteins, "testcell"), { recursive: true });
  for (const name of ["inventory.snapshot.json", "overlay.json"]) await writeFile(path.join(proteins, name), await readFile(path.join(PROTEINS, name)));
  await writeFile(path.join(proteins, "testcell", "shelves.json"), JSON.stringify(madeUpSeveral().data));
  const out = path.join(folder, "scene-several.out");
  return new Promise((resolve) => {
    const child = spawn("python3", [path.join(ROOT, "tools", "extract_architecture.py"), "--proteins", proteins, "--out", out], { stdio: ["ignore", "pipe", "pipe"] });
    let said = "";
    child.stdout.on("data", (chunk) => (said += chunk));
    child.stderr.on("data", (chunk) => (said += chunk));
    child.on("close", async (code) => resolve({ code, said, scene: code === 0 ? JSON.parse(await readFile(out, "utf8")) : null }));
  });
})();

test("several shelves: the build puts the shelves' summary in the scene, and the scene still follows its format", async (t) => {
  const { code, said, scene } = await builtSeveral;
  const declined = code !== 0 && !/Traceback/.test(said) ? said.trim().split("\n").at(-1) : null;
  if (declined) return t.skip(`the build did not run: ${declined}`);
  assert.equal(code, 0, said);
  assert.deepEqual(validate(scene), []);
  assert.deepEqual(scene.meta.warnings.filter((warning) => warning.startsWith("species proteins")), []);
  assert.deepEqual(scene.proteins.shelves.map((item) => item.id), ["testcell"]);
  const [cell] = scene.proteins.shelves;
  assert.deepEqual(cell.shelves.map((shelf) => [shelf.id, shelf.proteins]), [["cell", 48], ["er", 7], ["mito", 17], ["nucleus", 23], ["other", 8], ["membrane", 11]]);
  assert.deepEqual([cell.no_shelf, cell.families, cell.family_lines, cell.lone, cell.lone_parts], [17, 10, 18, 14, 5]);
  assert.match(said, /species proteins testcell of 2026-11-15: 131 proteins \(6 outside, 42 in, 56 inside, 27 not known\); 10 families and 36 with none, in 3 files of members/);
  assert.ok(["own", "units"].includes(firstMode(scene.proteins, "testcell")));
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
    // Every marker stands once in the stack of the species' shelves.
    const stack = layoutStack(shelves);
    const areas = [...stack.shelves.flatMap((shelf) => AREAS.map(([id]) => shelf[id])), ...(stack.apart ? [stack.apart] : [])];
    assert.equal(areas.reduce((sum, area) => sum + area.blocks.reduce((total, block) => total + block.places.length, 0), 0), shelves.markers.length, `${summary.id}: every marker stands once`);
    assert.equal(shelves.byShelf.reduce((sum, entry) => sum + entry.proteins, 0), shelves.total, `${summary.id}: every protein is on one shelf or on none`);
    if (shelves.several) {
      // Several shelves: what the scene says of each shelf is what the page counts on it, and every line has a key of its own.
      assert.deepEqual(summary.shelves.map((shelf) => [shelf.id, shelf.label, shelf.proteins, shelf.counts]), shelves.byShelf.filter((entry) => entry.id !== null).map((entry) => [entry.id, entry.label, entry.proteins, entry.counts]), `${summary.id}: the scene's counts by shelf are the page's`);
      assert.equal(summary.no_shelf, shelves.byShelf.find((entry) => entry.id === null)?.proteins ?? 0, `${summary.id}: the proteins on no shelf`);
      if (shelves.kind === "families") assert.deepEqual([summary.families, summary.family_lines], [shelves.familyCount, shelves.families.length], `${summary.id}: its families, and their lines`);
      for (const shelf of shelves.shelves) assert.ok(!/undefined|\bthe (a|an|the) /i.test(JSON.stringify(shelves.sideWords(shelf.id))), `${summary.id}: the words of the shelf ${shelf.id} read ill: ${shelves.sideWords(shelf.id).in.short}`);
    } else {
      // One shelf: the stack is the one-shelf layout, place for place; no key carries a shelf; the scene says nothing by shelf.
      sameAsOneShelf(shelves, summary.id);
      for (const key of shelves.byKey.keys()) assert.ok(key.startsWith(`own:${summary.id}:`) && /^own:[^:]+:[a-z]:/.test(key), `${summary.id}: the key ${key}`);
      assert.ok(!("shelves" in summary) && !("no_shelf" in summary), `${summary.id}: a species with one shelf is summarised as it always was`);
    }
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
    const allowed = ["www.uniprot.org", "parasite.wormbase.org", "www.ebi.ac.uk", "www.ncbi.nlm.nih.gov", "www.proteinatlas.org"];
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
    t.diagnostic(`${summary.id}: ${shelves.total} proteins, ${shelves.markers.length} markers (${shelves.kind}), ${shelves.several ? `${stack.shelves.length} shelves, ` : ""}${stack.width.toFixed(0)} by ${stack.depth.toFixed(0)}`);
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
    const files = found.files.filter((file) => file.species === summary.id && !file.path.endsWith("shelves.json") && !file.path.endsWith(NAMES_FILE));
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
    // A member that would make one of Cells' units names a unit of the inventory.
    const withUnit = [...seen].length && shelves.markers.flatMap((marker) => shelves.membersOf(marker)).filter((member) => member.units.length);
    for (const member of withUnit) for (const unit of member.units) assert.ok(UNITS.has(unit), `${member.id}: ${unit}`);
    t.diagnostic(`${summary.id}: ${files.length} files of members, ${(bytes / 1024 / 1024).toFixed(2)} MB; the largest that opens is ${largest.label} with ${largest.count}; ${withUnit.length} members would make one of Cells' units`);
    // Beside them, the names of every member (one file for each large catalogue), each leading to the line it stands on.
    const listed = found.files.filter((file) => file.species === summary.id && file.path.endsWith(NAMES_FILE));
    assert.equal(listed.length, 1, `${summary.id}: one file of names beside the members`);
    const names = JSON.parse(await readFile(listed[0].source, "utf8"));
    shelves.addNames(names);
    assert.equal(shelves.names.length, shelves.total, `${summary.id}: a name for every protein`);
    for (const name of shelves.names) {
      const line = shelves.lineOfName(name);
      assert.ok(line && shelves.membersOf(line).some((member) => member.id === name.id), `${summary.id}: ${name.id} leads to its own line`);
    }
  }
});

test("the search finds a protein by its gene inside a family that is not open, a family by its name, and a shelf", async () => {
  const proteinsDir = path.join(folder, "several"), membersDir = path.join(folder, "several-members");
  await proteinFiles({ proteins: { shelves: readShelves(proteinsDir).summaries } }, { proteinsDir, membersDir }); // the names file is written beside the members
  const { data } = madeUpSeveral();
  const shelves = new Shelves(data, {});
  const before = shelves.search("tgm");
  assert.equal(before.namesMissing, true, "before the names are in, the search says it finds families only");
  shelves.addNames(JSON.parse(await readFile(path.join(membersDir, "testcell", NAMES_FILE), "utf8")));
  const member = shelves.names[3];
  const found = shelves.search(member.id);
  assert.equal(found.proteins[0].id, member.id, "a member is found by its identifier");
  assert.equal(found.proteins[0].line, shelves.lineOfName(member));
  assert.ok(!found.namesMissing);
  const family = shelves.families[0];
  assert.ok(shelves.search(family.label).families.includes(family), "a family's line is found by its name");
  assert.ok(shelves.search(shelves.shelves[0].label).shelves.length >= 1, "a shelf is found by its name");
  assert.equal(shelves.search("a"), null, "one letter finds nothing yet");
});

test("the human's entries that the inventory names only as going with a machine are drawn plain, with their roles", () => {
  const data = JSON.parse(readFileSync(path.join(PROTEINS, "human", "shelves.json"), "utf8"));
  const shelves = new Shelves(data, { units: UNITS });
  const roles = data.inventory_roles;
  assert.ok(roles && Object.keys(roles.proteins).length === 27, "the 27 entries whose every role goes with the machine");
  for (const [id, said] of Object.entries(roles.proteins)) assert.ok(said.length && said.every((role) => /auxiliary/.test(role) || ["beta", "uniplex", "FXYD", "FXYD (gamma)"].includes(role)), `${id}: ${said}`);
  for (const id of ["Q07699", "P05026", "Q9BPX6", "O00168"]) assert.ok(shelves.goesWithOnly({ type: "p", id, units: ["U01"] }), `${id} goes with the machine`);
  assert.ok(!shelves.goesWithOnly({ type: "p", id: "Q99250", units: ["U01"] }), "SCN2A, the pore, still makes it");
  for (const id of roles.families) assert.ok(shelves.goesWithOnly({ type: "f", id, units: ["U01"] }), `${id}: a family of only such entries is drawn plain`);
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
  // A species held back from the picture for now (the map's overlay, `species_held`) keeps its files, and the scene carries none of it.
  const held = new Set(Object.keys(JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8")).species_held || {}));
  assert.deepEqual(scene.proteins.shelves.map((item) => item.id), [...own].filter((id) => !held.has(id)).sort());
  for (const item of scene.proteins.shelves) {
    assert.match(said, new RegExp(`species proteins ${item.id} of \\d{4}-\\d{2}-\\d{2}: [\\d,]+ proteins`));
    assert.equal(item.file, `proteins/${item.id}/shelves.json`);
    // Of a source: its name, its class and what it came through. Its licence in full, what it holds and how it is cited are in the species' file.
    assert.ok(item.sources.length > 0 && item.sources.every((source) => source.name && source.class && Object.keys(source).every((key) => ["name", "class", "through"].includes(key))), item.id);
    assert.ok(JSON.stringify(item).length < 3000, `${item.id}: a species' summary stays under 3,000 characters (names and counts: the proteins and the sources in full are beside the page)`);
  }
  assert.ok(!MACHINE.test(JSON.stringify([scene.proteins.shelves, scene.proteins.shelf_links])), "a machine path leaked into the scene");
  assert.ok(!JSON.stringify(scene.proteins.shelf_links).includes("checked"));
  for (const [key, patterns] of Object.entries(scene.proteins.shelf_links)) {
    for (const pattern of [].concat(patterns)) {
      assert.equal(new URL(pattern.url.replaceAll("{id}", "X")).protocol, "https:", key);
      // The address is made from the identifier; the words may name the database alone.
      assert.ok(pattern.text && pattern.url.includes("{id}"), key);
    }
  }
  // The page then finds, for each species, which of the two it opens on.
  for (const item of scene.proteins.shelves) assert.ok(["own", "units"].includes(firstMode(scene.proteins, item.id)));
  const files = await proteinFiles(scene, { membersDir: path.join(folder, "cut") });
  assert.deepEqual(files.problems, []);
  assert.ok(files.files.length <= 80, `${files.files.length} files beside the page: a version holds at most 511, a publish sends 255 at a time, and the runs need theirs`);
});
