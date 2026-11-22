#!/usr/bin/env node
// Runs every real-click check once, several at a time, and says what passed: the check that
// stands before a publish, as one command.
//
//   node tools/check_all.mjs [--out DIR] [--jobs N] [--only PATTERN] [--limit MINUTES] [--list] [--suite FILE]
//
// Each scenario is one run of one of the check tools, with its own browser. A run takes
// a place of the browser lock (tools/lib/browser_lock.mjs), so as many run at once as there
// are places (four on the project's machine: one core each), and --jobs asks for fewer.
// The longest scenarios start first. A scenario marked `alone` holds a time bound (what a frame
// costs): it runs after all the others, with no other browser beside it, because measured beside
// three other browsers a frame's cost says more of them than of the page (on 19 November 2026 the
// shelves' frame check missed its bound in two of three whole runs and passed each time it ran alone).
// Every other check that holds a time is a measure (tools/lib/measures.mjs): its value, unit and bound are written in the
// scenario's log and gathered here into the summary. Beside others (CELLS_MEASURES=beside, set here while several
// scenarios run at once) a scenario whose measures all stand within their bounds has had them held there, under load;
// one that passes every check but has a measure over its bound is not judged there: it is sent to the alone phase and
// run again, and there a measure over its bound fails as a check does. The summary names the scenarios sent there and
// gives each measure's value both times. A scenario that fails a check beside others stays failed and is not run again.
// --only runs the scenarios whose names match a regular
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
//
// --suite FILE runs the scenarios a JSON file lists instead of these (each `{ name, tool, args, env, minutes, alone }`,
// its tool a path of its own): the runner's own test (tests/check_all_measures.test.mjs) holds its rules so, on made-up
// scenarios, with no page built.

import { spawn, execFileSync } from "node:child_process";
import { createWriteStream, readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, DEFAULT_RUNS, ROOT } from "./lib/build_page.mjs";
import { BROWSER_CPUS, places } from "./lib/browser_lock.mjs";
import { changedLines } from "./lib/git_state.mjs";
import { measuresIn } from "./lib/measures.mjs";

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
  // A species' life stages in the Scope view, on a check-only scene with a made-up species (tools/check_stages.mjs): a wide
  // window (60 to 90 s on one core) and a phone (60 to 90 s). The wide one is 1280 by 720, the tighter of the two wide sizes
  // (the strip ran under the look's note there and not at 1440 by 900). The other sizes stay runnable by hand: CASE=wide or CASE=360.
  { name: "stages-wide", tool: "check_stages.mjs", args: [pictures], env: { CASE: "720", NAME: "stages-wide" }, minutes: 2 },
  { name: "stages-phone", tool: "check_stages.mjs", args: [pictures], env: { CASE: "phone" }, minutes: 2 },
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
  // The example's tumour tissue (the line and the sheet) on its real runs (tools/check_tissue.mjs), skipped where they are not on this machine.
  { name: "tissue-wide", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "wide", NAME: "tissue-wide" }, minutes: 3 },
  { name: "tissue-phone", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "phone", NAME: "tissue-phone" }, minutes: 2 },
  { name: "tissue-reduced", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "reduced", NAME: "tissue-reduced" }, minutes: 2 },
  { name: "tissue-play", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "play", NAME: "tissue-play" }, minutes: 4 }, // the play of the stated changes, watched whole
  { name: "tissue-sheet", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "sheet", NAME: "tissue-sheet" }, minutes: 3 }, // the switch turned to the sheet, in the check's own catalogue
  { name: "tissue-layout", tool: "check_tissue.mjs", args: [pictures], env: { CASE: "layout", NAME: "tissue-layout" }, minutes: 6 }, // no name meets another or lies on a cell, at five sizes in every state a press reaches
  // What each address of the exported page fetches beside it, cold, held to the budgets of tools/references/fetches.json (tools/check_fetches.mjs).
  // The export publishes what the landing's cards list, every experiment with a card: the case "with every experiment listed" (fetches-all) is this one since 18 November 2026.
  { name: "fetches", tool: "check_fetches.mjs", args: [pictures], env: { CASE: "listed", NAME: "fetches" }, minutes: 4 },
  // The Experiments tab's landing (tools/check_landing.mjs): at 1440 by 900, 1280 by 720, 400 by 860 and 360 by 780, each in both themes, and its cards' file held back, refused and given on "Try again".
  { name: "landing-wide", tool: "check_landing.mjs", args: [pictures], env: { CASE: "wide", NAME: "landing-wide" }, minutes: 4 },
  { name: "landing-720", tool: "check_landing.mjs", args: [pictures], env: { CASE: "720", NAME: "landing-720" }, minutes: 4 },
  { name: "landing-phone", tool: "check_landing.mjs", args: [pictures], env: { CASE: "phone", NAME: "landing-phone" }, minutes: 4 },
  { name: "landing-narrow", tool: "check_landing.mjs", args: [pictures], env: { CASE: "narrow", NAME: "landing-narrow" }, minutes: 4 },
  { name: "landing-retry", tool: "check_landing.mjs", args: [pictures], env: { CASE: "retry", NAME: "landing-retry" }, minutes: 1 },
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
  { name: "laws-atlas", tool: "check_laws.mjs", args: [pictures], env: { CASE: "atlas" }, minutes: 1 },
  { name: "laws-atlas-phone", tool: "check_laws.mjs", args: [pictures], env: { CASE: "atlas-phone", THEME: "dark" }, minutes: 1 },
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
  // The human's bench from its dossier, and the way from a chain to its protein in the atlas and back (wide and on a phone).
  { name: "catalogue-human", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "human", NAME: "catalogue-human" }, minutes: 2 },
  { name: "catalogue-human-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "human", NAME: "catalogue-human-phone", WIDTH: "390", HEIGHT: "844" }, minutes: 2 },
  // The Shape level on E. coli's machines: wide, at 1280 by 720 in the dark, and on phones of 400 and 360 px.
  { name: "catalogue-shape", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shape", NAME: "catalogue-shape", WIDTH: "1440", HEIGHT: "900" }, minutes: 2 },
  { name: "catalogue-shape-720", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shape", NAME: "catalogue-shape-720", WIDTH: "1280", HEIGHT: "720", THEME: "dark" }, minutes: 2 },
  { name: "catalogue-shape-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shape", NAME: "catalogue-shape-phone", WIDTH: "400", HEIGHT: "844" }, minutes: 2 },
  { name: "catalogue-shape-360", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shape", NAME: "catalogue-shape-360", WIDTH: "360", HEIGHT: "780", THEME: "dark" }, minutes: 2 },
  { name: "catalogue-vault", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "vault", NAME: "catalogue-vault", WIDTH: "1440", HEIGHT: "900" }, minutes: 4 },
  { name: "catalogue-vault-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "vault", NAME: "catalogue-vault-phone", WIDTH: "400", HEIGHT: "844" }, minutes: 4 },
  { name: "catalogue-human-720", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "human", NAME: "catalogue-human-720", WIDTH: "1280", HEIGHT: "720" }, minutes: 2 },
  // The benches read beside the page (the planarian's by family, the thale cress's with its machines of light, one that cannot be read).
  { name: "catalogue-benches", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "benches", NAME: "catalogue-benches", WIDTH: "1440", HEIGHT: "900" }, minutes: 3 },
  { name: "catalogue-benches-720", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "benches", NAME: "catalogue-benches-720", WIDTH: "1280", HEIGHT: "720", THEME: "dark" }, minutes: 3 },
  { name: "catalogue-benches-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "benches", NAME: "catalogue-benches-phone", WIDTH: "400", HEIGHT: "844" }, minutes: 3 },
  { name: "catalogue-benches-360", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "benches", NAME: "catalogue-benches-360", WIDTH: "360", HEIGHT: "780", THEME: "dark" }, minutes: 3 },
  // The shelf of organelles behind the human's bench and the scale rail between them (wide, at 1280 by 720, and on phones of 390 and 360 px).
  { name: "catalogue-shelf", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shelf", NAME: "catalogue-shelf", WIDTH: "1440", HEIGHT: "900" }, minutes: 3 },
  { name: "catalogue-shelf-720", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shelf", NAME: "catalogue-shelf-720", WIDTH: "1280", HEIGHT: "720" }, minutes: 3 },
  { name: "catalogue-shelf-phone", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shelf", NAME: "catalogue-shelf-phone", WIDTH: "390", HEIGHT: "844" }, minutes: 3 },
  { name: "catalogue-shelf-360", tool: "check_catalogue.mjs", args: [pictures], env: { CASE: "shelf", NAME: "catalogue-shelf-360", WIDTH: "360", HEIGHT: "780" }, minutes: 3 },
  flux("phone", { WIDTH: "400", HEIGHT: "780" }, 2),
  flux("address", { ADDRESS: "1" }, 2),
  flux("loop", { LOOP: "1", MOVING: "1" }, 3), // the planarian's own looping run: it needs the run among the replays served (out/runs)
  { name: "shelves-planarian", tool: "check_shelves.mjs", args: ["planarian"], minutes: 2 },
  // The planarian's members filed by what its own scan added (19 November 2026): each says so, with the databases behind it.
  { name: "shelves-scan", tool: "check_shelves.mjs", args: ["scan"], minutes: 2 },
  { name: "layers-closeup", tool: "check_layers.mjs", args: ["closeup"], env: { RUN: SHEET }, minutes: 2 },
  { name: "shelves-syn3a", tool: "check_shelves.mjs", args: ["syn3a"], minutes: 1 },
  { name: "shelves-nofiles", tool: "check_shelves.mjs", args: ["nofiles"], minutes: 1 },
  { name: "shelves-ecoli", tool: "check_shelves.mjs", args: ["ecoli"], minutes: 1 },
  { name: "shelves-stack-thalecress", tool: "check_shelves.mjs", args: ["stack"], env: { SPECIES: "thalecress" }, minutes: 1 },
  { name: "shelves-stack-mouse", tool: "check_shelves.mjs", args: ["stack"], env: { SPECIES: "mouse" }, minutes: 1 },
  { name: "shelves-accessory-mouse", tool: "check_shelves.mjs", args: ["accessory"], env: { SPECIES: "mouse" }, minutes: 1 },
  // The frog (19 November 2026): its stack of six shelves, and a reviewed entry found by the twin of its gene that is not shown.
  { name: "shelves-stack-xenopus", tool: "check_shelves.mjs", args: ["stack"], env: { SPECIES: "xenopus" }, minutes: 1 },
  { name: "shelves-twins", tool: "check_shelves.mjs", args: ["twins"], env: { SPECIES: "xenopus" }, minutes: 2 },
  { name: "shelves-trail", tool: "check_shelves.mjs", args: ["trail"], minutes: 2 },
  { name: "shelves-search", tool: "check_shelves.mjs", args: ["search"], minutes: 2 },
  { name: "shelves-map", tool: "check_shelves.mjs", args: ["map"], env: { SPECIES: "thalecress" }, minutes: 1 },
  { name: "shelves-colours", tool: "check_shelves.mjs", args: ["colours"], minutes: 1 },
  { name: "shelves-gathering", tool: "check_shelves.mjs", args: ["gathering"], minutes: 1 },
  { name: "shelves-frame", tool: "check_shelves.mjs", args: ["frame"], minutes: 2, alone: true },
  { name: "shelves-accessory-human", tool: "check_shelves.mjs", args: ["accessory"], env: { SPECIES: "human" }, minutes: 2 },
  { name: "shelves-doors", tool: "check_shelves.mjs", args: ["doors"], minutes: 2 },
  { name: "layers-zero", tool: "check_layers.mjs", args: ["zero"], env: { RUN: SHEET }, minutes: 1 },
  { name: "layers-switch", tool: "check_layers.mjs", args: ["switch"], env: { RUN: SHEET }, minutes: 1 },
  { name: "layers-flow", tool: "check_layers.mjs", args: ["flow", DEFAULT_RUNS, pictures], env: { RUN: DEV, REFERENCE: path.join(ROOT, "tools", "references", "secreted-species-dev-run-0.4.json") }, minutes: 1 },
  { name: "layers-example", tool: "check_layers.mjs", args: ["example", DEFAULT_RUNS, pictures], env: { RUN: EXAMPLE }, minutes: 1 },
];

const MADE = value("--suite") ? JSON.parse(readFileSync(path.resolve(value("--suite")), "utf8")) : null;
const only = value("--only") ? new RegExp(value("--only")) : null;
const chosen = (MADE || SUITE).filter((item) => !only || only.test(item.name));
if (args.includes("--list")) {
  for (const item of chosen) console.log(`${item.name}${item.alone ? "  [alone, after the others]" : ""}  (${item.tool}${item.args?.length ? " " + item.args.map((word) => path.relative(ROOT, word) || word).join(" ") : ""}${Object.keys(item.env || {}).length ? "; " + Object.entries(item.env).map(([key, word]) => `${key}=${word}`).join(" ") : ""})`);
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
// What is uncommitted, less an untracked node_modules link (tools/lib/git_state.mjs): "" for a clean tree, null where git gave nothing.
const revision = git("rev-parse", "--short=8", "HEAD"), dirty = changedLines(git("status", "--porcelain", "--", "."))?.join("\n") ?? null;
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
if (!MADE) await buildPage({});
const slots = places().length;
const jobs = Math.max(1, Math.min(Number(value("--jobs", slots)) || slots, slots));
console.log(`${chosen.length} scenarios on ${revision ?? "an unknown revision"}${dirty ? " (with uncommitted changes)" : ""}, ${jobs} at a time; logs in ${path.relative(process.cwd(), out) || "."}`);

// ---------------------------------------------------------------- the scenarios, a few at a time
const began = Date.now();
const results = new Map();
const waiting = chosen.filter((item) => !item.alone).sort((a, b) => (b.minutes || 1) - (a.minutes || 1));
// Those that hold a time bound, for after the others (the head of this file says why).
const apart = chosen.filter((item) => item.alone);
// Beside others: while more than one scenario runs at once. A measure over its bound there sends its scenario to the alone
// phase (the head of this file says why); alone, after the others, or with one scenario at a time, every bound is held.
const BESIDE = jobs > 1 && waiting.length > 1;

function run(item, attempt = 1) {
  return new Promise((resolve) => {
    // A scenario run again alone keeps the log of its run beside others.
    const log = path.join(out, `${item.name}${item.sent ? ".alone" : ""}.log`);
    const stream = createWriteStream(log);
    const started = Date.now();
    // In a group of its own, so that a scenario over its time is stopped with the Chrome it started.
    const env = { ...process.env, ...(item.env || {}) };
    delete env.CELLS_MEASURES; // set only here, never left over from the shell
    if (BESIDE && !item.alone && !item.sent) env.CELLS_MEASURES = "beside";
    const child = spawn(process.execPath, [path.resolve(ROOT, "tools", item.tool), ...(item.args || [])], { cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"], detached: true });
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
        beside: env.CELLS_MEASURES === "beside",
        // Each bound on time the scenario held (tools/lib/measures.mjs): its value, unit and bound, and whether it stood within.
        measures: measuresIn(text),
      });
    });
  });
}

/** A measure as the summary says it: its value, unit and bound, and whether it stood within. */
const said = (one) => `${one.name}: ${one.value} ${one.unit} (${one.op === "<=" ? "at most" : "under"} ${one.bound})`;
/** A scenario's measures beside others and alone, paired by name and by their order under one name. */
function bothTimes(first, again) {
  const seen = new Map();
  const key = (one) => {
    const n = seen.get(one.name) || 0;
    seen.set(one.name, n + 1);
    return `${one.name}\u0000${n}`;
  };
  const alone = new Map(again.map((one) => [key(one), one]));
  seen.clear();
  return first.map((one) => {
    const other = alone.get(key(one));
    return { name: one.name, unit: one.unit, bound: one.bound, op: one.op, beside: one.value, alone: other ? other.value : null, within_beside: one.within, within_alone: other ? other.within : false };
  });
}

async function worker() {
  for (let item = waiting.shift(); item; item = waiting.shift()) {
    let result = await run(item);
    const ok = result.exit === 0 && result.checks !== null && result.passed === result.checks;
    // Every check held beside others but a measure over its bound: judged again alone, after the others.
    const over = result.measures.filter((one) => one.deferred);
    if (result.beside && ok && over.length) {
      apart.push({ ...item, sent: result });
      console.log(`again ${item.name}: ${over.length === 1 ? "a measure" : `${over.length} measures`} over ${over.length === 1 ? "its bound" : "their bounds"} beside others (${over.map(said).join("; ")}), ${result.seconds} s; run again alone, after the others`);
      continue;
    }
    if (item.sent) result = { ...result, sent_alone: true, beside_run: { seconds: item.sent.seconds, log: item.sent.log }, both: bothTimes(item.sent.measures, result.measures) };
    results.set(item.name, result);
    console.log(`${ok ? (result.skipped ? "skip" : "pass") : "FAIL"}  ${item.name}${item.sent ? " (run again alone)" : ""}: ${result.skipped && ok ? result.skipped : result.checks === null ? `no count (exit ${result.exit})` : `${result.passed} of ${result.checks}`}, ${result.seconds} s, font ${result.font}`);
    for (const line of result.failed.slice(0, 5)) console.log(`      ${line}`);
    if (item.sent) for (const one of result.both) console.log(`      ${one.name}: ${one.beside} ${one.unit} beside others, ${one.alone ?? "not measured"} ${one.alone === null ? "" : `${one.unit} `}alone (${one.op === "<=" ? "at most" : "under"} ${one.bound})`);
  }
}
await Promise.all(Array.from({ length: jobs }, worker));
if (apart.length) {
  const sent = apart.filter((item) => item.sent).map((item) => item.name);
  console.log(`${apart.length === 1 ? "one scenario runs" : `${apart.length} scenarios run`} alone, after the others: ${apart.map((item) => item.name).join(", ")}${sent.length ? ` (sent there by a measure over its bound beside others: ${sent.join(", ")})` : ""}`);
  waiting.push(...apart);
  await worker();
}

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
  alone: apart.map((item) => item.name),
  // The scenarios a measure over its bound beside others sent to the alone phase: each measure's value both times, and the result alone.
  sent_alone: list.filter((result) => result.sent_alone).map((result) => ({ name: result.name, passed: good(result), measures: result.both })),
  checks: { passed: list.reduce((sum, result) => sum + (result.passed || 0), 0), of: list.reduce((sum, result) => sum + (result.checks || 0), 0) },
};
await writeFile(path.join(out, "summary.json"), JSON.stringify(summary, null, 1) + "\n");
const minutes = (summary.seconds / 60).toFixed(1);
if (bad.length) console.log(`${bad.length} of ${list.length} scenarios did not pass (${bad.map((result) => result.name).join(", ")}); ${summary.checks.passed} of ${summary.checks.of} checks passed; ${minutes} minutes`);
else if (summary.skipped.length) console.log(`${summary.passed} scenarios passed and ${summary.skipped.length} skipped (${summary.skipped.join(", ")}): ${summary.checks.passed} of ${summary.checks.of} checks; ${minutes} minutes`);
else console.log(`all ${list.length} scenarios passed: ${summary.checks.passed} of ${summary.checks.of} checks; ${minutes} minutes`);
process.exit(bad.length ? 1 : 0);
