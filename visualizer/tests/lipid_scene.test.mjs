// The assembly as lipids in water (src/lenses/lipid_assembly.js, lipid_marks.js, lipid_water.js),
// driven through the view (src/lenses/lineage.js) with stand-ins for the stage and the labels: heads
// to the water and tails in; the molecules divided as the run records, and the neck drawn on the
// union of the two daughters; the founder's gathering, the picture's own, only at a run's start and
// never with less motion; the free molecules, a function of the water's clock alone and never in the
// camera's way; nothing made per frame; the words the picture says of itself; and the water handed
// back. No WebGL: the view only makes objects.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { LineageLens, OWN_WORDS, GATHER_WORDS, CLUSTER_WHERE_SMALL_OR_STILL } from "../src/lenses/lineage.js";
import { GATHER_S, CROWD, neckField, FreeCrowd } from "../src/lenses/lipid_assembly.js";
import { HEAD, FORMS } from "../src/lenses/lipid_marks.js";
import { PROTOCELL } from "../src/lenses/lipid_assembly.js";
import { NETWORK, networkOf } from "../src/lenses/protocell_marks.js";
import { MOTES } from "../src/lenses/lipid_water.js";

const text = readFileSync(path.join(ROOT, "data", "origin", "example-run.json"), "utf8");
const example = () => JSON.parse(text);
const entry = JSON.parse(readFileSync(path.join(ROOT, "data", "models", "gard.json"), "utf8"));

function lensFor({ moving = true, width = 1600, height = 1000, autoplay = false, withEntry = false } = {}) {
  const shown = [];
  const labels = {
    shown,
    add: (spec) => { const item = { ...spec, hidden: false }; shown.push(item); return item; },
    clear: () => shown.splice(0),
    remove: (item) => shown.splice(shown.indexOf(item), 1),
  };
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const decoration = { moving, time: 0 };
  const stage = {
    palette: { dark: false, accent: "#1f6fd0", bg: "#eef2f6", fg: "#12283a" }, scene: new THREE.Scene(), camera, width, height, reducedMotion: !moving, invalidate() {}, decoration,
    rig: { setView(view) { camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance)); camera.lookAt(view.target); camera.updateMatrixWorld(); }, flyTo(view) { this.setView(view); } },
    dress() {},
  };
  const lens = new LineageLens(stage, null, labels, example(), { entry: withEntry ? entry : null, autoplay });
  lens.activate();
  lens.update(16, 0, 16);
  return { lens, stage, shown, decoration };
}
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const length = (a) => Math.hypot(a[0], a[1], a[2]);

test("heads to the water and tails in: every lipid of the micelle faces out from its centre, on its surface", () => {
  const { lens } = lensFor({ moving: false });
  lens.setShape("micelle");
  lens.player.seek(40.5);
  lens.update(16, 0, 16);
  const layout = lens.sides[0].layout, R = layout.radius(layout.counts[0]);
  assert.equal(layout.beads.length, layout.counts[0]);
  for (const bead of layout.beads) {
    const out = sub(bead.pos, layout.centres[0]);
    assert.ok(dot(out, bead.axis) / length(out) > 0.95, "the head faces the water");
    assert.ok(Math.abs(length(out) - R) < HEAD, "the head stands on the surface");
    assert.ok(bead.tailLength > 0 && bead.tailLength <= R, "the tails reach inward, no deeper than the centre");
  }
});

test("at a fission the molecules are divided as the run records, and while the daughters overlap the heads lie on the neck", () => {
  const { lens } = lensFor({ moving: false });
  lens.setShape("micelle");
  const run = lens.mainRun, k = 37;
  for (const part of [0.15, 0.3, 0.5, 0.9]) {
    lens.player.seek(k - 0.15 + part * 0.3);
    lens.update(16, 0, 16);
    const layout = lens.sides[0].layout;
    const kept = new Int32Array(run.n), let_go = new Int32Array(run.n);
    for (const bead of layout.beads) (bead.side === 0 ? kept : let_go)[bead.type]++;
    assert.deepEqual(Array.from(kept), Array.from(run.carried(k)), `${part}: the daughter that carries on holds what the run says`);
    assert.deepEqual(Array.from(let_go), Array.from(run.other(k)), `${part}: and the other`);
    const balls = [0, 1].map((s) => ({ c: layout.centres[s], r: layout.radius(layout.counts[s]) }));
    const k2 = 0.42 * Math.max(balls[0].r, 0.5);
    for (const bead of layout.beads) {
      const surface = [0, 1, 2].map((a) => bead.pos[a] - bead.axis[a] * HEAD * 0.15);
      assert.ok(Math.abs(neckField(surface, balls, k2).f) < 0.02, `${part}: a head off the surface of the two daughters: ${neckField(surface, balls, k2).f}`);
    }
  }
});

test("the founder gathers from the water only at a run's start, while the clock stands; then the page may play it", () => {
  const { lens } = lensFor({ autoplay: true });
  const layout = lens.sides[0].layout;
  assert.equal(layout.gathering, true, "at the start the founder gathers");
  assert.equal(layout.beads.length, 40);
  lens.player.play();
  for (let frame = 0; frame < 60; frame++) lens.update(16, 0, 16);
  assert.equal(lens.player.time, 0, "the clock stands while the founder gathers");
  for (let frame = 0; frame < (GATHER_S + 0.5) * 60; frame++) lens.update(16, 0, 16);
  assert.equal(layout.gathering, false, "gathered");
  for (let frame = 0; frame < 30; frame++) lens.update(16, 0, 16);
  assert.ok(lens.player.time > 0, "then the clock goes on");
  lens.player.pause();
  lens.player.seek(12.4);
  lens.update(16, 0, 16);
  assert.equal(layout.gathering, false, "a jump elsewhere does not gather");
  lens.player.seek(0);
  lens.update(16, 0, 16);
  assert.equal(layout.gathering, true, "back at the start, the founder gathers again");
  const still = lensFor({ moving: false, autoplay: true }).lens;
  assert.equal(still.sides[0].layout.gathering, false, "with less motion the founder stands gathered");
  for (let frame = 0; frame < 30; frame++) still.update(16, 0, 16);
  assert.equal(still.player.playing, false, "and the page does not play by itself");
});

test("the free molecules: the supply's mix, the picture's number, a function of the water's clock, never in the camera's way", () => {
  const { lens, stage } = lensFor();
  assert.equal(lens.crowd.count, CROWD.wide);
  const types = new Set(lens.crowd.all.map((free) => free.type));
  assert.ok([...types].every((type) => type >= 0 && type < lens.mainEnvironment.count));
  assert.ok(types.size > 40, "every type alike, as the run holds every type at one concentration");
  const centre = [0, 1.85, 0], eye = stage.camera.position.toArray();
  const once = lens.crowd.at(12.5, centre, eye), again = new FreeCrowd(lens.mainEnvironment).at(12.5, centre, eye);
  assert.deepEqual(once.map((free) => free.pos), again.map((free) => free.pos), "where each stands is the water's clock's alone");
  const toEye = sub(eye, centre), far = length(toEye);
  for (const free of once) {
    const p = sub(free.pos, centre), along = dot(p, toEye) / far;
    if (along <= 0 || along >= far) continue;
    const side = Math.sqrt(Math.max(0, dot(p, p) - along * along));
    assert.ok(side >= 1.9 - 1e-6, `a free molecule between the camera and the assembly: ${side}`);
  }
  assert.equal(lensFor({ width: 400, height: 860 }).lens.crowd.count, CROWD.narrow);
  assert.equal(lens.water.moteCount, MOTES.wide);
});

test("nothing is made per frame: the same geometries and materials before and after playing through fissions at every speed", () => {
  const { lens } = lensFor();
  const made = () => {
    const ids = new Set();
    for (const root of [lens.root, lens.water.group]) root.traverse((object) => {
      if (object.geometry) ids.add(object.geometry.uuid);
      for (const material of Array.isArray(object.material) ? object.material : object.material ? [object.material] : []) {
        ids.add(material.uuid);
        if (material.map) ids.add(material.map.uuid);
      }
    });
    return ids;
  };
  lens.player.seek(20.3);
  lens.update(16, 0, 16);
  const before = made();
  for (const speed of [0.001, 0.25, 1, 8]) {
    lens.player.setSpeed(speed);
    lens.player.play();
    for (let frame = 0; frame < 90; frame++) lens.update(16, 0, 16);
  }
  assert.deepEqual([...made()].sort(), [...before].sort());
});

test("the picture says what is its own: on the picture, in the legend, and while the founder gathers", () => {
  const { lens, shown } = lensFor({ withEntry: true });
  assert.ok(shown.some((label) => label.text === OWN_WORDS), "the line on the picture");
  const gather = shown.find((label) => label.text === GATHER_WORDS);
  assert.ok(gather && !gather.hidden, "said while the founder gathers");
  const chrome = lens.chrome();
  assert.match(chrome.legend.note.text, /No law of Cells computes how the lipids move and pack/);
  assert.match(chrome.legend.note.text, /^Example: invented numbers · not a run of Cells' engine/);
  assert.match(lens.describe("assembly:assembly").note, /No light shows what helped any one join: the run does not record it/, "no light for what helped a join, where the run records none, and the assembly's panel says so");
  for (const [slot, form] of FORMS.slice(0, 3).entries()) assert.ok(chrome.legend.items[slot].label.includes(form.replace("soft ", "")), `the legend says the form of a leading type's head: ${form}`);
  assert.match(chrome.legend.items[3].label, /round, grey/);
  assert.ok(chrome.legend.items.some((item) => item.swatch === "origin-halo" && /^in, out: /.test(item.label)), "the haloed molecules coming and going are keyed: the run's joins and leaves");
  assert.ok(chrome.timeline && chrome.timeline.player === lens.player, "the page's one clock");
  // The entry's word, and the law's two forms in D192's words, on the card.
  assert.match(chrome.card.text, /Modelled for comparison only \(D197\)|Designed, not modelled\./);
  const facts = lens.describe("assembly:assembly").facts;
  const law = facts.find(([label]) => /two forms/.test(label));
  assert.ok(law && /Kolmogorov's cycle criterion/.test(law[1]) && /docs\/DECISIONS\.md, D192/.test(law[1]), "D192's words, cited");
  assert.match(lens.describe("assembly:assembly").note, /no law of Cells computes how the lipids move and pack/);
});

test("the water is the view's while it is shown, and handed back", () => {
  const { lens, stage } = lensFor();
  assert.ok(stage.scene.children.includes(lens.water.group));
  const fog = stage.scene.fog;
  lens.deactivate();
  assert.ok(!stage.scene.children.includes(lens.water.group), "the water goes with the view");
  assert.equal(stage.scene.fog, fog, "and the scene's own fog is left as it was");
  for (const material of [lens.lipid.heads, lens.lipid.tails, lens.materials.plate]) assert.equal(material.fog, false, "the view's haze, not three.js's fog, so what the camera looks at keeps its colours");
});

test("the protocell: a shell of two faces, heads to the water outside and inside, tails between, every molecule on the picture, the near side see-through", () => {
  const { lens, stage } = lensFor({ moving: false });
  if (!CLUSTER_WHERE_SMALL_OR_STILL) assert.equal(lens.shape, "protocell", "the view opens on the protocell");
  lens.setShape("protocell");
  lens.player.seek(40.5);
  lens.update(16, 0, 16);
  const layout = lens.sides[0].layout, R = layout.radius(layout.counts[0]), c = layout.centres[0];
  let outer = 0, inner = 0;
  for (const bead of layout.beads) {
    const v = sub(bead.pos, c), r = length(v), out = dot(v, bead.axis) / r;
    if (bead.leaflet === 0) {
      outer++;
      assert.ok(out > 0.9 && Math.abs(r - R) < HEAD * PROTOCELL.head, `an outer head faces the water outside, on the outer face (${r} against ${R})`);
    } else {
      inner++;
      assert.ok(out < -0.9 && Math.abs(r - (R - PROTOCELL.thickness)) < HEAD * PROTOCELL.head, `an inner head faces the water inside, on the inner face (${r})`);
    }
    assert.equal(bead.tailLength, PROTOCELL.tail);
  }
  assert.ok(outer > inner && inner > 0, `both faces: ${outer} outside, ${inner} inside`);
  assert.ok(R - PROTOCELL.thickness - HEAD * PROTOCELL.head > 0.35, "an inside that shows, at 40 molecules too");
  // Every molecule is drawn; those on the camera's side see-through, so that the inside shows.
  const drawn = lens.drawn[0].filter((lipid) => !lipid.free);
  assert.equal(drawn.length, layout.beads.length + layout.adrift.length + layout.leavers.length);
  const eye = stage.camera.position.clone().sub(lens.sides[0].group.position).toArray();
  const toward = (lipid) => dot(sub(lipid.pos, c), sub(eye, c));
  const seen = drawn.filter((lipid) => lipid.ghost > 0);
  assert.ok(seen.length > 5 && seen.every((lipid) => toward(lipid) > 0), "the see-through ones are on the near side");
  assert.ok(drawn.some((lipid) => lipid.ghost === 0 && toward(lipid) < 0), "the far side stands solid");
});

test("inside a protocell, the catalytic network is read from the run's own table, among the types it holds; nothing of it pulses with a join", () => {
  const { lens } = lensFor({ moving: false });
  lens.setShape("protocell");
  lens.player.seek(30.55);
  lens.update(16, 0, 16);
  const x = lens.mainRun.compositionAt(30.55), environment = lens.mainEnvironment;
  const [net] = lens.sides[0].network.drawn;
  assert.equal(net.held, x.filter((count) => count > 0).length, "a point for each type held");
  assert.ok(net.links.length > 0 && net.links.length <= NETWORK.wide);
  for (const link of net.links) {
    assert.ok(x[link.from] > 0 && x[link.to] > 0 && link.from !== link.to, "between two types it holds");
    assert.equal(link.v, environment.catalysis(link.to, link.from), "the run's own factor: the column type speeds the row type");
    assert.ok(link.v >= NETWORK.least);
  }
  for (let i = 1; i < net.links.length; i++) assert.ok(net.links[i - 1].v >= net.links[i].v, "the strongest drawn");
  // The same composition gives the same network: a join of a type already held changes no link's strength.
  const again = networkOf(x, environment, NETWORK.wide);
  assert.deepEqual(again.links, net.links);
  lens.setShape("micelle");
  lens.update(16, 0, 16);
  assert.equal(lens.sides[0].network.group.visible, false, "a micelle has no inside to draw");
});

test("with less motion the protocell stands: nothing gathers, streams or glows", () => {
  const { lens } = lensFor({ moving: false });
  lens.player.setSpeed(0.5);
  lens.player.play();
  for (let frame = 0; frame < 180; frame++) lens.update(16, 0, 16);
  assert.deepEqual(lens.sides[0].layout.inMotion(), { flying: 0, glowing: 0 });
  assert.equal(lens.sides[0].layout.leavers.length, 0);
  assert.match(lens.streamWords(), /in place/);
});
