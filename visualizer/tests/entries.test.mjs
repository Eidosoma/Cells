// The entries of the species switch, in three kinds (schema/ENTRIES.md, schema/CELL_TYPES.md,
// schema/MODEL_SYSTEMS.md), as tools/lib/entries.py reads them; the scene is built through it.
// What the page shows of them is tests/entries_page.test.mjs's.
//
//   - a made-up species with two cell types, one extending the other, and a made-up model
//     system are read from files alone (tests/entries-fixtures/);
//   - every breach is warned of, and the entry is left out (on parsed data, so no file is written);
//   - the repository's species are read by it exactly as tools/lib/species.py reads them, each
//     with one cell type of its own;
//   - the GARD entry holds to its contract, says what it is, and claims nothing of the engine.
//
//   node --test tests/entries.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const FIXTURES = path.join(ROOT, "tests", "entries-fixtures"); // beside tests/fixtures/, which holds what the run-fixture tool writes
const overlay = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const CAPABILITIES = Object.fromEntries(overlay.capabilities.map((item) => [item.id, item.scale]));
const json = (file) => JSON.parse(readFileSync(file, "utf8"));
const copy = (value) => JSON.parse(JSON.stringify(value));

// The reader, called as the build will call it: a request on its standard input, the answer on its output.
const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import entries, species
def answer(request):
    if request["mode"] == "folders":
        found, shapes, models, warnings, remarks = entries.read_entries(request["species"], request.get("cells"), request.get("models"), request["capabilities"], tracked=request.get("tracked"), own=request.get("own"))
        plain = species.read_species(request["species"], request["capabilities"])
        return {"species": found, "models": models, "warnings": warnings, "remarks": remarks, "plain": {"species": plain[0], "warnings": plain[2]}}
    found, models, warnings, remarks = entries.check(request["species"], request["raw"], request["cells"], request["models"], request["capabilities"], tracked=request.get("tracked"), own=request.get("own"))
    return {"species": found, "models": models, "warnings": warnings, "remarks": remarks}
print(json.dumps([answer(request) for request in json.load(sys.stdin)]))
`;
/** Each request answered by one run of the reader; one request or a list of them. */
function ask(request) {
  const many = Array.isArray(request) ? request : [request];
  const run = spawnSync("python3", ["-c", READER, path.join(ROOT, "tools")], { input: JSON.stringify(many.map((one) => ({ capabilities: CAPABILITIES, ...one }))), encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const answers = JSON.parse(run.stdout);
  return Array.isArray(request) ? answers : answers[0];
}

// The made-up files, read once: the folders' answer, and the parts for the parsed checks.
const TRACKED = ["docs/DECISIONS.md"];
const sound = ask({ mode: "folders", species: path.join(FIXTURES, "species"), cells: path.join(FIXTURES, "cells"), models: path.join(FIXTURES, "models"), tracked: TRACKED, own: FIXTURES });
const raw = { brightfin: json(path.join(FIXTURES, "species", "brightfin.json")) };
const cellFiles = Object.fromEntries(readdirSync(path.join(FIXTURES, "cells")).map((name) => [name, json(path.join(FIXTURES, "cells", name))]));
const modelFiles = Object.fromEntries(readdirSync(path.join(FIXTURES, "models")).map((name) => [name, json(path.join(FIXTURES, "models", name))]));
/** A request on the made-up files as parsed, after a change to them. */
const changed = (change = () => {}) => {
  const request = { mode: "parsed", species: copy(sound.plain.species), raw: copy(raw), cells: copy(cellFiles), models: copy(modelFiles), tracked: TRACKED, own: FIXTURES };
  change(request);
  return request;
};
const parsed = (change) => ask(changed(change));

test("a made-up species with two cell types, one extending the other, and a made-up model system are read from files alone", () => {
  assert.deepEqual(sound.warnings, []);
  const [brightfin] = sound.species;
  assert.deepEqual(brightfin.cell_types.map((item) => [item.id, item.label, item.modelled.state]), [["generic", "Generic cell", "generic"], ["ciliated", "Ciliated cell", "planned"], ["ciliated-dense", "Ciliated cell, dense", "planned"]]);
  assert.equal(brightfin.default_cell_type, "generic");
  const [own, ciliated, dense] = brightfin.cell_types;
  assert.equal(own.own, true, "the species' own cell block is its first cell type");
  assert.deepEqual(own.levels.map((level) => level.id), ["cell", "tissue"]);
  assert.deepEqual(own.parts, raw.brightfin.cell.parts);
  // The variant takes what it leaves out from its parent, and keeps its own name, place and difference.
  for (const key of ["levels", "parts", "capabilities", "engine", "facts", "sources", "modelled"]) assert.deepEqual(dense[key], ciliated[key], `the variant takes its parent's ${key}`);
  assert.equal(dense.order, 21);
  assert.equal(dense.differs.in, "parameters");
  // The model system, with the labels of its view's levels where the file gives none.
  assert.deepEqual(sound.models.map((item) => [item.id, item.kind, item.group]), [["toyworld", "model system", "Origin of life"]]);
  assert.deepEqual(sound.models[0].levels.map((level) => [level.id, level.label]), [["molecules", "Molecules"], ["assembly", "One assembly"], ["lineage", "Lineages"]]);
  // Its sourced notes (schema/ENTRIES.md, "Notes"), carried as the file gives them.
  assert.deepEqual(sound.models[0].notes, modelFiles["toyworld.json"].notes);
});

test("every breach is warned of, and the entry is left out", () => {
  const cell = (name, change) => (request) => change(request.cells[`brightfin.${name}.json`], request);
  const model = (change) => (request) => change(request.models["toyworld.json"], request);
  const cases = [
    // A cell type.
    ["a cell type of another format", cell("ciliated", (data) => (data.format = "cells.visualizer.cell@1")), /its format is not cells\.visualizer\.cell_type@1/],
    ["a file named apart from its id", cell("ciliated", (data) => (data.id = "ciliate")), /named <species>\.<id>\.json/],
    ["a level that is the species'", cell("ciliated", (data) => data.levels.push({ id: "organ" })), /gives only its own levels/],
    ["a part the viewer cannot draw", cell("ciliated", (data) => (data.parts.cilia = true)), /cannot draw the part cilia/],
    ["a capability the map does not have", cell("ciliated", (data) => (data.capabilities["cap.beating"] = { place: "present" })), /not a capability of the map/],
    ["a word above what the record holds: designed, with no design note", cell("ciliated", (data) => (data.modelled.state = "designed")), /gives its design note's path/],
    ["a cell type of its own file that is generic", cell("ciliated", (data) => (data.modelled = { state: "generic", text: "A generic stand-in." })), /not generic: only a species' own cell is/],
    ["a capability designed in this cell with no design note", cell("ciliated", (data) => (data.capabilities["cap.channels"].state = "designed")), /cap\.channels: a cell type that is designed gives its design note's path/],
    ["a design note on a development branch", cell("ciliated", (data) => Object.assign(data.modelled, { state: "designed", design: "docs/TOY_DESIGN.md" })), /not a tracked file of main/],
    ["a citation with a branch", cell("ciliated", (data) => (data.modelled.record[0].branch = "toy-design")), /takes path and where only/],
    ["a citation of a file main does not track", cell("ciliated", (data) => (data.modelled.record[0].path = "docs/TOY_DESIGN.md")), /not a tracked file of main/],
    ["a viewer's note that is not there", cell("ciliated", (data) => (data.modelled.record[0].path = "visualizer/docs/NOWHERE.md")), /not a file of the viewer's folder/],
    ["a word with no record", cell("ciliated", (data) => delete data.modelled.record), /cites the record behind the word/],
    ["a fact on a source that is not permissive", cell("ciliated", (data) => Object.assign(data.sources.made, { licence: "CC BY-NC 4.0", class: "non-commercial" })), /not permissive/],
    ["a class that does not follow from the licence", cell("ciliated", (data) => (data.sources.made.class = "no stated terms")), /does not follow from its licence/],
    ["a binding to the engine not marked provisional", cell("ciliated", (data) => delete data.engine.provisional), /marked provisional/],
    ["a variant that does not say how it differs", cell("ciliated-dense", (data) => delete data.differs), /says how it differs/],
    ["two variants that extend each other", (request) => { request.cells["brightfin.ciliated.json"].extends = "ciliated-dense"; request.cells["brightfin.ciliated.json"].differs = { in: "parameters", says: "A loop." }; }, /extend one another in a loop/],
    // A species' cell types.
    ["a cell type named with no file", (request) => request.raw.brightfin.cell_types.push("ghost"), /has no sound file/],
    ["a default that is not one of its types", (request) => (request.raw.brightfin.default_cell_type = "ghost"), /is not one of its cell types/],
    // A model system.
    ["a model system that is generic", model((data) => (data.modelled.state = "generic")), /one of proposed, planned, designed, modelled for a model system/],
    ["a model system with a species' id", model((data, request) => { data.id = "brightfin"; request.models = { "brightfin.json": data }; }), /a species' id/],
    ["a model system with a taxon", model((data) => (data.taxon = 1)), /not an organism: it takes no taxon/],
    ["a model system as the page's default", model((data) => (data.default = true)), /never the page's default/],
    ["a view the viewer does not have", model((data) => (data.view.kind = "rna-world")), /view\.kind is one of assembly/],
    ["a level of no view", model((data) => data.levels.push({ id: "cell" })), /come from its view's list/],
    ["levels out of order", model((data) => data.levels.reverse()), /stand in their view's order/],
    ["no assembly level", model((data) => data.levels.splice(1, 1)), /has no assembly level/],
    ["a clock that is not a label", model((data) => (data.clock = { base: "fission", says: "…", per_second: 4 })), /a label only/],
    ["a run of a kind not listed", model((data) => (data.runs = [{ file: "data/origin/run.json", label: "A run", kind: "result" }])), /kind one of example, development, experiment/],
    ["a run file that is not there", model((data) => (data.runs = [{ file: "data/origin/nowhere.json", label: "A run", kind: "example" }])), /is not there/],
    ["modelled with no registered model", model((data) => Object.assign(data.modelled, { state: "modelled", design: "docs/DECISIONS.md" })), /names its registered model/],
    // A note of an entry: sourced, as a word of the ladder is (schema/ENTRIES.md, "Notes").
    ["a note with no record", model((data) => delete data.notes[0].record), /notes\[0\] cites the record its words rest on/],
    ["a note citing a file main does not track", model((data) => (data.notes[0].record = [{ path: "docs/TOY_DESIGN.md", where: "All of it" }])), /notes\[0\]\.record\[0\] cites docs\/TOY_DESIGN\.md, which is not a tracked file of main/],
    ["a note citing a branch", model((data) => (data.notes[0].record[0].branch = "toy-design")), /notes\[0\]\.record\[0\] takes path and where only/],
    ["a note with no words", model((data) => (data.notes[0].text = " ")), /notes\[0\] has no text/],
    ["a note with a key it does not take", model((data) => (data.notes[0].sources = ["made"])), /notes\[0\] takes id, label, text and record/],
    ["two notes of one id", model((data) => data.notes.push(copy(data.notes[0]))), /two notes have the id 'made-up'/],
    ["a cell type's note with no record", cell("ciliated", (data) => (data.notes = [{ id: "a", label: "A note", text: "Words." }])), /notes\[0\] cites the record/],
  ];
  const results = ask(cases.map(([, change]) => changed(change)));
  cases.forEach(([what, , pattern], index) => assert.ok(results[index].warnings.some((line) => pattern.test(line)), `${what}: ${JSON.stringify(results[index].warnings)}`));
  // A breach leaves the entry out, and only it.
  const broken = parsed(model((data) => (data.view.kind = "rna-world")));
  assert.deepEqual(broken.models, []);
  assert.equal(broken.species.length, 1);
  const leftCell = parsed(cell("ciliated-dense", (data) => delete data.differs));
  assert.deepEqual(leftCell.species[0].cell_types.map((item) => item.id), ["generic", "ciliated"], "a cell type with a breach is left out alone; its species stays, with its other types");
  const designed = parsed(cell("ciliated", (data) => Object.assign(data.capabilities["cap.channels"], { state: "designed", design: "docs/DECISIONS.md" })));
  assert.equal(designed.species[0].cell_types.length, 3, "a capability's word in this cell may give the design note its word asks for");
});

test("the repository's species are read exactly as the species reader reads them, each with one cell type of its own", () => {
  const read = ask({ mode: "folders", species: path.join(ROOT, "data", "species"), cells: path.join(ROOT, "data", "cells") });
  // Whatever files are there, the mouse's included: the entries reader warns of nothing the species reader does not.
  assert.deepEqual(read.warnings.filter((line) => !read.plain.warnings.includes(line)), [], "no warning beyond the species reader's own");
  assert.deepEqual(read.species.map((item) => item.id), read.plain.species.map((item) => item.id), "the same species, in the same order");
  for (const [index, item] of read.species.entries()) {
    const { cell_types: types, default_cell_type: chosen, ...rest } = item;
    assert.deepEqual(rest, read.plain.species[index], `${item.id}: everything the species reader gives, unchanged`);
    assert.equal(types[0].own, true, `${item.id}: its first cell type is its own cell block`);
    assert.ok(types.map((type) => type.id).includes(chosen), `${item.id}: it opens on one of its cell types`);
    assert.deepEqual(types[0].parts, item.cell.parts);
    assert.deepEqual(types[0].levels, item.levels.filter((level) => ["cell", "tissue"].includes(level.id)));
    assert.equal(types[0].label, item.modelled.state === "generic" ? "Generic cell" : "Its cell");
  }
});

test("the GARD entry is a model, not an organism, under Origin of life, and claims of the engine only what the record says", (t) => {
  // The paths it cites are held against main's tracked files where the main checkout can be asked.
  const common = spawnSync("git", ["-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8" }).stdout.trim();
  const main = common ? path.dirname(common) : null;
  const listed = main && existsSync(path.join(main, "src", "cells")) ? spawnSync("git", ["-C", main, "ls-files"], { encoding: "utf8" }).stdout.split("\n").filter(Boolean) : null;
  if (!listed) t.diagnostic("no main checkout to ask: the cited paths of main are not held to its tracked files here");
  const read = ask({ mode: "folders", species: path.join(ROOT, "data", "species"), models: path.join(ROOT, "data", "models"), tracked: listed, own: ROOT });
  assert.deepEqual(read.warnings.filter((line) => line.startsWith("entry gard.json")), []);
  const gard = read.models.find((item) => item.id === "gard");
  assert.ok(gard, "the GARD entry is read");
  assert.equal(gard.group, "Origin of life");
  assert.equal(gard.is, "A model, not an organism");
  assert.deepEqual(gard.levels.map((level) => [level.id, level.label]), [["molecules", "Molecules"], ["assembly", "One assembly"], ["population", "Population"], ["lineage", "Lineages"]]);
  assert.equal(gard.clock.base, "fission");
  // Its runs are files of the assembly view's own contract (schema/ASSEMBLY_RUN.md); the reader holds each to its format, its model and its clock.
  for (const run of gard.runs) assert.ok(existsSync(path.join(ROOT, run.file)), `${run.file} is there`);
  // What Cells models of it: modelled, for comparison only. Both parts of GARD's build are on main (PROGRESS, 17 November 2026; D192, D197)
  // and the engine's declarations (data/engine/declarations.json, written at main 93fc8c2c) list its model with its laws and operators. Its runs are not judged.
  assert.equal(gard.modelled.state, "modelled");
  assert.equal(gard.modelled.model, "cells.assembly_lineages@1", "the model the engine's declarations list");
  const { aliases } = JSON.parse(readFileSync(path.join(ROOT, "data", "engine", "viewer-ids.json"), "utf8"));
  const declared = JSON.parse(readFileSync(path.join(ROOT, "data", "engine", "declarations.json"), "utf8")).models.find((item) => item.id === aliases[gard.modelled.model]);
  assert.ok(declared && declared.rows.length > 0, "the model the entry names is a model of the engine's declarations, with its pieces");
  assert.equal(gard.modelled.design, "docs/GARD_DESIGN.md");
  assert.match(gard.modelled.text, /^Modelled for comparison only \(D197\)/);
  assert.match(gard.modelled.text, /development runs, not judged/);
  assert.doesNotMatch(gard.modelled.text, /qualified|judged to|validated|replicat/i, "no word above what the record holds");
  assert.deepEqual(gard.runs.map((run) => run.kind), ["development", "development"], "the engine's two runs, the passive law first");
  assert.match(gard.runs[0].file, /pair-consistent/);
  assert.match(gard.runs[1].file, /single-event/);
  for (const cited of ["visualizer/docs/ORIGIN_OF_LIFE.md", "docs/GARD_DESIGN.md", "docs/DECISIONS.md", "PROGRESS.md"]) assert.ok(gard.modelled.record.some((item) => item.path === cited), cited);
  assert.match(gard.modelled.record.find((item) => item.path === "docs/DECISIONS.md").where, /D192/);
  for (const item of gard.modelled.record) assert.deepEqual(Object.keys(item).sort(), ["path", "where"], "a citation names a tracked file and where in it, and no branch");
  // It binds to no name of the engine's design (no law, operator or record it would write), and names no branch.
  const words = readFileSync(path.join(ROOT, "data", "models", "gard.json"), "utf8").replace('"cells.visualizer.model_system@1"', "").replace('"model": "cells.assembly_lineages@1"', ""); // its own format and its registered model aside
  assert.ok(!/@\d|assembly_count|boundary_similarity|\bt0\d\d\b|gard-design/.test(words), "no law, operator or record of the engine's design, and no branch");
});
