#!/usr/bin/env node
// Runs every real-click check once, several at a time, and says what passed: the check that
// stands before a publish, as one command.
//
//   node tools/check_all.mjs [--out DIR] [--jobs N] [--only PATTERN] [--limit MINUTES] [--list]
//
// Each scenario is one run of one of the check tools, with its own browser. A run takes
// a place of the browser lock (tools/lib/browser_lock.mjs), so as many run at once as there
// are places (four on the project's machine: one core each), and --jobs asks for fewer.
// The longest scenarios start first. --only runs the scenarios whose names match a regular
// expression; --list names them and runs nothing. A scenario that has not ended after
// --limit minutes (40 unless given) is stopped together with its browser and counted as
// failed, so that one browser that hangs cannot hold the whole command.
//
// Into DIR (out/check-all/<time> unless given; on disk, never under /tmp) go one log for
// each scenario, the pictures the checks take (DIR/pictures) and summary.json: the revision
// and whether the tree was clean, and for each scenario its result, the checks that failed,
// whether the page's own font had arrived, and how long it took. The command ends with 0
// only when every scenario passed.
//
// Before the scenarios start, the page is built once, so that the files of the species'
// proteins are made by one process and not by several at once. The replays the layer checks
// read must be there already (README, "Experiment replays"): the command says so if not.

import { spawn, execFileSync } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, DEFAULT_RUNS, ROOT } from "./lib/build_page.mjs";
import { BROWSER_CPUS, places } from "./lib/browser_lock.mjs";

const args = process.argv.slice(2);
const value = (name, fallback = null) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
const out = path.resolve(value("--out", path.join(ROOT, "out", "check-all", stamp)));
const pictures = path.join(out, "pictures");
const DEV = "secreted-species-dev-run--secreted-species-dev-run", EXAMPLE = "example-sheet--invented-numbers";
// A sheet of 127 cells with voltage, generations and junction gates: the layer checks of a sheet open it by name, since the
// Experiments view opens on the first listed example (a small network since 17 November 2026). It is packaged for the checks
// and not listed or published.
const SHEET = "e07-v1--a-donor-fast-k1-d37-s1.0--seed5";
const LIMIT_MS = Math.max(1000, (Number(value("--limit", 40)) || 40) * 60 * 1000);

// The scenarios, the longest first. `minutes` is a rough length on one core, used only for the order.
const flux = (name, env, minutes = 4) => ({ name: `flux-${name}`, tool: "check_cellflux.mjs", args: [pictures], env: { NAME: `flux-${name}`, ...env }, minutes });
const SUITE = [
  { name: "species", tool: "check_species.mjs", minutes: 14 },
  { name: "species-model", tool: "check_species.mjs", env: { CASE: "model" }, minutes: 3 },
  // The origin-of-life view on the map's page (tools/check_origin.mjs): wide in both themes, a phone, by address, and the pair of forms on a check-only scene.
  { name: "origin-main", tool: "check_origin.mjs", args: [pictures], env: { CASE: "main", NAME: "origin-main" }, minutes: 2 },
  { name: "origin-dark", tool: "check_origin.mjs", args: [pictures], env: { CASE: "main", NAME: "origin-dark", THEME: "dark" }, minutes: 2 },
  { name: "origin-short", tool: "check_origin.mjs", args: [pictures], env: { CASE: "main", NAME: "origin-short", WIDTH: "1040", HEIGHT: "640" }, minutes: 2 },
  { name: "origin-phone", tool: "check_origin.mjs", args: [pictures], env: { CASE: "phone", NAME: "origin-phone" }, minutes: 2 },
  { name: "origin-address", tool: "check_origin.mjs", args: [pictures], env: { CASE: "address", NAME: "origin-address" }, minutes: 2 },
  { name: "origin-pair", tool: "check_origin.mjs", args: [pictures], env: { CASE: "pair", NAME: "origin-pair" }, minutes: 1 },
  // The engine's own runs: the page's where GARD's entry names them, else two adapted from their folder on a check-only scene ("skip" where neither is at hand).
  { name: "origin-engine", tool: "check_origin.mjs", args: [pictures], env: { CASE: "engine", NAME: "origin-engine" }, minutes: 3 },
  { name: "origin-engine-phone", tool: "check_origin.mjs", args: [pictures], env: { CASE: "engine", PHONE: "1", WIDTH: "400", HEIGHT: "800", NAME: "origin-engine-phone" }, minutes: 3 },
  // A machine's closer view (tools/check_machine.mjs): wide, on a phone in the dark, opened by the address, with less
  // motion, and with the cell drawn to scale. Minutes as measured on 16 November 2026 with up to three browsers on the visualizer's eight CPUs.
  { name: "machine-main", tool: "check_machine.mjs", args: [pictures], env: { CASE: "main", NAME: "machine-main" }, minutes: 20 },
  { name: "machine-phone", tool: "check_machine.mjs", args: [pictures], env: { CASE: "main", NAME: "machine-phone", WIDTH: "390", HEIGHT: "844", THEME: "dark" }, minutes: 12 },
  { name: "machine-address", tool: "check_machine.mjs", args: [pictures], env: { CASE: "address", NAME: "machine-address" }, minutes: 10 },
  { name: "machine-reduced", tool: "check_machine.mjs", args: [pictures], env: { CASE: "reduced", NAME: "machine-reduced" }, minutes: 5 },
  { name: "machine-scale", tool: "check_machine.mjs", args: [pictures], env: { CASE: "scale", NAME: "machine-scale" }, minutes: 10 },
  { name: "input-cell", tool: "check_input.mjs", env: { CHECK_ONLY: "cell" }, minutes: 5 },
  { name: "cell-ecoli", tool: "check_input.mjs", env: { CHECK_ONLY: "cell", CHECK_SPECIES: "ecoli" }, minutes: 5 },
  { name: "cell-thalecress", tool: "check_input.mjs", env: { CHECK_ONLY: "cell", CHECK_SPECIES: "thalecress" }, minutes: 5 },
  { name: "cell-mouse", tool: "check_input.mjs", env: { CHECK_ONLY: "cell", CHECK_SPECIES: "mouse" }, minutes: 5 },
  { name: "look-look", tool: "check_look.mjs", args: ["look"], minutes: 5 },
  flux("thalecress", { SPECIES: "thalecress" }, 5),
  flux("ecoli", { SPECIES: "ecoli" }, 5),
  // The junction network and a sweep's chart in the Experiments view, on check-only scenes (tools/check_junctions.mjs).
  { name: "junctions-network", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "network", NAME: "junctions-network" }, minutes: 2 },
  { name: "junctions-sweep", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "sweep", NAME: "junctions-sweep" }, minutes: 2 },
  { name: "junctions-phone", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "sweep", NAME: "junctions-phone", WIDTH: "390", HEIGHT: "844", THEME: "dark" }, minutes: 2 },
  { name: "junctions-reduced", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "network", NAME: "junctions-reduced", REDUCED: "1", THEME: "dark" }, minutes: 2 },
  { name: "junctions-levin", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "levin", NAME: "junctions-levin" }, minutes: 3 }, // the replication's real runs where they are on this machine, else skipped
  { name: "junctions-levin-phone", tool: "check_junctions.mjs", args: [pictures], env: { CASE: "levin", NAME: "junctions-levin-phone", WIDTH: "390", HEIGHT: "844", THEME: "dark" }, minutes: 3 }, // the same, and GARD in the tab, on a phone
  // The example's tissue line on its real runs (tools/check_tissue.mjs), skipped where they are not on this machine.
  { name: "tissue-wide", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "wide", NAME: "tissue-wide" }, minutes: 3 },
  { name: "tissue-phone", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "phone", NAME: "tissue-phone" }, minutes: 2 },
  { name: "tissue-reduced", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "reduced", NAME: "tissue-reduced" }, minutes: 2 },
  // The bacteria drawn to scale (17 November 2026): at the cell's stop and at the molecule stop, where the close-up's lanes take over.
  flux("ecoli-scale-cell", { SPECIES: "ecoli", SIZE: "real", SCALE: "cell" }, 5),
  flux("ecoli-scale-molecule", { SPECIES: "ecoli", SIZE: "real", SCALE: "molecule" }, 5),
  flux("syn3a-scale-cell", { SPECIES: "syn3a", SIZE: "real", SCALE: "cell" }, 5),
  flux("syn3a-scale-molecule", { SPECIES: "syn3a", SIZE: "real", SCALE: "molecule" }, 5),
  flux("moving", { MOVING: "1" }, 5),
  flux("light", {}),
  flux("dark", { THEME: "dark" }),
  flux("short", { WIDTH: "1040", HEIGHT: "640" }, 3),
  { name: "input-zoom", tool: "check_input.mjs", env: { CHECK_ONLY: "zoom" }, minutes: 3 },
  { name: "shelves-human", tool: "check_shelves.mjs", args: ["human"], minutes: 3 },
  { name: "input-atlas", tool: "check_input.mjs", env: { CHECK_ONLY: "atlas" }, minutes: 2 },
  { name: "input-species", tool: "check_input.mjs", env: { CHECK_ONLY: "species" }, minutes: 2 },
  { name: "input-experiments", tool: "check_input.mjs", env: { CHECK_ONLY: "experiments" }, minutes: 2 },
  { name: "input-engine", tool: "check_input.mjs", env: { CHECK_ONLY: "engine" }, minutes: 2 },
  { name: "look-switch", tool: "check_look.mjs", args: ["switch"], minutes: 2 },
  { name: "look-views", tool: "check_look.mjs", args: ["views"], minutes: 2 },
  // `minutes` only orders the scenarios, the longest first; every scenario has the same limit (--limit, 40 minutes).
  // In software the three walks took 4.7 and 6.2 minutes beside other work (17 November 2026); on the card, 71 s.
  { name: "look-loss", tool: "check_look.mjs", args: ["loss"], minutes: 6 },
  // The Laws library (tools/check_laws.mjs): presses, keys, the card's search and Family, the Engine view's door and the way back, a lost context; the address, and what it leaves behind; a 360 px phone; no 3D.
  { name: "laws-main", tool: "check_laws.mjs", args: [pictures], env: { CASE: "main", NAME: "laws-main" }, minutes: 3 },
  { name: "laws-address", tool: "check_laws.mjs", args: [pictures], env: { CASE: "address", NAME: "laws-address" }, minutes: 1 },
  { name: "laws-phone", tool: "check_laws.mjs", args: [pictures], env: { CASE: "phone", NAME: "laws-phone" }, minutes: 1 },
  { name: "laws-text", tool: "check_laws.mjs", args: [pictures], env: { CASE: "text", NAME: "laws-text" }, minutes: 1 },
  { name: "laws-gone", tool: "check_laws.mjs", args: [pictures], env: { CASE: "gone", NAME: "laws-gone" }, minutes: 1 },
  // The Machines tab (tools/check_catalogue.mjs): wide in both themes, a phone, by address, with no 3D, and the six tabs' row on phones.
  { name: "catalogue-main", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "main", NAME: "catalogue-main" }, minutes: 2 },
  { name: "catalogue-dark", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "main", NAME: "catalogue-dark", THEME: "dark" }, minutes: 2 },
  { name: "catalogue-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "phone", NAME: "catalogue-phone" }, minutes: 1 },
  { name: "catalogue-address", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "address", NAME: "catalogue-address" }, minutes: 2 },
  { name: "catalogue-text", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "text", NAME: "catalogue-text" }, minutes: 1 },
  { name: "catalogue-tabs", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "tabs", NAME: "catalogue-tabs" }, minutes: 6 },
  // The animals' benches: the planarian's, wide and on a phone (its outlines instanced, a unit's parts chosen by a real press).
  { name: "catalogue-animals", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "animals", NAME: "catalogue-animals" }, minutes: 2 },
  { name: "catalogue-animals-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "animals", NAME: "catalogue-animals-phone", WIDTH: "390", HEIGHT: "844" }, minutes: 2 },
  flux("phone", { WIDTH: "400", HEIGHT: "780" }, 2),
  flux("address", { ADDRESS: "1" }, 2),
  flux("loop", { LOOP: "1", MOVING: "1" }, 3), // the planarian's own looping run: it needs the run among the replays served (out/runs)
  { name: "shelves-planarian", tool: "check_shelves.mjs", args: ["planarian"], minutes: 2 },
  { name: "layers-closeup", tool: "check_layers.mjs", args: ["closeup"], env: { RUN: SHEET }, minutes: 2 },
  { name: "shelves-syn3a", tool: "check_shelves.mjs", args: ["syn3a"], minutes: 1 },
  { name: "shelves-nofiles", tool: "check_shelves.mjs", args: ["nofiles"], minutes: 1 },
  { name: "shelves-ecoli", tool: "check_shelves.mjs", args: ["ecoli"], minutes: 1 },
  { name: "shelves-stack-thalecress", tool: "check_shelves.mjs", args: ["stack"], env: { SPECIES: "thalecress" }, minutes: 1 },
  { name: "shelves-stack-mouse", tool: "check_shelves.mjs", args: ["stack"], env: { SPECIES: "mouse" }, minutes: 1 },
  { name: "shelves-accessory-mouse", tool: "check_shelves.mjs", args: ["accessory"], env: { SPECIES: "mouse" }, minutes: 1 },
  { name: "shelves-trail", tool: "check_shelves.mjs", args: ["trail"], minutes: 2 },
  { name: "shelves-search", tool: "check_shelves.mjs", args: ["search"], minutes: 2 },
  { name: "shelves-map", tool: "check_shelves.mjs", args: ["map"], env: { SPECIES: "thalecress" }, minutes: 1 },
  { name: "shelves-colours", tool: "check_shelves.mjs", args: ["colours"], minutes: 1 },
  { name: "shelves-gathering", tool: "check_shelves.mjs", args: ["gathering"], minutes: 1 },
  { name: "shelves-frame", tool: "check_shelves.mjs", args: ["frame"], minutes: 2 },
  { name: "shelves-accessory-human", tool: "check_shelves.mjs", args: ["accessory"], env: { SPECIES: "human" }, minutes: 2 },
  { name: "shelves-doors", tool: "check_shelves.mjs", args: ["doors"], minutes: 2 },
  { name: "layers-zero", tool: "check_layers.mjs", args: ["zero"], env: { RUN: SHEET }, minutes: 1 },
  { name: "layers-switch", tool: "check_layers.mjs", args: ["switch"], env: { RUN: SHEET }, minutes: 1 },
  { name: "layers-flow", tool: "check_layers.mjs", args: ["flow", DEFAULT_RUNS, pictures], env: { RUN: DEV, REFERENCE: path.join(ROOT, "tools", "references", "secreted-species-dev-run-0.4.json") }, minutes: 1 },
  { name: "layers-example", tool: "check_layers.mjs", args: ["example", DEFAULT_RUNS, pictures], env: { RUN: EXAMPLE }, minutes: 1 },
];

const only = value("--only") ? new RegExp(value("--only")) : null;
const chosen = SUITE.filter((item) => !only || only.test(item.name));
if (args.includes("--list")) {
  for (const item of chosen) console.log(`${item.name}  (${item.tool}${item.args?.length ? " " + item.args.map((word) => path.relative(ROOT, word) || word).join(" ") : ""}${Object.keys(item.env || {}).length ? "; " + Object.entries(item.env).map(([key, word]) => `${key}=${word}`).join(" ") : ""})`);
  process.exit(0);
}
if (!chosen.length) {
  console.error(`no scenario's name matches ${value("--only")}`);
  process.exit(2);
}

// ---------------------------------------------------------------- before the scenarios
// This command and what it starts keep to the processors set aside for browser runs, from
// the start: a scenario is otherwise free until it has taken its place, and the engine's
// jobs have the other processors.
const set = process.env.CELLS_BROWSER_CPU || BROWSER_CPUS;
if (set !== "any") {
  try {
    execFileSync("taskset", ["-a", "-cp", set, String(process.pid)], { stdio: "ignore" });
  } catch {}
}
const git = (...words) => {
  try {
    return execFileSync("git", ["-C", ROOT, ...words], { encoding: "utf8" }).trim();
  } catch {
    return null;
  }
};
const revision = git("rev-parse", "--short=8", "HEAD"), dirty = git("status", "--porcelain", "--", ".");
await mkdir(pictures, { recursive: true });
// The replays the layer checks read.
let runs = [];
try {
  runs = JSON.parse(await readFile(path.join(DEFAULT_RUNS, "index.json"), "utf8")).runs.map((run) => run.id);
} catch {}
const needs = chosen.some((item) => item.name.startsWith("layers-") || item.name === "input-experiments");
if (needs && !(runs.includes(DEV) && runs.includes(EXAMPLE))) {
  console.error("the replays are not made, or lack the development run or the example: see README, \"Experiment replays\" (two calls of npm run adapt:runs)");
  process.exit(2);
}
// One build of the page, so that the species' proteins are written once and not by every scenario at its start.
await buildPage({});
const slots = places().length;
const jobs = Math.max(1, Math.min(Number(value("--jobs", slots)) || slots, slots));
console.log(`${chosen.length} scenarios on ${revision ?? "an unknown revision"}${dirty ? " (with uncommitted changes)" : ""}, ${jobs} at a time; logs in ${path.relative(process.cwd(), out) || "."}`);

// ---------------------------------------------------------------- the scenarios, a few at a time
const began = Date.now();
const results = new Map();
const waiting = [...chosen].sort((a, b) => (b.minutes || 1) - (a.minutes || 1));

function run(item, attempt = 1) {
  return new Promise((resolve) => {
    const log = path.join(out, `${item.name}.log`);
    const stream = createWriteStream(log);
    const started = Date.now();
    // In a group of its own, so that a scenario over its time is stopped with the Chrome it started.
    const child = spawn(process.execPath, [path.join(ROOT, "tools", item.tool), ...(item.args || [])], { cwd: ROOT, env: { ...process.env, ...(item.env || {}) }, stdio: ["ignore", "pipe", "pipe"], detached: true });
    child.stdout.pipe(stream, { end: false });
    child.stderr.pipe(stream, { end: false });
    let over = false;
    const stop = (signal) => {
      try {
        process.kill(-child.pid, signal);
      } catch {} // the group has ended
    };
    // First asked to end, so that the check gives its place and its profile back; then ended.
    const limit = setTimeout(() => {
      over = true;
      stop("SIGTERM");
      setTimeout(() => stop("SIGKILL"), 5000).unref();
    }, LIMIT_MS);
    child.on("close", async (code) => {
      clearTimeout(limit);
      if (over) stop("SIGKILL"); // whatever of its browser is left
      stream.end();
      let text = "";
      try {
        text = await readFile(log, "utf8");
      } catch {}
      // Every place taken for too long by runs that are not this command's: try once more.
      if (!over && /held the lock for too long/.test(text) && attempt < 3) return resolve(run(item, attempt + 1));
      const counted = [...text.matchAll(/^(\d+) of (\d+) checks passed/gm)].at(-1);
      resolve({
        name: item.name,
        exit: over ? "stopped: over its time" : code,
        passed: counted ? Number(counted[1]) : null,
        checks: counted ? Number(counted[2]) : null,
        failed: [...text.matchAll(/^FAIL\s+(.*)$/gm)].map((match) => match[1].slice(0, 300)),
        // A scenario that had nothing at hand to check says so ("skip  why"): it is counted apart, never as a pass.
        skipped: text.match(/^skip\s+(.*)$/m)?.[1]?.slice(0, 300) || null,
        font: /own font: arrived/.test(text) ? "arrived" : /own font: not arrived/.test(text) ? "not arrived" : "not said",
        seconds: Math.round((Date.now() - started) / 1000),
        log: path.relative(out, log),
      });
    });
  });
}

async function worker() {
  for (let item = waiting.shift(); item; item = waiting.shift()) {
    const result = await run(item);
    results.set(item.name, result);
    const ok = result.exit === 0 && result.checks !== null && result.passed === result.checks;
    console.log(`${ok ? (result.skipped ? "skip" : "pass") : "FAIL"}  ${item.name}: ${result.skipped && ok ? result.skipped : result.checks === null ? `no count (exit ${result.exit})` : `${result.passed} of ${result.checks}`}, ${result.seconds} s, font ${result.font}`);
    for (const line of result.failed.slice(0, 5)) console.log(`      ${line}`);
  }
}
await Promise.all(Array.from({ length: jobs }, worker));

// ---------------------------------------------------------------- what passed
const list = chosen.map((item) => results.get(item.name));
const good = (result) => result.exit === 0 && result.checks !== null && result.passed === result.checks;
const bad = list.filter((result) => !good(result));
const summary = {
  format: "cells.visualizer.check_all@1",
  revision,
  clean: dirty === "",
  started: new Date(began).toISOString(),
  seconds: Math.round((Date.now() - began) / 1000),
  jobs,
  places: places(),
  scenarios: list,
  passed: list.length - bad.length - list.filter((result) => good(result) && result.skipped).length,
  skipped: list.filter((result) => good(result) && result.skipped).map((result) => result.name),
  failed: bad.map((result) => result.name),
  checks: { passed: list.reduce((sum, result) => sum + (result.passed || 0), 0), of: list.reduce((sum, result) => sum + (result.checks || 0), 0) },
};
await writeFile(path.join(out, "summary.json"), JSON.stringify(summary, null, 1) + "\n");
const minutes = (summary.seconds / 60).toFixed(1);
if (bad.length) console.log(`${bad.length} of ${list.length} scenarios did not pass (${bad.map((result) => result.name).join(", ")}); ${summary.checks.passed} of ${summary.checks.of} checks passed; ${minutes} minutes`);
else if (summary.skipped.length) console.log(`${summary.passed} scenarios passed and ${summary.skipped.length} skipped (${summary.skipped.join(", ")}): ${summary.checks.passed} of ${summary.checks.of} checks; ${minutes} minutes`);
else console.log(`all ${list.length} scenarios passed: ${summary.checks.passed} of ${summary.checks.of} checks; ${minutes} minutes`);
process.exit(bad.length ? 1 : 0);
