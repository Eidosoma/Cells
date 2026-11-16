// How a species atlas's products were found, and what their records are: two facts, kept apart
// (schema/SPECIES_ATLAS.md, format @2, 16 November 2026). Until then one word mixed them, and a
// product with a reviewed entry was counted as not found by signature, so the mouse's card said 3
// of its 158 products were candidates when all 158 were found by a family's signature.
//
// What this file holds:
//   1. the shared search sets how a product was found from its family's part in the machine and
//      never from its entry's review state: run on a made-up catalogue with a reviewed and an
//      unreviewed carrier of one signature, both are found the same way and differ in their entry;
//   2. every atlas of the repository gives both facts, in the contract's words, the same way for a
//      product in every unit that lists it, and no older word;
//   3. the counts the card gives are worked out again from the files, species by species, and the
//      card's sentences carry them; a scene made before the change gets no false count.
//
//   node --test tests/atlas_products.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { productWords, speciesWords } from "../src/lenses/proteins.js";

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const OVERLAY = path.join(ROOT, "data", "proteins", "overlay.json");
const SNAPSHOT = path.join(ROOT, "data", "proteins", "inventory.snapshot.json");
const ATLASES = path.join(ROOT, "data", "proteins", "atlases");
const overlay = await json(OVERLAY);
const stamp = { created: (await json(SNAPSHOT)).inventory.created };
const FOUND_BY = overlay.species.found_by.filter((word) => !word.older).map((word) => word.id);
const ENTRIES = overlay.species.entry_kinds.filter((word) => !word.older).map((word) => word.id);
const CANDIDATE = new Set(overlay.species.found_by.filter((word) => word.candidate).map((word) => word.id));
const LEFT_OUT = new Set(Object.entries(overlay.units).filter(([, unit]) => unit.left_out).map(([id]) => id));
const files = (await readdir(ATLASES)).filter((name) => name.endsWith(".json")).sort();
const atlases = await Promise.all(files.map(async (name) => [name.replace(/\.json$/, ""), await json(path.join(ATLASES, name))]));

// ---------------------------------------------------------------- 1. the shared search

const SEARCH = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import proteome_shelves as P

class Filing:
    def __init__(self, carriers):
        self._carriers = carriers
        self.names = {key: {"name": f"family {key}"} for key in carriers}
    def carriers(self):
        return self._carriers

# One unit whose machine is made by family "own" and goes with family "nav_beta" (an accessory one).
snapshot = {"units": [{"id": "U01", "products": [{"human_uniprot": "H1"}]}]}
families = {"own": {"of": "the machine's own family", "signatures": ["IPR1"]}, "nav_beta": {"of": "a family that goes with it", "signatures": ["IPR2"]}}
units = {"U01": {"parts": ["own", "nav_beta"]}}
entries = {
    "R1": {"name": "Reviewed carrier", "gene": "rev1", "length": 100, "reviewed": True},
    "U1": {"name": "Unreviewed carrier", "gene": "unr1", "length": 100, "reviewed": False},
    "A1": {"name": "Reviewed accessory", "gene": "acc1", "length": 50, "reviewed": True},
}
human = {"H1": {"IPR1", "IPR2"}}
filing = Filing({"IPR1": ["R1", "U1"], "IPR2": ["A1"]})
found, _, _ = P.find_units(snapshot, entries, filing, human, families, units, {}, "the test species")
out = {"products": found["U01"]["products"]}
# A protein that would be found by an accessory family in one unit and by the machine's own in another stops the build.
snapshot2 = {"units": [{"id": "U01", "products": [{"human_uniprot": "H1"}]}, {"id": "U02", "products": [{"human_uniprot": "H1"}]}]}
families2 = {"own": {"of": "own", "signatures": ["IPR1"]}, "nav_beta": {"of": "goes with", "signatures": ["IPR1", "IPR3"]}}
units2 = {"U01": {"parts": ["own"]}, "U02": {"parts": ["own2", "nav_beta"]}}
families2["own2"] = {"of": "own two", "signatures": ["IPR3"]}
human2 = {"H1": {"IPR1", "IPR3"}}
try:
    P.find_units(snapshot2, entries, Filing({"IPR1": ["R1"], "IPR3": ["U1"]}), human2, families2, units2, {}, "the test species")
    out["stopped"] = None
except SystemExit as stop:
    out["stopped"] = str(stop)
print(json.dumps(out))
`;

test("the shared search: a reviewed and an unreviewed carrier of one signature are found the same way, and differ only in their entry", () => {
  const run = spawnSync("python3", ["-I", "-c", SEARCH, path.join(ROOT, "tools")], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const { products, stopped } = JSON.parse(run.stdout);
  const by = Object.fromEntries(products.map((product) => [product.ids[0].id, product]));
  assert.deepEqual([by.R1.found_by, by.U1.found_by], ["family signature", "family signature"], "how found does not follow the entry");
  assert.deepEqual([by.R1.entry, by.U1.entry], ["reviewed", "unreviewed"]);
  // A reviewed entry of a family that only goes with the machine is that, and no candidate for its work.
  assert.deepEqual([by.A1.found_by, by.A1.entry], ["accessory signature", "reviewed"]);
  assert.match(by.A1.evidence_note, /no candidate for the machine's own work/);
  for (const product of products) assert.ok(!("evidence" in product), "the older word is not written");
  assert.match(stopped || "", /accessory family in one unit/, "a product found two ways stops the build");
});

// ---------------------------------------------------------------- 2. every atlas of the repository

test("every atlas gives both facts in the contract's words, the same way for a product in every unit, and no older word", () => {
  assert.ok(atlases.length >= 7, files.join());
  for (const [id, atlas] of atlases) {
    assert.equal(atlas.format, "cells.visualizer.species_atlas@2", id);
    const seen = new Map();
    const products = [...Object.entries(atlas.units).flatMap(([unit, entry]) => entry.products.map((product) => [unit, product])), ...(atlas.extra || []).map((product) => ["extra", product])];
    for (const [unit, product] of products) {
      const label = `${id} ${unit}: ${product.gene || product.name}`;
      assert.ok(FOUND_BY.includes(product.found_by), `${label}: found_by ${product.found_by}`);
      assert.ok(ENTRIES.includes(product.entry), `${label}: entry ${product.entry}`);
      assert.ok(!("evidence" in product), `${label}: the older word`);
      assert.equal(Boolean(product.citation?.text), product.found_by === "named in a publication", `${label}: a citation goes with a paper's naming`);
      // A UniProtKB entry is reviewed or unreviewed; a record with no UniProtKB id is a genome annotation.
      assert.equal(product.entry === "genome annotation", product.ids[0]?.db !== "uniprot", `${label}: ${product.entry} for ${product.ids[0]?.db}`);
      if (unit === "extra") continue;
      const key = JSON.stringify(product.ids[0]);
      assert.equal(seen.get(key) ?? product.found_by, product.found_by, `${label}: found two ways in two units`);
      seen.set(key, product.found_by);
    }
  }
});

test("a unit's note calls no accessory family's protein a candidate: it names them apart, as going with the machine", () => {
  for (const [id, atlas] of atlases) {
    for (const [unit, entry] of Object.entries(atlas.units)) {
      const at = (entry.note || "").indexOf("Each is a candidate by its family alone");
      if (at < 0) continue;
      const candidates = entry.note.slice(0, at);
      for (const product of entry.products.filter((item) => item.found_by === "accessory signature" && item.gene)) {
        assert.ok(!new RegExp(`(^|[\\s,(])${product.gene.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([\\s,.]|$)`).test(candidates), `${id} ${unit}: ${product.gene} is named among the candidates`);
      }
      if (entry.products.some((item) => item.found_by === "accessory signature")) assert.match(entry.note, /which go with the machine and make none by themselves: .* no candidates? for its own work\./, `${id} ${unit}`);
    }
  }
});

// ---------------------------------------------------------------- 3. the card's counts, from the files

/** What the card counts for one atlas, worked out from its file: each product once, by its first id, in the units drawn. */
function counted(atlas) {
  const distinct = new Map();
  for (const [unit, entry] of Object.entries(atlas.units)) {
    if (LEFT_OUT.has(unit)) continue;
    for (const product of entry.products) if (!distinct.has(JSON.stringify(product.ids[0]))) distinct.set(JSON.stringify(product.ids[0]), product);
  }
  const tally = (field) => [...distinct.values()].reduce((sum, product) => ({ ...sum, [product[field]]: (sum[product[field]] || 0) + 1 }), {});
  const found = tally("found_by"), entries = tally("entry");
  return { products: distinct.size, candidates: Object.entries(found).reduce((sum, [kind, n]) => sum + (CANDIDATE.has(kind) ? n : 0), 0), reviewed: entries.reviewed || 0, found, entries };
}

const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib.protein_atlas import Species, read_species_files
snapshot = json.load(open(sys.argv[2], encoding="utf-8"))
overlay = json.load(open(sys.argv[3], encoding="utf-8"))
species = Species(snapshot, overlay, read_species_files(sys.argv[4]))
print(json.dumps({"warnings": species.warnings, "atlases": species.summary()}))
`;
const read = spawnSync("python3", ["-I", "-c", READER, path.join(ROOT, "tools"), SNAPSHOT, OVERLAY, ATLASES], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

test("the counts the builder gives each species are those worked out from its file", () => {
  assert.equal(read.status, 0, read.stderr);
  const { warnings, atlases: summary } = JSON.parse(read.stdout);
  assert.deepEqual(warnings, []);
  const byId = new Map(summary.map((item) => [item.id, item]));
  for (const [id, atlas] of atlases) {
    const mine = counted(atlas), theirs = byId.get(id);
    assert.deepEqual([theirs.counts.products, theirs.counts.candidates, theirs.counts.reviewed], [mine.products, mine.candidates, mine.reviewed], id);
    assert.deepEqual(Object.fromEntries(theirs.found_by.filter((item) => item.count).map((item) => [item.id, item.count])), mine.found, id);
    assert.deepEqual(Object.fromEntries(theirs.entries.filter((item) => item.count).map((item) => [item.id, item.count])), mine.entries, id);
  }
  // The two the user saw wrong, as the files now count them: every product found by a family's signature.
  assert.deepEqual(counted(Object.fromEntries(atlases).mouse).found, { "family signature": 116, "accessory signature": 42 });
  assert.deepEqual(counted(Object.fromEntries(atlases).mouse).entries, { reviewed: 155, unreviewed: 3 });
  assert.deepEqual(counted(Object.fromEntries(atlases).fruitfly).found, { "family signature": 37, "accessory signature": 17 });
  assert.deepEqual(counted(Object.fromEntries(atlases).fruitfly).entries, { reviewed: 28, unreviewed: 26 });
});

test("each species' card says how its products were found, then what their records are, with the files' numbers; no count reads as more sure", () => {
  const { atlases: summary } = JSON.parse(read.stdout);
  const proteins = { stamp, findings: overlay.species.findings, atlases: summary };
  for (const species of summary.filter((item) => !item.reference)) {
    const card = speciesWords(proteins, species).card;
    const mine = counted(Object.fromEntries(atlases)[species.id]);
    assert.deepEqual(card.stats.map(([value]) => value), [species.counts.with_products, mine.products, mine.candidates], species.id);
    assert.ok(!/undefined|NaN/.test(JSON.stringify(card)), `${species.id}: ${card.check}`);
    assert.ok(!/signature or similarity/.test(card.check), `${species.id}: the older sentence`);
    if (!mine.products) continue;
    const found = card.check.slice(card.check.indexOf("How they were found:"), card.check.indexOf("Their records:"));
    const records = card.check.slice(card.check.indexOf("Their records:"));
    for (const n of Object.values(mine.found)) assert.ok(new RegExp(`(^|\\D)${n.toLocaleString("en-US")}\\D`).test(found), `${species.id}: ${n} is not in "${found}"`);
    for (const n of Object.values(mine.entries)) assert.ok(new RegExp(`(^|\\D)${n.toLocaleString("en-US")}\\D`).test(records), `${species.id}: ${n} is not in "${records}"`);
    // An accessory family's products are counted apart, and called no candidates for the machine's work.
    if (mine.found["accessory signature"]) assert.match(found, /only by that of a family that goes with one .* no candidates? for its own work/, species.id);
    if (mine.reviewed) assert.match(records, /a reviewed entry says how the entry was written, not that the protein does a unit's work\./, species.id);
  }
  // The mouse and the fly, word for word.
  const mouse = speciesWords(proteins, summary.find((item) => item.id === "mouse")).card.check;
  assert.match(mouse, /How they were found: 116 by the signature of a family that makes the machine, candidates by family, not established counterparts; 42 only by that of a family that goes with one/);
  assert.match(mouse, /Their records: 155 UniProtKB entries reviewed by a curator, 3 annotated automatically;/);
  const fly = speciesWords(proteins, summary.find((item) => item.id === "fruitfly")).card.check;
  assert.match(fly, /How they were found: 37 by the signature of a family that makes the machine, candidates by family, not established counterparts; 17 only by/);
  assert.match(fly, /Their records: 28 UniProtKB entries reviewed by a curator, 26 annotated automatically;/);
});

test("a scene made before the two facts were kept apart gets no false count and no 'undefined' on the card", () => {
  const old = { id: "mouse", label: "Mouse", organism: "Mus musculus", plain: "The laboratory mouse.", made: "2026-11-16", counts: { units: 48, with_products: 43, products: 158, candidates: 3 }, findings: [], evidence: [{ id: "reviewed entry", count: 155 }], sources: [], method: [] };
  const card = speciesWords({ stamp, findings: overlay.species.findings }, old).card;
  assert.deepEqual(card.stats, [[43, "of 48 units have products"], [158, "gene products"]], "the older count of candidates is not shown");
  assert.ok(!/undefined|candidates|signature/.test(card.check), card.check);
  assert.equal(productWords(old.counts, undefined, undefined), "");
});
