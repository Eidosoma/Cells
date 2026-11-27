// The Machines catalogue (schema/MACHINE_CATALOGUE.md): the generated file is what its tool
// writes; every entry says only what its records give; the view lays it out at one scale and
// draws it within a ceiling; and the page offers it second among the tabs.
//
//   node --test tests/machine_catalogue.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { ROOT } from "../tools/lib/build_page.mjs";
import { Catalogue, CATALOGUE_FORMAT, pageId, kindOf } from "../src/lenses/machines_data.js";
import { describe, describePart, sections, doorsFor, doorWords, textSections, textDescribe, present, recordLines, levelsOf, lookedFor } from "../src/lenses/machines_card.js";
import { layoutOf, shapeOf, UNIT_NM, CARD } from "../src/lenses/machines_layout.js";
import { MachinesLens, MARKS } from "../src/lenses/machines.js";
import { organelles as organellesOfCell } from "../src/lenses/cell_structures.js";

const read = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
// The catalogue's core (what the page carries) and its species' benches (read beside the page), read together here.
const core = read("data/catalogue/catalogue.json");
const benchOf = (species) => read(`data/catalogue/benches/${species}.json`);
const raw = { ...core, entries: Object.keys(core.benches).flatMap((species) => benchOf(species).entries), by_protein: Object.fromEntries(Object.keys(core.benches).map((species) => [species, benchOf(species).by_protein])), none_found: Object.fromEntries(Object.keys(core.benches).map((species) => [species, benchOf(species).none_found || []])), organelles: Object.keys(core.benches).flatMap((species) => benchOf(species).organelles || []) };
const overlay = read("data/catalogue/overlay.json");
const scene = { ...read("data/architecture/architecture.scene.json"), catalogue: raw };
const motor = read("data/machines/ecoli.flagellar-motor.json");
const catalogue = new Catalogue(raw, scene);
const SPECIES = [...new Set([...raw.entries.map((entry) => entry.species), ...(scene.proteins.atlases || []).map((atlas) => atlas.id)])];
/** A word of a status the record has not given: none may stand on the page for a machine (D209). */
const CLAIMED = /(?<!not |no )\b(modelled|modeled|qualified|judged|designed|simulated)\b/i;
/** A catalogue in which the thale cress has no size in hand (no species has none since 17 November 2026): the all-cards case. */
const bare = { ...raw, entries: raw.entries.map((entry) => (entry.species === "thalecress" ? { ...entry, size: undefined } : entry)), unit_sizes: { ...raw.unit_sizes, species: raw.unit_sizes.species.filter((value) => value !== "thalecress") } };
const bareScene = { ...scene, catalogue: bare };
/** The catalogue's copy of a source of a species' own scan that is not permissive (CDD): it stands only as the species' scan record carries it, with the
 * record's terms and class (`gathered:<species>:scan_<key>`); tests/licence_classes.test.mjs holds that record against its register DECIDED. */
function scanCopy(key, source) {
  const [, species, own] = /^gathered:([^:]+):scan_(\w+)$/.exec(key) || [];
  const record = species && read("data/catalogue/gather.json").species[species]?.atlas?.scan?.record;
  const held = record ? read(record).sources?.[own] : null;
  return Boolean(held && held.licence === source?.licence && held.class === source?.class);
}

test("the catalogue is what its tool writes, from the files it names", () => {
  // The core and every bench are what the tool writes (`--check`), and together they are its whole catalogue.
  execFileSync("python3", [path.join(ROOT, "tools", "build_catalogue.py"), "--check"], { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  const written = execFileSync("python3", [path.join(ROOT, "tools", "build_catalogue.py"), "--out", "-"], { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });
  const whole = JSON.parse(written);
  assert.deepEqual(whole.entries, raw.entries);
  assert.deepEqual(whole.by_protein, raw.by_protein);
  assert.equal(raw.format, CATALOGUE_FORMAT);
  assert.ok(!/\d{2}:\d{2}:\d{2}/.test(written), "no clock time: the same inputs give the same bytes");
  for (const file of raw.made.from) assert.ok(readFileSync(path.join(ROOT, file)), file);
});

test("each entry is a kind of the catalogue, once for its species, and a machine with a closer view keeps that view's id", () => {
  const kinds = new Set(raw.kinds.map((kind) => kind.id));
  const seen = new Set();
  for (const entry of raw.entries) {
    assert.ok(kinds.has(entry.id), entry.id);
    assert.ok(!seen.has(`${entry.species}:${entry.id}`), `${entry.species} lists ${entry.id} twice`);
    seen.add(`${entry.species}:${entry.id}`);
    assert.ok(raw.groups.some((group) => group.id === raw.kinds.find((kind) => kind.id === entry.id).group));
    if (entry.closer) assert.equal(entry.closer.file, `machines/${entry.species}.${entry.id}.json`);
  }
  assert.equal(pageId("flagellar-motor"), `machine:${motor.id}`, "one machine, one identity: the catalogue's id is its closer view's");
  assert.equal(kindOf("machine:flagellar-motor:c-ring"), "flagellar-motor");
});

test("the Physarum bench links every archived experiment and attributes each resolved chain", () => {
  const { entries, by_protein } = benchOf("physarum");
  const records = entries.flatMap((entry) => entry.structures.map((row) => row.id));
  assert.equal(entries.length, 9);
  assert.equal(records.length, 74);
  assert.equal(new Set(records).size, 74);
  for (const entry of entries) {
    assert.equal(entry.size.surface.entry, entry.structures[0].id);
    assert.ok(entry.size.chains.every((chain) => chain.organism));
    const panel = describe(catalogue, "physarum", pageId(entry.id));
    const archive = panel.sections.find((section) => section.title === "Experimental structures");
    assert.equal(archive.items.length, entry.structures.length);
    assert.equal(archive.items[0].links[0].url, `https://www.rcsb.org/structure/${entry.size.surface.entry}`);
  }
  const id = pageId("actin-fragmin-complex");
  assert.ok(catalogue.passes(catalogue.item("physarum", id), "9L2N"));
  const complex = catalogue.item("physarum", id);
  assert.deepEqual(complex.size.chains.map((chain) => [chain.organism, chain.protein]).sort(), [["Gallus gallus", "P68139"], ["Physarum polycephalum", "Q94707"]]);
  const chicken = complex.size.chains.find((chain) => chain.protein === "P68139");
  const panel = describePart(catalogue, "physarum", id, chicken.id);
  assert.ok(panel.facts.some(([key, value]) => key === "Source organism" && value === "Gallus gallus"));
  assert.ok(!panel.doors.some((door) => door.lens === "proteins"));
  assert.equal(by_protein.P68139, undefined);
  assert.deepEqual(by_protein.P08053, [["myosin-ii-regulatory-domain", "deposited chain"]]);
});

test("every number stands on a permissive source the entry names, and a size is its species file's own, never a second number", () => {
  for (const entry of raw.entries) {
    for (const block of [entry.count, entry.size, entry.named].filter(Boolean)) {
      for (const key of block.sources || []) assert.ok(raw.sources[key]?.class === "permissive" || scanCopy(key, raw.sources[key]), `${entry.species} ${entry.id}: ${key}`);
    }
    if (entry.count) assert.ok(entry.count.sources.length && /\d/.test(entry.count.text), `${entry.species} ${entry.id}: a count with its sources`);
    if (entry.size?.shape === "rod") assert.ok(entry.size.long_nm.every((n) => entry.size.text.includes(String(n))), `${entry.species} ${entry.id}`);
    // A measured size is the species file's own statement of the part where it has one, else the viewer's measure that the
    // overlay names: the same numbers, from the tool's own output, never a second number beside the species file's.
    if (entry.size?.shape === "measured") {
      // The part of its cell that the overlay names for this machine (the ribosome's `cell.parts.ribosome`), where it names one.
      const named = overlay.species[entry.species]?.find((item) => item.kind === entry.id)?.size?.part;
      const part = named ? read(`data/species/${entry.species}.json`).cell.parts?.[named] : null;
      if (entry.size.from.startsWith("cell.parts.")) assert.deepEqual(entry.size.whole.across_nm, part.across_nm, `${entry.species} ${entry.id}`);
      else {
        assert.ok(!part, `${entry.species} ${entry.id}: the species' file states the part, so the overlay's measure is not to be read`);
        const record = read(entry.size.from);
        assert.equal(record.tool, "tools/measure_particle.py");
        assert.deepEqual(entry.size.whole.across_nm, record.measured[entry.size.entry].whole.across_nm);
        const measured = record.measured[entry.size.entry], named = measured.parts || measured;
        for (const body of entry.size.parts) assert.deepEqual([body.across_nm, body.centre_nm, body.axes], [named[body.id].across_nm, named[body.id].centre_nm, named[body.id].axes], body.id);
        for (const body of entry.size.chains || []) assert.ok(measured.chains.some((chain) => `chain-${chain.chain}` === body.id && chain.across_nm.join() === body.across_nm.join()), body.id);
      }
      // Its sources hold the structure it is measured from (an entry of the Protein Data Bank, CC0); a paper beside it (one a
      // species' file cites for what it says of the part) is permissive, as every source above.
      assert.ok(entry.size.sources.some((key) => /^CC0\b/.test(raw.sources[key].licence)), `${entry.species} ${entry.id}: a structure of the Protein Data Bank (CC0) among its sources`);
      assert.match(entry.size.says, /viewer's own measure|viewer's own/, "the size says it is the viewer's measure");
    }
  }
  // The overlay holds no size of its own: a size is read from a species' fact, from a part of its cell, or from the held file (a paper
  // under a non-commercial licence, which the tool checks the drawn size against: data/catalogue/held_sizes.json).
  for (const list of Object.values(overlay.species)) for (const item of list) if (item.size) assert.ok(item.size.part || item.size.fact || item.size.held || overlay.measures[item.size.measure], JSON.stringify(item.size));
  assert.ok(!JSON.stringify(overlay).includes("across_nm"), "no width is written in the overlay");
});

test("what Cells models of a machine is said only as a record says it: a status line of a kind's own is the ATP synthase's alone", () => {
  for (const record of Object.values(raw.records)) if (record.revision) assert.match(record.revision, /^[0-9a-f]{40}$/, "a link at a full revision, never a branch");
  for (const kind of raw.kinds) {
    for (const line of kind.records) {
      if (typeof line !== "object") continue;
      assert.equal(kind.id, "atp-synthase", `${kind.id} has a status line of its own`);
      assert.ok(raw.records[line.ref]?.revision, `${kind.id}: its line names a record read at a revision`);
      assert.match(line.says, /^Decided \d{1,2} [A-Z][a-z]+ \d{4} \(D\d+\): /, "said as what was decided, in plain past tense, with its date and its decision");
    }
  }
  for (const species of SPECIES) {
    for (const item of catalogue.of(species)) {
      const panel = describe(catalogue, species, item.id, { scene });
      // UniProt's own sentences are quoted as UniProt's (one says a domain "has been modeled": a structure's model, not Cells').
      const words = JSON.stringify({ ...panel, sections: (panel.sections || []).filter((section) => section.key !== "laws" && !section.title?.startsWith("Copies, in UniProt's words")) });
      assert.ok(!CLAIMED.test(words.replace(/E\. coli is proposed, not modelled/g, "")), `${species} ${item.id}: ${words.match(CLAIMED)?.[0]}`);
      const own = raw.kinds.find((kind) => kind.id === "atp-synthase").records.find((line) => typeof line === "object");
      if (item.kind) assert.equal(words.includes(own.status), item.id === "machine:atp-synthase", `${species} ${item.id}`);
      if (item.kind) for (const line of recordLines(catalogue, item, scene)) assert.ok(line.source.path, `${item.id}: a record line names its record`);
    }
  }
});

test("a species' machines: its own entries, and the law inventory's units its atlas found there", () => {
  const planarian = catalogue.of("planarian");
  assert.ok(planarian.some((item) => item.id === "machine:ribosome"), "every cell has ribosomes (docs/CELL_STRUCTURES.md)");
  const units = planarian.filter((item) => item.unit);
  assert.ok(units.length > 30 && units.every((item) => ["found", "different family"].includes(item.unit.species.planarian.finding)), String(units.length));
  assert.equal(catalogue.of("ecoli").filter((item) => item.unit).length, 0, "no unit of the inventory was found in E. coli");
  // The inventory's own species (human): every unit that names gene products, whatever its mapping; none that names none.
  const leftOut = raw.units_left_out.units;
  const withProducts = scene.entities.filter((entity) => entity.kind === "unit" && entity.group === "proteins" && !leftOut[entity.id] && entity.sections.some((section) => section.key === "products" && section.items?.length));
  assert.deepEqual(catalogue.of("human").filter((item) => item.unit).map((item) => item.id).sort(), withProducts.map((entity) => entity.id).sort());
  assert.deepEqual(catalogue.of("ecoli").filter((item) => item.sized).map((item) => item.id).sort(), ["machine:atp-synthase", "machine:flagellar-motor", "machine:hslv", "machine:lon", "machine:protein-translocon", "machine:ribosome", "machine:rna-polymerase"], "every E. coli machine but FtsH and the chemoreceptor array has a size: measured from a structure, or the motor's from its own file");
  assert.ok(!catalogue.item("ecoli", "machine:ftsh").sized, "no entry holds FtsH whole: a card");
  // The thale cress: its 80S drawn at the human's measure, and its ER calcium pump at the human's SERCA2b, the unit its atlas finds.
  assert.deepEqual(catalogue.of("thalecress").filter((item) => item.sized).map((item) => item.id).sort(), ["machine:ribosome", "unit.U41"]);
  // The list and the text page: every machine once, by group (what was looked for by family and not found, apart).
  for (const species of SPECIES) {
    const listed = sections(catalogue, species).filter((section) => section.label !== "Looked for by family, no candidate found" && section.label !== "Organelles").flatMap((section) => section.entities.map((entity) => entity.id));
    assert.deepEqual(listed.sort(), catalogue.of(species).map((item) => item.id).sort(), species);
    // Its organelles, on the shelf, under their own heading and in no group of machines (20 November 2026).
    assert.deepEqual(sections(catalogue, species).find((section) => section.label === "Organelles")?.entities.map((entity) => entity.id) || [], catalogue.organellesOf(species).map((item) => item.id), `${species}: its organelles, apart`);
    assert.deepEqual(textSections(scene, species), sections(catalogue, species));
  }
});

test("no unit that is no protein assembly is a machine of the catalogue, and the catalogue never says the atlas's count of units", () => {
  const units = new Map(scene.entities.filter((entity) => entity.kind === "unit" && entity.group === "proteins").map((entity) => [entity.id, entity]));
  for (const [id, why] of Object.entries(raw.units_left_out.units)) {
    const unit = units.get(id);
    assert.ok(unit, `${id} is a unit of the scene`);
    const products = unit.sections.some((section) => section.key === "products" && section.items?.length);
    assert.ok(/leak|permeab/i.test(`${unit.label} ${unit.eyebrow}`) || !products, `${id} (${unit.label}) is left out as ${why}`);
    for (const species of SPECIES) assert.ok(!catalogue.of(species).some((item) => item.id === id), `${species} holds ${id}`);
  }
  // Every unit with gene products that is not left out stands in the catalogue for the inventory's own species.
  for (const unit of units.values()) if (!raw.units_left_out.units[unit.id] && unit.sections.some((section) => section.key === "products" && section.items?.length)) assert.ok(catalogue.item("human", unit.id), unit.id);
  for (const species of SPECIES) assert.ok(!/\b48\b/.test(JSON.stringify(sections(catalogue, species))), species);
});

test("its doors: the Protein atlas where the species' own proteins hold the set, the closer view, the cell's ribosomes; and the doors other views get into it", () => {
  const ribosome = describe(catalogue, "ecoli", "machine:ribosome", { scene });
  assert.deepEqual(ribosome.doors.map((door) => door.label), ["Show its 59 proteins in the Protein atlas", "Show where it sits in the cell"]);
  assert.deepEqual(describe(catalogue, "ecoli", "machine:flagellar-motor", { scene }).doors.find((door) => door.look), { label: "Look closer in the cell", lens: "cell", look: "closer", machine: "flagellar-motor" });
  assert.equal(describe(catalogue, "mpneumoniae", "machine:ribosome", { scene }).doors.filter((door) => door.lens === "proteins").length, 0, "no set of its proteins is marked, so no door into the atlas");
  assert.ok(describe(catalogue, "mpneumoniae", "machine:attachment-organelle", { scene }).doors.some((door) => door.mark === "where" && door.value === "attachment organelle"));
  // A machine the species shown does not have says which do.
  const away = describe(catalogue, "planarian", "machine:flagellar-motor", { scene });
  assert.match(away.note, /E\. coli/);
  const { lens: lacking } = lensFor("planarian");
  assert.ok(lacking.has("machine:flagellar-motor") && !lacking.has("machine:no-such-machine") && !lacking.has("unit.U49"), "a machine the species lacks can be chosen, to say which species have it; a unit left out cannot");
  // Other views' doors: the Cell view's ribosomes, the closer view's machine, an atlas unit the species has.
  assert.deepEqual(doorsFor(scene.entities.find((entity) => entity.id === "cap.ribosomes"), scene, { species: "syn3a" }), [{ label: "Show it in the Machines catalogue", lens: "machines", value: "machine:ribosome" }]);
  assert.equal(doorsFor({ id: "machine:flagellar-motor" }, scene, { species: "ecoli" }).length, 1);
  assert.equal(doorsFor({ id: "machine:flagellar-motor:c-ring" }, scene, { species: "ecoli" }).length, 0, "a part of the closer view is not a machine of the catalogue");
  const unit = catalogue.of("planarian").find((item) => item.unit).unit;
  assert.equal(doorsFor(unit, scene, { species: "planarian" }).length, 1);
  assert.equal(doorsFor(unit, scene, { species: "ecoli" }).length, 0);
  // A unit is shown under Machines as the atlas shows it for the species, with the way into the atlas.
  const shown = present(unit, scene, "planarian");
  assert.ok(shown.finding && shown.doors.some((door) => door.select === unit.id && door.lens === "proteins"));
  assert.equal(textDescribe(scene, "machine:ribosome", "syn3a").label, "Ribosome");
});

test("the layout: one scale for every shape, a card's size the same for all, nothing outside its tray", () => {
  const ecoli = layoutOf(catalogue.of("ecoli"), raw.groups, { columns: 3, measured: { "machine:flagellar-motor": { w: 14, d: 6, h: 23 } } });
  assert.ok(ecoli.scale && ecoli.scale.length * UNIT_NM === ecoli.scale.nm);
  // A measured machine's bodies: each at its size, centre and axes; the room it takes is the box round them.
  const ribosome = ecoli.items.find((item) => item.id === "machine:ribosome");
  assert.equal(ribosome.shape.kind, "measured");
  const one = shapeOf({ size: { shape: "measured", parts: [{ across_nm: [20, 10, 6], centre_nm: [0, 0, 0], axes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] }] } });
  assert.deepEqual([one.w, one.h, one.d].map((n) => Math.round(n * UNIT_NM * 1000) / 1000), [20, 10, 6]);
  assert.ok(ribosome.shape.w * UNIT_NM >= 20 && ribosome.shape.w * UNIT_NM <= 30, `the ribosome's room: ${ribosome.shape.w * UNIT_NM} nm`);
  for (const item of ecoli.items) {
    const tray = ecoli.trays.find((value) => value.group === item.group);
    assert.ok(item.x - item.w / 2 >= tray.x - tray.w / 2 - 1e-6 && item.x + item.w / 2 <= tray.x + tray.w / 2 + 1e-6 && item.z - item.d / 2 >= tray.z - tray.d / 2 - 1e-6 && item.z + item.d / 2 <= tray.z + tray.d / 2 + 1e-6, `${item.id} in its tray`);
    if (item.type === "card") assert.deepEqual([item.w, item.d], [CARD.w, CARD.d]);
  }
  const rod = shapeOf(catalogue.item("mpneumoniae", "machine:attachment-organelle"));
  assert.equal(rod.length * UNIT_NM, 300, "drawn at the top of its range");
  // Cards never overlap.
  const planarian = layoutOf(catalogue.of("planarian"), raw.groups, { columns: 1 });
  const cards = planarian.items.filter((item) => item.type === "card");
  for (const a of cards) for (const b of cards) if (a !== b) assert.ok(Math.abs(a.x - b.x) >= CARD.w - 1e-6 || Math.abs(a.z - b.z) >= CARD.d - 1e-6, `${a.id} and ${b.id}`);
  // Shapes and cards in one tray never overlap either, and every one stays in its tray.
  for (const item of planarian.items) {
    const tray = planarian.trays.find((value) => value.group === item.group);
    assert.ok(item.x - item.w / 2 >= tray.x - tray.w / 2 - 1e-6 && item.x + item.w / 2 <= tray.x + tray.w / 2 + 1e-6 && item.z - item.d / 2 >= tray.z - tray.d / 2 - 1e-6 && item.z + item.d / 2 <= tray.z + tray.d / 2 + 1e-6, `${item.id} in its tray`);
    for (const other of planarian.items) if (other !== item && other.group === item.group) assert.ok(Math.abs(item.x - other.x) >= (item.w + other.w) / 2 - 1e-6 || Math.abs(item.z - other.z) >= (item.d + other.d) / 2 - 1e-6, `${item.id} and ${other.id}`);
  }
  assert.ok(planarian.scale, "the planarian's bench has shapes drawn to scale, and its scale bar");
  // In a tray, the shapes stand in front of the cards (nearer the eye), and a tray is no wider than its machines and name need.
  for (const tray of planarian.trays) {
    const inTray = planarian.items.filter((item) => item.group === tray.group);
    const cardsBack = Math.max(-Infinity, ...inTray.filter((item) => item.type === "card").map((item) => item.z + item.d / 2));
    for (const shape of inTray.filter((item) => item.type === "shape")) assert.ok(shape.z - shape.d / 2 > cardsBack, `${shape.id} in front of the cards`);
  }
  const proteinsTray = planarian.trays.find((tray) => tray.group === "proteins");
  assert.ok(proteinsTray.w * UNIT_NM <= 130, `the ribosome's tray: ${proteinsTray.w * UNIT_NM} nm wide`);
  // A group that stands behind (the particles whose job is not known: the vault is the largest shape on a bench) has its tray at the very
  // back, behind the units' tray, at one column and at three: nothing stands behind it to be hidden (19 November 2026).
  assert.equal(raw.groups.find((group) => group.id === "unknown").stands, "behind");
  for (const columns of [1, 3]) {
    const bench = layoutOf(catalogue.of("planarian"), raw.groups, { columns });
    const unknown = bench.trays.find((tray) => tray.group === "unknown"), ions = bench.trays.find((tray) => tray.group === "ions");
    assert.ok(unknown.z + unknown.d / 2 < ions.z - ions.d / 2, `${columns} across: the vault's tray stands behind the units'`);
    assert.ok(bench.trays.every((tray) => tray === unknown || tray.z - tray.d / 2 > unknown.z + unknown.d / 2), `${columns} across: no tray stands behind the vault's`);
    assert.ok(bench.bounds.minZ < unknown.z - unknown.d / 2, `${columns} across: the bench reaches past it`);
  }
  assert.equal(layoutOf(new Catalogue(bare, bareScene).of("thalecress"), raw.groups, { columns: 1 }).scale, null, "no scale bar where nothing is drawn to scale");
});

/** The view with stand-ins for the stage and the labels: no WebGL, the view only makes objects. */
function lensFor(species, { width = 1400, height = 900, raw: model = scene, load = null } = {}) {
  const shown = [];
  const labels = { add: (spec) => (shown.push(spec), spec), clear: () => shown.splice(0), remove() {} };
  const palette = { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", bioRibosome: "#4c4aa8", bioProtein: "#3f86e0", bioMito: "#f0874a", bioIon: "#37b58c", dark: false };
  const flights = [];
  const stage = { palette, scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(34, width / height, 0.1, 5000), width, height, reducedMotion: true, invalidate() {}, rig: { setView() {}, flyTo: (view) => flights.push(view) }, dress() {} };
  const lens = new MachinesLens(stage, { raw: model }, labels);
  // A bench read from beside the page by the test's own reader (the core alone in the page).
  if (load) {
    const read = lens.catalogue.loadBench.bind(lens.catalogue);
    lens.catalogue.loadBench = (name, options = {}) => read(name, { load, ...options });
  }
  lens.machines.set("machine:flagellar-motor", motor);
  lens.setSpecies(species);
  lens.activate();
  if (lens.relayout) lens.update(16);
  return { lens, stage, shown, flights };
}

test("the view draws within a ceiling, with the flagellar motor at each of its levels", () => {
  const { lens } = lensFor("ecoli");
  const outline = lens.cost();
  // The measured machines' outlines are one instanced mesh for the whole bench: a bench of many machines stays light on a phone.
  console.log(`# E. coli's bench: ${JSON.stringify(outline)}`);
  assert.ok(outline.draws <= 40 && outline.triangles <= 40000, JSON.stringify(outline));
  lens.setSelection("machine:flagellar-motor");
  assert.equal(lens.built.get("machine:flagellar-motor").level, 2, "chosen, it shows its parts");
  assert.ok(lens.has("machine:flagellar-motor:c-ring") || [...lens.built.get("machine:flagellar-motor").ids].length > 3, "its parts can be chosen under their closer view's ids");
  lens.setMode("3");
  const subunits = lens.cost();
  assert.ok(subunits.draws <= 120 && subunits.triangles <= 120000, JSON.stringify(subunits));
  const { lens: many } = lensFor("thalecress");
  const cards = many.cost();
  assert.ok(cards.draws <= 30 && cards.triangles <= 10000, `the cards are instances: ${JSON.stringify(cards)}`);
  // The animals' benches, at a phone's size: the outlines of every measured machine and unit are one draw, and a
  // chosen machine's bodies one more, however many chains it has (the innexin channel's sixteen).
  for (const species of ["human", "mouse", "planarian", "fruitfly"]) {
    const { lens: bench } = lensFor(species, { width: 390, height: 844 });
    const cost = bench.cost();
    console.log(`# ${species}'s bench at 390 by 844: ${JSON.stringify(cost)}`);
    assert.ok(cost.draws <= 40 && cost.triangles <= 40000, `${species}: ${JSON.stringify(cost)}`);
  }
  const { lens: planarian } = lensFor("planarian", { width: 390, height: 844 });
  const before = planarian.cost();
  planarian.setSelection("unit.U36");
  planarian.setMode("3");
  assert.equal(planarian.built.get("unit.U36").ids.size, 16, "the innexin channel's sixteen chains");
  const chosen = planarian.cost();
  assert.ok(chosen.draws <= before.draws + 2 && chosen.draws <= 40, `chosen, at its chains: ${JSON.stringify(chosen)} (the bench alone: ${JSON.stringify(before)})`);
});

test("the animals' benches: the machines they share, each measured from a structure, whose organism the panel names", () => {
  const sized = (species) => catalogue.of(species).filter((item) => item.size).map((item) => item.id).sort();
  for (const species of ["human", "mouse", "planarian", "fruitfly"]) {
    assert.ok(catalogue.item(species, "machine:ribosome").size.entry === "8YOP", `${species}: the eukaryotic ribosome, from a structure of the human one`);
    for (const unit of ["unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]) if (catalogue.item(species, unit)) assert.ok(catalogue.item(species, unit).size, `${species}: ${unit}`);
  }
  assert.deepEqual(sized("planarian"), ["machine:ribosome", "machine:vault", "unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]);
  // Only these five units have a size, each from a structure of its own kind (Kv1.1 is not Kv1.2; Cx45 is not Cx43).
  const units = Object.keys(raw.unit_sizes.units).sort();
  assert.deepEqual(units, ["unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]);
  for (const species of SPECIES) for (const item of catalogue.of(species)) if (item.unit && item.size) assert.ok(units.includes(item.unit.id), `${species}: ${item.unit.id}`);
  for (const species of ["ecoli", "syn3a", "mpneumoniae"]) assert.equal(catalogue.of(species).filter((item) => item.unit && item.size).length, 0, species);
  assert.deepEqual(catalogue.of("thalecress").filter((item) => item.unit && item.size).map((item) => item.id), ["unit.U41"], "the plant: its ER calcium pump alone, where its atlas finds it");
  // The gap-junction unit: a connexin channel where the species builds it of connexins, an innexin channel where of innexins.
  assert.equal(catalogue.item("human", "unit.U36").size.entry, "7Z22");
  assert.equal(catalogue.item("mouse", "unit.U36").size.entry, "7Z22");
  assert.equal(catalogue.item("planarian", "unit.U36").size.entry, "5H1R");
  assert.equal(catalogue.item("fruitfly", "unit.U36").size.entry, "5H1R");
  // Where the shape is of the family the species has, the panel does not repeat the atlas's line that the shape drawn is of
  // the family the engine's law names: it says whose family the shape here is. A species that builds it of connexins keeps none.
  const said = (species) => describe(catalogue, species, "unit.U36", { scene }).finding?.more || "";
  assert.match(said("planarian"), /The shape drawn here is of the family this species has\.$/);
  assert.doesNotMatch(said("planarian"), /the shape drawn, the assembly/);
  assert.doesNotMatch(said("human"), /The shape drawn here/);
  // Said plainly: whose structure it is, and that none of the species' own is in hand.
  const big = (species, id) => describe(catalogue, species, id, { scene }).facts.find(([label]) => label === "How big")[1];
  assert.match(big("planarian", "machine:ribosome"), /a structure of Homo sapiens \(one of Schmidtea mediterranea: none in hand\)/);
  assert.match(big("planarian", "machine:ribosome"), /RACK1 \(entity 70\), whose name says neither subunit, stands in the small subunit/);
  assert.doesNotMatch(big("human", "machine:ribosome"), /none in hand/);
  assert.match(big("human", "unit.U06"), /a structure of Rattus norvegicus \(one of Homo sapiens: none in hand\)/);
  assert.match(big("fruitfly", "unit.U36"), /a structure of Caenorhabditis elegans \(one of Drosophila melanogaster: none in hand\)/);
  assert.match(big("mouse", "unit.U41"), /Of its one kind of chain, \d+% of the sequence/);
  // Where the species' file says whose structure it is (\`whose\`), its words stand, and no second sentence of it is added.
  for (const species of SPECIES) {
    const size = catalogue.item(species, "machine:ribosome")?.size;
    if (!size?.whose) continue;
    assert.doesNotMatch(big(species, "machine:ribosome"), /none in hand/, species);
    assert.ok(big(species, "machine:ribosome").includes(size.whose), species);
    assert.doesNotMatch(describePart(catalogue, species, "machine:ribosome", "large", { scene }).facts.find(([label]) => label === "Measured from")[1], /none in hand/, species);
  }
  // A unit with a size says it is drawn to scale; one with none keeps the card's words.
  const unit = describe(catalogue, "fruitfly", "unit.U36", { scene });
  assert.equal(unit.swatch, "mach-sized");
  assert.match(unit.note, /^A unit of the law inventory, and a protein assembly\..*drawn to scale from the viewer's own measure of a structure of the family Fruit fly's atlas finds it built from/);
  assert.match(describe(catalogue, "human", "unit.U39", { scene }).note, /of its own kind: an illustration, not the structure\.$/);
  assert.equal(describe(catalogue, "planarian", "unit.U05", { scene }).note, "A unit of the law inventory, and a protein assembly. The panel says what the inventory states of its laws, as the Protein atlas does. No size of it is in hand, so it is a card, not a shape.");
  // Nothing on a sized unit's panel says it is modelled, qualified or judged.
  for (const id of units) assert.doesNotMatch(JSON.stringify(describe(catalogue, "mouse", id, { scene }).facts), /\bmodell?ed\b|qualified|judged/i, id);
  // Its parts and chains are chosen under the unit's id, and their panels say whose structure they are of.
  const { lens } = lensFor("planarian");
  lens.setSelection("unit.U39");
  assert.equal(lens.built.get("unit.U39").level, 2);
  assert.deepEqual([...lens.built.get("unit.U39").ids].sort(), ["unit.U39:alpha", "unit.U39:beta", "unit.U39:gamma"]);
  assert.ok(lens.has("unit.U39:alpha"));
  const alpha = lens.describe("unit.U39:alpha");
  assert.match(alpha.label, /α, the pump/);
  assert.match(alpha.facts.find(([label]) => label === "Measured from")[1], /7E1Z, a structure of Homo sapiens \(one of Schmidtea mediterranea: none in hand\)/);
  // Named by an address before its machine shows it, a part (or a chain) still opens: its machine drawn at its level.
  const { lens: fresh } = lensFor("planarian");
  assert.ok(fresh.has("unit.U39:beta") && !fresh.has("unit.U39:delta") && !fresh.has("unit.U05:alpha"));
  fresh.setSelection("unit.U39:beta");
  assert.deepEqual([fresh.selected, fresh.selectedPart, fresh.built.get("unit.U39").level], ["unit.U39", "unit.U39:beta", 2]);
  assert.match(fresh.describe("unit.U39:beta").label, /β, outside the cell/);
  fresh.setSelection("unit.U36:chain-C");
  assert.deepEqual([fresh.selected, fresh.selectedPart, fresh.built.get("unit.U36").level], ["unit.U36", "unit.U36:chain-C", 3]);
  assert.equal(fresh.built.get("unit.U39").group, null, "the machine chosen before is an outline again");
  lens.setSelection("unit.U36");
  lens.setMode("3");
  const shades = lens.bodyColours("unit.U36");
  assert.ok(new Set(shades).size >= 2, "the chains of one kind are told apart by the hemichannel that holds them");
  assert.notEqual(shades[0], shades[8], "the two hemichannels differ");
});

test("a measured machine chosen shows its parts, each in its own shade, and each can be chosen", () => {
  const { lens } = lensFor("ecoli");
  lens.setSelection("machine:ribosome");
  const built = lens.built.get("machine:ribosome");
  assert.equal(built.level, 2);
  assert.equal(lens.outlineItems.filter((item) => item.id === "machine:ribosome").length, 2, "its outline is two instances of the bench's outlines");
  assert.deepEqual([...built.ids].sort(), ["machine:ribosome:large", "machine:ribosome:small"]);
  const [large, small] = lens.bodyColours("machine:ribosome");
  assert.notEqual(large, small, "the two subunits are told apart");
  // While it is chosen, every other machine is faint.
  const other = lens.outlineItems.findIndex((item) => item.id === "machine:hslv");
  const colourOf = (index) => lens.outlines.getColorAt(index, new THREE.Color()) ?? (() => { const c = new THREE.Color(); lens.outlines.getColorAt(index, c); return c; })();
  const faintNow = colourOf(other).getHexString();
  assert.ok(lens.has("machine:ribosome:small") && /Small subunit/.test(lens.describe("machine:ribosome:small").label));
  lens.setSelection(null);
  assert.notEqual(colourOf(other).getHexString(), faintNow, "let go, the others are in their colours again");
  assert.equal(lens.built.get("machine:ribosome").level, 1, "let go, it is an outline again");
  assert.equal(lens.built.get("machine:ribosome").group, null, "drawn by the bench's instanced outlines, with no bodies of its own");
});

test("the ATP synthase stands as its measured parts, ring below head, and shows its parts and then each chain", () => {
  const { lens } = lensFor("ecoli");
  const atp = catalogue.item("ecoli", "machine:atp-synthase").entry.size;
  assert.deepEqual(atp.parts.map((part) => part.id), ["head", "central-stalk", "peripheral-stalk", "ring", "stator-foot"]);
  const at = (id) => atp.parts.find((part) => part.id === id).centre_nm[1];
  assert.ok(at("ring") < at("central-stalk") && at("central-stalk") < at("head"), "the frame runs from the ring to the head: the ring stands lowest");
  // The frame's own axis: the head stands straight above the ring, so the ring's extent along y is its extent across the membrane.
  const centre = (id) => atp.parts.find((part) => part.id === id).centre_nm;
  const [dx, dy, dz] = centre("head").map((n, k) => n - centre("ring")[k]);
  assert.ok(Math.hypot(dx, dz) < 0.02 * Math.abs(dy), JSON.stringify([dx, dy, dz]));
  assert.equal(atp.chains.length, 22, "α3 β3 γ δ ε a b2 c10");
  assert.deepEqual(levelsOf(catalogue.item("ecoli", "machine:atp-synthase")).map((level) => level.label), ["Outline", "Parts", "Subunits", "Shape"]);
  assert.deepEqual(levelsOf(catalogue.item("ecoli", "machine:lon")).map((level) => level.label), ["Outline", "Subunits", "Shape"], "Lon has no named parts: its whole, then its six chains, then its shape");
  lens.setSelection("machine:atp-synthase");
  assert.equal(lens.built.get("machine:atp-synthase").level, 2);
  assert.equal(lens.built.get("machine:atp-synthase").ids.size, 5);
  const slab = lens.built.get("machine:atp-synthase").group.children.find((mesh) => mesh.userData.slab);
  assert.ok(slab, "where its membrane lies, as thick as the ring reaches along its axis");
  const ring = atp.parts.find((part) => part.id === "ring");
  // Centred on the ring, as thick as the ring's farthest atoms reach along the axis (the frame's axis is the ring's first, nearly).
  assert.ok(Math.abs(slab.position.y - ring.centre_nm[1] / UNIT_NM) < 1e-9 && Math.abs(slab.geometry.parameters.height * UNIT_NM - ring.farthest_nm[0]) < 0.1, String(slab.geometry.parameters.height * UNIT_NM));
  assert.match(describe(catalogue, "ecoli", "machine:atp-synthase", { scene }).facts.find(([label]) => label === "How big")[1], new RegExp(`as thick as the ring's farthest atoms reach along the machine's axis: ${slab.geometry.parameters.height * UNIT_NM >= 6.65 && slab.geometry.parameters.height * UNIT_NM < 6.75 ? "6\\.7" : "x"} nm\\.`));
  // It stays inside its tray, wider than the machine, and is no part that can be chosen.
  lens.root.updateMatrixWorld(true);
  const placed = lens.layout.items.find((item) => item.id === "machine:atp-synthase");
  const tray = lens.layout.trays.find((value) => value.group === placed.group);
  const box = new THREE.Box3().setFromObject(slab);
  assert.ok(box.min.x >= tray.x - tray.w / 2 && box.max.x <= tray.x + tray.w / 2 && box.min.z >= tray.z - tray.d / 2 && box.max.z <= tray.z + tray.d / 2, JSON.stringify([box, tray]));
  assert.ok(box.max.x - box.min.x > placed.w && slab.userData.unpickable);
  lens.setMode("3");
  assert.equal(lens.built.get("machine:atp-synthase").ids.size, 22);
  assert.match(lens.describe("machine:atp-synthase:chain-A").label, /ATP synthase subunit alpha, chain A/);
  lens.setSelection("machine:lon");
  assert.equal(lens.built.get("machine:lon").level, 3, "chosen, Lon goes to its first deeper level, its chains");
  const words = describe(catalogue, "ecoli", "machine:atp-synthase", { scene }).facts.find(([label]) => label === "How big")[1];
  assert.match(words, /Protein Data Bank entry 6OQR, a structure of Escherichia coli/);
  assert.match(words, /Drawn as its chains' ellipsoids, each at its measured size, centre and axes, in the colour of the part that holds it/);
  // At Parts each part is its chains, in one colour, chosen as the part: the peripheral stalk is its three chains, not one slab.
  lens.setSelection("machine:atp-synthase");
  lens.setMode("2");
  const parts = lens.built.get("machine:atp-synthase");
  assert.equal(parts.bodies.count, 22, "its 22 chains, drawn as its five parts");
  const stalk = parts.bodies.userData.bodies.filter((body) => body.id === "machine:atp-synthase:peripheral-stalk");
  assert.equal(stalk.length, 3, "b2 and δ");
  assert.equal(new Set(lens.bodyColours("machine:atp-synthase").filter((_, index) => parts.bodies.userData.bodies[index].id === "machine:atp-synthase:head")).size, 1, "a part in one colour");
  assert.match(lens.describe("machine:atp-synthase:peripheral-stalk").facts.find(([label]) => label === "Drawn as")[1], /^Its 3 chains' ellipsoids/);
});

test("a species the catalogue holds no bench for says so, by rule: its units of the law inventory stand alone", () => {
  // A catalogue made here without the mouse's bench: the mouse, which has an atlas, is shown for its units and the card says why.
  const without = { ...raw, benches: Object.fromEntries(Object.entries(raw.benches).filter(([id]) => id !== "mouse")), entries: raw.entries.filter((entry) => entry.species !== "mouse") };
  const { lens } = lensFor("mouse", { raw: { ...scene, catalogue: without } });
  // Its units are cards where the catalogue gives them no size (the mouse's have sizes; the frog's, today, none).
  assert.equal(lens.chrome().card.notice, `No bench of machines has been gathered for Mouse yet: only the units of the law inventory that its atlas finds stand here${lens.counts.sized ? "" : ", each a card"}.`);
  assert.ok(lens.catalogue.of("mouse").every((item) => item.unit), "nothing but its units");
  // A species with its bench says nothing of it; and in the scene as built, every species with an atlas and no bench says the same.
  assert.doesNotMatch(lensFor("mouse").lens.chrome().card.notice || "", /No bench/);
  for (const atlas of (scene.proteins.atlases || []).filter((item) => !item.reference && !catalogue.species.includes(item.id))) assert.match(lensFor(atlas.id).lens.chrome().card.notice, /^No bench of machines has been gathered for .+ yet/, atlas.id);
});

test("the legend names every mark that is drawn, and the card says what is and is not in hand", () => {
  const { lens } = lensFor("thalecress", { raw: bareScene });
  const chrome = lens.chrome();
  assert.ok(!chrome.legend.items.some((item) => item.id === "mach-sized"), "no shape is drawn where no size is in hand");
  assert.match(chrome.card.notice, /^No machine of Thale cress has a size in hand/);
  assert.ok(chrome.card.species.options.length > 1);
  const { lens: ecoli } = lensFor("ecoli");
  assert.deepEqual(ecoli.chrome().legend.items.filter((item) => MARKS.some((mark) => mark.id === item.id)).map((item) => item.id), ["mach-sized", "mach-card", "mach-chosen"]);
  ecoli.setSelection("machine:flagellar-motor");
  assert.deepEqual(ecoli.chrome().card.modes.options.map(([, label]) => label), ["Outline", "Parts", "Subunits"]);
});

test("the page offers it second among the tabs, owning the ids it makes, and keeps the rest of the order", () => {
  const viewer = readFileSync(path.join(ROOT, "src", "ui", "viewer.js"), "utf8");
  const list = viewer.slice(viewer.indexOf("const LENSES = ["), viewer.indexOf("];", viewer.indexOf("const LENSES = [")));
  assert.deepEqual([...list.matchAll(/\{ id: "([a-z]+)"/g)].map((match) => match[1]), ["cell", "machines", "proteins", "engine", "laws", "experiments"]);
  const entry = list.split("\n").find((line) => line.includes('id: "machines"'));
  for (const word of ["needs: (scene) => scene.catalogue?.entries?.length || Object.keys(scene.catalogue?.benches || {}).length", "owns: machinesOwn", "doorsFor: machinesDoors", "textSections: machinesSections", "present: machinesPresent", "styles: MACHINES_CSS"]) assert.ok(entry.includes(word), word);
  // The view shown keeps an id it holds itself: a closer view in the Cell view keeps machine:<id>.
  assert.match(viewer, /const owner = id && !this\.current\?\.has\?\.\(id\) && this\.views\?\.find/);
});

test("the dossiers on the benches: which machines, named by what, their proteins by tier, their counts, and the way to and from the atlas", () => {
  const dossier = (species) => read(`data/catalogue/dossiers/${species}.json`);
  // Every machine a dossier names is on its species' bench; the overlay's entry stands where both name one.
  for (const species of ["ecoli", "human"]) {
    const kinds = dossier(species).machines.map((machine) => `machine:${machine.kind}`);
    for (const id of kinds) assert.ok(catalogue.item(species, id), `${species}: ${id}`);
  }
  assert.equal(catalogue.of("ecoli").filter((item) => !item.unit).length, 21);
  assert.equal(catalogue.of("human").filter((item) => !item.unit).length, 33); // 32, and the vault (19 November 2026)
  const words = (species, id) => describe(catalogue, species, id, { scene });
  const fact = (panel, label) => panel.facts.find(([name]) => name === label)?.[1];
  const rnap = words("ecoli", "machine:rna-polymerase");
  assert.match(fact(rnap, "Named by"), /^E\. coli's file: “/, "the species' file names it, as decided");
  assert.match(fact(rnap, "Also named by"), /reviewed UniProt entries carry the Gene Ontology's term/);
  // A count from an open paper: the number, what it counts, in what cell, the paper and where in it.
  assert.match(fact(rnap, "How many"), /^1,844 per cell: RNA polymerase: .*, in wild-type cells grown in M9 glucose medium \(.*2023.*, RESULTS > .*paragraph 1\)$/);
  // Its proteins by tier, each said as such.
  const proteasome = words("human", "machine:proteasome");
  assert.deepEqual(proteasome.sections.map((section) => section.title).filter((title) => /^Its parts|^Named with/.test(title)), ["Its parts, held by the structure", "Its parts by UniProt's keyword, not held by the structure", "Named with it by the Gene Ontology alone"].filter((title) => proteasome.sections.some((section) => section.title === title)));
  assert.match(fact(proteasome, "Its proteins"), /^\d+ parts and \d+ named with it alone, by the Gene Ontology and UniProt \(its dossier\)/);
  // What Cells models of it: FR-13 names the proteasome among the machines with no model; a kind it does not name is said so.
  assert.ok(proteasome.sections[0].items.some((line) => /It names the proteasome among the machines the engine has no model of/.test(line.lines[0])));
  assert.ok(words("human", "machine:complex-i").sections[0].items.some((line) => /does not name this one: it is not on the engine's plan/.test(line.lines[0])));
  // The mitochondrial ATP synthase reads D209's line as the kind's own, in its own words.
  assert.ok(words("human", "machine:atp-synthase").chips.some((chip) => /Planned, first/.test(chip.label)));
  // The gathering's pick, beside the entry measured where they differ.
  assert.match(fact(words("ecoli", "machine:ribosome"), "The gathering's pick"), /^Protein Data Bank entry 6BU8, “70S ribosome with S1 domains 1 and 2 \(Class 1\)” \(3\.5 Å\), which holds 53 of the 55 proteins its dossier seeks: not the entry this size is measured from$/);
  // The nuclear pore stays a card, and says why in one line.
  const pore = catalogue.item("human", "machine:nuclear-pore");
  assert.ok(!pore.sized);
  assert.match(fact(words("human", "machine:nuclear-pore"), "How big"), /^Decided 17 November 2026: the nuclear pore stays a card\. Its entry, 9AAV, is an integrative model that holds about a third of the proteins/);
  // Parts are sub-assemblies, each the genes the overlay groups from the dossier's rows; subunits are chains, each its protein.
  const size = catalogue.item("human", "machine:proteasome").size;
  assert.deepEqual(size.parts.map((part) => part.id), ["core", "base", "lid"]);
  assert.equal(size.parts.find((part) => part.id === "core").proteins.length, 14);
  assert.ok(size.chains.length === 46 && size.chains.every((chain) => /^[OPQ]\d/.test(chain.protein || "")), "every chain joined to its protein by the dossier's reading of its entity");
  assert.ok(size.membrane === undefined && catalogue.item("human", "machine:atp-synthase").size.membrane.part === "ring");
  // E. coli's ATP synthase is measured from the dossier's own entry, so its chains are joined too; the ribosome's 7K00 is not the dossier's.
  assert.ok(catalogue.item("ecoli", "machine:atp-synthase").size.chains.every((chain) => chain.protein));
  assert.ok(!(catalogue.item("ecoli", "machine:ribosome").size.chains || []).some((chain) => chain.protein));
  // From a chain to its protein in the atlas, and from a protein of the atlas back to its machine.
  const { lens } = lensFor("human");
  lens.setSelection("machine:proteasome");
  lens.setMode("3");
  const chain = [...lens.built.get("machine:proteasome").ids][0];
  const panel = lens.describe(chain);
  const door = panel.doors.find((value) => value.lens === "proteins");
  assert.ok(door && door.show === "own" && /^[OPQ]\d/.test(door.find) && /^Show \S+ in the Protein atlas$/.test(door.label), JSON.stringify(panel.doors));
  assert.match(fact(panel, "Its protein"), /as its dossier reads the entry's entity/);
  const back = doorsFor({ id: `own:human:p@x:${door.find}` }, scene, { species: "human" });
  assert.ok(back.some((value) => value.lens === "machines" && value.value === "machine:proteasome" && /^It is a part of the proteasome: show it in Machines$/.test(value.label)), JSON.stringify(back));
  // The thale cress's ribosome: the human's structure, said plainly; the ER calcium pump's choice of entry, said in the overlay.
  assert.match(fact(words("thalecress", "machine:ribosome"), "How big"), /a structure of Homo sapiens \(one of Arabidopsis thaliana: none in hand\)/);
  assert.match(overlay.measures["animals-serca"].chosen, /1SU4/);
  // "Also named by" is a dossier's sentence with its sources, never a file's text (a record's words stay the record's).
  for (const species of SPECIES) for (const item of catalogue.of(species)) if (item.entry?.also_named) assert.ok(typeof item.entry.also_named.text === "string" && item.entry.also_named.text.length < 600 && item.entry.also_named.sources?.length, `${species} ${item.id}`);
  assert.match(fact(words("human", "machine:ribosome"), "Also named by"), /reviewed UniProt entries carry the Gene Ontology's term/);
  // Nothing on any panel of the two benches claims a model.
  for (const species of ["ecoli", "human"]) for (const item of catalogue.of(species)) if (!item.unit) {
    const panel = words(species, item.id);
    assert.doesNotMatch(JSON.stringify({ ...panel, sections: panel.sections.filter((value) => !value.title.startsWith("Copies, in UniProt's words")) }), CLAIMED, `${species} ${item.id}`);
  }
});

test("the Shape level: offered where a shape file is published, one draw, each surface chosen as its chain or part and lit when chosen", async () => {
  const file = (name) => read(`data/catalogue/shapes/${name}`);
  // Offered wherever the catalogue names a published shape file: every measured machine and unit (the mycoplasmas'
  // ribosomes at E. coli's, whose measure they are drawn at), and nowhere a size has none.
  for (const species of SPECIES) for (const item of catalogue.of(species)) if (item.size?.shape === "measured") assert.ok(item.size.surface, `${species} ${item.id}: a measured size, and its shape`);
  assert.equal(catalogue.item("syn3a", "machine:ribosome").size.surface.file, "shapes/ecoli.ribosome.json");
  assert.equal(catalogue.item("planarian", "unit.U39").size.surface.file, "shapes/animals.sodium-pump.json");
  assert.ok(!(levelsOf(catalogue.item("ecoli", "machine:ftsh")) || []).some((level) => level.label === "Shape"), "no size, no shape, no level");
  // On every bench, a chosen machine or unit at Shape stays within the ceiling: the bench's draws and triangles plus its shape's.
  for (const species of SPECIES) {
    const { lens: bench } = lensFor(species, { width: 390, height: 844 });
    const cost = bench.cost();
    const heaviest = Math.max(0, ...catalogue.of(species).map((item) => item.size?.surface?.triangles || 0));
    assert.ok(cost.draws + 1 <= 40 && cost.triangles + heaviest <= 40000, `${species}: the bench ${JSON.stringify(cost)} and its heaviest shape, ${heaviest} triangles`);
  }
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const { lens } = lensFor("ecoli");
  lens.surfaces = new Map(["ecoli.atp-synthase.json", "ecoli.translocon.json", "ecoli.ribosome.json"].map((name) => [`shapes/${name}`, { status: "found", data: file(name) }]));
  const bench = lens.cost();
  lens.setSelection("machine:atp-synthase");
  lens.setMode("4");
  await settle();
  const built = lens.built.get("machine:atp-synthase");
  assert.equal(built.level, 4);
  assert.ok(built.surface && !built.bodies.visible, "the surfaces drawn, the ellipsoids put away");
  const cost = lens.cost();
  assert.ok(cost.draws <= 40 && cost.triangles <= 40000 && cost.triangles - bench.triangles <= 9348 + 400, `${JSON.stringify(cost)} against the bench's ${JSON.stringify(bench)}`);
  // A press on a surface chooses its chain; the chain is lit in the page's accent, the others are not.
  const row = built.surface.surfaces.find((value) => value.partId === "head");
  const picked = built.surface.mesh.userData.pick({ faceIndex: row.first });
  assert.equal(picked, `machine:atp-synthase:${row.id}`);
  lens.setSelection(picked);
  assert.equal(lens.built.get("machine:atp-synthase"), built, "choosing a chain does not rebuild the machine");
  const colourAt = (vertex) => new THREE.Color().fromBufferAttribute(built.surface.mesh.geometry.getAttribute("color"), vertex).getHexString();
  const accent = new THREE.Color("#1f6fd0").getHexString();
  assert.equal(colourAt(row.firstVertex), accent);
  const other = built.surface.surfaces.find((value) => value.id !== row.id);
  assert.notEqual(colourAt(other.firstVertex), accent);
  // The chain's panel: its protein, its door into the atlas, and a door to its part.
  const panel = lens.describe(picked);
  assert.ok(panel.doors.some((door) => door.find) && panel.doors.some((door) => /^Its part: Head/.test(door.label)), JSON.stringify(panel.doors));
  // The machine's panel says what its shape is, in the contract's words.
  lens.setSelection("machine:atp-synthase");
  const said = lens.describe("machine:atp-synthase").facts.find(([label]) => label === "Its shape")[1];
  assert.match(said, /^The viewer's own smooth surface of Protein Data Bank entry 6OQR's coordinates \(a chain at 1\.0 nm\), worked out by tools\/shape_particle\.py: .* An illustration, not the structure and not a measurement; the Protein Data Bank states no surface\.$/);
  assert.doesNotMatch(said, /It is the shape of a structure of/, "E. coli's own entry");
  assert.doesNotMatch(said, CLAIMED);
  // Let go, its surfaces are freed.
  const mesh = built.surface.mesh;
  lens.setSelection(null);
  assert.equal(mesh.parent, null);
  // A coarser width than the setting's is said; the human's proteasome was made at 1.5 nm.
  assert.match(levelsOf(catalogue.item("human", "machine:proteasome")).at(-1).says, /a chain at 1\.5 nm, coarser than the setting's 1\.0 nm to hold the budget/);
  // The translocon: the catalogue names no chains of it, so a surface is chosen as its part.
  lens.setSelection("machine:protein-translocon");
  lens.setMode("4");
  await settle();
  const translocon = lens.built.get("machine:protein-translocon");
  assert.match(translocon.surface.mesh.userData.pick({ faceIndex: 0 }), /^machine:protein-translocon:sec[yeg]$/);
  // The ribosome: its two subunits as solids, each chosen as its part.
  lens.setSelection("machine:ribosome");
  lens.setMode("4");
  await settle();
  const ribosome = lens.built.get("machine:ribosome");
  assert.deepEqual(ribosome.surface.surfaces.map((value) => value.partId).sort(), ["large", "small"]);
  assert.match(ribosome.surface.mesh.userData.pick({ faceIndex: 0 }), /^machine:ribosome:(large|small)$/);
  // A shape file that cannot be read: the ellipsoids stay, and the panel says why.
  lens.surfaces.set("shapes/ecoli.hslv.json", { status: "failed", data: null, words: "The shape file shapes/ecoli.hslv.json could not be read (a test)." });
  lens.setSelection("machine:hslv");
  lens.setMode("4");
  await settle();
  const hslv = lens.built.get("machine:hslv");
  assert.ok(!hslv.surface && hslv.bodies.visible);
  assert.equal(lens.describe("machine:hslv").facts.find(([label]) => label === "Its shape")[1], "The shape file shapes/ecoli.hslv.json could not be read (a test).");
  // At Subunits a chosen chain is lit too, by its instance.
  lens.setMode("3");
  const chain = [...lens.built.get("machine:hslv").ids][0];
  lens.setSelection(chain);
  const index = lens.built.get("machine:hslv").bodies.userData.bodies.findIndex((body) => body.id === chain);
  assert.equal(lens.bodyColours("machine:hslv")[index], accent);
});

test("what Version 33's looks found: the card's words where there are units, polymerase II's name, the opening view", () => {
  // The card speaks of the law inventory's tray only where the species has units.
  assert.doesNotMatch(lensFor("ecoli").lens.chrome().card.text, /law inventory/);
  assert.match(lensFor("planarian").lens.chrome().card.text, /The membrane machines in the tray of moving ions are units of the law inventory/);
  // The human's RNA polymerase II, named by its dossier's term, beside I and III; E. coli's keeps the kind's label.
  assert.deepEqual(["rna-polymerase", "rna-polymerase-i", "rna-polymerase-iii"].map((kind) => catalogue.item("human", `machine:${kind}`).label), ["RNA polymerase II", "RNA polymerase I", "RNA polymerase III"]);
  assert.equal(catalogue.item("ecoli", "machine:rna-polymerase").label, "RNA polymerase");
  // The Detail asks for one row.
  const { lens } = lensFor("ecoli");
  lens.setSelection("machine:atp-synthase");
  assert.equal(lens.chrome().card.modes.oneRow, true);
  assert.deepEqual(lens.chrome().card.modes.options.map(([, label]) => label), ["Outline", "Parts", "Subunits", "Shape"]);
});

test("a unit's shape: drawn by its page id, its surfaces chosen as its chains, and whose structure it is", async () => {
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const { lens } = lensFor("planarian");
  const file = (name) => read(`data/catalogue/shapes/${name}`);
  lens.surfaces = new Map(["animals.innexin-channel.json", "animals.ribosome.json"].map((name) => [`shapes/${name}`, { status: "found", data: file(name) }]));
  lens.setSelection("unit.U36");
  assert.ok(levelsOf(lens.item("unit.U36")).some((level) => level.id === 4 && level.label === "Shape"));
  lens.setMode("4");
  await settle();
  const built = lens.built.get("unit.U36");
  assert.ok(built.surface, "the innexin channel's surfaces drawn");
  const picked = built.surface.mesh.userData.pick({ faceIndex: 0 });
  assert.match(picked, /^unit\.U36:chain-[A-P]$/);
  assert.ok(lens.cost().draws <= 40 && lens.cost().triangles <= 40000, JSON.stringify(lens.cost()));
  const said = lens.describe("unit.U36").facts.find(([label]) => label === "Its shape")[1];
  assert.match(said, /Protein Data Bank entry 5H1R's coordinates \(a chain at 1\.0 nm\)/);
  assert.match(said, /It is the shape of a structure of Caenorhabditis elegans, as its size is\.$/);
  // The planarian's ribosome: the human 80S's shape, its two subunits as solids, said whose.
  lens.setSelection("machine:ribosome");
  lens.setMode("4");
  await settle();
  assert.deepEqual(lens.built.get("machine:ribosome").surface.surfaces.map((row) => row.partId).sort(), ["large", "small"]);
  assert.match(lens.describe("machine:ribosome").facts.find(([label]) => label === "Its shape")[1], /each part as one solid, at 2\.0 nm, coarser than the setting's 1\.6 nm to hold the budget.*It is the shape of a structure of Homo sapiens, as its size is\.$/);
});

test("the page carries the catalogue's core; each species' bench is read beside it when shown, and one that cannot be read says so", async () => {
  // The core holds what every bench needs, and no entry; it is far lighter than the benches together.
  assert.ok(!core.entries && !core.by_protein && core.benches.human.file === "catalogue/human.json");
  const size = (value) => JSON.stringify(value).length;
  const benches = Object.keys(core.benches).reduce((sum, species) => sum + size(benchOf(species)), 0);
  console.log(`# the core ${size(core)} bytes; the eight benches ${benches} bytes together`);
  assert.ok(size(core) < benches / 5);
  for (const kind of core.kinds) assert.deepEqual(kind.species, [...new Set([...raw.entries, ...raw.organelles].filter((entry) => entry.id === kind.id).map((entry) => entry.species))], kind.id);
  // Before its bench is read a species has its units alone, and its machines once it is in.
  const coreScene = { ...scene, catalogue: core };
  const shown = new Catalogue(core, coreScene);
  assert.ok(!shown.hasBench("human") && shown.of("human").every((item) => item.unit));
  const read = await shown.loadBench("human", { load: async (where) => readJSON(where) });
  assert.equal(read.status, "found");
  assert.equal(shown.of("human").filter((item) => !item.unit).length, raw.entries.filter((entry) => entry.species === "human").length);
  assert.ok(shown.machinesOf("human", "P25786").some(([kind]) => kind === "proteasome"), "its proteins' machines with it, for the atlas's way back");
  // A bench that cannot be read: plain words, and the units stand.
  const failed = await new Catalogue(core, coreScene).loadBench("mouse", { load: async () => { throw new Error("catalogue/mouse.json answered 404"); } });
  assert.equal(failed.status, "failed");
  assert.match(failed.words, /^The machines of this species could not be read \(catalogue\/mouse\.json: catalogue\/mouse\.json answered 404\)\. The units of the law inventory stand without them\.$/);
  // The view: its card says so, and the tab still works with the units.
  const { lens } = lensFor("mouse", { raw: coreScene });
  lens.catalogue.benches.set("mouse", failed);
  lens.catalogue.cache.delete("mouse");
  lens.build();
  assert.equal(lens.chrome().card.notice, failed.words);
  assert.ok(lens.layout.items.length > 0 && lens.layout.items.every((item) => item.item.unit));
});

const readJSON = (where) => JSON.parse(readFileSync(path.join(ROOT, "data", "catalogue", where.replace(/^catalogue\//, "benches/")), "utf8"));

test("the eight dossiers on the benches: candidates by family said as such, and each of the dossiers' records said as what it is", () => {
  const words = (species, id) => describe(catalogue, species, id, { scene });
  const fact = (panel, label) => panel.facts.find(([name]) => name === label)?.[1];
  const section = (panel, start) => panel.sections.find((value) => value.title.startsWith(start));
  // Every dossier's machines on its species' bench.
  for (const species of ["ecoli", "human", "mouse", "fruitfly", "thalecress", "planarian", "syn3a", "mpneumoniae"]) {
    // (A machine its family route alone names, with no candidate, is listed apart: below.)
    for (const machine of read(`data/catalogue/dossiers/${species}.json`).machines) assert.ok(catalogue.item(species, `machine:${machine.kind}`) || catalogue.noneFound(species).some((row) => row.id === machine.kind), `${species} ${machine.kind}`);
  }
  // The thale cress's machines of light stand in a tray of their own, its label and plain line gather.json's.
  assert.ok(catalogue.of("thalecress").some((item) => item.group === "light"));
  assert.equal(raw.groups.find((group) => group.id === "light").label, read("data/catalogue/gather.json").groups_proposed.find((group) => group.id === "light").label);
  // A species by family: its proteins are candidates by their family, never the machine's parts, with what was looked for.
  const proteasome = words("planarian", "machine:proteasome");
  assert.match(fact(proteasome, "Its proteins"), /candidates by their family \(InterPro\) for parts of Human's machine: candidates, not the machine's parts/);
  // Nothing of the species names it: its line says what was looked for, labelled so, and never "Named by".
  assert.equal(fact(proteasome, "Named by"), undefined);
  assert.equal(fact(proteasome, "Looked for, by family"), "64 of Planarian's proteins are candidates, by their InterPro family, for 31 of the 32 parts of Human's machine. For 1 part no line of Planarian's table carries the family, which says what the table holds, not that Planarian lacks the protein; for 0 the table cannot tell, its scan being older than the family; 0 have no family to look for.");
  assert.ok(section(proteasome, "Candidates by family, not its parts").items.length > 0);
  assert.ok(!proteasome.sections.some((value) => /^Its parts/.test(value.title)), "no list calls them parts");
  const looked = section(proteasome, "What was looked for, part by part").items.map((value) => value.detail);
  // Since the planarian's own scan (19 November 2026) no part is left as "cannot tell": each has candidates, or no line of the table carries its family.
  assert.ok(looked.some((value) => /not in the table: no line of the species' table carries its family, which says what the table holds, not that the species lacks the protein/.test(value)) && !looked.some((value) => /cannot tell/.test(value)));
  // The words for a table that cannot tell stay, for a species whose table's scan is older than a family: on planted rows.
  assert.match(lookedFor({ looked_for: [["A", "part", "cannot tell"], ["B", "part", "candidates"], ["C", "part", "cannot tell"]], proteins: [["p1"]] }, "Planarian", "Human"), /^1 of Planarian's proteins is a candidate, by its InterPro family, for 1 of the 3 parts of Human's machine\. For 0 parts no line of Planarian's table carries the family, which says what the table holds, not that Planarian lacks the protein; for 2 the table cannot tell, its scan being older than the family; 0 have no family to look for\.$/);
  assert.match(fact(proteasome, "A structure elsewhere"), /^Protein Data Bank entry 7QYB, “Proteasome-ZFAND5 Complex Z-C state” \(4\.1 Å\), a structure of Homo sapiens; none of Planarian's own is in hand$/);
  // The species' own records keep their place above the dossier's.
  const ribosome = words("planarian", "machine:ribosome");
  assert.match(fact(ribosome, "Named by"), /CELL_STRUCTURES/);
  assert.equal(fact(ribosome, "Also named by"), undefined);
  assert.match(fact(ribosome, "Looked for, by family"), /^105 of Planarian's proteins are candidates, by their InterPro family, for 68 of the 95 parts of Human's machine \(59 of the 80 its entry holds\)\./);
  // Syn3A's own file names its ribosome ("Named by"); the family route beside it is what was looked for.
  const syn3a = words("syn3a", "machine:ribosome");
  assert.match(fact(syn3a, "Named by"), /^Syn3A's file: “/);
  assert.match(fact(syn3a, "Looked for, by family"), /of E\. coli's machine/);
  assert.ok(section(syn3a, "What was looked for, part by part of E. coli's machine"));
  // On every bench by family, the line's counts are the dossier's own: its sentence gives the same numbers.
  const LINE = /^(\d+) of .+'s proteins (?:is a candidate, by its|are candidates, by their) InterPro family, for (\d+) of the (\d+) parts? of .+'s machine(?: \((\d+) of the (\d+) its entry holds\))?\. For (\d+) parts? no line of .+'s table carries the family, which says what the table holds, not that .+ lacks the protein; for (\d+) the table cannot tell, its scan being older than the family; (\d+) (?:has|have) no family to look for\.$/;
  let routes = 0;
  for (const entry of raw.entries) {
    if (entry.gathered?.route?.by !== "family") continue;
    routes += 1;
    const panel = words(entry.species, `machine:${entry.id}`);
    const line = LINE.exec(fact(panel, "Looked for, by family") || "");
    assert.ok(line, `${entry.species} ${entry.id}: ${fact(panel, "Looked for, by family")}`);
    const [proteins, found, parts, heldFound = found, held = parts, absent, unknown, none] = line.slice(1).map((value) => value);
    const own = entry.gathered.route.text.match(/\b\d+\b/g);
    assert.deepEqual([proteins, parts, found, heldFound, held, absent, unknown, none], own, `${entry.species} ${entry.id}: ${entry.gathered.route.text}`);
    assert.ok(!panel.facts.some(([label, text]) => /^(Also )?Named by$/.test(label) && text === entry.gathered.route.text), `${entry.species} ${entry.id}: the family route is not said to name it`);
  }
  assert.equal(routes, 50, "the planarian's, Syn3A's and M. pneumoniae's machines by family, with candidates or named by their own records (49 until the planarian's own scan found candidates for myosin II)");
  // One "part", many "parts".
  assert.match(fact(words("syn3a", "machine:ftsh"), "Looked for, by family"), /^1 of Syn3A's proteins is a candidate, by its InterPro family, for 1 of the 3 parts of E\. coli's machine\. For 2 parts /);
  assert.match(fact(words("syn3a", "machine:lon"), "Looked for, by family"), /for 1 of the 1 part of E\. coli's machine\. For 0 parts /);
  // PaxDb's abundance, UniProt's sentences and the Gene Ontology's sub-assemblies, each said as what it is.
  const human = words("human", "machine:proteasome");
  assert.match(section(human, "PaxDb's abundance").note, /no count of copies in a cell/);
  assert.match(section(human, "Copies, in UniProt's words").note, /not a count of copies in a cell/);
  assert.ok(section(human, "Sub-assemblies its records name").items.some((value) => /proteasome core complex \(GO:0005839\)/.test(value.label)));
  // A count with its whole chain of citation: as the paper writes it, and whom it cites; several conditions, none picked.
  assert.match(fact(words("human", "machine:ribosome"), "How many"), /^1064 × 10\^4 per cell: cytosolic ribosomes, in a HeLa cell, .*; it cites Merrick and Pavitt, 2018\)$/);
  const mouse = words("mouse", "machine:ribosome");
  assert.match(fact(mouse, "How many"), /^3 numbers, each in its own condition \(below\); none is picked$/);
  assert.equal(section(mouse, "Counts per cell").items.length, 3);
  // A pick that holds other complexes says so beside its title.
  assert.match(fact(words("human", "machine:signal-recognition-particle"), "The gathering's pick"), /“[^”]+”.*it holds the machine among other complexes, and a measure would leave 48 of its entities out/);
  // Nothing on any panel of any bench claims a model.
  for (const species of SPECIES) for (const item of catalogue.of(species)) if (!item.unit) {
    const panel = words(species, item.id);
    assert.doesNotMatch(JSON.stringify({ ...panel, sections: panel.sections.filter((value) => !value.title.startsWith("Copies, in UniProt's words")) }), CLAIMED, `${species} ${item.id}`);
  }
  // UniProt's sentences stand in quotation marks, as UniProt's.
  assert.ok(section(words("ecoli", "machine:ftsh"), "Copies, in UniProt's words").items[0].lines.every((line) => /^“.*”$/.test(line)));
});

test("no panel of any bench says a file's or a field's name: the dossiers' sentences reach it in plain words", () => {
  // The tools that measured and shaped a structure are named, by rule, where its size and its shape are said.
  const NAMED = /tools\/(?:measure|shape)_particle\.py/g;
  const TOOL = /gather\.json|\.py\b|\((?:data|tools|schema|src)\/|listed under dropped|\b(?:left_out|holds_more|structure_elsewhere|not_looked_for|no_structure|looked_for|by_protein|per_cell|in_atlas|own_mark|sub_assemblies|left_out_entities|proteins_wanted|also_named)\b|(?:^|[\s(])--[a-z]/;
  const said = (panel) => JSON.stringify([panel.label, panel.note, panel.plain, panel.facts, (panel.sections || []).map((section) => [section.title, section.note, (section.items || []).map((item) => [item.label, item.detail, item.lines])]), (panel.doors || []).map((door) => door.label)]).replace(NAMED, "");
  let panels = 0;
  for (const species of SPECIES) for (const item of catalogue.of(species)) {
    // The text view (the List with no 3D) gives the same panel (textDescribe is describe).
    for (const panel of [describe(catalogue, species, item.id, { scene }), ...[...(item.size?.parts || []), ...(item.size?.chains || [])].map((part) => describePart(catalogue, species, item.id, part.id, { scene }))].filter(Boolean)) {
      assert.doesNotMatch(said(panel), TOOL, `${species} ${panel.id || item.id}: ${said(panel).match(TOOL)?.[0]}`);
      panels += 1;
    }
  }
  // And what was looked for by family and not found, listed apart.
  for (const species of SPECIES) for (const row of catalogue.noneFound(species)) {
    const panel = describe(catalogue, species, `machine:${row.id}`, { scene });
    assert.doesNotMatch(said(panel), TOOL, `${species} ${row.id}`);
    assert.doesNotMatch(said(panel), CLAIMED, `${species} ${row.id}`);
    panels += 1;
  }
  assert.ok(panels > 800, `${panels} panels: every machine, unit, part and chain of the eight benches, and what is listed apart`);
  // A source that is a file of the tree: named in words in the list, the file itself in the panel's list of files.
  const proteasome = describe(catalogue, "planarian", "machine:proteasome", { scene });
  assert.ok(proteasome.sections.find((section) => section.title === "Sources and licences").items.some((item) => item.label.startsWith("The planarian atlas's own table of the species' proteins:")));
  assert.ok(proteasome.sources.some((source) => source.path === "visualizer/data/proteins/planarian/predicted_proteins.tsv"));
  // A machine of a species whose bench is not in hand is not "not in" it: its bench is being read, or could not be.
  const shown = new Catalogue(core, { ...scene, catalogue: core });
  assert.match(describe(shown, "human", "machine:ribosome", { scene }).note, /^The machines of Human are being read\.$/);
  shown.benches.set("human", { status: "failed", words: "The machines of this species could not be read (a test)." });
  assert.equal(describe(shown, "human", "machine:ribosome", { scene }).note, "The machines of this species could not be read (a test).");
  assert.match(describe(shown, "syn3a", "machine:nuclear-pore", { scene })?.note || "", /^The catalogue lists it for /, "a machine the species lacks still says which species have it");
});

test("what an address or a door names waits on its species' bench: chosen once it is read, at its level, and flown to, as on a bench in hand", async () => {
  // The core alone in the page, its bench read when the test lets it.
  const cold = (species) => {
    let open = null;
    const gate = new Promise((resolve) => (open = resolve));
    const shown = lensFor(species, { raw: { ...scene, catalogue: core }, load: async (where) => (await gate, readJSON(where)) });
    return { ...shown, open };
  };
  const inHand = (species, id) => {
    const shown = lensFor(species);
    shown.lens.setSelection(id);
    shown.lens.focus(id);
    return shown;
  };
  const same = (a, b, what) => {
    for (const key of ["selected", "selectedPart"]) assert.equal(a.lens[key], b.lens[key], `${what}: ${key}`);
    assert.equal(a.lens.built.get(a.lens.selected)?.level, b.lens.built.get(b.lens.selected)?.level, `${what}: its level`);
    assert.deepEqual(a.flights.at(-1), b.flights.at(-1), `${what}: the same flight`);
  };
  // An address or a door: the viewer waits on `ready`, then chooses (a machine, a chain, a part, a unit, a card).
  for (const [species, id] of [["human", "machine:ribosome"], ["human", "machine:proteasome:chain-U"], ["mouse", "machine:ribosome:small"], ["mouse", "unit.U39"], ["planarian", "machine:proteasome"]]) {
    const shown = cold(species);
    const ready = shown.lens.ready;
    assert.ok(ready?.then, `${species}: not ready while its bench is read`);
    assert.ok(!shown.lens.has(id) || !id.split(":")[2], `${species} ${id}: a part is not known before its bench`);
    // The viewer's select waits on the bench for what the view does not hold yet (a part, a chain), and only for that.
    assert.equal(shown.lens.waitsFor(id), shown.lens.has(id) ? null : ready, `${species} ${id}`);
    shown.open();
    await ready;
    assert.equal(shown.lens.ready, null, "ready once it is laid out");
    shown.lens.setSelection(id);
    shown.lens.focus(id);
    same(shown, inHand(species, id), `${species} ${id}`);
  }
  // A choice made while the bench is read (a unit pressed meanwhile, a machine from the List): chosen again on the bench
  // laid out, at its own levels, and flown to where it stands now, once.
  for (const [species, id] of [["mouse", "unit.U39"], ["human", "machine:ribosome"], ["thalecress", "machine:rna-polymerase"]]) {
    const shown = cold(species);
    shown.lens.setSelection(id);
    shown.lens.focus(id);
    const before = shown.flights.length, ready = shown.lens.ready;
    shown.open();
    await ready;
    assert.equal(shown.flights.length, before + 1, `${species} ${id}: one flight, though both the species and the activation asked for the bench`);
    same(shown, inHand(species, id), `${species} ${id}, chosen while its bench was read`);
  }
});

test("a bench by family holds only the machines its species' records name or that have candidates; the others are listed apart, and told as looked for", () => {
  // No bench holds a machine its family route alone names with no candidate; each such machine is listed apart, with its reference.
  for (const species of Object.keys(core.benches)) {
    const bench = benchOf(species);
    for (const entry of bench.entries) assert.ok(!(entry.named?.by === "family signature" && !entry.gathered?.proteins?.length), `${species} ${entry.id}: on the bench with no candidate`);
    for (const row of bench.none_found || []) {
      assert.ok(!bench.entries.some((entry) => entry.id === row.id) && !raw.kinds.find((kind) => kind.id === row.id).species.includes(species), `${species} ${row.id}: listed apart, and in no kind's species`);
      assert.ok(row.looked_for.length && row.looked_for.every(([, , outcome, count]) => outcome !== "candidates" && count === 0), `${species} ${row.id}: no candidate`);
      // The dossier's own sentence gives the same counts as its rows.
      const many = (outcome) => String(row.looked_for.filter((value) => value[2] === outcome).length);
      assert.deepEqual(row.text.match(/\b\d+\b/g), ["0", String(row.looked_for.length), "0", "0", String(row.looked_for.filter((value) => value[1] === "part").length), many("not in the table"), many("cannot tell"), many("no family signature")], `${species} ${row.id}`);
    }
    assert.equal(core.benches[species].machines, bench.entries.length, `${species}: the core's count is the bench's`);
  }
  // The three benches by family: what stands on each, and what is listed apart.
  const shown = (species) => ({ machines: benchOf(species).entries.length, named: benchOf(species).entries.filter((entry) => entry.named?.by !== "family signature").length, family: benchOf(species).entries.filter((entry) => entry.named?.by === "family signature").length, none: (benchOf(species).none_found || []).map((row) => row.id) });
  // Since the planarian's own scan (19 November 2026) every machine looked for has a candidate: myosin II stands on the bench, and none is listed apart.
  assert.deepEqual(shown("planarian"), { machines: 32, named: 1, family: 31, none: [] }); // and the vault, a candidate by family (19 November 2026)
  assert.deepEqual(shown("syn3a"), { machines: 9, named: 6, family: 3, none: ["tat-translocase", "bam-complex", "chaperonin", "clpxp", "hslv", "complex-i", "complex-ii", "cytochrome-bo3", "recbcd", "chemoreceptor-array"] });
  assert.deepEqual(shown("mpneumoniae"), { machines: 11, named: 7, family: 4, none: ["tat-translocase", "bam-complex", "clpxp", "hslv", "complex-i", "complex-ii", "cytochrome-bo3", "recbcd", "chemoreceptor-array"] });
  // What the species' own file names stays, whatever the family route found.
  for (const id of ["ribosome", "rna-polymerase", "atp-synthase", "protein-translocon", "ftsh", "lon"]) assert.ok(catalogue.item("syn3a", `machine:${id}`), id);
  assert.ok(catalogue.item("mpneumoniae", "machine:attachment-organelle"));
  // The card's counts are the bench's: the machines its own records name, the candidates by family, the units.
  for (const species of ["planarian", "syn3a", "mpneumoniae"]) {
    const { lens } = lensFor(species);
    const items = catalogue.of(species), stats = Object.fromEntries(lens.chrome().card.stats.map(([value, label]) => [label, value]));
    assert.deepEqual(stats, { "named by its own records": shown(species).named, "candidates by family": shown(species).family, "in the law inventory": items.filter((item) => item.unit).length }, species);
    assert.equal(lens.layout.items.filter((item) => !item.item.unit).length, shown(species).machines, `${species}: the bench lays out its machines, and no other`);
    // A candidate by family says so on its card's face, in words; a machine its records name has its name alone.
    const faces = lens.plaques.map((plaque) => plaque.text);
    for (const item of items.filter((value) => value.entry && !value.sized)) {
      const rows = item.entry.gathered?.looked_for || [];
      const said = `candidates for ${rows.filter((row) => row[2] === "candidates").length} of ${rows.length} ${rows.length === 1 ? "part" : "parts"},`;
      assert.equal(faces.includes(said) && faces.includes("by family"), item.entry.named?.by === "family signature" ? true : faces.includes(said), `${species} ${item.id}`);
    }
  }
  assert.ok(lensFor("planarian").lens.plaques.some((plaque) => plaque.text === "candidates for 31 of 32 parts," && plaque.tone === "soft"));
  // Listed apart: in the List under its own heading with the caveat, each with its reference; the search finds it there.
  const list = sections(catalogue, "syn3a");
  const apart = list.find((section) => section.label === "Looked for by family, no candidate found");
  assert.equal(apart.entities.length, 10);
  assert.match(apart.note, /This says what Syn3A's table holds, not that Syn3A lacks the machine/);
  assert.ok(apart.entities.some((entity) => entity.id === "machine:bam-complex" && entity.label === "BAM complex (E. coli's)" && entity.swatch === "mach-none"));
  assert.ok(!list.filter((section) => section !== apart).some((section) => section.entities.some((entity) => entity.id === "machine:bam-complex")), "never as a machine of the species");
  assert.ok(sections(catalogue, "planarian").flatMap((section) => section.entities).some((entity) => entity.id === "machine:proteasome" && entity.label === "Proteasome · candidates by family"), "a candidate by family is said so in the List");
  assert.ok(sections(catalogue, "syn3a").flatMap((section) => section.entities).some((entity) => entity.id === "machine:ribosome" && entity.label === "Ribosome"), "a machine its own file names, as it was");
  // Its panel: what was looked for, and that it is not on the bench.
  const bam = describe(catalogue, "syn3a", "machine:bam-complex", { scene });
  assert.equal(bam.chips[0].label, "No candidate found");
  assert.match(bam.note, /^Looked for by family, no candidate found: .*not that Syn3A lacks the machine; none of them is on Syn3A's bench\.$/);
  assert.equal(bam.facts[0][1], "No protein of Syn3A's table is a candidate, by its InterPro family, for any of the 5 parts of E. coli's machine. For 5 parts no line of Syn3A's table carries the family, which says what the table holds, not that Syn3A lacks the protein; for 0 the table cannot tell, its scan being older than the family; 0 have no family to look for.");
  // The card lists them, and its search finds them there, not as machines of the species.
  const { lens } = lensFor("syn3a");
  lens.setQuery("bamA");
  assert.equal(lens.chrome().legend.items.find((item) => item.id === "mach-found")?.count ?? 0, 0, "no machine of the species is found by it");
  assert.ok(lens.catalogue.noneFound("syn3a").some((row) => row.looked_for.some(([gene]) => gene === "bamA")));
});

test("a protein's door into Machines says what its dossier makes it: a part, a part by keyword, or a candidate by family; an unknown tier has none", () => {
  const WORDS = {
    part: /^It is a part of the [^:]+: show it in Machines$/,
    "deposited chain": /^A chain of this protein is resolved in [^:]+: show it in Machines$/,
    "part by keyword": /^It is a part, by UniProt's keyword, of the [^:]+: show it in Machines$/,
    named: /^It is named with the [^:]+: show it in Machines$/,
    "candidate by family": /^It is a candidate, by its family, for a part of (?:(?:Human|E\. coli)'s [^:]+|the vault): show it in Machines$/,
    // The vault's footings, each in its own words (19 November 2026); the record alone says part.
    "part by record": /^It is a part, by the Complex Portal's record, of the vault: show it in Machines$/,
    "named by a reviewed entry, by similarity": /^It is named with the vault in UniProt's reviewed entry, by similarity to another species' protein: show it in Machines$/,
    "named by a reviewed entry, citing publications": /^It is named with the vault in UniProt's reviewed entry, which cites publications for some of its lines: show it in Machines$/,
  };
  let doors = 0;
  for (const species of Object.keys(core.benches)) {
    for (const [accession, rows] of Object.entries(benchOf(species).by_protein)) {
      const shown = doorsFor({ id: `own:${species}:p:${accession}` }, scene, { species });
      for (const [kind, tier] of rows) {
        const door = shown.find((value) => value.value === `machine:${kind}`);
        if (!catalogue.item(species, `machine:${kind}`)) continue;
        assert.ok(door && WORDS[tier]?.test(door.label), `${species} ${accession} ${kind} (${tier}): ${door?.label}`);
        doors += 1;
      }
    }
  }
  assert.ok(doors > 2000, `${doors} doors`);
  const item = catalogue.item("planarian", "machine:proteasome");
  assert.equal(doorWords("candidate by family", item, scene), "It is a candidate, by its family, for a part of Human's proteasome");
  assert.equal(doorWords("a tier no dossier gives", item, scene), null, "an unknown tier has no door");
});

test("a unit whose shape file cannot be read says why in its panel, as a machine does", async () => {
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const { lens } = lensFor("planarian");
  lens.surfaces = new Map([["shapes/animals.sodium-pump.json", { status: "failed", data: null, words: "The shape file shapes/animals.sodium-pump.json could not be read (a test)." }]]);
  lens.setSelection("unit.U39");
  lens.setMode("4");
  await settle();
  assert.ok(!lens.built.get("unit.U39").surface && lens.built.get("unit.U39").bodies.visible);
  // The page builds a unit's panel through `present`: it says why all the same.
  const panel = present(scene.entities.find((entity) => entity.id === "unit.U39"), scene, "planarian");
  assert.equal(panel.facts.find(([label]) => label === "Its shape")[1], "The shape file shapes/animals.sodium-pump.json could not be read (a test).");
  lens.catalogue.shapeWords.clear();
});

test("each bench is published beside the page at catalogue/<species>.json, and the local server answers it", async () => {
  const { benchFiles, buildPage } = await import("../tools/lib/build_page.mjs");
  const { files, problems } = await benchFiles();
  assert.deepEqual(problems, []);
  assert.deepEqual(files.map((file) => file.path), Object.values(core.benches).map((bench) => bench.file).sort());
  const { createServer } = await import("../tools/serve.mjs");
  const server = createServer({ offline: true, log: () => {} });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const answer = await fetch(`http://127.0.0.1:${server.address().port}/catalogue/human.json`);
    assert.equal(answer.status, 200);
    assert.equal((await answer.json()).species, "human");
    assert.equal((await fetch(`http://127.0.0.1:${server.address().port}/catalogue/none-such.json`)).status, 404);
  } finally {
    server.close();
  }
  // A page for the disk carries every bench inside it, as it carries its shapes.
  const page = await buildPage({ inlineRuns: true, runsDir: path.join(ROOT, "data", "no-such-folder") });
  for (const file of files) assert.ok(page.includes(`data-file="${file.path}"`), file.path);
});

test("every measured machine and unit, at every level it has, stays within the ceiling on its species' bench", async () => {
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  let heaviest = { triangles: 0 };
  for (const species of SPECIES) {
    const { lens } = lensFor(species, { width: 390, height: 844 });
    lens.surfaces = new Map();
    for (const item of catalogue.of(species)) {
      if (item.size?.shape !== "measured") continue;
      const file = item.size.surface?.file;
      if (file && !lens.surfaces.has(file)) lens.surfaces.set(file, { status: "found", data: read(`data/catalogue/${file}`) });
      lens.setSelection(item.id);
      for (const level of levelsOf(item) || [{ id: 1 }]) {
        lens.setMode(String(level.id));
        await settle();
        const cost = lens.cost();
        assert.ok(cost.draws <= 40 && cost.triangles <= 40000, `${species} ${item.id} at level ${level.id}: ${JSON.stringify(cost)}`);
        if (cost.triangles > heaviest.triangles) heaviest = { species, id: item.id, level: level.id, ...cost };
      }
      lens.setSelection(null);
    }
  }
  console.log(`# the heaviest chosen machine at any level: ${JSON.stringify(heaviest)}`);
});

test("a chain named by an address while a shape of parts is shown: the machine goes to its Subunits, and the Detail says so", async () => {
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const { lens } = lensFor("human");
  let told = 0;
  lens.onChrome = () => told++;
  lens.surfaces = new Map([["shapes/human.mitochondrial-ribosome.json", { status: "found", data: read("data/catalogue/shapes/human.mitochondrial-ribosome.json") }]]);
  lens.setSelection("machine:mitochondrial-ribosome");
  lens.setMode("4");
  await settle();
  assert.equal(lens.built.get("machine:mitochondrial-ribosome").level, 4);
  const chain = catalogue.item("human", "machine:mitochondrial-ribosome").size.chains[3].id;
  told = 0;
  lens.setSelection(`machine:mitochondrial-ribosome:${chain}`);
  assert.equal(lens.built.get("machine:mitochondrial-ribosome").level, 3, "its shape is of its two parts: the chain is drawn at Subunits");
  assert.equal(lens.chrome().card.modes.active, "3");
  assert.ok(told > 0, "the card is drawn again");
  assert.ok(lens.cost().triangles <= 40000, JSON.stringify(lens.cost()));
});

// Since 19 November 2026: the Complex Portal's forms in a kind's panel, and the vault with its three footings. About 0.1 s
// (panels only, nothing compiled or drawn). The reason: these are the words the page says, and a footing said in the wrong words,
// or a form counted as a machine, is a claim the record does not make.
test("a kind's forms stand in its panel and are no machines; the vault says each footing in its own words and puts no prokaryotic vault on a bench", () => {
  const words = (species, id) => describe(catalogue, species, id, { scene });
  const fact = (panel, label) => panel.facts.find(([name]) => name === label)?.[1];
  const forms = (panel) => panel.sections.find((section) => section.title === "Forms the Complex Portal curates");
  // Forms: lines of a kind's panel, in no count and on no bench of their own.
  const proteasome = forms(words("human", "machine:proteasome"));
  assert.equal(proteasome.items.length, 13);
  assert.equal(proteasome.shown, 4, "the first few stand and the rest open by a press");
  assert.ok(proteasome.items.every((item) => /^CPX-\d+ · \d+ proteins? · holds \d+ of this machine's \d+ parts$/.test(item.detail) && /^https:\/\/www\.ebi\.ac\.uk\/complexportal\/complex\/CPX-\d+$/.test(item.links[0].url)));
  const evidence = new Set(proteasome.items.map((item) => item.lines.at(-1).replace(/^Evidence ECO:\d+\. /, "")));
  assert.ok([...evidence].every((line) => ["Seen in this species' own proteins (a physical interaction).", "Put together by the Complex Portal's curators from the literature.", "Inferred: not observed in this species. The Complex Portal takes it from the same complex in another species, which its record does not name."].includes(line) || /^Taken from a paralogous complex of this species\.$|^Inferred: not observed in this species\. The Complex Portal takes it from the same complex in /.test(line)), [...evidence].join(" | "));
  const mouse = Object.values(Object.fromEntries(catalogue.of("mouse").filter((item) => item.entry?.gathered?.forms).map((item) => [item.id, item.entry.gathered.forms.items.length])));
  assert.ok(mouse.length > 0 && catalogue.of("mouse").every((item) => !item.id.startsWith("machine:CPX")), "forms are no machine");
  assert.ok(!forms(words("human", "machine:myosin-ii")) && !forms(words("human", "machine:axonemal-dynein")), "an entry that is not a form of the kind is kept out (the nexin-dynein regulatory complex holds 2 of the 14 parts)");
  assert.ok(!forms(words("human", "machine:nuclear-pore")).items.some((item) => item.detail.startsWith("CPX-2477")), "TREX-2 is an exception, with its reason in gather.json");
  // The vault: three footings, each in its own words.
  const human = words("human", "machine:vault"), mouseVault = words("mouse", "machine:vault"), planarian = words("planarian", "machine:vault");
  assert.match(fact(human, "Named by"), /^By the record: the Complex Portal's entry CPX-10181, “Vault ribonucleoprotein complex”, lists MVP \(78 copies\), TEP1 \(no number of copies given\) and PARP4 \(no number of copies given\) and 4 vault RNAs, named by their RNAcentral identifiers/);
  assert.match(fact(mouseVault, "Named by"), /^Named by a reviewed entry, by similarity or with citations: UniProt's reviewed entries E9PYK3, P97499 and Q9EQK5 name the vault particle .* the proteins are not called parts\./);
  assert.match(fact(planarian, "Named by"), /^By family alone: h1SMcG0002250 \(IPR039059\) carries the signature of the major vault protein family \(IPR039059\) or PARP4's marker domain \(IPR058904\), as marked\. A candidate is a candidate\. A signature not found is not an absence/);
  const footing = (panel, gene) => panel.sections.find((section) => section.title === "Its proteins, each on its own footing").items.find((item) => item.label === gene).lines.join("\n");
  assert.match(footing(mouseVault, "Parp4"), /every one marked “by similarity” to the human protein Q9UKK3\. This is a footing of its own, firmer than a family alone and weaker than a record; it does not make the protein a part of the vault\./);
  assert.match(footing(mouseVault, "Mvp"), /1 cites publications and 5 are marked “by similarity” to the human protein Q14764/);
  assert.match(footing(human, "PARP4"), /Copies of PARP4 in a vault, two curated sources: the Complex Portal's entry says “There are about 9 copies of PARP4 per vault which may act to ADP-ribosylate itself and MVP”; UniProt's entry says “Interacts with MVP \(via MVP repeats 3 and 4\); each MVP subunit binds a single PARP4 molecule, allowing each vault to house up to 78 PARP4 molecules \(PubMed:40691181\)”\. Both stand, each in its source's words; the page reconciles nothing\./);
  assert.match(footing(human, "TEP1"), /Its entry also names it a component of another complex, FUNCTION: “Component of the telomerase ribonucleoprotein complex that is essential for the replication of chromosome termini \(PubMed:19179534\)” \(cites PubMed:19179534\)/);
  assert.match(footing(human, "TEP1"), /\(by similarity to the mouse protein P97499\)/, "the human TEP1's vault lines are by similarity to the mouse's TEP1, not to a human protein");
  assert.match(footing(planarian, "h1SMcG0002250"), /A candidate is a candidate: it is not called a part of the vault/);
  for (const panel of [human, mouseVault, planarian]) {
    assert.match(fact(panel, "How big"), /^The Complex Portal's entry CPX-10181 \(the human vault\): 72\.5 by 41 by 41 nm, about 13 MDa\. The preprint, for mammalian vaults: “about 67 nm long and 40 nm wide” \(Introduction, .*The viewer's measure of a structure: 74\.5 by 50\.4 by 50\.4 nm/);
    const preprint = fact(panel, "A preprint on prokaryotic vaults");
    assert.match(preprint, /^A bioRxiv preprint, not peer reviewed, posted 5 November 2026: Athukoralage and others, doi:10\.64898\/2026\.11\.04\.764334, version 1 \(CC BY 4\.0\), reports that relatives of the major vault protein from phages and some bacteria form vault-like particles when they are made in a host bacterium: it says “homologs assemble into vaults when expressed in Escherichia coli” \(Introduction, the paragraph that begins “Here, we survey”\), “found MVP homologs in 29 bacterial and 4 archaeal phyla” \(Abstract\)/);
    assert.match(preprint, /Whether such particles form in the organisms themselves, and what they do, is not known: .* No prokaryotic vault stands on any bench as a species' machine/);
    assert.match(fact(panel, "What it does"), /^Not known\./);
  }
  assert.match(fact(human, "How many"), /predicted to hold about 10,000 vaults.*not a measured count/);
  assert.equal(fact(mouseVault, "How many"), "No count in hand for this species");
  assert.match(fact(mouseVault, "A structure of its own"), /3GF5, 3GNF and 3GNG, which are fragments or parts of the particle, none taken for it\. The size and shape are those of a vault of the human, measured from Protein Data Bank entry 9MXV/);
  assert.doesNotMatch(fact(mouseVault, "How big"), /none in hand/, "the mouse's own fragments exist: the page does not say none is in hand");
  // A species in which no signature was found: no vault on its bench, and the panel that names it says what was looked for, not an absence.
  for (const species of ["ecoli", "fruitfly", "thalecress", "syn3a", "mpneumoniae"]) {
    assert.ok(!catalogue.item(species, "machine:vault"), `${species}: no vault on its bench`);
    const panel = words(species, "machine:vault");
    assert.match(panel.eyebrow, /^Machines · not shown for /);
    assert.match(fact(panel, "What was looked for"), /^(UniProt's list of the entries of the reference proteome|No protein of .* table carries) .*the vault particle\.$/);
    assert.match(panel.note, /A signature not found in a species is not an absence/);
  }
  // A species the catalogue holds no bench for (the frog): its panel says that no bench was gathered, never that the species lacks the
  // machine, and nothing of a signature looked for, since none was.
  const frog = words("xenopus", "machine:vault");
  assert.match(frog.eyebrow, /^Machines · no bench for /);
  assert.match(frog.note, /^No bench of machines has been gathered for .* yet: nothing here says whether it has this one\. The catalogue lists it for /);
  assert.ok(!/signature|absence/.test(frog.note) && frog.facts.length === 0, frog.note);
  // Its way to and from the Protein atlas, per protein.
  assert.ok(["Q14764", "Q99973", "Q9UKK3"].every((id) => human.doors.some((door) => door.find === id)) && ["Q9EQK5", "E9PYK3"].every((id) => mouseVault.doors.some((door) => door.find === id)) && planarian.doors.some((door) => door.find === "h1SMcG0002250"));
  assert.ok(catalogue.machinesOf("mouse", "Q9EQK5").some(([kind, tier]) => kind === "vault" && tier === "named by a reviewed entry, citing publications"));
  assert.equal(catalogue.item("human", "machine:vault").size.entry, "9MXV-assembly1");
  assert.equal(catalogue.kinds.get("vault").group, "unknown");
  assert.ok(catalogue.groupById.get("unknown") && catalogue.kinds.get("vault").identified_by === "vault");
});

// About 0.2 s: it builds the human's organelles once with the Cell view's own builders (no WebGL), to hold their sizes.
test("the organelles on the shelf: no machines, sized by their species' file's facts, drawn by the Cell view's models, and said with the map's status", () => {
  const shelf = catalogue.organellesOf("human");
  assert.deepEqual(shelf.map((item) => item.id), ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "lipid-droplet", "mitochondrion", "autophagosome", "lysosome", "peroxisome", "centriole", "endocytic-vesicle", "copi-vesicle"].map((kind) => `organelle:${kind}`));
  assert.ok(catalogue.of("human").every((item) => !item.organelle) && catalogue.counts("human").machines === catalogue.of("human").length, "no organelle is a machine or in a count of machines");
  const human = read("data/species/human.json");
  for (const item of shelf.filter((value) => value.size && !(value.size.held && !value.size.text))) {
    const fact = human.cell.facts.find((value) => value.label === item.size.label);
    assert.equal(item.size.text, fact.value, `${item.id}: its size is its species' file's fact, whole`);
    for (const key of fact.sources) assert.equal(human.sources[key].class, "permissive", `${item.id}: ${key}`);
  }
  assert.ok(shelf.filter((value) => !value.size).every((item) => /^Looked for on \d+ [A-Z][a-z]+ \d{4}: /.test(item.entry.no_size)), "one with no size says what was looked for");
  for (const item of shelf) {
    const panel = describe(catalogue, "human", item.id, { scene });
    const map = scene.entities.find((entity) => entity.id === item.kind.map_part), status = map && scene.statuses.find((value) => value.id === map.status);
    if (map) assert.equal(panel.sections[0].items[0].detail, status.label, `${item.id}: the map's own status of its part, read from the scene`);
    else assert.match(panel.note, /^No part of the map stands at it/, `${item.id}: nothing said of what Cells models of it`);
    // The map's own words are quoted as the map's; the files it rests on are named as they are, headings and all.
    const words = JSON.stringify({ ...panel, sources: [] }).replace(/In the map's own words: “[^”]*”/g, "");
    assert.ok(!CLAIMED.test(words), `${item.id}: ${words.match(CLAIMED)?.[0]}`);
  }
  const { lens } = lensFor("human");
  const drawn = lens.ensureShelf().layout.items;
  const at = (id) => drawn.find((entry) => entry.id === id);
  assert.ok(Math.abs(at("organelle:nucleus").w - 1000) < 2, `the nucleus drawn 10 µm across, by its held size: ${at("organelle:nucleus").w}`);
  // An organelle the Cell view has no model of: a plain shape at its size (the lysosome's single example, 0.56 µm; the peroxisome at
  // the middle of an encyclopedia's range); listed in the species' file's `cell.parts.shelf`, which the Cell view does not read.
  assert.ok(at("organelle:lysosome").type === "shape" && Math.abs(at("organelle:lysosome").w - 56) < 0.5 && Math.abs(at("organelle:peroxisome").w - 55) < 0.5);
  assert.deepEqual(organellesOfCell(human.cell.parts), ["er", "golgi", "mitochondria"], "the Cell view's own list of what it draws is as it was");
  // The page says the nucleus's drawn size and its basis in words; no number of the held paper, its name or its licence's class.
  const nucleusPanel = JSON.stringify(describe(catalogue, "human", "organelle:nucleus", { scene }));
  const held = read("data/catalogue/held_sizes.json").species.human.nucleus;
  assert.ok(/Drawn about 10 µm across, near the size of a HeLa nucleus inside the cell, on a published measurement that the project's files cite and this page does not show/.test(nucleusPanel) && /visualizer\/data\/catalogue\/held_sizes.json/.test(nucleusPanel));
  for (const word of [held.source.doi, "Iida", "510 ± 121", "non-commercial"]) assert.ok(!nucleusPanel.includes(word), word);
  assert.ok(Math.abs(at("organelle:mitochondrion").w - 118) < 1 && Math.abs(at("organelle:mitochondrion").h - 55) < 1, "the mitochondrion 1.18 µm long and 0.55 µm wide");
  assert.deepEqual(drawn.filter((entry) => entry.type === "card").map((entry) => entry.id), [], "every organelle of the human's shelf is drawn (20 November 2026, step D)");
  assert.ok(lens.shelf.root.visible === false && lens.cost().triangles < 40000, "at the bench's stop the shelf is not drawn, and the bench costs what it did");
  assert.deepEqual(lens.railOf().map((stop) => stop.id).filter((id) => !id.startsWith("nm")), ["shelf", "small", "bench"]);
  // Step D (20 November 2026): the rest as 3D models. The reticulum and the Golgi by the Cell view's models, at a general figure's
  // sheet and cisterna; a centriole as one barrel of the Cell view's centrosome; the others simple models of their own; the small
  // ones on a plank of their own, with a stop of their own between the bench's and the shelf's.
  const model = (id) => lens.shelf.holders.get(id);
  const scaled = (id, key) => model(id).model.measure[key] * model(id).holder.scale.x;
  assert.ok(Math.abs(scaled("organelle:endoplasmic-reticulum", "thick") - 4) < 0.01, "the reticulum's sheets 40 nm thick, the middle of 30 to 50 nm");
  assert.ok(Math.abs(scaled("organelle:golgi-apparatus", "cisterna") - 75) < 0.01, "the Golgi's widest cisterna 0.75 µm, the middle of 0.5 to 1 µm");
  assert.ok(Math.abs(at("organelle:centriole").w - 40) < 0.5 && Math.abs(Math.max(at("organelle:centriole").h, at("organelle:centriole").d) - 20) < 0.5, "a centriole about 0.4 µm long and 0.2 µm across, held (one figure each)");
  assert.ok(Math.abs(at("organelle:endocytic-vesicle").h - 15) < 0.5 && Math.abs(at("organelle:copi-vesicle").w - 12.6) < 0.2 && Math.abs(at("organelle:autophagosome").h - 100) < 0.5 && Math.abs(at("organelle:lipid-droplet").w - 255) < 0.5);
  for (const id of ["organelle:lysosome", "organelle:peroxisome", "organelle:autophagosome", "organelle:copi-vesicle", "organelle:endocytic-vesicle", "organelle:lipid-droplet"]) {
    assert.ok(model(id).model.simple && model(id).model.materials.every((material) => material.userData.look?.hue), `${id}: a simple model, every material painted from the page's palette`);
    assert.match(lens.drawnWords(id), /a simple model of its own, since the Cell view has none; .*the picture's choice\. An illustration/, id);
  }
  assert.deepEqual(drawn.filter((entry) => entry.plank === "small").map((entry) => entry.id), ["mitochondrion", "autophagosome", "lysosome", "peroxisome", "centriole", "endocytic-vesicle", "copi-vesicle"].map((kind) => `organelle:${kind}`));
  const views = lens.stopViews();
  assert.ok(views.bench.distance < views.small.distance && views.small.distance < views.shelf.distance, "the small organelles' stop between the bench's and the shelf's");
  // Every organelle named at each stop, each name a way to it (on a wide window), and the frame's cost at the planks' stops.
  const { shown } = lensFor("human");
  const named = (stop) => {
    lens.labels = { add: (spec) => (shown.push(spec), spec), clear: () => shown.splice(0), remove() {} };
    lens.goToScale(stop, true);
    lens.stage.rig.distance = lens.homeView().distance;
    lens.stage.rig.target = lens.homeView().target;
    lens.band = null;
    lens.afterMove();
    return new Set(shown.map((spec) => spec.id).filter((id) => String(id).startsWith("organelle:")));
  };
  for (const stop of ["bench", "small", "shelf"]) {
    assert.deepEqual([...named(stop)].sort(), shelf.map((item) => item.id).sort(), `at the ${stop}'s stop every organelle is named`);
    assert.equal(lens.band, stop);
  }
  const heavy = lens.cost();
  console.log(`# the human's shelf's stop: ${JSON.stringify(heavy)}`);
  assert.ok(heavy.draws <= 64 && heavy.triangles <= 240000, `at the shelf's stop: ${JSON.stringify(heavy)}`);
  // The held sizes say only the size drawn and its basis in words.
  for (const id of ["organelle:centriole", "organelle:endocytic-vesicle"]) {
    const text = JSON.stringify(describe(catalogue, "human", id, { scene }));
    assert.match(text, /on a published measurement that the project's files cite and this page does not show/, id);
    const entry = read("data/catalogue/held_sizes.json").species.human[id.slice("organelle:".length)];
    for (const word of [entry.source.doi, entry.source.text.split(" and others")[0], "non-commercial", ...(entry.read.results.match(/\d+(?:[–-]\d+)? nm/g) || [])]) assert.ok(!text.includes(word), `${id}: ${word}`);
  }
  // A general figure says it is one, and stands only as far as its reference's qualifier reaches (the narrow reading).
  for (const label of ["Endoplasmic reticulum", "Golgi apparatus", "Lipid droplet", "Autophagosome"]) assert.match(human.cell.facts.find((fact) => fact.label === label).value, /general (figure|range)/, label);
  const mouse = read("data/species/mouse.json");
  assert.deepEqual(mouse.cell.facts.filter((fact) => /general (figure|range)/.test(fact.value)).map((fact) => fact.label), ["Golgi apparatus", "Autophagosome"], "for mammalian cells only");
  assert.ok(Math.abs(lensFor("mouse").lens.ensureShelf().layout.items.find((entry) => entry.id === "organelle:nucleus").w - 620) < 2, "the mouse's nucleus 6.2 µm across, a sphere of 126 µm³ (ours)");
  // Every bench, a row each (20 November 2026, round 2): the organelles its species' cell holds, sized where a permissive number was read,
  // else a card that says what was looked for; a species whose cell holds none has no shelf, no rail and no page scale bar.
  const ROWS = {
    human: ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "lipid-droplet", "mitochondrion", "autophagosome", "lysosome", "peroxisome", "centriole", "endocytic-vesicle", "copi-vesicle"],
    mouse: ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "mitochondrion", "autophagosome"],
    fruitfly: ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "mitochondrion"],
    planarian: ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "mitochondrion"],
    thalecress: ["nucleus", "endoplasmic-reticulum", "golgi-apparatus", "mitochondrion", "chloroplast", "vacuole"],
    ecoli: [], syn3a: [], mpneumoniae: [], xenopus: [], physarum: [], // the frog: no bench gathered yet, so no shelf
  };
  assert.deepEqual(Object.keys(ROWS).sort(), [...SPECIES].sort());
  for (const [species, kinds] of Object.entries(ROWS)) {
    const items = catalogue.organellesOf(species);
    assert.deepEqual(items.map((item) => item.id), kinds.map((kind) => `organelle:${kind}`), species);
    for (const item of items) assert.ok(item.size || /^Looked for on /.test(item.entry.no_size), `${species} ${item.id}: a size, or what was looked for`);
    const shown = lensFor(species).lens;
    assert.equal(Boolean(shown.chrome().rail), kinds.length > 0, `${species}: a rail only with a shelf`);
    assert.equal(shown.scaleInfo() === null, kinds.length === 0, `${species}: the page's scale bar only with a shelf`);
  }
  const plant = lensFor("thalecress").lens.ensureShelf().layout.items.find((entry) => entry.id === "organelle:chloroplast");
  assert.ok(plant.type === "shape" && Math.abs(plant.w - 560) < 2, `the chloroplast as its file states it, 5.6 µm across: ${plant.w}`);
});
