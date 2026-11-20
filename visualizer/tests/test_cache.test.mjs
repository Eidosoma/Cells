// The quick sweep's record of passes (tests/lib/test_cache.mjs), held on planted changes in a made-up tree: a made-up
// tool, output, test file, manifest of saved downloads, evidence folder and engine checkout, in a folder of its own on
// disk under out/, removed after. One byte changed in each kind of input runs the test again; nothing changed skips it;
// forced, it runs; a failing run records no pass; a record that cannot be read is no record; a missing input is a miss;
// and where the cache was not asked for (npm test) nothing is read, skipped or written. No world is made and no
// download is read. About a second, most of it the three made-up runs of node's test runner at the end.
//
//   node --test tests/test_cache.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { asked, fingerprint, Missing, passedBefore, readRecord, recordPath, SKIP_MARK, testId, writeRecord } from "./lib/test_cache.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(path.join(ROOT, "out"), { recursive: true });
const HOME = mkdtempSync(path.join(ROOT, "out", ".test-cache-proof-"));
test.after(() => rmSync(HOME, { recursive: true, force: true }));
const MADE = path.join(HOME, "tree"), CACHE = path.join(HOME, "cache"), ENGINE = path.join(HOME, "engine");
const at = (...parts) => path.join(MADE, ...parts);
const put = (file, text) => {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text);
};
put(at("tools", "made_tool.py"), "print('the same bytes every time')\n");
put(at("tools", "lib", "made_lib.py"), "VALUE = 1\n");
put(at("tests", "lib", "made_helper.mjs"), "export const helper = 1;\n");
put(at("tests", "made.test.mjs"), "// a made-up rebuild test\n");
put(at("data", "made", "output.json"), '{"made": "output"}\n');
// The page's modules a tool reaches: src/scene/ whole, a module a tool imports and what that imports, a folder a Python
// tool names; and one that nothing reaches.
put(at("src", "scene", "made_scene.js"), "export const scene = 1;\n");
put(at("tools", "made_page_tool.mjs"), 'import { entry } from "../src/made/entry.js";\nexport default entry;\n');
put(at("src", "made", "entry.js"), 'import { inner } from "./inner.js";\nexport const entry = inner;\n');
put(at("src", "made", "inner.js"), "export const inner = 1;\n");
put(at("tools", "made_runner.py"), 'STAGES = ROOT / "src" / "named" / "stages.js"\n');
put(at("src", "named", "stages.js"), "export const stages = 1;\n");
put(at("src", "unreached", "alone.js"), "export const alone = 1;\n");
put(at("node_modules", ".package-lock.json"), '{"packages": {"made": {"version": "1.0.0"}}}\n');
const SAVED = path.join(HOME, "downloads", "made", "source");
put(path.join(SAVED, "MANIFEST.json"), JSON.stringify({ files: [{ name: "entry.bin", size_bytes: 4, ok: true }, { name: "never.bin", ok: false }] }));
put(path.join(SAVED, "entry.bin"), "abcd");
put(path.join(SAVED, "entry.request.json"), '{"asked": "made"}');
const EVIDENCE = path.join(HOME, "evidence");
put(path.join(EVIDENCE, "requests.json"), JSON.stringify({ requests: [{ name: "answer.json" }] }));
put(path.join(EVIDENCE, "responses", "answer.json"), '{"answer": 1}');
const git = (...words) => spawnSync("git", ["-C", ENGINE, "-c", "user.name=made", "-c", "user.email=made@example.invalid", "-c", "commit.gpgsign=false", ...words], { encoding: "utf8" });
put(path.join(ENGINE, "src", "cells", "made.py"), "X = 1\n");
assert.equal(spawnSync("git", ["init", "-q", ENGINE]).status, 0);
git("add", "-A");
assert.equal(git("commit", "-q", "-m", "made").status, 0);

const SPEC = { file: at("tests", "made.test.mjs"), downloads: [path.join(HOME, "downloads", "*", "*")], evidence: [EVIDENCE], files: [path.join(SAVED, "entry.bin")], env: ["MADE_DATASETS"] };
const ENV = { MADE_DATASETS: "/made/datasets", CELLS_ENGINE_REPO: ENGINE };
let RUNTIME = { node: "v0.0.1", python: { version: "3.0.0", executable: "python3", libraries: {} } };
const OPTIONS = (env = ENV) => ({ root: MADE, env, runtime: () => RUNTIME });
const print = (env = ENV) => fingerprint(SPEC, OPTIONS(env)).hash;

/** A change made and undone: the fingerprint differs while it stands and is the first again once it is undone. */
function changes(label, make, undo) {
  const before = print();
  make();
  let during;
  try {
    during = print();
  } finally {
    undo();
  }
  assert.notEqual(during, before, `${label}: one change, and the fingerprint is the same`);
  assert.equal(print(), before, `${label}: undone, and the fingerprint is not the first`);
}
const byte = (file) => {
  const kept = readFileSync(file);
  return [() => writeFileSync(file, Buffer.concat([kept.subarray(0, -1), Buffer.from([kept.at(-1) ^ 1])])), () => writeFileSync(file, kept)];
};
const grown = (file) => {
  const kept = readFileSync(file);
  return [() => appendFileSync(file, "x"), () => writeFileSync(file, kept)];
};
const added = (file, text = "x") => [() => put(file, text), () => rmSync(file)];
/** One byte of a file that is read as JSON changed so that it still reads. */
const swapped = (file, from, to) => {
  const kept = readFileSync(file, "utf8");
  assert.equal(from.length, to.length);
  assert.ok(kept.includes(from), `${file} holds ${from}`);
  return [() => writeFileSync(file, kept.replace(from, to)), () => writeFileSync(file, kept)];
};

test("nothing changed, the same fingerprint; one byte changed in each kind of input, another", () => {
  assert.equal(print(), print(), "read twice, the same");
  changes("a tool", ...byte(at("tools", "made_tool.py")));
  changes("a tool's library", ...byte(at("tools", "lib", "made_lib.py")));
  changes("a tool added", ...added(at("tools", "new_tool.py")));
  changes("the helpers under tests/lib", ...byte(at("tests", "lib", "made_helper.mjs")));
  changes("the test's own file", ...byte(at("tests", "made.test.mjs")));
  changes("an output in the data folder (a hand edit)", ...byte(at("data", "made", "output.json")));
  changes("a file added to the data folder", ...added(at("data", "made", "more.json")));
  changes("a module under src/scene/", ...byte(at("src", "scene", "made_scene.js")));
  changes("a module of src/ a tool imports", ...byte(at("src", "made", "entry.js")));
  changes("a module that one imports in turn", ...byte(at("src", "made", "inner.js")));
  changes("a module in a folder of src/ a Python tool names", ...byte(at("src", "named", "stages.js")));
  {
    const before = print();
    const [make, undo] = byte(at("src", "unreached", "alone.js"));
    make();
    const during = print();
    undo();
    assert.equal(during, before, "a module of src/ that no tool reaches is not read");
  }
  changes("the manifest of the saved downloads", ...swapped(path.join(SAVED, "MANIFEST.json"), '"size_bytes":4', '"size_bytes":5'));
  changes("the size of a file the manifest lists", ...grown(path.join(SAVED, "entry.bin")));
  changes("a file beside the manifest that it does not list", ...grown(path.join(SAVED, "entry.request.json")));
  changes("a folder of downloads added where the test looks", ...added(path.join(HOME, "downloads", "made", "second", "MANIFEST.json"), '{"files": []}'));
  changes("the evidence's requests", ...byte(path.join(EVIDENCE, "requests.json")));
  changes("the size of an evidence file", ...grown(path.join(EVIDENCE, "responses", "answer.json")));
  changes("the installed node packages", ...byte(at("node_modules", ".package-lock.json")));
  for (const [name, value] of [["MADE_DATASETS", "/made/elsewhere"], ["PYTHONPATH", "/made/python"]]) {
    const kept = ENV[name];
    changes(`the environment's ${name}`, () => (ENV[name] = value), () => (kept === undefined ? delete ENV[name] : (ENV[name] = kept)));
  }
  changes("the engine's checkout: what is uncommitted", ...added(path.join(ENGINE, "src", "cells", "loose.py")));
  const head = git("rev-parse", "HEAD").stdout.trim();
  changes("the engine's checkout: its revision", () => {
    put(path.join(ENGINE, "src", "cells", "made.py"), "X = 2\n");
    git("commit", "-q", "-am", "another");
  }, () => {
    git("reset", "-q", "--hard", head);
  });
  for (const [label, change] of [["node's version", { node: "v0.0.2" }], ["python3's version", { python: { ...RUNTIME.python, version: "3.0.1" } }], ["a library's version", { python: { ...RUNTIME.python, libraries: { made: "2" } } }]]) {
    const kept = RUNTIME;
    changes(label, () => (RUNTIME = { ...kept, ...change }), () => (RUNTIME = kept));
  }
});

test("a missing input is a miss, never a pass", () => {
  const missing = (label, make, undo) => {
    make();
    try {
      assert.throws(() => print(), Missing, label);
    } finally {
      undo();
    }
    assert.doesNotThrow(() => print(), label);
  };
  const gone = (file) => {
    const kept = readFileSync(file);
    return [() => rmSync(file), () => put(file, kept)];
  };
  missing("a file its manifest lists as fetched", ...gone(path.join(SAVED, "entry.bin")));
  missing("the manifest itself", ...gone(path.join(SAVED, "MANIFEST.json")));
  missing("the evidence's requests", ...gone(path.join(EVIDENCE, "requests.json")));
  missing("the test's own file", ...gone(at("tests", "made.test.mjs")));
  const kept = ENV.CELLS_ENGINE_REPO;
  missing("an engine checkout that is not there", () => (ENV.CELLS_ENGINE_REPO = path.join(HOME, "no-engine")), () => (ENV.CELLS_ENGINE_REPO = kept));
  missing("a tool that imports a module it computes", ...added(at("tools", "computed.mjs"), "const name = \"x\";\nawait import(`../src/${name}.js`);\n"));
  missing("a Python tool that joins src to a name it computes", ...added(at("tools", "computed.py"), "PAGE = ROOT / \"src\" / folder\n"));
  missing("a module a tool imports that is not there", ...added(at("tools", "lost.mjs"), 'import "../src/made/lost.js";\n'));
  // A file the manifest lists as not fetched, and that is absent, is part of what it states: no miss.
  assert.ok(fingerprint(SPEC, OPTIONS()).lines.some((line) => line.endsWith("never.bin\tabsent, as listed")));
  // The interpreters as they are: node's and python3's own versions; a tool that imports a library not installed is a miss.
  const real = fingerprint(SPEC, { root: MADE, env: ENV });
  const runtime = JSON.parse(real.lines.find((line) => line.startsWith("runtime\t")).slice("runtime\t".length));
  assert.equal(runtime.node, process.version);
  assert.match(runtime.python.version, /^3\.\d+/);
  assert.deepEqual(runtime.python.libraries, {}, "the made-up tools import nothing outside Python's own");
  put(at("tools", "uses_library.py"), "import made_up_library_not_installed\n");
  try {
    assert.throws(() => fingerprint(SPEC, { root: MADE, env: ENV }), /a library a tool imports is not installed \(made_up_library_not_installed\)/);
  } finally {
    rmSync(at("tools", "uses_library.py"));
  }
});

/** A test's context as node's runner gives it, made up: its name, its file, and what the helper asks of it. */
function context(name = "rebuilds the made-up output") {
  const t = { name, filePath: SPEC.file, passed: true, skipped: null, afters: [], notes: [] };
  t.skip = (message) => (t.skipped = message);
  t.after = (fn) => t.afters.push(fn);
  t.diagnostic = (message) => t.notes.push(message);
  t.end = (passed = true) => {
    t.passed = passed;
    for (const fn of t.afters) fn();
  };
  return t;
}
const records = () => (existsSync(CACHE) ? readdirSync(CACHE).filter((name) => name.endsWith(".json")) : []);

test("cold it runs and records its pass; warm it is skipped, saying so; changed, forced, failed, or with a record that cannot be read, it runs", async () => {
  rmSync(CACHE, { recursive: true, force: true });
  const env = { ...ENV, CELLS_TEST_QUICK: "1", CELLS_TEST_CACHE: CACHE };
  const run = async (more = {}, passed = true, t = context()) => {
    const skipped = await passedBefore(t, SPEC, OPTIONS({ ...env, ...more }));
    if (!skipped) t.end(passed);
    return { skipped, t };
  };
  // Cold: no record; it runs, and its pass is recorded whole.
  let { skipped, t } = await run();
  assert.equal(skipped, false);
  assert.equal(t.skipped, null);
  assert.equal(records().length, 1, "one record");
  const id = testId(SPEC.file, t.name, MADE), hash = print();
  const record = readRecord(CACHE, id, hash);
  assert.deepEqual(Object.keys(record).sort(), ["fingerprint", "format", "result", "test", "when"], "which test, which fingerprint, when, and passed: nothing else");
  assert.equal(record.result, "passed");
  assert.equal(record.test, "tests/made.test.mjs › rebuilds the made-up output");
  assert.ok(!readdirSync(CACHE).some((name) => name.endsWith(".part")), "no part-written file is left");
  // Warm: skipped, its own line saying why and that npm test runs it.
  ({ skipped, t } = await run());
  assert.equal(skipped, true);
  assert.ok(t.skipped.startsWith(SKIP_MARK) && /passed before on these same inputs/.test(t.skipped) && /npm test runs it/.test(t.skipped), t.skipped);
  assert.equal(t.afters.length, 0, "skipped, nothing is recorded");
  // Another test of the same inputs has no record of its own.
  ({ skipped } = await run({}, true, context("another made-up test")));
  assert.equal(skipped, false, "a record is one test's");
  // One byte changed: it runs; undone, the first record stands again.
  const [make, undo] = byte(at("tools", "made_tool.py"));
  make();
  ({ skipped } = await run({}, false)); // and fails: no pass recorded on the changed inputs
  assert.equal(skipped, false, "changed, it runs");
  assert.equal(readRecord(CACHE, id, print()), null, "a failing run records no pass");
  ({ skipped } = await run());
  assert.equal(skipped, false, "still changed and no pass recorded, it runs again");
  undo();
  assert.equal((await run()).skipped, true, "undone, the first record skips it again");
  // Forced: it runs.
  assert.equal((await run({ CELLS_TEST_FORCE: "1" })).skipped, false, "forced, it runs");
  // A record that cannot be read, or that says anything but this test's pass on these inputs, is no record.
  const file = recordPath(CACHE, id, hash);
  const good = readFileSync(file, "utf8");
  for (const bad of [good.slice(0, 20), "", JSON.stringify({ ...JSON.parse(good), result: "failed" }), JSON.stringify({ ...JSON.parse(good), test: "tests/other.test.mjs › another" }), JSON.stringify({ ...JSON.parse(good), fingerprint: "0".repeat(64) })]) {
    writeFileSync(file, bad);
    const t2 = context();
    assert.equal(await passedBefore(t2, SPEC, OPTIONS(env)), false, `a record reading ${bad.slice(0, 40)} skips nothing`);
  }
  writeFileSync(file, good);
  // What it rests on changed while it ran: it records nothing.
  rmSync(file);
  const t3 = context();
  assert.equal(await passedBefore(t3, SPEC, OPTIONS(env)), false);
  appendFileSync(at("data", "made", "output.json"), " ");
  t3.end(true);
  assert.equal(readRecord(CACHE, id, hash), null);
  assert.equal(readRecord(CACHE, id, print()), null, "changed while it ran, no pass on either fingerprint");
  assert.ok(t3.notes.some((note) => /changed while it ran \(data data\/made\/output\.json\)/.test(note)), t3.notes.join(" | "));
  writeFileSync(at("data", "made", "output.json"), '{"made": "output"}\n');
  // A missing input: it runs, and records nothing.
  const kept = readFileSync(path.join(SAVED, "entry.bin"));
  rmSync(path.join(SAVED, "entry.bin"));
  const t4 = context();
  assert.equal(await passedBefore(t4, SPEC, OPTIONS(env)), false);
  assert.equal(t4.afters.length, 0, "missing, nothing will be recorded");
  assert.ok(t4.notes.some((note) => /records nothing/.test(note)), t4.notes.join(" | "));
  put(path.join(SAVED, "entry.bin"), kept);
});

test("where the cache was not asked for (npm test, or no switch), nothing is read, skipped or written", async () => {
  rmSync(CACHE, { recursive: true, force: true });
  const env = { ...ENV, CELLS_TEST_CACHE: CACHE };
  writeRecord(CACHE, testId(SPEC.file, "rebuilds the made-up output", MADE), print());
  for (const [label, more] of [["no switch", {}], ["switched off", { CELLS_TEST_QUICK: "0" }], ["under npm test, the switch exported", { CELLS_TEST_QUICK: "1", npm_lifecycle_event: "test" }]]) {
    assert.equal(asked({ ...env, ...more }), false, label);
    const t = context();
    assert.equal(await passedBefore(t, SPEC, OPTIONS({ ...env, ...more })), false, `${label}: it runs`);
    assert.equal(t.skipped, null, label);
    assert.equal(t.afters.length, 0, `${label}: nothing will be written`);
    assert.equal(t.notes.length, 0, `${label}: nothing said`);
  }
  assert.equal(records().length, 1, "only the planted record");
  assert.equal(asked({ CELLS_TEST_QUICK: "1", npm_lifecycle_event: "test:quick" }), true, "npm run test:quick asks");
});

test("through node's own runner: a pass recorded, then skipped with its own line and counted by the quick sweep's summary; a failure records nothing", () => {
  rmSync(CACHE, { recursive: true, force: true });
  const made = path.join(HOME, "made-run.test.mjs");
  const helper = pathToFileURL(path.join(ROOT, "tests", "lib", "test_cache.mjs")).href;
  writeFileSync(made, [
    'import test from "node:test";',
    `import { passedBefore } from ${JSON.stringify(helper)};`,
    `const SPEC = ${JSON.stringify(SPEC)};`,
    `const OPTIONS = { root: ${JSON.stringify(MADE)}, runtime: () => (${JSON.stringify(RUNTIME)}) };`,
    'test("rebuilds the made-up output", async (t) => {',
    "  if (await passedBefore(t, SPEC, OPTIONS)) return;",
    '  if (process.env.MADE_FAIL) throw new Error("made to fail");',
    "});",
    "",
  ].join("\n"));
  const env = { ...process.env, ...ENV, CELLS_TEST_QUICK: "1", CELLS_TEST_CACHE: CACHE };
  delete env.npm_lifecycle_event; // this file runs under npm test, which never asks; the made-up run stands for test:quick
  delete env.NODE_TEST_CONTEXT; // set for this file by node's runner: the made-up run is a runner of its own
  delete env.CELLS_TEST_FORCE;
  const node = (more = {}) => spawnSync(process.execPath, ["--test", "--test-reporter=spec", "--test-reporter-destination=stdout", `--test-reporter=${path.join(ROOT, "tests", "lib", "quick_summary.mjs")}`, "--test-reporter-destination=stdout", made], { cwd: HOME, env: { ...env, ...more }, encoding: "utf8" });
  const failed = node({ MADE_FAIL: "1" });
  assert.notEqual(failed.status, 0, failed.stdout);
  assert.equal(records().length, 0, "a failing run records no pass");
  const cold = node();
  assert.equal(cold.status, 0, cold.stdout + cold.stderr);
  assert.match(cold.stdout, /✔ rebuilds the made-up output/);
  assert.match(cold.stdout, /no test skipped/);
  assert.equal(records().length, 1, "its pass recorded");
  const warm = node();
  assert.equal(warm.status, 0, warm.stdout + warm.stderr);
  assert.match(warm.stdout, /﹣ rebuilds the made-up output \([^)]*\) # quick sweep: passed before on these same inputs \(fingerprint [0-9a-f]{12}, recorded [^)]+\); npm test runs it/);
  assert.match(warm.stdout, /quick sweep: 1 test skipped, each passed before on the same inputs; npm test runs it:\n.*made-run\.test\.mjs › rebuilds the made-up output/);
});
