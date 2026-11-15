// The species switch of the protein atlas. A species file is held to its contract
// (schema/SPECIES_ATLAS.md) when the scene is built; the scene carries one atlas for each
// species; and the view shows a unit as the chosen species' atlas has it, while the unit,
// its form and the engine's laws stay as they are.
//
// The species used here is made up, in a temporary folder: no test depends on a species
// file of the repository. The repository's own files, if there are any, are held to the
// contract at the end. Nothing needs a browser.
//
//   node --test tests/species_switch.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { copyFile, mkdir, mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { validate } from "../src/scene/model.js";
import { css } from "../src/ui/styles.js";
import { findingMark } from "../src/lenses/protein_parts.js";
import { atlasOf, defaultAtlas, inSpecies, quietAtlas, speciesWords } from "../src/lenses/proteins.js";

const SNAPSHOT = path.join(ROOT, "data", "proteins", "inventory.snapshot.json");
const OVERLAY = path.join(ROOT, "data", "proteins", "overlay.json");
const snapshot = JSON.parse(await readFile(SNAPSHOT, "utf8"));
const overlay = JSON.parse(await readFile(OVERLAY, "utf8"));
const contract = await readFile(path.join(ROOT, "schema", "SPECIES_ATLAS.md"), "utf8");
const UNITS = snapshot.units.map((unit) => unit.id);
// A unit the overlay flags as left out of the picture for now (`left_out`): every file keeps its
// entry for it, and the page neither draws nor counts it. DRAWN are the others.
const LEFT_OUT = UNITS.filter((id) => overlay.units[id]?.left_out);
const DRAWN = UNITS.filter((id) => !overlay.units[id]?.left_out);
/** The line every atlas adds to how it was made, where a unit is left out. */
const LEFT_OUT_LINE = /^The inventory has \d+ units\. \w+ of them, .+, (?:is|are) left out of the picture for now: .+\. The \d+ others are shown and counted here\.$/;
const FINDINGS = overlay.species.findings.map((word) => word.id);
const EVIDENCE = overlay.species.evidence.map((word) => word.id);
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;

// ---------------------------------------------------------------- a made-up species

// Three units are special; every other unit is found, with one product that all of them share.
const OTHER = "U37", NONE = "U21", LUMPED = "U35";

function madeUp(change = () => {}) {
  const units = {};
  for (const id of UNITS) {
    units[id] = {
      finding: "found",
      note: null,
      products: [{ name: `Test protein of ${id}`, gene: null, role: null, ids: [{ db: "uniprot", id: "A0A000000" }], length: 1400, evidence: "similarity search", evidence_note: "best match to the human candidate", citation: null }],
    };
  }
  units[OTHER] = {
    finding: "different family",
    note: "The test worm has no connexins; its junction channels are innexins.",
    products: [
      { name: "Innexin", gene: "inx-1", role: "subunit", ids: [{ db: "Worm Base", id: "WB0001" }], length: 412, evidence: "named in a publication", evidence_note: null, citation: { text: "A. Author (2000). A made-up paper.", doi: "https://doi.org/10.1000/made-up", pmid: 12345 } },
      { name: "Innexin-like", gene: null, role: null, ids: [{ db: "uniprot", id: "A0A000001" }, { db: "pdb", id: "1ABC" }], length: 398, evidence: "family signature", evidence_note: "carries the innexin signature", citation: null },
      { name: "Curated innexin", gene: "inx-2", role: null, ids: [{ db: "uniprot", id: "P00001" }], length: 405, evidence: "reviewed entry", evidence_note: null, citation: null },
    ],
  };
  units[NONE] = { finding: "none found", note: "A search by family signature found nothing.", products: [] };
  units[LUMPED] = { finding: "nothing to look for", note: "A lumped permeability.", products: [] };
  const data = {
    format: "cells.visualizer.species_atlas@1",
    species: { id: "testworm", label: "Test worm", organism: "Vermis probatus", taxon: 1, plain: "A made-up animal, for the tests." },
    made: "2026-11-14",
    method: ["Made up for the tests."],
    sources: [
      { name: "UniProt", url: "https://www.uniprot.org/", release: "2026_04", accessed: "2026-11-14", licence: "CC BY 4.0", cite: "made up", holds: "nothing" },
      { name: "Worm Base", url: "https://worms.example/", accessed: "2026-11-14", licence: "CC0 1.0", holds: "nothing" },
    ],
    not_copied: "Nothing was read.",
    units,
    // Named with another spelling of the same database, to check that names are compared loosely.
    extra: [{ name: "Spare protein", gene: null, role: null, ids: [{ db: "wormbase", id: "WB0002" }], length: 100, evidence: "similarity search", evidence_note: null, citation: null, why: "It bears on the picture but makes no unit." }],
  };
  change(data);
  return data;
}

// The builder's reader of species files runs on its own, without reading a checkout.
const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib.protein_atlas import Species, read_species_files
snapshot = json.load(open(sys.argv[2], encoding="utf-8"))
overlay = json.load(open(sys.argv[3], encoding="utf-8"))
request = json.load(sys.stdin)
files = read_species_files(request["folder"]) if "folder" in request else [tuple(item) for item in request["files"]]
species = Species(snapshot, overlay, files)
print(json.dumps({"warnings": species.warnings, "remarks": species.remarks, "atlases": species.summary(), "units": {unit: species.of_unit(unit) for unit in species.unit_ids}}))
`;

function read(request, overlayFile = OVERLAY) {
  const run = spawnSync("python3", ["-c", READER, path.join(ROOT, "tools"), SNAPSHOT, overlayFile], { input: JSON.stringify(request), encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  return JSON.parse(run.stdout);
}
const readOne = (data, name = "testworm") => read({ files: [[name, data, null]] });

// The whole build, once, with the made-up species in a folder of its own. It runs while the
// quick checks do. It reads a checkout: where there is none, or the build declines it for a
// reason of its own, the two checks on it are skipped. A build that crashes is a failure.
const folder = await mkdtemp(path.join(os.tmpdir(), "cells-species-"));
await writeFile(path.join(folder, "testworm.json"), JSON.stringify(madeUp()));
const built = new Promise((resolve) => {
  const out = path.join(folder, "scene.out");
  const child = spawn("python3", [path.join(ROOT, "tools", "extract_architecture.py"), "--atlases", folder, "--out", out], { stdio: ["ignore", "pipe", "pipe"] });
  let said = "";
  child.stdout.on("data", (chunk) => (said += chunk));
  child.stderr.on("data", (chunk) => (said += chunk));
  child.on("close", async (code) => resolve({ code, said, scene: code === 0 ? JSON.parse(await readFile(out, "utf8")) : null }));
});
test.after(() => rm(folder, { recursive: true, force: true }));
/** Why the build did not run, if it declined in so many words; null if it ran or crashed. */
const declined = ({ code, said }) => (code !== 0 && !/Traceback/.test(said) ? said.trim().split("\n").at(-1) : null);

// What the overlays flag as left out of the picture comes back when the flag is taken off. A
// second build, with both overlays copied without their flags, runs beside the first.
const MAP = path.join(ROOT, "data", "architecture", "overlay.json");
const map = JSON.parse(await readFile(MAP, "utf8"));
const LEFT_OUT_PARTS = map.capabilities.filter((capability) => capability.left_out);
const aside = await mkdtemp(path.join(os.tmpdir(), "cells-leftout-"));
test.after(() => rm(aside, { recursive: true, force: true }));
const unflagged = { map: structuredClone(map), atlas: structuredClone(overlay) };
for (const capability of unflagged.map.capabilities) delete capability.left_out;
// A species held back from the picture is flagged in the map's overlay too: with the flag off it is a species again.
delete unflagged.map.species_held;
for (const unit of Object.values(unflagged.atlas.units)) delete unit.left_out;
const UNFLAGGED_OVERLAY = path.join(aside, "proteins", "overlay.json");
await mkdir(path.join(aside, "proteins"));
await writeFile(UNFLAGGED_OVERLAY, JSON.stringify(unflagged.atlas));
await copyFile(SNAPSHOT, path.join(aside, "proteins", "inventory.snapshot.json"));
await writeFile(path.join(aside, "map.json"), JSON.stringify(unflagged.map));
const builtUnflagged =
  LEFT_OUT.length || LEFT_OUT_PARTS.length
    ? new Promise((resolve) => {
        const out = path.join(aside, "scene.out");
        const child = spawn(
          "python3",
          [path.join(ROOT, "tools", "extract_architecture.py"), "--overlay", path.join(aside, "map.json"), "--proteins", path.join(aside, "proteins"), "--atlases", path.join(ROOT, "data", "proteins", "atlases"), "--out", out],
          { stdio: ["ignore", "pipe", "pipe"] }
        );
        let said = "";
        child.stdout.on("data", (chunk) => (said += chunk));
        child.stderr.on("data", (chunk) => (said += chunk));
        child.on("close", async (code) => resolve({ code, said, scene: code === 0 ? JSON.parse(await readFile(out, "utf8")) : null }));
      })
    : null;

const sound = readOne(madeUp());
const species = sound.atlases[1];
/** The scene's protein block, as far as the view's words need it. */
const proteins = { stamp: { created: snapshot.inventory.created }, atlases: sound.atlases, findings: overlay.species.findings, product_evidence: overlay.species.evidence, no_entry: overlay.species.no_entry };
const items = (unit) => sound.units[unit].testworm.items;

// ---------------------------------------------------------------- the contract, at build time

test("the vocabulary is the contract's: four findings and four kinds of evidence", () => {
  assert.equal(FINDINGS.length, 4);
  assert.equal(EVIDENCE.length, 4);
  for (const word of [...FINDINGS, ...EVIDENCE]) assert.ok(contract.includes(`\`${word}\``), `the contract does not have the word '${word}'`);
  assert.ok(contract.includes(overlay.species.format), "the format the builder asks for is the contract's");
});

test("a species file that holds to the contract raises nothing", () => {
  assert.deepEqual(sound.warnings, []);
  assert.deepEqual(sound.remarks, []);
  assert.deepEqual(sound.atlases.map((atlas) => atlas.id), ["human", "testworm"]);
  assert.equal(species.label, "Test worm");
  assert.equal(species.organism, "Vermis probatus");
  assert.equal(species.reference, undefined);
});

test("a species atlas counts its own units and products, a shared product once", () => {
  const counts = species.counts;
  assert.equal(counts.units, DRAWN.length, "the units the page draws");
  assert.equal(counts.with_products, DRAWN.length - 2, "all but the unit with nothing found and the lumped one");
  assert.equal(counts.products, 4, "the product every found unit shares is one product");
  assert.equal(counts.candidates, 2, "the two found by signature or similarity");
  assert.equal(species.findings.reduce((sum, item) => sum + item.count, 0), DRAWN.length, "every unit drawn has one finding");
  assert.deepEqual(species.findings.map((item) => item.id), FINDINGS);
  assert.deepEqual(Object.fromEntries(species.findings.map((item) => [item.id, item.count])), { found: DRAWN.length - 3, "different family": 1, "none found": 1, "nothing to look for": 1 });
  assert.deepEqual(species.evidence.map((item) => item.count), [1, 1, 1, 1]);
  assert.equal(species.extra.length, 1);
  assert.equal(species.extra[0].note, "It bears on the picture but makes no unit.");
});

test("the human atlas is the inventory's own, and states no finding", () => {
  const human = sound.atlases[0];
  assert.equal(human.id, "human");
  assert.equal(human.reference, true);
  assert.equal(human.findings, undefined, "the snapshot states no findings");
  assert.equal(human.made, snapshot.inventory.created);
  assert.deepEqual(human.sources, snapshot.sources);
  assert.equal(human.counts.products, snapshot.inventory.counts.candidate_genes);
  assert.equal(human.counts.units, snapshot.inventory.counts.functional_units - LEFT_OUT.length, "the units the page draws");
  for (const unit of UNITS) assert.equal(sound.units[unit].human, undefined, "a unit's human candidates stay in its own sections");
});

const BROKEN = [
  ["a missing unit", (data) => delete data.units.U05, new RegExp(`it has no entry for 1 of the inventory's ${UNITS.length} units: U05`)],
  ["a unit the inventory does not have", (data) => (data.units.U99 = { finding: "found", products: [] }), /it names units the inventory does not have: U99/],
  ["an unknown word for a finding", (data) => (data.units.U01.finding = "present"), /U01: unknown finding 'present'/],
  ["an unknown word for evidence", (data) => (data.units.U01.products[0].evidence = "orthology"), /U01: unknown evidence 'orthology'/],
  ["a publication without its citation", (data) => (data.units[OTHER].products[0].citation = null), /U37: inx-1 is named in a publication, but has no citation/],
  ["a citation without its text", (data) => (data.units[OTHER].products[1].citation = { doi: "10.1/x" }), /the citation on Innexin-like has no text/],
  ["a database the sources do not list", (data) => (data.units.U01.products[0].ids = [{ db: "planmine", id: "x" }]), /it names the database 'planmine' \(1 times, first on U01/],
  ["a web address in place of an id", (data) => (data.units.U01.products[0].ids = [{ db: "uniprot", id: "https://www.uniprot.org/uniprotkb/P1" }]), /an id on Test protein of U01 is a web address/],
  ["a web address on a product", (data) => (data.units.U01.products[0].url = "https://example.org/"), /Test protein of U01 holds a web address/],
  ["a machine path", (data) => (data.not_copied = "see /home/someone/notes"), /it holds a machine path/],
  ["a missing date and method", (data) => (delete data.made, (data.method = [])), /it lacks: made \(a date\), method/],
  ["a source without its licence", (data) => delete data.sources[1].licence, /its source Worm Base lacks: licence/],
  ["a species id that is not the file's name", (data) => (data.species.id = "worm"), /its species id is 'worm', but the file is named testworm\.json/],
];

test("what breaks the contract is warned about, so a strict build fails", () => {
  for (const [what, change, expected] of BROKEN) {
    const { warnings, atlases } = readOne(madeUp(change));
    assert.ok(warnings.some((warning) => expected.test(warning)), `${what}: ${JSON.stringify(warnings)}`);
    assert.ok(warnings.every((warning) => warning.startsWith("species atlas testworm: ")), `${what}: every warning names its file`);
    assert.equal(atlases.length, 2, `${what}: what is sound in the file is still shown`);
  }
});

test("what was warned about is left out of the scene", () => {
  const unknown = readOne(madeUp((data) => (data.units.U01.finding = "present")));
  assert.deepEqual(unknown.units.U01.testworm, { finding: null, note: null, items: [] });
  const uncited = readOne(madeUp((data) => (data.units[OTHER].products[0].citation = null)));
  assert.deepEqual(uncited.units[OTHER].testworm.items.map((item) => item.label), ["Innexin-like", "inx-2"]);
});

test("a source's address is linked only if it is https", () => {
  // The contract sets no rule on the address, so this is a remark; the address is left out all the same.
  for (const address of ["http://worms.example/", "javascript:alert(1)"]) {
    const { warnings, remarks, atlases, units } = readOne(madeUp((data) => (data.sources[1].url = address)));
    assert.deepEqual(warnings, []);
    assert.ok(remarks.some((remark) => /its source Worm Base has an address that is not https, so it is named but not linked/.test(remark)), JSON.stringify(remarks));
    assert.equal(atlases[1].sources[1].url, undefined);
    assert.equal(atlases[1].sources[1].name, "Worm Base");
    assert.ok(!JSON.stringify([atlases, units]).includes(address));
    // Its entries are still named, as text.
    assert.ok(units[OTHER].testworm.items[0].lines.includes("Worm Base: WB0001"));
    assert.deepEqual(units[OTHER].testworm.items[0].links.map((link) => link.text), ["Paper", "PubMed"]);
  }
});

test("a file that cannot be shown is left out with one warning, and never stops the build", async () => {
  const wrong = readOne(madeUp((data) => (data.format = "something@1")));
  assert.deepEqual(wrong.atlases.map((atlas) => atlas.id), ["human"]);
  assert.match(wrong.warnings[0], /left out, its format is 'something@1'/);
  assert.match(readOne([1, 2]).warnings[0], /left out, its format is 'list'/);
  assert.match(readOne(madeUp((data) => (data.species.id = "human")), "human").warnings[0], /left out, the species id 'human' is already taken/);
  const twice = read({ files: [["testworm", madeUp(), null], ["testworm2", madeUp(), null]] });
  assert.deepEqual(twice.atlases.map((atlas) => atlas.id), ["human", "testworm"]);
  assert.match(twice.warnings[0], /species atlas testworm2: left out, the species id 'testworm' is already taken/);

  // A file another agent is still writing, and one that is not text at all.
  const partial = await mkdtemp(path.join(os.tmpdir(), "cells-species-partial-"));
  try {
    await writeFile(path.join(partial, "half.json"), JSON.stringify(madeUp()).slice(0, 4000));
    await writeFile(path.join(partial, "noise.json"), Buffer.from([0xff, 0xfe, 0x00, 0x01]));
    await writeFile(path.join(partial, "notes.txt"), "not a species file");
    const { warnings, atlases } = read({ folder: partial });
    assert.deepEqual(atlases.map((atlas) => atlas.id), ["human"]);
    assert.equal(warnings.length, 2);
    for (const warning of warnings) assert.match(warning, /^species atlas (half|noise): left out, the file could not be read as JSON/);
  } finally {
    await rm(partial, { recursive: true, force: true });
  }
  // No folder at all: the inventory's own atlas, and nothing to say.
  const none = read({ folder: path.join(folder, "no-such-folder") });
  assert.deepEqual(none.atlases.map((atlas) => atlas.id), ["human"]);
  assert.deepEqual(none.warnings, []);
  assert.deepEqual(none.units.U01, {});
});

test("a file with very many problems names the first and counts the rest", () => {
  const { warnings } = readOne(madeUp((data) => Object.values(data.units).forEach((unit) => (unit.finding = "present"))));
  assert.equal(warnings.length, 13);
  assert.match(warnings.at(-1), new RegExp(`and ${UNITS.length - 12} more problems$`));
});

test("what is within the contract's letter but looks wrong is remarked on, not warned about", () => {
  const { warnings, remarks } = readOne(
    madeUp((data) => {
      data.units.U01.products = [];
      data.units[NONE].note = null;
      data.units[LUMPED].products = [{ name: "Odd one", evidence: "reviewed entry", ids: [{ db: "uniprot", id: "P00002" }] }];
      delete data.extra[0].why;
    })
  );
  assert.deepEqual(warnings, []);
  for (const expected of [/U01 is 'found' but lists no product/, /U21 is 'none found' without a note/, /U35 is 'nothing to look for' but lists 1 products/, /extra: Spare protein has no 'why'/]) {
    assert.ok(remarks.some((remark) => expected.test(remark)), `${expected}: ${JSON.stringify(remarks)}`);
  }
});

// ---------------------------------------------------------------- what the panel lists

test("each product states its evidence in the contract's words", () => {
  const labels = new Map(overlay.species.evidence.map((word) => [word.label, word]));
  for (const unit of UNITS) {
    for (const item of items(unit)) {
      const word = labels.get(item.tag);
      assert.ok(word, `${unit}: ${item.label} carries the tag '${item.tag}'`);
      assert.equal(item.tag_title, word.description);
    }
  }
  assert.deepEqual(items(OTHER).map((item) => item.tag), ["Named in a publication", "Family signature", "Reviewed entry"]);
});

test("a product found by signature or similarity is called a candidate, and no other is", () => {
  const candidate = /^Candidate, not an established counterpart/;
  const [published, signature, reviewed] = items(OTHER);
  assert.ok(signature.lines.some((line) => candidate.test(line)), "found by signature");
  assert.ok(items("U01")[0].lines.some((line) => candidate.test(line)), "found by similarity");
  assert.ok(signature.lines.includes("Candidate, not an established counterpart: carries the innexin signature"), "the file's words, as written");
  for (const item of [published, reviewed]) assert.ok(!item.lines.some((line) => /candidate/i.test(line)), `${item.label} is not a candidate`);
  for (const word of overlay.species.evidence) {
    assert.equal(/A candidate, not an established counterpart\.$/.test(word.description), Boolean(word.candidate), `${word.id}: the description says whether it is a candidate`);
  }
});

test("links are built from ids and citations, never read from the file", () => {
  const [published, signature, reviewed] = items(OTHER);
  assert.deepEqual(signature.links, [
    { text: "UniProt A0A000001", url: "https://www.uniprot.org/uniprotkb/A0A000001/entry" },
    { text: "PDB 1ABC", url: "https://www.rcsb.org/structure/1ABC" },
  ]);
  assert.deepEqual(reviewed.links, [{ text: "UniProt P00001", url: "https://www.uniprot.org/uniprotkb/P00001/entry" }]);
  // A species database: the contract gives its address, not the address of an entry. The id is text.
  assert.ok(published.lines.includes("Worm Base: WB0001"));
  assert.deepEqual(published.links, [
    { text: "Worm Base", url: "https://worms.example/" },
    { text: "Paper", url: "https://doi.org/10.1000/made-up" },
    { text: "PubMed", url: "https://pubmed.ncbi.nlm.nih.gov/12345/" },
  ]);
  assert.ok(published.lines.includes("A. Author (2000). A made-up paper."));
  assert.equal(published.label, "inx-1");
  assert.equal(published.detail, "Innexin, subunit");
  assert.ok(signature.lines.includes("398 amino acids"));
  assert.ok(items("U01")[0].lines.includes("1,400 amino acids"));

  const allowed = new Set(["www.uniprot.org", "www.rcsb.org", "doi.org", "pubmed.ncbi.nlm.nih.gov", ...madeUp().sources.map((source) => new URL(source.url).hostname)]);
  let count = 0;
  for (const item of [...UNITS.flatMap(items), ...species.extra]) {
    for (const link of item.links) {
      count += 1;
      const url = new URL(link.url);
      assert.equal(url.protocol, "https:");
      assert.ok(allowed.has(url.hostname), `${item.label}: ${link.url}`);
    }
  }
  assert.ok(count > UNITS.length - 3);
  assert.ok(sound.units[OTHER].testworm.keywords.includes("inx-1") && sound.units[OTHER].testworm.keywords.includes("WB0001"), "a unit can be found by its species' products");
});

test("an entry of a species' database is linked where the overlay holds a checked address for that species", async () => {
  const other = structuredClone(overlay);
  other.species.entries = { testworm: { wormbase: { text: "Worm Base {id}", url: "https://worms.example/gene/{id}" } } };
  const file = path.join(folder, "overlay-with-entries.txt");
  await writeFile(file, JSON.stringify(other));
  const linked = read({ files: [["testworm", madeUp(), null]] }, file);
  assert.deepEqual(linked.warnings, []);
  const [published] = linked.units[OTHER].testworm.items;
  assert.deepEqual(published.links[0], { text: "Worm Base WB0001", url: "https://worms.example/gene/WB0001" });
  assert.ok(!published.lines.some((line) => line.startsWith("Worm Base:")), "the id is in the link, not said twice");
  assert.deepEqual(linked.atlases[1].extra[0].links, [{ text: "Worm Base WB0002", url: "https://worms.example/gene/WB0002" }]);
  // The pattern belongs to one species: another species that names the same database gets the plain form.
  const elsewhere = read({ files: [["otherworm", madeUp((data) => (data.species.id = "otherworm")), null]] }, file);
  assert.ok(elsewhere.units[OTHER].otherworm.items[0].lines.includes("Worm Base: WB0001"));
  // Every pattern the repository's overlay holds is https, has a place for the id, and says when it was checked.
  for (const [who, patterns] of Object.entries(overlay.species.entries || {})) {
    for (const [database, pattern] of Object.entries(patterns)) {
      assert.ok(/^https:\/\/[^{]+\{id\}/.test(pattern.url) && pattern.text.includes("{id}") && pattern.checked, `${who}: ${database}`);
    }
  }
});

test("under a gene's name stand the protein's name and role, unless one only repeats the other", () => {
  const detail = (product) => readOne(madeUp((data) => (data.units[OTHER].products = [{ ids: [{ db: "uniprot", id: "P00009" }], evidence: "reviewed entry", ...product }]))).units[OTHER].testworm.items[0];
  assert.deepEqual([detail({ gene: "inx-1", name: "Innexin", role: "innexin" }).label, detail({ gene: "inx-1", name: "Innexin", role: "innexin" }).detail], ["inx-1", "Innexin"]);
  assert.equal(detail({ gene: "scna-1", name: "Scna-1", role: "alpha" }).detail, "alpha");
  assert.equal(detail({ gene: "atp-1", name: "Pump alpha subunit", role: "alpha" }).detail, "Pump alpha subunit");
  assert.equal(detail({ gene: null, name: "Innexin, gene model X1", role: "innexin" }).detail, null);
  assert.equal(detail({ gene: null, name: "Innexin, gene model X1", role: "innexin" }).label, "Innexin, gene model X1");
  assert.equal(detail({ gene: "inx-1", name: "Innexin", role: "subunit" }).detail, "Innexin, subunit");
});

// ---------------------------------------------------------------- what the view shows

/** A unit as the scene carries it: the inventory's side in its own fields, each species' side under "species". */
function unitPart(id) {
  return {
    id: `unit.${id}`,
    label: `Unit ${id}`,
    kind: "unit",
    group: "proteins",
    mapping: "assigned",
    swatch: "map-assigned",
    evidence: ["expressed isoform"],
    form: { shape: "junction", subunits: 6, style: "solid" },
    chips: [{ label: "Assigned in source", swatch: "map-assigned" }, { label: "Between two cells" }],
    facts: [["Assembly", "2 x 6"]],
    sections: [
      { key: "laws", title: "Engine laws", items: [{ label: "a_law@1", code: true }] },
      { key: "products", title: "Candidate products", items: [{ label: "GJC1", links: [{ text: "UniProt P36383", url: "https://www.uniprot.org/uniprotkb/P36383/entry" }] }] },
      { key: "structures", title: "Reference structures", items: [{ label: "PDB 7XYZ" }] },
    ],
    keywords: "a_law@1 GJC1",
    species: sound.units[id],
  };
}

test("the view opens on the inventory's own atlas, and a scene without atlases is shown as before", () => {
  assert.equal(defaultAtlas(proteins), "human");
  assert.equal(atlasOf(proteins, "testworm").label, "Test worm");
  assert.equal(atlasOf(proteins, "nowhere"), null);
  assert.equal(defaultAtlas({}), null);
  assert.equal(defaultAtlas(undefined), null);
  const unit = unitPart(OTHER);
  assert.equal(inSpecies(unit, {}, null), unit);
  assert.equal(inSpecies(unit, proteins, "nowhere"), unit);
});

test("in the human atlas a unit is the scene's own part, untouched", () => {
  const unit = unitPart(OTHER);
  assert.equal(inSpecies(unit, proteins, "human"), unit);
});

test("in another species a unit keeps its laws, mapping and form, and lists that species' products", () => {
  const unit = unitPart(OTHER);
  const before = structuredClone(unit);
  const shown = inSpecies(unit, proteins, "testworm");
  assert.deepEqual(unit, before, "the scene's part is not changed");
  // What the engine's law names is the same in every atlas.
  for (const key of ["id", "label", "kind", "mapping", "swatch", "evidence", "form", "facts"]) assert.deepEqual(shown[key], unit[key], key);
  assert.deepEqual(shown.sections.map((section) => section.key), ["laws", "products", "structures"]);
  const [laws, products, structures] = shown.sections;
  assert.deepEqual(laws.items, unit.sections[0].items);
  assert.equal(laws.note, "The same laws for every species.");
  assert.equal(products.title, "Test worm gene products");
  assert.deepEqual(products.items, items(OTHER));
  assert.ok(!JSON.stringify(products).includes("GJC1"), "the inventory's human candidates are not listed as the species' own");
  assert.deepEqual(structures, unit.sections[2]);
  // The finding, plainly, with the file's note and what still belongs to the family the law names.
  const word = overlay.species.findings.find((item) => item.id === "different family");
  assert.deepEqual(shown.finding, { title: "Test worm", organism: "Vermis probatus", swatch: "find-band", text: word.sentence, note: "The test worm has no connexins; its junction channels are innexins.", more: word.more });
  assert.match(word.more, /shape drawn, the assembly and the reference structures/);
  assert.deepEqual(shown.chips.slice(0, 2), unit.chips);
  assert.deepEqual(shown.chips[2], { label: "Test worm: a different family", title: word.description, swatch: "find-band" });
  assert.deepEqual(shown.sign, { swatch: "find-band", title: "Test worm: a different family" });
  assert.ok(shown.keywords.startsWith("a_law@1 GJC1 ") && shown.keywords.includes("inx-1"));
});

test("nothing found is said plainly; found and nothing-to-look-for carry no mark", () => {
  const none = inSpecies(unitPart(NONE), proteins, "testworm");
  assert.equal(none.finding.text, "The search found no gene product for this unit.");
  assert.equal(none.finding.note, "A search by family signature found nothing.");
  assert.equal(none.sign.swatch, "find-dashes");
  assert.deepEqual(none.sections.find((section) => section.key === "products").items, [], "an empty list is not drawn");
  const found = inSpecies(unitPart("U01"), proteins, "testworm");
  assert.equal(found.sign, null);
  assert.equal(found.chips.at(-1).label, "Test worm: found");
  assert.equal(found.chips.at(-1).swatch, null);
  const lumped = inSpecies(unitPart(LUMPED), proteins, "testworm");
  assert.equal(lumped.sign, null);
  assert.equal(lumped.finding.text, "The inventory names no natural gene product for this unit, so there is nothing to look for in any species.");
  // A unit the inventory lists no product for still gets the species' products, after its laws.
  const bare = unitPart("U01");
  bare.sections = bare.sections.filter((section) => section.key !== "products");
  assert.deepEqual(inSpecies(bare, proteins, "testworm").sections.map((section) => section.key), ["laws", "products", "structures"]);
  // A unit the file has no sound entry for says so.
  const gap = { ...unitPart("U01"), species: { testworm: { finding: null, note: null, items: [] } } };
  assert.equal(inSpecies(gap, proteins, "testworm").finding.text, overlay.species.no_entry);
});

test("only a finding that differs is marked, and each mark has a ring to draw and a sign to show", () => {
  const marked = overlay.species.findings.filter((word) => word.mark);
  assert.deepEqual(marked.map((word) => word.id), ["different family", "none found"]);
  for (const word of marked) {
    assert.ok(css.includes(`.swatch-find-${word.mark} {`), `no sign for ${word.mark}`);
    const ring = findingMark(word.mark, 5);
    ring.computeBoundingBox();
    assert.ok(Math.abs(ring.boundingBox.max.y - ring.boundingBox.min.y) < 1e-6, "the ring lies flat on the membrane");
    assert.ok(ring.boundingBox.max.x > 5 && ring.boundingBox.max.x < 6, "around the unit, clear of its neighbours");
  }
  assert.notEqual(findingMark("band", 5).attributes.position.count, findingMark("dashes", 5).attributes.position.count, "an unbroken ring and a broken one");
});

test("a species that lacks most of the machines is shown quietly: faint units and no rings, with its own proteins pointed at", () => {
  // The made-up worm differs for two units: a ring beside each is no trouble.
  assert.equal(quietAtlas(proteins, species), false);
  assert.equal(inSpecies(unitPart(NONE), proteins, "testworm").faint, false);
  // A species in which almost nothing was found: a ring beside each unit would bury the picture.
  const bare = readOne(madeUp((data) => {
    for (const id of UNITS) if (id !== LUMPED) data.units[id] = { finding: "none found", note: "A search by family signature found nothing.", products: [] };
    Object.assign(data.species, { id: "barebug", label: "Bare-B1" });
  }), "barebug");
  assert.deepEqual(bare.warnings, []);
  const quiet = { ...proteins, atlases: bare.atlases };
  const atlas = bare.atlases[1];
  assert.equal(quietAtlas(quiet, atlas), true);
  assert.equal(quietAtlas(quiet, bare.atlases[0]), false, "the inventory's own side is never quiet");
  const unit = { ...unitPart(NONE), species: { barebug: bare.units[NONE].barebug } };
  const shown = inSpecies(unit, quiet, "barebug");
  assert.equal(shown.sign, null, "no sign on the unit's name");
  assert.equal(shown.faint, true, "the unit is drawn faint");
  assert.equal(shown.finding.swatch, "find-faint");
  assert.ok(css.includes(".swatch-find-faint {") && css.includes(".label.is-faint"));
  const said = speciesWords(quiet, atlas);
  assert.match(said.caveat, /A unit drawn faint is one the Bare-B1 atlas found no gene product for/, "a proper name keeps its capitals in a sentence");
  assert.ok(!/A ring marks/.test(said.caveat));
  assert.match(said.card.check, /Most of these machines were not found in it\. The 1 of its own proteins that bear on the picture are listed below/);
  assert.equal(said.card.extraOpen, true);
  assert.deepEqual(said.findings.items.filter((item) => item.swatch).map((item) => item.swatch), ["find-faint", "find-faint"]);
  // A species named by a plain word is written small in a sentence.
  assert.match(speciesWords(proteins, species).caveat, /the Test worm atlas differs/);
  assert.match(speciesWords(proteins, { ...species, label: "Planarian" }).caveat, /the planarian atlas differs/);
});

test("the species' card gives its own counts and sources, and claims nothing of the engine", () => {
  const said = speciesWords(proteins, species);
  assert.equal(said.card.heading, "Test worm atlas");
  assert.equal(said.card.organism, "Vermis probatus");
  assert.deepEqual(said.card.stats.map(([value]) => value), [species.counts.with_products, 4, 2]);
  assert.equal(said.card.text, "A made-up animal, for the tests.");
  assert.deepEqual(said.card.sources, species.sources);
  assert.equal(said.card.notCopied, "Nothing was read.");
  // How it was made: the file's own lines, and where a unit is left out of the picture, the line that says so.
  assert.equal(said.card.method[0], "Made up for the tests.");
  assert.equal(said.card.method.length, LEFT_OUT.length ? 2 : 1);
  if (LEFT_OUT.length) assert.match(said.card.method[1], LEFT_OUT_LINE);
  assert.match(said.card.check, /units and their laws are the engine's, the same for every species/);
  assert.match(said.card.check, /not anything the engine models/);
  assert.match(said.card.check, /2 of the 4 products were found by signature or similarity: candidates, not established counterparts\./);
  assert.match(said.caveat, /what the engine's law names, the same for every species/);
  assert.match(said.stamp, /^Test worm atlas of 14 Nov 2026 · inventory of /);
  // The findings, as the legend lists them: a sign only where the species differs.
  assert.deepEqual(said.findings.items.map((item) => [item.id, item.count, item.swatch]), [
    ["found", DRAWN.length - 3, null],
    ["different family", 1, "find-band"],
    ["none found", 1, "find-dashes"],
    ["nothing to look for", 1, null],
  ]);
  // Nowhere do the view's own words, or the vocabulary, say that the engine models this species' proteins.
  const words = JSON.stringify([said, overlay.species]);
  assert.ok(!/(engine|Cells) (models|simulates) (a |the )?(test worm|this species|species'|planarian)/i.test(words));
  assert.ok(!/The proteins Cells models/.test(words), "that heading is the inventory's own atlas's");
});

// ---------------------------------------------------------------- the whole build

test("the build puts every atlas in the scene and each species' side on every unit", async (t) => {
  const { code, said, scene } = await built;
  if (declined({ code, said })) return t.skip(`the build did not run: ${declined({ code, said })}`);
  assert.equal(code, 0, said);
  assert.deepEqual(validate(scene), []);
  assert.deepEqual(scene.meta.warnings.filter((warning) => warning.startsWith("species atlas")), []);
  assert.match(said, /species atlas testworm of 2026-11-14: products for \d+ of \d+ units, 4 gene products, 2 of them candidates/);
  assert.deepEqual(scene.proteins.atlases, sound.atlases, "the scene's atlases are the reader's");
  // The findings' words are the overlay's, but where something left out of the picture gives one another wording.
  const reworded = new Map(LEFT_OUT.flatMap((id) => overlay.units[id].left_out.rewords || []).filter((change) => change.in === "species.findings").map((change) => [`${change.id}/${change.field}`, change.to]));
  assert.deepEqual(scene.proteins.findings, overlay.species.findings.map((word) => Object.fromEntries(Object.entries(word).map(([field, text]) => [field, reworded.get(`${word.id}/${field}`) ?? text]))));
  assert.deepEqual(scene.proteins.product_evidence, overlay.species.evidence);
  assert.equal(scene.proteins.remarks, undefined, "remarks are for the build's report, not for the page");
  const units = scene.entities.filter((entity) => entity.kind === "unit");
  assert.deepEqual(units.map((unit) => unit.id.replace("unit.", "")).sort(), [...DRAWN].sort(), "the units drawn are the inventory's, less what is left out");
  for (const unit of units) {
    const id = unit.id.replace("unit.", "");
    assert.deepEqual(unit.species, sound.units[id], `${unit.id}: each species' side`);
    assert.ok(FINDINGS.includes(unit.species.testworm.finding));
  }
  assert.ok(!MACHINE.test(JSON.stringify([scene.proteins, units])), "a machine path leaked into the scene");
});

test("the build leaves the inventory's side of every unit as it was", async (t) => {
  const { code, said, scene } = await built;
  if (declined({ code, said })) return t.skip(`the build did not run: ${declined({ code, said })}`);
  assert.equal(code, 0, said);
  const stated = snapshot.inventory.counts;
  const out = snapshot.units.filter((unit) => LEFT_OUT.includes(unit.id));
  for (const mapping of overlay.mappings) {
    assert.equal(scene.proteins.mappings.find((item) => item.id === mapping.id).count, stated.functional_units_by_status[mapping.inventory] - out.filter((unit) => unit.status === mapping.inventory).length);
  }
  const shown = snapshot.laws.filter((law) => [law.unit, ...(law.also_in || [])].some((unit) => DRAWN.includes(unit)));
  assert.equal(scene.proteins.evidence.reduce((sum, item) => sum + item.count, 0), shown.length, "the evidence block still counts law records, not products");
  const lawEvidence = new Set(overlay.evidence.map((item) => item.id));
  for (const unit of scene.entities.filter((entity) => entity.kind === "unit")) {
    const listed = snapshot.units.find((item) => `unit.${item.id}` === unit.id);
    assert.ok(unit.evidence.every((kind) => lawEvidence.has(kind)), `${unit.id}: its evidence is its laws'`);
    assert.deepEqual(unit.sections.map((section) => section.key).filter((key) => !["laws", "products", "structures"].includes(key)), []);
    const products = unit.sections.find((section) => section.key === "products");
    assert.deepEqual((products?.items || []).map((item) => item.label), (listed.products || []).map((product) => product.gene), `${unit.id}: the inventory's candidates`);
    assert.equal(products ? products.title : "Candidate products", "Candidate products");
    // In the human atlas the view shows exactly this part.
    assert.equal(inSpecies(unit, scene.proteins, "human"), unit);
    assert.equal(inSpecies(unit, scene.proteins, "testworm").sections.find((section) => section.key === "products").title, "Test worm gene products");
  }
});

// ---------------------------------------------------------------- left out of the picture, and back

test("a unit left out of the picture keeps its entry in every file, and is not counted on the page", (t) => {
  if (!LEFT_OUT.length) return t.skip("no unit is left out of the picture");
  // The file must still have an entry for it: the contract asks one for each unit of the inventory.
  const without = readOne(madeUp((data) => delete data.units[LEFT_OUT[0]]));
  assert.match(without.warnings.join("\n"), new RegExp(`it has no entry for 1 of the inventory's ${UNITS.length} units: ${LEFT_OUT[0]}`));
  // What the file says of it is read like any other entry, and stays out of the counts.
  assert.equal(sound.units[LEFT_OUT[0]].testworm.finding, "found");
  assert.equal(species.counts.units, UNITS.length - LEFT_OUT.length);
  assert.match(species.method.at(-1), LEFT_OUT_LINE);
  assert.match(sound.atlases[0].method.at(-1), LEFT_OUT_LINE, "the inventory's own atlas says it too");
  assert.ok(species.method.at(-1).includes(overlay.units[LEFT_OUT[0]].left_out.says));
});

test("with its flag taken off, a unit is counted again and no atlas speaks of it", (t) => {
  if (!LEFT_OUT.length) return t.skip("no unit is left out of the picture");
  const back = read({ files: [["testworm", madeUp(), null]] }, UNFLAGGED_OVERLAY);
  assert.deepEqual(back.warnings, []);
  const [human, worm] = back.atlases;
  assert.equal(worm.counts.units, UNITS.length);
  assert.equal(worm.counts.with_products, UNITS.length - 2);
  assert.equal(worm.findings.reduce((sum, item) => sum + item.count, 0), UNITS.length);
  assert.deepEqual(worm.method, ["Made up for the tests."]);
  assert.equal(human.counts.units, snapshot.inventory.counts.functional_units);
  assert.deepEqual(human.method, overlay.species.reference.method);
});

test("the sentence that says what is left out reads right for one unit and for several, and a flag must say its part", async () => {
  const SAY = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib.protein_atlas import left_out_sentence, left_out_flag
flags = json.loads(sys.argv[2])
print(json.dumps([left_out_sentence(49, flags[:1]), left_out_sentence(49, flags, drawn=47), left_out_sentence(49, []), left_out_sentence(49, flags[:1], drawn=48)]))
for flag in flags:
    left_out_flag("a unit", flag)
left_out_flag("a unit", json.loads(sys.argv[3]))
`;
  const flags = [
    { since: "2026-11-15", says: "an engineered protein cage", reason: "it is a designed protein, not a part of a cell" },
    { since: "2026-11-16", says: "a made-up pore", reason: "it is made up" },
  ];
  const say = (bad) => spawnSync("python3", ["-c", SAY, path.join(ROOT, "tools"), JSON.stringify(flags), JSON.stringify(bad)], { encoding: "utf8" });
  // A flag that does not say how the page names the thing, or why, stops the build with its reason.
  for (const bad of [{ since: "2026-11-15", reason: "none" }, { since: "soon", says: "a thing", reason: "none" }, { since: "2026-11-15", says: "a thing", reason: " " }, "yes"]) {
    const run = say(bad);
    assert.notEqual(run.status, 0, JSON.stringify(bad));
    assert.match(run.stderr, /a unit: left_out needs 'since' \(a date\), 'says' \(how the page names it\) and 'reason'/);
  }
  const run = say(flags[0]);
  assert.equal(run.status, 0, run.stderr);
  const [one, two, none, counted] = JSON.parse(run.stdout);
  assert.equal(one, "The inventory has 49 units. One of them, an engineered protein cage, is left out of the picture for now: it is a designed protein, not a part of a cell.");
  assert.equal(two, "The inventory has 49 units. Two of them, an engineered protein cage and a made-up pore, are left out of the picture for now: it is a designed protein, not a part of a cell; it is made up. The 47 others are shown and counted here.");
  assert.equal(none, "");
  assert.ok(counted.endsWith("The 48 others are shown and counted here."));
});

test("with the flags taken off, the build brings back what was left out, as it was", async (t) => {
  if (!builtUnflagged) return t.skip("nothing is left out of the picture");
  const { code, said, scene } = await builtUnflagged;
  if (declined({ code, said })) return t.skip(`the build did not run: ${declined({ code, said })}`);
  assert.equal(code, 0, said);
  assert.deepEqual(validate(scene), []);
  assert.deepEqual(scene.left_out, []);
  assert.ok(!/left out of the picture/.test(said + JSON.stringify(scene)), "nothing is left out, and nothing says so");
  const parts = new Map(scene.entities.map((entity) => [entity.id, entity]));
  // The units: all of the inventory's, each district, site and kind of evidence, and the atlas's own summary.
  assert.deepEqual([...parts.values()].filter((entity) => entity.kind === "unit").map((unit) => unit.id.replace("unit.", "")).sort(), [...UNITS].sort());
  assert.equal(scene.proteins.counts.units, UNITS.length);
  assert.equal(scene.proteins.summary, overlay.summary);
  assert.deepEqual(scene.proteins.findings, overlay.species.findings);
  assert.deepEqual(scene.proteins.districts.map((item) => item.id), overlay.districts.map((item) => item.id));
  assert.deepEqual(scene.proteins.sites, overlay.sites);
  assert.deepEqual(scene.proteins.evidence.map((item) => item.id), overlay.evidence.map((item) => item.id));
  assert.equal(scene.proteins.evidence.reduce((sum, item) => sum + item.count, 0), snapshot.inventory.counts.records);
  // The capabilities: each is a part again, linked to what implements it, and that part's text is its own.
  for (const capability of LEFT_OUT_PARTS) {
    assert.equal(parts.get(capability.id)?.part, capability.part, `${capability.id} is a part of the cell again`);
    for (const target of capability.implemented_by || []) {
      assert.ok(scene.relations.some((relation) => relation.from === capability.id && relation.to === target && relation.kind === "implements"), `${capability.id} -> ${target}`);
      assert.equal(parts.get(target).plain, map.components.find((item) => item.id === target).plain);
    }
    // Each text a wording stood in for is the overlay's own again.
    for (const change of capability.left_out.rewords || []) {
      if (change.in === "scales") assert.equal(parts.get(change.id)[change.field], map.scales.find((item) => item.id === change.id)[change.field], `${change.id}.${change.field}`);
      if (change.in === "model_groups") assert.equal(scene.model_groups.find((item) => item.id === change.id)[change.field], map.model_groups.find((item) => item.id === change.id)[change.field]);
    }
  }
  for (const unit of LEFT_OUT) assert.ok(scene.relations.some((relation) => relation.from === `unit.${unit}` && relation.kind === "modelled_by"), `unit.${unit} is linked to its law again`);
  // A species' place for the capability is in the scene again, as its file has it.
  for (const item of scene.species || []) {
    const file = JSON.parse(await readFile(path.join(ROOT, "data", "species", `${item.id}.json`), "utf8"));
    assert.deepEqual(Object.keys(item.cell.capabilities).sort(), Object.keys(file.cell.capabilities || {}).sort(), `${item.id}: its places`);
  }
});

// ---------------------------------------------------------------- the repository's own species files

test("every species file of the repository holds to the contract", (t) => {
  const own = path.join(ROOT, "data", "proteins", "atlases");
  if (!existsSync(own)) return t.skip("no species file yet");
  const { warnings, remarks, atlases } = read({ folder: own });
  for (const remark of remarks) t.diagnostic(remark);
  assert.deepEqual(warnings, []);
  assert.ok(atlases.length > 1, "the folder holds no species file");
  for (const atlas of atlases.slice(1)) {
    assert.equal(atlas.findings.reduce((sum, item) => sum + item.count, 0), DRAWN.length, `${atlas.id}: one finding for every unit drawn`);
    assert.equal(atlas.counts.units, DRAWN.length);
  }
});
