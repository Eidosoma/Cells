// Checks of the replay view that need no browser: a run file is read as the contract
// says (schema/RUN_VIEW.md), the playhead behaves, and the colour ramp reads one way.
//
//   node --test tests/replay.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { syntheticRun, syntheticIndex } from "./helpers/synthetic_replay.mjs";
import { validateReplay, Run } from "../src/replay/run.js";
import { openReplay, loadRun, decodeBase64 } from "../src/replay/source.js";
import { Player, SPEEDS } from "../src/replay/player.js";
import { Catalogue, RUN } from "../src/replay/catalogue.js";
import { Ramp, luminance, parse } from "../src/replay/ramp.js";
import { clock, duration, niceDomain, number, reading } from "../src/replay/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const overlay = JSON.parse(await readFile(path.join(ROOT, "data", "runs", "overlay.json"), "utf8"));
const { file, entry } = syntheticRun();
const copy = () => JSON.parse(JSON.stringify(file));

test("the synthetic run follows the replay format and says it is synthetic", () => {
  assert.deepEqual(validateReplay(file), []);
  assert.match(file.view.derivation[0], /synthetic/i);
  assert.match(file.view.run.label, /synthetic/i);
  assert.match(file.view.run.id, /^[a-z0-9.-]+$/);
  for (const record of file.view.records) assert.equal(record.offset % 4, 0, `${record.id} is not aligned`);
});

test("a run file that breaks the contract is refused with the reason", () => {
  const cases = [
    [(bad) => (bad.format = "something else"), /format is/],
    [(bad) => (bad.view.records[1].offset = 3), /multiple of 4/],
    [(bad) => (bad.view.records[1].shape = [9999, 127]), /past the end|times, the run has/],
    [(bad) => (bad.view.records = bad.view.records.filter((record) => record.id !== "t")), /no record of the times/],
    [(bad) => (bad.view.events[0].at.index = 9999), /unknown set or index/],
    [(bad) => (bad.view.sets[1].geometry.ends[0] = [0, 9999]), /does not exist/],
    [(bad) => delete bad.view.records.find((record) => record.id === "junction_abundance").quantised, /must be marked quantised/],
    [(bad) => (bad.view.derivation = []), /must list its derivation/],
    [(bad) => (bad.view.run.note = "see /home/someone/runs"), /machine path/],
  ];
  for (const [damage, expected] of cases) {
    const bad = copy();
    damage(bad);
    const problems = validateReplay(bad);
    assert.ok(problems.some((problem) => expected.test(problem)), `expected ${expected}, got ${JSON.stringify(problems)}`);
    assert.throws(() => openReplay(bad), /does not follow the replay format/);
  }
  const short = copy();
  short.payload.byte_length += 4;
  assert.throws(() => openReplay(short));
});

test("an opened run gives back what was saved, at the right place and time", () => {
  const run = openReplay(file, entry);
  assert.ok(run instanceof Run);
  assert.equal(run.sets.get("cell").ids.length, 127);
  assert.equal(run.sets.get("junction").ids.length, 342);
  assert.equal(run.events.length, 85);
  assert.equal(run.start, 0);
  assert.equal(run.end, 2340);
  const vm = run.records.get("vm");
  // The payload's own bytes, read independently.
  const bytes = decodeBase64(file.payload.data);
  const direct = new Float32Array(bytes, vm.offset, vm.shape[0] * vm.shape[1]);
  assert.equal(vm.at(7, 30), direct[7 * 127 + 30]);
  const disc = run.regions[0].indices;
  assert.equal(disc.length, 37);
  assert.ok(vm.at(0, disc[0]) > -0.03 && vm.at(0, 0) < -0.07, "the disc starts depolarised and the rest at rest");
  assert.deepEqual(run.recordsOn("cell").map((record) => record.id), ["vm", "generation"]);
});

test("the record shown at a time is the last one saved at or before it, for uneven times", () => {
  const run = openReplay(file, entry);
  assert.equal(run.indexAt(-5), 0);
  assert.equal(run.indexAt(0), 0);
  assert.equal(run.indexAt(9.99), 0);
  assert.equal(run.indexAt(10), 1);
  // An event's own time finds the record taken at it, though times are stored as 32-bit floats.
  const first = run.events[0];
  const at = run.indexAt(first.time);
  assert.ok(Math.abs(run.t[at] - first.time) < 1e-3, `record ${at} is at ${run.t[at]}, the event at ${first.time}`);
  assert.equal(run.indexAt(1e9), run.count - 1);
  for (let k = 1; k < run.count; k++) assert.ok(run.t[k] >= run.t[k - 1], "times are in order");
  assert.equal(run.eventsBy(first.time - 0.01), 0);
  assert.equal(run.eventsBy(first.time), 1);
  assert.equal(run.eventsBy(1e9), 85);
  assert.equal(run.eventsBetween(first.time - 1, first.time).length, 1);
  const slot = first.at.index;
  assert.ok(run.eventsOf("cell", slot).some((event) => event === first));
  assert.equal(run.t[run.indexFrom(2020)], 2020);
});

test("a quantised record is drawn but never printed, and an invalid record is flagged", () => {
  const run = openReplay(file, entry);
  const formed = run.records.get("junction_abundance");
  assert.equal(formed.quantised, true);
  assert.ok(formed.at(0, 0) > 0.99 && formed.at(0, 0) <= 1);
  assert.equal(formed.text(0, 0), null);
  assert.equal(reading({ unit: "1", quantised: true }, 0.4), null);
  assert.equal(run.records.get("vm").text(0, 0).endsWith(" mV"), true);

  const flagged = openReplay(syntheticRun({ invalidFrom: 2000 }).file);
  assert.equal(flagged.isValid(0), true);
  assert.equal(flagged.isValid(flagged.indexAt(2100)), false);
  const plain = copy();
  plain.view.records = plain.view.records.filter((record) => record.id !== "valid");
  assert.equal(openReplay(plain).isValid(5), true, "a run that saves no flag has only valid records");
});

test("a run is found inline in the page first, then fetched from beside it", async () => {
  const text = JSON.stringify(file);
  const page = { querySelector: (selector) => (selector.includes(`data-replay="${entry.id}"`) ? { textContent: text } : null) };
  const inline = await loadRun(entry, { root: page, fetcher: () => assert.fail("an inline run must not be fetched") });
  assert.equal(inline.id, entry.id);

  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    return { ok: true, json: async () => JSON.parse(text) };
  };
  const fetched = await loadRun(entry, { root: { querySelector: () => null }, fetcher });
  assert.deepEqual(asked, [entry.file]);
  assert.equal(fetched.count, inline.count);

  await assert.rejects(loadRun(entry, { root: null, fetcher: async () => ({ ok: false, status: 404 }) }), /404/);
  await assert.rejects(loadRun({ ...entry, id: "e07-v1--another--seed9" }, { root: null, fetcher }), /holds run/);
});

test("the playhead plays at its speed, stops at the end and steps by saved records", () => {
  const run = openReplay(file, entry);
  const player = new Player();
  const heard = [];
  player.addEventListener("time", () => heard.push("time"));
  player.addEventListener("state", () => heard.push("state"));
  player.load(run);
  assert.equal(player.time, 0);
  assert.equal(player.tick(1000), false, "paused: no movement");
  player.play();
  assert.equal(player.tick(500), true);
  assert.equal(player.time, 30);
  assert.equal(player.index, run.indexAt(30));
  player.setSpeed(SPEEDS[2]);
  player.tick(1000);
  assert.equal(player.time, 30 + SPEEDS[2]);
  player.seek(1e9);
  assert.equal(player.time, run.end);
  assert.equal(player.tick(1000), false);
  assert.equal(player.playing, false, "it stops at the end");
  player.play();
  assert.equal(player.time, run.start, "playing from the end starts over");
  player.pause();
  player.seek(12);
  player.step(1);
  assert.ok(Math.abs(player.time - run.events[0].time) < 1e-3, "one step forward lands on the next saved record");
  player.step(-1);
  assert.equal(player.time, 10);
  player.seek(-50);
  assert.equal(player.time, 0);
  assert.ok(heard.includes("time") && heard.includes("state"));
});

test("the ramp is one hue that reads in one direction, in both themes", () => {
  const light = new Ramp(["#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]);
  const dark = new Ramp(["#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#b7d3f6"]);
  for (const [ramp, direction] of [[light, -1], [dark, 1]]) {
    let last = luminance(ramp.at(0));
    for (let k = 1; k <= 20; k++) {
      const next = luminance(ramp.at(k / 20));
      assert.ok((next - last) * direction > 0, "lightness changes one way along the ramp");
      last = next;
    }
    assert.deepEqual(ramp.at(0), parse(ramp.hex[0]));
    assert.deepEqual(ramp.at(1), parse(ramp.hex[4]));
    assert.deepEqual(ramp.at(NaN), parse(ramp.hex[0]));
    assert.match(ramp.css(), /^linear-gradient\(to right, #/);
  }
  // The page's tokens are these same stops.
  return readFile(path.join(ROOT, "src", "page.css"), "utf8").then((css) => {
    assert.equal(css.match(/--seq-0: #6da7ec; --seq-1: #3987e5; --seq-2: #256abf; --seq-3: #184f95; --seq-4: #0d366b;/g)?.length, 1);
    assert.equal(css.match(/--seq-0: #1c5cab; --seq-1: #2a78d6; --seq-2: #5598e7; --seq-3: #86b6ef; --seq-4: #b7d3f6;/g)?.length, 2);
  });
});

test("times and values are written in plain units", () => {
  assert.equal(clock(13.785, { precise: true }), "13.8 s");
  assert.equal(clock(750), "12 min 30 s");
  assert.equal(clock(2340), "39 min");
  assert.equal(clock(3900), "1 h 5 min");
  assert.equal(duration(2340), "39 min");
  assert.equal(number(-21.74, 1), "−21.7");
  assert.equal(number(-0.01, 1), "0.0");
  assert.equal(reading({ unit: "V", dtype: "float32" }, -0.0217), "−21.7 mV");
  assert.deepEqual(niceDomain(-78.7, -18.5), { low: -80, high: -10, step: 10 });
  assert.deepEqual(niceDomain(0, 3), { low: 0, high: 3, step: 0.5 });
});

test("the catalogue describes a run in the experiment's own words and judges nothing", () => {
  const index = syntheticIndex(overlay.experiments["e07-v1"], [entry]);
  const catalogue = new Catalogue(index);
  assert.equal(catalogue.sections().length, 1);
  const before = catalogue.describe(RUN + entry.id);
  assert.equal(before.id, RUN + entry.id);
  assert.ok(before.chips.some((chip) => chip.label === "Recorded class: Erosion"));
  assert.match(before.note, /experiment's own summary/);
  assert.deepEqual(before.related[0].ids, overlay.experiments["e07-v1"].engine_entities);
  assert.equal(before.sections.length, 0, "before the file is in, only the catalogue's facts");

  const after = catalogue.describe(RUN + entry.id, openReplay(file, entry));
  const facts = Object.fromEntries(after.facts);
  assert.equal(facts["Disc size"], "37 cells");
  assert.equal(facts["Residence time R"], "1020 s (17 min)");
  const readouts = after.sections.find((section) => section.title === "What the run recorded").items;
  const supplementary = readouts.find((item) => item.label === "ΔJ over the records, mean");
  assert.equal(supplementary.tag, "Supplementary");
  assert.match(supplementary.note, /not judged/);
  assert.equal(readouts.find((item) => item.label === "ΔJ").tag, null);
  assert.match(after.disclosures[0].lines[0], /synthetic/i);

  // A value the run did not record is said to be missing, never shown as zero.
  const missing = copy();
  missing.view.run.readouts.push({ id: "recruitment_fraction", value: null, supplementary: false, status: null });
  const told = catalogue.describe(RUN + entry.id, openReplay(missing, entry)).sections[0].items.find((item) => item.label === "Recruitment fraction");
  assert.equal(told.detail, "none recorded");
  assert.equal(catalogue.describe("run:no-such-run"), null);
});

// The adapter's real output, when it is on this machine: the loader must take it as it is.
const adapted = path.join(ROOT, "out", "runs-adapter");
test("adapted runs, when present, are read by the loader", { skip: !existsSync(path.join(adapted, "index.json")) }, async () => {
  const index = JSON.parse(await readFile(path.join(adapted, "index.json"), "utf8"));
  assert.equal(index.format, "cells.visualizer.replay_index@1");
  assert.ok(index.runs.length > 0);
  const catalogue = new Catalogue(index);
  for (const item of index.runs) {
    const text = await readFile(path.join(adapted, path.basename(item.file)), "utf8");
    assert.ok(Buffer.byteLength(text) < 1024 * 1024, `${item.id} is over 1 MB`);
    const data = JSON.parse(text);
    assert.deepEqual(validateReplay(data), [], item.id);
    const run = openReplay(data, item);
    assert.equal(run.id, item.id);
    assert.equal(run.count, item.records);
    assert.ok(run.recordsOn("cell").some((record) => record.id === "vm" && !record.quantised));
    assert.ok(catalogue.describe(RUN + item.id, run).facts.length > 4);
    for (const event of run.events) {
      const k = run.indexAt(event.time);
      assert.ok(Math.abs(run.t[k] - event.time) < 1e-3, `no record at the event of ${event.time} s`);
    }
  }
});
