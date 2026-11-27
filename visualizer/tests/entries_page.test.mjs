// The switch's entries on the page (schema/ENTRIES.md, docs/ENTRIES_DESIGN.md section 6): the
// ladder's words, the switch's rows, a species with two cell types (made up here: no species of
// the repository has a second type yet), the model system's card, the seam by which a view of a
// model system is mounted (src/ui/entry_views.js), and the run files published beside the page.
// Nothing needs a browser; the real-click checks are tools/check_species.mjs (CASE=model).
//
//   node --test tests/entries_page.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { ROOT, modelFiles, shapeFiles } from "../tools/lib/build_page.mjs";
import { CellLens } from "../src/lenses/cell.js";
import { EntryCardLens, entryId, levelId } from "../src/lenses/entry_card.js";
import { LADDER, MODELLED, notInEngine, modelSystems, modelSystemOf, cellTypesOf, cellTypeOf, switchRows, switchSections } from "../src/scene/entries.js";
import { registerEntryView, entryView, entryTab, makeEntryLens, fitView, mountStyles } from "../src/ui/entry_views.js";

const scene = JSON.parse(readFileSync(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));
const capabilities = scene.entities.filter((entity) => entity.kind === "capability");
const options = (raw) => [...raw.species.map((item) => [item.id, item.label, item.organism]), ...modelSystems(raw).map((item) => [item.id, item.label, item.is])];

/** The planarian with a second cell type of a made-up file: a neoblast-like cell that holds no junctions, proposed. */
function twoTypes() {
  const species = structuredClone(scene.species.find((item) => item.id === "planarian"));
  const own = cellTypeOf(species);
  const second = {
    id: "made-up",
    label: "A made-up cell type",
    own: false,
    modelled: { state: "proposed", text: "Nothing of it is in the engine: a made-up cell type of this test." },
    levels: own.levels.map((level) => (level.id === "cell" ? { ...level, label: "A made-up cell" } : level)),
    parts: { ...own.parts },
    capabilities: { ...own.capabilities, "cap.junctions": { place: "absent", why: "The made-up cell holds no junctions." } },
    facts: [{ label: "Made up", value: "for this test", sources: [] }],
  };
  species.cell_types = [own, second];
  species.default_cell_type = own.id;
  return { species, own, second, raw: { ...scene, species: scene.species.map((item) => (item.id === species.id ? species : item)) } };
}

/** A Cell view as far as its plan and its panel go, with no stage (as tests/cell_build.test.mjs plans one). */
function cellLens(species, type = null) {
  const lens = Object.create(CellLens.prototype);
  Object.assign(lens, {
    species, cellType: type || cellTypeOf(species), sizeMode: "schematic",
    model: { ofKind: (kind) => (kind === "capability" ? capabilities : []), get: (id) => scene.entities.find((item) => item.id === id) || null, raw: scene },
    capabilityByPart: new Map(capabilities.map((entity) => [entity.part, entity])),
    leftOut: new Set((scene.left_out || []).map((item) => item.part).filter(Boolean)),
    flux: { has: () => false, inPanel: (entity) => entity },
    cells: {},
  });
  lens.plan();
  return lens;
}

test("the ladder's five words, and nothing of an entry is in the engine short of modelled", () => {
  assert.deepEqual(LADDER, ["generic", "proposed", "planned", "designed", "modelled"]);
  assert.deepEqual(Object.keys(MODELLED), LADDER);
  for (const state of ["proposed", "planned", "designed"]) {
    assert.match(MODELLED[state], /, not modelled$/);
    assert.ok(notInEngine({ state }));
  }
  assert.ok(!notInEngine({ state: "generic" }) && !notInEngine({ state: "modelled" }) && !notInEngine(undefined));
});

test("the switch's rows: every species and model system once, with its line and word, and no cell-type row where a species has one type", () => {
  const rows = switchRows(scene, options(scene));
  assert.equal(rows.length, scene.species.length + modelSystems(scene).length);
  for (const item of scene.species) {
    assert.equal(cellTypesOf(item).length, 1, `${item.id}: one cell type today`);
    const row = rows.find((one) => one.id === item.id);
    assert.equal(row.kind, "species");
    assert.equal(row.word, MODELLED[item.modelled.state]);
    assert.equal(row.organism, item.organism);
  }
  for (const item of modelSystems(scene)) {
    const row = rows.find((one) => one.id === item.id);
    assert.equal(row.kind, "model system");
    assert.equal(row.organism, item.is, "a model system's line is what it is, not an organism");
    assert.equal(row.group, item.group);
    assert.equal(row.word, MODELLED[item.modelled.state]);
    // "Modelled" only where the entry names its registered model and cites the record that says so (schema/ENTRIES.md).
    assert.ok(row.word !== "Modelled" || (/@\d+$/.test(item.modelled.model || "") && item.modelled.record?.length > 0), `${item.id}: "Modelled" with no registered model or no line of the record`);
    assert.ok(!scene.species.some((one) => one.group === item.group), "a model system stands under a heading of its own");
  }
});

test("a species with two cell types: a row for each under it, the second with its own word", () => {
  const { species, own, second, raw } = twoTypes();
  const rows = switchRows(raw, options(raw));
  const at = rows.findIndex((row) => row.id === species.id);
  assert.deepEqual(rows.slice(at, at + 3).map((row) => [row.id, row.kind]), [[species.id, "species"], [`${species.id}.${own.id}`, "cell type"], [`${species.id}.${second.id}`, "cell type"]]);
  const row = rows[at + 2];
  assert.equal(row.label, `${species.label}, ${second.label}`);
  assert.equal(row.word, "Proposed, not modelled");
  assert.equal(row.group, rows[at].group);
  assert.equal(cellTypeOf(species).id, own.id, "the default is the species' own");
  assert.equal(cellTypeOf(species, "no-such-type").id, own.id, "an unknown type shows the default");
});

test("the switch nests eukaryote groups and leaves Archaea open to future model entries", () => {
  const rows = switchRows(scene, options(scene));
  const sections = switchSections(rows);
  assert.deepEqual(sections.map((section) => section.name), ["Eukarya", "Bacteria", "Origin of life"]);
  const eukarya = sections[0].groups;
  assert.deepEqual(eukarya.map((group) => group.name), ["Animals", "Plants", "Amoebozoa"]);
  assert.deepEqual(eukarya[2].rows.map((row) => row.id), ["physarum"]);
  assert.equal(new Set(sections.flatMap((section) => section.groups.flatMap((group) => group.rows.map((row) => row.id)))).size, rows.length);
  const haloferax = { id: "haloferax", group: "Archaea" };
  const expanded = switchSections([...rows, haloferax]);
  assert.deepEqual(expanded.map((section) => section.name), ["Eukarya", "Bacteria", "Archaea", "Origin of life"]);
  assert.deepEqual(expanded[2].groups, [{ name: "Archaea", rows: [haloferax] }]);
});

test("a species with two cell types: the Cell view plans the type shown, and its panel lists both", () => {
  const { species, own, second } = twoTypes();
  const first = cellLens(species, own), other = cellLens(species, second);
  assert.ok(!first.absent.has("cap.junctions"), "the planarian's own cell holds its junctions");
  assert.equal(other.absent.get("cap.junctions"), "The made-up cell holds no junctions.");
  assert.equal(other.levels.cell.label, "A made-up cell", "its own cell level");
  assert.equal(other.levels.organism, first.levels.organism, "the body stays the species'");
  const panel = other.describe(`species:${species.id}`);
  const types = panel.sections.find((section) => section.title === "Its cell types");
  assert.deepEqual(types.items.map((item) => [item.label, item.detail]), [[own.label, MODELLED[species.modelled.state]], [second.label, "Proposed, not modelled"]]);
  assert.deepEqual(panel.sections.find((section) => section.title === "Its cell").items.map((item) => item.label), ["Made up"]);
  // With one type the panel has no such list.
  assert.ok(!cellLens(scene.species.find((item) => item.id === "planarian")).describe("species:planarian").sections.some((section) => section.title === "Its cell types"));
});

test("a model system's card: its levels on the rail, its word in the caveat and the panel, in the entry's own words, nothing of a cell", () => {
  const entry = modelSystems(scene)[0];
  assert.ok(entry, "the scene carries a model system");
  assert.equal(modelSystemOf(scene, entry.id), entry);
  assert.equal(modelSystemOf(scene, "planarian"), null, "a species is not a model system");
  const stage = { scene: { add() {}, remove() {} }, invalidate() {} };
  const card = new EntryCardLens(stage, null, null, entry);
  const word = MODELLED[entry.modelled.state];
  const chrome = card.chrome();
  assert.deepEqual(chrome.rail.map((stop) => stop.id), entry.levels.map((level) => level.id));
  assert.equal(chrome.railTitle, "Level");
  assert.ok(chrome.caveat.startsWith(`${entry.label}: ${word.charAt(0).toLowerCase()}${word.slice(1)}.`), chrome.caveat);
  assert.match(chrome.caveat, /not on this page yet/);
  assert.equal(chrome.card.heading, entry.label);
  assert.equal(chrome.card.organism, entry.is);
  assert.ok(!chrome.view, "no cell's colour or size switches");
  const panel = card.describe(entryId(entry));
  assert.equal(panel.eyebrow, "Model system");
  assert.ok(panel.chips.some((chip) => chip.label === word));
  // What Cells models of it, in the entry's own words.
  assert.equal(panel.plain, entry.modelled.text);
  assert.deepEqual(panel.sections.find((section) => section.title === "What the word rests on").items.map((item) => item.label), entry.modelled.record.map((item) => item.path));
  // Its sourced notes, word for word, each with what it cites (schema/ENTRIES.md, "Notes").
  const noted = new EntryCardLens(stage, null, null, { ...entry, notes: [{ id: "a", label: "A note", text: "Its words, as the record says them.", record: [{ path: "docs/DECISIONS.md", where: "D1" }] }] }).describe(entryId(entry));
  assert.deepEqual(noted.sections.find((section) => section.title === "Notes").items, [{ label: "A note", lines: ["Its words, as the record says them."], note: "It rests on docs/DECISIONS.md (D1)." }]);
  assert.equal(panel.sections.some((section) => section.title === "Notes"), Boolean(entry.notes?.length));
  // A level of the rail opens its panel.
  const shown = [];
  card.onShown = (id) => shown.push(id);
  card.goToScale(entry.levels.at(-1).id);
  assert.deepEqual(shown, [levelId(entry, entry.levels.at(-1).id)]);
  assert.ok(card.has(shown[0]) && card.has(entryId(entry)) && !card.has("cap.membrane"));
  assert.equal(card.describe(shown[0]).label, entry.levels.at(-1).label);
  assert.ok(card.entities().length === entry.levels.length + 1);
});

test("the seam: a view registered for a kind is made from the entry and its run files once read; until then, and on a failure, the card stands", async () => {
  const entry = { id: "made-up", label: "A made-up model system", is: "A model, not an organism", group: "Made up", levels: [{ id: "assembly", label: "One assembly" }], view: { kind: "made-up-kind" }, runs: [{ file: "data/x/run.json", label: "A run", kind: "example", path: "models/made-up/run.json" }], modelled: { state: "proposed", text: "Nothing of it is in the engine." } };
  assert.throws(() => registerEntryView("made-up-kind", {}), /make/);
  assert.equal(entryView("made-up-kind"), null);
  assert.deepEqual(entryTab(entry), { label: "Model system", short: "Model" });
  const alone = makeEntryLens({}, null, null, entry, { loader: async () => assert.fail("nothing is read without a view") });
  assert.ok(alone.lens instanceof EntryCardLens && alone.ready === null);

  const made = [];
  registerEntryView("made-up-kind", { label: "One assembly", short: "Assembly", make: (stage, model, labels, given) => (made.push(given), { id: "made-up-view" }) });
  assert.deepEqual(entryTab(entry), { label: "One assembly", short: "Assembly" });
  const read = [];
  const { lens, ready } = makeEntryLens({}, null, null, entry, { loader: async (where) => (read.push(where), { format: "made-up", frames: [] }) });
  assert.match(lens.chrome().caveat, /its run file is being read/);
  const view = await ready;
  assert.equal(view.id, "made-up-view");
  assert.deepEqual(read, ["models/made-up/run.json"], "each run is read from the path the scene gives it");
  assert.equal(made[0].entry, entry);
  assert.deepEqual(made[0].runs.map((run) => [run.label, run.data.format]), [["A run", "made-up"]]);

  const failing = makeEntryLens({}, null, null, entry, { loader: async () => { throw new Error("models/made-up/run.json answered 404"); } });
  let redrawn = 0;
  failing.lens.onChrome = () => redrawn++;
  assert.equal(await failing.ready, null);
  assert.equal(redrawn, 1);
  assert.match(failing.lens.chrome().caveat, /could not be shown: models\/made-up\/run\.json answered 404/);
});

test("the seam fits a view that knows nothing of the viewer: its levels on the rail, its other choices on the card, its styles put in once", async () => {
  // A view with the origin view's shape (src/lenses/lineage.js): levels() and setLevel(), a card with a pair of forms, a legend of keys with no counts.
  const calls = [];
  const view = {
    level: "assembly",
    levels() { return [{ id: "molecules", label: "Molecules", active: this.level === "molecules" }, { id: "assembly", label: "One assembly", active: this.level === "assembly" }]; },
    setLevel(id) { calls.push(["level", id]); this.level = id; },
    setPair(on) { calls.push(["pair", on]); },
    chrome() {
      return {
        card: { heading: "A made-up view", modes: { label: "Packing", options: [["a", "A"]], active: "a" }, pair: { label: "The two forms", options: [["one", "One"], ["pair", "Both"]], active: "one" }, sources: [{ path: "schema/ASSEMBLY_RUN.md", where: "what the view reads of a run" }] },
        legend: { title: "Molecule types", items: [{ label: "a key with no count", swatch: "x" }], note: { text: "Example: invented numbers." } },
        timeline: { player: { run: null }, eventWord: "fission" },
      };
    },
  };
  const entry = { id: "made-up", label: "A made-up model system", is: "A model, not an organism", levels: [{ id: "molecules", shows: "Its molecules." }, { id: "assembly", shows: "One assembly." }] };
  const fitted = fitView(view, entry, { choices: { pair: (lens, value) => lens.setPair(value === "pair"), compare: (lens, value) => lens.setCompare(value) } });
  assert.equal(fitted, view, "the view itself, fitted");
  let chrome = view.chrome();
  assert.deepEqual(chrome.rail, [{ id: "molecules", label: "Molecules", title: "Its molecules." }, { id: "assembly", label: "One assembly", title: "One assembly." }]);
  assert.equal(chrome.railActive, "assembly");
  assert.equal(chrome.railTitle, "Level");
  view.goToScale("molecules");
  assert.equal(view.chrome().railActive, "molecules");
  assert.deepEqual(chrome.card.choices.map((choice) => [choice.key, choice.label, choice.active]), [["pair", "The two forms", "one"]], "a choice the card does not give is not offered");
  chrome.card.choices[0].set("pair");
  assert.deepEqual(calls, [["level", "molecules"], ["pair", true]]);
  assert.equal(chrome.card.organism, entry.is);
  assert.deepEqual(chrome.card.stats, []);
  assert.deepEqual(chrome.card.sources, [{ name: "schema/ASSEMBLY_RUN.md", licence: "what the view reads of a run" }]);
  assert.equal(chrome.card.modes.label, "Packing", "modes and marks stay the card's own");
  assert.equal(chrome.legend.note.text, "Example: invented numbers.");
  assert.equal(chrome.timeline.eventWord, "fission");
  for (const name of ["setHover", "setIsolate", "setSelection", "focus", "applyPalette", "has", "sections", "entities", "update"]) assert.equal(typeof view[name], "function", name);
  // The entry's own panels stay the card's, whatever view is shown: the statement beside the switch opens them.
  const full = { ...entry, group: "Made up", modelled: { state: "designed", text: "Nothing of it is in the engine.", record: [{ path: "docs/DECISIONS.md", where: "D1" }] } };
  const selected = [];
  const own = fitView({ has: (id) => id === "own:part", describe: (id) => (id === "own:part" ? { id, label: "Its own part" } : null), sections: () => [{ label: "Its parts", entities: [{ id: "own:part" }] }], setSelection: (id) => selected.push(id), chrome: () => ({}) }, full);
  own.setSelection("model:made-up");
  own.setSelection("own:part");
  assert.deepEqual(selected, [null, "own:part"], "the card's ids reach the view as nothing chosen");
  assert.ok(own.has("model:made-up") && own.has("model:made-up:level:assembly") && own.has("own:part") && !own.has("cap.membrane"));
  assert.equal(own.describe("model:made-up").eyebrow, "Model system");
  assert.equal(own.describe("own:part").label, "Its own part");
  assert.deepEqual(own.sections().map((section) => section.label), ["Its parts", "Model system"]);
  assert.deepEqual(own.entities().map((item) => item.id), ["own:part", "model:made-up"]);
  // Where its chrome gives no caveat, the line under the picture gives the entry's word.
  assert.equal(own.chrome().caveat, "A made-up model system: designed, not modelled.");
  assert.equal(fitView({ chrome: () => ({ caveat: "Its own words." }) }, full).chrome().caveat, "Its own words.");
  assert.equal(fitView({ chrome: () => ({ timeline: { player: {} } }) }, full).chrome().caveat, undefined, "no caveat over a timeline, which stands in its place");
  // Its styles, each once: tokens into the document's head, rules into the viewer's shadow root.
  const place = () => ({ children: [], append(child) { this.children.push(child); }, querySelector(selector) { return this.children.find((child) => selector.includes(`"${child.dataset.entryView}"`)) || null; } });
  const document = { head: place(), createElement: () => ({ dataset: {}, textContent: "" }) };
  const root = place();
  for (let twice = 0; twice < 2; twice++) mountStyles("made-up-kind", { page: ":root { --made-up: 1; }", shadow: ".made-up {}" }, { root, document });
  assert.deepEqual([document.head.children.map((style) => style.textContent), root.children.map((style) => style.textContent)], [[":root { --made-up: 1; }"], [".made-up {}"]]);
  // Through the registry: autoplay is handed over, and the view comes back fitted, its styles in.
  const given = [];
  registerEntryView("made-up-fitted", { make: (stage, model, labels, options) => (given.push(options), { levels: () => [{ id: "assembly", label: "One assembly", active: true }], chrome: () => ({}) }), styles: { shadow: ".fitted {}" } });
  const shadow = place();
  const made = await makeEntryLens({}, null, null, { ...entry, view: { kind: "made-up-fitted" }, runs: [] }, { root: shadow, document, autoplay: false }).ready;
  assert.equal(given[0].autoplay, false);
  assert.deepEqual(made.chrome().rail.map((stop) => stop.id), ["assembly"]);
  assert.deepEqual(shadow.children.map((style) => style.textContent), [".fitted {}"]);
});

test("a model system's run files are published beside the page, at the path the scene gives each", async () => {
  const { files, problems } = await modelFiles(scene);
  assert.deepEqual(problems, []);
  const runs = modelSystems(scene).flatMap((item) => (item.runs || []).map((run) => ({ ...run, model: item.id })));
  assert.deepEqual(files.map((file) => file.path), runs.map((run) => run.path));
  for (const run of runs) assert.match(run.path, new RegExp(`^models/${run.model}/[a-z0-9_.-]+\\.json$`));
  const broken = await modelFiles({ models: [{ id: "x", runs: [{ file: "data/no/such.json", label: "A run", path: "models/x/such.json" }, { file: "elsewhere.json", label: "Another", path: "../x.json" }] }] });
  assert.equal(broken.files.length, 0);
  assert.equal(broken.problems.length, 2);
});

test("a machine's shapes are published beside the page, one file a machine, at shapes/<species>.<machine>.json (schema/MACHINE_SHAPES.md)", async () => {
  const { files, problems } = await shapeFiles();
  assert.deepEqual(problems, []);
  assert.ok(files.length >= 6, `${files.length} shape files`);
  for (const file of files) {
    assert.match(file.path, /^shapes\/[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/);
    assert.equal(path.relative(ROOT, file.source), path.join("data", "catalogue", "shapes", path.basename(file.path)));
  }
  // A folder that is not there publishes nothing, and says nothing is wrong.
  assert.deepEqual(await shapeFiles({ shapesDir: path.join(ROOT, "data", "no-such-folder") }), { files: [], problems: [] });
});
