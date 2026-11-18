// The tissue's runs as the page packages them (tools/adapt_run.py), for each part of the example the selection names
// (the line and the sheet), held to what the runs' driver states and to what the condition gives the transfers:
//
// - Bands: the cell's colour is the stated quantity's band under the criterion's thresholds (src/replay/tissue_line.js,
//   Breaks). For every arm, record and cell, the band the packaged value falls in is the state the driver states for it
//   (criterion.json beside the run), and the packaged state is the driver's. The packaged numbers are 32-bit, a rounding
//   of the driver's: this is where a rounding that crossed a threshold would show.
// - Transfers: in the "neither" condition miR200 is neutral and every junction's voltage difference is zero, so its
//   junction flux is Fick's, down its own gradient (the record's note, section 7.1): over an interval, what a junction's
//   route carried goes from the cell holding more miR200 to the cell holding less. Held for every route and interval
//   where the two cells' order is the same at both ends; it catches a wrong route order and a wrong sign together. A
//   run with D = 0 declares no routes, and carries nothing.
// - Size: what the tissue fetches for one arm (its run file and its transfers' file) stays under about a megabyte.
//
// The packaged numbers are 32-bit: a difference between two cells, or between two of a route's totals, smaller than a
// millionth of the numbers it is taken from is below what 32 bits keep, and is not read.
//
//   node --test tests/tissue_packages.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openReplay, decodeBase64 } from "../src/replay/source.js";
import { Breaks } from "../src/replay/tissue_line.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const EVIDENCE = process.env.EVIDENCE || "/mnt/workspaces/Cells";
const PARTS = ["gap-junction-tissue-line", "gap-junction-tissue-sheet"];
const selection = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "selection.json"), "utf8"));
const folderOf = (part) => path.join(EVIDENCE, selection[part].evidence_folder, ...(selection[part].within || []));
const FLOOR = 1e-6; // a millionth: below it, a 32-bit difference is rounding
const ARM_BYTES = 1024 * 1024; // what the tissue fetches for one arm, at most
const QUANTITY = "stated.mir200_minus_zeb_mrna";
const missing = PARTS.filter((part) => !existsSync(folderOf(part)));
const skip = missing.length ? `the selection's runs are not on this machine (${missing.map(folderOf).join(", ")})` : false;

/** Every part's runs, packaged by the page's adapter into a folder of the test's own, each opened with every part attached. */
function packaged() {
  const out = mkdtempSync(path.join(os.tmpdir(), "cells-tissue-"));
  test.after(() => rmSync(out, { recursive: true, force: true }));
  for (const part of PARTS) {
    const done = spawnSync("python3", [path.join(ROOT, "tools", "adapt_run.py"), "--evidence", EVIDENCE, "--experiment", part, "--out", out], { encoding: "utf8" });
    assert.equal(done.status, 0, done.stderr);
  }
  const index = JSON.parse(readFileSync(path.join(out, "index.json"), "utf8"));
  return index.runs
    .filter((row) => PARTS.includes(row.experiment))
    .map((row) => {
      const run = openReplay(JSON.parse(readFileSync(path.join(out, `${row.id}.json`), "utf8")), row);
      for (const part of row.parts || []) {
        const file = JSON.parse(readFileSync(path.join(out, path.basename(part.file)), "utf8"));
        run.attach(part.id, decodeBase64(file.payload.data));
      }
      const arm = row.id.slice(row.experiment.length + 2);
      const bytes = statSync(path.join(out, `${row.id}.json`)).size + (row.parts || []).filter((part) => part.id === "passive-transferred").reduce((sum, part) => sum + statSync(path.join(out, path.basename(part.file))).size, 0);
      return { row, run, arm, bytes, criterion: JSON.parse(readFileSync(path.join(folderOf(row.experiment), arm, "criterion.json"), "utf8")) };
    });
}

let cache = null;
const runs = () => (cache ??= packaged());

test("each part's arms are packaged, and what the tissue fetches for one arm stays under a megabyte", { skip }, () => {
  for (const part of PARTS) assert.ok(runs().some((item) => item.row.experiment === part), `${part} has runs`);
  for (const { row, bytes } of runs()) assert.ok(bytes <= ARM_BYTES, `${row.id}: ${bytes} bytes`);
});

test("the band each packaged value falls in is the state the driver states, for every arm, record and cell", { skip }, () => {
  const colours = { below: ["#000000", "#000000"], above: ["#ffffff", "#ffffff"], between: "#808080" };
  const word = { below: "M", between: "X", above: "E" };
  let read = 0;
  for (const { row, run, criterion } of runs()) {
    const record = run.records.get(QUANTITY), states = run.records.get(`${QUANTITY}.state`);
    assert.ok(record && states, `${row.id}: the stated quantity and its states are packaged`);
    const breaks = new Breaks(record.marks, -1, 1, colours);
    assert.deepEqual([breaks.lower, breaks.upper], [criterion.criterion.lower.threshold, criterion.criterion.threshold], `${row.id}: the scale breaks where the criterion does`);
    const ids = run.sets.get("cell").ids;
    const column = criterion.cells.map((cell) => ids.indexOf(cell));
    assert.ok(column.every((k) => k >= 0), `${row.id}: every cell the criterion names is a cell of the run`);
    assert.equal(run.count, criterion.times_s.length, `${row.id}: one packaged record for each stated time`);
    const wrong = [];
    criterion.times_s.forEach((time, k) => {
      assert.ok(Math.abs(run.t[k] - time) <= 1e-6 * Math.max(1, time), `${row.id}: record ${k} at ${time} s`);
      criterion.cells.forEach((cell, c) => {
        const stated = criterion.states[k][c], value = record.at(k, column[c]);
        if (word[breaks.side(value)] !== stated || states.text(k, column[c]) !== stated) wrong.push({ time, cell, stated, value, driver: criterion.values[k][c] });
        read++;
      });
    });
    assert.deepEqual(wrong.slice(0, 5), [], `${row.id}: ${wrong.length} values fall in another band than their stated state`);
  }
  assert.ok(read > 100000, `every value was read (${read})`);
});

/** For one run: every (route, interval) read, and those where what crossed did not go from more to less. `byOrder` maps routes to junctions by their order instead of by the view's `at`. */
function directions(run, { byOrder = false } = {}) {
  const routes = run.sets.get("passive_route"), junctions = run.sets.get("junction");
  assert.ok(routes?.geometry?.kind === "on" && routes.geometry.set === "junction", "each route stands on the junction the view says it acts at");
  assert.equal(junctions.roles?.sender, "the junction's first cell (ends[0])", "the junction's sender is its first cell, as the view states");
  let read = 0;
  const wrong = [];
  routes.ids.forEach((name, r) => {
    const species = routes.species[r];
    const carried = Array.isArray(species) ? species : [species];
    for (const id of carried) {
      const moved = run.records.get(`passive_transferred.${id}`), held = run.records.get(`amount.${id}`);
      assert.ok(moved && held, `the route ${name}'s total and the amounts of what it carries (${id}) are packaged`);
      assert.equal(moved.sign?.from, "outside", "positive: from the route's outside end (the junction's receiver) into its inside end (its sender), as the view states");
      const junction = byOrder ? r : routes.geometry.index[r];
      const [sender, receiver] = junctions.geometry.ends[junction];
      for (let k = 0; k + 1 < run.count; k++) {
        const before = held.at(k, sender) - held.at(k, receiver), after = held.at(k + 1, sender) - held.at(k + 1, receiver);
        const scale = Math.max(Math.abs(held.at(k, sender)), Math.abs(held.at(k, receiver)), Math.abs(held.at(k + 1, sender)), Math.abs(held.at(k + 1, receiver)));
        if (Math.abs(before) <= FLOOR * scale || Math.abs(after) <= FLOOR * scale || before > 0 !== after > 0) continue;
        const delta = moved.at(k + 1, r) - moved.at(k, r), total = Math.max(Math.abs(moved.at(k, r)), Math.abs(moved.at(k + 1, r)));
        if (Math.abs(delta) <= FLOOR * total) continue;
        read++;
        // Into the sender when positive: right where the receiver held more.
        if (delta > 0 !== before < 0) wrong.push({ route: name, junction, interval: [run.t[k], run.t[k + 1]], before, delta });
      }
    }
  });
  return { read, wrong };
}

test("what each junction carried over an interval went from the cell holding more miR200 to the cell holding less", { skip }, () => {
  let total = 0, coupled = 0;
  for (const { row, run } of runs()) {
    if (!run.sets.get("passive_route")) {
      // D = 0: the run declares no routes, and no transfers are packaged.
      assert.equal(run.records.get("passive_transferred.u"), undefined, `${row.id}: no routes, nothing carried`);
      continue;
    }
    coupled++;
    const { read, wrong } = directions(run);
    assert.deepEqual(wrong, [], `${row.id}: ${wrong.length} of ${read} intervals carried against the gradient`);
    total += read;
  }
  assert.ok(coupled >= 2 && total > 1000, `enough intervals were read to mean something (${total}, in ${coupled} runs)`);
  // On a line whose cells fall in one order along it every junction carries the same way, so a wrong route order keeps
  // every direction: it is seen in how much each carried. Fick's flux with one constant on every junction makes what a
  // junction carried over an interval, over the mean of its two cells' difference then, the same for every junction of
  // that interval (up to the change of the difference within it). Read by where each route acts, the largest of these
  // over the smallest stays near one at most intervals; read in the routes' own order (j0, j10, j11, …), it does not.
  for (const { row, run } of runs()) {
    if (!run.sets.get("passive_route")) continue;
    const right = proportion(run), shuffled = proportion(run, { byOrder: true });
    if (right === null) continue;
    assert.ok(right < 1.5, `${row.id}: by where each route acts, what junctions carried is in proportion to their differences (median spread ${right})`);
    assert.ok(shuffled > 100, `${row.id}: read in the routes' own order it is not (median spread ${shuffled})`);
  }
});

/** The median, over intervals where three junctions or more carried, of the largest over the smallest of (carried / mean difference); null where there are none. */
function proportion(run, { byOrder = false } = {}) {
  const routes = run.sets.get("passive_route"), junctions = run.sets.get("junction");
  const spreads = [];
  for (let k = 0; k + 1 < run.count; k++) {
    const ratios = [];
    routes.ids.forEach((_, r) => {
      const id = Array.isArray(routes.species[r]) ? routes.species[r][0] : routes.species[r];
      const moved = run.records.get(`passive_transferred.${id}`), held = run.records.get(`amount.${id}`);
      const [sender, receiver] = junctions.geometry.ends[byOrder ? r : routes.geometry.index[r]];
      const gradient = (held.at(k, receiver) - held.at(k, sender) + held.at(k + 1, receiver) - held.at(k + 1, sender)) / 2;
      const delta = moved.at(k + 1, r) - moved.at(k, r), scale = Math.max(Math.abs(held.at(k, sender)), Math.abs(held.at(k, receiver)));
      if (Math.abs(gradient) > FLOOR * scale && Math.abs(delta) > FLOOR * Math.max(Math.abs(moved.at(k, r)), Math.abs(moved.at(k + 1, r)))) ratios.push(Math.abs(delta / gradient));
    });
    if (ratios.length >= 3) spreads.push(Math.max(...ratios) / Math.min(...ratios));
  }
  if (!spreads.length) return null;
  spreads.sort((a, b) => a - b);
  return spreads[Math.floor(spreads.length / 2)];
}
