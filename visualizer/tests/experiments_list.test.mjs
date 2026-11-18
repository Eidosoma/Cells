// The Experiments view's list: only the experiments whose catalogue entry says `listed` stand in it,
// beside the doors to other views the overlay names; a published page carries only the listed
// experiments' runs and the runs its scene names (lib/build_page.mjs, publishedReplays); and the
// page's own overlay and selection hold the replication's entry as data, each source with its own
// revision (17 November 2026).
//
//   node --test tests/experiments_list.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Catalogue } from "../src/replay/catalogue.js";
import { publishedReplays } from "../tools/lib/build_page.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const index = {
  format: "cells.visualizer.replay_index@1",
  experiments: [{ id: "listed-one", listed: true, label: "Listed" }, { id: "old", label: "Old" }, { id: "loop", label: "A loop" }],
  runs: [
    { id: "old--a", experiment: "old", arm: "a" },
    { id: "listed-one--x", experiment: "listed-one", arm: "x" },
    { id: "loop--planarian", experiment: "loop", arm: "planarian" },
  ],
  doors: [{ entry: "gard" }],
};

test("only listed experiments stand in the list, the view opens on the first of them, and the doors are carried", () => {
  const catalogue = new Catalogue(index);
  assert.deepEqual(["listed-one", "old", "loop"].map((id) => catalogue.isListed(id)), [true, false, false]);
  assert.equal(catalogue.firstListed(), "listed-one--x");
  assert.deepEqual(catalogue.sections().map((section) => section.label), ["Listed"]);
  assert.deepEqual(catalogue.doors, [{ entry: "gard" }]);
  // A catalogue that says nothing of listing lists every experiment, as before.
  const plain = new Catalogue({ ...index, experiments: index.experiments.map(({ listed, ...rest }) => rest) });
  assert.ok(["listed-one", "old", "loop"].every((id) => plain.isListed(id)) && plain.firstListed() === "old--a");
});

test("an experiment opens on the run its entry names (opens.run, an arm), where that arm is packaged; else on its first run", () => {
  const two = { ...index, runs: [...index.runs, { id: "listed-one--y", experiment: "listed-one", arm: "y" }] };
  const named = (arm) => new Catalogue({ ...two, experiments: two.experiments.map((item) => (item.id === "listed-one" ? { ...item, opens: { run: arm } } : item)) });
  assert.equal(named("y").firstListed(), "listed-one--y");
  assert.equal(named("y").listRows().find((row) => row.id === "listed-one").first, "listed-one--y", "its row in the list opens the same run");
  assert.equal(named("not-packaged").firstListed(), "listed-one--x");
  assert.equal(new Catalogue(two).firstListed(), "listed-one--x");
});

test("a published page carries the listed experiments' runs and the runs its scene names, nothing else", () => {
  const scene = { species: [{ id: "planarian", cell_type: { loop: "loop--planarian" } }] };
  const published = publishedReplays(index, scene);
  assert.deepEqual(published.runs.map((run) => run.id), ["listed-one--x", "loop--planarian"]);
  assert.deepEqual(published.experiments.map((item) => item.id), ["listed-one", "loop"], "the loop's entry stays, unlisted, for the run the species names");
  assert.equal(publishedReplays({ ...index, experiments: index.experiments.map(({ listed, ...rest }) => rest) }, scene).runs.length, 3, "a catalogue that lists nothing is carried whole");
});

test("the page's overlay lists the replication and GARD's door, each source with its own revision, in words that judge nothing", () => {
  const overlay = readJson("data/replays/overlay.json"), selection = readJson("data/replays/selection.json");
  const listed = Object.entries(overlay.experiments).filter(([, entry]) => entry.listed === true).map(([id]) => id);
  assert.deepEqual(listed, ["gap-junction-linear-network"]);
  assert.deepEqual(overlay.doors, [{ entry: "gard" }]);
  const entry = overlay.experiments["gap-junction-linear-network"];
  // Its runs open on the quantity the driver states beside each (concentration.json), else on the amount; the two forms' units are said, never converted.
  // The tab opens on its part `opens.part` names (the tumour tissue's line, until the user says otherwise).
  assert.deepEqual([entry.development, entry.outcome.judged, entry.summary, entry.opens], [true, false, "summary.json", { run: "figure5-network-g1", record: ["stated.concentration", "amount.mR"], layers: ["junction-coupling"], part: "gap-junction-tissue-line" }]);
  assert.match(entry.units, /the Norton form's runs in mM, the as-written runs in µM .* never converts one to the other\.$/);
  assert.match(entry.outcome.status, /^Development work, not judged/);
  assert.match(entry.plain, /^How strongly must gap junctions couple cells for healthy tissue to turn a tumor back to the healthy state, and how do the tumor's membrane voltage and connexin expression change that\?/);
  assert.match(entry.plain, /J\. Grodstein, J\. Mathews and M\. Levin, "Membrane voltage and connexin expression work together to enhance tumor growth and metastasis in cancer", bioRxiv, 2026, doi:10\.64898\/2026\.09\.02\.748840/);
  // Every source of a listed entry carries its own revision: a commit (a link is built at it) or "pending" (no link until it lands).
  for (const source of [...entry.sources, ...entry.outcome.sources]) assert.ok(typeof source.revision === "string" && (/^[0-9a-f]{7,40}$/.test(source.revision) || source.revision === "pending"), JSON.stringify(source));
  // Never "replicated", "reproduces" or "agrees"; "replication" only as the record's own name for the work (a source's line), never in the page's words.
  assert.doesNotMatch(JSON.stringify(entry), /replicated|reproduc|agree/i);
  assert.doesNotMatch([entry.label, entry.plain, entry.outcome.text, entry.outcome.status].join(" "), /replicat/i);
  // The selection names the run folder folder by folder, and reads its arms from that folder's own index.
  assert.deepEqual(selection["gap-junction-linear-network"].within, ["runs", "dev-06", "viewer"]);
  assert.equal(selection["gap-junction-linear-network"].runs, "index");
});

test("the catalogue keeps its doors when a later call adapts one more experiment with an overlay that names none", async () => {
  const { spawnSync } = await import("node:child_process");
  const { mkdtempSync, rmSync, writeFileSync } = await import("node:fs");
  const os = await import("node:os");
  const scratch = mkdtempSync(path.join(os.tmpdir(), "cells-doors-"));
  try {
    const tool = (name, args) => spawnSync("python3", [path.join(ROOT, "tools", name), ...args], { encoding: "utf8" });
    const fixtures = path.join(scratch, "fixtures"), out = path.join(scratch, "runs");
    assert.equal(tool("make_run_fixture.py", ["--out", fixtures]).status, 0);
    const overlay = JSON.parse(readFileSync(path.join(fixtures, "overlay.json"), "utf8"));
    writeFileSync(path.join(scratch, "with-doors.json"), JSON.stringify({ ...overlay, doors: [{ entry: "gard" }] }));
    let done = tool("adapt_run.py", ["--experiment", "synthetic-world", "--root", path.join(fixtures, "run-world"), "--run", "viewed", "--overlay", path.join(scratch, "with-doors.json"), "--out", out]);
    assert.equal(done.status, 0, done.stderr);
    done = tool("adapt_run.py", ["--experiment", "example-sheet", "--root", path.join(fixtures, "run-example"), "--run", "invented-numbers", "--overlay", path.join(fixtures, "overlay.json"), "--out", out]);
    assert.equal(done.status, 0, done.stderr);
    assert.deepEqual(JSON.parse(readFileSync(path.join(out, "index.json"), "utf8")).doors, [{ entry: "gard" }]);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
});
