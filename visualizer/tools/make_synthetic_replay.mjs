#!/usr/bin/env node
// Writes made-up runs in the replay format, so the replay view can be developed and
// checked without any experiment's data. Every label says the data is synthetic.
//
//   node tools/make_synthetic_replay.mjs [--out out/runs-dev]
//
// Then: node tools/serve.mjs --runs out/runs-dev

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { syntheticRun, syntheticIndex } from "../tests/helpers/synthetic_replay.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const out = path.resolve(args.includes("--out") ? args[args.indexOf("--out") + 1] : path.join(root, "out", "runs-dev"));
const overlay = JSON.parse(await readFile(path.join(root, "data", "runs", "overlay.json"), "utf8"));

await mkdir(out, { recursive: true });
const entries = [];
for (const options of [{ seed: 1, erode: 0.35, arm: "synthetic-example-eroding" }, { seed: 2, erode: 0, arm: "synthetic-example-holding" }]) {
  const { file, entry } = syntheticRun(options);
  if (options.erode === 0) {
    file.view.run.class = entry.class = "neutral";
  }
  const text = JSON.stringify(file);
  entry.bytes = Buffer.byteLength(text);
  await writeFile(path.join(out, `${entry.id}.json`), text);
  entries.push(entry);
  console.log(`wrote ${entry.id}.json (${(entry.bytes / 1024).toFixed(0)} KB, ${entry.records} records)`);
}
await writeFile(path.join(out, "index.json"), JSON.stringify(syntheticIndex(overlay.experiments["e07-v1"], entries), null, 1));
console.log(`wrote index.json in ${path.relative(process.cwd(), out)}`);
