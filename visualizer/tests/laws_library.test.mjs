// The Laws library (schema/LAWS_LIBRARY.md): its list held to the contract and, where the main
// checkout is there to ask, to the code it was read from; and its view driven as the page drives
// a view, with stand-ins for the stage and the labels. No WebGL: the view only makes objects.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { LAWS_FORMAT, Library, problemsOf } from "../src/lenses/laws_data.js";
import { LawsLens, LAWS_LOOK, LAWS_BLOOM, LAWS_BLOOM_LIGHT, MARKS } from "../src/lenses/laws.js";
import { plaquesOf, longDate } from "../src/lenses/laws_marks.js";
import { PER_BAND } from "../src/lenses/laws_layout.js";
import { LAWS_CSS } from "../src/lenses/laws_styles.js";
import { sections as listSections } from "../src/lenses/laws_card.js";

const raw = JSON.parse(readFileSync(path.join(ROOT, "data", "laws", "pieces.json"), "utf8"));
const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "laws", "overlay.json"), "utf8"));
const contract = readFileSync(path.join(ROOT, "schema", "LAWS_LIBRARY.md"), "utf8");
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const byId = new Map(raw.pieces.map((piece) => [piece.id, piece]));
const frameById = new Map(raw.frames.map((frame) => [frame.id, frame]));

// ------------------------------------------------------------ the list

test("the list holds to its contract: one entry for each id, every family and frame named, where each piece stands", () => {
  assert.equal(raw.format, LAWS_FORMAT);
  assert.deepEqual(problemsOf(raw), []);
  assert.equal(raw.stamp.generator, "visualizer/tools/extract_laws.py");
  assert.match(raw.stamp.main.revision, /^[0-9a-f]{7,40}$/);
  assert.notEqual(raw.stamp.main.on_remote, false, "the list states a main revision that others can find");
  assert.ok(!MACHINE.test(JSON.stringify(raw)), "a machine path leaked into the list");
  for (const piece of raw.pieces) {
    assert.ok(contract.includes(`\`${piece.kind}\``), `${piece.id}: its kind ${piece.kind} is not one the contract names`);
    assert.ok(["main", "candidate", "design"].includes(piece.where), piece.id);
    if (piece.where === "candidate") assert.equal(piece.read.revision, raw.stamp.candidate.revision, `${piece.id}: a candidate's piece is read at the candidate`);
    if (piece.where === "main") assert.equal(piece.read.revision, raw.stamp.main.revision, `${piece.id}: a piece on main is read at main`);
    if (piece.where === "design") assert.ok(piece.curated.named_in?.length && piece.curated.named_in.every((note) => note.path && note.ref), `${piece.id}: a design piece names the notes that name it`);
  }
  const counted = raw.counts;
  assert.equal(counted.pieces, raw.pieces.length);
  for (const family of raw.families) assert.equal(counted.by_family[family.id], raw.pieces.filter((piece) => piece.family === family.id).length, family.id);
});

test("what counts as a piece follows the lead's provisional answers of 16 November 2026", () => {
  assert.match(raw.stamp.what_counts.by, /the lead's provisional answers of 16 November 2026/);
  assert.match(contract, /the lead's provisional answers of 16 November 2026/);
  // A kernel in the code that no kind imports is not a piece yet: apart, and never counted.
  const apart = new Set(raw.unregistered.map((item) => item.id));
  for (const id of ["bounding_patch_constant_field@1"]) {
    assert.ok(apart.has(id), `${id} is kept apart as not registered`);
    assert.ok(!byId.has(id), `${id} is not a piece yet`);
  }
  // "It becomes one when registered": since fa19d80c two kinds import these two kernels, and they are pieces through them.
  for (const [id, kind] of [["bounding_patch_damage@1", "cells.patch_damage@1"], ["ph_conditioned_factor@1", "cells.ph_condition@1"]]) {
    if (!byId.has(kind)) continue; // a list read before the kinds were registered
    assert.ok(!apart.has(id), `${id} is registered through ${kind}, and no longer kept apart`);
    assert.equal(byId.get(id)?.registry, "a registered kind", id);
    assert.equal(byId.get(id)?.registered_in?.kind, kind, id);
  }
  for (const item of raw.unregistered) assert.match(item.words, /not a piece yet/, item.id);
  assert.equal(raw.counts.unregistered, raw.unregistered.length);
  assert.equal(raw.counts.pieces, raw.pieces.length, "what is apart is not counted");
  // Every other piece says where it stands registered; the older families' laws are marked as theirs.
  const inner = raw.frames.find((frame) => frame.kind === "inner model");
  const innerLaws = new Set(inner.rows.filter((row) => row.read.path.endsWith("inner_laws.py")).flatMap((row) => row.pieces));
  for (const piece of raw.pieces) {
    if (piece.where === "design") continue;
    if (piece.registry === "inner_laws.py") assert.ok(innerLaws.has(piece.id) && piece.registered_in.path.endsWith("inner_laws.py"), `${piece.id}: registered in inner_laws.py, and @3's rows say so`);
    if (piece.kind === "operator") assert.equal(piece.registry, "OPERATORS", piece.id);
    if (piece.kind === "kind") assert.equal(piece.registry, "the kind registry", piece.id);
    if (piece.registry === "an older family") assert.ok(piece.declared_by.every((entry) => entry.how !== "direct") && piece.read.found_by === "LAW_CODES table", `${piece.id}: an older family's law is a catalogue table's, and no frame declares it directly`);
    if (piece.registry === "a registered operator") assert.ok(byId.get(piece.registered_in.operator)?.kind === "operator", `${piece.id}: named in an operator's module`);
  }
  // inner_laws' provenance tag is a source tag, never a level; rk4 keeps its missing version.
  const tagged = raw.pieces.filter((piece) => piece.read?.fields?.provenance);
  assert.ok(tagged.length >= 1 && tagged.every((piece) => piece.registry === "inner_laws.py" && piece.status === null), "a provenance tag is read only from inner_laws.py, and gives no level");
  const rk4 = byId.get("rk4");
  assert.ok(rk4 && rk4.read.fields.unversioned === true, "rk4 is shown as it is, with no version");
});

test("no status without a source; a box's status is the box's; no level is inferred", () => {
  for (const piece of raw.pieces) {
    if (piece.status) {
      assert.ok(piece.status.source?.path && piece.status.level && piece.status.label, `${piece.id}: a status with no source`);
      assert.equal(piece.kind, "operator", `${piece.id}: today only the operators have a level recorded for the piece`);
    }
    if (piece.box) {
      assert.ok(piece.box.source?.path && piece.box.level && piece.box.label, `${piece.id}: a box with no source`);
      assert.equal(piece.where, "main", `${piece.id}: a box is given only for a piece on main`);
    }
    if (piece.where === "design") assert.equal(piece.status, null, `${piece.id}: a design piece has no level`);
  }
  for (const frame of raw.frames) for (const box of frame.boxes || []) assert.ok(box.source?.path && box.level, `${frame.id}: a box with no source`);
});

test("every 'declared by' names a listed frame, and says how; every frame's row names listed pieces", () => {
  for (const piece of raw.pieces) {
    for (const entry of piece.declared_by) {
      assert.ok(frameById.has(entry.frame), `${piece.id}: declared by ${entry.frame}`);
      assert.ok(["direct", "kind", "inner"].includes(entry.how), `${piece.id}: ${entry.how}`);
      const frame = frameById.get(entry.frame);
      const names = frame.rows.flatMap((row) => row.pieces);
      if (entry.how === "direct") assert.ok(names.includes(piece.id), `${piece.id}: no row of ${entry.frame} names it`);
      if (entry.how === "kind") assert.ok(names.includes(entry.via) && byId.get(entry.via).read.fields.pieces.includes(piece.id), `${piece.id}: not a piece of ${entry.via}`);
      if (entry.how === "inner") assert.equal(entry.via, frame.inner, `${piece.id}: ${entry.frame} does not hold ${entry.via}`);
    }
  }
  for (const frame of raw.frames) for (const row of frame.rows) for (const id of row.pieces) assert.ok(byId.has(id), `${frame.id} names ${id}`);
});

test("no registry code is used twice, and the next free code follows the codes in use", () => {
  const codes = new Map();
  for (const piece of raw.pieces) {
    const code = piece.read?.fields?.code;
    if (code === undefined) continue;
    assert.ok(!codes.has(code), `code ${code} is used by ${codes.get(code)} and ${piece.id}`);
    codes.set(code, piece.id);
  }
  const inner = raw.frames.find((frame) => frame.kind === "inner model");
  const channels = inner.rows.find((row) => row.label === "Channel laws");
  // The inner model's own codes are a registry of their own, apart from the older families' catalogue codes.
  assert.deepEqual(Object.keys(channels.codes), channels.pieces);
  assert.equal(new Set(Object.values(channels.codes)).size, channels.pieces.length, "the inner model's codes are distinct");
  assert.equal(channels.next_code, Math.max(...Object.values(channels.codes)) + 1, "the next free code follows the inner model's own");
});

test("nothing from a reference simulator is listed as a piece or a frame", () => {
  for (const item of [...raw.pieces, ...raw.frames]) {
    for (const word of overlay.references) {
      assert.ok(!item.id.toLowerCase().includes(word), `${item.id} is named after a reference simulator`);
      assert.ok(!String(item.read?.path || "").toLowerCase().includes(word), `${item.id} is read from a reference simulator's file`);
    }
  }
});

test("what stands on main in the list is still found at the revision it states (where the main checkout is there to ask)", (t) => {
  const common = spawnSync("git", ["-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8" }).stdout.trim();
  const repo = common ? path.dirname(common) : null;
  const revision = raw.stamp.main.revision;
  if (!repo || !existsSync(path.join(repo, "src", "cells")) || spawnSync("git", ["-C", repo, "cat-file", "-e", `${revision}^{commit}`]).status !== 0) {
    t.skip("the main checkout, or the revision the list states, is not here to ask");
    return;
  }
  const files = new Map();
  const read = (file) => {
    if (!files.has(file)) files.set(file, spawnSync("git", ["-C", repo, "show", `${revision}:${file}`], { encoding: "utf8", maxBuffer: 1 << 26 }).stdout);
    return files.get(file);
  };
  // A catalogue law may be named by a comprehension (Kv1's are written f"kv1p{i}_mh…"): its table is read again with the tool's own reader.
  const tables = {};
  for (const piece of raw.pieces.filter((item) => item.where === "main")) {
    if (piece.read.found_by === "LAW_CODES table") (tables[piece.read.path] ??= []).push(piece.id);
    else assert.ok(read(piece.read.path).includes(piece.id.replace(/^cells\./, "")), `${piece.id} is not found in ${piece.read.path} at ${revision}`);
  }
  const check = `
import json, sys
sys.path.insert(0, sys.argv[1])
import extract_laws as tool
reading = tool.Reading(sys.argv[2], sys.argv[3])
tables = json.loads(sys.argv[4])
print(json.dumps({path: sorted(set(ids) - set(reading.value(path, "LAW_CODES") or {})) for path, ids in tables.items()}))
`;
  const run = spawnSync("python3", ["-I", "-c", check, path.join(ROOT, "tools"), repo, revision, JSON.stringify(tables)], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  for (const [file, missing] of Object.entries(JSON.parse(run.stdout))) assert.deepEqual(missing, [], `${file} at ${revision} no longer lists them in LAW_CODES`);
  for (const frame of raw.frames.filter((item) => item.read.revision === revision)) assert.ok(read(frame.read.path).includes(frame.id), `${frame.id} is not in ${frame.read.path}`);
  // A design note on main names its pieces at the revision the list states, and the code does not hold them.
  for (const piece of raw.pieces.filter((item) => item.where === "design")) {
    for (const note of piece.curated.named_in.filter((item) => item.ref === "main")) assert.ok(read(note.path).includes(piece.id), `${note.path} does not name ${piece.id} at ${revision}`);
  }
});

test("the tool's rules: which constant names name a piece, and the globs of the Engine view's boxes", () => {
  const code = `
import json, sys
sys.path.insert(0, sys.argv[1])
import extract_laws as tool
names = [("LAW_ID", "src/cells/processes/x.py"), ("FACE_LAW", "src/cells/core/x.py"), ("SOLVER_ID", "src/cells/numerics/x.py"), ("ARS222_ID", "src/cells/numerics/imex.py"),
         ("READ_ID", "src/cells/processes/x.py"), ("KIND_ID", "src/cells/processes/x.py"), ("KIND_ID", "src/cells/models/inner_kinds/x.py"), ("STABLE_RNG_ID", "src/cells/processes/x.py"), ("MODEL_ID", "src/cells/core/x.py")]
print(json.dumps({"kinds": [tool.constant_kind(name, where) for name, where in names],
                  "globs": [bool(tool.glob_regex(pattern).match(path)) for pattern, path in [("src/cells/processes/*channels*.py", "src/cells/processes/hcn_channels.py"), ("src/cells/coupling/**", "src/cells/coupling/a/b.py"), ("src/cells/processes/*.py", "src/cells/processes/a/b.py")]]}))
`;
  const run = spawnSync("python3", ["-I", "-c", code, path.join(ROOT, "tools")], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const out = JSON.parse(run.stdout);
  assert.deepEqual(out.kinds, ["law", "law", "solver", "solver", "read", "route kind", null, null, null]);
  assert.deepEqual(out.globs, [true, true, false]);
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
  // Each form is where the piece stands: solid on main, banded on the candidate, an outline for a design.
  const form = { main: "solid", candidate: "band", design: "design" };
  for (const bar of lens.layout.bars) if (bar.id) assert.equal(bar.form, form[byId.get(bar.id).where], bar.id);
  // And the older families' laws stand above the registered ones of their family, narrower: marked as in an older family.
  for (const family of raw.families) {
    const column = lens.layout.bars.filter((bar) => bar.id && bar.family === family.id);
    const older = column.filter((bar) => bar.older), registered = column.filter((bar) => !bar.older);
    for (const bar of column) assert.equal(bar.older, ["an older family", "no registry"].includes(byId.get(bar.id).registry), bar.id);
    if (older.length && registered.length) assert.ok(Math.min(...older.map((bar) => bar.y)) > Math.max(...registered.map((bar) => bar.y)), `${family.id}: the older families' part is apart`);
    for (const bar of older) assert.ok(bar.w < registered[0]?.w || bar.w < 1.3, bar.id);
  }
});

test("a chosen piece lights exactly the slots that declare it, and draws a line to each", () => {
  const { lens } = lensFor();
  for (const piece of raw.pieces) {
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
  for (const frame of raw.frames) {
    lens.setSelection(`laws:${frame.id}`);
    const expected = new Set(raw.pieces.filter((piece) => piece.declared_by.some((entry) => entry.frame === frame.id)).map((piece) => piece.id));
    assert.deepEqual(lens.lights().bars, expected, frame.id);
    assert.equal(lens.routes.length, frame.rows.reduce((sum, row) => sum + row.pieces.length, 0), `${frame.id}: a route from each of its slots`);
  }
});

test("search, family and where narrow the wall; the arrow keys step through what passes", () => {
  const { lens } = lensFor();
  const families = new Map(raw.families.map((family) => [family.id, family.label]));
  const matches = (piece, words) => [piece.id, piece.curated?.unit, piece.curated?.label, piece.read?.path, families.get(piece.family), piece.kind].some((text) => text && String(text).toLowerCase().includes(words));
  for (const words of ["calcium", "kir2", "proton", "operators/", "inner_kinds"]) {
    lens.setQuery(words);
    assert.deepEqual(lens.order(), raw.pieces.filter((piece) => matches(piece, words)).map((piece) => `laws:${piece.id}`), words);
    const found = lens.layout.bars.filter((bar) => bar.id && matches(byId.get(bar.id), words));
    for (const bar of found) {
      const slot = lens.barSlot.get(bar.id)[0];
      assert.ok(bar.form === "design" || lens.wall[slot.set].target[slot.index] > 0, `${bar.id} is found and stays flush`);
    }
  }
  lens.setQuery("");
  lens.setMark("operators");
  assert.equal(lens.order().length, raw.pieces.filter((piece) => piece.family === "operators").length);
  lens.setMark("all");
  lens.setMode("candidate");
  assert.deepEqual(lens.order(), raw.pieces.filter((piece) => piece.where === "candidate").map((piece) => `laws:${piece.id}`));
  lens.setMode("all");
  lens.setSelection(null);
  const first = lens.step(1);
  assert.equal(first, `laws:${raw.pieces[0].id}`);
  lens.setSelection(first);
  assert.equal(lens.step(1), `laws:${raw.pieces[1].id}`);
  assert.equal(lens.step(-1), `laws:${raw.pieces.at(-1).id}`);
});

test("every piece and every frame can be chosen by id; the list holds every id the view accepts", () => {
  const { lens } = lensFor();
  const listed = lens.sections().flatMap((section) => section.entities.map((entity) => entity.id));
  assert.deepEqual(new Set(listed), new Set([...raw.pieces.map((piece) => `laws:${piece.id}`), ...raw.frames.map((frame) => `laws:${frame.id}`)]));
  assert.equal(listed.length, new Set(listed).size, "no id is listed twice");
  for (const id of listed) {
    assert.ok(lens.has(id), id);
    lens.setSelection(id);
    assert.equal(lens.selected, id);
    assert.ok(lens.describe(id)?.label, `${id}: the panel has nothing to say`);
  }
  assert.equal(lens.has("kv1p5_mh@1"), false, "a bare engine id is not this view's");
  assert.equal(lens.has("laws:nothing@1"), false);
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

test("the panel says a status only where the record states one, and 'no level recorded' everywhere else", () => {
  const { lens } = lensFor();
  for (const piece of raw.pieces) {
    const entity = lens.describe(`laws:${piece.id}`);
    const chips = entity.chips.map((chip) => chip.label);
    if (piece.status) {
      assert.equal(entity.status, piece.status.level, piece.id);
      assert.ok(entity.sources.some((source) => source.path === piece.status.source.path), `${piece.id}: its status's source is cited`);
      assert.ok(!chips.includes("No level recorded for this piece"), piece.id);
    } else {
      assert.equal(entity.status, null, piece.id);
      assert.ok(chips.includes("No level recorded for this piece"), piece.id);
      const said = entity.facts.find(([label]) => label === "Status")[1];
      if (piece.box) assert.match(said, /a status of the box, not of the piece/, piece.id);
    }
    // A file read on a working branch is named in words, never linked at the main address.
    if (piece.read && piece.read.revision !== raw.stamp.main.revision) assert.ok(!entity.sources.some((source) => source.path === piece.read.path), `${piece.id}: a branch's file is linked`);
    if (piece.read?.fields?.doc) assert.ok(entity.plain.includes(piece.read.fields.doc), `${piece.id}: what it computes is its module's own words`);
    if (piece.read?.fields?.provenance) assert.match(entity.facts.find(([label]) => label === "Provenance tag")[1], /a source tag in inner_laws\.py, not a level/, piece.id);
    if (piece.registry === "an older family") assert.ok(chips.includes("In a model family's table"), piece.id);
    if (piece.registry === "no registry") assert.ok(chips.includes("A named law in no registry"), piece.id);
    if (piece.read?.fields?.unversioned) assert.match(entity.facts.find(([label]) => label === "Version")[1], /no version/, piece.id);
  }
  for (const frame of raw.frames) assert.equal(lens.describe(`laws:${frame.id}`).status, null, `${frame.id}: a frame takes no status from its parts`);
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
  const entry = { solid: "laws-main", band: "laws-candidate", design: "laws-design" };
  for (const form of new Set(lens.layout.bars.filter((bar) => bar.id).map((bar) => bar.form))) assert.ok(ids.has(entry[form]), `the ${form} form is in the legend`);
  if (lens.layout.bars.some((bar) => bar.id && bar.older)) assert.ok(ids.has("laws-older"));
  for (const id of ["laws-height", "laws-chosen", "laws-rack", "laws-slot"]) assert.ok(ids.has(id), id);
  assert.equal(ids.has("laws-block"), lens.blocks.mesh.count > 0, "the inner model's block, where a rack holds it");
  assert.equal(ids.has("laws-next"), lens.nextCount > 0, "the next free code's empty socket, where a row has one");
  assert.ok(!ids.has("laws-older-family") && !MARKS.some((mark) => mark.id === "laws-older-family"), "no mark for the older model families: the map does not show them");
  assert.match(legend.note.text, /stand for nothing/, "the room is said to stand for nothing");
  if (!raw.pieces.some((piece) => piece.where === "candidate")) assert.ok(!ids.has("laws-candidate"), "a mark with nothing to show is left out");
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
  lens.setIsolate("laws-older");
  const olderBar = lens.layout.bars.find((bar) => bar.id && bar.older && bar.form === "solid"), at = lens.barSlot.get(olderBar.id)[0];
  assert.ok(lens.wall[at.set].target[at.index] > 0, "an older family's law stands forward");
  assert.ok(lens.chrome().legend.items.some((item) => item.id === "laws-found"), "what the legend's choice fades is named while it is faded");
  lens.setIsolate("laws-rack");
  assert.equal(lens.isolate, null);
  // The next free code is no dashed outline (dashed is how a status looks on the page's other views): its number is written in an empty socket.
  assert.ok(!Object.values(lens.materials).some((material) => material.isLineDashedMaterial), "no dashed mark");
  for (const id of [...MARKS.map((mark) => mark.id), legend.note.swatch]) assert.ok(LAWS_CSS.includes(`.swatch-${id} `), `${id}: the page's legend has a swatch for it`);
  // The list and the panel use the same swatches as the legend, each as the wall draws the piece or the frame.
  const used = new Set(lens.sections().flatMap((section) => section.entities.map((entity) => entity.swatch)));
  for (const piece of raw.pieces.slice(0, 40)) for (const section of lens.describe(`laws:${piece.id}`).sections || []) for (const item of section.items || []) if (item.swatch) used.add(item.swatch);
  for (const swatch of used) assert.ok(MARKS.some((mark) => mark.id === swatch), `${swatch}: a swatch the legend does not explain`);
  for (const piece of raw.pieces) {
    const entity = lens.sections().flatMap((section) => section.entities).find((item) => item.id === `laws:${piece.id}`);
    const bar = lens.layout.bars.find((item) => item.id === piece.id);
    assert.equal(entity.swatch, bar.form === "design" ? "laws-design" : bar.older ? "laws-older" : bar.form === "band" ? "laws-candidate" : "laws-main", piece.id);
  }
  // No legend word and no name in the room is a level: the levels are the panel's, with their sources.
  const levels = new Set();
  for (const piece of raw.pieces) for (const said of [piece.status, piece.box]) if (said) levels.add(said.level_label);
  const plaques = plaquesOf(lens.library, lens.layout);
  for (const text of [...legend.items.map((item) => item.label), ...plaques.map((plaque) => plaque.text)]) for (const level of levels) if (level) assert.ok(!text.includes(level), `"${text}" says a level: ${level}`);
  // At rest each form is one colour, one size and one depth: a bar differs from another only as the legend says.
  const colours = (set) => {
    const out = new Set(), colour = new THREE.Color();
    for (let index = 0; index < set.mesh.count; index++) out.add((set.mesh.getColorAt(index, colour), colour.getHexString()));
    return out;
  };
  for (const name of ["solid", "band", "design"]) {
    if (!lens.wall[name].mesh.count) continue;
    assert.equal(colours(lens.wall[name]).size, 1, `${name}: one colour at rest`);
    assert.ok([...lens.wall[name].offset].every((value) => value === 0), `${name}: all flush at rest`);
  }
  const bars = lens.layout.bars.filter((bar) => bar.id);
  assert.equal(new Set(bars.map((bar) => `${bar.h}|${bar.d}`)).size, 1, "every bar is as tall and as deep as every other");
  assert.equal(new Set(bars.map((bar) => `${bar.older}|${bar.w}`)).size, new Set(bars.map((bar) => bar.older)).size, "a bar is narrower only for being an older family's or in no registry");
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
    for (const family of raw.families) assert.equal(families.filter((plaque) => plaque.text === family.short).length, 1, `${family.id} is named once`);
    const shelves = plaques.filter((plaque) => plaque.kind === "shelf");
    for (const shelf of raw.shelves) {
      const many = raw.families.filter((family) => family.shelf === shelf.id).length > 1;
      assert.equal(shelves.filter((plaque) => plaque.text === shelf.label).length, many ? 1 : 0, `${shelf.id}: named ${many ? "once" : "only by its family"}${lens.narrow ? " on a tall screen" : ""}`);
    }
    // On the wall no name is written twice (a rack's rows may share a family's word: they name the rack's rows).
    const wall = plaques.filter((plaque) => plaque.kind === "family" || plaque.kind === "shelf");
    for (const text of new Set(wall.map((plaque) => plaque.text))) if (wall.filter((plaque) => plaque.text === text).length > 1) assert.fail(`"${text}" is written twice on the wall`);
    const revision = plaques.find((plaque) => plaque.kind === "revision");
    assert.ok(revision.text.includes(`main ${raw.stamp.main.revision}`) && revision.text.includes(longDate(raw.stamp.main.date)), revision.text);
    assert.match(longDate("2026-11-16"), /^16 November 2026$/);
    assert.ok(!plaques.some((plaque) => /older model famil/i.test(plaque.text)), "nothing is written of the older model families: the map does not show them");
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
  const potassium = lens.layout.heads.find((head) => head.family.id === "potassium");
  lens.setMark("potassium");
  assert.ok(Math.abs(flights.at(-1).target.x - potassium.x) < 2.5 && flights.at(-1).distance < home.distance, "toward the family's column");
  lens.setMark("all");
  assert.ok(Math.abs(flights.at(-1).distance - home.distance) < 1e-6, "and home again");
  // An address naming what the map no longer shows (a model family now in legacy code): accepted, nothing lit, no move, no bloom.
  const gone = raw.left_out.frames[0];
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
  broken.pieces[1].declared_by = [{ frame: "no_such_model@1", how: "direct" }];
  broken.pieces[2].status = { level: "qualified" };
  const problems = problemsOf(broken);
  assert.ok(problems.some((line) => /listed twice/.test(line)));
  assert.ok(problems.some((line) => /no_such_model@1/.test(line)));
  assert.ok(problems.some((line) => /a status with no source/.test(line)));
  assert.throws(() => new Library(broken), /not valid/);
});

// ------------------------------------------------------------ on the map's page

test("on the map's page: the Engine view's box opens the library on its pieces, and each piece links back to its box", async () => {
  const { doorsFor, describe } = await import("../src/lenses/laws_card.js");
  const scene = { laws: raw };
  const inBox = (id) => raw.pieces.filter((piece) => piece.box?.id === id);
  for (const id of new Set(raw.pieces.map((piece) => piece.box?.id).filter(Boolean))) {
    const [door] = doorsFor({ id }, scene);
    assert.equal(door.lens, "laws", id);
    assert.equal(door.value, id);
    assert.match(door.label, new RegExp(`^Show its ${inBox(id).length} pieces? in the Laws library$`), id);
  }
  assert.deepEqual(doorsFor({ id: "laws.nothing" }, scene), [], "a box that holds no piece of the list has no door");
  assert.deepEqual(doorsFor({ id: "laws.pumps" }, {}), [], "nor any box where the page carries no list");
  const library = new Library(raw);
  for (const piece of raw.pieces) {
    const entity = describe(library, `laws:${piece.id}`);
    assert.deepEqual(entity.related, piece.box ? [{ title: "On the Engine view", ids: [piece.box.id] }] : [], piece.id);
  }
  for (const frame of raw.frames.filter((item) => item.boxes?.length)) assert.deepEqual(describe(library, `laws:${frame.id}`).related[0].ids, frame.boxes.map((box) => box.id), frame.id);
  // The door's value picks out the box's pieces; the card says so and offers the way back.
  const { lens } = lensFor();
  lens.setFinding("laws.pumps");
  assert.deepEqual(lens.order(), inBox("laws.pumps").map((piece) => `laws:${piece.id}`));
  assert.match(lens.chrome().card.open.label, /The pieces of the Engine view's Pumps/);
  assert.equal(lens.chrome().card.open.count, inBox("laws.pumps").length);
  assert.ok(lens.chrome().legend.items.some((item) => item.id === "laws-found"), "what the door picks out is named in the legend");
  assert.equal(lens.back(), true);
  assert.equal(lens.filter.box, null);
  assert.equal(lens.back(), false, "nothing left to go back from");
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

// ------------------------------------------------------------ no legacy code on the map

test("the map shows no legacy code: what moved into src/cells/legacy/, and the model families the legacy registration registers, are left out; the other model families are shown", async () => {
  const { describe } = await import("../src/lenses/laws_card.js");
  // The list the page carries says what it left out, and by which table; none of it is drawn or listed.
  assert.ok(raw.left_out && /move1-table\.json at main [0-9a-f]{7,}/.test(raw.left_out.table), "the file says what it left out, and by which table");
  assert.match(raw.left_out.registration, /^src\/cells\/legacy\/registration\.py at main [0-9a-f]{7,}: parse, the model dispatch$/, "and by which registration");
  // Every model family left out moved into legacy code, or the legacy registration dispatches its model ID, or both.
  for (const frame of raw.left_out.frames) assert.ok(frame.now?.startsWith("src/cells/legacy/") || frame.registered?.path === "src/cells/legacy/registration.py", frame.id);
  // Two stayed in the core, registered by legacy code: resolved_tissue@1 and @2 (main 76846486), their modules read by active code.
  const registeredOnly = raw.left_out.frames.filter((frame) => !frame.now);
  assert.deepEqual(registeredOnly.map((frame) => frame.id), ["resolved_tissue@1", "resolved_tissue@2"]);
  for (const frame of registeredOnly) assert.ok(frame.path.startsWith("src/cells/core/") && Number.isInteger(frame.registered.line) && frame.read_by.length > 0, frame.id);
  const library = new Library(raw);
  const listed = new Set(listSections(library).flatMap((section) => section.entities.map((entity) => entity.id)));
  for (const gone of [...raw.left_out.frames.map((item) => ({ ...item, as: "frame" })), ...raw.left_out.pieces.map((item) => ({ ...item, as: "piece" }))]) {
    assert.ok(!listed.has(`laws:${gone.id}`), `${gone.id} is not in the list`);
    assert.ok(!library.piece(gone.id) && !library.frame(gone.id), `${gone.id} is not drawn`);
    // An address naming it opens the library and says plainly it is not shown; nothing of what it was.
    const said = describe(library, `laws:${gone.id}`);
    assert.equal(said.status, null, gone.id);
    assert.deepEqual([said.facts, said.sources], [[], []], `${gone.id}: no facts and no source`);
    const plain = gone.as === "piece" ? /^The map no longer shows this piece/
      : gone.now ? /^The map does not show legacy code, and this model family is legacy code now\. Its module moved into the engine's legacy code, src\/cells\/legacy\//
      : /^The map does not show legacy code, and this model family is legacy code now\. The engine's legacy code registers it\. Its own module stays in src\/cells\/core\/, where active code still reads it\.$/;
    assert.match(said.plain, plain, gone.id);
  }
  // The other model families are not legacy code: drawn as cases, listed, found, and with their own panel.
  const families = raw.frames.filter((frame) => frame.kind === "older family");
  assert.deepEqual(families.map((frame) => frame.id).sort(), ["apical_vertex_mechanics@1", "capsid_graph@1", "finite_bond_assembly@1", "ionic_worlds@1", "resolved_pump_tissue@1", "resolved_pump_tissue@2", "source_decay@1"]);
  assert.deepEqual(library.cases.map((frame) => frame.id), families.map((frame) => frame.id));
  for (const frame of families) {
    assert.ok(listed.has(`laws:${frame.id}`), `${frame.id} is in the list`);
    const said = describe(library, `laws:${frame.id}`);
    assert.equal(said.eyebrow, "A model family");
    assert.match(said.plain, /^A model family: one module for each combination of features\. Its laws are a table inside its own module/);
  }
  // Nothing the map shows calls a thing older or legacy, but the panel of what it does not show.
  const shownWords = [
    ...MARKS.map((mark) => `${mark.label} ${mark.description}`),
    ...listSections(library).map((section) => section.label),
    ...[...library.pieces, ...library.frames].flatMap((part) => { const said = describe(library, `laws:${part.id}`); return [said.eyebrow, said.plain, ...said.chips.map((chip) => chip.label), ...said.facts.map(([label, value]) => `${label} ${value}`)]; }),
  ].join("\n").replace(/“[^”]*”/g, "“…”"); // a module's own words, quoted, are its own
  assert.ok(!/older|legacy/i.test(shownWords), (shownWords.match(/.{0,60}(older|legacy).{0,60}/i) || [""])[0]);
  // A list read before the move, with a model family and a piece in legacy code, shows neither; a model family that stayed is shown.
  const before = JSON.parse(JSON.stringify(raw));
  delete before.left_out;
  const law = before.pieces.find((piece) => piece.registry === "no registry" && piece.read);
  before.frames.push({ id: "moved_family@1", kind: "older family", read: { ...law.read, path: "src/cells/legacy/models/moved_family.py", found_by: "MODEL_ID" }, rows: [] });
  before.frames.push({ id: "kept_family@1", kind: "older family", read: { ...law.read, path: "src/cells/models/kept_family.py", found_by: "MODEL_ID" }, rows: [] });
  law.read = { ...law.read, path: "src/cells/legacy/processes/old.py" };
  const kept = before.pieces.find((piece) => piece.kind === "operator");
  kept.declared_by = [...kept.declared_by, { frame: "moved_family@1", how: "direct" }];
  const other = new Library(before);
  assert.ok(!other.frame("moved_family@1") && !other.piece(law.id), "neither is shown");
  assert.ok(other.frame("kept_family@1") && other.cases.some((frame) => frame.id === "kept_family@1"), "a model family that stayed is shown");
  assert.ok(other.notShown("moved_family@1") && other.notShown(law.id), "both are known as not shown");
  assert.ok(other.piece(kept.id).declared_by.every((entry) => entry.frame !== "moved_family@1"), "a piece keeps only what declares it on the map");
  assert.equal(other.counts().pieces, raw.pieces.length - 1);
  // What still stands and was read where legacy code now is: active models declare it, or active code names it.
  for (const id of ["constant_field@1", "logmean_electrodiffusion@1", "maintained_chemical_reservoirs@1", "rk4", "gauged_dense_kirchhoff@1", "ideal_detailed_balance_mass_action@1", "prescribed_patch_injury_resealing@1"]) assert.ok(library.piece(id), `${id} stays`);
});

test("the library's own sources link at the revision the list was read at, said beside the link where the map's differs; the scene's own sources stay at the map's", async (t) => {
  const { describe } = await import("../src/lenses/laws_card.js");
  const { SceneModel } = await import("../src/scene/model.js");
  const main = raw.stamp.main;
  assert.match(main.full_revision, /^[0-9a-f]{40}$/, "the list states the full revision it was read at");
  assert.ok(main.full_revision.startsWith(main.revision));
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const model = new SceneModel(scene);
  const library = new Library(raw);
  const at = /\/blob\/[^/]+\/$/;
  const linked = [];
  for (const part of [...library.pieces, ...library.frames]) {
    const read = part.read;
    const said = describe(library, `laws:${part.id}`, { map: scene.meta });
    const own = said.sources.filter((source) => source.revision);
    // Each piece or frame read on main hands out its file once, at the list's revision, and links there.
    assert.equal(own.length, read?.revision === main.revision ? 1 : 0, part.id);
    for (const source of own) {
      assert.deepEqual([source.path, source.revision], [read.path, main.full_revision], part.id);
      assert.equal(model.sourceUrl(source), scene.meta.source_base_url.replace(at, `/blob/${main.full_revision}/`) + read.path, part.id);
      assert.equal(source.where, `${read.found_by}, as read at main ${main.revision}`, `${part.id}: the map is at ${scene.meta.revision}, so the link says where it goes`);
      linked.push(read.path);
    }
    // A status's or a box's source is the scene's: at the map's revision, as before.
    for (const source of said.sources.filter((item) => !item.revision)) assert.ok(model.sourceUrl(source).startsWith(scene.meta.source_base_url), `${part.id}: ${source.path}`);
  }
  assert.ok(linked.length >= library.frames.length + library.pieces.filter((piece) => piece.where === "main").length);
  // On a map read at the list's own revision, the link needs no words.
  const same = { ...scene.meta, revision: main.revision, source_base_url: scene.meta.source_base_url.replace(at, `/blob/${main.full_revision}/`) };
  const piece = library.piece("maintained_chemical_reservoirs@1");
  assert.equal(describe(library, "laws:maintained_chemical_reservoirs@1", { map: same }).sources[0].where, piece.read.found_by);
  // Where the main checkout is here to ask, every file linked is there at that revision.
  const common = spawnSync("git", ["-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8" }).stdout.trim();
  const repo = common ? path.dirname(common) : null;
  if (!repo || spawnSync("git", ["-C", repo, "cat-file", "-e", `${main.full_revision}^{commit}`]).status !== 0) return t.skip("the main checkout, or the list's revision, is not here to ask");
  for (const file of new Set(linked)) assert.equal(spawnSync("git", ["-C", repo, "cat-file", "-e", `${main.full_revision}:${file}`]).status, 0, `${file} is not at ${main.full_revision}`);
});

test("a piece whose Engine view box is not drawn says so, and no link leads to a box that is not drawn", async () => {
  const { describe, doorsFor, drawnIn } = await import("../src/lenses/laws_card.js");
  const library = new Library(raw);
  const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
  const without = { ...scene, entities: scene.entities.filter((entity) => entity.id !== "laws.pumps") };
  const drawn = drawnIn(without);
  const nak = describe(library, "laws:nak_atp_mass_action_positive@1", { drawn });
  assert.match(nak.facts.find(([label]) => label === "Status")[1], /Its box when the list was read, Pumps, is not on the Engine view now\./);
  assert.ok(!/established|implemented|qualified/i.test(nak.facts.find(([label]) => label === "Status")[1]), "a gone box's status is not said");
  assert.deepEqual(nak.related, [], "no link to it");
  // Every link a panel offers leads to a box the page draws, whichever box is missing.
  for (const scenePart of [scene, without]) {
    const isDrawn = drawnIn(scenePart);
    for (const piece of library.pieces) for (const group of describe(library, `laws:${piece.id}`, { drawn: isDrawn }).related || []) for (const id of group.ids) assert.ok(isDrawn(id), `${piece.id} links ${id}, which is not drawn`);
    for (const frame of library.frames) for (const group of describe(library, `laws:${frame.id}`, { drawn: isDrawn }).related || []) for (const id of group.ids) assert.ok(isDrawn(id), `${frame.id} links ${id}`);
  }
  // Standing alone, with no Engine view, nothing is said of the boxes beyond what the list read.
  assert.equal(drawnIn({ entities: [] }), null);
  assert.match(describe(library, "laws:nak_atp_mass_action_positive@1").facts.find(([label]) => label === "Status")[1], /a status of the box, not of the piece/);
  // The door counts only the pieces the map shows.
  const [door] = doorsFor({ id: "laws.pumps" }, { laws: raw });
  assert.equal(door.label, `Show its ${library.inBox("laws.pumps").length} pieces in the Laws library`);
});
