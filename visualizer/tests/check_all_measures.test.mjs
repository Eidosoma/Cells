// The click runner's rule for a bound on time (tools/check_all.mjs, tools/lib/measures.mjs), held on made-up scenarios
// through the runner itself (--suite: no page is built and no browser is started): a scenario whose measures stand
// within their bounds beside others passes there and is not run again; one with a measure over its bound beside others
// is run again alone, after the others, and passes or fails by what it measures alone; a scenario that fails a check
// beside others stays failed and is not run again; one of the `alone` class is judged on its first run, alone. Each
// made-up scenario is a small node script; about two seconds in all.
//
//   node --test tests/check_all_measures.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(path.join(ROOT, "out"), { recursive: true });
const HOME = mkdtempSync(path.join(ROOT, "out", ".check-all-measures-"));
test.after(() => rmSync(HOME, { recursive: true, force: true }));

// A made-up scenario: one measure of a time against its bound (its value beside others and alone given by the
// scenario), a check that holds it, and a check that fails where MADE_FAIL is set. Each run is counted in a file.
const TOOL = path.join(HOME, "made_scenario.mjs");
writeFileSync(TOOL, [
  `import { appendFileSync } from "node:fs";`,
  `import { within } from ${JSON.stringify(pathToFileURL(path.join(ROOT, "tools", "lib", "measures.mjs")).href)};`,
  "const beside = process.env.CELLS_MEASURES === \"beside\";",
  "appendFileSync(process.env.MADE_RUNS, `${process.env.MADE_NAME} ${beside ? \"beside\" : \"alone\"}\\n`);",
  "const value = Number(beside ? process.env.MADE_BESIDE : process.env.MADE_ALONE);",
  "const results = [];",
  "const check = (name, ok) => { results.push(Boolean(ok)); console.log(`${ok ? \"pass\" : \"FAIL\"}  ${name}`); };",
  "check(\"a count that is pass or fail everywhere\", !process.env.MADE_FAIL);",
  "check(\"a frame leaves room at 60 frames a second\", within(\"a frame's work\", value, 8));",
  "console.log(`${results.filter(Boolean).length} of ${results.length} checks passed`);",
  "process.exit(results.every(Boolean) ? 0 : 1);",
  "",
].join("\n"));
const RUNS = path.join(HOME, "runs.txt");
const made = (name, beside, alone, more = {}) => ({ name, tool: TOOL, env: { MADE_NAME: name, MADE_RUNS: RUNS, MADE_BESIDE: String(beside), MADE_ALONE: String(alone), ...more.env }, minutes: 1, ...(more.alone ? { alone: true } : {}) });
const SUITE = [
  made("within-beside", 3, 3),
  made("over-beside-within-alone", 12, 3),
  made("over-beside-over-alone", 12, 12),
  made("fails-beside", 12, 3, { env: { MADE_FAIL: "1" } }),
  made("alone-class-over", 12, 12, { alone: true }),
];
writeFileSync(path.join(HOME, "suite.json"), JSON.stringify(SUITE));
const OUT = path.join(HOME, "out");
const env = { ...process.env, CELLS_BROWSER_CPU: "any", CELLS_BROWSER_SLOTS: "4" };
delete env.CELLS_MEASURES;
const ran = spawnSync(process.execPath, [path.join(ROOT, "tools", "check_all.mjs"), "--suite", path.join(HOME, "suite.json"), "--jobs", "3", "--out", OUT], { cwd: ROOT, env, encoding: "utf8", timeout: 120000 });
const summary = existsSync(path.join(OUT, "summary.json")) ? JSON.parse(readFileSync(path.join(OUT, "summary.json"), "utf8")) : null;
const runsOf = (name) => (existsSync(RUNS) ? readFileSync(RUNS, "utf8").trim().split("\n").filter((line) => line.split(" ")[0] === name).map((line) => line.split(" ")[1]) : []);
const result = (name) => summary.scenarios.find((item) => item.name === name);
const ok = (item) => item.exit === 0 && item.checks !== null && item.passed === item.checks;

test("the runner ran the made-up suite and wrote its summary, ending in failure where a scenario failed", () => {
  assert.ok(summary, ran.stdout + ran.stderr);
  assert.equal(ran.status, 1, ran.stdout + ran.stderr);
  assert.match(ran.stdout, /^5 scenarios on /m, ran.stdout);
  assert.equal(summary.scenarios.length, 5);
});

test("within its bound beside others, a scenario passes there and is not run again", () => {
  assert.deepEqual(runsOf("within-beside"), ["beside"]);
  const item = result("within-beside");
  assert.ok(ok(item), JSON.stringify(item));
  assert.ok(!summary.sent_alone.some((sent) => sent.name === "within-beside"));
  assert.deepEqual(item.measures.map((one) => [one.name, one.value, one.bound, one.within]), [["a frame's work", 3, 8, true]], "its measure is in the summary");
});

test("over its bound beside others, a scenario is run again alone, and passes or fails by what it measures alone", () => {
  assert.deepEqual(runsOf("over-beside-within-alone"), ["beside", "alone"]);
  assert.deepEqual(runsOf("over-beside-over-alone"), ["beside", "alone"]);
  const good = result("over-beside-within-alone"), bad = result("over-beside-over-alone");
  assert.ok(ok(good), JSON.stringify(good));
  assert.ok(!ok(bad), JSON.stringify(bad));
  assert.ok(summary.failed.includes("over-beside-over-alone") && !summary.failed.includes("over-beside-within-alone"));
  // The summary says which were sent there, with each measure's value both times.
  const sent = Object.fromEntries(summary.sent_alone.map((item) => [item.name, item]));
  assert.deepEqual(Object.keys(sent).sort(), ["over-beside-over-alone", "over-beside-within-alone"]);
  assert.deepEqual(sent["over-beside-within-alone"].measures.map((one) => [one.name, one.beside, one.alone, one.bound]), [["a frame's work", 12, 3, 8]]);
  assert.deepEqual(sent["over-beside-over-alone"].measures.map((one) => [one.name, one.beside, one.alone, one.bound]), [["a frame's work", 12, 12, 8]]);
  assert.equal(sent["over-beside-within-alone"].passed, true);
  assert.equal(sent["over-beside-over-alone"].passed, false);
  // Alone, after the others: every run alone was started once every run beside others had ended.
  assert.match(ran.stdout, /run again alone, after the others/);
  const order = readFileSync(RUNS, "utf8").trim().split("\n").map((line) => line.split(" ")[1]);
  assert.ok(order.lastIndexOf("beside") < order.indexOf("alone"), order.join(","));
});

test("a scenario that fails a check beside others stays failed, and is not run again", () => {
  assert.deepEqual(runsOf("fails-beside"), ["beside"]);
  assert.ok(!ok(result("fails-beside")));
  assert.ok(summary.failed.includes("fails-beside"));
  assert.ok(!summary.sent_alone.some((sent) => sent.name === "fails-beside"));
});

test("a scenario of the alone class is judged on its first run, alone, as before", () => {
  assert.deepEqual(runsOf("alone-class-over"), ["alone"]);
  assert.ok(!ok(result("alone-class-over")));
  assert.deepEqual(summary.alone.filter((name) => name === "alone-class-over"), ["alone-class-over"]);
  assert.ok(!summary.sent_alone.some((sent) => sent.name === "alone-class-over"));
});
