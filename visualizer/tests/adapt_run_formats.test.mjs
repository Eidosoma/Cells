// The run adapter on views written by main's run-view writer at 89bd2ffb, which holds the core seams pass's three format
// items and its addition (the engine's docs/CORE_SEAMS_DESIGN.md §9 and §4.3, docs/RUN_VIEW_DESIGN.md §9; on main from
// d64fb664, 18 November 2026): kinds are words, a law's ID under `laws`; each species a route carries moves with its own
// flux, coupled stoichiometry being `per_cycle`; a reference over a field the run did not save stands only with that
// field's entry under `unstated`; and a channel set's `factors`. The format keeps its name (cells.run_view@1), so the
// adapter reads views of both shapes side by side, and an older view packages exactly as before.
//
// tests/engine-views/run-view-89bd2ffb holds eight small worlds (tools/make_engine_view_fixture.sh); what no small world
// of the engine shows is planted on copies of them from tests/fixtures/run-view-made-up (made up, and marked so). Each
// claim comes with the planted error its check must catch. Nothing here runs the engine.
//
//   node --test tests/adapt_run_formats.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Run, validateReplay } from "../src/replay/run.js";
import { streamsOf } from "../src/layers/marks/beads.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "adapt_run.py");
const VIEWS = path.join(ROOT, "tests", "engine-views");
const NEW = path.join(VIEWS, "run-view-89bd2ffb"), OLD = path.join(VIEWS, "run-view-b5d3faf0");
const WORLDS = ["secretion", "subset", "increments", "kinds", "division", "factors", "condition", "dose"];
const PLANTS = path.join(ROOT, "tests", "fixtures", "run-view-made-up", "plants.json");
const EXPERIMENT = "engine-views";
const PATHS = /\/home\/|\/mnt\/|\/Users\/|\/tmp\/|[A-Za-z]:\\\\/;

// On disk under out/, as the other adapter tests keep theirs: /tmp is memory on the project's machine.
mkdirSync(path.join(ROOT, "out"), { recursive: true });
const scratch = mkdtempSync(path.join(ROOT, "out", "adapt-formats-"));
test.after(() => rmSync(scratch, { recursive: true, force: true }));
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
const OVERLAY = path.join(scratch, "overlay.json");
writeFileSync(OVERLAY, JSON.stringify({ format: "cells.visualizer.replay_overlay@1", experiments: { [EXPERIMENT]: { adapter: "standard-history", development: true, label: "The run view's writer (test fixture)", plain: "Unit-test worlds the engine's run-view writer wrote.", sources: [], engine_entities: [], outcome: { judged: false, status: "A development run: not judged" }, parameters: {}, readouts: {}, events: {}, stops: { complete: { label: "Ran to its end" } } } } }));

/** Adapt the named worlds of one folder of views into `out`; the adapter's result. */
function adapt(root, worlds, out) {
  const selection = path.join(scratch, `selection-${path.basename(out)}.json`);
  writeFileSync(selection, JSON.stringify({ [EXPERIMENT]: { evidence_folder: path.basename(root), runs: worlds } }));
  return spawnSync("python3", ["-I", TOOL, "--experiment", EXPERIMENT, "--root", root, ...worlds.flatMap((world) => ["--run", world]), "--overlay", OVERLAY, "--selection", selection, "--out", out], { encoding: "utf8" });
}

/** A packaged run opened with every part attached: its file, view, Run and a record by id. */
function open(folder, world) {
  const file = readJson(path.join(folder, `${EXPERIMENT}--${world}.json`));
  const bytes = Buffer.from(file.payload.data, "base64");
  const run = new Run(file.view, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  for (const part of file.view.parts || []) {
    const held = Buffer.from(readJson(path.join(folder, path.basename(part.file))).payload.data, "base64");
    run.attach(part.id, held.buffer.slice(held.byteOffset, held.byteOffset + held.byteLength));
  }
  return { file, view: file.view, run, record: (id) => file.view.records.find((item) => item.id === id), set: (id) => file.view.sets.find((item) => item.id === id) };
}

/** One world of a folder of views with its view changed in a copy, adapted: [result, output folder]. */
function changed(label, change, world, from = NEW) {
  const copy = path.join(scratch, `copy-${label}`);
  cpSync(from, copy, { recursive: true });
  const file = path.join(copy, world, "view.json");
  const view = readJson(file);
  change(view);
  writeFileSync(file, JSON.stringify(view));
  const out = path.join(scratch, `copy-${label}-out`);
  return [adapt(copy, [world], out), out];
}

/** A made-up plant (tests/fixtures/run-view-made-up) applied to a view: keys of sets replaced, and sets added. */
function planted(plant) {
  return (view) => {
    for (const [id, keys] of Object.entries(plant.sets || {})) Object.assign(view.sets.find((item) => item.id === id), keys);
    view.sets.push(...(plant.add_sets || []));
  };
}

const newOut = path.join(scratch, "new"), oldOut = path.join(scratch, "old");
const newDone = adapt(NEW, WORLDS, newOut);
assert.equal(newDone.status, 0, `the adapter failed on the views written at 89bd2ffb:\n${newDone.stderr}`);
const oldDone = adapt(OLD, WORLDS.slice(0, 5), oldOut);
assert.equal(oldDone.status, 0, `the adapter failed on the views written at b5d3faf0:\n${oldDone.stderr}`);
const written = (world) => readJson(path.join(NEW, world, "view.json"));
const setOf = (view, id) => view.sets.find((item) => item.id === id);

test("the views written at 89bd2ffb are main's writer's own: every world, the three items in the writer's words, under 1 MB", () => {
  const note = readFileSync(path.join(NEW, "README.md"), "utf8");
  assert.match(note, /^# Runs written by the engine's run-view writer \(89bd2ffb\)/);
  assert.ok(note.includes("89bd2ffba7a0732a1dc20a6c2e61f86786c9b535"), "the note names the revision it was written at");
  assert.match(note, /that is main at `89bd2ffb`: the writer is on main since 050aa741/);
  assert.match(note, /Its writer holds the core seams pass's three format items/);
  assert.match(note, /planted\*\* factor\s+source/);
  assert.deepEqual(readdirSync(NEW).filter((name) => name !== "README.md").sort(), [...WORLDS].sort(), "every world of the tool was written at this revision");
  const size = (folder) => readdirSync(folder, { withFileTypes: true }).reduce((total, item) => total + (item.isDirectory() ? size(path.join(folder, item.name)) : statSync(path.join(folder, item.name)).size), 0);
  assert.ok(size(NEW) < 1_000_000, `the set is ${size(NEW)} bytes`);
  assert.ok(!PATHS.test(readdirSync(NEW, { recursive: true }).filter((name) => /\.(json|jsonl|md)$/.test(name)).map((name) => readFileSync(path.join(NEW, name), "utf8")).join("\n")), "no kept text file names a machine path");
  for (const world of WORLDS) {
    const view = written(world);
    assert.equal(view.format, "cells.run_view@1", `${world}: the format keeps its name`);
    for (const item of view.sets) if (item.kinds) assert.ok(item.kinds.every((kind) => typeof kind === "string" && !kind.includes("@")), `${world}: the set ${item.id}'s kinds are words`);
  }
  // Against the same five worlds at b5d3faf0: the kind world's kind is now a word with the law under laws; the subset world,
  // whose records name no reference, no longer states one; the others are the same views but for the label the script plants.
  assert.deepEqual([setOf(written("kinds"), "passive_route").kinds, setOf(written("kinds"), "passive_route").laws], [["leak"], [{ law_id: "proton_constant_field_leak@1" }]]);
  assert.deepEqual(setOf(readJson(path.join(OLD, "kinds", "view.json")), "passive_route").kinds, ["proton_constant_field_leak@1"]);
  assert.ok(readJson(path.join(OLD, "subset", "view.json")).constants.some((item) => item.id === "amount_reference"));
  assert.ok(!written("subset").constants.some((item) => item.id === "amount_reference"), "a reference constant only where a record names it");
  for (const world of ["increments", "division"]) {
    for (const file of readdirSync(path.join(NEW, world), { recursive: true }).filter((name) => statSync(path.join(NEW, world, name)).isFile())) {
      assert.ok(readFileSync(path.join(NEW, world, file)).equals(readFileSync(path.join(OLD, world, file))), `${world}/${file}: the same bytes as at b5d3faf0`);
    }
  }
});

test("every world of the new shape is packaged, and every package passes the page's own checks", () => {
  for (const world of WORLDS) {
    const { file, view } = open(newOut, world);
    assert.deepEqual(validateReplay(file), [], world);
    assert.ok(!PATHS.test(JSON.stringify(view)), `${world}: no machine path`);
  }
});

test("kinds: a word with its law under laws is packaged as written and its law named beside it; an older view's law ID as a kind packages as before", () => {
  const routes = open(newOut, "kinds").set("passive_route");
  assert.deepEqual([routes.kinds, routes.laws, routes.species], [["leak"], [{ law_id: "proton_constant_field_leak@1" }], [["H"]]]);
  const said = (folder, world) => open(folder, world).view.derivation.find((line) => line.startsWith("What the run's operators state of each of their entities"));
  assert.equal(said(newOut, "kinds"), "What the run's operators state of each of their entities is carried as the view gives it (passive_route: proton_leak_0 (leak; law proton_constant_field_leak@1) carries H at bounding_0); a route's species is the one the view says it carries.");
  // The older shape: the law's ID under kinds is carried and said as written, with no word about it and no refusal.
  const older = open(oldOut, "kinds");
  assert.deepEqual([older.set("passive_route").kinds, older.set("passive_route").laws], [["proton_constant_field_leak@1"], undefined]);
  assert.equal(said(oldOut, "kinds"), "What the run's operators state of each of their entities is carried as the view gives it (passive_route: proton_leak_0 (proton_constant_field_leak@1) carries H at bounding_0); a route's species is the one the view says it carries.");
  // Plant: the new view put back in the old form as text (the law's ID as the kind, no laws) is the older view's file, byte for
  // byte, and packages byte for byte as the older view.
  const copy = path.join(scratch, "copy-kinds-old-form");
  cpSync(NEW, copy, { recursive: true });
  const text = readFileSync(path.join(copy, "kinds", "view.json"), "utf8");
  const form = (kind, laws) => `      "kinds": [\n        "${kind}"\n      ],\n${laws ? '      "laws": [\n        {\n          "law_id": "proton_constant_field_leak@1"\n        }\n      ],\n' : ""}`;
  assert.equal(text.split(form("leak", true)).length, 2, "the new form stands once in the view");
  writeFileSync(path.join(copy, "kinds", "view.json"), text.replace(form("leak", true), form("proton_constant_field_leak@1", false)));
  assert.ok(readFileSync(path.join(copy, "kinds", "view.json")).equals(readFileSync(path.join(OLD, "kinds", "view.json"))), "the older view's file");
  const backOut = path.join(scratch, "copy-kinds-old-form-out");
  const back = adapt(copy, ["kinds"], backOut);
  assert.equal(back.status, 0, back.stderr);
  for (const name of readdirSync(backOut).filter((item) => item.startsWith(`${EXPERIMENT}--kinds`))) {
    assert.ok(readFileSync(path.join(backOut, name)).equals(readFileSync(path.join(oldOut, name))), `${name}: the same bytes as the older view's package`);
  }
  // FR-5's pH condition: its kind a word and its law under laws, named beside it; its own facts (ph50, slope) are named, never refused.
  const condition = open(newOut, "condition");
  assert.deepEqual([condition.set("ph_condition").kinds, condition.set("ph_condition").laws, condition.set("ph_condition").ph50], [["factor"], [{ law_id: "cells.ph_conditioned_factor@1" }], undefined]);
  assert.ok(said(newOut, "condition").includes("ph_condition: acid_0 (factor; law cells.ph_conditioned_factor@1) at lumen_0"));
  assert.ok(condition.view.derivation.includes("The view gives what the adapter does not read, and none of it is packaged: the set ph_condition: ph50, slope. Each is named here, never refused."));
  // Plant: a kind that is not a word is refused, as before.
  const [refused, refusedOut] = changed("kinds-not-a-word", (view) => (setOf(view, "passive_route").kinds = [7]), "kinds");
  assert.notEqual(refused.status, 0);
  assert.match(refused.stderr, /its view gives the set passive_route 'kinds' that is not a word for each of its entities/);
  assert.ok(!existsSync(path.join(refusedOut, "index.json")));
});

test("carries: a route that lists several species is said to move each with its own flux, never as one coupled movement", () => {
  const plants = readJson(PLANTS);
  assert.match(plants.made_up, /^Made up by the viewer for its own tests/);
  // One species a route reads as before.
  assert.ok(open(newOut, "condition").view.derivation.some((line) => line.includes("proton_leak_0 (leak; law proton_constant_field_leak@1) carries H at bounding_0;")));
  const routes = plants.plants.find((plant) => plant.world === "condition");
  const [result, out] = changed("carries-two", planted(routes), "condition");
  assert.equal(result.status, 0, result.stderr);
  const { view, file, set } = open(out, "condition");
  assert.deepEqual(validateReplay(file), []);
  assert.deepEqual(set("passive_route").species, [["X"], ["X", "H"], ["H"], ["H"]], "a list stays a list, as the view gives it");
  const facts = view.derivation.find((line) => line.startsWith("What the run's operators state"));
  assert.ok(facts.includes("cargo_transfer_0 (permeation; law passive_neutral_permeation@1) carries X, H (each with its own flux) at bounding_0"), facts);
  assert.ok(facts.endsWith("a route's species is the one the view says it carries. Where an entity carries more than one species, each moves with its own flux, not as a coupled set: only a stated per_cycle couples species."));
  // The planted error the wording must not make: no line joins the species of one entity as one movement.
  for (const line of view.derivation) assert.doesNotMatch(line, /carries X and H|carries H and X/);
  // An operator's route: each species it lists is taken as secreted on its own, and said so.
  const exchange = plants.plants.find((plant) => plant.world === "secretion");
  const [secreting, secretingOut] = changed("carries-operator", planted(exchange), "secretion");
  assert.equal(secreting.status, 0, secreting.stderr);
  const opened = open(secretingOut, "secretion");
  assert.deepEqual(validateReplay(opened.file), []);
  assert.deepEqual(opened.set("species").secreted, ["Na", "S"]);
  assert.ok(opened.view.derivation.some((line) => line.includes("secrete (export) carries S, Na (each with its own flux)")));
  assert.ok(opened.view.derivation.some((line) => line.endsWith("Where an entity carries more than one, each moves with its own flux, and each is taken on its own.")));
  for (const line of opened.view.derivation) assert.doesNotMatch(line, /carries S and Na/);
  // The page draws no coupling from it: a route's lane takes its species only where the route carries one.
  assert.equal(opened.set("exchange_route").species.filter((value) => typeof value === "string").length, 1);
});

test("per_cycle: a membrane pump's is packaged as written and drawn; a cycle kind's set of its own is named and left out, never refused", () => {
  const { view, file, run, set } = open(newOut, "factors");
  const pump = setOf(written("factors"), "membrane").pumps[0];
  assert.deepEqual(pump.per_cycle, [{ count: -3, role: "sodium", species: "Na" }, { count: 2, role: "potassium", species: "K" }]);
  assert.deepEqual(set("membrane").pumps, [pump], "the membrane's pump, carried whole");
  // What the page draws of it (marks/beads.js): one stream for each species one cycle moves, at its count per cycle.
  const cycles = view.records.find((item) => item.id === "pump_cycles");
  const streams = streamsOf(run, [], cycles, 0).filter((stream) => stream.kind === "pump");
  assert.deepEqual(streams.map((stream) => [stream.species, stream.per]), [["Na", -3], ["K", 2]]);
  // Plant: a pump whose counts run the other way is refused by the page's check.
  const flipped = structuredClone(file);
  flipped.view.sets.find((item) => item.id === "membrane").pumps[0].per_cycle_sign = "outward-positive";
  assert.ok(validateReplay(flipped).some((problem) => problem.includes("pumps must give")));
  // A cycle kind's per_cycle on a set of its own (made up: no cycle kind gives one at 89bd2ffb).
  const plant = readJson(PLANTS).plants.find((item) => item.world === "condition");
  const [result, out] = changed("per-cycle", planted(plant), "condition");
  assert.equal(result.status, 0, result.stderr);
  const cycled = open(out, "condition");
  assert.deepEqual(validateReplay(cycled.file), []);
  assert.equal(cycled.set("transporter_population").per_cycle, undefined, "not packaged");
  assert.deepEqual([cycled.set("transporter_population").kinds, cycled.set("transporter_population").laws], [["cycle"], [{ law_id: "cells.proton_atp_mass_action_positive@1" }]]);
  assert.ok(cycled.view.derivation.includes("The view gives per_cycle on the set transporter_population: a coupled stoichiometry, by mode and population, as the view states it. It is not packaged: no layer of the page draws a cycle kind's modes. The one coupled movement the page draws is a membrane pump's, from what one cycle of it moves (the membrane set's pumps, per_cycle)."));
  // Plant: it is not one value for each entity, and is still not refused (it does not join the per-entity facts' check).
  const [uneven] = changed("per-cycle-uneven", (view) => {
    planted(plant)(view);
    setOf(view, "transporter_population").per_cycle.push([]);
  }, "condition");
  assert.equal(uneven.status, 0, uneven.stderr);
  // A membrane's calcium pump (none in a kept world): named and left out.
  const [calcium, calciumOut] = changed("calcium-pump", (view) => (setOf(view, "membrane").calcium_pumps[0] = { id: "calcium_pump_0", law_id: "a_calcium_pump_law@1", per_cycle: [{ role: "calcium", species: "Na", count: -1 }], per_cycle_sign: "inward-positive" }), "factors");
  assert.equal(calcium.status, 0, calcium.stderr);
  const withCalcium = open(calciumOut, "factors");
  assert.equal(withCalcium.set("membrane").calcium_pumps, undefined);
  assert.ok(withCalcium.view.derivation.includes("The view gives 1 membrane(s) a calcium pump (calcium_pumps: its law and what one cycle moves, per_cycle): membrane_0. They are not packaged: no layer of the page reads a calcium pump's cycles."));
});

test("factors: each population's factor sources are named with the note on its availability, and left out; a malformed list is refused", () => {
  const { view, set } = open(newOut, "factors");
  assert.deepEqual(setOf(written("factors"), "channel").factors, [["f_b", "f_c"], []]);
  assert.equal(set("channel").factors, undefined, "not packaged");
  assert.equal(view.records.some((item) => item.field === "channel_availability"), false, "the page has no name for a population's availability");
  const note = written("factors").records.find((item) => item.field === "channel_availability").note;
  assert.match(note, /^the held availability, before the routing door/);
  assert.ok(view.derivation.includes(`The view states, for each channel population, the factor sources by which the routing door scales its availability at every stage (factors, in declared order): kir_0: f_b, f_c; nav_0: none. They are not packaged: no layer of the page reads a population's availability. Of its record channel_availability, which is not packaged either, the view says: ${note}${/[.!?]$/.test(note) ? "" : "."}`));
  // A world whose populations declare no factors says nothing of them (the five older worlds, the kind world here).
  assert.ok(!open(newOut, "kinds").view.derivation.some((line) => line.includes("factor sources")));
  // Plants: not one list for each population, and a source that is no name.
  for (const [label, factors] of [["factors-count", [["f_b", "f_c"]]], ["factors-name", [[3], []]]]) {
    const [result, out] = changed(label, (view) => (setOf(view, "channel").factors = factors), "factors");
    assert.notEqual(result.status, 0, label);
    assert.match(result.stderr, /its view gives the channel set factors that are not, for each population, the list of the factor sources it declares/, label);
    assert.ok(!existsSync(path.join(out, "index.json")), `${label}: nothing is catalogued`);
  }
});

test("references: a field reference stands only with its unstated entry, and every sentence about it names the field and the view's reason", () => {
  const view = written("dose");
  const record = view.records.find((item) => item.id === "observed_extracellular_amount_increment");
  assert.deepEqual(record.reference, { field: "extracellular_amount_reference" });
  const entry = view.unstated.find((item) => item.id === "extracellular_amount_reference");
  assert.equal(entry.what, "view field");
  const opened = open(newOut, "dose");
  assert.deepEqual(opened.run.unstated.get("extracellular_amount_reference"), entry.why, "the reason is carried");
  assert.ok(opened.view.derivation.includes(`The view stores 2 field(s) as an increment over a fixed reference (its reference): amount_increment over amount_reference; extracellular_amount_increment over the field extracellular_amount_reference, which the run did not save (${entry.why}).`));
  assert.ok(opened.record("extracellular_amount.S"), "the level itself was saved, and is read as saved");
  // Plant: the entry taken away. Refused, with the record and the field named; nothing is catalogued.
  const [refused, refusedOut] = changed("field-without-entry", (view) => (view.unstated = view.unstated.filter((item) => item.id !== "extracellular_amount_reference")), "dose");
  assert.notEqual(refused.status, 0);
  assert.match(refused.stderr, /its view's record (observed_)?extracellular_amount_increment is stored over the field extracellular_amount_reference \(its reference\), which the run did not save, and its view gives no entry for extracellular_amount_reference under unstated saying why/);
  assert.ok(!existsSync(path.join(refusedOut, "index.json")));
  // Through the worked-out levels: the increments world, whose run kept the increments only, with its reference planted as a
  // field the run did not save and that field's entry, as the writer would give them. The level cannot be worked out: said.
  const why = "planted by this test: a field the run did not save";
  const asField = (view) => {
    for (const item of view.records) if (item.field === "amount_increment") item.reference = { field: "amount_reference" };
    view.constants = view.constants.filter((item) => item.id !== "amount_reference");
    view.unstated.push({ id: "amount_reference", what: "view field", why });
  };
  const [unsaved, unsavedOut] = changed("field-increment", asField, "increments");
  assert.equal(unsaved.status, 0, unsaved.stderr);
  const left = open(unsavedOut, "increments");
  assert.deepEqual(validateReplay(left.file), []);
  assert.equal(left.record("amount.S"), undefined, "not packaged");
  assert.ok(left.view.derivation.includes(`Not packaged: amount (its increment amount_increment is stored over the field amount_reference, which the run did not save (${why}), so the adapter cannot add it).`));
  assert.ok(left.view.derivation.some((line) => line.includes(`amount_increment over the field amount_reference, which the run did not save (${why})`)));
  assert.ok(!left.view.derivation.some((line) => /(^|[^_])amount is amount_reference plus/.test(line)), "nothing is worked out over a field");
  assert.match(left.record("extracellular_amount.S").note, /^Worked out by the viewer: the run's fixed reference extracellular_amount_reference \(a named constant of the view\)/, "the other level, over its constant, is worked out as before");
  // ... and without the entry, refused.
  const [bare] = changed("field-increment-bare", (view) => {
    asField(view);
    view.unstated = view.unstated.filter((item) => item.id !== "amount_reference");
  }, "increments");
  assert.notEqual(bare.status, 0);
  assert.match(bare.stderr, /is stored over the field amount_reference \(its reference\), which the run did not save, and its view gives no entry for amount_reference under unstated saying why/);
  // A constant reference is worked out as before, and the subset world, whose records name none, states none.
  assert.match(open(newOut, "increments").record("amount.S").note, /^Worked out by the viewer: the run's fixed reference amount_reference \(a named constant of the view\)/);
  assert.equal(open(newOut, "subset").view.constants.some((item) => item.id === "amount_reference"), false);
  assert.equal(open(oldOut, "subset").view.constants.some((item) => item.id === "amount_reference"), true);
});

test("a key the adapter does not know is found and named, never refused; no older view has one", () => {
  const [result, out] = changed("unknown-keys", (view) => {
    view.planted_top = 1;
    view.run.planted_run = "x";
    view.records[0].planted_record = true;
    setOf(view, "cell").planted_set = [1];
  }, "secretion");
  assert.equal(result.status, 0, result.stderr);
  const { view } = open(out, "secretion");
  assert.ok(view.derivation.includes("The view gives what the adapter does not read, and none of it is packaged: the view: planted_top; its run: planted_run; the set cell: planted_set; its records: planted_record. Each is named here, never refused."));
  assert.equal(view.sets.find((item) => item.id === "cell").planted_set, undefined);
  for (const world of WORLDS.slice(0, 5)) {
    assert.ok(!open(oldOut, world).view.derivation.some((line) => line.startsWith("The view gives what the adapter does not read")), `${world} at b5d3faf0`);
    assert.ok(!open(newOut, world).view.derivation.some((line) => line.startsWith("The view gives what the adapter does not read")), `${world} at 89bd2ffb`);
  }
});
