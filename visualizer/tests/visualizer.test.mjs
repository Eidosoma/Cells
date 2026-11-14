// Checks that run without a browser: the scene is valid, the page builds, and the
// page asks for nothing the artifact frame would block.
//
//   npm test

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import os from "node:os";
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

// ---------------------------------------------------------------- replays in the page

/** The scene as the page carries it. */
const sceneOf = (page) => JSON.parse(/<script type="application\/json">(.*?)<\/script>/s.exec(page)[1]);

test("the page carries the replay catalogue, and the runs themselves only when asked", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "cells-runs-"));
  try {
    const empty = path.join(folder, "none");
    await mkdir(empty);
    assert.equal(sceneOf(await buildPage({ runsDir: empty })).replays, undefined, "no catalogue, no Experiments view");

    const runs = path.join(folder, "runs");
    await mkdir(runs);
    const run = { format: "cells.visualizer.replay@1", view: { format: "cells.run_view@1" }, payload: { encoding: "base64", byte_length: 0, data: "" } };
    await writeFile(path.join(runs, "x--arm--seed1.json"), JSON.stringify(run));
    await writeFile(
      path.join(runs, "index.json"),
      JSON.stringify({ format: "cells.visualizer.replay_index@1", experiments: [{ id: "x", label: "X" }], runs: [{ id: "x--arm--seed1", experiment: "x", file: "runs/x--arm--seed1.json" }] })
    );
    const linked = await buildPage({ runsDir: runs });
    assert.equal(sceneOf(linked).replays.runs[0].id, "x--arm--seed1");
    assert.ok(!linked.includes('<script type="application/json" data-replay='), "by default a run stays in its own file beside the page");
    const inline = await buildPage({ runsDir: runs, inlineRuns: true });
    assert.ok(inline.includes('<script type="application/json" data-replay="x--arm--seed1">'), "a standalone page carries its runs");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("every engine part an experiment's replays point at is on the map", async () => {
  const replayOverlay = JSON.parse(await readFile(path.join(ROOT, "data", "runs", "overlay.json"), "utf8"));
  const ids = new Set(scene.entities.map((entity) => entity.id));
  const tracked = new Set(scene.entities.flatMap((entity) => (entity.sources || []).map((source) => source.path)));
  for (const [name, experiment] of Object.entries(replayOverlay.experiments)) {
    for (const id of experiment.engine_entities) assert.ok(ids.has(id), `${name}: ${id} is not a part of the scene`);
    assert.ok(experiment.label && experiment.plain && experiment.sources.length, `${name} needs a label, a plain line and a source`);
    assert.ok((experiment.classes || []).every((item) => item.id && item.label && item.description), `${name}: every class is described`);
    // What an experiment found is the record's, so it must say where the record says it.
    const outcome = experiment.outcome;
    assert.ok(outcome, `${name} says nothing about what it found`);
    assert.equal(typeof outcome.judged, "boolean", `${name}: judged or not`);
    assert.ok(outcome.status && outcome.text && outcome.sources?.length, `${name}: its outcome needs a status, the record's line and a source`);
    assert.ok(outcome.judged ? ["yes", "no", "mixed"].includes(outcome.answer) && outcome.label : outcome.answer === null, `${name}: an answer only where something is judged`);
  }
  assert.ok(tracked.size > 0);
});

