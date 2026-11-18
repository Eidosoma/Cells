// The assembly view playing the engine's own runs: two runs of one world, one of each form of the law,
// adapted by tools/adapt_assembly_run.py from their folder where it is at hand (ASSEMBLY_RUNS names
// it, as in tests/adapt_assembly_run.test.mjs; skipped where it is not). Nothing of them is committed:
// the files are made here, in a scratch folder, as the check-only scene makes them.
//
// What must stand: the pair side by side on a wide screen, the engine's passive law first; one at a
// time on a phone, by a switch; the run's standing, revision and model as the mark, and no word of an
// example; what the run states of its law's check and its ledger, line by line as it states it; the
// stream and the membership by the run's own event times; and a ceiling on what the pair costs.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { LineageLens } from "../src/lenses/lineage.js";
import { mergeRunFiles } from "../src/lenses/lineage_entry.js";
import { FINE } from "../src/lenses/lineage_clock.js";
import { STREAM_CAP } from "../src/lenses/lipid_assembly.js";

const REAL = process.env.ASSEMBLY_RUNS || "/mnt/workspaces/Cells::gard-g1-part2-20261117/probes-6af93a51/probes/lineage,gard-g1-part2-20261117/probes-6af93a51/probes/lineage_single_event";
const [REAL_ROOT, REAL_LIST] = REAL.split("::");
const REAL_RUNS = (REAL_LIST || "").split(",").filter(Boolean);
const here = REAL_RUNS.length > 0 && REAL_RUNS.every((run) => existsSync(path.join(REAL_ROOT, run, "run.json")));
const skip = here ? false : `the engine's run folders are not at hand (${REAL})`;

let files = null;
function adapted() {
  if (files) return files;
  const dir = mkdtempSync(path.join(tmpdir(), "lineage-engine-"));
  try {
    const run = spawnSync("python3", ["-I", path.join(ROOT, "tools", "adapt_assembly_run.py"), "--evidence", REAL_ROOT, "--out", dir, "--standing", "development", "--standing-from", "a test", ...REAL_RUNS], { encoding: "utf8" });
    assert.equal(run.status, 0, run.stderr);
    files = readdirSync(dir).sort().map((name) => JSON.parse(readFileSync(path.join(dir, name), "utf8")));
    return files;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
const entry = () => ({ ...JSON.parse(readFileSync(path.join(ROOT, "data", "models", "gard.json"), "utf8")), runs: [] });

function lensFor({ moving = true, width = 1600, height = 1000 } = {}) {
  const shown = [];
  const labels = {
    shown,
    add: (spec) => { const item = { ...spec, hidden: false }; shown.push(item); return item; },
    clear: () => shown.splice(0),
    remove: (item) => shown.splice(shown.indexOf(item), 1),
  };
  const palette = { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", muted: "#566878", seq0: "#6da7ec", seq1: "#3987e5", seq2: "#256abf", seq3: "#184f95", seq4: "#0d366b", dark: false };
  const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 5000);
  const stage = {
    palette, scene: new THREE.Scene(), camera, width, height, reducedMotion: !moving, invalidate() {},
    rig: { setView(view) { camera.position.copy(view.target).add(new THREE.Vector3(Math.sin(view.azimuth) * Math.sin(view.polar), Math.cos(view.polar), Math.cos(view.azimuth) * Math.sin(view.polar)).multiplyScalar(view.distance)); camera.lookAt(view.target); camera.updateMatrixWorld(); }, flyTo(view) { this.setView(view); } },
    dress() {},
    decoration: { moving: false, time: 0 },
  };
  const lens = new LineageLens(stage, null, labels, mergeRunFiles(adapted()), { entry: entry() });
  lens.activate();
  lens.update(16, 0, 16);
  return { lens, stage, shown };
}

const EXAMPLE_WORDS = /invented numbers|Example:/;

test("on a wide screen it opens on the pair: the engine's passive law first, the comparison model beside it, each named by its run, its form and the engine's name for its law", { skip }, () => {
  const { lens, shown } = lensFor();
  assert.equal(lens.pair, true);
  assert.deepEqual(lens.sides.map((side) => side.run.form), ["pair-consistent", "single-event"]);
  const [passive, comparison] = lens.sides.map((side) => side.run);
  const said = shown.filter((label) => !label.hidden).map((label) => label.text);
  assert.ok(said.includes(`${passive.label}: the pair-consistent form, the engine's passive law (${passive.law.engine_name})`), said.join(" | "));
  assert.ok(said.includes(`${comparison.label}: the preprint's single-event form, the comparison model (D192) (${comparison.law.engine_name})`), said.join(" | "));
  // The mark: the run's standing, its revision and the engine's model, on the picture, in the legend, in the bar and on the card.
  const mark = `Development run of the engine, not judged · ${passive.raw.revision.slice(0, 8)} · ${passive.provenance.model}`;
  assert.equal(lens.mark, mark);
  const chrome = lens.chrome();
  assert.ok(said.includes(mark), "on the picture");
  assert.equal(chrome.legend.example, mark);
  assert.ok(chrome.stamp.startsWith(mark) && chrome.card.text.startsWith(mark));
  // No word of an example anywhere, and no word that says which form is right.
  const everything = [chrome.stamp, chrome.card.text, chrome.legend.note.text, ...chrome.legend.items.map((item) => item.label), ...said, ...["assembly:assembly", `assembly:run:${passive.id}`, `assembly:run:${comparison.id}`, `assembly:fission:${comparison.id}:37`].flatMap((id) => { const d = lens.describe(id); return [d.plain, d.note, ...d.facts.flat(), ...d.chips.map((chip) => chip.label)]; })].filter(Boolean).join("\n");
  assert.doesNotMatch(everything, EXAMPLE_WORDS);
  assert.doesNotMatch(everything, /\b(wrong|incorrect|better|worse|unphysical|is right)\b/i);
  // A run of the engine carries no analysis: no threshold, and no key of marks it does not make.
  lens.setLevel("lineage");
  assert.equal(lens.mainRun.threshold, null);
  assert.ok(!lens.chrome().legend.items.some((item) => /threshold|bead: inherited/.test(item.label)));
});

test("what each run states of its law's check and of its ledger is in its panel, line by line, as the run states it", { skip }, () => {
  const { lens } = lensFor();
  for (const run of lens.pairRuns) {
    const panel = lens.describe(`assembly:run:${run.id}`);
    for (const line of run.raw.states.lines) assert.ok(panel.facts.some(([label, value]) => label === line.path && value === `${line.text}${line.unit ? ` ${line.unit}` : ""}`), `${run.id}: ${line.path}`);
    assert.ok(panel.facts.some(([label, value]) => label === "Revision" && value.startsWith(run.raw.revision)));
    assert.ok(panel.facts.some(([label, value]) => label === "Laws" && value.includes(run.law.engine_name)));
    assert.ok(lens.sections().some((section) => section.entities.some((entity) => entity.id === `assembly:run:${run.id}`)), "listed");
    // A fission's panel names the run's own carrier keys.
    assert.match(lens.describe(`assembly:fission:${run.id}:37`).facts.find(([label]) => label === "Carrier keys")[1], /^the parent \d+:\d+; the first daughter \d+:\d+, the second \d+:\d+/);
  }
  // The ledger's line for each form, as the run states it: closure for the passive form, the residual it reports for the driven one.
  const closure = (run) => Object.fromEntries(run.raw.states.lines.filter((line) => line.path.startsWith("ledger.closure.")).map((line) => [line.path.slice(15), line.text]));
  assert.equal(closure(lens.pairRuns[0]).holds, "true");
  assert.equal(closure(lens.pairRuns[1]).holds, "false");
  assert.match(closure(lens.pairRuns[1]).reads, /unsourced cycle work/);
});

test("on a phone one run at a time, the engine's default first, with a switch to the other; wide again, the pair", { skip }, () => {
  const { lens, stage } = lensFor({ width: 400, height: 800 });
  assert.equal(lens.pair, false);
  assert.equal(lens.sides.length, 1);
  assert.equal(lens.mainRun.form, "pair-consistent");
  const choice = lens.chrome().card.pair;
  assert.deepEqual(choice.options.map(([value]) => value), lens.pairRuns.map((run) => run.id), "no side by side on a phone");
  lens.setPair(lens.pairRuns[1].id);
  lens.update(16, 0, 16);
  assert.equal(lens.mainRun.form, "single-event");
  assert.equal(lens.sides[0].run.form, "single-event");
  assert.equal(lens.chrome().card.pair.active, lens.pairRuns[1].id);
  // Turned wide, the run chosen stays the one shown (the pair comes back only when asked for).
  stage.width = 1600;
  stage.height = 1000;
  lens.update(16, 0, 16);
  assert.equal(lens.sides.length, 1);
  lens.setPair("pair");
  lens.update(16, 0, 16);
  assert.equal(lens.sides.length, 2);
});

test("the clock spaces each growth's events by the run's own times; molecule by molecule it still walks event by event", { skip }, () => {
  const { lens } = lensFor();
  const run = lens.pairRuns[0];
  assert.ok(run.times && run.times.length === run.events.length);
  for (const g of [0, 17, 63]) {
    const length = run.growthLength(g);
    for (const share of [0.1, 0.37, 0.8]) {
      let expected = 0;
      for (let i = 0; i < length; i++) if (run.times[run.starts[g] + i] / 65535 <= share) expected++;
      assert.equal(run.eventsBy(g, share), expected, `growth ${g} at ${share}`);
    }
    for (let e = 0; e <= length; e += 7) assert.equal(run.phaseAt(run.timeOf(g, e)).e, e, `growth ${g}, ${e} events`);
  }
  // Four molecules a second, whatever the spacing: two seconds from a growth's start see about eight events.
  lens.player.seek(17.2);
  lens.player.setSpeed(FINE);
  const before = run.phaseAt(lens.player.time);
  lens.player.play();
  for (let frame = 0; frame < 120; frame++) lens.update(1000 / 60, 0, 1000 / 60);
  const after = run.phaseAt(lens.player.time);
  assert.equal(after.g, before.g);
  assert.ok(Math.abs(after.e - before.e - 8) <= 1, `${before.e} to ${after.e}`);
});

test("the stream on the engine's pair: never more in flight than the cap on either side, and each holds what its run holds at every moment", { skip }, () => {
  for (const speed of [0.5, 2, 8]) {
    const { lens } = lensFor();
    lens.player.seek(30.3);
    lens.player.setSpeed(speed);
    lens.player.play();
    let worst = 0, seen = 0, frames = 0;
    for (let frame = 0; frame < 4 * 60 && lens.player.playing; frame++) {
      lens.update(16, 0, 16);
      frames++;
      for (const side of lens.sides) {
        worst = Math.max(worst, side.layout.inMotion().flying);
        assert.deepEqual(Array.from(side.layout.members(side.run.n)), Array.from(side.run.compositionAt(lens.player.time)), `${speed}, ${side.run.form}, at ${lens.player.time}`);
      }
      seen += lens.sides.some((side) => side.layout.inMotion().flying > 0) ? 1 : 0;
    }
    assert.ok(worst >= 1 && worst <= STREAM_CAP.wide, `${speed}: ${worst} in flight at most`);
    assert.ok(seen / frames > 0.8, `${speed}: something comes or goes nearly all the time (${seen} of ${frames})`);
  }
});

test("what the engine's pair costs to draw at the opening, two protocells in water (a ceiling about a fifth above what it costs)", { skip }, () => {
  const { lens } = lensFor();
  lens.player.seek(37);
  lens.update(16, 0, 16);
  // It costs 31 draws and 117,476 triangles at fission 37; its lineage 53 and 133,266 (17 November 2026).
  const pair = lens.cost();
  assert.ok(pair.draws <= 37 && pair.triangles <= 141000, `the pair of protocells: ${JSON.stringify(pair)}`);
  lens.setLevel("lineage");
  lens.update(16, 0, 16);
  const lineage = lens.cost();
  assert.ok(lineage.draws <= 64 && lineage.triangles <= 160000, `the pair's lineage: ${JSON.stringify(lineage)}`);
});
