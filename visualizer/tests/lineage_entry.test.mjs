// The origin-of-life view on the map's page (src/lenses/lineage_entry.js): its registration with
// the seam, the run it plays, its choices on the page's card, and the example's mark kept where
// the picture is free of the page's cards. No WebGL: the view only makes objects.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { entryView, fitView } from "../src/ui/entry_views.js";
import { runToPlay, mergeRunFiles } from "../src/lenses/lineage_entry.js";
import { CLUSTER_WHERE_SMALL_OR_STILL } from "../src/lenses/lineage.js";

const example = JSON.parse(readFileSync(path.join(ROOT, "data", "origin", "example-run.json"), "utf8"));
const forms = JSON.parse(readFileSync(path.join(ROOT, "tests", "fixtures", "assembly-forms", "forms.json"), "utf8"));
const entry = { ...JSON.parse(readFileSync(path.join(ROOT, "data", "models", "gard.json"), "utf8")), runs: [{ file: "data/origin/example-run.json", label: "An example of invented numbers", kind: "example", path: "models/gard/example-run.json" }] };

function made({ width = 1400, height = 900, runs = [{ kind: "example", data: example }], blocked = null } = {}) {
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const stage = { palette: { dark: false }, scene: new THREE.Scene(), camera, width, height, reducedMotion: true, invalidate() {}, decoration: { moving: false, time: 0 }, dress() {},
    rig: { setView(view) { camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance)); camera.lookAt(view.target); camera.updateMatrixWorld(); }, flyTo(view) { this.setView(view); } } };
  const shown = [];
  const labels = { keepClear: { top: 60 }, blocked, add: (spec) => { const item = { ...spec, hidden: false, width: spec.text.length * 6, height: 20 }; shown.push(item); return item; }, clear: () => shown.splice(0), remove() {} };
  const registration = entryView("assembly");
  const view = fitView(registration.make(stage, null, labels, { entry, runs, autoplay: false }), entry, registration);
  view.activate();
  view.update(16, 0, 16);
  return { view, stage, shown };
}

test("the view is registered for model systems of kind assembly, with a short name for a phone's bar", () => {
  const registration = entryView("assembly");
  assert.ok(registration, "registered");
  assert.equal(registration.label, "Origin of life");
  // That the bar keeps to one row with it is held in a browser at 390 px, with the page's font and with its
  // stand-in (tools/check_species.mjs, CASE=model): the viewer tightens the bar where its words would not fit.
  assert.equal(registration.short, "Origin");
  assert.ok(registration.styles.page.includes("--origin-type-1") && registration.styles.shadow.includes(".swatch-origin-type-1"));
});

test("it plays the engine's runs wherever the entry names any (read together), and the example where it names none", () => {
  assert.equal(runToPlay([{ kind: "development", data: forms }, { kind: "example", data: example }]), forms);
  assert.equal(runToPlay([{ kind: "development", data: forms }]), forms);
  assert.equal(runToPlay([{ kind: "example", data: example }]), example);
  assert.equal(runToPlay([]), null);
  // Two files of one world are read as one: the environment once, the runs side by side.
  const [a, b] = forms.runs.map((run) => ({ ...forms, runs: [run] }));
  const merged = runToPlay([{ kind: "development", data: a }, { kind: "development", data: b }]);
  assert.equal(merged.environments.length, 1);
  assert.deepEqual(merged.runs.map((run) => run.id), forms.runs.map((run) => run.id));
  // An example is never read with them, and two worlds under one id are refused.
  assert.throws(() => mergeRunFiles([a, example]), /example/);
  const other = { ...b, environments: b.environments.map((environment) => ({ ...environment, reservoir: { each: 0.5 } })) };
  assert.throws(() => mergeRunFiles([a, other]), /differently/);
});

test("its choices reach the page's card: the similarity always, the two forms of the law only for two real runs of one world", () => {
  const { view } = made();
  const choices = view.chrome().card.choices.map((item) => item.key);
  assert.deepEqual(choices, ["compare"], "the example is never one of a pair");
  view.chrome().card.choices[0].set("other");
  assert.equal(view.compare, "other");
  const pair = made({ runs: [{ kind: "development", data: forms }] }).view;
  const offered = pair.chrome().card.choices.find((item) => item.key === "pair");
  assert.ok(offered && /two forms of the law/.test(offered.label));
  offered.set("pair");
  assert.equal(pair.sides.length, 2);
  assert.equal(pair.chrome().rail.length, 4, "its levels on the rail");
  assert.equal(pair.chrome().railTitle, "Level");
});

test("the example's mark stands at the first place free of the page's cards, under the bar, at every level", () => {
  // A card on the left and one across the top middle, as a phone's card and a rail's button might stand.
  const cards = [{ left: 16, top: 68, right: 300, bottom: 320 }, { left: 600, top: 60, right: 900, bottom: 140 }];
  const { view, stage, shown } = made({ blocked: () => cards });
  const mark = () => shown.find((label) => label.text === example.example.says);
  const point = new THREE.Vector3();
  for (const level of ["molecules", "population", "lineage", "assembly"]) {
    view.setLevel(level);
    view.update(16, 0, 16);
    const tag = mark();
    point.copy(tag.anchor).project(stage.camera);
    point.set((point.x * 0.5 + 0.5) * stage.width, (-point.y * 0.5 + 0.5) * stage.height, point.z);
    const top = point.y - tag.height - tag.lift, box = { left: point.x - tag.width / 2, right: point.x + tag.width / 2, top, bottom: top + tag.height };
    assert.ok(top >= 60, `${level}: under the bar (${top})`);
    assert.ok(cards.every((card) => box.right <= card.left || box.left >= card.right || box.bottom <= card.top || box.top >= card.bottom), `${level}: clear of the cards: ${JSON.stringify(box)}`);
    assert.ok(box.left >= 0 && box.right <= stage.width, `${level}: inside the window`);
  }
});

test("turning back to the cluster on a phone and with less motion is one line", () => {
  assert.equal(typeof CLUSTER_WHERE_SMALL_OR_STILL, "boolean");
  const source = readFileSync(path.join(ROOT, "src", "lenses", "lineage.js"), "utf8");
  assert.equal(source.match(/^export const CLUSTER_WHERE_SMALL_OR_STILL = (true|false);$/gm)?.length, 1);
});
