// Checks that run without a browser: the scene is valid, the page builds, and the
// page asks for nothing the artifact frame would block.
//
//   npm test

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import os from "node:os";
import { buildPage, ROOT, THREE_CDN, DEFAULT_SCENE } from "../tools/lib/build_page.mjs";
import { validate, SceneModel } from "../src/scene/model.js";
import { inSpecies } from "../src/lenses/proteins.js";

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

test("a source links to the engine at the revision the map was read at, and to the viewer's own files on its branch", () => {
  // Files move on main (D188), and a published page must keep pointing at what it cited: so no link goes to a branch's tip
  // of the engine. The scene states its revision in short; the link carries the whole of it.
  assert.match(scene.meta.source_base_url, /\/blob\/[0-9a-f]{40}\/$/, "the engine's link base is not at a revision");
  assert.ok(scene.meta.source_base_url.includes(`/blob/${scene.meta.revision}`), "the link's revision is not the one the map states");
  assert.match(scene.meta.own_source_base_url, /\/blob\/visualizer\/$/, "the viewer's own link base is not its branch");
  const model = new SceneModel(scene);
  assert.equal(model.sourceUrl({ path: "docs/DECISIONS.md" }), scene.meta.source_base_url + "docs/DECISIONS.md");
  assert.equal(model.sourceUrl({ path: "visualizer/docs/MOUSE.md" }), scene.meta.own_source_base_url + "visualizer/docs/MOUSE.md");
  // An older scene, which gives one base only, links as it always did.
  const older = new SceneModel({ ...scene, meta: { ...scene.meta, own_source_base_url: undefined } });
  assert.equal(older.sourceUrl({ path: "visualizer/docs/MOUSE.md" }), scene.meta.source_base_url + "visualizer/docs/MOUSE.md");
});

test("a cited source that is the viewer's own is a file of this folder", () => {
  // The extractor takes such a source on this folder's word (it reaches main with the branch's next merge):
  // a note that is cited and was never committed fails here, in a fresh checkout.
  const own = new Set(scene.entities.flatMap((entity) => entity.sources || []).map((source) => source.path).filter((file) => file.startsWith("visualizer/")));
  assert.ok(own.size > 0);
  for (const file of own) assert.ok(existsSync(path.join(ROOT, file.slice("visualizer/".length))), `${file} is cited and is not in this folder`);
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

// What the overlays flag as left out of the picture for now (`left_out`): the inventory and the
// engine keep it, the scene does not draw it. The inventory's units that are left out, and the rest.
const leftOutUnits = snapshot.units.filter((unit) => atlasOverlay.units[unit.id]?.left_out);
const drawnUnits = snapshot.units.filter((unit) => !atlasOverlay.units[unit.id]?.left_out);
const leftOutCapabilities = overlay.capabilities.filter((capability) => capability.left_out);

test("the protein atlas matches the inventory it was made from, less what is left out of the picture", () => {
  const stated = snapshot.inventory.counts;
  assert.equal(snapshot.units.length, stated.functional_units);
  assert.equal(units.length, drawnUnits.length);
  assert.deepEqual(units.map((unit) => unit.id).sort(), drawnUnits.map((unit) => `unit.${unit.id}`).sort());
  assert.equal(scene.proteins.counts.units, drawnUnits.length, "the page counts the units it draws");
  assert.equal(scene.proteins.counts.inventory_units, stated.functional_units, "and still knows how many the inventory has");
  const byMapping = Object.fromEntries(scene.proteins.mappings.map((item) => [item.id, item.count]));
  for (const mapping of atlasOverlay.mappings) {
    const out = leftOutUnits.filter((unit) => unit.status === mapping.inventory).length;
    assert.equal(byMapping[mapping.id], stated.functional_units_by_status[mapping.inventory] - out, `units that are ${mapping.inventory}`);
  }
  // A record counts where a unit that is drawn has it.
  const drawn = new Set(drawnUnits.map((unit) => unit.id));
  const shown = snapshot.laws.filter((law) => [law.unit, ...(law.also_in || [])].some((unit) => drawn.has(unit)));
  const laws = scene.proteins.evidence.reduce((sum, item) => sum + item.count, 0);
  assert.equal(laws, shown.length, "every law record of a drawn unit has one kind of evidence");
  assert.equal(shown.length, stated.records - (snapshot.laws.length - shown.length));
  assert.equal(scene.proteins.counts.laws, stated.laws - snapshot.laws.filter((law) => !shown.includes(law) && (law.record_type || "law") === "law").length);
});

test("what an overlay leaves out of the picture is named once in the scene, and nothing else points at it", () => {
  const listed = scene.left_out;
  assert.ok(Array.isArray(listed), "the scene has no list of what is left out: rebuild it");
  // A species held back from the picture for now is named there too, and is nowhere else in the scene.
  const held = Object.keys(overlay.species_held || {});
  // A part whose files all stand in the map's legacy folder is left out by that rule, with its reason (the user, 17 November 2026).
  const legacyParts = listed.filter((item) => item.kind === "component");
  for (const item of legacyParts) {
    assert.ok(overlay.legacy && overlay.components.some((part) => part.id === item.id), `${item.id} is left out as legacy code, yet the map has no such part or no legacy rule`);
    assert.equal(item.reason, item.files ? overlay.legacy.reason : "its source was removed from the engine");
    assert.equal(item.since, overlay.legacy.since);
  }
  const expected = [...leftOutCapabilities.map((item) => item.id), ...leftOutUnits.map((unit) => `unit.${unit.id}`), ...held.map((id) => `species.${id}`), ...legacyParts.map((item) => item.id)];
  for (const id of held) {
    assert.ok(!scene.species.some((item) => item.id === id), `${id} is held back, yet the scene lists it as a species`);
    assert.ok(!scene.proteins.atlases.some((item) => item.id === id) && !scene.proteins.shelves.some((item) => item.id === id), `${id} is held back, yet the scene carries its atlas or its proteins`);
  }
  assert.deepEqual(listed.map((item) => item.id).sort(), [...expected].sort());
  const ids = new Set(scene.entities.map((entity) => entity.id));
  for (const item of listed) {
    assert.ok(!ids.has(item.id), `${item.id} is left out, yet it is a part of the scene`);
    assert.ok(!scene.relations.some((relation) => relation.from === item.id || relation.to === item.id), `${item.id} is left out, yet a link points at it`);
    assert.match(item.since, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(item.says?.trim() && item.reason?.trim() && item.label?.trim(), `${item.id} does not say what it is and why it is left out`);
    assert.ok(!("why" in item), "the overlay's own record of why stays in the overlay");
  }
  // A capability that is left out names its part of the cell, so the cell view does not draw it as scenery.
  for (const capability of leftOutCapabilities) assert.equal(listed.find((item) => item.id === capability.id).part, capability.part);
  // No species keeps a place for it in the scene, and no district, site or kind of evidence stays that only it held.
  for (const species of scene.species || []) for (const capability of leftOutCapabilities) assert.ok(!(capability.id in (species.cell.capabilities || {})), `${species.id} still names a place for ${capability.id}`);
  for (const district of scene.proteins.districts) assert.ok(units.some((unit) => unit.district === district.id) || !leftOutUnits.length, `the district ${district.id} holds no unit that is drawn`);
  for (const site of scene.proteins.sites) assert.ok(units.some((unit) => unit.site === site.id) || !leftOutUnits.length, `the site ${site.id} holds no unit that is drawn`);
  for (const item of scene.proteins.evidence) assert.ok(item.count > 0 || !leftOutUnits.length, `the evidence ${item.id} is of no record that is drawn`);
});

test("the page says once that a unit of the inventory is not drawn, and its numbers are of what is drawn", () => {
  const { proteins } = scene;
  const said = /The inventory has (\d+) units\. (\w+) of them, (.+), (?:is|are) left out of the picture for now: (.+?)\./;
  if (!leftOutUnits.length) {
    assert.ok(!/left out of the picture/.test(JSON.stringify(proteins)), "nothing is left out, yet the atlas says something is");
    return;
  }
  // The atlas's own summary, which the inventory's card shows, says it; each species' atlas says it under how it was made.
  const [, total, , named, reason] = said.exec(proteins.summary) || [];
  assert.equal(Number(total), snapshot.units.length, proteins.summary);
  for (const unit of leftOutUnits) {
    const flag = atlasOverlay.units[unit.id].left_out;
    assert.ok(named.includes(flag.says) && reason.includes(flag.reason), `the summary does not name ${unit.id} as its flag says it`);
  }
  for (const atlas of proteins.atlases) {
    assert.equal(atlas.counts.units, drawnUnits.length, `${atlas.id}: units counted`);
    const line = (atlas.method || []).at(-1) || "";
    assert.match(line, said, `${atlas.id} does not say that a unit is left out`);
    assert.ok(line.endsWith(`The ${drawnUnits.length} others are shown and counted here.`), line);
    if (atlas.findings) assert.equal(atlas.findings.reduce((sum, item) => sum + item.count, 0), drawnUnits.length, `${atlas.id}: one finding for each unit drawn`);
  }
});

test("while the protein cage is left out, nothing outside the Engine view names a cage but the sentence that says so", () => {
  const caged = (scene.left_out || []).filter((item) => /cage/i.test(`${item.says} ${item.label}`));
  if (!caged.length) return; // the cage is back in the picture
  const lensOf = new Map(scene.groups.map((group) => [group.id, group.lens]));
  const found = [];
  const walk = (node, where) => {
    if (typeof node === "string") {
      if (/\bcages?\b|capsid|\bmi3\b/i.test(node) && !/left out of the picture for now/.test(node)) found.push(`${where}: ${node.slice(0, 80)}`);
    } else if (Array.isArray(node)) node.forEach((item, index) => walk(item, `${where}[${index}]`));
    else if (node && typeof node === "object") for (const [key, value] of Object.entries(node)) walk(value, `${where}.${key}`);
  };
  for (const entity of scene.entities) if (lensOf.get(entity.group) !== "engine") walk(entity, entity.id);
  walk(scene.proteins, "proteins");
  walk(scene.species, "species");
  walk(scene.model_groups, "model_groups");
  walk(scene.representations, "representations");
  assert.deepEqual(found, []);
  // The engine keeps its assembly models on the map, and they say that the cage is not drawn elsewhere.
  for (const capability of leftOutCapabilities) {
    for (const target of capability.implemented_by || []) {
      const part = scene.entities.find((entity) => entity.id === target);
      assert.ok(part, `${target} is still on the Engine view`);
      if (capability.left_out.engine_note) assert.ok(part.plain.endsWith(capability.left_out.engine_note), `${target} does not say that ${capability.id} is left out`);
    }
  }
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
    // A unit whose laws all stand in held legacy code, which the map leaves out, links to no part, and the stamp says so.
    const inLegacy = (scene.proteins.stamp.in_legacy || {})[unit.id.replace("unit.", "")];
    const historical = unit.sections.find(section => section.key === "laws").items
      .every(item => item.lines.some(line => line === `Historical inventory record at ${scene.proteins.stamp.read_at}.`));
    const cited = unit.sources.some(source => source.revision === scene.proteins.stamp.read_at);
    assert.ok(links.length || inLegacy?.length || (historical && cited), `${unit.id} needs a current engine link or pinned inventory sources`);
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
    // The frog's one named dependence may stand in the scene alone; the snapshot and the units are held as before.
    assert.ok(name === "scene" ? xenbaseFree(JSON.stringify(data)) : !/xenbase|XB-GENE/i.test(JSON.stringify(data).replace(/No Xenbase data/g, "")), `Xenbase content in the ${name}`);
  }
  assert.ok(snapshot.sources.some((source) => source.name === "UniProt" && source.licence === "CC BY 4.0" && source.release), "the UniProt notice with its release");
});

// The one way Xenbase may stand in the scene: the frog's shelves name it as the source behind the gene names UniProt gives,
// read through UniProt (decided on 19 November 2026), and the scene carries that source as exactly this entry. Every other
// mention fails: an identifier, a link, a second source naming it, the entry with anything more, the word anywhere else.
const NAMED_XENBASE = '{"name":"Xenbase","class":"non-commercial","through":"UniProt"}';
const xenbaseFree = (text) => !/xenbase|XB-GENE/i.test(text.replace(/No Xenbase data/g, "").replaceAll(NAMED_XENBASE, ""));

test("the scene names Xenbase only as the frog's dependence read through UniProt, in that one exact entry", () => {
  const entry = JSON.parse(NAMED_XENBASE);
  const planted = (sources, more = {}) => JSON.stringify({ shelves: [{ id: "xenopus", ...more, sources }] });
  assert.ok(xenbaseFree(planted([{ name: "UniProt", class: "permissive" }, entry])), "the one exact entry stands");
  assert.ok(!xenbaseFree(planted([{ ...entry, url: "https://www.xenbase.org/" }])), "the entry with its address");
  assert.ok(!xenbaseFree(planted([{ ...entry, holds: "gene names" }])), "the entry with anything more");
  assert.ok(!xenbaseFree(planted([entry, { name: "Xenbase", class: "non-commercial", through: "UniProt and InterPro" }])), "a second source naming it, with other fields");
  assert.ok(!xenbaseFree(planted([entry], { from: "gene names from Xenbase" })), "the word elsewhere");
  assert.ok(!xenbaseFree(planted([entry, { name: "UniProt", class: "permissive", id: "XB-GENE-1" }])), "an identifier (made up)");
  assert.ok(!xenbaseFree(planted([entry], { link: "https://www.xenbase.org/made-up-page" })), "a link");
  // The scene as built holds it once, from the frog's shelves, and the frog's atlas names no Xenbase.
  assert.equal(JSON.stringify(scene.proteins.shelves).split(NAMED_XENBASE).length - 1, (scene.proteins.shelves || []).some((item) => item.id === "xenopus") ? 1 : 0);
  assert.ok(!/xenbase/i.test(JSON.stringify((scene.proteins.atlases || []).find((atlas) => atlas.id === "xenopus") || {})), "the frog's atlas names Xenbase");
});

test("a species atlas links out only to its named sources, over https", () => {
  // The hosts a species' side of the atlas may link to: the databases its ids name, the
  // papers it cites, and the home pages of the sources it states.
  const allowed = ["www.uniprot.org", "www.rcsb.org", "parasite.wormbase.org", "www.ebi.ac.uk", "europepmc.org", "pubmed.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "doi.org"];
  const links = [];
  const collect = (node, where) => {
    if (Array.isArray(node)) return node.forEach((item) => collect(item, where));
    if (!node || typeof node !== "object") return;
    if (typeof node.url === "string") links.push([where, node.url]);
    for (const value of Object.values(node)) collect(value, where);
  };
  for (const unit of units) collect(unit.species, unit.id);
  collect(scene.proteins.atlases, "atlases");
  for (const [where, link] of links) {
    const url = new URL(link);
    assert.equal(url.protocol, "https:", `${where}: ${link}`);
    assert.ok(allowed.includes(url.hostname), `${where}: ${link}`);
  }
  const others = (scene.proteins.atlases || []).filter((atlas) => !atlas.reference);
  if (others.length) assert.ok(links.length > 0, "a species atlas should carry its links out");
  // Each further species states where its entries came from and under what terms.
  for (const atlas of others) {
    assert.ok(atlas.sources.length > 0, `${atlas.id} names no source`);
    for (const source of atlas.sources) assert.ok(source.name && source.licence, `${atlas.id}: a source without a name or its terms`);
    assert.ok(!/xenbase|XB-GENE/i.test(JSON.stringify(atlas)), `Xenbase content in the ${atlas.id} atlas`);
  }
});

test("the scene carries the species the page can show, each with its shapes", () => {
  const species = scene.species || [];
  assert.ok(species.length > 0, "the scene names no species: rebuild it");
  assert.equal(species.filter((item) => item.default).length, 1, "exactly one species is the one the page opens on");
  for (const item of species) {
    // No species is said to be modelled: the record names no registered model of an organism. A word below it is the ladder's (schema/ENTRIES.md).
    assert.ok(["generic", "proposed", "planned", "designed"].includes(item.modelled.state), `${item.id} is said to be modelled`);
    assert.ok(item.modelled.text?.trim(), `${item.id} does not say what Cells models of it`);
    for (const level of item.levels) if (level.shape?.ref) assert.ok(scene.shapes?.[level.shape.ref], `${item.id}: no shape ${level.shape.ref}`);
    // Each with its cell types, its own first, and the one the page opens on (schema/CELL_TYPES.md).
    assert.ok(item.cell_types?.[0]?.own && item.cell_types.some((type) => type.id === item.default_cell_type), `${item.id}: its cell types, its own first, and its default`);
  }
  // The model systems beside them (schema/MODEL_SYSTEMS.md): each a model, not an organism, under a heading of its own, never modelled before the record says so.
  for (const item of scene.models || []) {
    assert.equal(item.kind, "model system");
    assert.ok(item.group && item.is && !("organism" in item) && !("cell" in item), `${item.id}: a model system has a heading and its line, and nothing of an organism`);
    assert.ok(["proposed", "planned", "designed"].includes(item.modelled.state) || (item.modelled.state === "modelled" && /@\d+$/.test(item.modelled.model || "") && item.modelled.record?.length > 0), `${item.id} is said to be modelled with no registered model or no line of the record`);
    for (const run of item.runs || []) assert.ok(run.path && !run.path.startsWith("data/"), `${item.id}: its run ${run.file} has the path it is published at`);
  }
});

test("the scene names each species' own proteins by file, with counts and sources, and holds none of them", () => {
  const shelves = scene.proteins.shelves || [];
  assert.ok(shelves.length > 0, "the scene names no species' proteins: rebuild it");
  for (const item of shelves) {
    assert.match(item.file, /^proteins\/[a-z0-9_-]+\/shelves\.json$/);
    assert.equal(Object.values(item.counts).reduce((sum, n) => sum + n, 0), item.proteins, item.id);
    assert.ok(item.sources.length > 0 && item.sources.every((source) => source.name && source.class), item.id);
    assert.ok(JSON.stringify(item).length < 3000, `${item.id}: a species' summary stays under 3,000 characters: its proteins and its sources in full are beside the page, not in the scene`);
  }
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
  // The page names no path of the machine it was built on. The bundler writes each module's path above it, and a library
  // linked from another folder was named by that folder's path until 19 November 2026; the build now names every module
  // from this folder and refuses a script that names one outside it (tools/lib/build_page.mjs, bundle).
  for (const part of ["/home/", "/mnt/", "/Users/", "\n// ../"]) assert.ok(!page.includes(part), `a path of the build's machine stands in the page (${JSON.stringify(part)})`);
  assert.ok(page.includes("\n// node_modules/three/examples/jsm/"), "the libraries bundled into the page are named from this folder");
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
    const model = new SceneModel(sceneOf(linked));
    const files = model.raw.proteins.evidence_files;
    const embedded = new Map([...inline.matchAll(/<script type="application\/json" data-file="([^"]+\/unit-evidence\.json)">(.*?)<\/script>/gs)].map(([, file, json]) => [file, JSON.parse(json)]));
    assert.deepEqual([...embedded.keys()].sort(), Object.values(files).sort());
    assert.ok(!linked.includes('/unit-evidence.json">'), "a web page loads the detailed evidence on selection");
    for (const [species, file] of Object.entries(files)) {
      const units = scene.entities.filter((entity) => entity.kind === "unit" && entity.species?.[species]);
      let reads = 0;
      const read = (requested) => {
        assert.equal(requested, file);
        reads++;
        return embedded.get(requested);
      };
      const entry = model.requestUnitEvidence(units[0].id, species, read);
      assert.equal(model.requestUnitEvidence(units[1].id, species, read), entry);
      await entry.ready;
      assert.equal(entry.status, "ready");
      assert.equal(reads, 1);
      for (const unit of units) {
        const summary = model.get(unit.id).species[species];
        assert.equal(summary.items, undefined);
        assert.deepEqual({ ...summary, ...entry.units[unit.id] }, unit.species[species]);
        const shown = inSpecies(model.get(unit.id), model.raw.proteins, species);
        assert.deepEqual(shown.finding, inSpecies(unit, scene.proteins, species).finding);
        assert.deepEqual(shown.sections.find((section) => section.key === "products").items, unit.species[species].items);
      }
    }
    // A page exported without the Experiments view keeps its replays (the cell view's flux reads a species' looping run from
    // them) and says the view is hidden; the page's list of views offers Experiments only where it is not.
    assert.equal(sceneOf(linked).replays.hidden, undefined, "by default the view is offered");
    const fromSnapshot = JSON.parse(JSON.stringify(sceneOf(linked).replays));
    fromSnapshot.experiments[0].engine_entities = ["op.scheduled_cell_replacement@1"];
    const translated = sceneOf(await buildPage({replays: fromSnapshot})).replays.experiments[0];
    assert.deepEqual(translated.engine_entities, ["op.cells.operator.scheduled_cell_replacement@1"]);
    assert.deepEqual(fromSnapshot.experiments[0].engine_entities, ["op.scheduled_cell_replacement@1"]);
    const hidden = await buildPage({ runsDir: runs, hideExperiments: true });
    assert.equal(sceneOf(hidden).replays.hidden, true);
    assert.equal(sceneOf(hidden).replays.runs[0].id, "x--arm--seed1", "the replays stay with the page");
    const viewer = await readFile(path.join(ROOT, "src", "ui", "viewer.js"), "utf8");
    assert.match(viewer, /id: "experiments"[^\n]*needs: \(scene\) => scene\.replays\?\.runs\?\.length && !scene\.replays\.hidden/, "the view is offered only where the scene does not hide it");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("every engine part an experiment's replays point at is on the map", async () => {
  const replayOverlay = JSON.parse(await readFile(path.join(ROOT, "data", "replays", "overlay.json"), "utf8"));
  const ids = new Set(scene.entities.map((entity) => entity.id));
  const tracked = new Set(scene.entities.flatMap((entity) => (entity.sources || []).map((source) => source.path)));
  for (const [name, experiment] of Object.entries(replayOverlay.experiments)) {
    for (const id of experiment.engine_entities) assert.ok(ids.has(id), `${name}: ${id} is not a part of the scene`);
    assert.ok(experiment.label && experiment.plain && experiment.sources.length, `${name} needs a label, a plain line and a source`);
    assert.ok((experiment.classes || []).every((item) => item.id && item.label && item.description), `${name}: every class is described`);
    // An example has invented numbers (schema/QUANTITY_LAYERS.md, rule 6): nothing was found, no part of the engine stands behind it, and it has no class.
    if (experiment.example === true) {
      assert.ok(!experiment.outcome && !experiment.classes && !experiment.development && experiment.engine_entities.length === 0, `${name}: an example has no outcome, no class and no engine part`);
      assert.ok(/invented numbers/.test(experiment.label) && experiment.plain.startsWith("Invented numbers") && !/example/i.test(`${experiment.label} ${experiment.plain}`), `${name}: invented numbers say so in their name and in their first words, and never "example" (18 November 2026)`);
      continue;
    }
    // What an experiment found is the record's, so it must say where the record says it.
    const outcome = experiment.outcome;
    assert.ok(outcome, `${name} says nothing about what it found`);
    assert.equal(typeof outcome.judged, "boolean", `${name}: judged or not`);
    assert.ok(outcome.status && outcome.text && outcome.sources?.length, `${name}: its outcome needs a status, the record's line and a source`);
    assert.ok(outcome.judged ? ["yes", "no", "mixed"].includes(outcome.answer) && outcome.label : outcome.answer === null, `${name}: an answer only where something is judged`);
  }
  assert.ok(tracked.size > 0);
});

