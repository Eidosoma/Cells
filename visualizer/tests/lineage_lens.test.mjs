// The assembly view (src/lenses/lineage.js) driven as the page drives a view, with stand-ins for the
// stage and the labels: its levels, choosing by id, by pointer and by key, the clock's steps, the
// words that must stand, the rule on the 0.9 line, motion at speed, a ceiling on what the scene
// costs, the narrow layout, and less motion. No WebGL: the view only makes objects.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { LineageLens, LEVELS, ORIGIN_LOOK } from "../src/lenses/lineage.js";
import { FINE, OPENING, LADDER } from "../src/lenses/lineage_clock.js";
import { GLOW_CAP } from "../src/lenses/assembly_beads.js";
import { PARTS } from "../src/lenses/lineage_card.js";

const text = readFileSync(path.join(ROOT, "data", "origin", "example-run.json"), "utf8");
const example = () => JSON.parse(text);

function lensFor({ moving = true, width = 1600, height = 1000, file = example(), entry = null } = {}) {
  const shown = [];
  const labels = {
    shown,
    add: (spec) => { const item = { ...spec, hidden: false }; shown.push(item); return item; },
    clear: () => shown.splice(0),
    remove: (item) => shown.splice(shown.indexOf(item), 1),
  };
  const palette = { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", muted: "#566878", seq0: "#6da7ec", seq1: "#3987e5", seq2: "#256abf", seq3: "#184f95", seq4: "#0d366b", dark: false };
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const views = [], dressed = [];
  const stage = {
    palette, scene: new THREE.Scene(), camera, width, height, reducedMotion: !moving, invalidate() {},
    rig: { setView(view) { views.push(view); camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance)); camera.lookAt(view.target); camera.updateMatrixWorld(); }, flyTo(view) { this.setView(view); } },
    dress: (fit) => dressed.push(fit),
  };
  const lens = new LineageLens(stage, null, labels, file, { entry });
  lens.activate();
  lens.update(16, 0, 16);
  return { lens, stage, shown, views, dressed };
}
const pickAt = (lens, point, from) => {
  lens.root.updateMatrixWorld(true);
  const raycaster = new THREE.Raycaster();
  raycaster.set(from, point.clone().sub(from).normalize());
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

test("its levels are the entry's: molecules, one assembly, population, lineages; an entry may give fewer", () => {
  const { lens, views } = lensFor();
  assert.deepEqual(lens.levels().map((level) => level.id), ["molecules", "assembly", "population", "lineage"]);
  assert.equal(lens.level, "assembly", "it opens on one assembly");
  for (const level of LEVELS) {
    assert.ok(lens.setLevel(level.id), level.id);
    assert.equal(lens.level, level.id);
    assert.ok(views.at(-1).target, `${level.id}: the camera goes to its stop`);
  }
  assert.match(LEVELS.find((level) => level.id === "population").waiting, /Not drawn yet/);
  assert.equal(lens.setLevel("tissue"), false, "a level of the species' list is not this view's");
  const fewer = lensFor({ entry: { levels: [{ id: "assembly", label: "One assembly" }, { id: "lineage", label: "Lineages" }] } }).lens;
  assert.deepEqual(fewer.levels().map((level) => level.id), ["assembly", "lineage"]);
  assert.equal(fewer.setLevel("molecules"), false, "a level the entry lacks is not offered");
});

test("every part in the list can be chosen by id and the panel says what it is; a fission chosen takes the clock there", () => {
  const { lens } = lensFor();
  const listed = lens.sections().flatMap((section) => section.entities.map((entity) => entity.id));
  assert.equal(listed.length, new Set(listed).size, "no id is listed twice");
  assert.ok(listed.includes("assembly:fission:lineage-a:120") && listed.includes("assembly:part:carpet"));
  for (const id of listed) {
    assert.ok(lens.has(id), id);
    const entity = lens.describe(id);
    assert.ok(entity?.label && entity.plain, `${id}: the panel has nothing to say`);
  }
  lens.setSelection("assembly:fission:lineage-a:57");
  assert.equal(lens.player.time, 57, "choosing a fission takes the clock to it");
  assert.equal(lens.sides[0].run.phaseAt(lens.player.time).phase, "split");
  assert.equal(lens.has("laws:kv1p5_mh@1"), false);
  assert.equal(lens.has("assembly:fission:lineage-a:999"), false);
});

test("a part is chosen by pointer: a ray at a post of the fence, the tape, the carpet and a bead", () => {
  const { lens } = lensFor();
  lens.setLevel("lineage");
  lens.player.seek(100);
  lens.update(16, 0, 16);
  const fence = lens.sides[0].fence;
  const top = fence.topOf(50, "carried");
  assert.equal(pickAt(lens, top.clone().add(new THREE.Vector3(0, -0.4, 0)), top.clone().add(new THREE.Vector3(0, -0.4, 12))), "assembly:fission:lineage-a:50");
  const tape = lens.tape;
  const x = tape.xOf(20);
  assert.equal(pickAt(lens, new THREE.Vector3(x, tape.mesh.position.y, tape.mesh.position.z), new THREE.Vector3(x, tape.mesh.position.y, tape.mesh.position.z + 3)), "assembly:fission:lineage-a:20");
  const carpet = lens.carpet.mesh.position;
  assert.match(pickAt(lens, carpet.clone(), carpet.clone().add(new THREE.Vector3(0, 10, 0))) || "", /^assembly:pair:lineage-a:\d+:\d+$/);
  const side = lens.sides[0], bead = side.layout.beads[0];
  const at = new THREE.Vector3(...bead.pos).add(side.group.position);
  assert.equal(pickAt(lens, at, at.clone().add(new THREE.Vector3(...bead.dir).multiplyScalar(6))), `assembly:type:${bead.type}`);
});

test("the keys step a fission at a time, by the page's one clock", () => {
  const { lens } = lensFor();
  lens.player.seek(12.4);
  assert.equal(lens.step(1), "assembly:fission:lineage-a:13");
  assert.equal(lens.player.time, 13);
  lens.step(-1);
  assert.equal(lens.player.time, 12);
  assert.equal(lens.player.playing, false, "a step pauses the clock");
});

test("the clock counts fissions: its ladder, its opening step, molecule by molecule where the run has its trace, and no true speed", () => {
  const { lens } = lensFor();
  const base = lens.player.base;
  assert.equal(base.id, "fission");
  assert.equal(lens.player.speed, OPENING);
  assert.deepEqual(base.speedsFor(lens.player.end), [FINE, ...LADDER]);
  assert.match(base.words(FINE).says, /^Molecule by molecule: 4 molecules join or leave each second of watching/);
  for (const speed of base.speedsFor(lens.player.end)) assert.ok(!/true speed|slowed|times faster/.test(JSON.stringify(base.words(speed))), String(speed));
  assert.equal(base.length(lens.player.end - lens.player.start), "120 fissions");
  // Without a trace no molecule-by-molecule step is offered.
  const bare = example();
  for (const run of bare.runs) delete run.trace;
  const without = lensFor({ file: bare }).lens;
  assert.deepEqual(without.player.base.speedsFor(120), LADDER);
  // Molecule by molecule, the clock moves four molecules a second of watching.
  lens.player.seek(5.3);
  lens.player.setSpeed(FINE);
  lens.player.play();
  const run = lens.mainRun, before = run.phaseAt(lens.player.time);
  lens.player.tick(1000);
  const after = run.phaseAt(lens.player.time);
  assert.equal(after.g, before.g);
  assert.ok(Math.abs(after.e - before.e - 4) <= 1, `four molecules in a second: ${before.e} to ${after.e}`);
});

test("words that must stand: the example's mark on the picture and in the legend, and the picture's choices said", () => {
  const { lens, shown } = lensFor();
  const says = "Example: invented numbers · not a run of Cells' engine";
  for (const level of LEVELS) {
    lens.setLevel(level.id);
    assert.equal(shown.filter((label) => label.text === says).length, 1, `${level.id}: the mark stands at the place shown`);
  }
  lens.setLevel("lineage");
  const chrome = lens.chrome();
  assert.equal(chrome.legend.example, says);
  assert.ok(chrome.stamp.includes(says) && chrome.card.text.includes(says));
  assert.ok(lens.describe("assembly:fission:lineage-a:3").facts.some(([label, value]) => label === "Example" && value.startsWith(says)));
  assert.ok(shown.some((label) => /the shape is the picture's choice/.test(label.text)), "the shape is said to be the picture's");
  assert.ok(shown.some((label) => /the picture's choice/.test(label.text) && /map/i.test(label.text)), "the map's axes are said to be the picture's");
  assert.match(lens.describe("assembly:assembly").note, /the picture's choice/);
  for (const part of PARTS.filter((item) => ["tape", "spine", "map"].includes(item.id))) assert.match(part.note, /picture's choice/, part.id);
  assert.match(lens.describe("assembly:part:carpet").note, /Worked out by the view/);
  // Nothing of the model is named by the code: the heading is the file's.
  assert.equal(chrome.card.heading, example().model.label);
});

test("the 0.9 line stands only on the parent with the daughter carried on, only where the analysis states it, and the marks are read as written", () => {
  const { lens, shown } = lensFor();
  lens.setLevel("lineage");
  lens.player.seek(120);
  lens.update(16, 0, 16);
  const fence = lens.sides[0].fence;
  assert.ok(fence.sheet && fence.sheet.visible, "the analysis's threshold stands on the comparison it was made for");
  assert.ok(shown.some((label) => label.text === "0.9: the analysis's threshold of inheritance"));
  const marks = example().runs[0].analysis.inheritance.marks;
  assert.equal(fence.rings.count, marks.filter((mark) => !mark).length, "a ring for each break the analysis marks");
  assert.equal(fence.caps.count, marks.filter((mark) => mark).length);
  for (const compare of ["other", "grown"]) {
    lens.setCompare(compare);
    lens.update(16, 0, 16);
    assert.equal(fence.sheet.visible, false, `${compare}: no threshold on another comparison`);
    assert.equal(fence.rings.count, 0, `${compare}: no mark on another comparison`);
  }
  // A mark against its own H is drawn as marked: the view decides nothing.
  const flipped = example();
  const k = flipped.runs[0].analysis.inheritance.marks.indexOf(true) + 1;
  flipped.runs[0].analysis.inheritance.marks[k - 1] = false;
  const other = lensFor({ file: flipped }).lens;
  other.player.seek(120);
  other.update(16, 0, 16);
  assert.ok(other.sides[0].run.similarityAt(k).carried > 0.9);
  assert.ok(other.sides[0].fence.ringK.includes(k), "drawn as the analysis marks it");
  // No analysis: no sheet, no ring, no label of a threshold.
  const bare = example();
  delete bare.runs[0].analysis;
  const none = lensFor({ file: bare });
  none.lens.setLevel("lineage");
  none.lens.player.seek(120);
  none.lens.update(16, 0, 16);
  assert.equal(none.lens.sides[0].fence.sheet, null);
  assert.equal(none.lens.sides[0].fence.rings.count, 0);
  assert.ok(!none.shown.some((label) => /^0\.9/.test(label.text)));
});

test("a composome is ringed and named only where the run's analysis names one", () => {
  assert.equal(lensFor().lens.map.composomes.length, 0, "the example names none, and the map names none");
  const named = example();
  named.runs[0].analysis.composomes = { method: "a test's own, no clustering", names: [{ id: "c1", label: "C1", fissions: [60, 61, 62, 63] }] };
  const { lens, shown } = lensFor({ file: named });
  lens.setLevel("lineage");
  assert.equal(lens.map.composomes.length, 1);
  assert.ok(shown.some((label) => label.text === "C1: named by the run's analysis"));
  assert.match(lens.describe("assembly:fission:lineage-a:61").facts.find(([label]) => label === "Composome")[1], /named by the run's analysis \(a test's own/);
});

test("motion at speed: molecules fly only molecule by molecule; at fission steps they glow in place, within a bound, and from two a second not at all", () => {
  const bound = { flying: 0, glowing: 0 };
  const watch = (speed, seconds = 6) => {
    const { lens } = lensFor();
    lens.player.seek(20.3);
    lens.player.setSpeed(speed);
    lens.player.play();
    let worst = { flying: 0, glowing: 0 };
    for (let frame = 0; frame < seconds * 60; frame++) {
      lens.update(16, 0, 16);
      const now = lens.sides[0].layout.inMotion();
      worst = { flying: Math.max(worst.flying, now.flying), glowing: Math.max(worst.glowing, now.glowing) };
    }
    return worst;
  };
  const fine = watch(FINE);
  assert.ok(fine.flying >= 1 && fine.flying <= 4, `molecule by molecule, at most four in flight: ${JSON.stringify(fine)}`);
  for (const speed of [0.25, 0.5, 1]) {
    const seen = watch(speed);
    assert.equal(seen.flying, 0, `${speed}: none flies`);
    assert.ok(seen.glowing <= GLOW_CAP, `${speed}: at most ${GLOW_CAP} glow at once: ${JSON.stringify(seen)}`);
  }
  for (const speed of [2, 8]) assert.deepEqual(watch(speed, 3), bound, `${speed}: nothing flies or glows`);
});

test("less motion: the cluster, nothing flies or glows, nothing eases", () => {
  const { lens } = lensFor({ moving: false });
  assert.equal(lens.shape, "cluster");
  lens.player.setSpeed(FINE);
  lens.player.play();
  for (let frame = 0; frame < 120; frame++) lens.update(16, 0, 16);
  assert.deepEqual(lens.sides[0].layout.inMotion(), { flying: 0, glowing: 0 });
  lens.player.pause();
  lens.update(16, 0, 16);
  assert.equal(lens.update(16, 0, 16), false, "paused, nothing is left to move");
});

test("a pair under one clock, each labelled with its own law", () => {
  const { lens, shown } = lensFor();
  lens.setPair(true);
  lens.update(16, 0, 16);
  assert.equal(lens.sides.length, 2);
  for (const run of example().runs) assert.ok(shown.some((label) => label.text === `${run.label}: ${run.law.name}`), run.id);
  lens.player.seek(44);
  lens.update(16, 0, 16);
  assert.deepEqual(lens.sides.map((side) => side.phase.k), [44, 44], "both runs at the same fission");
});

test("what the scene costs to draw: one assembly, the lineage, and the pair (ceilings about a fifth above what it costs)", () => {
  const { lens } = lensFor();
  lens.player.seek(120);
  lens.update(16, 0, 16);
  const assembly = lens.cost();
  assert.ok(assembly.draws <= 9 && assembly.triangles <= 9000, `one assembly: ${JSON.stringify(assembly)}`);
  lens.setLevel("lineage");
  lens.update(16, 0, 16);
  const one = lens.cost();
  assert.ok(one.draws <= 37 && one.triangles <= 55000, `the lineage, one run: ${JSON.stringify(one)}`);
  lens.setPair(true);
  lens.player.seek(120);
  lens.update(16, 0, 16);
  const pair = lens.cost();
  assert.ok(pair.draws <= 54 && pair.triangles <= 100000, `the lineage, the pair: ${JSON.stringify(pair)}`);
});

test("a run of another model than its entry's is refused; the threshold is a part only where the analysis states one", () => {
  assert.throws(() => lensFor({ entry: { id: "another-model" } }), /not of the entry another-model/);
  assert.equal(lensFor({ entry: { id: example().model.id } }).lens.set.model.id, example().model.id);
  const bare = example();
  delete bare.runs[0].analysis;
  const none = lensFor({ file: bare }).lens;
  assert.equal(none.has("assembly:threshold"), false, "no threshold part where the analysis states none");
  assert.equal(lensFor().lens.describe("assembly:threshold").label, "The analysis's threshold, 0.9");
});

test("a tall screen: the narrow layout, the cluster, and the lineage seen at a slant", () => {
  const { lens, views } = lensFor({ width: 400, height: 860 });
  lens.update(16, 0, 16);
  assert.equal(lens.narrow, true);
  assert.equal(lens.shape, "cluster", "on a phone the cluster, unless the visitor chose the micelle");
  assert.equal(lens.sides[0].layout.axis, 1, "on a tall screen the daughters part up and down");
  lens.player.seek(30);
  lens.update(16, 0, 16);
  const [carried, other] = lens.sides[0].layout.centres;
  assert.ok(carried[0] === 0 && other[0] === 0 && other[1] > carried[1], "and not across");
  lens.setLevel("lineage");
  assert.ok(views.at(-1).azimuth > 0.6, "the lineage recedes into the screen");
  const chosen = lensFor({ width: 1600, height: 1000 }).lens;
  chosen.setShape("micelle");
  chosen.stage.width = 400; chosen.stage.height = 860;
  chosen.update(16, 0, 16);
  assert.equal(chosen.shape, "micelle", "a shape the visitor chose is kept");
});

test("it asks the stage for the page's look, keeps the types' colours out of filmic light, and hands the look back", () => {
  const { lens, dressed, stage } = lensFor();
  assert.deepEqual(dressed[0], ORIGIN_LOOK);
  assert.equal(lens.materials.lead.toneMapped, false);
  assert.equal(lens.materials.ring.toneMapped, false);
  assert.equal(lens.tokens.fromTokens, false, "a stand-in stage has no page to read the view's tokens from: the page's neutral ones stand in");
  lens.deactivate();
  assert.deepEqual(dressed.at(-1), { rich: false });
  assert.ok(!stage.scene.children.includes(lens.root));
});
