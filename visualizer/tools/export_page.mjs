#!/usr/bin/env node
// Writes the page to a file.
//
//   node tools/export_page.mjs [--scene PATH] [--runs DIR] [--out out/cells-architecture.html] [--standalone] [--inline-runs]
//
// Default: the page as an artifact wants it (content only; the service adds the document
// around it). Replays stay in their own files, which are published beside the page; the
// tool prints that list. --standalone writes a complete HTML document to open straight
// from disk; it carries the replays inline, because a file opened from disk cannot fetch.
// --inline-runs puts them inline in the artifact page too.

import { mkdir, writeFile, stat } from "node:fs/promises";
import path from "node:path";
import { buildPage, readReplays, wrap, ROOT, DEFAULT_SCENE, DEFAULT_RUNS } from "./lib/build_page.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const standalone = args.includes("--standalone");
const inlineRuns = standalone || args.includes("--inline-runs");
const runsDir = path.resolve(value("--runs", DEFAULT_RUNS));
const out = path.resolve(value("--out", path.join(ROOT, "out", standalone ? "cells-architecture.standalone.html" : "cells-architecture.html")));
const content = await buildPage({ scenePath: path.resolve(value("--scene", DEFAULT_SCENE)), runsDir, inlineRuns });
await mkdir(path.dirname(out), { recursive: true });
await writeFile(out, standalone ? wrap(content) : content);
const size = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : `${(bytes / 1024).toFixed(0)} KB`);
console.log(`wrote ${path.relative(process.cwd(), out)} (${size(Buffer.byteLength(content))}${standalone ? ", standalone" : ", artifact content"})`);

const replays = await readReplays(runsDir);
if (!replays) {
  console.log("no replays: the Experiments view is left out (run tools/adapt_run.py to make them)");
} else if (inlineRuns) {
  console.log(`${replays.runs.length} replays are inside the page`);
} else {
  // What to publish beside the page: the path the page fetches, and the file on disk.
  const files = {};
  for (const run of replays.runs) {
    const source = path.join(runsDir, path.basename(run.file));
    files[run.file] = path.relative(process.cwd(), source);
    console.log(`  beside the page: ${run.file}  (${size((await stat(source)).size)})`);
  }
  await writeFile(path.join(path.dirname(out), "cells-architecture.files.json"), JSON.stringify(files, null, 1) + "\n");
  console.log(`wrote ${path.relative(process.cwd(), path.join(path.dirname(out), "cells-architecture.files.json"))}: the files to publish with the page`);
}
