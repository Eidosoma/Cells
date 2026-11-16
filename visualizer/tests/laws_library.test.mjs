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
import { LawsLens, LAWS_LOOK } from "../src/lenses/laws.js";

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
  for (const id of ["bounding_patch_damage@1", "ph_conditioned_factor@1", "bounding_patch_constant_field@1"]) {
    assert.ok(apart.has(id), `${id} is kept apart as not registered`);
    assert.ok(!byId.has(id), `${id} is not a piece yet`);
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

function lensFor({ moving = false, width = 1600, height = 1000 } = {}) {
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
  const palette = { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", dark: false };
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const dressed = [];
  const stage = {
    palette, scene: new THREE.Scene(), camera, width, height, reducedMotion: !moving, invalidate() {},
    rig: { setView(view) { camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance)); camera.lookAt(view.target); camera.updateMatrixWorld(); }, flyTo() {}, distance: 100 },
    dress: (fit) => dressed.push(fit),
  };
  const lens = new LawsLens(stage, { raw: { laws: raw } }, labels);
  lens.activate();
  return { lens, stage, shown, dressed };
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
    assert.equal(lens.lines.children.length, expectedSlots(piece).size, `${piece.id}: one line to each slot`);
  }
});

test("a chosen frame lights exactly its pieces on the wall", () => {
  const { lens } = lensFor();
  for (const frame of raw.frames) {
    lens.setSelection(`laws:${frame.id}`);
    const expected = new Set(raw.pieces.filter((piece) => piece.declared_by.some((entry) => entry.frame === frame.id)).map((piece) => piece.id));
    assert.deepEqual(lens.lights().bars, expected, frame.id);
    assert.equal(lens.lines.children.length, frame.rows.reduce((sum, row) => sum + row.pieces.length, 0), `${frame.id}: a line from each of its slots`);
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
    if (piece.registry === "an older family") assert.ok(chips.includes("In an older family"), piece.id);
    if (piece.registry === "no registry") assert.ok(chips.includes("A named law in no registry"), piece.id);
    if (piece.read?.fields?.unversioned) assert.match(entity.facts.find(([label]) => label === "Version")[1], /no version/, piece.id);
  }
  for (const frame of raw.frames) assert.equal(lens.describe(`laws:${frame.id}`).status, null, `${frame.id}: a frame takes no status from its parts`);
});

test("it asks the stage for the page's look, and hands it back as it found it", () => {
  const { lens, dressed, stage } = lensFor();
  assert.deepEqual(dressed[0], LAWS_LOOK);
  assert.equal(lens.materials.line.toneMapped, false, "what is chosen stays out of filmic light");
  assert.equal(lens.materials.line.userData.noContact, true, "and out of contact shade");
  lens.deactivate();
  assert.deepEqual(dressed.at(-1), { rich: false });
  assert.ok(!stage.scene.children.includes(lens.root));
});

test("with less motion asked for nothing eases: the lines stand at once", () => {
  const still = lensFor({ moving: false }).lens;
  still.setSelection("laws:kv1p5_mh@1");
  assert.equal(still.growth, 1);
  assert.equal(still.update(16), false, "nothing is left to move");
  const moving = lensFor({ moving: true }).lens;
  moving.setSelection("laws:kv1p5_mh@1");
  assert.equal(moving.growth, 0);
  assert.equal(moving.update(16), true, "the line grows toward its slot");
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

test("a tall screen stacks the wall in bands of five and the frames one above another", () => {
  const { lens } = lensFor({ width: 400, height: 860 });
  lens.update(16);
  assert.equal(lens.narrow, true);
  const bands = new Set(lens.layout.heads.map((head) => head.band));
  assert.equal(bands.size, Math.ceil(raw.families.length / 5));
  const [inner, composite] = lens.layout.frames;
  assert.ok(inner.y > composite.y, "the inner model stands above the composite");
  assert.ok(lens.layout.bounds.maxX - lens.layout.bounds.minX < 12, "and the picture is narrow");
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
