#!/usr/bin/env node
// Writes the page to a file.
//
//   node tools/export_page.mjs [--scene PATH] [--runs DIR] [--out out/cells-architecture.html] [--standalone] [--inline-runs] [--hide-experiments]
//
// Default: the page as an artifact wants it (content only; the service adds the document
// around it). Replays stay in their own files, which are published beside the page, and so
// do the species' own proteins (schema/SPECIES_PROTEINS.md); the tool prints that list and
// writes it to cells-architecture.files.json. --standalone writes a complete HTML document
// to open straight from disk; it carries all of them inline, because a file opened from
// disk cannot fetch. --inline-runs puts them inline in the artifact page too. --hide-experiments writes the
// page without its Experiments view: the replays stay with it, because the cell view's flux reads a species'
// looping run from them, but no tab, list or address opens the view.

import { mkdir, readFile, rm, writeFile, stat } from "node:fs/promises";
import path from "node:path";
import { buildPage, proteinFiles, machineFiles, modelFiles, readReplays, publishedReplays, wrap, ROOT, DEFAULT_SCENE, DEFAULT_RUNS } from "./lib/build_page.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const standalone = args.includes("--standalone");
const inlineRuns = standalone || args.includes("--inline-runs");
const runsDir = path.resolve(value("--runs", DEFAULT_RUNS));
const out = path.resolve(value("--out", path.join(ROOT, "out", standalone ? "cells-architecture.standalone.html" : "cells-architecture.html")));
const scenePath = path.resolve(value("--scene", DEFAULT_SCENE));
const hideExperiments = args.includes("--hide-experiments");
const content = await buildPage({ scenePath, runsDir, inlineRuns, published: true, hideExperiments });
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
// Only the listed experiments' runs and the runs the scene names are published (lib/build_page.mjs, publishedReplays).
const replays = publishedReplays(await readReplays(runsDir), JSON.parse(await readFile(scenePath, "utf8")));
if (!replays) {
  console.log("no replays: the Experiments view is left out (run tools/adapt_run.py to make them)");
} else if (inlineRuns) {
  console.log(`${replays.runs.length} replays are inside the page${hideExperiments ? "; the Experiments view is hidden" : ""}`);
} else {
  if (hideExperiments) console.log("the Experiments view is hidden: its replays stay beside the page for the cell view's flux");
  for (const run of replays.runs) {
    await beside(run.file, path.join(runsDir, path.basename(run.file)));
    // A layer's records come in files of their own beside the replay (schema/QUANTITY_LAYERS.md, rule 10).
    for (const part of run.parts || []) await beside(part.file, path.join(runsDir, path.basename(part.file)));
  }
}
// The species' own proteins, for the protein atlas's shelves.
const proteins = await proteinFiles(JSON.parse(await readFile(scenePath, "utf8")));
for (const problem of proteins.problems) console.log(`proteins: ${problem}: the atlas is shown without that species' own proteins`);
if (inlineRuns && proteins.files.length) console.log(`${proteins.files.length} files of the species' own proteins are inside the page`);
else for (const file of proteins.files) await beside(file.path, file.source);
// The machines a species' cell can show closer (schema/MACHINES.md), each a file beside the page.
const machines = await machineFiles(JSON.parse(await readFile(scenePath, "utf8")));
for (const problem of machines.problems) console.log(`machines: ${problem}: that foot is shown without a closer view`);
if (inlineRuns && machines.files.length) console.log(`${machines.files.length} machine files are inside the page`);
else for (const file of machines.files) await beside(file.path, file.source);
// A model system's run files (schema/MODEL_SYSTEMS.md), each beside the page.
const modelled = await modelFiles(JSON.parse(await readFile(scenePath, "utf8")));
for (const problem of modelled.problems) console.log(`models: ${problem}`);
if (!inlineRuns) for (const file of modelled.files) await beside(file.path, file.source);
const list = path.join(path.dirname(out), "cells-architecture.files.json");
if (Object.keys(files).length) {
  await writeFile(list, JSON.stringify(files, null, 1) + "\n");
  console.log(`wrote ${path.relative(process.cwd(), list)}: the ${Object.keys(files).length} files to publish with the page (${size(bytes)})`);
} else if (!standalone) {
  await rm(list, { force: true }); // no list left over from an earlier export
}
