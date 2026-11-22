// tools/adapt_assembly_run.py: from the engine's run format (cells.assembly_lineages.run@1) to the
// assembly view's own (cells.visualizer.assembly_run@1). Held on a test's own made-up run folder
// (tests/fixtures/assembly-engine-run/make.py) everywhere, and on the engine's two runs of one world
// where their folder is at hand (ASSEMBLY_RUNS names it; skipped where it is not).

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { problemsOf, AssemblySet, decodeEvents } from "../src/lenses/assembly_run.js";
import { mergeRunFiles } from "../src/lenses/lineage_entry.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "adapt_assembly_run.py");
const MAKE = path.join(ROOT, "tests", "fixtures", "assembly-engine-run", "make.py");
// The engine's provisional set of 17 November 2026 (read only), or the folder ASSEMBLY_RUNS names: "<evidence root>::<run folder>,<run folder>".
const REAL = process.env.ASSEMBLY_RUNS || "/mnt/workspaces/Cells::gard-g1-part2-20261117/probes-6af93a51/probes/lineage,gard-g1-part2-20261117/probes-6af93a51/probes/lineage_single_event";
const [REAL_ROOT, REAL_LIST] = REAL.split("::");
const REAL_RUNS = (REAL_LIST || "").split(",").filter(Boolean);
const realHere = REAL_RUNS.length > 0 && REAL_RUNS.every((run) => existsSync(path.join(REAL_ROOT, run, "run.json")));

const py = (args) => spawnSync("python3", ["-I", ...args], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
const adapt = (root, out, runs) => py([TOOL, "--evidence", root, "--out", out, "--standing", "development", "--standing-from", "a test", ...runs]);
const readAll = (dir) => readdirSync(dir).sort().map((name) => ({ name, text: readFileSync(path.join(dir, name), "utf8") }));

function scratch() {
  const dir = mkdtempSync(path.join(tmpdir(), "adapt-assembly-"));
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

test("a made-up run folder of the engine's format becomes a file the view holds to its contract, its trace reaching every parent", () => {
  const { dir, done } = scratch();
  try {
    for (const form of ["pair-consistent", "single-event"]) assert.equal(py([MAKE, path.join(dir, "runs", form), "--form", form]).status, 0);
    const result = adapt(dir, path.join(dir, "out"), ["runs/pair-consistent", "runs/single-event"]);
    assert.equal(result.status, 0, result.stderr);
    const files = readAll(path.join(dir, "out")).map(({ text }) => JSON.parse(text));
    assert.equal(files.length, 2);
    for (const file of files) {
      assert.deepEqual(problemsOf(file), []);
      assert.equal(file.example, undefined, "a run of the engine's format is never an example");
      assert.equal(file.development.says, "Development run of the engine, not judged");
      assert.equal(file.development.from, "a test");
      const run = file.runs[0];
      const stated = JSON.parse(readFileSync(path.join(dir, "runs", run.law.form, "run.json"), "utf8"));
      // What the run names of itself, read from it.
      assert.equal(run.revision, stated.source.revision);
      assert.deepEqual(run.engine_models, [stated.engine_models.model, ...stated.engine_models.laws, ...stated.engine_models.operators]);
      assert.equal(run.law.engine_name, stated.law.id);
      assert.equal(run.provenance.folder, `runs/${run.law.form}`, "the folder as given, relative to the evidence: no machine path");
      assert.equal(run.provenance.definition_sha256, stated.definition_sha256);
      assert.equal(run.provenance.interfaces.law, stated.law.interface);
      assert.equal(run.fissions.length, stated.end.fissions);
      assert.equal(decodeEvents(run.trace.events).length, stated.end.events);
      assert.equal(run.trace.growths.length, run.fissions.length, "the run's empty last growth is left out");
      // The events' own times: each in its growth's span, in order within it.
      const fractions = new Uint16Array(Uint8Array.from(Buffer.from(run.trace.times.values, "base64")).buffer);
      assert.equal(fractions.length, stated.end.events);
      let at = 0;
      for (const length of run.trace.growths) {
        for (let e = 1; e < length; e++) assert.ok(fractions[at + e] >= fractions[at + e - 1]);
        at += length;
      }
      // Each line it states is the run's own text, in its place.
      const raw = readFileSync(path.join(dir, "runs", run.law.form, "run.json"), "utf8");
      for (const line of run.states.lines) {
        const key = line.path.split(".").at(-1);
        const value = line.text === "true" || line.text === "false" || line.text === "null" || /^[-\d.e+]+$/.test(line.text) ? line.text : JSON.stringify(line.text);
        assert.ok(raw.includes(`"${key}": ${value}`), `${line.path}: ${line.text}`);
      }
    }
    // One world, one of each form, the same rules: the view's pair, once the two files are read together.
    const set = new AssemblySet(mergeRunFiles(files));
    assert.deepEqual(set.formsPair()?.map((run) => run.form).sort(), ["pair-consistent", "single-event"]);
  } finally {
    done();
  }
});

test("the same input gives the same bytes, and a run whose interface IDs change at the freeze adapts to the same file but for what it names of them", () => {
  const { dir, done } = scratch();
  try {
    assert.equal(py([MAKE, path.join(dir, "runs", "a")]).status, 0);
    assert.equal(py([MAKE, path.join(dir, "runs", "b"), "--interfaces", "final"]).status, 0);
    for (const [run, out] of [["runs/a", "one"], ["runs/a", "two"], ["runs/b", "final"]]) assert.equal(adapt(dir, path.join(dir, out), [run]).status, 0);
    const [one, two, final] = ["one", "two", "final"].map((out) => readAll(path.join(dir, out)));
    assert.deepEqual(one, two, "deterministic");
    const a = JSON.parse(one[0].text), b = JSON.parse(final[0].text);
    assert.notDeepEqual(a.runs[0].provenance.interfaces, b.runs[0].provenance.interfaces);
    for (const file of [a, b]) {
      delete file.runs[0].provenance.interfaces;
      delete file.runs[0].provenance.folder;
      delete file.runs[0].provenance.files_sha256;
    }
    assert.deepEqual(a, b);
    // No interface ID is held in the adapter: it copies the run's own.
    const source = readFileSync(TOOL, "utf8");
    for (const name of ["exchange_law", "rate_factor", "lineage_operator", "assembly_lineages.operator"]) assert.ok(!source.includes(name), name);
  } finally {
    done();
  }
});

test("it stops with a plain error where the run lacks what the contract needs or states what it does not know", () => {
  const { dir, done } = scratch();
  try {
    const expected = {
      "unknown-key": /states judgement, which this adapter does not know/,
      "missing-record": /records table has no event_time/,
      "tail-events": /goes on for 1 events after its last fission/,
      "nan-similarity": /no similarity \(an empty daughter\)/,
      "bad-channel": /channel 99 is not in the run's channel table/,
      "wrong-axes": /fission_split has the axes/,
    };
    for (const [fault, words] of Object.entries(expected)) {
      assert.equal(py([MAKE, path.join(dir, "runs", fault), "--fault", fault]).status, 0);
      const result = adapt(dir, path.join(dir, "out"), [`runs/${fault}`]);
      assert.equal(result.status, 1, fault);
      assert.match(result.stderr, words, fault);
      assert.ok(!existsSync(path.join(dir, "out")) || readdirSync(path.join(dir, "out")).length === 0, `${fault}: nothing written`);
    }
    // Without a standing the run does not state, it stops too.
    assert.equal(py([MAKE, path.join(dir, "runs", "plain")]).status, 0);
    const bare = py([TOOL, "--evidence", dir, "--out", path.join(dir, "out"), "runs/plain"]);
    assert.equal(bare.status, 1);
    assert.match(bare.stderr, /run\.json states no standing/);
  } finally {
    done();
  }
});

test("the engine's two runs of one world: each a small file the view reads, the pair under one clock, every line as the run states it", { skip: realHere ? false : `the run folders are not at hand (${REAL})` }, () => {
  const { dir, done } = scratch();
  try {
    const result = adapt(REAL_ROOT, path.join(dir, "out"), REAL_RUNS);
    assert.equal(result.status, 0, result.stderr);
    const read = readAll(path.join(dir, "out"));
    assert.equal(read.length, REAL_RUNS.length);
    const files = read.map(({ text }) => JSON.parse(text));
    for (const [index, { text }] of read.entries()) {
      assert.ok(Buffer.byteLength(text) < 1024 * 1024, "well under 1 MB");
      const file = files[index];
      assert.deepEqual(problemsOf(file), []);
      const run = file.runs[0];
      const folder = path.join(REAL_ROOT, run.provenance.folder);
      const stated = JSON.parse(readFileSync(path.join(folder, "run.json"), "utf8"));
      assert.equal(run.fissions.length, stated.end.fissions);
      assert.equal(decodeEvents(run.trace.events).length, stated.end.events);
      assert.equal(run.law.form, stated.law.form);
      assert.equal(run.law.engine_name, stated.law.id);
      assert.equal(run.revision, stated.source.revision);
      assert.equal(run.provenance.qualifier, stated.run.qualifier);
      assert.equal(run.provenance.world, stated.world);
      const raw = readFileSync(path.join(folder, "run.json"), "utf8");
      for (const line of run.states.lines) {
        const key = line.path.split(".").at(-1);
        if (line.text.startsWith("[")) {
          // A list: its items as the run writes them, in order.
          assert.deepEqual(JSON.parse(line.text), line.path.split(".").reduce((value, part) => value[part], stated), line.path);
          continue;
        }
        const value = /^(true|false|null|[-\d.e+]+)$/.test(line.text) ? line.text : JSON.stringify(line.text);
        assert.ok(raw.includes(`"${key}": ${value}`), `${line.path}: ${line.text} is not run.json's own text`);
      }
      assert.ok(run.states.lines.some((line) => line.path === "ledger.closure.max_abs_residual_kT" && line.text === raw.match(/"max_abs_residual_kT": ([^,\n]+)/)[1]), "the ledger's largest residual, exactly as written");
    }
    const set = new AssemblySet(mergeRunFiles(files));
    assert.equal(set.formsPair()?.length, 2, "one world, one of each form: the pair");
  } finally {
    done();
  }
});

test("the held population preserves carrier identity, release time and returned counts and refuses a missing record", async () => {
  const { VesicleRun } = await import("../src/lenses/vesicle_run.js");
  const dir = mkdtempSync(path.join(tmpdir(), "vesicle-bundle-"));
  try {
    for (const [fault, message] of [
      ["", null],
      ["key", /carrier key/],
      ["record", /no membrane_footprint_quanta/],
      ["hold", /applied tension/],
      ["duplicate", /duplicate rupture/],
    ]) {
      const made = py([
        "-c",
        "import runpy,sys;runpy.run_path(sys.argv[1])['pore_fixture'](sys.argv[2],sys.argv[3])",
        MAKE,
        path.join(dir, "input"),
        fault,
      ]);
      assert.equal(made.status, 0, made.stderr);
      const out = path.join(dir, "adapted" + fault);
      const r = py([TOOL, "--evidence", dir, "--out", out, "--standing", "development", "--standing-from", "fixture", "input"]);
      if (message) {
        assert.equal(r.status, 1);
        assert.match(r.stderr, message);
        continue;
      }
      assert.equal(r.status, 0, r.stderr);
      const data = JSON.parse(readFileSync(path.join(out, readdirSync(out)[0]), "utf8"));
      const run = new VesicleRun(data);
      assert.deepEqual(
        [0, 1.99, 2, 6.99, 7].map((t) => run.survivors(t)),
        [2, 2, 1, 1, 0],
      );
      assert.equal(run.at(0, 1).sample.key, "4294967296");
      assert.deepEqual([run.at(0, 1).sample.membrane_footprint_quanta, run.at(2, 0).sample.membrane_footprint_quanta], [8, 4]);
      assert.equal(run.at(2, 1).sample, null);
      assert.deepEqual(
        data.releases.map((e) => [e.cause, e.slot, e.returned["L@pool"]]),
        [
          ["pore", 1, 8],
          ["pore", 0, 4],
        ],
      );
      assert.equal(run.at(1, 0).hold.sigma_N_per_m, 0.001);
      assert.equal(run.at(1, 0).sample.lumen_volume_L, undefined);
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
