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
import { syntheticRun } from "../tests/helpers/synthetic_replay.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const out = path.resolve(args.includes("--out") ? args[args.indexOf("--out") + 1] : path.join(root, "out", "runs-dev"));
const overlay = JSON.parse(await readFile(path.join(root, "data", "replays", "overlay.json"), "utf8"));

await mkdir(out, { recursive: true });
// Three made-up experiments, so the selector and each kind of outcome can be seen:
// judged with the answer no (ten runs, so the run list becomes a chooser), not judged,
// and judged with the answer yes.
const base = overlay.experiments["e07-v1"];
const made = (id, label, outcome) => ({ ...base, id, label: `${label} (synthetic)`, outcome: { ...outcome, text: `Synthetic: ${outcome.text}`, sources: base.sources }, stops: { "planned end": { label: "Ran to its planned end" }, halted: { label: "Stopped early: made up", early: true } } });
const experiments = [
  made("synthetic-renewal", "Renewal", { judged: true, status: "Judged, a made-up date", answer: "no", label: "The disc did not renew", text: "the disc did not renew." }),
  made("synthetic-pilot", "Write and hold", { judged: false, status: "Development runs, not judged", answer: null, text: "development runs with no judged reading." }),
  made("synthetic-check", "A qualification", { judged: true, status: "Judged, a made-up date", answer: "yes", label: "Every item passed", text: "every item of its protocol passed." }),
];
const plan = [
  ...Array.from({ length: 10 }, (_, index) => ({ experiment: "synthetic-renewal", seed: index + 1, erode: index % 2 ? 0.35 : 0, arm: "synthetic-example" })),
  { experiment: "synthetic-pilot", seed: 1, erode: 0, arm: "synthetic-hold" },
  { experiment: "synthetic-pilot", seed: 2, erode: 0.2, arm: "synthetic-hold", stop: "halted" },
  { experiment: "synthetic-check", seed: 1, erode: 0, arm: "synthetic-check" },
];
const entries = [];
for (const { experiment, stop, ...options } of plan) {
  const { file, entry, parts } = syntheticRun(options);
  entry.id = file.view.run.id = `${experiment}--${options.arm}--seed${options.seed}`;
  entry.file = `runs/${entry.id}.json`;
  // The records that come in files of their own, under the run's new name.
  for (const [part, content] of Object.entries(parts)) {
    const name = `${entry.id}.${part}.json`;
    content.run = entry.id;
    file.view.parts.find((item) => item.id === part).file = `runs/${name}`;
    const written = JSON.stringify(content);
    entry.parts.find((item) => item.id === part).file = `runs/${name}`;
    entry.parts.find((item) => item.id === part).bytes = Buffer.byteLength(written);
    await writeFile(path.join(out, name), written);
  }
  entry.experiment = file.view.run.experiment = experiment;
  if (options.erode === 0) file.view.run.class = entry.class = "neutral";
  if (experiment === "synthetic-pilot") {
    delete entry.class; // an experiment that records no class
    delete file.view.run.class;
  }
  if (stop) entry.stop = file.view.run.stop = stop;
  const text = JSON.stringify(file);
  entry.bytes = Buffer.byteLength(text);
  await writeFile(path.join(out, `${entry.id}.json`), text);
  entries.push(entry);
}
await writeFile(path.join(out, "index.json"), JSON.stringify({ format: "cells.visualizer.replay_index@1", experiments, runs: entries }, null, 1));
console.log(`wrote ${entries.length} synthetic runs of ${experiments.length} experiments and index.json in ${path.relative(process.cwd(), out)}`);
