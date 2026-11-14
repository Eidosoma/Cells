// Checks that run without a browser: the scene is valid, the page builds, and the
// page asks for nothing the artifact frame would block.
//
//   npm test

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, ROOT, THREE_CDN, DEFAULT_SCENE } from "../tools/lib/build_page.mjs";
import { validate } from "../src/scene/model.js";

const scene = JSON.parse(await readFile(DEFAULT_SCENE, "utf8"));
const overlay = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const snapshot = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"), "utf8"));
const atlasOverlay = JSON.parse(await readFile(path.join(ROOT, "data", "proteins", "overlay.json"), "utf8"));

test("the generated scene is structurally valid", () => {
  assert.deepEqual(validate(scene), []);
});

test("the extractor placed every engine file and raised no warning", () => {
  assert.equal(scene.meta.counts.engine_files_placed, scene.meta.counts.engine_files);
  assert.deepEqual(scene.meta.warnings, []);
});

test("every status claim beyond established carries a source", () => {
  for (const entity of scene.entities) {
    if (!entity.status || entity.kind === "scale") continue;
    const catchAll = /^Other /.test(entity.label) || entity.plain?.includes("not grouped elsewhere");
    if (!catchAll && entity.status !== "established") {
      assert.ok(entity.sources?.length, `${entity.id} (${entity.status}) has no source`);
    }
  }
});

test("each capability is drawn: it names a part of the cell and how it is represented", () => {
  const representations = new Set(overlay.representations.map((item) => item.id));
  for (const capability of scene.entities.filter((entity) => entity.kind === "capability")) {
    assert.ok(capability.part, `${capability.id} has no part`);
    assert.ok(representations.has(capability.representation), `${capability.id}: representation ${capability.representation}`);
  }
});

test("the scene and the protein snapshot hold no machine-specific paths", () => {
  for (const [name, data] of [["scene", scene], ["protein snapshot", snapshot]]) {
    assert.ok(!/\/home\/|\/mnt\/|\/Users\//.test(JSON.stringify(data)), `an absolute path leaked into the ${name}`);
  }
});

// ---------------------------------------------------------------- the protein atlas

const units = scene.entities.filter((entity) => entity.kind === "unit");

test("the protein atlas matches the inventory it was made from", () => {
  const stated = snapshot.inventory.counts;
  assert.equal(units.length, stated.functional_units);
  const byMapping = Object.fromEntries(scene.proteins.mappings.map((item) => [item.id, item.count]));
  for (const mapping of atlasOverlay.mappings) {
    assert.equal(byMapping[mapping.id], stated.functional_units_by_status[mapping.inventory], `units that are ${mapping.inventory}`);
  }
  const laws = scene.proteins.evidence.reduce((sum, item) => sum + item.count, 0);
  assert.equal(laws, stated.records, "every law record has one kind of evidence");
});

test("every law record of the inventory is still found in the engine", () => {
  const { found, records } = scene.proteins.stamp;
  assert.equal(found.missing || 0, 0);
  assert.equal(Object.values(found).reduce((sum, count) => sum + count, 0), records);
});

test("a protein unit states its mapping in the inventory's words, never as an engine status", () => {
  const mappings = new Set(scene.proteins.mappings.map((item) => item.id));
  const evidence = new Set(scene.proteins.evidence.map((item) => item.id));
  for (const unit of units) {
    assert.equal(unit.status, undefined, `${unit.id} must not carry an engine status`);
    assert.ok(mappings.has(unit.mapping), `${unit.id}: mapping ${unit.mapping}`);
    assert.ok(unit.evidence.length && unit.evidence.every((kind) => evidence.has(kind)), `${unit.id}: evidence ${unit.evidence}`);
    assert.ok(unit.plain && unit.short && unit.district && unit.site, `${unit.id} lacks a plain line, a short name, a district or a site`);
    assert.ok(unit.sources?.length, `${unit.id} has no source`);
  }
});

test("a generic law is drawn as a plain stand-in, with no subunits", () => {
  for (const unit of units) {
    const form = unit.form;
    if (unit.mapping === "generic") {
      assert.equal(form.style, "plain", `${unit.id} is generic but drawn as ${form.style}`);
      for (const key of ["subunits", "repeats", "trimers", "aux"]) assert.equal(form[key], undefined, `${unit.id} is generic but draws ${key}`);
    } else {
      assert.equal(form.style, unit.mapping === "assigned" ? "solid" : "glass", `${unit.id}: ${unit.mapping} drawn as ${form.style}`);
    }
  }
});

test("each protein unit is linked to the engine part that holds its law", () => {
  const ids = new Set(scene.entities.map((entity) => entity.id));
  for (const unit of units) {
    const links = scene.relations.filter((relation) => relation.from === unit.id && relation.kind === "modelled_by");
    assert.ok(links.length, `${unit.id} is linked to no engine part`);
    for (const link of links) assert.ok(ids.has(link.to) && !link.to.startsWith("unit."), `${unit.id} -> ${link.to}`);
  }
});

test("the protein atlas links out only to the named public resources, and copies nothing from Xenbase", () => {
  const allowed = ["www.uniprot.org", "alphafold.ebi.ac.uk", "www.proteinatlas.org", "www.rcsb.org", "pubmed.ncbi.nlm.nih.gov", "doi.org"];
  let count = 0;
  for (const unit of units) {
    for (const section of unit.sections || []) {
      for (const entry of section.items) {
        for (const link of entry.links || []) {
          count += 1;
          const url = new URL(link.url);
          assert.equal(url.protocol, "https:");
          assert.ok(allowed.includes(url.hostname), `${unit.id}: ${link.url}`);
        }
      }
    }
  }
  assert.ok(count > 100, "the atlas should carry its links out");
  for (const [name, data] of [["snapshot", snapshot], ["scene", scene.proteins], ["units", units]]) {
    const text = JSON.stringify(data).replace(/No Xenbase data/g, "");
    assert.ok(!/xenbase|XB-GENE/i.test(text), `Xenbase content in the ${name}`);
  }
  assert.ok(snapshot.sources.some((source) => source.name === "UniProt" && source.licence === "CC BY 4.0" && source.release), "the UniProt notice with its release");
});

test("every part belongs to a view", () => {
  const lensOf = new Map(scene.groups.map((group) => [group.id, group.lens]));
  const lenses = new Set(scene.entities.map((entity) => lensOf.get(entity.group)));
  assert.deepEqual([...lenses].sort(), ["cell", "engine", "proteins"]);
});

test("the page builds and loads scripts only from allowed hosts", async () => {
  const page = await buildPage();
  assert.ok(page.startsWith("<title>"), "the title must come first");
  assert.ok(!/<!doctype|<html|<body/i.test(page), "the artifact service adds the document around the page");
  assert.ok(page.includes(THREE_CDN));
  const allowed = [/^https:\/\/cdnjs\.cloudflare\.com\//, /^https:\/\/fonts\.googleapis\.com\//];
  for (const [, url] of page.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) {
    assert.ok(allowed.some((pattern) => pattern.test(url)), `not an allowed host: ${url}`);
  }
  for (const [, url] of page.matchAll(/from\s+"(https?:\/\/[^"]+)"/g)) {
    assert.ok(allowed[0].test(url), `not an allowed script host: ${url}`);
  }
  assert.ok(Buffer.byteLength(page) < 16 * 1024 * 1024, "over the 16 MB page limit");
});
