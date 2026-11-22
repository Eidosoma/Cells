#!/usr/bin/env node
// Writes the page to a file.
//
//   node tools/export_page.mjs [--scene PATH] [--runs DIR] [--overlay PATH] [--cards PATH] [--out out/cells-architecture.html] [--standalone] [--inline-runs] [--hide-experiments]
//
// Default: the page as an artifact wants it (content only; the service adds the document
// around it). Replays stay in their own files, which are published beside the page, and so
// do the species' own proteins (schema/SPECIES_PROTEINS.md); the tool prints that list and
// writes it to cells-architecture.files.json. --standalone writes a complete HTML document
// to open straight from disk; it carries all of them inline, because a file opened from
// disk cannot fetch. --inline-runs puts them inline in the artifact page too. --hide-experiments writes the
// page without its Experiments view: the replays stay with it, because the cell view's flux reads a species'
// looping run from them, but no tab, list or address opens the view.
//
// The runs folder (--runs) holds each run's own file and one file a part, as the adapter writes them, and is only read.
// Where an experiment's entry in the overlay (--overlay, data/replays/overlay.json) says `parts_together`, the parts of
// each of its runs are published as one file for the run (as few as stay under 1 MB), which the export writes into a
// folder of its own beside the page: <page's name>.runs/ (lib/build_page.mjs, packageParts; schema/RUN_VIEW.md, "Parts
// published together"). A page with its runs inside it keeps one part a script.
//
// The experiments published are those the Experiments tab's landing lists (--cards, data/replays/cards.json: its `listing`,
// schema/EXPERIMENT_CARDS.md), with the runs the scene names; the cards themselves and the stills they name are published
// beside the page (cards.json, the faces, fetched when the landing first opens; cards.details.json, each card whole, fetched
// the first time a card's detail is asked for; stills/<name>).

import { mkdir, readdir, readFile, rm, writeFile, stat } from "node:fs/promises";
import path from "node:path";
import { buildPage, splitUnitEvidence, proteinFiles, machineFiles, modelFiles, shapeFiles, benchFiles, landingFiles, readReplays, readCards, publishedReplays, packageParts, partsTogether, wrap, ROOT, DEFAULT_SCENE, DEFAULT_RUNS, DEFAULT_OVERLAY, DEFAULT_CARDS } from "./lib/build_page.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const standalone = args.includes("--standalone");
const inlineRuns = standalone || args.includes("--inline-runs");
const runsDir = path.resolve(value("--runs", DEFAULT_RUNS));
const out = path.resolve(value("--out", path.join(ROOT, "out", standalone ? "cells-architecture.standalone.html" : "cells-architecture.html")));
const scenePath = path.resolve(value("--scene", DEFAULT_SCENE));
const hideExperiments = args.includes("--hide-experiments");
const overlayPath = path.resolve(value("--overlay", DEFAULT_OVERLAY));
const cardsPath = path.resolve(value("--cards", DEFAULT_CARDS));
// Only the runs of the experiments the landing lists and the runs the scene names are published (lib/build_page.mjs,
// publishedReplays), their parts packaged as the overlay says (packageParts): the same catalogue goes into the page and names
// the files listed beside it.
const preparedScene = splitUnitEvidence(JSON.parse(await readFile(scenePath, "utf8")));
const scene = preparedScene.scene;
const listed = publishedReplays(await readReplays(runsDir), scene, (await readCards(cardsPath))?.listing);
const packaged = inlineRuns ? { replays: listed, files: [] } : await packageParts(listed, { runsDir, together: partsTogether(JSON.parse(await readFile(overlayPath, "utf8"))) });
const content = await buildPage({ preparedScene, runsDir, inlineRuns, hideExperiments, cardsPath, replays: listed ? packaged.replays : null });
await mkdir(path.dirname(out), { recursive: true });
await writeFile(out, standalone ? wrap(content) : content);
const size = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : `${(bytes / 1024).toFixed(0)} KB`);
console.log(`wrote ${path.relative(process.cwd(), out)} (${size(Buffer.byteLength(content))}${standalone ? ", standalone" : ", artifact content"})`);

// What to publish beside the page: the path the page fetches, and the file on disk.
const files = {};
let bytes = 0;
const beside = async (name, source) => {
  const length = (await stat(source)).size;
  files[name] = path.relative(process.cwd(), source);
  bytes += length;
  console.log(`  beside the page: ${name}  (${size(length)})`);
};
const replays = packaged.replays;
// The files of several parts are written into the export's own folder beside the page, made anew each time; the runs folder is never written.
const own = path.join(path.dirname(out), `${path.basename(out, path.extname(out))}.runs`);
for (const name of await readdir(own).catch(() => [])) if (name.endsWith(".json")) await rm(path.join(own, name), { force: true });
const written = new Map();
if (packaged.files.length) await mkdir(own, { recursive: true });
for (const file of packaged.files) {
  const target = path.join(own, path.basename(file.path));
  await writeFile(target, file.text);
  written.set(file.path, target);
}
if (packaged.files.length) console.log(`wrote ${packaged.files.length} files of several parts of a run into ${path.relative(process.cwd(), own)}/`);
if (!replays) {
  console.log("no replays: the Experiments view is left out (run tools/adapt_run.py to make them)");
} else if (inlineRuns) {
  console.log(`${replays.runs.length} replays are inside the page${hideExperiments ? "; the Experiments view is hidden" : ""}`);
} else {
  if (hideExperiments) console.log("the Experiments view is hidden: its replays stay beside the page for the cell view's flux");
  for (const run of replays.runs) {
    await beside(run.file, path.join(runsDir, path.basename(run.file)));
    // A layer's records come in files of their own beside the replay (schema/QUANTITY_LAYERS.md, rule 10).
    for (const part of run.parts || []) if (!(part.file in files)) await beside(part.file, written.get(part.file) || path.join(runsDir, path.basename(part.file)));
  }
}
// The species' own proteins, for the protein atlas's shelves.
if (!inlineRuns) {
  const assets = path.join(path.dirname(out), path.basename(out, path.extname(out)) + ".assets");
  for (const file of preparedScene.files) {
    const target = path.join(assets, file.path);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, file.text);
    await beside(file.path, target);
  }
}
const proteins = await proteinFiles(scene);
for (const problem of proteins.problems) console.log(`proteins: ${problem}: the atlas is shown without that species' own proteins`);
if (inlineRuns && proteins.files.length) console.log(`${proteins.files.length} files of the species' own proteins are inside the page`);
else for (const file of proteins.files) await beside(file.path, file.source);
// The machines a species' cell can show closer (schema/MACHINES.md), each a file beside the page.
const machines = await machineFiles(scene);
for (const problem of machines.problems) console.log(`machines: ${problem}: that foot is shown without a closer view`);
if (inlineRuns && machines.files.length) console.log(`${machines.files.length} machine files are inside the page`);
else for (const file of machines.files) await beside(file.path, file.source);
// A machine's shape (schema/MACHINE_SHAPES.md), one file a machine, each beside the page at shapes/<species>.<machine>.json.
const shapes = await shapeFiles();
if (!inlineRuns) for (const file of shapes.files) await beside(file.path, file.source);
// Each species' bench of the Machines catalogue, beside the page at catalogue/<species>.json (inside it, for a file on disk).
const benches = await benchFiles();
if (!inlineRuns) for (const file of benches.files) await beside(file.path, file.source);
// The landing's cards and the stills they name, beside the page at cards.json and stills/<name> (inside it, for a file on disk).
if (replays && !hideExperiments) {
  const landing = await landingFiles({ cardsPath });
  for (const problem of landing.problems) console.log(`landing: ${problem}`);
  if (!inlineRuns) for (const file of landing.files) await beside(file.path, file.source);
}
// A model system's run files (schema/MODEL_SYSTEMS.md), each beside the page.
const modelled = await modelFiles(scene);
for (const problem of modelled.problems) console.log(`models: ${problem}`);
if (!inlineRuns) for (const file of modelled.files) await beside(file.path, file.source);
const list = path.join(path.dirname(out), "cells-architecture.files.json");
if (Object.keys(files).length) {
  await writeFile(list, JSON.stringify(files, null, 1) + "\n");
  console.log(`wrote ${path.relative(process.cwd(), list)}: the ${Object.keys(files).length} files to publish with the page (${size(bytes)})`);
} else if (!standalone) {
  await rm(list, { force: true }); // no list left over from an earlier export
}
