// A machine drawn from its file (schema/MACHINES.md): the flagellar motor of E. coli first.
// The file is held to its contract (a basis for every number, organisms as the sentences name
// them, places that agree with the spans, every protein of the set once); the drawing to the
// file's sizes and counts; the rotor's turn to its rate, its way and the real time that passed,
// never stroboscopic; the panel to what it must say; and the Protein atlas's door that names
// some proteins of a set. Where the saved papers are on the machine, their sentences are
// checked too (tools/check_machine_sources.py); elsewhere that one check is skipped.
//
//   node --test tests/machines.test.mjs        (ECOLI_DATASETS=DATA where the downloads lie elsewhere)
//
// Nothing needs a browser.

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { KINDS, NM, buildMachine, cite, describeMachinePart, machineDoor, noModel, problemsOf, spans } from "../src/lenses/machine_parts.js";
import { BLUR, MachineMotion, sharpness, statementOf, turnsPerFrame } from "../src/layers/machine_motion.js";
import { Shelves } from "../src/lenses/protein_shelves.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const FOLDER = "data/machines";
const FILES = readdirSync(path.join(ROOT, FOLDER)).filter((name) => name.endsWith(".json")).sort();
const motor = () => json(`${FOLDER}/ecoli.flagellar-motor.json`);
const DATASETS = process.env.ECOLI_DATASETS || "/mnt/datasets/Cells";
const SAVED = existsSync(path.join(DATASETS, "ecoli", "europepmc-open-papers", "MANIFEST.json")) && existsSync(path.join(DATASETS, "ecoli", "europepmc-motor-papers", "MANIFEST.json"));

/** A stand-in for the lens: a material for each role, and a list of what is put in the picture and under which id. */
function stand() {
  const added = [];
  return {
    added,
    ctx: {
      material: (role, options = {}) => Object.assign(new THREE.MeshStandardMaterial({ transparent: true, opacity: role === "swept" ? 0.35 : 0.9 }), { userData: { role, ...options } }),
      add: (object, id) => added.push({ object, id }),
    },
  };
}
const build = (level = 2, machine = motor()) => {
  const s = stand();
  const built = buildMachine(s.ctx, machine, { level });
  built.root.updateMatrixWorld(true);
  return { ...built, added: s.added, machine };
};
const meshesOf = (built) => {
  const list = [];
  built.root.traverse((object) => object.isMesh && list.push(object));
  return list;
};
const triangles = (built) => meshesOf(built).reduce((sum, mesh) => sum + ((mesh.geometry.index ? mesh.geometry.index.count : mesh.geometry.attributes.position.count) / 3) * (mesh.isInstancedMesh ? mesh.count : 1), 0);
/** Where an object's box lies in the machine's own frame, in nanometres. */
const boxIn = (built, object) => {
  const box = new THREE.Box3().setFromObject(object), inverse = built.root.matrixWorld.clone().invert();
  return box.applyMatrix4(inverse);
};

// ------------------------------------------------------------------ the file

test("every machine file follows its contract: format, kinds, a basis for every number, places that agree with the spans", () => {
  assert.ok(FILES.includes("ecoli.flagellar-motor.json"), FILES.join(", "));
  for (const name of FILES) assert.deepEqual(problemsOf(json(`${FOLDER}/${name}`)), [], name);
});

test("what breaks the contract is said: a part out of its place, a number with no basis or two, a rotor part that does not turn", () => {
  const broken = (change) => {
    const machine = motor();
    change(machine);
    return problemsOf(machine).join("; ");
  };
  const part = (machine, id) => machine.parts.find((item) => item.id === id);
  assert.match(broken((m) => (part(m, "atpase-ring").z_nm.nm = [-30, -26])), /atpase-ring: not within c-ring along the axis/);
  assert.match(broken((m) => (part(m, "rod").across_nm.nm = 16)), /rod does not pass through p-ring's bore/);
  assert.match(broken((m) => (part(m, "hook").turns = false)), /the parts that turn .* are not the rotor's/);
  assert.match(broken((m) => delete part(m, "c-ring").across_nm.says), /c-ring\]\.across_nm: a number with no basis/);
  assert.match(broken((m) => (part(m, "c-ring").across_nm.choice = "and also chosen")), /a number with says and choice/);
  assert.match(broken((m) => (part(m, "c-ring").kind = "sphere")), /a kind the viewer does not draw/);
  assert.match(broken((m) => (part(m, "c-ring").across_nm.says = "no-such-sentence")), /no-such-sentence, which is no sentence/);
  assert.match(broken((m) => ((m.sources.open2020 = { text: "Made up A (2020) An open paper.", doi: "10.0000/made.up", class: "no stated terms", standing: "open paper, numbers only" }), (m.sentences["n-diameters"].source = "open2020"))), /a sentence of open2020, which is not permissive/);
});

test("a species named beside a number stands in the sentence it rests on; 'not stated' means none does; it is never read from references", () => {
  const machine = motor();
  const seen = [];
  const walk = (node) => {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== "object") return;
    if (node.measured_in && node.says) {
      const text = [node.says].flat().map((key) => `${machine.sentences[key].text} ${machine.sentences[key].where || ""}`).join(" ");
      for (const word of ["Salmonella", "E. coli"]) if (node.measured_in.includes(word)) assert.ok(text.includes(word), `${node.measured_in}: ${[node.says].flat().join(", ")}`);
      if (node.measured_in === "not stated") assert.doesNotMatch([node.says].flat().map((key) => machine.sentences[key].text).join(" "), /Salmonella|E\. coli/, [node.says].flat().join(", "));
      seen.push(node.measured_in);
    }
    if (node.measured_in && node.read) assert.match(node.measured_in, /^other bacteria: /);
    Object.values(node).forEach(walk);
  };
  walk(machine.parts);
  walk(machine.layers);
  walk(machine.motion);
  for (const word of ["Salmonella", "E. coli", "E. coli and Salmonella", "not stated"]) assert.ok(seen.includes(word), word);
  // The C ring's two other widths name no species, though one of the papers behind the sentence is of Salmonella.
  assert.match(machine.parts.find((part) => part.id === "c-ring").across_nm.disagree, /names no species/);
});

test("every protein of the machine's set stands in the file once, drawn or said not to be, with its gene as the species' table has it", () => {
  const machine = motor();
  const shelves = json(`data/proteins/${machine.species}/shelves.json`);
  const at = Object.fromEntries(shelves.highlights.columns.map((name, index) => [name, index]));
  const set = new Map(shelves.highlights.rows.filter((row) => row[at.mark] === machine.set.mark && row[at.value] === machine.set.value).map((row) => [row[at.id], row[at.gene]]));
  const lines = readFileSync(path.join(ROOT, `data/proteins/${machine.species}/proteins.tsv`), "utf8").split("\n").filter(Boolean);
  const head = lines[0].split("\t");
  const genes = new Map(lines.slice(1).map((line) => line.split("\t")).map((cells) => [cells[head.indexOf("id")], cells[head.indexOf("gene")]]));
  const named = [...machine.parts.flatMap((part) => part.proteins), ...machine.not_drawn];
  assert.equal(set.size, 34);
  assert.deepEqual(named.map((item) => item.id).sort(), [...set.keys()].sort());
  for (const item of named) assert.equal(genes.get(item.id), item.gene, item.id);
  assert.equal(machine.parts.flatMap((part) => part.proteins).length, 25);
  for (const item of machine.not_drawn) assert.ok(item.why && (item.says || item.read), item.gene);
});

test("a source is permissive, or an open paper whose numbers alone are taken; such a paper gives no sentence, only a number and its place", () => {
  const machine = motor();
  for (const [key, source] of Object.entries(machine.sources)) {
    if (source.standing === "open paper, numbers only") {
      assert.equal(source.class, "no stated terms", key);
      assert.match(source.ruling, /you can use any numbers from open papers even if no licence is decrlared/, key);
      assert.ok(!Object.values(machine.sentences).some((sentence) => sentence.source === key), `${key} gives a sentence`);
    } else assert.equal(source.class, "permissive", key);
    assert.ok(source.doi || source.url, key);
  }
  // The stator unit is one body; the one saved figure for what it holds names no species.
  const stator = machine.parts.find((part) => part.id === "stator-units");
  assert.deepEqual(stator.holds.figures.map((figure) => [figure.n, figure.measured_in]), [[[4, 2], "not stated"]]);
  assert.equal(stator.subunits.of.length, 0);
  // A number read from an open paper with no licence declared: allowed with its place in the paper, from such a source alone.
  const open = motor();
  open.sources.open2020 = { text: "Made up A (2020) An open paper. Journal 1:1.", doi: "10.0000/made.up", licence: "No open licence stated: an open paper", class: "no stated terms", standing: "open paper, numbers only" };
  open.parts.find((part) => part.id === "stator-units").holds.figures.push({ text: "five and two", n: [5, 2], read: { source: "open2020", where: "its abstract", find: ["A5B2"] }, measured_in: "other bacteria: Made-up bacterium" });
  assert.deepEqual(problemsOf(open), []);
  open.parts.find((part) => part.id === "stator-units").holds.figures[1].read.source = "nakamura2019";
  assert.match(problemsOf(open).join("; "), /read from nakamura2019, which is not an open paper whose numbers alone are taken/);
  delete open.parts.find((part) => part.id === "stator-units").holds.figures[1].read.where;
  assert.match(problemsOf(open).join("; "), /read with no place in the paper/);
});

test("the saved papers still hold every sentence the file quotes, and their records the licence it gives", { skip: SAVED ? false : "the saved papers are not on this machine (set ECOLI_DATASETS)" }, () => {
  const run = spawnSync("python3", ["-I", path.join(ROOT, "tools/check_machine_sources.py"), "--datasets", DATASETS], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stdout + run.stderr);
  assert.match(run.stdout, /1 machine file\(s\), \d+ sentences and terms checked/);
});

// ------------------------------------------------------------------ the drawing

test("the machine is drawn at the file's sizes, in nanometres scaled to the view's micrometres", () => {
  const built = build(2), machine = built.machine, at = spans(machine);
  assert.equal(built.root.scale.x, NM);
  const objectsOf = (part) => built.items.find((item) => item.part === part).objects;
  const c = boxIn(built, objectsOf("c-ring")[0]);
  assert.ok(Math.abs(c.max.x - c.min.x - 45) < 0.5, `the C ring is ${c.max.x - c.min.x} nm across`);
  assert.ok(Math.abs(c.min.y + 24) < 0.01 && Math.abs(c.max.y + 4) < 0.01, `the C ring runs ${c.min.y} to ${c.max.y}`);
  // In world units: 45 nm is 0.045 µm.
  const world = new THREE.Box3().setFromObject(objectsOf("c-ring")[0]);
  assert.ok(Math.abs(world.max.x - world.min.x - 0.045) < 0.0006);
  // The envelope: the outer membrane's middle 31 nm out, the wall's about 20.75 nm.
  assert.equal(at.get("outer-membrane").mid, 31);
  assert.equal(at.get("wall").mid, 20.75);
  const outer = boxIn(built, built.items.find((item) => item.part === "outer-membrane").objects?.[0] || built.added.find((entry) => entry.id === "machine:flagellar-motor:outer-membrane").object);
  assert.ok(Math.abs(outer.min.y - 28.75) < 0.01 && Math.abs(outer.max.y - 33.25) < 0.01, `${outer.min.y} to ${outer.max.y}`);
  // Ten stator units, meeting the rotor 20 nm from the axis: their bodies' inner faces stand there.
  const units = objectsOf("stator-units")[0];
  assert.equal(units.count, 10);
  const matrix = new THREE.Matrix4(), place = new THREE.Vector3();
  for (let k = 0; k < units.count; k++) {
    units.getMatrixAt(k, matrix);
    place.setFromMatrixPosition(matrix);
    assert.ok(Math.abs(Math.hypot(place.x, place.z) - 3.5 - 20) < 1e-6, `unit ${k} at ${Math.hypot(place.x, place.z)}`);
  }
});

test("each part can be chosen under its id; the envelope too; nothing of what is not drawn is drawn", () => {
  const built = build(2), machine = built.machine;
  const ids = new Set(built.added.map((entry) => entry.id).filter(Boolean));
  for (const part of machine.parts) assert.ok(ids.has(`machine:${machine.id}:${part.id}`), part.id);
  for (const layer of machine.layers) assert.ok(ids.has(`machine:${machine.id}:${layer.id}`), layer.id);
  const proteins = new Set(built.added.map((entry) => entry.object.material?.userData?.protein).filter(Boolean));
  for (const item of machine.not_drawn) assert.ok(!proteins.has(item.id), item.gene);
  // Level 1 leaves out the parts the file draws from level 2 on.
  const outline = new Set(build(1).added.map((entry) => entry.id).filter(Boolean));
  for (const part of machine.parts) assert.equal(outline.has(`machine:${machine.id}:${part.id}`), part.levels.includes(1), part.id);
});

test("level 3 draws as many copies as the sentences give, and each set of like copies says how far apart they are", () => {
  const built = build(3);
  const counts = {};
  for (const mesh of meshesOf(built)) if (mesh.isInstancedMesh && mesh.material.userData.protein) counts[mesh.material.userData.protein] = (counts[mesh.material.userData.protein] || 0) + mesh.count;
  assert.deepEqual({ fliF: counts.P25798, fliM: counts.P06974, fliP: counts.P0AC05, fliQ: counts.P0AC07, fliR: counts.P33135, flhA: counts.P76298, fliI: counts.P52612, fliH: counts.P31068, flgE: counts.P75937 }, { fliF: 34, fliM: 34, fliP: 5, fliQ: 4, fliR: 1, flhA: 9, fliI: 6, fliH: 12, flgE: 100 });
  const periods = Object.fromEntries(built.sets.map((set) => [set.part, set.copies]));
  assert.deepEqual(periods, { "ms-ring": 34, "c-ring": 34, rod: 1, hook: 11, filament: 11 });
});

test("what a frame costs: draw calls and triangles at each level stay under a ceiling", () => {
  const costs = [1, 2, 3].map((level) => {
    const built = build(level);
    return { level, draws: meshesOf(built).length, triangles: Math.round(triangles(built)) };
  });
  for (const cost of costs) assert.ok(cost.draws <= 40 && cost.triangles <= 60000, JSON.stringify(cost));
  console.log(`# costs ${JSON.stringify(costs)}`);
});

// ------------------------------------------------------------------ the turn

test("the rotor turns the way the file says: counter-clockwise to an eye outside the cell is a positive turn about the outward axis", () => {
  const built = build(2), motion = new MachineMotion(built);
  motion.set({ turning: true, slow: 1000 });
  const mark = built.sets.find((set) => set.part === "c-ring").objects[0];
  const before = new THREE.Vector3(), after = new THREE.Vector3();
  const centre = (object) => new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3()).applyMatrix4(built.root.matrixWorld.clone().invert());
  before.copy(centre(mark));
  motion.update(16, 16, 400); // four tenths of a second of real time, slowed a thousand times
  built.root.updateMatrixWorld(true);
  after.copy(centre(mark));
  // Seen from above (+y, outside the cell), the mark moved counter-clockwise: the turn from before to after is positive.
  const turn = Math.atan2(before.z * after.x - before.x * after.z, before.x * after.x + before.z * after.z);
  assert.ok(turn > 0, `the mark turned ${turn}`);
  assert.equal(built.arrow.userData.sign, 1);
  // The hook keeps its bend: its body does not move; the parts after it turn about their own line.
  const hook = built.items.find((item) => item.part === "hook").objects[0];
  assert.equal(hook.parent, built.root);
  assert.equal(built.afterSpin.rotation.y, built.spin.rotation.y);
});

test("below the limit a mark turns by exactly rate times the real time that passed, slowed by the flux's slow-down", () => {
  const built = build(2), motion = new MachineMotion(built), rate = built.machine.motion.rotor.drawn.turns_per_s;
  motion.set({ turning: true, slow: 1000 });
  const start = motion.angle;
  // dt is capped at a tenth of a second; the real time is what passed: the angle follows the real time.
  motion.update(100, 1000, 400);
  const turned = motion.angle - start;
  assert.ok(Math.abs(turned - (2 * Math.PI * rate * 0.4) / 1000) < 1e-12, `${turned}`);
  assert.equal(built.spin.rotation.y, motion.angle);
  for (const set of built.sets.filter((item) => item.copies === 1)) assert.equal(motion.sharp.get(set), 1, set.part);
  for (const set of built.sets) for (const object of set.objects) assert.ok(object.visible, set.part);
});

test("above the limit no mark is drawn, only its swept form, so no angle can be read as a direction or a rate; nothing pops between", () => {
  const built = build(3), motion = new MachineMotion(built);
  motion.set({ turning: true, slow: 1 });
  for (let k = 0; k < 20; k++) motion.update(16, 16 * k, 1000 / 60);
  assert.ok(motion.step > 2, `${motion.step} turns a frame at real-life speed`);
  for (const set of built.sets) {
    assert.equal(motion.sharp.get(set), 0, set.part);
    for (const object of set.objects) assert.equal(object.visible, false, set.part);
    assert.ok(set.blur.visible && set.blur.material.opacity > 0, set.part);
    // The swept form is a body of revolution about the line it turns on: it has no angle of its own.
    assert.ok(["LatheGeometry", "TubeGeometry", "CylinderGeometry"].includes(set.blur.geometry.type), set.blur.geometry.type);
  }
  assert.ok(built.arrow.visible !== false, "the arrowhead shows the way");
  // The fade is smooth: no step of speed changes how sharp a set is drawn by much.
  let last = 1;
  for (let step = 0; step <= 0.2; step += 0.0005) {
    const now = sharpness(step, 1);
    assert.ok(Math.abs(now - last) < 0.02 && now <= last, `at ${step}`);
    last = now;
  }
  // A set of like copies goes over sooner: from a quarter of its spacing.
  assert.equal(sharpness(BLUR.set / 34 + 1e-9, 1 / 34), 0);
  assert.equal(sharpness((BLUR.set / 34) * BLUR.fade, 1 / 34), 1);
  assert.equal(turnsPerFrame(150, 1, 1000 / 60), 2.5);
});

test("one long frame never draws marks that moved past their limit: the step is the larger of the smoothed one and the frame's own", () => {
  const built = build(3), motion = new MachineMotion(built);
  motion.set({ turning: true, slow: 1000 });
  for (let k = 0; k < 30; k++) motion.update(16.7, k * 16.7, 1000 / 60);
  const ring = built.sets.find((set) => set.part === "c-ring");
  assert.equal(motion.sharp.get(ring), 1, "slowed a thousand times, at sixty frames a second, the blocks are sharp");
  // A frame of a tenth of a second moves the 34 blocks (150 / 1000 × 0.1 = 0.015 turns) almost half their spacing (1/34 = 0.029).
  motion.update(100, 600, 100);
  assert.ok(motion.step >= 0.015 - 1e-12, `${motion.step}`);
  assert.equal(motion.sharp.get(ring), 0);
  for (const object of ring.objects) assert.equal(object.visible, false);
  // A frame of normal length after it: the blocks come back as the smoothed step allows, never past their limit.
  motion.update(16.7, 617, 1000 / 60);
  assert.ok(sharpness(motion.step, ring.period, BLUR) === motion.sharp.get(ring));
});

test("the hook's marks turn about its own line the same way as the rotor turns about the axis", () => {
  const built = build(2), motion = new MachineMotion(built);
  motion.set({ turning: true, slow: 1000 });
  const dots = built.sets.find((set) => set.part === "hook");
  const matrix = new THREE.Matrix4(), before = new THREE.Vector3(), after = new THREE.Vector3();
  dots.objects[0].getMatrixAt(0, matrix);
  before.setFromMatrixPosition(matrix);
  motion.update(16.7, 16.7, 200);
  dots.objects[0].getMatrixAt(0, matrix);
  after.setFromMatrixPosition(matrix);
  // The first dot sits at 4% along the hook: the turn from before to after, about the hook's line there, is positive.
  const t = (0.5 / 12) * 0.92 + 0.04, centre = built.curve.getPointAt(t), tangent = built.curve.getTangentAt(t).normalize();
  const turn = new THREE.Vector3().crossVectors(before.clone().sub(centre), after.clone().sub(centre)).dot(tangent);
  assert.ok(turn > 0, `${turn}`);
  assert.ok(motion.angle > 0);
});

test("still, the rotor stands with its marks and its arrowhead; the words say so", () => {
  const built = build(2), motion = new MachineMotion(built);
  motion.set({ turning: false, slow: 1 });
  const angle = motion.angle;
  assert.equal(motion.update(16, 16, 1000), false);
  assert.equal(motion.angle, angle);
  for (const set of built.sets) {
    for (const object of set.objects) assert.ok(object.visible, set.part);
    assert.equal(set.blur.visible, false, set.part);
  }
  const words = motion.statement().join(" | ");
  assert.match(words, /^Illustration: Cells has no model of this motor \| In a run it turns counter-clockwise, seen from outside the cell · shown still/);
});

test("the picture's words: an illustration and no run, the way and where it is seen from, and the speed; never that it is too fast to follow", () => {
  const machine = motor();
  const real = statementOf(machine, { turning: true, slow: 1 }).join(" | ");
  assert.equal(real, "Illustration: not a run · Cells has no model of this motor | Turning as in a run: counter-clockwise, seen from outside the cell | At real-life speed: about 150 turns a second, as while the cell swims; up to 300, its top speed");
  const slowed = statementOf(machine, { turning: true, slow: 1000, slowSaid: "slowed 1,000 times" }).join(" | ");
  assert.match(slowed, /Slowed 1,000 times: in life about 150 turns a second/);
  assert.throws(() => statementOf(machine, { turning: true, slow: 1000 }), /the flux's own words/);
  for (const words of [real, slowed, statementOf(machine).join(" ")]) {
    assert.doesNotMatch(words, /too fast|follow|slow it down/i);
    assert.doesNotMatch(words, /\b(simulat|model)s? (the|this) motor/i);
  }
  assert.equal(noModel(machine), "Cells has no model of this motor");
});

// ------------------------------------------------------------------ the panel and the door

test("a part's panel names its proteins, says where each size comes from, and opens the atlas on those proteins", () => {
  const machine = motor();
  const panel = describeMachinePart(machine, "c-ring", { species: { label: "E. coli" }, names: { P0ABZ1: "Flagellar motor switch protein FliG" } });
  const text = JSON.stringify(panel);
  assert.equal(panel.id, "machine:flagellar-motor:c-ring");
  assert.deepEqual(panel.sections.find((section) => section.title === "Its proteins").items.map((item) => item.label), ["fliG", "fliM", "fliN"]);
  assert.match(text, /measured in Salmonella · Nakamura and Minamino 2019/);
  assert.match(text, /Flagellar motor switch protein FliG/);
  assert.match(panel.note, /^Cells has no model of this motor/);
  assert.deepEqual(panel.doors, [{ label: "Show these 3 proteins in the Protein atlas", lens: "proteins", show: "own", mark: "complex", value: "flagellum", ids: ["P0ABZ1", "P06974", "P15070"] }]);
  assert.ok(panel.sections.some((section) => section.title === "How it moves"));
  assert.match(JSON.stringify(panel.disclosures), /Diameters of the LP ring complex/);
  // A stator unit's panel gives both figures for what a unit holds, and the open paper only by its place.
  const stator = JSON.stringify(describeMachinePart(machine, "stator-units", {}));
  assert.match(stator, /four MotA and two MotB/);
  assert.match(stator, /Held still/);
  // The envelope's spacing carries its caveat under the number itself, not only in the fold of sentences; a layer has no door.
  const outer = describeMachinePart(machine, "outer-membrane", {});
  const along = outer.sections.find((section) => section.title === "Sizes").items.find((item) => item.label === "Along the axis");
  assert.ok(along.lines.some((line) => /hyperosmotic conditions, which the paper says made the distance larger/.test(line)), JSON.stringify(along));
  assert.deepEqual(outer.doors, []);
  // The filament's copies are named as the file names them.
  assert.match(JSON.stringify(describeMachinePart(machine, "filament", {})), /Copies in one flagellum/);
  // No key of the file's sentences leaks into a panel's words.
  const keys = Object.keys(machine.sentences);
  for (const id of [...machine.parts, ...machine.layers].map((item) => item.id)) {
    const words = JSON.stringify(describeMachinePart(machine, id, {}).sections);
    for (const key of keys) assert.ok(!new RegExp(`(^|[^\\w-])${key}([^\\w-]|$)`).test(words), `${id}: ${key}`);
  }
  assert.equal(machineDoor(machine, { proteins: [] }), null);
  assert.equal(cite(machine.sources.mandela2022), "Mandela and others 2022");
});

test("the Protein atlas's door may name some proteins of a set: only the markers that hold them are lit, and counted", () => {
  const data = json("data/proteins/ecoli/shelves.json");
  const shelves = new Shelves(data, { label: "E. coli" });
  const ids = new Set(["P0ABZ1", "P06974", "P15070"]);
  const all = shelves.markers.filter((item) => shelves.highlightOf(item, "complex", "flagellum").length);
  const some = shelves.markers.filter((item) => shelves.highlightOf(item, "complex", "flagellum", ids).length);
  assert.ok(some.length >= 1 && some.length < all.length, `${some.length} of ${all.length}`);
  assert.deepEqual(some.flatMap((item) => shelves.highlightOf(item, "complex", "flagellum", ids).map((protein) => protein.gene)).sort(), ["fliG", "fliM", "fliN"]);
  assert.equal(shelves.highlightTotal("complex", "flagellum"), 34);
  assert.equal(shelves.highlightTotal("complex", "flagellum", ids), 3);
  // Without ids, as before.
  assert.deepEqual(all.flatMap((item) => shelves.highlightOf(item, "complex", "flagellum")).length, 34);
});

test("the drawing names no machine and no species: what it draws is the file's", () => {
  for (const file of ["src/lenses/machine_parts.js", "src/layers/machine_motion.js"]) {
    const code = readFileSync(path.join(ROOT, file), "utf8").replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
    assert.doesNotMatch(code, /\b(coli|escherichia|salmonella|flagell\w*|mot[AB]|fli[A-Z]|flg[A-Z]|C ring|MS ring|in a run)\b/i, file);
  }
  for (const kind of new Set(motor().parts.map((part) => part.kind))) assert.ok(KINDS.includes(kind), kind);
});
