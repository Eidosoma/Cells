// The life stages of a species on one strip (src/scene/life_stages.js, schema/SPECIES_STAGES.md), on made-up
// species only. It makes no world and starts no browser.
//
//   - every species file of the repository has no stages and is given back exactly as it is;
//   - a sound block is read; each breach refuses it with its own code, and the species is then read as if it had none;
//   - a species read through a stage takes the stage's own values and nothing else, as a file gives it and as the
//     scene carries it (its own cell type made again from the stage, so the file's cell never stands in for it);
//   - the strip stands evenly by order, a stated time written on its mark and never used to place it;
//   - the viewer's own plain change runs from one drawn stage to the next, passing named ones, and a made-up run's
//     records fill a span: both load into the Experiments tab's own Player, alone and in order;
//   - the address's `stage=`, to and from its text;
//   - the build reads the block through this same reader (tools/lib/species.py, through node), and says plainly where it
//     cannot. That one test starts four Python processes (one only to find the interpreter) and four node calls, about
//     half a second; the others take a fraction of a second together.
//
//   node --test tests/life_stages.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Player, SPEEDS, openingSpeed } from "../src/replay/player.js";
import { cellTypeOf, cellTypesOf } from "../src/scene/entries.js";
import {
  readStages, stageProblems, hasStages, speciesAt, fileOf, stripOf, elapsedBetween, passagesOf, illustration, recordsPlayer,
  journeyOf, levelFor, openingStage, stageFromAddress, stageToAddress, writeStage, FILL_KINDS, FILL_WORDS, ILLUSTRATION_SECONDS, HOLD, PACES,
} from "../src/scene/life_stages.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const copy = (value) => JSON.parse(JSON.stringify(value));
const freeze = (value) => {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const item of Object.values(value)) freeze(item);
  }
  return value;
};
const codes = (species) => stageProblems(species).map((item) => item.code);

// A made-up animal whose file describes its adult, with an egg drawn over it and two stages named and not drawn
// between: drawn, named, named, drawn. Every name, number and source is made up.
const DEWKIN = {
  format: "cells.visualizer.species@1",
  id: "dewkin",
  label: "Dewkin",
  organism: "Rorida exemplaris",
  plain: "A made-up animal, to show that life stages are read from files alone.",
  group: "Animals",
  order: 90,
  default: false,
  made: "2026-11-19",
  modelled: { state: "generic", text: "A made-up species for a test: Cells models a generic cell and a sheet of such cells, not this animal." },
  levels: [
    { id: "molecules" },
    { id: "cell", shape: { kind: "prism", sides: 6, radius_um: 10.6, height_um: 13 }, note: "A made-up cell; its shape is the picture's choice." },
    { id: "tissue", shape: { kind: "cell sheet", rings: 3 }, note: "A made-up sheet." },
    { id: "organ", shape: { kind: "outline", ref: "dewkin", parts: ["fin"] }, note: "A made-up fin.", sources: ["made"] },
    { id: "organism", shape: { kind: "outline", ref: "dewkin" }, note: "A made-up adult, 40 mm long.", sources: ["made"] },
  ],
  cell: {
    facts: [{ label: "Outline", value: "40 mm long (made up)", sources: ["made"] }],
    parts: { membranes: 1, wall: false, nucleus: true },
    capabilities: { "cap.channels": { place: "present", note: "A made-up note." } },
  },
  stages: {
    system: { id: "ds", label: "Dewkin stage", short: "DS", sources: ["made"] },
    times_after: "fertilisation",
    list: [
      {
        id: "egg", order: 1, index: "1", label: "Egg",
        plain: "The made-up egg, before its first division.",
        ends_at: "cell",
        no_further_levels: "An egg is one cell: it has no tissue, organ or body yet.",
        levels: [{ id: "cell", label: "The egg", shape: { kind: "sphere", across_um: 900 }, note: "A made-up egg, 900 µm across.", sources: ["made"] }],
        cell: {
          facts: [{ label: "Diameter", value: "900 µm (made up)", sources: ["made"] }],
          capabilities: { "cap.junctions": { place: "absent", why: "One cell has no neighbour." } },
        },
      },
      { id: "two-cell", order: 2, index: "2", label: "Two cells", time: { value: 80, unit: "min", about: true, temperature_c: 20, sources: ["made"], where: "a made-up table, row 2" }, missing: "No size of the two-cell form is in hand under usable terms." },
      { id: "larva", order: 3, index: "30-31", label: "Larva", time: { value: 3, unit: "d", temperature_c: 20, sources: ["made"], where: "a made-up table, row 30" }, missing: "No length of the larva is in hand under usable terms." },
      { id: "adult", order: 4, label: "Adult", own: true },
    ],
    spans: [],
  },
  sources: {
    made: { text: "Made up for the life stages' tests.", url: "https://example.org/made-up", licence: "CC BY 4.0", class: "permissive", accessed: "2026-11-19" },
    closed: { text: "A made-up source that may not be used.", url: "https://example.org/closed", licence: "CC BY-NC 4.0", class: "non-commercial", accessed: "2026-11-19" },
  },
};

/** The same animal with its two-cell form drawn too, and a made-up run filling the way from the egg to it. */
function withRun() {
  const species = copy(DEWKIN);
  const two = species.stages.list[1];
  delete two.missing;
  Object.assign(two, {
    ends_at: "cell",
    no_further_levels: "Two cells, made up: no tissue, organ or body yet.",
    levels: [{ id: "cell", label: "Two cells", shape: { kind: "sphere", across_um: 900 }, note: "A made-up form.", sources: ["made"] }],
    cell: { facts: [] },
  });
  species.stages.spans = [{ from: "egg", to: "two-cell", fill: { kind: "prescribed", run: "made-up-division" } }];
  return freeze(species);
}

/** A made-up run of four records over three minutes, in the shape the page's run reader gives one (src/replay/run.js). */
const RUN = freeze({
  id: "made-up-division",
  start: 0,
  end: 180,
  t: [0, 60, 120, 180],
  count: 4,
  indexAt(time) {
    let index = 0;
    for (let k = 0; k < this.t.length; k++) if (this.t[k] <= time + 1e-9) index = k;
    return index;
  },
  events: [],
  eventsBy: () => 0,
  validity: null,
  isValid: () => true,
  info: { judged_s: null },
});

freeze(DEWKIN);

test("every species file of the repository but the frog has no stages, and is given back exactly as it is; the frog is read with its block", () => {
  const folder = path.join(ROOT, "data", "species");
  const files = readdirSync(folder).filter((name) => name.endsWith(".json"));
  assert.ok(files.length >= 9, "the repository's species are read");
  for (const name of files) {
    const species = freeze(JSON.parse(readFileSync(path.join(folder, name), "utf8")));
    if (name === "xenopus.json") {
      // The frog (decided on 19 November 2026): its block sound, opening on its adult, its file the very same at its own stage.
      assert.deepEqual(stageProblems(species), []);
      assert.equal(openingStage(species), "adult");
      assert.equal(speciesAt(species), species);
      assert.equal(speciesAt(species, "adult"), species);
      assert.equal(speciesAt(species, "two-cell"), null, "a named stage cannot be entered");
      assert.deepEqual(stripOf(species).map((mark) => mark.id), ["egg", "two-cell", "four-cell", "tadpole", "froglet", "adult"]);
      assert.deepEqual(stageFromAddress("egg", species), { stage: "egg", open: null });
      continue;
    }
    assert.equal(species.stages, undefined, `${name} carries no stages block`);
    assert.equal(readStages(species), null);
    assert.equal(hasStages(species), false);
    for (const id of [null, "egg", "adult", "anything"]) assert.equal(speciesAt(species, id), species, `${name} at ${id}: the very same object`);
    assert.deepEqual(stripOf(species), []);
    assert.deepEqual(passagesOf(species), []);
    assert.equal(journeyOf(species).playable, false);
    assert.deepEqual(stageFromAddress("egg", species), { stage: null, open: null });
    assert.equal(stageToAddress(species, "egg"), null);
  }
});

test("a sound block is read in its order; the file's own stage and no stage give the species as it is", () => {
  const read = readStages(DEWKIN);
  assert.equal(read.ok, true, JSON.stringify(read.problems));
  assert.deepEqual(read.stages.map((stage) => stage.id), ["egg", "two-cell", "larva", "adult"]);
  assert.equal(read.own.id, "adult");
  assert.equal(speciesAt(DEWKIN, "adult"), DEWKIN);
  assert.equal(speciesAt(DEWKIN), DEWKIN);
  // A list written in another order is read in its order.
  const shuffled = copy(DEWKIN);
  shuffled.stages.list.reverse();
  assert.deepEqual(readStages(shuffled).stages.map((stage) => stage.id), ["egg", "two-cell", "larva", "adult"]);
  assert.deepEqual(FILL_KINDS, ["illustrative", "simulated", "modelled", "prescribed"]);
});

test("each breach refuses the block with its own code, and the species is then read as if it had none", () => {
  const cases = [
    ["order-gap", (s) => (s.stages.list[3].order = 5)],
    ["order-repeat", (s) => (s.stages.list[2].order = 2)],
    ["number-unsourced", (s) => delete s.stages.list[0].levels[0].sources],
    ["number-unsourced", (s) => (s.stages.list[0].cell.facts[0].sources = [])],
    ["number-unsourced", (s) => delete s.stages.list[1].time.where],
    ["source-unknown", (s) => (s.stages.list[0].levels[0].sources = ["nowhere"])],
    ["source-not-permissive", (s) => (s.stages.list[0].cell.facts[0].sources = ["closed"])],
    ["span-not-neighbours", (s) => (s.stages.spans = [{ from: "egg", to: "larva", fill: { kind: "illustrative" } }])],
    ["span-unknown-stage", (s) => (s.stages.spans = [{ from: "egg", to: "pupa", fill: { kind: "illustrative" } }])],
    ["span-repeat", (s) => (s.stages.spans = [{ from: "larva", to: "adult", fill: { kind: "prescribed", run: "a" } }, { from: "larva", to: "adult", fill: { kind: "prescribed", run: "b" } }])],
    ["fill-kind", (s) => (s.stages.spans = [{ from: "egg", to: "two-cell", fill: { kind: "emerged" } }])],
    ["fill-run-missing", (s) => (s.stages.spans = [{ from: "egg", to: "two-cell", fill: { kind: "simulated" } }])],
    ["fill-illustrative-run", (s) => (s.stages.spans = [{ from: "egg", to: "two-cell", fill: { kind: "illustrative", run: "a" } }])],
    ["fill-illustrative-ends", (s) => {
      s.stages.list[3].order = 1; // the adult first, then the egg; the two named stages last, with no drawn stage after them
      s.stages.list[0].order = 2;
      s.stages.list[1].order = 3;
      s.stages.list[2].order = 4;
      s.stages.list[0].index = "0";
      s.stages.spans = [{ from: "two-cell", to: "larva", fill: { kind: "illustrative" } }];
    }],
    ["own-count", (s) => delete s.stages.list[3].own],
    ["own-count", (s) => (s.stages.list[0] = { ...s.stages.list[0], own: true, levels: undefined, ends_at: undefined, cell: undefined, no_further_levels: undefined })],
    ["own-differs", (s) => (s.stages.list[3].levels = [{ id: "cell", shape: { kind: "sphere", across_um: 1 }, sources: ["made"] }])],
    ["named-draws", (s) => (s.stages.list[1].levels = [{ id: "cell", shape: { kind: "sphere", across_um: 1 }, sources: ["made"] }])],
    ["drawn-states-nothing", (s) => delete s.stages.list[2].missing],
    ["level-above-end", (s) => s.stages.list[0].levels.push({ id: "tissue", shape: { kind: "cell sheet", rings: 1 }, sources: ["made"] })],
    ["no-further-sentence", (s) => delete s.stages.list[0].no_further_levels],
    ["facts-of-another-form", (s) => delete s.stages.list[0].cell.facts],
    ["index-order", (s) => (s.stages.list[2].index = "1")],
    ["index-without-system", (s) => delete s.stages.system],
    ["times-after", (s) => delete s.stages.times_after],
    ["time-shape", (s) => (s.stages.list[1].time.unit = "weeks")],
    ["stage-key", (s) => (s.stages.list[1].colour = "blue")],
    ["stage-id", (s) => (s.stages.list[1].id = "Two Cell")],
    ["modelled-shape", (s) => (s.stages.list[0].modelled = { state: "planned", text: "No record behind it." })],
    ["cell-type-unknown", (s) => (s.stages.list[0].cell_types = ["ciliated"])],
    ["opens-on-unknown", (s) => (s.stages.opens_on = "pupa")],
    ["opens-on-named", (s) => (s.stages.opens_on = "larva")],
  ];
  for (const [code, breach] of cases) {
    const species = copy(DEWKIN);
    breach(species);
    freeze(species);
    assert.ok(codes(species).includes(code), `${code}: got ${JSON.stringify(stageProblems(species))}`);
    assert.equal(readStages(species).ok, false);
    assert.equal(speciesAt(species, "egg"), species, `${code}: a refused block leaves the species as it is`);
    assert.deepEqual(stripOf(species), []);
    for (const item of stageProblems(species)) assert.ok(item.says.length > 10, "each refusal says what is wrong");
  }
  assert.deepEqual(codes(DEWKIN), [], "the made-up animal itself is sound");
});

test("read through a stage: the stage's own values over the file, nothing else changed", () => {
  const egg = speciesAt(DEWKIN, "egg");
  assert.notEqual(egg, DEWKIN);
  assert.equal(fileOf(egg), DEWKIN, "it knows the file it was read from");
  // Its levels: molecules and its own cell, small to large; it ends at its cell and says so.
  assert.deepEqual(egg.levels.map((level) => level.id), ["molecules", "cell"]);
  assert.equal(egg.levels[0], DEWKIN.levels[0], "a level the stage does not give is the file's own");
  assert.deepEqual(egg.levels[1].shape, { kind: "sphere", across_um: 900 });
  assert.equal(egg.no_further_levels, "An egg is one cell: it has no tissue, organ or body yet.");
  // Its cell: its own facts, the file's parts (and it says so), the capabilities place by place.
  assert.deepEqual(egg.cell.facts.map((fact) => fact.label), ["Diameter"]);
  assert.equal(egg.cell.parts, DEWKIN.cell.parts);
  assert.deepEqual(Object.keys(egg.cell.capabilities).sort(), ["cap.channels", "cap.junctions"]);
  assert.deepEqual(egg.stage.inherits, ["cell.parts", "modelled"]);
  assert.equal(egg.stage.id, "egg");
  assert.equal(egg.stage.system.short, "DS");
  // Everything else is the file's, the very same values.
  for (const key of ["id", "label", "organism", "plain", "group", "order", "default", "made", "modelled", "sources", "stages"]) assert.equal(egg[key], DEWKIN[key], key);
  // A stage that cannot be entered, or that the species does not have, gives null.
  assert.equal(speciesAt(DEWKIN, "two-cell"), null);
  assert.equal(speciesAt(DEWKIN, "pupa"), null);
  // Read again from a species read through a stage, the file is read: the egg's own block is the file's.
  assert.equal(speciesAt(egg, "adult"), DEWKIN);
  assert.equal(readStages(egg), readStages(DEWKIN));
  // A stage that keeps every level drops the file's sentence on levels it lacks; the file is never changed.
  assert.ok(Object.isFrozen(DEWKIN.stages.list[0]));
});

test("in the scene's shape the own cell type is made again from the stage; a stage that leaves the cell alone keeps the types", () => {
  // As tools/lib/entries.py carries a species: its cell types resolved, its own first, holding copies of the file's cell.
  const scene = copy(DEWKIN);
  const own = { id: "cell", label: "Generic cell", own: true, modelled: scene.modelled, levels: scene.levels.filter((level) => level.id === "cell" || level.id === "tissue"), parts: scene.cell.parts, capabilities: scene.cell.capabilities, facts: scene.cell.facts, loop: "dewkin-loop" };
  const ciliated = { id: "ciliated", label: "Ciliated cell", order: 20, modelled: scene.modelled, levels: [{ id: "cell", shape: { kind: "capsule", length_um: 30, across_um: 8 } }], parts: {}, capabilities: {}, facts: [] };
  scene.cell_types = [own, ciliated];
  scene.default_cell_type = "cell";
  // A drawn larva that changes only the body's outline: the cell is the file's own.
  Object.assign(scene.stages.list[2], { levels: [{ id: "organism", shape: { kind: "outline", ref: "dewkin-larva" }, note: "A made-up larva.", sources: ["made"] }] });
  delete scene.stages.list[2].missing;
  freeze(scene);
  assert.deepEqual(codes(scene), []);

  const egg = speciesAt(scene, "egg");
  const type = cellTypeOf(egg);
  assert.equal(type.own, true);
  assert.deepEqual(type.levels.map((level) => level.id), ["cell"], "no copy of the file's sheet stands in the egg's type");
  assert.deepEqual(type.levels[0].shape, { kind: "sphere", across_um: 900 }, "the egg's cell, not the adult's, is what the Scope view reads first");
  assert.equal(type.loop, null, "a looping run of the file's cell is not the egg's");
  assert.deepEqual(cellTypesOf(egg).map((item) => item.id), ["cell"], "the species' other types are of its own form; the egg names none");
  assert.equal(egg.default_cell_type, "cell");
  assert.equal(cellTypeOf(egg, "ciliated").id, "cell", "a type the stage does not have gives its default");

  const larva = speciesAt(scene, "larva");
  assert.deepEqual(cellTypesOf(larva).map((item) => item.id), ["cell", "ciliated"]);
  assert.equal(cellTypeOf(larva).loop, "dewkin-loop", "the cell is the file's own, and so is its run");
  assert.equal(larva.levels.find((level) => level.id === "cell"), scene.levels.find((level) => level.id === "cell"));
  assert.equal(larva.levels.find((level) => level.id === "organism").shape.ref, "dewkin-larva");
  assert.equal(larva.no_further_levels, undefined, "a stage with every level says nothing of further levels");
  assert.deepEqual(larva.stage.inherits, ["cell.parts", "cell.facts", "modelled", "cell types"]);
});

test("the strip stands evenly by order; a stated time is written on its mark, never used to place it", () => {
  const marks = stripOf(DEWKIN);
  assert.deepEqual(marks.map((mark) => mark.place), [0, 1 / 3, 2 / 3, 1]);
  assert.deepEqual(marks.map((mark) => [mark.id, mark.drawn, mark.enterable, mark.own]), [["egg", true, true, false], ["two-cell", false, false, false], ["larva", false, false, false], ["adult", true, true, true]]);
  assert.equal(marks[1].words, "DS 2 · Two cells");
  assert.equal(marks[1].timeWords, "about 80 min after fertilisation, at 20 °C");
  assert.equal(marks[2].timeWords, "3 days after fertilisation, at 20 °C");
  assert.match(marks[2].says, /^DS 30-31 · Larva\. 3 days after fertilisation, at 20 °C\. named, not drawn: No length/);
  assert.equal(marks[3].indexWords, null, "a stage the system gives no index has none");
  // Between two stated times at one temperature the viewer may say how long lies between them, as a derivation.
  const between = elapsedBetween(DEWKIN, "two-cell", "larva");
  assert.equal(between.ok, true);
  assert.equal(between.low, 3 * 1440 - 80);
  assert.match(between.says, /worked out by the viewer from the two stages' stated times/);
  assert.equal(elapsedBetween(DEWKIN, "egg", "two-cell").ok, false, "the egg gives no time");
  const warmer = copy(DEWKIN);
  warmer.stages.list[2].time.temperature_c = 25;
  assert.equal(elapsedBetween(freeze(warmer), "two-cell", "larva").why, "their times are stated at different temperatures");
});

test("drawn, named, named, drawn: one plain change from the egg to the adult, passing the named marks", () => {
  const passages = passagesOf(DEWKIN);
  assert.deepEqual(passages.map((item) => [item.from, item.to, item.a, item.b, item.player.kind]), [["egg", "adult", 0, 3, "illustrative"]]);
  const change = passages[0].player;
  assert.deepEqual(change.through, ["two-cell", "larva"]);
  assert.match(change.says, /^Illustration: not a run\. A plain change from Egg to Adult; Two cells, Larva are named, not drawn\. Nothing of how/);
  // Each end held, then one gives way through an empty picture to the other: no moment shows a blend between.
  const weights = (p) => Object.fromEntries(change.frameAt(p).draws.map((item) => [item.stage, item.weight]));
  assert.deepEqual(weights(0), { egg: 1 });
  assert.deepEqual(weights(HOLD), { egg: 1 });
  assert.deepEqual(weights(0.5), {});
  assert.deepEqual(weights(1 - HOLD), { adult: 1 });
  for (let p = 0; p <= 1; p += 0.01) assert.ok(change.frameAt(p).draws.length <= 1, `at ${p.toFixed(2)} at most one picture is drawn`);
  // Each end at the level the visitor is at, where it has it; an egg at the whole body is drawn at its cell.
  assert.deepEqual(change.frameAt(0.05, "organism").draws, [{ stage: "egg", weight: 1, level: "cell" }]);
  assert.deepEqual(change.frameAt(0.95, "organism").draws, [{ stage: "adult", weight: 1, level: "organism" }]);
  assert.equal(levelFor(speciesAt(DEWKIN, "egg"), "tissue"), "cell");
  // On the journey, a named mark is passed: the frame there is the change's, with that stage named, and draws no picture of it.
  const journey = journeyOf(DEWKIN);
  assert.equal(journey.playable, true);
  const atLarva = journey.frameAt(2);
  assert.equal(atLarva.kind, "illustrative");
  assert.equal(atLarva.stage, "larva");
  assert.ok(atLarva.draws.every((item) => item.stage !== "larva"));
  assert.deepEqual(journey.frameAt(0).draws, [{ stage: "egg", weight: 1, level: "cell" }], "at a drawn stage, its own picture");
});

test("the plain change and a made-up run's records both load into the Experiments tab's Player, alone and in order", () => {
  const species = withRun();
  assert.deepEqual(codes(species), []);
  const runPlayer = (fill, span) => (fill.run === RUN.id ? recordsPlayer(RUN, { from: span.from, to: span.to, kind: fill.kind, levels: ["cell"] }) : null);
  const passages = passagesOf(species, { runPlayer });
  assert.deepEqual(passages.map((item) => [item.from, item.to, item.player.kind]), [["egg", "two-cell", "prescribed"], ["two-cell", "adult", "illustrative"]]);
  const run = passages[0].player;
  assert.equal(run.says, `${FILL_WORDS.prescribed}: made-up-division, from its record at 0 to its record at 180 in its own time`);
  assert.equal(run.watch, 180 / openingSpeed(180), "a run plays at the speed its replay opens at");

  // Alone: each player's own clock in the Player, as the Experiments tab plays a run.
  const alone = new Player();
  alone.load(run.asRun());
  assert.deepEqual([alone.start, alone.end, alone.speed], [0, 180, openingSpeed(180)]);
  alone.play();
  alone.tick(5000);
  assert.equal(alone.time, 5 * openingSpeed(180));
  assert.equal(run.frameAt(alone.time).record, 1, "the record at or before the time, as every replay shows one");
  alone.load(passages[1].player.asRun());
  assert.deepEqual([...SPEEDS], [1]);
  alone.play();
  alone.tick(1000);
  assert.equal(alone.time, 1 / ILLUSTRATION_SECONDS);

  // In order: the journey is one clock with every field the timeline reads (src/ui/timeline.js).
  const journey = journeyOf(species, passages);
  for (const key of ["start", "end", "t", "count", "indexAt", "events", "eventsBy", "validity", "isValid", "info", "timeBase"]) assert.ok(key in journey, key);
  for (const key of ["id", "speedsFor", "openingSpeed", "words", "clock", "length", "advance", "place", "timeAt"]) assert.ok(key in journey.timeBase, `timeBase.${key}`);
  assert.equal(journey.info.judged_s, null);
  assert.deepEqual(journey.events.map((event) => [event.time, event.label, event.enterable]), [[0, "DS 1 · Egg", true], [1, "DS 2 · Two cells", true], [2, "DS 30-31 · Larva", false], [3, "Adult", true]]);
  assert.deepEqual([0, 0.5, 1, 2, 3].map((time) => journey.timeBase.place(time)), [0, 1 / 6, 1 / 3, 2 / 3, 1], "the track is the strip, evenly by order");
  assert.ok(journey.timeBase.words(1).says.includes("own pace") && !/true speed/.test(JSON.stringify(PACES.map(journey.timeBase.words))));
  const player = new Player();
  player.load(journey);
  assert.deepEqual([player.start, player.end, player.speed], [0, 3, 1]);
  assert.deepEqual([...SPEEDS], [...PACES]);
  const seen = [];
  player.play();
  for (let k = 0; k < 40 && player.playing; k++) {
    player.tick(500);
    const frame = journey.frameAt(player.time);
    seen.push([Number(player.time.toFixed(3)), frame.kind, frame.record ?? null, frame.stage ?? null]);
  }
  assert.equal(player.time, 3);
  assert.equal(player.playing, false, "it stops at the last stage");
  const kinds = seen.map(([, kind]) => kind).filter((kind, k, all) => kind !== all[k - 1]);
  assert.deepEqual(kinds, ["prescribed", "stage", "illustrative", "stage"], "the run's span first, then the plain change, in order");
  const records = seen.filter(([, kind]) => kind === "prescribed").map(([, , record]) => record);
  assert.deepEqual([...new Set(records)], [0, 1, 2], "the run's records in their order");
  assert.ok(seen.some(([time, kind, , stage]) => kind === "illustrative" && stage === "larva" && time === 2), "the named larva is passed");
  const watched = 180 / openingSpeed(180) + ILLUSTRATION_SECONDS;
  assert.equal(seen.length, Math.ceil(watched / 0.5), "each passage at its own pace");
  // The keyboard's steps go stage by stage; the strip's ends hold the playhead.
  player.seek(0);
  player.step(1);
  assert.equal(player.time, 1);
  player.seek(-5);
  assert.equal(player.time, 0);
  assert.equal(journey.read(1.5).now, "Between DS 2 · Two cells and Adult");
  assert.equal(journey.read(2).of, ": named, not drawn");
  // A run that is not at hand: nothing is drawn, and the reason is given; illustration does not stand in for it.
  const waiting = passagesOf(species);
  assert.equal(waiting[0].player.kind, "none");
  assert.match(waiting[0].player.says, /the run made-up-division that fills it is not at hand/);
});

test("the stage a species opens on, and the address's stage, to and from its text", () => {
  // It opens on the file's own stage, unless the block names another drawn stage.
  assert.equal(openingStage(DEWKIN), "adult");
  assert.deepEqual(stageFromAddress("egg", DEWKIN), { stage: "egg", open: null });
  assert.deepEqual(stageFromAddress(" egg ", DEWKIN), { stage: "egg", open: null });
  assert.deepEqual(stageFromAddress("adult", DEWKIN), { stage: "adult", open: null });
  assert.deepEqual(stageFromAddress("larva", DEWKIN), { stage: "adult", open: "larva" }, "a named stage cannot be entered: its card opens at the opening stage");
  assert.deepEqual(stageFromAddress("pupa", DEWKIN), { stage: "adult", open: null }, "a stage the species does not have is passed over");
  assert.deepEqual(stageFromAddress("", DEWKIN), { stage: "adult", open: null });
  assert.equal(stageToAddress(DEWKIN, "egg"), "egg");
  assert.equal(stageToAddress(DEWKIN, "adult"), null, "the stage it opens on is not written");
  assert.equal(stageToAddress(DEWKIN, "larva"), null);
  const params = new URLSearchParams("entry=dewkin&stage=old");
  assert.equal(writeStage(params, DEWKIN, "egg").toString(), "entry=dewkin&stage=egg");
  assert.equal(writeStage(params, DEWKIN, "adult").toString(), "entry=dewkin");
  assert.equal(stageFromAddress(new URLSearchParams("entry=dewkin&stage=egg").get("stage"), DEWKIN).stage, "egg");
  // A species that opens on its egg while its file describes the adult.
  const early = copy(DEWKIN);
  early.stages.opens_on = "egg";
  freeze(early);
  assert.deepEqual(codes(early), []);
  assert.equal(openingStage(early), "egg");
  assert.equal(readStages(early).own.id, "adult", "the file's own stage stays the form the file describes");
  assert.deepEqual(stageFromAddress("", early), { stage: "egg", open: null });
  assert.equal(stageToAddress(early, "egg"), null);
  assert.equal(stageToAddress(early, "adult"), "adult", "the file's own stage is written where the species opens on another");
  assert.equal(speciesAt(early, "adult"), early, "and read at it the species is its file, as it is");
  assert.equal(openingStage(JSON.parse(readFileSync(path.join(ROOT, "data", "species", "mouse.json"), "utf8"))), null);
});

test("the play control's switch: a journey may play only the passages a run fills, and stops where one it may not play begins", () => {
  const species = withRun();
  const runPlayer = (fill, span) => (fill.run === RUN.id ? recordsPlayer(RUN, { from: span.from, to: span.to, kind: fill.kind }) : null);
  const passages = passagesOf(species, { runPlayer });
  const runsOnly = (passage) => passage.player.kind !== "none" && passage.player.kind !== "illustrative";
  const journey = journeyOf(species, passages, { plays: runsOnly });
  assert.equal(journey.playable, true);
  assert.equal(journey.stretchEnd(0), 1, "from the egg, play runs the run's span and stops at the two-cell form");
  assert.equal(journey.stretchEnd(0.5), 1);
  assert.equal(journey.stretchEnd(1), null, "from there only the viewer's own change follows: nothing plays");
  assert.equal(journey.stretchEnd(3), null);
  assert.equal(journeyOf(DEWKIN, passagesOf(DEWKIN), { plays: runsOnly }).playable, false, "a strip that only the viewer's own change fills has no play");
  const player = new Player();
  player.load(journey);
  player.play();
  for (let k = 0; k < 100 && player.time < 1; k++) player.tick(500);
  assert.equal(player.time, 1);
  player.tick(500);
  assert.equal(player.time, 1, "it does not move into the change");
  assert.deepEqual([player.start, player.end], [0, 3], "the playhead may stand on any stage of the strip");
});

test("the build reads the block through this reader: carried where sound, refused with the reader's code, and plainly where node is missing", () => {
  // tools/lib/species.py asks src/scene/life_stages.js through node (one call for each species with stages), and holds the
  // species read through each drawn stage to the species contract. About half a second: four Python processes (one only to find the interpreter), four node calls.
  const folder = path.join(ROOT, "tests", "fixtures", "stages", "species");
  const file = JSON.parse(readFileSync(path.join(folder, "dewkin.json"), "utf8"));
  const gap = copy(file);
  gap.stages.list[3].order = 5;
  const broken = copy(file);
  broken.stages.list[0].levels[0].shape.across_um = -1; // the block is sound; the egg read through it is not a species
  const script = `
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from lib import species
request = json.load(sys.stdin)
out = []
for given in request["given"]:
    reader = species.Reader(Path(request["folder"]), request["capabilities"])
    found = reader.species(Path(request["folder"]) / "dewkin.json", given=given)
    out.append({"stages": bool(found and found.get("stages")), "found": bool(found), "warnings": reader.warnings})
print(json.dumps(out))
`;
  const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
  const capabilities = Object.fromEntries(overlay.capabilities.map((item) => [item.id, item.scale]));
  // The interpreter itself, found where this machine keeps it, so that it can be started with no PATH at all.
  const python = spawnSync("python3", ["-I", "-c", "import sys; print(sys.executable)"], { encoding: "utf8" }).stdout.trim();
  const ask = (given, env = process.env) => {
    const done = spawnSync(python, ["-I", "-c", script, path.join(ROOT, "tools")], { input: JSON.stringify({ folder, capabilities, given }), encoding: "utf8", env });
    assert.equal(done.status, 0, done.stderr);
    return JSON.parse(done.stdout);
  };
  const [sound, refused, unfit] = ask([file, gap, broken]);
  assert.deepEqual([sound.found, sound.stages, sound.warnings], [true, true, []]);
  assert.deepEqual([refused.found, refused.stages], [true, false], "a refused block leaves the species as it was");
  assert.match(refused.warnings[0], /its stages are refused, order-gap: the order has a gap/);
  assert.deepEqual([unfit.found, unfit.stages], [true, false]);
  assert.match(unfit.warnings.join(" "), /dewkin\.json at its stage egg: .*across_um must be a number above zero/);
  assert.match(unfit.warnings.at(-1), /breaks the species contract/);
  // A stage's word in the ladder is held to its record by the entries reader, as the species' own is.
  const worded = copy(file);
  worded.stages.list[0].modelled = { state: "planned", text: "A made-up word.", record: [{ path: "docs/NOT_A_FILE.md", where: "nowhere" }] };
  const entries = spawnSync(python, ["-I", "-c", `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import entries, species
request = json.load(sys.stdin)
reader = species.Reader(__import__("pathlib").Path(request["folder"]), request["capabilities"])
found = reader.species(__import__("pathlib").Path(request["folder"]) / "dewkin.json", given=request["given"])
out, models, warnings, remarks = entries.check([found], {"dewkin": request["given"]}, {}, {}, request["capabilities"], tracked=[])
print(json.dumps({"stages": bool(out and out[0].get("stages")), "warnings": warnings}))
`, path.join(ROOT, "tools")], { input: JSON.stringify({ folder, capabilities, given: worded }), encoding: "utf8" });
  assert.equal(entries.status, 0, entries.stderr);
  const ladder = JSON.parse(entries.stdout);
  assert.equal(ladder.stages, false, "a stage whose word cites no tracked record leaves the species without its stages");
  assert.match(ladder.warnings.join(" "), /its stage egg: .*the species is shown without its stages/);
  const [lost] = ask([file], { PATH: "/nonexistent" });
  assert.deepEqual([lost.found, lost.stages], [true, false]);
  assert.match(lost.warnings[0], /its stages cannot be read: node is not on this machine, and the build reads stages through src\/scene\/life_stages\.js/);
});
