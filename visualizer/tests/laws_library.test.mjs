// The Laws library (schema/LAWS_LIBRARY.md): its list held to the contract and, where the main
// checkout is there to ask, to the code it was read from; and its view driven as the page drives
// a view, with stand-ins for the stage and the labels. No WebGL: the view only makes objects.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { LAWS_FORMAT, Library, problemsOf, namespaced } from "../src/lenses/laws_data.js";
import { LawsLens, LAWS_LOOK, LAWS_BLOOM, LAWS_BLOOM_LIGHT, MARKS } from "../src/lenses/laws.js";
import { plaquesOf, longDate } from "../src/lenses/laws_marks.js";
import { PER_BAND } from "../src/lenses/laws_layout.js";
import { LAWS_CSS } from "../src/lenses/laws_styles.js";
import { sections as listSections } from "../src/lenses/laws_card.js";

const raw = JSON.parse(readFileSync(path.join(ROOT, "data", "laws", "pieces.json"), "utf8"));
const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "laws", "overlay.json"), "utf8"));
// The tests' oracle is the engine's own file, not the list made from it.
const MANIFEST_PATH = path.join(ROOT, "data", "engine", "declarations.json");
const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf8"));
const contract = readFileSync(path.join(ROOT, "schema", "LAWS_LIBRARY.md"), "utf8");
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const library = new Library(raw);
const byId = new Map(library.pieces.map((piece) => [piece.id, piece]));
const frameById = new Map(library.frames.map((frame) => [frame.id, frame]));
const tool = (args) => spawnSync("python3", ["-I", path.join(ROOT, "tools", "extract_laws.py"), ...args], { encoding: "utf8" });

// ------------------------------------------------------------ the list, held to the manifest

test("the list is the manifest's: every piece and model of the engine's file, carried unchanged, and nothing else declared", () => {
  assert.equal(raw.format, LAWS_FORMAT);
  assert.deepEqual(problemsOf(raw), []);
  assert.equal(raw.stamp.generator, "visualizer/tools/extract_laws.py");
  assert.deepEqual(raw.stamp.manifest, { path: "data/engine/declarations.json", kind: manifest.kind, revision: manifest.revision, short: manifest.revision.slice(0, 8), dirty: false, origin: manifest.origin });
  assert.equal(raw.stamp.read, `Read from the engine's declarations at main ${manifest.revision.slice(0, 8)}`);
  assert.ok(!MACHINE.test(JSON.stringify(raw)), "a machine path leaked into the list");
  // Every piece of the manifest, once, unchanged; every declared piece of the list is one of them.
  const declared = raw.pieces.filter((piece) => piece.where === "declared");
  assert.deepEqual(declared.map((piece) => piece.declared), manifest.pieces);
  assert.deepEqual(declared.map((piece) => piece.id), manifest.pieces.map((piece) => piece.declared_id));
  assert.deepEqual(raw.models.map((model) => model.declared), manifest.models);
  assert.deepEqual([raw.legacy, raw.not_extracted], [manifest.legacy, manifest.not_extracted]);
  // Anything else on the wall is a design note's, and declares nothing.
  for (const piece of raw.pieces.filter((item) => item.where !== "declared")) assert.ok(piece.where === "design" && piece.declared === null, piece.id);
  assert.equal(raw.counts.pieces, manifest.pieces.length);
  assert.equal(library.counts().declared, manifest.pieces.length);
  for (const family of raw.families) assert.equal(raw.counts.by_family[family.id], raw.pieces.filter((piece) => piece.family === family.id).length, family.id);
  // No level from any other record: the manifest gives none today, and the list adds none.
  for (const piece of raw.pieces) assert.ok(!("status" in piece) && !piece.box?.level, `${piece.id}: a level that is not the manifest's`);
  assert.ok(contract.includes(LAWS_FORMAT), "the contract names the list's format");
});

test("making the list again from the manifest gives the committed bytes", () => {
  const run = tool(["--out", "-"]);
  assert.equal(run.status, 0, run.stderr);
  assert.equal(run.stdout, readFileSync(path.join(ROOT, "data", "laws", "pieces.json"), "utf8"));
});

test("the reader refuses another major of the manifest, a tree that was not clean, and a revision that is not whole", () => {
  mkdirSync(path.join(ROOT, "out"), { recursive: true });
  const scratch = mkdtempSync(path.join(ROOT, "out", "laws-reader-"));
  try {
    for (const [change, says] of [
      [{ kind: "cells.declarations@3" }, /another major/],
      [{ kind: "cells.declarations@1" }, /another major/],
      [{ kind: "something.else@2" }, /not a cells\.declarations manifest/],
      [{ dirty: true }, /not clean/],
      [{ dirty: null }, /not clean/],
      [{ revision: manifest.revision.slice(0, 8) }, /not a full Git revision/],
    ]) {
      const file = path.join(scratch, "declarations.json");
      writeFileSync(file, JSON.stringify({ ...manifest, ...change }));
      const run = tool(["--manifest", file, "--out", path.join(scratch, "pieces.json")]);
      assert.equal(run.status, 2, JSON.stringify(change));
      assert.match(run.stderr, says, JSON.stringify(change));
      assert.ok(!existsSync(path.join(scratch, "pieces.json")), "nothing is written");
    }
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
  // The view refuses a list read from another major, or from a tree that was not clean, as well.
  assert.throws(() => new Library({ ...raw, stamp: { ...raw.stamp, manifest: { ...raw.stamp.manifest, kind: "cells.declarations@3" } } }), /not cells\.declarations@2/);
  assert.throws(() => new Library({ ...raw, stamp: { ...raw.stamp, manifest: { ...raw.stamp.manifest, dirty: true } } }), /not clean/);
});

test("a manifest that gains pieces takes no change: a model family with rows of its own, its laws and operators of its own interfaces", async () => {
  const { describe } = await import("../src/lenses/laws_card.js");
  const grown = JSON.parse(JSON.stringify(manifest));
  const law = { ...JSON.parse(JSON.stringify(manifest.pieces.find((piece) => piece.declared_id === "kv1p5_mh@1"))), id: "cells.lineage_split@1", declared_id: "cells.lineage_split@1", name: "lineage_split", interface: "cells.lineage_law@1", host: "cells.assembly_lineages@1", declared_host: "cells.assembly_lineages@1", family: "cells.assembly_lineages@1", models: ["cells.assembly_lineages@1"], reads: null, changes: null, fields: { rate: 1 }, provenance: { tag: "cited", citation: null, source: null }, units: {}, signs: {} };
  const operator = { ...JSON.parse(JSON.stringify(law)), id: "cells.lineage_census@1", declared_id: "cells.lineage_census@1", name: "lineage_census", piece: "operator", interface: "cells.lineage_operator@1", fields: {} };
  grown.pieces.push(law, operator);
  grown.models.find((model) => model.id === "cells.assembly_lineages@1").rows = [
    { role: "law", id: law.id, declared_id: law.declared_id, piece: "law", slot: null },
    { role: "operator", id: operator.id, declared_id: operator.declared_id, piece: "operator", slot: null },
  ];
  mkdirSync(path.join(ROOT, "out"), { recursive: true });
  const scratch = mkdtempSync(path.join(ROOT, "out", "laws-grown-"));
  try {
    const file = path.join(scratch, "declarations.json");
    writeFileSync(file, JSON.stringify(grown));
    const run = tool(["--manifest", file, "--out", path.join(scratch, "pieces.json")]);
    assert.equal(run.status, 0, run.stderr);
    const list = JSON.parse(readFileSync(path.join(scratch, "pieces.json"), "utf8"));
    assert.equal(list.pieces.filter((piece) => piece.where === "declared").length, manifest.pieces.length + 2);
    const grownLibrary = new Library(list);
    assert.equal(grownLibrary.piece("cells.lineage_split@1").family, "law", "a family's own law stands among the laws");
    assert.equal(grownLibrary.piece("cells.lineage_census@1").family, "operator", "a family's own operator among the operators");
    const frame = grownLibrary.frame("cells.assembly_lineages@1");
    assert.ok(grownLibrary.racks.includes(frame) && !grownLibrary.cases.includes(frame), "a family with rows is a rack");
    assert.deepEqual(grownLibrary.piece("cells.lineage_split@1").declared_by, [{ frame: "cells.assembly_lineages@1", how: "direct" }]);
    // A family's own law: kernels, provenance and test apply; reads and changes do not (they are cells laws' keys).
    assert.equal(grownLibrary.nullMeaning(grownLibrary.piece("cells.lineage_split@1"), "reads"), "not applicable");
    assert.equal(grownLibrary.nullMeaning(grownLibrary.piece("cells.lineage_census@1"), "test"), "not stated");
    const said = describe(grownLibrary, "laws:cells.lineage_census@1");
    assert.match(said.eyebrow, /operator of its model family's own interface/);
    // And the view draws it: a bar on the wall and a card in its rack.
    const lens = new LawsLens(lensFor().stage, { raw: { laws: list } }, { add: () => ({ element: { classList: { toggle() {}, add() {}, remove() {} }, style: {} } }), clear() {}, remove() {} });
    assert.ok(lens.layout.bars.some((bar) => bar.id === "cells.lineage_split@1"));
    assert.ok(lens.cardList.some((card) => card.piece === "cells.lineage_census@1" && card.frame === "cells.assembly_lineages@1"));
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
});

test("each model's rows are its rows in the manifest: their roles, their slots, the next free code, and a row with no piece", () => {
  for (const model of manifest.models) {
    const frame = library.frame(model.declared_id);
    assert.ok(frame, model.declared_id);
    const shown = frame.rows.flatMap((row) => [...row.pieces.map((id, index) => ({ id: namespaced(id), role: row.role, slot: row.tags[index] })), ...row.none.map((entry) => ({ id: namespaced(entry.id), role: row.role, slot: null }))]);
    const rows = model.rows.filter((row) => row.role !== "inner model").map((row) => ({ id: row.id, role: row.role, slot: row.slot ? Object.values(row.slot)[0] : null }));
    assert.deepEqual(new Set(shown.map((row) => JSON.stringify(row))), new Set(rows.map((row) => JSON.stringify(row))), model.declared_id);
    const inner = model.rows.find((row) => row.role === "inner model");
    if (inner) assert.equal(frame.inner, inner.declared_id);
    if (model.type === "family" && !model.rows.length) assert.ok(library.cases.includes(frame), `${model.declared_id} is a closed case`);
    else assert.ok(library.racks.includes(frame), `${model.declared_id} is a rack`);
  }
  const inner = library.frames.find((frame) => frame.kind === "inner model");
  const channels = inner.rows.find((row) => row.role === "channel law");
  assert.equal(channels.next_code, manifest.models.find((model) => model.type === "inner").next_code);
  assert.deepEqual(channels.tags, manifest.models.find((model) => model.type === "inner").rows.filter((row) => row.role === "channel law").map((row) => row.slot.code));
  // The fuel kind is a row with no piece of its own: said as such.
  assert.deepEqual([...library.rowOnly.keys()], manifest.models.flatMap((model) => model.rows.filter((row) => row.piece === null).map((row) => row.id)));
});

test("what declares a piece follows the manifest: its own row, the kind that hosts it, or the inner model a model holds", () => {
  for (const piece of library.pieces.filter((item) => item.where === "declared")) {
    const d = piece.declared;
    assert.ok(piece.declared_by.length, `${piece.id}: some model declares it`);
    for (const entry of piece.declared_by) {
      const frame = frameById.get(entry.frame);
      if (entry.how === "direct") assert.ok(frame.declared.rows.some((row) => row.id === d.id), `${piece.id}: a row of ${entry.frame}`);
      if (entry.how === "kind") assert.equal(namespaced(entry.via), d.host, `${piece.id}: hosted by ${entry.via}`);
      if (entry.how === "inner") assert.equal(namespaced(frame.inner), d.family, `${piece.id}: of the inner model ${entry.frame} holds`);
    }
    // Every model the manifest lets declare it does.
    for (const model of d.models) assert.ok(piece.declared_by.some((entry) => namespaced(entry.frame) === model), `${piece.id}: ${model}`);
  }
});

test("a design note's laws are kept only where the note still names them at the manifest's revision, apart from the declared pieces", (t) => {
  const designed = library.pieces.filter((piece) => piece.where === "design");
  assert.equal(designed.length, overlay.designed.length);
  for (const piece of designed) {
    assert.ok(!manifest.pieces.some((item) => namespaced(item.declared_id) === namespaced(piece.id)), `${piece.id} is not declared`);
    assert.equal(library.familyById.get(piece.family).shelf, "design", `${piece.id} stands on the shelf apart`);
  }
  const common = spawnSync("git", ["-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8" }).stdout.trim();
  const repo = common ? path.dirname(common) : null;
  if (!repo || spawnSync("git", ["-C", repo, "cat-file", "-e", `${manifest.revision}^{commit}`]).status !== 0) return t.skip("the main checkout, or the manifest's revision, is not here to ask");
  const files = new Map();
  for (const piece of designed)
    for (const note of piece.named_in) {
      if (!files.has(note.path)) files.set(note.path, spawnSync("git", ["-C", repo, "show", `${manifest.revision}:${note.path}`], { encoding: "utf8", maxBuffer: 1 << 26 }).stdout.split("\n"));
      assert.ok(files.get(note.path)[note.line - 1]?.includes(piece.id), `${note.path}:${note.line} does not name ${piece.id} at ${manifest.revision}`);
    }
});

test("the three meanings of null, as the format page defines them, and an empty list as none", async () => {
  const { describe } = await import("../src/lenses/laws_card.js");
  const kv = library.piece("kv1p5_mh@1");
  const kind = library.piece("cells.transporter@1");
  const operator = library.piece("ideal_osmosis_linear_compliance_water@1");
  // Not applicable: a law owns nothing and a kind has no kernels; nothing is said.
  assert.equal(library.nullMeaning(kv, "owns"), "not applicable");
  assert.equal(library.nullMeaning(kind, "kernels"), "not applicable");
  // Not extracted: the pair is in not_extracted.
  assert.equal(library.nullMeaning(kv, "energy"), "not extracted");
  assert.equal(library.nullMeaning(kind, "provenance"), "not extracted");
  assert.equal(library.nullMeaning(operator, "test"), "not extracted");
  // Not stated: the key applies, and the declaration does not state it.
  assert.equal(library.nullMeaning(kv, "test"), "not stated");
  const facts = (piece) => new Map(describe(library, `laws:${piece.id}`).facts);
  assert.equal(facts(kv).get("Test"), "not stated");
  assert.equal(facts(kv).get("Energy"), "not yet extracted in the engine's declarations");
  assert.ok(!facts(kv).has("Owns"), "nothing is said of what does not apply");
  assert.equal(facts(kind).get("Provenance"), "not yet extracted in the engine's declarations");
  assert.ok(!facts(kind).has("Kernels"));
  // An empty list: the declaration lists none.
  assert.equal(facts(kv).get("Reads"), "the declaration lists none");
  // A nested null keeps its field's own meaning: a leak law with no gate has no RK4 step bound; an operator with no split part, no step method.
  assert.equal(facts(library.piece("kleak_always_open@1")).get("Reference RK4 step bound"), "none: a law with no gate");
  assert.equal(facts(library.piece("cell_owned_compartments@1")).get("Step method"), "none");
  const label = { kernels: "Kernels", provenance: "Provenance", test: "Test", reads: "Reads", changes: "Changes", owns: "Owns", writes: "Writes", provides: "Provides", controls: "Controls", ledgers: "Ledgers", energy: "Energy", units: "Units", signs: "Signs", requires: "Requires", laws: "Laws it hosts" };
  // Held on every piece: a null key is said by its meaning, and never by a value.
  for (const piece of library.pieces.filter((item) => item.where === "declared")) {
    const said = facts(piece);
    for (const key of Object.keys(label)) {
      if (piece.declared[key] !== null) continue;
      const meaning = library.nullMeaning(piece, key);
      if (meaning === "not applicable") assert.ok(!said.has(label[key]), `${piece.id}: ${key}`);
      else assert.equal(said.get(label[key]), meaning === "not extracted" ? "not yet extracted in the engine's declarations" : "not stated", `${piece.id}: ${key}`);
    }
    // No level anywhere today: the manifest gives none.
    assert.match(said.get("Status"), /^not stated/, piece.id);
  }
});

test("what the manifest has not exercised yet is said as the format page says it: a status with its source, a page, a work's DOI or URL, a calibrated piece, a scoped read, a piece outside the package", async () => {
  const { describe } = await import("../src/lenses/laws_card.js");
  const fixture = JSON.parse(JSON.stringify(raw));
  const kv = fixture.pieces.find((piece) => piece.id === "kv1p5_mh@1").declared;
  Object.assign(kv, {
    status: "established",
    status_source: "docs/SOME_RECORD.md",
    doc: "docs/library/cells/laws/kv1p5_mh@1.md",
    test: "tests/unit/test_kv1p5.py::test_planted",
    provenance: { tag: "calibrated", source: "a fit to recorded currents", citation: { source: "a paper", place: "table 2", licence: "CC BY 4.0", departures: ["one gate fewer"], works: [{ authors: ["A. Author"], year: 2001, title: "A title", doi: "10.1000/xyz", url: null }, { authors: ["B. Author"], year: 2002, title: "Another", doi: null, url: "https://example.org/b" }] } },
    reads: [{ name: "membrane_area", mode: "reference", stage: "inner", scoped: true }],
    module_path: null,
    line: null,
  });
  const other = new Library(fixture);
  const said = describe(other, "laws:kv1p5_mh@1");
  const facts = new Map(said.facts);
  assert.equal(facts.get("Status"), "established (from docs/SOME_RECORD.md)");
  assert.equal(facts.get("Page"), "docs/library/cells/laws/kv1p5_mh@1.md");
  assert.equal(facts.get("Test"), "tests/unit/test_kv1p5.py::test_planted");
  assert.equal(facts.get("Provenance"), "calibrated");
  assert.equal(facts.get("Rests on"), "a fit to recorded currents");
  assert.equal(facts.get("Departs from it"), "one gate fewer");
  assert.equal(facts.get("Declared in"), "cells.models.inner_laws, outside the cells package");
  const works = said.sections.find((section) => section.title === "Works").items;
  assert.deepEqual(works.map((work) => work.links.map((link) => link.url)), [["https://doi.org/10.1000/xyz"], ["https://example.org/b"]]);
  assert.equal(said.sections.find((section) => section.title === "Reads").items[0].detail, "reference, at the inner stage, only the slots it names");
  assert.ok(said.sources.some((source) => source.path === "docs/library/cells/laws/kv1p5_mh@1.md" && source.revision === manifest.revision), "the page links at the manifest's revision");
  assert.ok(!said.sources.some((source) => !source.path), "no link to a file outside the package");
  // Today: no page linked anywhere, and no level shown.
  for (const piece of library.pieces.filter((item) => item.where === "declared")) {
    const today = describe(library, `laws:${piece.id}`);
    assert.ok(!today.sources.some((source) => source.path.startsWith("docs/library/")), piece.id);
    assert.equal(today.status, null);
  }
});

// ------------------------------------------------------------ the view, without a browser

function lensFor({ moving = false, width = 1600, height = 1000, dark = false } = {}) {
  const shown = [];
  const labels = {
    shown,
    add: (spec) => {
      const item = { ...spec, hidden: false, element: { classList: { toggle() {}, add() {}, remove() {} }, style: {} } };
      shown.push(item);
      return item;
    },
    clear: () => shown.splice(0),
    remove: (item) => shown.splice(shown.indexOf(item), 1),
  };
  const palette = dark
    ? { ghost: "#8496a8", fg: "#e6edf3", plate: "#172836", edge: "#95a6b7", plateEdge: "#314a60", accent: "#5b9dee", bg: "#0b151e", dark: true }
    : { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", dark: false };
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const dressed = [], bloom = [], glows = new Set(), flights = [];
  const place = (view) => {
    camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance));
    camera.lookAt(view.target);
    camera.updateMatrixWorld();
  };
  const stage = {
    palette, scene: new THREE.Scene(), camera, width, height, reducedMotion: !moving, invalidate() {},
    rig: { setView: place, flyTo: (view) => flights.push(view), distance: 100 },
    dress: (fit) => dressed.push(fit),
    setBloom: (strength) => bloom.push(strength),
    glow: (object, on = true) => (on ? glows.add(object) : glows.delete(object)),
  };
  const lens = new LawsLens(stage, { raw: { laws: raw } }, labels);
  lens.activate();
  return { lens, stage, shown, dressed, bloom, glows, flights, place, camera };
}
const expectedSlots = (piece) => {
  const out = new Set();
  for (const entry of piece.declared_by) {
    const frame = frameById.get(entry.frame);
    if (entry.how === "inner") out.add(`${frame.id}|${entry.via}`);
    else frame.rows.forEach((row, r) => row.pieces.forEach((id, index) => id === (entry.how === "kind" ? entry.via : piece.id) && out.add(`${frame.id}|${r}|${index}`)));
  }
  return out;
};

test("the wall holds every piece of the list, a bar for each in its family's column", () => {
  const { lens } = lensFor();
  const bars = lens.layout.bars.filter((bar) => bar.id);
  assert.equal(bars.length, raw.pieces.length);
  assert.deepEqual(new Set(bars.map((bar) => bar.id)), new Set(raw.pieces.map((piece) => piece.id)));
  for (const family of raw.families) {
    assert.equal(bars.filter((bar) => bar.family === family.id).length, raw.pieces.filter((piece) => piece.family === family.id).length, family.id);
    assert.ok(bars.filter((bar) => bar.family === family.id).every((bar) => byId.get(bar.id).family === family.id), family.id);
  }
  // Each form is where the piece stands: solid where declared, an outline for a design note's.
  const form = { declared: "solid", design: "design" };
  for (const bar of lens.layout.bars) if (bar.id) assert.equal(bar.form, form[byId.get(bar.id).where], bar.id);
  // Every bar is one size: nothing on the wall is narrower or set apart within its column.
  const bars2 = lens.layout.bars.filter((bar) => bar.id);
  assert.equal(new Set(bars2.map((bar) => `${bar.w}|${bar.h}|${bar.d}`)).size, 1);
});

test("a chosen piece lights exactly the slots that declare it, and draws a line to each", () => {
  const { lens } = lensFor();
  for (const piece of library.pieces) {
    lens.setSelection(`laws:${piece.id}`);
    const lit = lens.lights();
    assert.deepEqual(new Set([...lit.cards, ...lit.blocks]), expectedSlots(piece), piece.id);
    assert.deepEqual([...lit.bars], [piece.id], `${piece.id}: only its own bar is lit`);
    assert.equal(lens.routes.length, expectedSlots(piece).size, `${piece.id}: one route to each slot`);
    assert.ok(lens.lines.children.length <= 1, `${piece.id}: all its routes are one mesh, one draw`);
  }
});

test("a chosen frame lights exactly its pieces on the wall", () => {
  const { lens } = lensFor();
  for (const frame of library.frames) {
    lens.setSelection(`laws:${frame.id}`);
    const expected = new Set(library.pieces.filter((piece) => piece.declared_by.some((entry) => entry.frame === frame.id)).map((piece) => piece.id));
    assert.deepEqual(lens.lights().bars, expected, frame.id);
    assert.equal(lens.routes.length, frame.rows.reduce((sum, row) => sum + row.pieces.length, 0), `${frame.id}: a route from each of its slots`);
  }
});

test("search, family and where narrow the wall; the arrow keys step through what passes", () => {
  const { lens } = lensFor();
  const families = new Map(raw.families.map((family) => [family.id, family.label]));
  const matches = (piece, words) => [piece.id, piece.declared?.id, piece.declared?.interface, piece.kind, piece.declared?.module_path, families.get(piece.family)].some((text) => text && String(text).toLowerCase().includes(words));
  const order = (keep) => raw.families.flatMap((family) => library.pieces.filter((piece) => piece.family === family.id && keep(piece))).map((piece) => `laws:${piece.id}`);
  for (const words of ["calcium", "kir2", "proton", "operators/", "inner_kinds", "cycle_law"]) {
    lens.setQuery(words);
    assert.deepEqual(lens.order(), order((piece) => matches(piece, words)), words);
    const found = lens.layout.bars.filter((bar) => bar.id && matches(byId.get(bar.id), words));
    for (const bar of found) {
      const slot = lens.barSlot.get(bar.id)[0];
      assert.ok(bar.form === "design" || lens.wall[slot.set].target[slot.index] > 0, `${bar.id} is found and stays flush`);
    }
  }
  lens.setQuery("");
  lens.setMark("split");
  assert.equal(lens.order().length, raw.pieces.filter((piece) => piece.family === "split").length);
  lens.setMark("all");
  lens.setMode("design");
  assert.deepEqual(lens.order(), order((piece) => piece.where === "design"));
  lens.setMode("all");
  lens.setSelection(null);
  const all = order(() => true);
  const first = lens.step(1);
  assert.equal(first, all[0]);
  lens.setSelection(first);
  assert.equal(lens.step(1), all[1]);
  assert.equal(lens.step(-1), all.at(-1));
});

test("every piece and every frame can be chosen by id; the list holds every id the view accepts", () => {
  const { lens } = lensFor();
  const listed = lens.sections().flatMap((section) => section.entities.map((entity) => entity.id));
  const expected = [...raw.pieces.map((piece) => piece.id), ...raw.models.map((model) => model.id), ...[...library.rowOnly.values()].map((row) => row.id), ...raw.legacy.map((item) => item.id)];
  assert.deepEqual(new Set(listed), new Set(expected.map((id) => `laws:${id}`)));
  assert.equal(listed.length, new Set(listed).size, "no id is listed twice");
  for (const id of listed) {
    assert.ok(lens.has(id), id);
    lens.setSelection(id);
    assert.equal(lens.selected, id);
    assert.ok(lens.describe(id)?.label, `${id}: the panel has nothing to say`);
  }
  assert.equal(lens.has("kv1p5_mh@1"), false, "a bare engine id is not this view's");
  // Either spelling of a declared ID names one piece (D185), and the view draws it by its declared spelling.
  lens.setSelection("laws:cells.kv1p5_mh@1");
  assert.equal(lens.selected, "laws:kv1p5_mh@1");
  lens.setSelection("laws:atp_driven_transporter_mass_action_positive@1");
  assert.equal(lens.selected, "laws:cells.atp_driven_transporter_mass_action_positive@1");
  // Any other ID is answered: the declarations do not list it.
  assert.equal(lens.has("laws:nothing@1"), true);
  assert.match(lens.describe("laws:nothing@1").plain, /^The engine's declarations do not list nothing@1/);
  assert.equal(lens.has("laws:not an id"), false);
  for (const section of lens.sections()) for (const entity of section.entities) assert.ok(typeof entity.keywords === "string", `${entity.id}: the list's search finds it by its words`);
});

test("a piece is chosen by pointer: a ray at its bar or its slot hits it", () => {
  const { lens } = lensFor();
  lens.root.updateMatrixWorld(true);
  const raycaster = new THREE.Raycaster();
  const pickAt = (point) => {
    raycaster.set(point.clone().add(new THREE.Vector3(0, 0, 40)), new THREE.Vector3(0, 0, -1));
    for (const hit of raycaster.intersectObjects([lens.root], true)) {
      let id = null, through = false;
      for (let node = hit.object; node; node = node.parent) {
        if (node.userData.unpickable) through = true;
        if (id === null && node.userData.pick) id = typeof node.userData.pick === "function" ? node.userData.pick(hit) : node.userData.pick;
      }
      if (!through && id) return id;
    }
    return null;
  };
  for (const id of ["kv1p5_mh@1", "cells.transporter@1", "ideal_osmosis_linear_compliance_water@1", "junction_ungated@1"]) assert.equal(pickAt(lens.barPoint(id)), `laws:${id}`, id);
  const card = lens.cardList.find((item) => item.piece === "nak_atp_mass_action_positive@1");
  assert.equal(pickAt(new THREE.Vector3(card.x, card.y, card.z)), "laws:nak_atp_mass_action_positive@1");
});

test("a piece's panel says what the manifest states of it, links its files at the manifest's revision, and shows no level it does not give", () => {
  const { lens } = lensFor();
  for (const piece of library.pieces.filter((item) => item.where === "declared")) {
    const d = piece.declared;
    const entity = lens.describe(`laws:${piece.id}`);
    const facts = new Map(entity.facts);
    assert.equal(entity.status, null, piece.id);
    assert.equal(facts.get("Interface"), d.interface, piece.id);
    assert.equal(facts.get("Family"), d.family, piece.id);
    assert.equal(facts.get("Models"), d.models.join(", "), piece.id);
    assert.equal(facts.get("Declared in"), `${d.module_path}, line ${d.line}`, piece.id);
    assert.match(facts.get("Status"), /^not stated/, piece.id);
    // Where it is declared, and each kernel, linked at the manifest's revision; nothing else of the engine's.
    const own = entity.sources.filter((source) => source.revision);
    assert.ok(own.every((source) => source.revision === manifest.revision), piece.id);
    assert.ok(own.some((source) => source.path === d.module_path && source.where.startsWith(`line ${d.line}`)), `${piece.id}: where it is declared`);
    for (const kernel of Object.values(d.kernels || {})) if (kernel.module_path) assert.ok(own.some((source) => source.path === kernel.module_path), `${piece.id}: its kernel ${kernel.function}`);
    assert.equal(entity.sources.length, own.length, `${piece.id}: no source but the manifest's`);
    // Its provenance tag in the format page's words; a citation with its place, licence and departures.
    if (d.provenance) assert.equal(facts.get("Provenance"), { parity: "moved from an older family (moving is not calibrating)", cited: "cited", calibrated: "calibrated" }[d.provenance.tag], piece.id);
    if (d.provenance?.citation) for (const label of ["Cited", "Where in it", "Licence", "Departs from it"]) assert.ok(facts.get(label), `${piece.id}: ${label}`);
    // Its interface's own fields, each by its name in the format page's words (or its own key where the page has none).
    const named = { code: "Code", gates: "Gates", rk4_step_s: "Reference RK4 step bound", moves: "Moves per forward cycle", model_key: "Definition key", parts: "Parts of the step", step_method: "Step method" };
    for (const key of Object.keys(d.fields)) if (named[key]) assert.ok(facts.has(named[key]), `${piece.id}: ${key}`);
  }
  for (const frame of library.frames) assert.equal(lens.describe(`laws:${frame.id}`).status, null, `${frame.id}: a model takes no status from its parts`);
});

test("it asks the stage for the page's look, and hands it back as it found it", () => {
  const { lens, dressed, stage } = lensFor();
  assert.deepEqual(dressed[0], LAWS_LOOK);
  for (const name of ["line", "ring", "lit"]) {
    assert.equal(lens.materials[name].toneMapped, false, `${name}: what is chosen stays out of filmic light`);
    assert.equal(lens.materials[name].userData.noContact, true, `${name}: and out of contact shade`);
  }
  lens.deactivate();
  assert.deepEqual(dressed.at(-1), { rich: false });
  assert.ok(!stage.scene.children.includes(lens.root));
});

test("only what is chosen glows: bloom is off at rest, and on only from the chosen, its slots and its routes", () => {
  const { lens, bloom, glows } = lensFor();
  assert.equal(bloom.at(-1), 0, "at rest nothing blooms");
  assert.deepEqual([...glows], [lens.shine], "the one thing marked to glow is the group of what is chosen");
  const shining = (() => {
    const out = [];
    lens.shine.traverse((object) => (object.isMesh || object.isLine) && out.push(object));
    return out;
  })();
  assert.equal(lens.litBars.mesh.count + lens.litSlots.mesh.count, 0, "and at rest it holds nothing to draw");
  const piece = byId.get("nak_atp_mass_action_positive@1");
  lens.setSelection(`laws:${piece.id}`);
  assert.equal(bloom.at(-1), LAWS_BLOOM_LIGHT.strength, "in the light theme, the light theme's bloom");
  assert.equal(lens.litBars.mesh.count, 1, "the chosen bar's lit copy");
  assert.equal(lens.litSlots.mesh.count, expectedSlots(piece).size, "a lit copy of each slot that declares it");
  for (const object of [...shining, ...lens.lines.children]) assert.ok([lens.litBars.mesh, lens.litSlots.mesh, lens.ring].includes(object) || object.parent === lens.lines, "nothing else is in the group that glows");
  // A design piece keeps its glass outline when chosen: no solid lit copy is drawn over it.
  const design = raw.pieces.find((item) => item.where === "design");
  lens.setSelection(`laws:${design.id}`);
  assert.equal(lens.litBars.mesh.count, 0, `${design.id}: a design piece is not drawn solid when chosen`);
  lens.setSelection(null);
  assert.equal(bloom.at(-1), 0, "letting go turns the bloom off");
  assert.equal(lens.litBars.mesh.count + lens.litSlots.mesh.count + lens.routes.length, 0);
  lens.setSelection(`laws:${piece.id}`);
  lens.deactivate();
  assert.equal(bloom.at(-1), 0, "leaving the view turns it off");
  assert.equal(glows.size, 0, "and unmarks what it marked");
});

test("a chosen rack in the light theme shines at its edges and rails, its cards still cards; in the dark it shines whole", () => {
  const id = "resolved_pump_composite@1";
  const at = (set, n) => {
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), scale = new THREE.Vector3();
    set.mesh.getMatrixAt(n, matrix);
    matrix.decompose(position, new THREE.Quaternion(), scale);
    return { z: position.z, d: scale.z, w: scale.x, h: scale.y };
  };
  const colourOf = (set, n) => {
    const colour = new THREE.Color();
    set.mesh.getColorAt(n, colour);
    return colour.getHexString();
  };
  const light = lensFor({ moving: false }), dark = lensFor({ moving: false, dark: true });
  for (const { lens, bloom } of [light, dark]) {
    lens.setSelection(`laws:${id}`);
    lens.update(16);
    const theme = lens.palette.dark ? "dark" : "light";
    const cards = lens.cardList.map((card, index) => ({ card, index })).filter(({ card }) => card.frame === id);
    const rails = lens.rails.items.filter((rail) => rail.id === `laws:${id}`).length;
    assert.equal(lens.litSlots.mesh.count, cards.length + 1 + (theme === "light" ? rails : 0), `${theme}: a lit copy for each card and the block${theme === "light" ? ", and each rail" : ""}`);
    const accent = new THREE.Color(lens.palette.accent).getHexString();
    for (const { index } of cards) assert.equal(colourOf(lens.slots, index) === accent, theme === "dark", `${theme}: a lit card's face ${theme === "dark" ? "is" : "is not"} the accent itself`);
    // Where each lit copy's front stands against its card's front.
    cards.forEach(({ index }, n) => {
      const card = at(lens.slots, index), copy = at(lens.litSlots, n);
      const ahead = copy.z + copy.d / 2 > card.z + card.d / 2;
      assert.equal(ahead, theme === "dark", `${theme}: the shine ${theme === "dark" ? "covers the card" : "stands behind the card's face, round its edges"}`);
      if (theme === "light") assert.ok(copy.w > card.w && copy.h > card.h, "and it is wider and taller, so its edges show");
    });
    assert.equal(bloom.at(-1), (theme === "dark" ? LAWS_BLOOM : LAWS_BLOOM_LIGHT).strength);
  }
});

test("the legend says what each visual difference stands for, and nothing else differs", () => {
  const { lens } = lensFor();
  const { legend } = lens.chrome();
  const ids = new Set(legend.items.map((item) => item.id));
  for (const item of legend.items) assert.ok(MARKS.some((mark) => mark.id === item.id && mark.label === item.label), item.id);
  const entry = { solid: "laws-declared", design: "laws-design" };
  for (const form of new Set(lens.layout.bars.filter((bar) => bar.id).map((bar) => bar.form))) assert.ok(ids.has(entry[form]), `the ${form} form is in the legend`);
  for (const id of ["laws-height", "laws-chosen", "laws-rack", "laws-slot", "laws-case", "laws-none"]) assert.ok(ids.has(id), id);
  assert.equal(ids.has("laws-block"), lens.blocks.mesh.count > 0, "the inner model's block, where a rack holds it");
  assert.equal(ids.has("laws-next"), lens.nextCount > 0, "the next free code's empty socket, where a row has one");
  assert.match(legend.note.text, /stand for nothing/, "the room is said to stand for nothing");
  // The legend's counts are the manifest's.
  const count = new Map(legend.items.map((item) => [item.id, item.count]));
  assert.equal(count.get("laws-declared"), manifest.pieces.length);
  assert.equal(count.get("laws-rack"), manifest.models.filter((model) => model.rows.length).length);
  assert.equal(count.get("laws-case"), manifest.models.filter((model) => !model.rows.length).length);
  assert.equal(count.get("laws-none"), manifest.models.flatMap((model) => model.rows.filter((row) => row.piece === null)).length);
  assert.equal(count.get("laws-next"), manifest.models.filter((model) => model.next_code !== null).length);
  // What only a search, a filter or a test of size draws is named while it is drawn.
  assert.ok(!ids.has("laws-found") && !ids.has("laws-empty"));
  lens.setQuery("calcium");
  assert.ok(lens.chrome().legend.items.some((item) => item.id === "laws-found"), "a search's forward and faint are named");
  lens.setQuery("");
  lens.setSize(1000);
  assert.ok(lens.chrome().legend.items.some((item) => item.id === "laws-empty"), "the empty places of a test of size are named");
  lens.setSize(0);
  for (const item of lens.chrome().legend.items) assert.ok(typeof item.count === "number" && item.description, `${item.id}: a count and a description for the page's legend`);
  // The legend's own choice picks out the pieces of a mark, as a filter does; a mark of the room picks out nothing.
  lens.setIsolate("laws-design");
  const design = lens.wall.design;
  assert.ok(lens.layout.bars.filter((bar) => bar.id && bar.form === "solid").every((bar) => { const at = lens.barSlot.get(bar.id)[0]; return lens.wall[at.set].target[at.index] === 0; }), "the rest stays back");
  assert.ok(design.mesh.count > 0);
  lens.setIsolate("laws-declared");
  const declaredBar = lens.layout.bars.find((bar) => bar.id && bar.form === "solid"), at = lens.barSlot.get(declaredBar.id)[0];
  assert.ok(lens.wall[at.set].target[at.index] > 0, "a declared piece stands forward");
  assert.ok(lens.chrome().legend.items.some((item) => item.id === "laws-found"), "what the legend's choice fades is named while it is faded");
  lens.setIsolate("laws-rack");
  assert.equal(lens.isolate, null);
  // The next free code is no dashed outline (dashed is how a status looks on the page's other views): its number is written in an empty socket.
  assert.ok(!Object.values(lens.materials).some((material) => material.isLineDashedMaterial), "no dashed mark");
  for (const id of [...MARKS.map((mark) => mark.id), legend.note.swatch]) assert.ok(LAWS_CSS.includes(`.swatch-${id} `), `${id}: the page's legend has a swatch for it`);
  // The list and the panel use the same swatches as the legend, each as the wall draws the piece or the frame.
  // (the legacy model IDs the wall lists as not shown have no swatch: nothing is drawn for them)
  const used = new Set(lens.sections().flatMap((section) => section.entities.map((entity) => entity.swatch)).filter(Boolean));
  for (const piece of raw.pieces.slice(0, 40)) for (const section of lens.describe(`laws:${piece.id}`).sections || []) for (const item of section.items || []) if (item.swatch) used.add(item.swatch);
  for (const swatch of used) assert.ok(MARKS.some((mark) => mark.id === swatch), `${swatch}: a swatch the legend does not explain`);
  for (const piece of raw.pieces) {
    const entity = lens.sections().flatMap((section) => section.entities).find((item) => item.id === `laws:${piece.id}`);
    const bar = lens.layout.bars.find((item) => item.id === piece.id);
    assert.equal(entity.swatch, bar.form === "design" ? "laws-design" : "laws-declared", piece.id);
  }
  // No legend word and no name in the room is a level: the scene's level words are not written anywhere in the room.
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const levels = new Set((scene.statuses || []).map((status) => status.label));
  const plaques = plaquesOf(lens.library, lens.layout);
  for (const text of [...legend.items.map((item) => item.label), ...plaques.map((plaque) => plaque.text)]) for (const level of levels) if (level) assert.ok(!new RegExp(`\\b${level}\\b`, "i").test(text), `"${text}" says a level: ${level}`);
  // At rest each form is one colour, one size and one depth: a bar differs from another only as the legend says.
  const colours = (set) => {
    const out = new Set(), colour = new THREE.Color();
    for (let index = 0; index < set.mesh.count; index++) out.add((set.mesh.getColorAt(index, colour), colour.getHexString()));
    return out;
  };
  for (const name of ["solid", "design"]) {
    if (!lens.wall[name].mesh.count) continue;
    assert.equal(colours(lens.wall[name]).size, 1, `${name}: one colour at rest`);
    assert.ok([...lens.wall[name].offset].every((value) => value === 0), `${name}: all flush at rest`);
  }
  const bars = lens.layout.bars.filter((bar) => bar.id);
  assert.equal(new Set(bars.map((bar) => `${bar.h}|${bar.d}`)).size, 1, "every bar is as tall and as deep as every other");
  assert.equal(new Set(bars.map((bar) => bar.w)).size, 1, "every bar is as wide as every other");
  // The room: one colour to each of its parts.
  for (const [name, set] of Object.entries({ planks: lens.planks, dividers: lens.dividers, rim: lens.rim, panels: lens.panels, rails: lens.rails, sockets: lens.sockets, blocks: lens.blocks })) assert.equal(colours(set).size, 1, `${name}: the room's ${name} are one colour`);
  // The cards in the racks are coloured by where their piece stands, as the bars are.
  const cardForms = new Map();
  lens.cardList.forEach((card, index) => {
    const colour = new THREE.Color();
    lens.slots.mesh.getColorAt(index, colour);
    cardForms.set(card.form, new Set([...(cardForms.get(card.form) || []), colour.getHexString()]));
  });
  for (const [form, seen] of cardForms) assert.equal(seen.size, 1, `the cards of the ${form} form are one colour`);
});

test("the room's names are written from the list: each family once, a shelf only where it holds several, and the revision read at", () => {
  for (const size of [{}, { width: 400, height: 860 }]) {
    const { lens } = lensFor(size);
    lens.update(16);
    const plaques = plaquesOf(lens.library, lens.layout);
    const families = plaques.filter((plaque) => plaque.kind === "family");
    for (const family of raw.families) assert.equal(families.filter((plaque) => plaque.family === family.id && plaque.text === family.short).length, 1, `${family.id} is named once`);
    const shelves = plaques.filter((plaque) => plaque.kind === "shelf");
    for (const shelf of raw.shelves) {
      const many = raw.families.filter((family) => family.shelf === shelf.id).length > 1;
      assert.equal(shelves.filter((plaque) => plaque.text === shelf.label).length, many ? 1 : 0, `${shelf.id}: named ${many ? "once" : "only by its family"}${lens.narrow ? " on a tall screen" : ""}`);
    }
    // On the wall no shelf's name is written twice; a family's short name may recur on another shelf (Channel, under laws and under design notes), never on one.
    for (const text of new Set(shelves.map((plaque) => plaque.text))) assert.equal(shelves.filter((plaque) => plaque.text === text).length, 1, `"${text}" is written twice on the wall`);
    for (const shelf of raw.shelves) {
      const names = families.filter((plaque) => library.familyById.get(plaque.family).shelf === shelf.id).map((plaque) => plaque.text);
      assert.equal(new Set(names).size, names.length, `${shelf.id}: a name written twice on one shelf`);
    }
    // The revision the manifest was written at, and no date: the manifest states none.
    const revision = plaques.find((plaque) => plaque.kind === "revision");
    assert.ok(revision.text.startsWith(`Read from the engine's declarations at main ${manifest.revision.slice(0, 8)}`), revision.text);
    assert.ok(!/committed|20[0-9]{2}/.test(revision.text), revision.text);
    assert.match(longDate("2026-11-16"), /^16 November 2026$/);
    // Each slot's code, key or position, where its model has slots; the row with no piece by its ID.
    const tags = plaques.filter((plaque) => plaque.kind === "tag").map((plaque) => plaque.text);
    for (const row of manifest.models.flatMap((model) => model.rows)) if (row.slot) assert.ok(tags.includes(String(Object.values(row.slot)[0])), `${row.id}: ${JSON.stringify(row.slot)}`);
    assert.ok(plaques.some((plaque) => plaque.kind === "none" && plaque.text === "maintained_chemical_reservoirs@1: no piece"));
    // Names of one band never run into each other: each is narrower than the step between columns (letters at most 0.62 of an em wide).
    const heads = lens.layout.heads;
    const step = Math.min(...heads.flatMap((head, n) => (n && heads[n - 1].band === head.band ? [head.x - heads[n - 1].x] : [])));
    for (const plaque of families) assert.ok(plaque.text.length * plaque.h * 1.05 * 0.62 < step, `${plaque.text}: fits its column`);
  }
});

test("the library opens on all of itself, nothing cut and the frame filled; choosing moves the camera toward it", () => {
  const { lens, camera, place, flights, stage } = lensFor();
  place(lens.homeView());
  camera.updateProjectionMatrix();
  const { bounds, wall } = lens.layout;
  const points = [];
  for (const x of [bounds.minX, bounds.maxX]) for (const y of [-0.3, wall.y + wall.h]) for (const z of [bounds.minZ, bounds.maxZ]) points.push(new THREE.Vector3(x, y, z).project(camera));
  for (const point of points) assert.ok(Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1, `a corner of the library is cut: ${point.x.toFixed(2)}, ${point.y.toFixed(2)}`);
  const ys = points.map((point) => point.y), xs = points.map((point) => point.x);
  assert.ok(Math.max(...ys) > 0.85 || (Math.max(...xs) > 0.85 && Math.min(...xs) < -0.85), "the library fills the frame: no band of it left empty");
  assert.ok(Math.max(...ys) + Math.min(...ys) < 0.12 && Math.max(...ys) + Math.min(...ys) > -0.12, "and it is centred, with as much room above as below");
  const home = lens.homeView();
  lens.focus("laws:kir2p1_mh2@1");
  const toPiece = flights.at(-1);
  assert.ok(toPiece.distance < home.distance, "a piece: the camera comes closer");
  lens.focus("laws:resolved_pump_tissue@3");
  assert.ok(flights.at(-1).distance <= home.distance && flights.at(-1).target.distanceTo(home.target) > 0.5, "a frame: the camera moves toward it");
  // The viewer sets the panel's room after it asks for the move: within the flight the move is fitted again beside the panel.
  lens.focus("laws:kir2p1_mh2@1");
  const asked = flights.length;
  stage.insets = { right: 420 };
  lens.update(16);
  assert.equal(flights.length, asked + 1, "fitted again when the panel opens");
  lens.update(16);
  assert.equal(flights.length, asked + 1, "and only once");
  stage.insets = {};
  // Letting go ends the move: a change of the panel's room afterwards fits nothing again.
  lens.setSelection("laws:kir2p1_mh2@1");
  lens.focus("laws:kir2p1_mh2@1");
  lens.setSelection(null);
  const after = flights.length;
  stage.insets = { right: 420 };
  lens.update(16);
  assert.equal(flights.length, after, "no move for a choice let go");
  // With the panel open beside it: a rack is come up to, and every lit slot of a piece is whole beside the panel.
  const right = 416, width = stage.width, height = stage.height;
  stage.insets = { right };
  lens.setSelection("laws:resolved_pump_composite@1");
  lens.focus("laws:resolved_pump_composite@1");
  const rack = lens.layout.frames.find((frame) => frame.id === "resolved_pump_composite@1");
  assert.ok(flights.at(-1).distance < home.distance * 0.85 && Math.abs(flights.at(-1).target.x - rack.x) < rack.w / 2, "the camera comes up to the rack");
  const seen = (view, items) => {
    place(view);
    camera.setViewOffset(width, height, right / 2, 0, width, height);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    for (const item of items) for (const dx of [-1, 1]) for (const dy of [-1, 1]) {
      const point = new THREE.Vector3(item.x + (dx * item.w) / 2, item.y + (dy * item.h) / 2, item.z).project(camera);
      const x = ((point.x + 1) / 2) * width, y = ((1 - point.y) / 2) * height;
      assert.ok(x >= 0 && x <= width - right && y >= 0 && y <= height, `a lit slot of ${lens.selected} is cut or under the panel: ${x.toFixed(0)}, ${y.toFixed(0)}`);
    }
    camera.clearViewOffset();
    camera.updateProjectionMatrix();
  };
  for (const id of ["nak_atp_mass_action_positive@1", "kir2p1_mh2@1"]) {
    lens.setSelection(`laws:${id}`);
    lens.focus(`laws:${id}`);
    const items = lens.library.slotsOf(id).map((slot) => lens.slotItem(slot.block ? `${slot.frame}|${slot.block}` : `${slot.frame}|${slot.row}|${slot.index}`));
    seen(flights.at(-1), items);
  }
  stage.insets = {};
  lens.setSelection(null);
  // A family chosen on the card: toward its column; let go, back to the whole library.
  const channel = lens.layout.heads.find((head) => head.family.id === "channel");
  lens.setMark("channel");
  assert.ok(Math.abs(flights.at(-1).target.x - channel.x) < 2.5 && flights.at(-1).distance < home.distance, "toward the family's column");
  lens.setMark("all");
  assert.ok(Math.abs(flights.at(-1).distance - home.distance) < 1e-6, "and home again");
  // An address naming what the map does not show (a legacy model ID): accepted, nothing lit, no move, no bloom.
  const gone = raw.legacy[0];
  const moves = flights.length;
  lens.setSelection(`laws:${gone.id}`);
  lens.focus(`laws:${gone.id}`);
  assert.equal(flights.length, moves, "the camera stays where it was");
  assert.equal(lens.litSlots.mesh.count + lens.litBars.mesh.count + lens.routes.length, 0, "nothing is lit");
  // On a tall screen the library opens on its whole wall, where its size shows and its names can be read.
  const tall = lensFor({ width: 400, height: 860 });
  tall.lens.update(16);
  tall.place(tall.lens.homeView());
  tall.camera.updateProjectionMatrix();
  const w = tall.lens.layout.wall;
  for (const x of [w.x - w.w / 2, w.x + w.w / 2]) for (const y of [w.y, w.y + w.h]) {
    const point = new THREE.Vector3(x, y, w.z).project(tall.camera);
    assert.ok(Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1, "the tall screen's wall is in frame");
  }
});

test("with less motion asked for nothing eases and no light runs: the routes stand at once", () => {
  const still = lensFor({ moving: false }).lens;
  still.setSelection("laws:kv1p5_mh@1");
  assert.equal(still.growth, 1);
  assert.equal(still.running, 0, "no light runs along the routes");
  assert.equal(still.materials.line.uniforms.pulse.value, 0);
  assert.equal(still.update(16), false, "nothing is left to move");
  const moving = lensFor({ moving: true }).lens;
  moving.setSelection("laws:kv1p5_mh@1");
  assert.equal(moving.growth, 0);
  assert.equal(moving.update(16), true, "the route grows toward its slot");
  for (let n = 0; n < 600 && moving.update(16); n++);
  assert.equal(moving.update(16), false, "and the light runs a few times, then holds steady: motion only where it tells something");
  assert.equal(moving.materials.line.uniforms.pulse.value, 0);
});

test("what it costs to draw, at the real size and at a thousand pieces", () => {
  const { lens } = lensFor();
  lens.setSelection("laws:resolved_pump_composite@1"); // the most lines at once
  const today = lens.cost();
  assert.ok(today.draws <= 40 && today.triangles <= 40000, `today: ${JSON.stringify(today)}`);
  lens.setSize(1000);
  assert.equal(lens.layout.bars.length, 1000, "the test of size fills the wall to a thousand places");
  assert.equal(lens.layout.bars.filter((bar) => bar.id).length, raw.pieces.length, "and adds no piece");
  lens.setSelection("laws:resolved_pump_composite@1");
  const thousand = lens.cost();
  assert.ok(thousand.draws <= 40 && thousand.triangles <= 60000, `at a thousand: ${JSON.stringify(thousand)}`);
  assert.ok(thousand.draws <= today.draws + 1, "a thousand bars cost no more draws than the real list, but the empty slots' own set");
});

test("a tall screen stacks the wall in bands that break at shelves, and the frames one above another", () => {
  const { lens } = lensFor({ width: 400, height: 860 });
  lens.update(16);
  assert.equal(lens.narrow, true);
  const bands = new Map();
  for (const head of lens.layout.heads) bands.set(head.band, [...(bands.get(head.band) || []), head]);
  for (const heads of bands.values()) assert.ok(heads.length <= PER_BAND, `at most ${PER_BAND} families to a band`);
  for (const shelf of raw.shelves) assert.equal(new Set(lens.layout.heads.filter((head) => head.shelf === shelf.id).map((head) => head.band)).size, 1, `${shelf.id} is never split across bands`);
  const [inner, composite] = lens.layout.frames;
  assert.ok(inner.y > composite.y, "the inner model stands above the composite");
  assert.ok(lens.layout.bounds.maxX - lens.layout.bounds.minX < 13, "and the picture is narrow");
});

test("the Library refuses a list that breaks its contract", () => {
  const broken = JSON.parse(JSON.stringify(raw));
  broken.pieces.push({ ...broken.pieces[0] });
  broken.pieces[1].family = "no_such_family";
  broken.pieces[2].status = { level: "qualified" };
  broken.pieces[3].declared = { ...broken.pieces[3].declared, declared_id: "someone_else@1" };
  const problems = problemsOf(broken);
  assert.ok(problems.some((line) => /listed twice/.test(line)));
  assert.ok(problems.some((line) => /no_such_family/.test(line)));
  assert.ok(problems.some((line) => /a level that is not the manifest's/.test(line)));
  assert.ok(problems.some((line) => /its declaration does not match/.test(line)));
  assert.throws(() => new Library(broken), /not valid/);
});

// ------------------------------------------------------------ on the map's page

test("on the map's page: the doors into the library open a declared piece, or say plainly that the engine's declarations do not list it", async () => {
  const { doorsFor, describe, drawnIn, unitLaws } = await import("../src/lenses/laws_card.js");
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const withLaws = { ...scene, laws: raw };
  // An Engine view box that holds the files of declared pieces opens the library on them.
  const inBox = (id) => library.pieces.filter((piece) => piece.box?.id === id);
  for (const id of new Set(library.pieces.map((piece) => piece.box?.id).filter(Boolean))) {
    const [door] = doorsFor({ id }, withLaws);
    assert.deepEqual([door.lens, door.value], ["laws", id], id);
    assert.match(door.label, new RegExp(`^Show its ${inBox(id).length} declared pieces? in the Laws library$`), id);
  }
  assert.deepEqual(doorsFor({ id: "laws.nothing" }, withLaws), [], "a box that holds no declared piece has no door");
  assert.deepEqual(doorsFor({ id: "laws.channels" }, {}), [], "nor any part where the page carries no list");
  // An Engine view operator the manifest declares opens that operator.
  for (const piece of library.pieces.filter((item) => item.declared?.piece === "operator")) {
    const doors = doorsFor({ id: `op.${piece.id}` }, withLaws);
    assert.deepEqual(doors, [{ label: `Open ${piece.id} on the Laws library's wall`, lens: "laws", value: `laws:${piece.id}` }], piece.id);
  }
  // A unit of the Protein atlas: a door onto each of its laws that is declared; words, and no door, for each that is not.
  const units = scene.entities.filter((entity) => entity.kind === "unit");
  assert.equal(units.length, 48);
  const opening = [];
  for (const unit of units) {
    const laws = unitLaws(unit);
    const doors = doorsFor(unit, withLaws);
    const declared = laws.filter((law) => library.piece(law)?.where === "declared"), undeclared = laws.filter((law) => !declared.includes(law));
    assert.deepEqual(doors.filter((door) => door.lens).map((door) => door.value), declared.map((law) => `laws:${library.piece(law).id}`), unit.id);
    const words = doors.filter((door) => !door.lens);
    assert.ok(words.every((door) => door.says === true), `${unit.id}: words in a door's place say so, so that the panel never takes another view's own door for words`);
    assert.equal(words.length, undeclared.length ? 1 : 0, `${unit.id}: one line for the laws that are not declared`);
    if (undeclared.length === 1) assert.equal(words[0].label, `No active model declares this unit's law ${undeclared[0]}. The engine's declarations do not list it, and the Laws library does not show it.`, unit.id);
    if (undeclared.length > 1) assert.equal(words[0].label, `No active model declares these laws of this unit: ${undeclared.join(", ")}. The engine's declarations do not list them, and the Laws library does not show them.`, unit.id);
    if (doors.some((door) => door.lens)) opening.push(unit.label);
  }
  // As many units open a piece as name a law the manifest declares (10 of the 48 at 7538b0cd): counted from the manifest, not fixed here.
  const declaredIds = new Set(manifest.pieces.flatMap((piece) => [piece.id, piece.declared_id, namespaced(piece.declared_id)]));
  assert.equal(opening.length, units.filter((unit) => unitLaws(unit).some((law) => declaredIds.has(namespaced(law)))).length, opening.join("; "));
  // Each declared piece links back to its box where the page draws it, and an operator to its own part.
  const drawn = drawnIn(scene);
  for (const piece of library.pieces.filter((item) => item.where === "declared")) {
    const ids = describe(library, `laws:${piece.id}`, { drawn }).related[0]?.ids || [];
    for (const id of ids) assert.ok(drawn(id), `${piece.id}: links ${id}, which the page draws`);
    if (piece.box && drawn(piece.box.id)) assert.ok(ids.includes(piece.box.id), piece.id);
    if (piece.declared.piece === "operator" && drawn(`op.${piece.id}`)) assert.ok(ids.includes(`op.${piece.id}`), piece.id);
  }
  // Standing alone, with no Engine view, nothing is linked.
  assert.ok(library.pieces.every((piece) => !describe(library, `laws:${piece.id}`).related?.length));
  // The door's value picks out the box's pieces; the card says so and offers the way back.
  const { lens } = lensFor();
  const box = library.pieces.find((piece) => piece.box)?.box;
  lens.setFinding(box.id);
  assert.deepEqual(lens.order(), raw.families.flatMap((family) => inBox(box.id).filter((piece) => piece.family === family.id)).map((piece) => `laws:${piece.id}`));
  assert.equal(lens.chrome().card.open.label, `The pieces of the Engine view's ${box.label}`);
  assert.equal(lens.chrome().card.open.count, inBox(box.id).length);
  assert.equal(lens.back(), true);
  assert.equal(lens.back(), false, "nothing left to go back from");
  // A door onto one piece chooses it, as a press would: the page hears the choice.
  const heard = [];
  lens.stage.canvas = { dispatchEvent: (event) => heard.push(event.detail) };
  lens.setFinding("laws:cells.kv1p5_mh@1");
  assert.deepEqual(heard, [{ id: "laws:kv1p5_mh@1", fly: true }]);
  assert.equal(lens.chrome().card.find.label, "Find a piece", "the card offers a search field");
});

test("the page carries the list in its scene, and the viewer offers the view with its swatches, its ids and its doors", async () => {
  const { buildPage, bundle } = await import("../tools/lib/build_page.mjs");
  assert.equal(typeof bundle, "function", "one bundling for the map's page and a view standing alone");
  const page = await buildPage();
  const scene = JSON.parse(/<script type="application\/json">(.*?)<\/script>/s.exec(page)[1]);
  assert.deepEqual(scene.laws, raw, "the list, whole");
  const viewer = readFileSync(path.join(ROOT, "src", "ui", "viewer.js"), "utf8");
  const entry = viewer.split("\n").find((line) => line.includes('id: "laws"'));
  // Its tab's titles are stated in that line and nowhere else: this test holds none of its own.
  assert.match(entry || "", /\blabel: "[^"]+", short: "[^"]+"/, "the entry states its tab's title, wide and on a phone");
  for (const word of ["needs: (scene) => scene.laws?.pieces?.length", 'owns: (id) => id.startsWith("laws:")', "doorsFor: lawsDoors", "styles: LAWS_CSS"]) assert.ok(entry?.includes(word), word);
});

test("where no 3D can be drawn, the list and the panel come from the scene's list", async () => {
  const { textSections, textDescribe, sections, describe } = await import("../src/lenses/laws_card.js");
  const scene = { laws: raw };
  const library = new Library(raw);
  assert.deepEqual(textSections(scene), sections(library));
  assert.deepEqual(textDescribe(scene, "laws:kir2p1_mh2@1"), describe(library, "laws:kir2p1_mh2@1"));
  assert.deepEqual(textSections({}), [], "a page that carries no list lists nothing");
  assert.equal(textDescribe({}, "laws:kir2p1_mh2@1"), null);
});

// ------------------------------------------------------------ what the wall does not show, and its links

test("an address naming what the wall does not show is answered: a legacy model ID in the manifest's words, a row with no piece, and any other ID as not declared", async () => {
  const { describe } = await import("../src/lenses/laws_card.js");
  // A legacy model ID: the manifest's own words for what it is; nothing of what it was.
  for (const item of manifest.legacy) {
    const said = describe(library, `laws:${item.id}`);
    assert.equal(said.plain, `The engine's declarations list ${item.id} among the older model families: legacy code, to be dropped, with no page of its own. The map does not show it.`);
    assert.deepEqual([said.status, said.facts, said.sources], [null, [], []], item.id);
  }
  // The wall lists them where it lists what it does not show, by ID as the manifest gives them.
  const notShown = listSections(library).find((section) => section.label.startsWith("Not shown"));
  assert.deepEqual(notShown.entities.map((entity) => entity.label), manifest.legacy.map((item) => item.id));
  // A row with no piece of its own: the fuel kind, and the cycle laws that run on it.
  const fuel = describe(library, "laws:maintained_chemical_reservoirs@1");
  assert.equal(fuel.eyebrow, "A row of resolved_pump_tissue@3 · fuel kind");
  assert.match(fuel.plain, /a row with no entry of its own in the engine's declarations/);
  assert.deepEqual(fuel.opens[0].items.map((item) => item.label).sort(), manifest.pieces.filter((piece) => (piece.fields?.fuel_kinds || []).includes("maintained_chemical_reservoirs@1")).map((piece) => piece.declared_id).sort());
  // Any other ID, an old piece of the wall included: not listed, so not shown; never called legacy unless the manifest says so.
  for (const id of ["cav1p2_m2h@1", "rk4", "capsid_graph@1", "source_decay@1", "neutral_mobile_leak@1"]) {
    const said = describe(library, `laws:${id}`);
    if (!said) continue; // not an ID at all (rk4 has no version): the view does not answer it
    assert.equal(said.plain, `The engine's declarations do not list ${id}: no active registry declares it, so the map does not show it.`, id);
    assert.ok(!/legacy|older/.test(said.plain), id);
  }
  // A piece still declared keeps the address the wall gave it before, whichever spelling that was (the wall read at fa19d80c).
  for (const id of ["atp_driven_transporter_mass_action_positive@1", "proton_atp_mass_action_positive@1", "rapid_proton_buffer@1", "cells.passive_routes@1", "kv1p5_mh@1", "site_occupancy@1"]) assert.ok(library.piece(id), `${id} still opens its piece`);
});

test("the library's own sources link at the manifest's revision, said beside the link where the map's differs, and every linked file is there", async (t) => {
  const { describe } = await import("../src/lenses/laws_card.js");
  const { SceneModel } = await import("../src/scene/model.js");
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const model = new SceneModel(scene);
  const at = /\/blob\/[^/]+\/$/;
  const linked = new Set();
  const differs = !scene.meta.source_base_url.includes(`/blob/${manifest.revision}/`);
  for (const id of [...library.pieces.map((piece) => piece.id), ...library.frames.map((frame) => frame.id)]) {
    const said = describe(library, `laws:${id}`, { map: scene.meta });
    for (const source of said.sources) {
      assert.equal(source.revision, manifest.revision, `${id}: ${source.path}`);
      assert.equal(model.sourceUrl(source), scene.meta.source_base_url.replace(at, `/blob/${manifest.revision}/`) + source.path, id);
      if (differs) assert.ok(source.where.endsWith(`, as declared at main ${manifest.revision.slice(0, 8)}`), `${id}: ${source.where}`);
      linked.add(source.path);
    }
  }
  // On a map at the manifest's revision, the links need no words.
  const same = { ...scene.meta, revision: manifest.revision.slice(0, 8), source_base_url: scene.meta.source_base_url.replace(at, `/blob/${manifest.revision}/`) };
  assert.equal(describe(library, "laws:kv1p5_mh@1", { map: same }).sources[0].where, `line ${manifest.pieces.find((piece) => piece.declared_id === "kv1p5_mh@1").line}`);
  // Where the main checkout is here to ask, every file linked is there at that revision.
  const common = spawnSync("git", ["-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8" }).stdout.trim();
  const repo = common ? path.dirname(common) : null;
  if (!repo || spawnSync("git", ["-C", repo, "cat-file", "-e", `${manifest.revision}^{commit}`]).status !== 0) return t.skip("the main checkout, or the manifest's revision, is not here to ask");
  for (const file of linked) assert.equal(spawnSync("git", ["-C", repo, "cat-file", "-e", `${manifest.revision}:${file}`]).status, 0, `${file} is not at ${manifest.revision}`);
});

test("a box the page does not draw is never linked, and no level of a box is said", async () => {
  const { describe, drawnIn } = await import("../src/lenses/laws_card.js");
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const boxed = library.pieces.find((piece) => piece.box);
  const without = { ...scene, entities: scene.entities.filter((entity) => entity.id !== boxed.box.id) };
  const said = describe(library, `laws:${boxed.id}`, { drawn: drawnIn(without) });
  assert.ok(!(said.related[0]?.ids || []).includes(boxed.box.id), "no link to a box that is not drawn");
  for (const piece of library.pieces) {
    const text = JSON.stringify(describe(library, `laws:${piece.id}`, { drawn: drawnIn(scene) }));
    for (const status of scene.statuses || []) assert.ok(!text.includes(`is ${status.label.toLowerCase()}`), `${piece.id} says a box's level`);
  }
});
