#!/usr/bin/env node
// Writes the example run of the assembly view: invented numbers in the form of
// schema/ASSEMBLY_RUN.md, so that the view can be built and shown before Cells' engine has a run
// of an assembly lineage. It is not a run of Cells' engine and not any published study's run, and
// nothing in it is a finding. The page never runs this tool: it reads the file the tool writes.
//
//   node tools/make_assembly_example.mjs            writes data/origin/example-run.json
//   node tools/make_assembly_example.mjs --out -    writes it to standard output
//
// The numbers follow the rules of a GARD assembly as the sources print them (the Plastic
// Heredity preprint, doi:10.5281/zenodo.22143269, CC BY 4.0, its Appendix F; and the open
// papers named in the file's sources):
//   - 100 molecule types; a catalysis table beta_ij = exp(-4 + 4 Z_ij), Z standard normal, the
//     diagonal kept, drawn once for the environment;
//   - a boost b_i = 1 + (beta x)_i / N; a join of type i at rate kf rho_i N b_i and a leave at
//     kb x_i b_i, both with b_i taken at the assembly as it stands (the preprint's single-event form);
//     kf = 1e-2, kb = 1e-4, rho_i = 0.01 held constant;
//   - a start at 40 molecules of 40 types; growth to 80 by one molecule at a time, each chosen in
//     proportion to every rate; then an exact half drawn without replacement goes to the first
//     daughter, and the first daughter carries the lineage on (the preprint's version T2-02).
// What is the tool's own: the seeds, the one table they draw, the number of fissions, and the
// example's analysis (the marks of inheritance at the preprint's strict 0.9, worked out here
// because an example has no analysis of its own; the view reads them as it would read a real
// analysis's). Run twice, it writes the same bytes.

import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const out = args.includes("--out") ? args[args.indexOf("--out") + 1] : path.join(root, "data", "origin", "example-run.json");

const TYPES = 100, KF = 1e-2, KB = 1e-4, RHO = 0.01, START = 40, SIZE = 80, FISSIONS = 120, THRESHOLD = 0.9;
const MATRIX_SEED = 16;
const LINEAGES = [
  { id: "lineage-a", label: "Lineage A", seed: 16 },
  { id: "lineage-b", label: "Lineage B", seed: 23 },
];

function stream(seed) { // mulberry32: small, and the same everywhere
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function normal(r) { let u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function cosine(x, y) { let d = 0, a = 0, b = 0; for (let i = 0; i < x.length; i++) { d += x[i] * y[i]; a += x[i] * x[i]; b += y[i] * y[i]; } return a > 0 && b > 0 ? d / Math.sqrt(a * b) : 0; }
const sparse = (x) => { const out = []; for (let i = 0; i < x.length; i++) if (x[i]) out.push([i, x[i]]); return out; };
const round = (value, digits) => Number(value.toFixed(digits));

// The environment: one table, drawn once and kept for every lineage in it.
const matrixStream = stream(MATRIX_SEED);
const beta = new Float64Array(TYPES * TYPES);
for (let k = 0; k < beta.length; k++) beta[k] = Math.exp(-4 + 4 * normal(matrixStream));

function lineage({ seed }) {
  const r = stream(seed);
  const x = new Int32Array(TYPES), bx = new Float64Array(TYPES);
  const order = Array.from({ length: TYPES }, (_, i) => i);
  for (let k = 0; k < START; k++) { const j = k + Math.floor(r() * (TYPES - k)); [order[k], order[j]] = [order[j], order[k]]; x[order[k]] = 1; }
  let n = START;
  for (let j = 0; j < TYPES; j++) if (x[j]) for (let i = 0; i < TYPES; i++) bx[i] += beta[i * TYPES + j] * x[j];
  const change = (i, d) => { x[i] += d; n += d; for (let k = 0; k < TYPES; k++) bx[k] += d * beta[k * TYPES + i]; };
  const rates = new Float64Array(2 * TYPES);
  const founder = sparse(x);
  const fissions = [], traceCounts = [], trace = [];
  let joined = 0, left = 0, discarded = 0, clock = 0;
  for (let f = 1; f <= FISSIONS; f++) {
    const events = [];
    let guard = 0;
    while (n < SIZE && guard++ < 100000) {
      let total = 0;
      for (let i = 0; i < TYPES; i++) {
        const b = 1 + bx[i] / n;
        rates[i] = KF * RHO * n * b;
        rates[TYPES + i] = KB * x[i] * b;
        total += rates[i] + rates[TYPES + i];
      }
      clock += -Math.log(1 - r()) / total;
      let u = r() * total, pick = 2 * TYPES - 1;
      for (let k = 0; k < 2 * TYPES; k++) { u -= rates[k]; if (u <= 0) { pick = k; break; } }
      const i = pick % TYPES, d = pick < TYPES ? 1 : -1;
      if (d < 0 && (x[i] === 0 || n === 1)) continue; // never an empty assembly in the example
      change(i, d);
      events.push(d > 0 ? i + 1 : -(i + 1));
      if (d > 0) joined++; else left++;
    }
    traceCounts.push(events.length);
    trace.push(...events);
    // The fission: an exact half, drawn without replacement, goes to the first daughter.
    const parent = Int32Array.from(x), bag = [];
    for (let i = 0; i < TYPES; i++) for (let c = 0; c < parent[i]; c++) bag.push(i);
    for (let k = 0; k < bag.length; k++) { const j = k + Math.floor(r() * (bag.length - k)); [bag[k], bag[j]] = [bag[j], bag[k]]; }
    const first = new Int32Array(TYPES), second = new Int32Array(TYPES);
    bag.forEach((type, k) => (k < Math.floor(bag.length / 2) ? first : second)[type]++);
    const h = [cosine(parent, first), cosine(parent, second)];
    discarded += second.reduce((a, b) => a + b, 0);
    fissions.push({ k: f, nominal: round(clock, 4), parent: sparse(parent), first: sparse(first), continues: "first", similarity: h.map((value) => round(value, 6)), totals: { joined, left, discarded }, inherited: h[0] > THRESHOLD });
    // The first daughter carries on.
    x.set(first); n = first.reduce((a, b) => a + b, 0);
    bx.fill(0);
    for (let j = 0; j < TYPES; j++) if (x[j]) for (let i = 0; i < TYPES; i++) bx[i] += beta[i * TYPES + j] * x[j];
  }
  return { founder, fissions, traceCounts, trace };
}

const ids = Array.from({ length: TYPES }, (_, i) => `t${String(i).padStart(3, "0")}`);
const rows = [];
for (let i = 0; i < TYPES; i++) rows.push(Array.from({ length: TYPES }, (_, j) => round(Math.log10(beta[i * TYPES + j]), 2)));

const runs = LINEAGES.map((spec) => {
  const made = lineage(spec);
  return {
    id: spec.id,
    label: spec.label,
    environment: "environment-1",
    mode: "single lineage",
    law: { name: "the preprint's single-event form", form: "single-event", engine_name: null, says: "The catalytic boost is taken at the assembly as it stands, for a join and a leave alike, as the preprint states it (its appendix F)." },
    engine_models: [],
    revision: null,
    rules: { start: "40 molecules of 40 types, drawn uniformly without replacement", events: "one molecule joins or leaves at a time, chosen in proportion to every rate", fission_size: SIZE, split: "an exact half, drawn without replacement, to the first daughter", continues: "the first daughter" },
    founder: made.founder,
    fissions: made.fissions.map(({ inherited, ...fission }) => fission),
    trace: { encoding: "signed type numbers, one for each molecule: +(i + 1) when type i joins, -(i + 1) when it leaves", growths: made.traceCounts, events: Buffer.from(Int8Array.from(made.trace).buffer).toString("base64") },
    analysis: {
      by: "the example tool itself: worked out with the numbers, which are invented, so that the view has an analysis to read",
      inheritance: { compares: "the parent just before a fission with the daughter that carries on", threshold: THRESHOLD, strict: true, says: "Inherited where H is above 0.9; at 0.9 or below, a break (the Plastic Heredity preprint's definition).", marks: made.fissions.map((fission) => fission.inherited) },
      composomes: null,
      composomes_note: "No clustering was run: the example names no composome.",
    },
  };
});

const file = {
  format: "cells.visualizer.assembly_run@1",
  example: { says: "Example: invented numbers · not a run of Cells' engine", made_by: "visualizer/tools/make_assembly_example.mjs" },
  model: { id: "gard", label: "GARD assembly", plain: "A droplet of fat-like molecules that grows by taking molecules in, splits in two, and may pass its mix of molecules to its daughters: the Graded Autocatalysis Replication Domain model." },
  time: { base: "fission", unit: "fission", plural: "fissions", nominal: "The rate constants carry no calibrated unit: the clock counts fissions, and a fission's nominal time is the model's own." },
  environments: [{
    id: "environment-1",
    types: ids,
    catalysis: { says: "beta_ij: how much a molecule of type j in the assembly speeds the joining and the leaving of type i", encoding: "log10, two decimals", rows },
    reservoir: { each: RHO, says: "every type held at the same concentration, never running down" },
    rates: { join: KF, leave: KB },
  }],
  runs,
  sources: {
    preprint: { text: "Plastic heredity: Predicting and steering how inheritance breaks, returns, and persists. Preprint, version 5.0.", doi: "10.5281/zenodo.22143269", licence: "CC BY 4.0", class: "permissive", accessed: "2026-11-16", for: "the rules, the constants and the 0.9 threshold (Appendix F; 'Common experimental framework')" },
    gross2014: { text: "Gross, Fouxon, Lancet and Markovitch (2014) Quasispecies in population of compositional assemblies. BMC Evol Biol 14:265.", doi: "10.1186/s12862-014-0265-1", licence: "CC BY 4.0", class: "permissive", accessed: "2026-11-16", for: "the rate law and single-lineage mode" },
    markovitch2018: { text: "Markovitch and Krasnogor (2018) Predicting species emergence in simulated complex pre-biotic networks. PLOS ONE 13:e0192871.", doi: "10.1371/journal.pone.0192871", licence: "CC BY 4.0", class: "permissive", accessed: "2026-11-16", for: "ln beta normal with mean -4 and standard deviation 4" },
  },
};

const text = JSON.stringify(file) + "\n";
if (out === "-") process.stdout.write(text);
else {
  mkdirSync(path.dirname(out), { recursive: true });
  writeFileSync(out, text);
  console.log(`wrote ${path.relative(process.cwd(), out)}: ${runs.length} runs of ${FISSIONS} fissions, ${Buffer.byteLength(text)} bytes`);
}
