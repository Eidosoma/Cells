// The inventory of public wet-lab evidence on planarian bioelectric proteins
// (data/evidence/planarian_bioelectric.json) keeps its shape and its fixed words, every
// record has a species, a category and a source, every catalogue id it names exists in
// the planarian catalogue, and it holds pointers and cited facts only.
//
//   node --test tests/planarian_evidence.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const FILE = path.join(ROOT, "data", "evidence", "planarian_bioelectric.json");
const NOTE = path.join(ROOT, "docs", "PLANARIAN_BIOELECTRIC_EVIDENCE.md");
const TABLE = path.join(ROOT, "data", "proteins", "planarian", "predicted_proteins.tsv");

const text = await readFile(FILE, "utf8");
const inventory = JSON.parse(text);
const note = await readFile(NOTE, "utf8");
const catalogue = new Set((await readFile(TABLE, "utf8")).trimEnd().split("\n").slice(1).map((line) => line.split("\t").slice(0, 2).join(":")));
const papers = new Map(inventory.papers.map((paper) => [paper.id, paper]));
const DEPOSIT = ["verified", "stated", "none found", "not determined"];

test("the inventory says what it is, and its fixed words are declared", () => {
  assert.equal(inventory.format, "cells.visualizer.planarian_bioelectric_evidence@1");
  assert.deepEqual(Object.keys(inventory), ["format", "made", "question", "target", "evidence_categories", "read_levels", "kinds", "families", "how_it_was_made", "papers", "records", "family_summary", "claims_checked", "context", "leads_not_audited", "not_determined"]);
  assert.match(inventory.made, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(inventory.target.organism, "Schmidtea mediterranea");
  // The lead's five categories, and the two added for protocols and for records that name no species.
  assert.deepEqual(Object.keys(inventory.evidence_categories), ["measured_exact", "related_strain", "reconstituted", "inferred_fitted", "other_simulator", "method", "not assigned"]);
  assert.deepEqual(Object.keys(inventory.read_levels), ["full text searched", "abstract only", "record only"]);
  assert.ok(inventory.kinds.length > 10 && Object.keys(inventory.families).length > 10);
});

test("every record has a species, a category, a kind, a family and a source, in the fixed words", () => {
  const ids = new Set();
  assert.ok(inventory.records.length >= 40);
  for (const record of inventory.records) {
    assert.ok(!ids.has(record.id), `${record.id} twice`);
    ids.add(record.id);
    assert.deepEqual(Object.keys(record).filter((key) => key !== "note"), ["id", "papers", "species", "families", "kinds", "measured", "how", "values", "evidence_category", "read", "deposit", "sequences", "genes", "could_test"], record.id);
    assert.ok(record.species.length > 0 && record.species.every((species) => species.name?.trim()), `${record.id}: species`);
    assert.ok(record.evidence_category in inventory.evidence_categories, `${record.id}: ${record.evidence_category}`);
    assert.ok(record.read in inventory.read_levels, `${record.id}: ${record.read}`);
    assert.ok(record.kinds.length > 0 && record.kinds.every((kind) => inventory.kinds.includes(kind)), `${record.id}: kinds`);
    assert.ok(record.families.length > 0 && record.families.every((family) => family in inventory.families), `${record.id}: families`);
    assert.ok(record.papers.length > 0, `${record.id}: no source`);
    for (const id of record.papers) {
      const paper = papers.get(id);
      assert.ok(paper, `${record.id} names the paper ${id}, which is not listed`);
      assert.ok(paper.doi || paper.pmid || paper.record, `${id} has no identifier`);
    }
    for (const field of ["measured", "how", "values", "could_test"]) assert.ok(record[field]?.trim(), `${record.id}: ${field}`);
    // A record that is not of the target species is never called measured in it.
    const target = record.species.some((species) => species.name === inventory.target.organism);
    if (record.evidence_category === "measured_exact") assert.ok(target, `${record.id} is 'measured_exact' without the target species`);
    if (record.evidence_category === "related_strain") assert.ok(!target, `${record.id} is 'related_strain' with the target species`);
  }
});

test("every paper states its licence, or that it states none, and how far it was read", () => {
  for (const paper of [...inventory.papers, ...inventory.context, ...inventory.leads_not_audited]) {
    assert.ok(paper.citation?.trim() && paper.year, paper.id);
    assert.ok(paper.licence?.trim(), `${paper.id}: no word on its licence`);
    assert.match(paper.licence, /^(CC BY|CC0|no licence stated|no open licence)/, `${paper.id}: ${paper.licence}`);
    assert.ok(paper.read in inventory.read_levels, `${paper.id}: ${paper.read}`);
  }
  // A record is read no further than the least-read of its papers.
  const depth = Object.keys(inventory.read_levels);
  for (const record of inventory.records) assert.equal(record.read, depth[Math.max(...record.papers.map((id) => depth.indexOf(papers.get(id).read)))], record.id);
});

test("every deposit says whether it was seen, and under what licence", () => {
  for (const record of inventory.records) {
    const deposit = record.deposit;
    assert.ok(DEPOSIT.includes(deposit.state), `${record.id}: ${deposit.state}`);
    if (deposit.state === "verified" || deposit.state === "stated") {
      assert.ok(deposit.where?.trim() && deposit.id?.trim(), `${record.id}: where the data is`);
      assert.ok(deposit.licence?.trim(), `${record.id}: the deposit's licence, or that none is stated`);
    } else {
      assert.ok(deposit.note?.trim(), `${record.id}: why no deposit is given`);
    }
    for (const sequence of record.sequences) assert.ok(sequence.accession && sequence.what && sequence.licence, `${record.id}: a sequence record`);
  }
});

test("every catalogue id a tie names exists in the planarian catalogue, and no gene is tied without a record", () => {
  let tied = 0;
  for (const record of inventory.records) {
    for (const gene of record.genes) {
      assert.ok(gene.name?.trim() && gene.species?.trim(), `${record.id}: a gene without a name or a species`);
      if (gene.tie) {
        tied += 1;
        assert.equal(gene.species, inventory.target.organism, `${record.id}: ${gene.name} is tied though it is of another species`);
        assert.ok(gene.tie.how?.trim(), `${record.id}: ${gene.name} is tied without saying how`);
        assert.equal(gene.tie.to[0].db, "uniprot", `${record.id}: ${gene.name} is tied without a database record`);
        for (const { db, id } of gene.tie.to) assert.ok(catalogue.has(`${db}:${id}`), `${record.id}: ${db}:${id} is not in the catalogue`);
      } else {
        assert.ok(gene.untied?.trim(), `${record.id}: ${gene.name} is neither tied nor said to be untied`);
      }
    }
  }
  assert.ok(tied > 10, "the ties the audit found");
});

test("it holds pointers and cited facts: no table, no trace, no machine path, and it is small", () => {
  assert.ok(text.length < 500_000, "under 500 KB");
  assert.ok(!/\/home\/|\/mnt\/|\/Users\/|\/tmp\//.test(text), "a machine path");
  assert.ok(!text.includes(os.hostname()) && !/localhost/.test(text), "a host name");
  const walk = (node, where) => {
    if (typeof node === "string") assert.ok(node.length < 1200, `${where}: a text of ${node.length} characters`);
    else if (typeof node === "number") assert.ok(/taxon|requests/.test(where), `${where}: a number where only pointers belong`);
    else if (Array.isArray(node)) node.forEach((item, index) => walk(item, `${where}[${index}]`));
    else if (node && typeof node === "object") for (const [key, value] of Object.entries(node)) walk(value, `${where}.${key}`);
  };
  walk(inventory, "inventory");
  // Nothing in it speaks for the engine, and no author was asked.
  assert.ok(!/\bCells (models|simulates|uses)\b|the engine (models|uses|has)/i.test(text));
  assert.match(inventory.how_it_was_made.rule, /No author was contacted/);
});

test("the note's counts are the inventory's", () => {
  const stated = note.match(/(\d+) records from (\d+) papers\./);
  assert.ok(stated, "the note does not state its counts");
  assert.equal(Number(stated[1]), inventory.records.length);
  assert.equal(Number(stated[2]), inventory.papers.length);
  for (const record of inventory.records) assert.ok(note.includes(`\`${record.id}\``), `the note's table lacks ${record.id}`);
  assert.ok(!/\/home\/|\/tmp\//.test(note), "a machine path in the note");
});
