// A sweep's chart: the adapter writes an experiment's sweeps into the catalogue from its summary
// and from nothing else, and the chart places the summary's numbers without computing anything
// from them (src/replay/sweep.js; schema/RUN_VIEW.md, "A sweep's chart"). The summary is a
// made-up one, tracked beside the engine views (tests/engine-views/sweep-made-up/summary.json),
// over the synthetic world's runs that the run-fixture tool writes.
//
//   node --test tests/sweep.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { logScaleFor, niceRange, sweepsOf, chartOf, tableOf, armWords } from "../src/replay/sweep.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SUMMARY = path.join(ROOT, "tests", "engine-views", "sweep-made-up", "summary.json");
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const python = (tool, args) => spawnSync("python3", [path.join(ROOT, "tools", tool), ...args], { encoding: "utf8" });

const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-sweep-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const FIXTURES = path.join(scratch, "fixtures");
assert.equal(python("make_run_fixture.py", ["--out", FIXTURES]).status, 0);
/** The adapter on the synthetic world with a summary beside its runs; `edit` changes the summary first. Returns { status, stderr, index }. */
const adapt = (name, edit = (summary) => summary) => {
  const out = path.join(scratch, name), overlayPath = path.join(scratch, `${name}-overlay.json`);
  const overlay = readJson(path.join(FIXTURES, "overlay.json"));
  overlay.experiments["synthetic-world"].summary = "summary.json";
  writeFileSync(overlayPath, JSON.stringify(overlay));
  writeFileSync(path.join(FIXTURES, "run-world", "summary.json"), JSON.stringify(edit(readJson(SUMMARY))));
  const done = python("adapt_run.py", ["--experiment", "synthetic-world", "--root", path.join(FIXTURES, "run-world"), "--run", "secreting", "--run", "viewed", "--run", "retiring", "--overlay", overlayPath, "--out", out]);
  return { status: done.status, stderr: done.stderr, index: done.status === 0 ? readJson(path.join(out, "index.json")) : null };
};

test("the adapter writes an experiment's sweeps from its summary, each arm joined to its run, and nothing computed", () => {
  const { status, stderr, index } = adapt("good");
  assert.equal(status, 0, stderr);
  const experiment = index.experiments.find((item) => item.id === "synthetic-world");
  assert.equal(experiment.summary, undefined, "the summary's name is the adapter's to read, not the catalogue's");
  const [sweep] = experiment.sweeps;
  const summary = readJson(SUMMARY).sweeps[0];
  assert.deepEqual([sweep.id, sweep.label, sweep.parameter, sweep.readouts, sweep.reference], [summary.id, summary.label, summary.parameter, summary.readouts, summary.reference]);
  const runs = Object.fromEntries(index.runs.map((row) => [row.arm, row.id]));
  assert.deepEqual(sweep.arms.map((arm) => [arm.arm, arm.run]), [["secreting", runs.secreting], ["viewed", runs.viewed], ["retiring", runs.retiring], ["not-run", null]]);
  // The numbers are the summary's, as it states them.
  sweep.arms.forEach((arm, k) => {
    assert.equal(arm.parameter, summary.arms[k].parameter);
    assert.deepEqual(arm.readouts, summary.arms[k].readouts);
    assert.deepEqual(arm.reference, summary.arms[k].reference);
  });
});

test("a summary that does not state what the chart reads is refused, with the reason", () => {
  const cases = [
    ["no unit", (summary) => (delete summary.sweeps[0].readouts[0].unit, summary), /needs an id, a label and a unit/],
    ["a readout it does not list", (summary) => ((summary.sweeps[0].arms[0].readouts.third = 1), summary), /readout the sweep does not list/],
    ["a reference without its words", (summary) => (delete summary.sweeps[0].reference, summary), /reference value the sweep does not name/],
    ["one arm", (summary) => ((summary.sweeps[0].arms = summary.sweeps[0].arms.slice(0, 1)), summary), /two arms or more/],
    ["not a summary", (summary) => ({ ...summary, format: "something else" }), /is not an experiment summary/],
  ];
  for (const [name, edit, said] of cases) {
    const done = adapt(name.replace(/ /g, "-"), edit);
    assert.notEqual(done.status, 0, name);
    assert.match(done.stderr, said, name);
  }
});

test("the chart places the summary's numbers: a log scale where the values ask for one, every arm a point, the shown arm marked", () => {
  assert.deepEqual([logScaleFor([0.5, 2, 8, 32]), logScaleFor([1, 2, 5]), logScaleFor([0, 10, 100]), logScaleFor([3])], [true, false, false, false]);
  assert.deepEqual(niceRange([6.2, 8.8]), { low: 6, high: 9, ticks: [6, 7, 8, 9] });
  const experiment = { sweeps: readJson(SUMMARY).sweeps.map((sweep) => ({ ...sweep, arms: sweep.arms.map((arm) => ({ ...arm, run: arm.arm === "not-run" ? null : `synthetic-world--${arm.arm}` })) })) };
  const [sweep] = sweepsOf(experiment, ["synthetic-world--secreting", "synthetic-world--viewed", "synthetic-world--retiring"], "synthetic-world--viewed");
  assert.equal(sweep.log, true);
  assert.deepEqual(sweep.arms.map((arm) => [arm.arm, Boolean(arm.run), arm.active]), [["secreting", true, false], ["viewed", true, true], ["retiring", true, false], ["not-run", false, false]]);
  const chart = chartOf(sweep, { width: 240, height: 156 });
  assert.equal(chart.points.length, 8, "two readouts for each of four arms");
  assert.equal(chart.references.length, 6, "the reference where the summary states it");
  // Along a log scale each factor of four is the same step.
  const xs = sweep.arms.map((arm) => chart.x(arm.parameter));
  assert.ok(Math.abs(xs[1] - xs[0] - (xs[2] - xs[1])) < 1e-9 && Math.abs(xs[3] - xs[2] - (xs[2] - xs[1])) < 1e-9);
  // Up the chart, a larger readout stands higher, and every point lies inside the plot.
  const [first, second] = [chart.points.find((point) => point.arm === 0 && point.readout === "first"), chart.points.find((point) => point.arm === 0 && point.readout === "second")];
  assert.ok(second.y < first.y);
  assert.ok(chart.points.every((point) => point.x >= chart.inner.left && point.x <= chart.inner.right && point.y >= chart.inner.top && point.y <= chart.inner.bottom));
  // The table gives the same numbers, in the parameter's order, with the reference in the summary's words.
  const table = tableOf(sweep);
  assert.deepEqual(table.head, ["Coupling (made-up unit)", "Amount in the first cell (mM)", "Amount in the second cell (mM)", "Amount in the first cell, the made-up reference (mM)", "Amount in the second cell, the made-up reference (mM)"]);
  assert.deepEqual(table.rows.map((row) => [row.arm, row.cells]), [["secreting", ["0.5", "6.2", "8.8", "6.25", "8.75"]], ["viewed", ["2", "7.1", "7.9", "7.14", "7.86"]], ["retiring", ["8", "7.4", "7.6", "", ""]], ["not-run", ["32", "7.5", "7.5", "7.5", "7.5"]]]);
  assert.equal(armWords(sweep, sweep.arms[1]), "viewed: Coupling 2 made-up unit; Amount in the first cell 7.1 mM; Amount in the second cell 7.9 mM; the made-up reference: 7.14 mM; the made-up reference: 7.86 mM; shown now");
  assert.match(armWords(sweep, sweep.arms[3]), /no run of it is packaged here$/);
  // Words that would judge are not the chart's.
  assert.doesNotMatch(JSON.stringify([table, sweep.arms.map((arm) => armWords(sweep, arm))]), /agree|replicat|reproduc|match/i);
});
