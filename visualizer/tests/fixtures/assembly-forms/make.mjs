#!/usr/bin/env node
// Writes forms.json beside it: a test's own made-up runs, two lineages of one small world that state
// the two forms of the law of catalysis (schema/ASSEMBLY_RUN.md, "The two forms of the law"), so that
// the view's pair of forms can be checked before the engine has run either. They are not runs of
// Cells' engine: the revision and the model they name are a test's, and no page carries this file.
//
//   node tests/fixtures/assembly-forms/make.mjs
//
// Deterministic. A small world (12 types, assemblies of 8 growing to 16, 10 fissions): the
// single-event form takes each molecule's boost at the assembly as it stands, for a join and a leave
// alike; the pair-consistent form leaves the leaving molecule out of its own leave's boost. The
// numbers are made up, and nothing they show is a finding.

import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const TYPES = 12, START = 8, SIZE = 16, FISSIONS = 10, KF = 1e-2, KB = 1e-3, RHO = 0.01;

function stream(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const normal = (r) => { let u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
const cosine = (x, y) => { let d = 0, a = 0, b = 0; for (let i = 0; i < x.length; i++) { d += x[i] * y[i]; a += x[i] * x[i]; b += y[i] * y[i]; } return a > 0 && b > 0 ? d / Math.sqrt(a * b) : 0; };
const sparse = (x) => { const out = []; for (let i = 0; i < x.length; i++) if (x[i]) out.push([i, x[i]]); return out; };
const round = (value, digits) => Number(value.toFixed(digits));

const matrix = stream(5);
const beta = Array.from({ length: TYPES * TYPES }, () => Math.exp(-4 + 4 * normal(matrix)));

function lineage(seed, form) {
  const r = stream(seed);
  const x = new Int32Array(TYPES);
  for (let k = 0; k < START; k++) x[k % TYPES]++;
  const founder = sparse(x);
  const boost = (i, leaving) => {
    let sum = 0, n = 0;
    for (let j = 0; j < TYPES; j++) { const c = x[j] - (leaving && j === i ? 1 : 0); sum += beta[i * TYPES + j] * c; n += c; }
    return 1 + (n > 0 ? sum / n : 0);
  };
  const fissions = [], growths = [], events = [];
  let joined = 0, left = 0, discarded = 0, clock = 0;
  for (let f = 1; f <= FISSIONS; f++) {
    let count = 0;
    while (x.reduce((a, b) => a + b, 0) < SIZE) {
      const n = x.reduce((a, b) => a + b, 0), rates = [];
      for (let i = 0; i < TYPES; i++) rates.push(KF * RHO * n * boost(i, false), x[i] > 0 && n > 1 ? KB * x[i] * boost(i, form === "pair-consistent") : 0);
      const total = rates.reduce((a, b) => a + b, 0);
      clock += -Math.log(1 - r()) / total;
      let u = r() * total, pick = rates.length - 1;
      for (let k = 0; k < rates.length; k++) { u -= rates[k]; if (u <= 0) { pick = k; break; } }
      const i = Math.floor(pick / 2), join = pick % 2 === 0;
      x[i] += join ? 1 : -1;
      events.push(join ? i + 1 : -(i + 1));
      if (join) joined++; else left++;
      count++;
    }
    growths.push(count);
    const parent = Int32Array.from(x), bag = [];
    for (let i = 0; i < TYPES; i++) for (let c = 0; c < parent[i]; c++) bag.push(i);
    for (let k = 0; k < bag.length; k++) { const j = k + Math.floor(r() * (bag.length - k)); [bag[k], bag[j]] = [bag[j], bag[k]]; }
    const first = new Int32Array(TYPES), second = new Int32Array(TYPES);
    bag.forEach((type, k) => (k < bag.length / 2 ? first : second)[type]++);
    discarded += SIZE / 2;
    fissions.push({ k: f, nominal: round(clock, 4), parent: sparse(parent), first: sparse(first), continues: "first", similarity: [round(cosine(parent, first), 6), round(cosine(parent, second), 6)], totals: { joined, left, discarded } });
    x.set(first);
  }
  return { founder, fissions, trace: { encoding: "signed type numbers, one for each molecule: +(i + 1) when type i joins, -(i + 1) when it leaves", growths, events: Buffer.from(Int8Array.from(events).buffer).toString("base64") } };
}

const rules = { start: "8 molecules, the first 8 types once each", events: "one molecule joins or leaves at a time", fission_size: SIZE, split: "an exact half, drawn without replacement, to the first daughter", continues: "the first daughter" };
const run = (id, label, seed, form, says) => {
  const made = lineage(seed, form);
  const marks = made.fissions.map((fission) => fission.similarity[0] > 0.9);
  return {
    id, label, environment: "world-1", world: "fixture world 1", mode: "single lineage",
    law: { name: form === "single-event" ? "the single-event form" : "the pair-consistent form", form, engine_name: null, says },
    engine_models: ["fixture-model"], revision: "fixture0",
    rules, ...made,
    analysis: { by: "the fixture's own maker", inheritance: { compares: "the parent just before a fission with the daughter that carries on", threshold: 0.9, strict: true, says: "Inherited where H is above 0.9.", marks }, composomes: null },
  };
};

const file = {
  format: "cells.visualizer.assembly_run@1",
  about: "A test's own made-up runs (tests/fixtures/assembly-forms/make.mjs): two lineages of one small world that state the two forms of the law, so that the view's pair of forms can be checked. They are not runs of Cells' engine, and no page carries them.",
  model: { id: "gard", label: "GARD assembly", plain: "A test's made-up runs." },
  time: { base: "fission", unit: "fission", plural: "fissions", nominal: "a made-up clock" },
  environments: [{
    id: "world-1",
    types: Array.from({ length: TYPES }, (_, i) => `t${String(i).padStart(3, "0")}`),
    catalysis: { says: "made up", encoding: "log10, two decimals", rows: Array.from({ length: TYPES }, (_, i) => Array.from({ length: TYPES }, (_, j) => round(Math.log10(beta[i * TYPES + j]), 2))) },
    reservoir: { each: RHO, says: "made up" },
    rates: { join: KF, leave: KB },
  }],
  runs: [
    run("single-1", "Run S", 11, "single-event", "Each molecule's boost is taken at the assembly as it stands, for a join and a leave alike."),
    run("pair-1", "Run P", 12, "pair-consistent", "The leaving molecule takes no part in its own leave's boost."),
  ],
  sources: {},
};
writeFileSync(path.join(here, "forms.json"), JSON.stringify(file) + "\n");
console.log("wrote tests/fixtures/assembly-forms/forms.json");
