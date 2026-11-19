// The judgement of what an address of the published page fetched (tools/lib/fetch_budget.mjs), on made-up fetches:
// a bound passed names the file that passed it, a file the address may not fetch is named, so is one the page does not
// publish and one fetched twice, and an address that fetched nothing it is for does not pass. And the table itself
// (tools/references/fetches.json): whole, with a row for every experiment the runs folder's catalogue holds.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { addressesOf, judge, matcher, tableProblems, BUDGETS_FORMAT } from "../tools/lib/fetch_budget.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TABLE = JSON.parse(readFileSync(path.join(ROOT, "tools", "references", "fetches.json"), "utf8"));

const row = { id: "pair", query: "lens=experiments&run=x--a", must: ["runs/x--a.json"], allowed: ["runs/x--a.json", "runs/x--a.*.json"], bytes: 1000 };
const file = (name, bytes, status = 200) => ({ path: name, bytes, status });

test("a pattern matches a published path, its star never across a folder", () => {
  assert.ok(matcher("runs/x--a.*.json")("runs/x--a.parts.json"));
  assert.ok(matcher("runs/planarian-loop--*")("runs/planarian-loop--p.amount.json"));
  assert.ok(!matcher("runs/x--a.*.json")("runs/x--a.json"));
  assert.ok(!matcher("models/gard/*")("models/gard/deeper/file.json"));
  assert.ok(!matcher("runs/x--a.json")("runs/x--aXjson"), "a dot is a dot");
});

test("what an address may fetch passes; each way past it is named with its file", () => {
  assert.deepEqual(judge(row, [file("runs/x--a.json", 600), file("runs/x--a.parts.json", 300)]), { total: 900, problems: [] });
  const over = judge(row, [file("runs/x--a.json", 600), file("runs/x--a.parts.json", 300), file("runs/x--a.more.json", 200)]);
  assert.deepEqual(over.problems, ["runs/x--a.more.json took what the address fetched to 1100 bytes, past its bound of 1000"]);
  const stray = judge(row, [file("runs/x--a.json", 600), file("runs/x--b.json", 40)]);
  assert.deepEqual(stray.problems, ["runs/x--b.json (40 bytes) is not one this address may fetch"], "another run is not allowed");
  assert.match(judge(row, [file("runs/x--a.json", 600), file("runs/x--a.gone.json", 0, 404)]).problems[0], /^runs\/x--a\.gone\.json was asked for and the page does not publish it \(it answered 404\)$/);
  assert.deepEqual(judge(row, [file("runs/x--a.json", 100), file("runs/x--a.json", 100)]).problems, ["runs/x--a.json was fetched twice"]);
  assert.deepEqual(judge(row, []).problems, ["nothing that matches runs/x--a.json was fetched: the address did not draw what it is for"], "an address that drew nothing does not pass");
  assert.deepEqual(judge({ ...row, files: 1 }, [file("runs/x--a.json", 100), file("runs/x--a.p.json", 100)]).problems, ["runs/x--a.p.json is file 2, past the bound of 1 files"]);
});

test("an experiment's row stands at its opening run, allows only that run's files, and a page's experiment with no row is said", () => {
  const replays = {
    experiments: [{ id: "x", opens: { run: "b" } }, { id: "y" }, { id: "z" }],
    runs: [{ id: "x--a", experiment: "x", arm: "a" }, { id: "x--b", experiment: "x", arm: "b" }, { id: "y--a", experiment: "y", arm: "a" }],
  };
  const table = { format: BUDGETS_FORMAT, addresses: [row], experiments: [{ experiment: "x", bytes: 500 }, { experiment: "z", bytes: 500 }] };
  const { rows, skipped, problems } = addressesOf(table, replays);
  assert.deepEqual(rows.map((item) => [item.id, item.query]), [["pair", row.query], ["x", "lens=experiments&run=x--b"]]);
  assert.deepEqual(rows[1].allowed, ["runs/x--b.json", "runs/x--b.*.json"]);
  assert.deepEqual(skipped, ["z: the page carries no run of it"]);
  assert.deepEqual(problems, ["the page carries runs of y, and the table gives it no budget: add a row to its experiments"]);
});

test("the table of budgets is whole, and has a row for every experiment of the runs folder that holds runs", () => {
  assert.deepEqual(tableProblems(TABLE), []);
  assert.deepEqual(tableProblems({ ...TABLE, addresses: [{ ...TABLE.addresses[0], must: [] }] }), ["address scope: must must list patterns"]);
  // The experiments that hold runs, from the overlay (what the adapter packages): every one has its row.
  const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "overlay.json"), "utf8"));
  const selection = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "selection.json"), "utf8"));
  const rowed = new Set(TABLE.experiments.map((item) => item.experiment));
  const packaged = Object.keys(selection).filter((id) => id in overlay.experiments);
  assert.ok(packaged.length >= 8);
  for (const id of packaged) assert.ok(rowed.has(id), `${id} is in the selection and has no row in tools/references/fetches.json`);
});
