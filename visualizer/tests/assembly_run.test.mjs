// The assembly view's run (schema/ASSEMBLY_RUN.md): the contract held on the example run, the
// example held to its tool, and the reader's rules (the run's H read, the analysis's marks read,
// the clock's phases). No browser.

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";
import { ASSEMBLY_FORMAT, AssemblySet, PART, problemsOf, similarity, sizeOf } from "../src/lenses/assembly_run.js";

const FILE = path.join(ROOT, "data", "origin", "example-run.json");
const text = readFileSync(FILE, "utf8");
const raw = JSON.parse(text);
const copy = () => JSON.parse(text);

test("the example holds to its contract, and is marked as an example that names no engine model", () => {
  assert.equal(raw.format, ASSEMBLY_FORMAT);
  assert.deepEqual(problemsOf(raw), []);
  assert.equal(raw.example.says, "Invented numbers · no run of Cells' engine");
  assert.match(raw.example.says, /^Invented numbers · /, "the replays' words for invented numbers, where they fit");
  for (const run of raw.runs) {
    assert.deepEqual(run.engine_models, [], `${run.id}: an example names no engine model`);
    assert.equal(run.revision, null);
  }
  assert.ok(Buffer.byteLength(text) < 400_000, `the example stays small: ${Buffer.byteLength(text)} bytes`);
  for (const source of Object.values(raw.sources)) assert.equal(source.class, "permissive", source.text);
});

test("the example is the tool's: run again, the tool writes the same bytes", () => {
  const run = spawnSync(process.execPath, [path.join(ROOT, "tools", "make_assembly_example.mjs"), "--out", "-"], { encoding: "utf8", maxBuffer: 1 << 24 });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(run.stdout, text, "the committed example is the tool's output; run the tool again after changing it");
});

test("each fission: the second daughter is the parent less the first; the run's own H is the cosine of the counts", () => {
  const set = new AssemblySet(raw);
  for (const run of set.runs) {
    assert.equal(run.fissionCount, 120);
    for (let k = 1; k <= run.fissionCount; k++) {
      const parent = run.parent(k);
      assert.equal(sizeOf(parent), 80, `${run.id} ${k}: a parent splits at 80`);
      assert.equal(sizeOf(run.carried(k)) + sizeOf(run.other(k)), 80);
      const own = run.similarityAt(k);
      // The view's own H (worked out only where the run did not save it) agrees with the run's at every fission.
      assert.ok(Math.abs(similarity(parent, run.carried(k)) - own.carried) < 1e-6, `${run.id} ${k}`);
      assert.ok(Math.abs(similarity(parent, run.other(k)) - own.other) < 1e-6, `${run.id} ${k}`);
    }
  }
});

test("the trace takes every growth from its start to the next parent, one molecule at a time", () => {
  const set = new AssemblySet(raw);
  for (const run of set.runs) {
    assert.ok(run.hasTrace);
    for (let g = 0; g < run.fissionCount; g++) {
      const end = run.during(g, run.growthLength(g));
      assert.deepEqual([...end], [...run.parent(g + 1)], `${run.id}: growth ${g} reaches fission ${g + 1}'s parent`);
    }
  }
  // A trace that misses a molecule is refused.
  const broken = copy();
  const bytes = Buffer.from(broken.runs[0].trace.events, "base64");
  bytes[5] = (256 - bytes[5]) & 255; // one join read as a leave
  broken.runs[0].trace.events = bytes.toString("base64");
  assert.ok(problemsOf(broken).some((line) => /does not reach/.test(line)), problemsOf(broken).join("; "));
});

test("the clock: fission k happens at time k, its split is drawn around it, and the growth fills the rest", () => {
  const run = new AssemblySet(raw).runs[0];
  assert.deepEqual(run.phaseAt(0), { phase: "grow", g: 0, e: 0, progress: 0, k: 0 });
  const split = run.phaseAt(37);
  assert.equal(split.phase, "split");
  assert.equal(split.k, 37);
  assert.ok(Math.abs(split.part - 0.5) < 1e-9, "a step lands in the middle of a split");
  assert.deepEqual([run.phaseAt(37 - PART).phase, run.phaseAt(37 + PART).phase], ["split", "split"]);
  const growing = run.phaseAt(37.5);
  assert.equal(growing.phase, "grow");
  assert.equal(growing.g, 37);
  assert.ok(growing.e > 0 && growing.e < run.growthLength(37));
  assert.equal(run.phaseAt(1e9).phase, "split", "the clock ends with the last split complete");
  assert.equal(run.phaseAt(1e9).part, 1);
  // Every molecule event has its moment on the clock, in order.
  let last = -1;
  for (let e = 0; e < run.growthLength(12); e++) {
    const t = run.timeOf(12, e);
    assert.ok(t > last);
    assert.equal(run.phaseAt(t).e, e, `the moment of growth 12's event ${e} shows that many events done`);
    last = t;
  }
});

test("the marks of inheritance are the analysis's, read as written, never worked out from H", () => {
  const flipped = copy();
  const marks = flipped.runs[0].analysis.inheritance.marks;
  const k = marks.indexOf(true) + 1;
  marks[k - 1] = false; // a mark against its own H: the view must still draw it as marked
  const run = new AssemblySet(flipped).runs[0];
  assert.ok(run.similarityAt(k).carried > 0.9);
  assert.equal(run.inherited(k), false);
  // Where the run states no analysis, no threshold and no mark.
  const bare = copy();
  delete bare.runs[0].analysis;
  const none = new AssemblySet(bare).runs[0];
  assert.equal(none.threshold, null);
  assert.equal(none.inherited(1), null);
});

test("a composome is named only where the run's analysis names one, with its method", () => {
  const run = new AssemblySet(raw).runs[0];
  assert.equal(run.composomes, null);
  assert.equal(run.composomeAt(40), null);
  const named = copy();
  named.runs[0].analysis.composomes = { method: "a test's own: no clustering", names: [{ id: "c1", label: "C1", fissions: [40, 41, 42] }] };
  const withOne = new AssemblySet(named).runs[0];
  assert.equal(withOne.composomeAt(41).id, "c1");
  const nameless = copy();
  nameless.runs[0].analysis.composomes = { names: [{ id: "c1", fissions: [1] }] };
  assert.ok(problemsOf(nameless).some((line) => /only with the method/.test(line)));
});

test("the reader refuses a file that breaks the contract", () => {
  const broken = copy();
  broken.runs[0].fissions[3].k = 9;
  broken.runs[0].fissions[4].first = [[0, 99]];
  broken.runs[1].engine_models = ["cells.something@1"];
  broken.time.base = "second";
  const problems = problemsOf(broken);
  for (const pattern of [/numbered 1, 2/, /more of a type than its parent/, /names no engine model/, /must count fissions/]) assert.ok(problems.some((line) => pattern.test(line)), `${pattern}: ${problems.join("; ")}`);
  assert.throws(() => new AssemblySet(broken), /not valid/);
  assert.deepEqual(problemsOf({ format: "x" }), [`the file is not ${ASSEMBLY_FORMAT}`]);
});

test("words that must not stand: no engine record name outside the contract's table, and no model named in the code", () => {
  const mine = [
    "schema/ASSEMBLY_RUN.md", "tools/make_assembly_example.mjs", "data/origin/README.md", "data/origin/example-run.json",
    ...readdirSync(path.join(ROOT, "src", "lenses")).filter((name) => /^(assembly|lineage|lipid|composition|similarity|catalysis)/.test(name)).map((name) => `src/lenses/${name}`),
    "src/standalone/lineage.js",
    ...readdirSync(path.join(ROOT, "src", "ui")).filter((name) => name.startsWith("origin")).map((name) => `src/ui/${name}`),
  ].filter((file) => statSync(path.join(ROOT, file), { throwIfNoEntry: false }));
  const records = ["assembly_count", "joined_total", "left_total", "discarded_total", "boundary_similarity", "fission_similarity", "fission_split", "fission_followed", "fission_time", "exchange_heat_kT", "fission_work_kT"];
  for (const file of mine) {
    const body = readFileSync(path.join(ROOT, file), "utf8");
    if (file !== "schema/ASSEMBLY_RUN.md") for (const name of records) assert.ok(!body.includes(name), `${file} names the engine's proposed record ${name}`);
    if (file.startsWith("src/")) assert.ok(!/\bGARD\b/.test(body), `${file}: the view's code names no model; GARD is in the data`);
  }
  const contract = readFileSync(path.join(ROOT, "schema", "ASSEMBLY_RUN.md"), "utf8");
  const heading = "## The adapter, from the engine's run format";
  const table = contract.slice(contract.indexOf(heading));
  for (const name of records.filter((item) => contract.includes(item))) assert.ok(table.includes(name) && contract.indexOf(name) >= contract.indexOf(heading), `${name} stands only in the contract's table`);
});

test("the vesicle replay keeps the intact threshold sample and released state at one instant and both children at a split", async () => {
  const { VesicleRun } = await import("../src/lenses/vesicle_run.js");
  const model = JSON.parse(readFileSync(path.join(ROOT, "data/models/origin-vesicles.json"), "utf8"));
  const runs = model.runs.map((r) => {
    const bytes = readFileSync(path.join(ROOT, r.file));
    assert.ok(bytes.length <= 1_000_000);
    return new VesicleRun(JSON.parse(bytes));
  });
  const lysis = runs.find((r) => r.file.releases.some((e) => e.cause === "threshold"));
  const growth = runs.find((r) => r.file.shears.length);
  const t = lysis.end,
    row = lysis.rows.findLastIndex((r) => r.t === t && r.slots[0].membrane_footprint_quanta > 0),
    intact = lysis.at(t, 0, row);
  assert.equal(lysis.at(t).sample.lumen_volume_L, 0);
  assert.ok(intact.sample.lumen_volume_L > 0);
  assert.equal(intact.sample.tension_N_per_m, lysis.file.releases[0].tension_N_per_m);
  assert.equal(lysis.file.trace.time.length, 49);
  assert.equal(growth.file.trace.time.length, 922);
  assert.deepEqual(
    growth.events.map((e) => e.outcome),
    ["split", "split", "refused_floor", "split", "refused_floor"],
  );
  for (const e of growth.file.shears.filter((e) => e.outcome === "split")) {
    assert.deepEqual(e.daughters[e.followed].counts, growth.at(e.time).sample.counts);
    for (const p of [...growth.membrane, ...growth.lumen])
      assert.equal(
        e.daughters.reduce((n, d) => n + d.counts[p.index], 0),
        e.parent_counts[p.index],
      );
  }
});
