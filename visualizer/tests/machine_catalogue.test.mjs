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
import { describe, describePart, sections, doorsFor, textSections, textDescribe, present, recordLines, levelsOf } from "../src/lenses/machines_card.js";
import { layoutOf, shapeOf, UNIT_NM, CARD } from "../src/lenses/machines_layout.js";
import { MachinesLens, MARKS } from "../src/lenses/machines.js";

const read = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const raw = read("data/catalogue/catalogue.json");
const overlay = read("data/catalogue/overlay.json");
const scene = { ...read("data/architecture/architecture.scene.json"), catalogue: raw };
const motor = read("data/machines/ecoli.flagellar-motor.json");
const catalogue = new Catalogue(raw, scene);
const SPECIES = [...new Set([...raw.entries.map((entry) => entry.species), ...(scene.proteins.atlases || []).map((atlas) => atlas.id)])];
/** A word of a status the record has not given: none may stand on the page for a machine (D209). */
const CLAIMED = /(?<!not |no )\b(modelled|modeled|qualified|judged|designed|simulated)\b/i;

test("the catalogue is what its tool writes, from the files it names", () => {
  const written = execFileSync("python3", [path.join(ROOT, "tools", "build_catalogue.py"), "--out", "-"], { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  assert.equal(written, readFileSync(path.join(ROOT, "data", "catalogue", "catalogue.json"), "utf8"), "run python3 tools/build_catalogue.py");
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

test("every number stands on a permissive source the entry names, and a size is its species file's own, never a second number", () => {
  for (const entry of raw.entries) {
    for (const block of [entry.count, entry.size, entry.named].filter(Boolean)) {
      for (const key of block.sources || []) assert.equal(raw.sources[key]?.class, "permissive", `${entry.species} ${entry.id}: ${key}`);
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
  // The overlay holds no size of its own: a size is read from a species' fact or from a part of its cell.
  for (const list of Object.values(overlay.species)) for (const item of list) if (item.size) assert.ok(item.size.part || item.size.fact || overlay.measures[item.size.measure], JSON.stringify(item.size));
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
      const words = JSON.stringify({ ...panel, sections: (panel.sections || []).filter((section) => section.key !== "laws") });
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
  assert.equal(catalogue.counts("thalecress").sized, 0, "the plant's machines and units stay cards: the measures stand on the animals' benches");
  // The list and the text page: every machine once, by group.
  for (const species of SPECIES) {
    const listed = sections(catalogue, species).flatMap((section) => section.entities.map((entity) => entity.id));
    assert.deepEqual(listed.sort(), catalogue.of(species).map((item) => item.id).sort(), species);
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
  assert.equal(layoutOf(catalogue.of("thalecress"), raw.groups, { columns: 1 }).scale, null, "no scale bar where nothing is drawn to scale");
});

/** The view with stand-ins for the stage and the labels: no WebGL, the view only makes objects. */
function lensFor(species, { width = 1400, height = 900 } = {}) {
  const shown = [];
  const labels = { add: (spec) => (shown.push(spec), spec), clear: () => shown.splice(0), remove() {} };
  const palette = { ghost: "#77889a", fg: "#12283a", plate: "#e3eaf1", edge: "#566878", plateEdge: "#bccad7", accent: "#1f6fd0", bg: "#eef2f6", bioRibosome: "#4c4aa8", bioProtein: "#3f86e0", bioMito: "#f0874a", bioIon: "#37b58c", dark: false };
  const flights = [];
  const stage = { palette, scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(34, width / height, 0.1, 5000), width, height, reducedMotion: true, invalidate() {}, rig: { setView() {}, flyTo: (view) => flights.push(view) }, dress() {} };
  const lens = new MachinesLens(stage, { raw: scene }, labels);
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
  assert.deepEqual(sized("planarian"), ["machine:ribosome", "unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]);
  // Only these five units have a size, each from a structure of its own kind (Kv1.1 is not Kv1.2; Cx45 is not Cx43).
  const units = Object.keys(raw.unit_sizes.units).sort();
  assert.deepEqual(units, ["unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]);
  for (const species of SPECIES) for (const item of catalogue.of(species)) if (item.unit && item.size) assert.ok(units.includes(item.unit.id), `${species}: ${item.unit.id}`);
  for (const species of ["thalecress", "ecoli", "syn3a", "mpneumoniae"]) assert.equal(catalogue.of(species).filter((item) => item.unit && item.size).length, 0, species);
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
  assert.match(big("planarian", "machine:ribosome"), /the measure leaves out RACK1/);
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
  assert.deepEqual(levelsOf(catalogue.item("ecoli", "machine:atp-synthase")).map((level) => level.label), ["Outline", "Parts", "Subunits"]);
  assert.deepEqual(levelsOf(catalogue.item("ecoli", "machine:lon")).map((level) => level.label), ["Outline", "Subunits"], "Lon has no named parts: its whole, then its six chains");
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

test("the legend names every mark that is drawn, and the card says what is and is not in hand", () => {
  const { lens } = lensFor("thalecress");
  const chrome = lens.chrome();
  assert.ok(!chrome.legend.items.some((item) => item.id === "mach-sized"), "no shape is drawn for the thale cress");
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
  for (const word of ["needs: (scene) => scene.catalogue?.entries?.length", "owns: machinesOwn", "doorsFor: machinesDoors", "textSections: machinesSections", "present: machinesPresent", "styles: MACHINES_CSS"]) assert.ok(entry.includes(word), word);
  // The view shown keeps an id it holds itself: a closer view in the Cell view keeps machine:<id>.
  assert.match(viewer, /const owner = id && !this\.current\?\.has\?\.\(id\) && this\.views\?\.find/);
});
