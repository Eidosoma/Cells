// The gap-junction example's tissue line (src/replay/tissue_line.js, src/lenses/tissue_line.js; schema/RUN_VIEW.md,
// "A part of an example"): a run folder with no index.json gives its packages that hold a view as its runs, the file the
// overlay names beside each is read as the stated quantity, and the picks an engine check refused are named from their
// REFUSED.json by their arm and their value of the sweep's parameter, and nothing more. The page puts the runs and the
// refused picks in the parameter's order, colours a value on a scale broken at the criterion's own thresholds, draws
// time down the pictures on a logarithmic or an even scale with every saved record a band, keeps the runs under one
// clock only where they share their times, and publishes the part with its listed example. Nothing is worked out of the
// values: no state, no count, no front. The page's own words for it are data, each with its source, and judge nothing.
//
//   node --test tests/tissue_line.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openReplay } from "../src/replay/source.js";
import { lineOf, partsOf, wholeOf, oneClock, Breaks, rangeOf, timeAxis, bands, unitWords, valueWords, TIME_SCALES } from "../src/replay/tissue_line.js";
import { TISSUE_COLOURS, tissueTokens } from "../src/ui/tissue_styles.js";
import { isPart, wholeRunOf } from "../src/ui/tissue_part.js";
import { cellsOf } from "../src/lenses/tissue_line.js";
import { publishedReplays } from "../tools/lib/build_page.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const python = (args, input) => spawnSync("python3", args, { encoding: "utf8", input });

const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-tissue-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const FIXTURES = path.join(scratch, "fixtures"), WORLD = path.join(FIXTURES, "run-world");
assert.equal(python([path.join(ROOT, "tools", "make_run_fixture.py"), "--out", FIXTURES]).status, 0);
const shape = JSON.parse(
  python(["-I", "-"], `import json, sys\nsys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})\nimport adapt_run as a\nfrom pathlib import Path\nfolder = Path(${JSON.stringify(path.join(WORLD, "viewed"))})\nview = json.load(open(folder / "view.json"))\nbases = {b["id"]: b for b in view["time"]["bases"]}\nline = next(i for i in ("observation", "accepted") if i in bases and bases[i].get("files"))\n_, times, count = a.view_rows("viewed", folder, bases[line], bases[line].get("array"))\ncells = [c for c in next(s for s in view["sets"] if s["id"] == "cell")["ids"] if c is not None]\nprint(json.dumps({"times": list(times), "cells": cells}))\n`).stdout
);

/** A run folder as the engine side wrote the tissue line's: no index.json, two packages with a view and a criterion beside each, a refused pick, and the summary's sweep. */
function picksFolder(name, { refused = { arm: "pick-c", status: "refused", d: 5e-14, error: "NumericalError('a made-up refusal on [1.0, 2.0]')", note: "made up" }, sweeps = null, refusedFolder = "pick-c" } = {}) {
  const folder = path.join(scratch, name);
  mkdirSync(folder, { recursive: true });
  for (const [arm, sign] of [["pick-a", -1], ["pick-b", 1]]) {
    cpSync(path.join(WORLD, "viewed"), path.join(folder, arm), { recursive: true });
    writeFileSync(path.join(folder, arm, "criterion.json"), JSON.stringify({
      format: "cells.experiment_criterion@1",
      quantity: { id: "score", label: "A made-up score", unit: "uM" },
      criterion: { threshold: 2, above: "epithelial", lower: { threshold: -2, below: "mesenchymal" }, between: "neither (X)", words: "A made-up criterion.", source: "this test" },
      times_s: shape.times,
      cells: shape.cells,
      values: shape.times.map((_, row) => shape.cells.map((_, k) => sign * (row + k + 3))),
      states: shape.times.map((_, row) => shape.cells.map(() => (sign < 0 ? "M" : "E"))),
    }));
  }
  if (refused) {
    mkdirSync(path.join(folder, refusedFolder), { recursive: true });
    writeFileSync(path.join(folder, refusedFolder, "REFUSED.json"), JSON.stringify(refused));
  }
  const readouts = shape.cells.map((cell) => ({ id: cell, label: `Cell ${cell}`, unit: "uM" }));
  writeFileSync(path.join(folder, "summary.json"), JSON.stringify({
    format: "cells.experiment_summary@1",
    experiment: "made-up",
    sweeps: sweeps || [{ id: "line", label: "A made-up line", parameter: { id: "d", label: "Junction diffusion constant D", unit: "m^2/s" }, readouts, arms: [{ arm: "pick-a", parameter: 0, readouts: {} }, { arm: "pick-b", parameter: 1e-13, readouts: {} }] }],
  }));
  return folder;
}

function adapt(folder, out, entry = {}) {
  const overlay = readJson(path.join(FIXTURES, "overlay.json"));
  overlay.experiments["made-up-line"] = {
    adapter: "standard-history",
    development: true,
    part_of: "synthetic-world",
    summary: "summary.json",
    sidecar: "criterion.json",
    refused_picks: true,
    opens: { record: ["stated.score"] },
    label: "A made-up line",
    tissue: { says: ["Development work, not judged."], ends: { "pick-a": "made-up end a", "pick-b": "made-up end b" }, refused: "Refused by an engine check: no run to show.", sources: [] },
    outcome: { judged: false, status: "Development work, not judged", answer: null, text: "" },
    ...entry,
  };
  writeFileSync(path.join(scratch, `${path.basename(out)}-overlay.json`), JSON.stringify(overlay));
  writeFileSync(path.join(scratch, `${path.basename(out)}-selection.json`), JSON.stringify({ "made-up-line": { evidence_folder: path.basename(folder), runs: "index" } }));
  return python([path.join(ROOT, "tools", "adapt_run.py"), "--experiment", "made-up-line", "--root", folder, "--overlay", path.join(scratch, `${path.basename(out)}-overlay.json`), "--selection", path.join(scratch, `${path.basename(out)}-selection.json`), "--out", out]);
}

test("a run folder with no index gives its packages with a view, reads the stated file the overlay names, and names each refused pick by its arm and value alone", () => {
  const folder = picksFolder("picks"), out = path.join(scratch, "out");
  const done = adapt(folder, out);
  assert.equal(done.status, 0, done.stderr);
  const index = readJson(path.join(out, "index.json"));
  assert.deepEqual(index.runs.map((run) => run.arm), ["pick-a", "pick-b"], "the packages that hold a view, by name; the refused folder is no run");
  const entry = index.experiments.find((item) => item.id === "made-up-line");
  assert.deepEqual(entry.refused_picks, [{ arm: "pick-c", sweep: "line", parameter: 5e-14, file: "REFUSED.json" }]);
  assert.doesNotMatch(JSON.stringify(index), /NumericalError|made-up refusal|\[1\.0, 2\.0\]/, "nothing of the refusal but its arm and its value is carried");
  assert.equal(entry.sidecar, undefined, "the overlay's name for the file beside each package is the adapter's, not the catalogue's");
  assert.equal(entry.part_of, "synthetic-world");
  const run = openReplay(readJson(path.join(out, `${index.runs[0].id}.json`)));
  const record = run.records.get("stated.score");
  assert.ok(record && record.marks.length === 2, "the criterion is read beside each package, with its two thresholds");
  assert.equal(run.records.get("stated.score.state").text(0, 0), "M", "the state is the driver's, carried as stated");
  assert.equal(record.at(0, 0), -3);
});

test("a refused pick that does not name itself, or a summary of several sweeps, is refused with the reason", () => {
  const wrong = picksFolder("picks-wrong", { refused: { arm: "another", status: "refused", d: 1e-14 } });
  let done = adapt(wrong, path.join(scratch, "out-wrong"));
  assert.notEqual(done.status, 0);
  assert.match(done.stderr, /does not name its own arm as refused/);
  const noValue = picksFolder("picks-novalue", { refused: { arm: "pick-c", status: "refused" } });
  done = adapt(noValue, path.join(scratch, "out-novalue"));
  assert.notEqual(done.status, 0);
  assert.match(done.stderr, /with its value of d/);
  const sweep = (id) => ({ id, label: id, parameter: { id: "d", label: "D", unit: "m^2/s" }, readouts: [{ id: shape.cells[0], label: "a", unit: "uM" }], arms: [{ arm: "pick-a", parameter: 0, readouts: {} }, { arm: "pick-b", parameter: 1, readouts: {} }] });
  const two = picksFolder("picks-two", { sweeps: [sweep("one"), sweep("two")] });
  done = adapt(two, path.join(scratch, "out-two"));
  assert.notEqual(done.status, 0);
  assert.match(done.stderr, /named by its sweep's parameter, and the summary states 2 sweeps/);
  // Without refused_picks in the overlay, nothing is read of the refused folder.
  const quiet = adapt(picksFolder("picks-quiet"), path.join(scratch, "out-quiet"), { refused_picks: undefined });
  assert.equal(quiet.status, 0, quiet.stderr);
  assert.equal(readJson(path.join(scratch, "out-quiet", "index.json")).experiments.find((item) => item.id === "made-up-line").refused_picks, undefined);
});

// ---------------------------------------------------------------- the line as the page reads it

const catalogue = {
  experiments: [
    { id: "whole", listed: true, label: "The example" },
    {
      id: "line",
      part_of: "whole",
      label: "The tissue line: 25 cells",
      short: "The tissue line",
      tissue: { says: ["Development work, not judged."], tumor: { cells: ["c0", "c1"], label: "Tumor" }, ends: { "d-0": "holds", "d-big": "normalised" }, ends_label: "End states", refused: "Refused by an engine check: no run to show.", sources: [{ path: "docs/X.md", where: "s7", revision: "e2388e262be41cc75bd35227761ae78b3bc5e46a" }] },
      sweeps: [{ id: "s", parameter: { id: "d", label: "Junction diffusion constant D of miR200", unit: "m^2/s" }, arms: [{ arm: "d-0", run: "line--d-0", parameter: 0 }, { arm: "d-big", run: "line--d-big", parameter: 1e-13 }, { arm: "d-none", run: null, parameter: 3e-14 }] }],
      refused_picks: [{ arm: "d-mid", sweep: "s", parameter: 7.18e-15, file: "REFUSED.json" }, { arm: "d-high", sweep: "s", parameter: 1e-14, file: "REFUSED.json" }, { arm: "d-elsewhere", sweep: "other", parameter: 2e-15, file: "REFUSED.json" }],
    },
    { id: "loose", part_of: "whole", label: "No words, no part" },
  ],
  runs: [
    { id: "whole--a", experiment: "whole", arm: "a" },
    { id: "line--d-big", experiment: "line", arm: "d-big" },
    { id: "line--d-0", experiment: "line", arm: "d-0" },
    { id: "loose--x", experiment: "loose", arm: "x" },
  ],
};

test("the line's slots stand in the order of the parameter, the refused picks among them, each named in its own number and unit", () => {
  const line = lineOf(catalogue, "line");
  assert.deepEqual(line.slots.map((slot) => [slot.kind, slot.arm, slot.label]), [
    ["run", "d-0", "D = 0 m²/s"],
    ["refused", "d-mid", "D = 7.18e-15 m²/s"],
    ["refused", "d-high", "D = 1e-14 m²/s"],
    ["run", "d-big", "D = 1e-13 m²/s"],
  ], "an arm with no packaged run is no slot, and a refused pick of another sweep is not this line's");
  assert.deepEqual(line.runs.map((slot) => [slot.id, slot.end]), [["line--d-0", "holds"], ["line--d-big", "normalised"]]);
  assert.equal(line.refusedWords, "Refused by an engine check: no run to show.");
  assert.equal(lineOf(catalogue, "whole"), null, "an entry with no words for a line is none");
  assert.equal(unitWords("m^2/s"), "m²/s");
  assert.equal(unitWords("uM"), "µM");
  assert.deepEqual([valueWords(0), valueWords(6.25e-15), valueWords(1e-13)], ["0", "6.25e-15", "1e-13"], "the record's own number, never rounded");
});

test("a part belongs to its example: its door, the address's word for it, the list's pressed row, and the published page", () => {
  assert.deepEqual(partsOf(catalogue, "whole").map((item) => item.id), ["line"], "an entry that names its example but has no words for a line is not offered");
  assert.equal(wholeOf(catalogue, "line").id, "whole");
  assert.deepEqual([isPart(catalogue, "line"), isPart(catalogue, "loose"), isPart(catalogue, "whole"), isPart(catalogue, null)], [true, false, false, false]);
  assert.equal(wholeRunOf(catalogue, "line"), "whole--a");
  const published = publishedReplays({ format: "cells.visualizer.replay_index@1", ...catalogue }, {});
  assert.deepEqual(published.runs.map((run) => run.id), ["whole--a", "line--d-big", "line--d-0", "loose--x"], "the runs of a part of a listed example are published with it");
  const alone = publishedReplays({ format: "cells.visualizer.replay_index@1", experiments: [{ id: "whole", label: "w" }, { id: "line", part_of: "whole", label: "l" }, { id: "other", listed: true, label: "o" }], runs: [{ id: "line--a", experiment: "line" }, { id: "other--a", experiment: "other" }] }, {});
  assert.deepEqual(alone.runs.map((run) => run.id), ["other--a"], "a part of an example that is not listed stays out");
});

test("a value's colour sits on a scale broken at the criterion's thresholds, light to strong in each arm, and grey between", () => {
  const marks = [{ value: -2, label: "mesenchymal below, neither (X) between" }, { value: 2, label: "epithelial above" }];
  const lum = ([r, g, b]) => 0.2126 * r ** 2.2 + 0.7152 * g ** 2.2 + 0.0722 * b ** 2.2;
  for (const theme of ["light", "dark"]) {
    const scale = new Breaks(marks, -60, 80, TISSUE_COLOURS[theme]);
    assert.deepEqual([-60, -2.01, -2, 0, 2, 2.01, 80].map((value) => scale.side(value)), ["below", "below", "between", "between", "between", "above", "above"]);
    const grey = scale.colour(0);
    assert.notDeepEqual(scale.colour(-2.01), grey, "just past a threshold is not between");
    assert.notDeepEqual(scale.colour(2.01), grey);
    assert.deepEqual(scale.colour(-1.99), grey);
    // Each arm runs one way in lightness: from its threshold to the scale's end, darker on a light page, lighter on a dark one.
    const below = [-2.01, -20, -40, -60].map((value) => lum(scale.colour(value))), above = [2.01, 30, 55, 80].map((value) => lum(scale.colour(value)));
    for (const arm of [below, above]) for (let k = 1; k < arm.length; k++) assert.ok(theme === "light" ? arm[k] < arm[k - 1] : arm[k] > arm[k - 1], `${theme}: ${arm}`);
    assert.deepEqual(scale.colour(-500), scale.colour(-60), "beyond the end, the end's colour");
    assert.match(scale.css(), /^linear-gradient\(to right, /);
  }
  // One threshold: the two hues meet at it.
  const one = new Breaks([{ value: 0, label: "above and below" }], -1, 1, TISSUE_COLOURS.light);
  assert.deepEqual([one.side(-0.1), one.side(0), one.side(0.1)], ["below", "above", "above"]);
  assert.throws(() => new Breaks([], -1, 1, TISSUE_COLOURS.light));
  // The scale's ends are the records' stated ranges, widened to round numbers.
  assert.deepEqual(rangeOf([{ range: [-59.8, 78.04] }, { range: [-59.3, 78.0] }]), { low: -60, high: 80 });
  // The tokens give the same colours to the page.
  for (const hex of [...TISSUE_COLOURS.light.below, ...TISSUE_COLOURS.dark.above]) assert.ok(tissueTokens.includes(hex));
});

test("time runs down a picture on a logarithmic scale or an even one, every saved record a band from its time to the next", () => {
  const times = Array.from({ length: 201 }, (_, k) => k * 100);
  const log = timeAxis(0, 20000, { step: 100 });
  assert.equal(log.scale, "log");
  assert.deepEqual([log.at(0), log.at(20000)], [0, 1]);
  assert.ok(Math.abs(log.at(100) - Math.log1p(1) / Math.log1p(200)) < 1e-12, "a time t stands at log(1 + t / step)");
  for (let k = 1; k < times.length; k++) assert.ok(log.at(times[k]) > log.at(times[k - 1]));
  for (let k = 1; k < log.ticks.length; k++) assert.ok(log.ticks[k].at - log.ticks[k - 1].at >= 0.075 - 1e-12, "ticks keep their distance");
  assert.deepEqual([log.ticks[0].words, log.ticks.at(-1).words], ["0", "5 h 33 min"]);
  assert.match(log.words, /logarithmic scale, the picture's choice/);
  const even = timeAxis(0, 20000, { scale: "even" });
  assert.equal(even.at(5000), 0.25);
  assert.deepEqual(even.ticks.map((tick) => tick.words), ["0", "1 h", "2 h", "3 h", "4 h", "5 h", "5 h 33 min"]);
  assert.deepEqual(TIME_SCALES.map(([id]) => id), ["log", "even"], "the picture opens on the logarithmic scale");
  const drawn = bands(times, log);
  assert.equal(drawn.length, times.length, "every saved record is drawn");
  for (let k = 0; k < times.length - 1; k++) assert.deepEqual([drawn[k].k, drawn[k].from, drawn[k].to], [k, log.at(times[k]), log.at(times[k + 1])]);
  assert.ok(drawn.at(-1).from === 1 && drawn.at(-1).to >= 1.005, "the last record's band stands past the run's end, long enough to be seen");
});

test("runs are shown under one clock only where they share their saved times", () => {
  const run = (id, t) => ({ id, t: Float32Array.from(t), count: t.length });
  assert.equal(oneClock([run("a", [0, 100, 200]), run("b", [0, 100, 200])]).id, "a");
  assert.throws(() => oneClock([run("a", [0, 100, 200]), run("b", [0, 100])]), /do not share their times/);
  assert.throws(() => oneClock([run("a", [0, 100, 200]), run("b", [0, 100, 300])]), /record 2 is at 200 s in a and 300 s in b/);
  assert.throws(() => oneClock([]));
});

test("the cells stand where the run's view prescribes them along the line", () => {
  const run = { sets: new Map([["cell", { ids: ["c0", "c1", "c2"], geometry: { kind: "spheres", centres: [[0, 0], [10, 0], [20, 0]], radius: [5, 5, 5] } }]]) };
  const cells = cellsOf(run);
  assert.deepEqual([cells.x, cells.width, cells.columns], [[5, 15, 25], 30, [0, 1, 2]]);
  assert.deepEqual([cells.columnAt(0), cells.columnAt(14.9), cells.columnAt(29.9), cells.columnAt(31)], [0, 1, 2, null]);
});

test("the page's overlay and selection hold the tissue line as a part of the example, in words that judge nothing, each with its source", () => {
  const overlay = readJson(path.join(ROOT, "data", "replays", "overlay.json")), selection = readJson(path.join(ROOT, "data", "replays", "selection.json"));
  const entry = overlay.experiments["gap-junction-tissue-line"];
  assert.equal(entry.listed, undefined, "not a third example in the list: a part of the second");
  assert.equal(entry.part_of, "gap-junction-linear-network");
  assert.deepEqual([entry.summary, entry.sidecar, entry.refused_picks, entry.opens.record], ["summary.json", "criterion.json", true, ["stated.mir200_minus_zeb_mrna"]]);
  // The lead's words for the rerun (17 November 2026, night): the arms, the threshold with its antecedent, and what BITSEY is.
  assert.deepEqual(entry.tissue.says, [
    "Development work, not judged.",
    "Three runs, fixed before they ran, at half, once and twice the threshold the search reported (x2/2 below, x2 near, 2 x2 above); none was refused.",
    "Its threshold, from the search rerun after an engine fix (FR-19): 7.1777e-15 m²/s. The search was a comparison with BITSEY's log saved at b2cb370, written by an earlier revision of its code: Cells' threshold is 0.99968 of the logged value, inside the band fixed before the run; development, not judged.",
    "BITSEY is the preprint's authors' public code and logs: it was not run, and its code is never copied into Cells.",
  ]);
  assert.deepEqual(entry.tissue.ends, { "neither-d3.58887e-15": "6 M, 19 E: the tumor holds", "neither-d7.17773e-15": "25 E: normalized", "neither-d1.43555e-14": "25 E: normalized" }, "the end states are the note's table (section 7.5), for the three arms");
  for (const source of [...entry.sources, ...entry.tissue.sources, ...entry.outcome.sources]) assert.match(source.revision, /^[0-9a-f]{40}$/);
  assert.ok(entry.tissue.sources.some((source) => source.path === "docs/GAP_JUNCTION_CANCER_REPLICATION.md" && source.revision.startsWith("17b7f9f8")) && entry.tissue.sources.some((source) => source.path === "PROGRESS.md" && source.revision.startsWith("295b3333")));
  // The page's own words (a source's path is the record's own name for its file, and is not checked here).
  const words = JSON.stringify([entry.label, entry.short, entry.plain, { ...entry.tissue, says: entry.tissue.says.filter((_, index) => index !== 3), sources: null }, entry.outcome.status, entry.outcome.text]);
  assert.doesNotMatch(words, /replicat|reproduc|agree|\bmatch|modelled|qualified|Grodstein|preprint|7\.18/i, "no comparison with the preprint's or its authors' numbers but the one sentence, and no word that judges");
  // The sentence that says whose code BITSEY is names the preprint for that alone.
  assert.doesNotMatch(entry.tissue.says[3], /replicat|reproduc|agree|\bmatch|modelled|qualified|Grodstein|7\.18|number|value|threshold/i, "what BITSEY is, with no comparison in it");
  // The logged value is spoken of in one sentence of the card alone, and BITSEY is said once for what it is.
  const logged = [entry.label, entry.short, entry.plain, ...entry.tissue.says, entry.outcome.text].filter((line) => /BITSEY|logged/.test(line));
  assert.deepEqual(logged, [entry.tissue.says[2], entry.tissue.says[3]]);
  assert.doesNotMatch(words, /the user|“|"include/i, "no sentence of the user's in a data file");
  assert.deepEqual(selection["gap-junction-tissue-line"].within, ["runs", "picks-02", "viewer"]);
  assert.equal(selection["gap-junction-tissue-line"].runs, "index");
});
